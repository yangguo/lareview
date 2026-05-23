from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .classifier import HeuristicClassifier, build_classification
from .errors import AmbiguousTableError
from .logging_utils import get_logger
from .models import CandidateTable, ClassificationResult, ConfidenceLevel, ConfirmedMapping, DetectionResponse, TableType
from .profiling import profile_table

logger = get_logger(__name__)


class WorkflowState(TypedDict, total=False):
    session_id: str
    run_id: str
    candidates: list[CandidateTable]
    frame_profiles: dict[str, dict[str, object]]
    classifications: list[ClassificationResult]
    suggested_mapping: ConfirmedMapping | None
    status: str
    requires_confirmation: bool
    errors: list[str]


class DetectionWorkflow:
    def __init__(self, run_store: Path, classifier: HeuristicClassifier | None = None) -> None:
        self.run_store = run_store
        self.classifier = classifier or HeuristicClassifier()
        graph = StateGraph(WorkflowState)
        graph.add_node("extract_candidates", self.extract_candidates)
        graph.add_node("classify_tables", self.classify_tables)
        graph.add_node("validate", self.validate)
        graph.add_node("fallback", self.fallback)
        graph.add_node("report", self.report)
        graph.set_entry_point("extract_candidates")
        graph.add_edge("extract_candidates", "classify_tables")
        graph.add_edge("classify_tables", "validate")
        graph.add_conditional_edges(
            "validate",
            self._next_step,
            {
                "fallback": "fallback",
                "report": "report",
            },
        )
        graph.add_edge("fallback", "report")
        graph.add_edge("report", END)
        self.graph = graph.compile()

    def _persist_state(self, state: WorkflowState) -> None:
        payload = {
            "session_id": state.get("session_id"),
            "run_id": state.get("run_id"),
            "status": state.get("status"),
            "requires_confirmation": state.get("requires_confirmation", False),
            "errors": state.get("errors", []),
            "classifications": [c.model_dump() for c in state.get("classifications", [])],
            "suggested_mapping": state.get("suggested_mapping").model_dump() if state.get("suggested_mapping") else None,
        }
        target = self.run_store / f"{state.get('run_id', 'unknown')}.json"
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def extract_candidates(self, state: WorkflowState) -> WorkflowState:
        return state

    def classify_tables(self, state: WorkflowState) -> WorkflowState:
        profiles = state["frame_profiles"]
        results: list[ClassificationResult] = []
        for candidate in state["candidates"]:
            profile = profiles.get(candidate.table_id, {})
            payload = self.classifier.classify(candidate, profile)
            results.append(build_classification(candidate, payload))
        state["classifications"] = results
        return state

    def validate(self, state: WorkflowState) -> WorkflowState:
        classifications = state.get("classifications", [])
        low_conf = [c for c in classifications if c.confidence_level == ConfidenceLevel.LOW]
        if low_conf:
            state["requires_confirmation"] = True
            state["status"] = "needs_confirmation"
            return state

        system = next((c for c in classifications if c.table_type == TableType.SYSTEM_ACCESS), None)
        hr_candidates = [c for c in classifications if c.table_type in {TableType.HR_ACTIVE, TableType.HR_DEPARTURE, TableType.HR_STATUS}]

        if not system or len(hr_candidates) == 0:
            state["requires_confirmation"] = True
            state["status"] = "needs_confirmation"
            state.setdefault("errors", []).append("could not deterministically map required tables")
            return state

        hr_primary = hr_candidates[0]
        mapping = ConfirmedMapping(
            system_access_table_id=system.table_id,
            system_access_id_column=system.key_columns[0] if system.key_columns else "",
            hr_active_table_id=hr_primary.table_id,
            hr_active_id_column=hr_primary.key_columns[0] if hr_primary.key_columns else "",
            hr_departure_table_id=hr_primary.table_id,
            hr_departure_id_column=hr_primary.key_columns[0] if hr_primary.key_columns else "",
        )
        state["suggested_mapping"] = mapping
        state["status"] = "ready"
        state["requires_confirmation"] = any(c.confidence_level == ConfidenceLevel.MEDIUM for c in classifications)
        return state

    def _next_step(self, state: WorkflowState) -> str:
        if state.get("requires_confirmation"):
            return "fallback"
        return "report"

    def fallback(self, state: WorkflowState) -> WorkflowState:
        if not state.get("classifications"):
            raise AmbiguousTableError("classification failed")
        state.setdefault("errors", []).append("manual confirmation required")
        state["status"] = "needs_confirmation"
        return state

    def report(self, state: WorkflowState) -> WorkflowState:
        logger.info("workflow_report", {"session_id": state.get("session_id"), "run_id": state.get("run_id")})
        self._persist_state(state)
        return state

    def run(self, *, session_id: str, run_id: str, candidates: list[CandidateTable], frames: dict[str, object]) -> DetectionResponse:
        profiles = {table_id: profile_table(frame) for table_id, frame in frames.items()}
        state: WorkflowState = {
            "session_id": session_id,
            "run_id": run_id,
            "candidates": candidates,
            "frame_profiles": profiles,
            "status": "running",
            "requires_confirmation": False,
            "errors": [],
        }
        result = self.graph.invoke(state)
        return DetectionResponse(
            session_id=session_id,
            run_id=run_id,
            status=result.get("status", "unknown"),
            classifications=result.get("classifications", []),
            suggested_mapping=result.get("suggested_mapping"),
            requires_confirmation=result.get("requires_confirmation", False),
        )
