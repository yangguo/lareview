from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import CandidateTable, ClassificationResult, ConfidenceLevel, TableType


class TableClassifierLLM(Protocol):
    def classify(self, candidate: CandidateTable, profile: dict[str, object]) -> dict[str, object]:
        ...


@dataclass
class HeuristicClassifier:
    prompt_version: str = "v1"

    def classify(self, candidate: CandidateTable, profile: dict[str, object]) -> dict[str, object]:
        columns = [c.lower() for c in candidate.columns]
        has_user = any(any(t in col for t in ("user", "account", "login", "email", "emp")) for col in columns)
        has_status = any(any(t in col for t in ("status", "state", "termination", "depart", "left")) for col in columns)
        score = 0.4
        table_type = TableType.UNKNOWN
        key_cols: list[str] = []

        if has_user:
            key_cols = [c for c in candidate.columns if any(t in c.lower() for t in ("user", "account", "login", "email", "emp"))][:1]
            score += 0.3
        if has_status:
            score += 0.2
        status_values = profile.get("status_values", [])
        if status_values:
            score += 0.1

        if has_user and has_status:
            table_type = TableType.HR_STATUS
        elif has_user and not has_status:
            table_type = TableType.SYSTEM_ACCESS

        return {
            "table_type": table_type.value,
            "confidence": min(score, 1.0),
            "key_columns": key_cols,
            "rationale": f"heuristic classifier {self.prompt_version}",
            "missing_requirements": [] if key_cols else ["missing user/account identifier column"],
        }


def to_level(confidence: float) -> ConfidenceLevel:
    if confidence >= 0.8:
        return ConfidenceLevel.HIGH
    if confidence >= 0.55:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def build_classification(candidate: CandidateTable, payload: dict[str, object]) -> ClassificationResult:
    confidence = float(payload.get("confidence", 0.0))
    return ClassificationResult(
        table_id=candidate.table_id,
        table_type=TableType(payload.get("table_type", TableType.UNKNOWN.value)),
        confidence=confidence,
        confidence_level=to_level(confidence),
        key_columns=[str(c) for c in payload.get("key_columns", [])],
        rationale=str(payload.get("rationale", "")),
        missing_requirements=[str(c) for c in payload.get("missing_requirements", [])],
    )
