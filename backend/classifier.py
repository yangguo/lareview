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
        columns_lower = [c.lower() for c in candidate.columns]
        user_hints = {"user", "account", "login", "email", "emp"}
        status_hints = {"status", "state", "termination", "departure", "left"}
        hr_hints = {"name", "department", "dept", "manager", "title", "hire", "dob", "phone", "address"}
        access_hints = {"entitle", "permission", "role", "access", "priv", "group"}

        has_user = any(any(t in col for t in user_hints) for col in columns_lower)
        has_status = any(any(t in col for t in status_hints) for col in columns_lower)
        has_hr = any(any(t in col for t in hr_hints) for col in columns_lower)
        has_access = any(any(t in col for t in access_hints) for col in columns_lower)

        score = 0.35
        table_type = TableType.UNKNOWN
        key_cols: list[str] = []

        if has_user:
            key_cols = [c for c in candidate.columns if any(t in c.lower() for t in user_hints)][:1]
            score += 0.25

        if has_status or has_hr or has_access:
            score += 0.25

        status_values = set(profile.get("status_values", []))

        departure_values = {"departed", "left", "terminated"}
        active_values = {"active", "inactive"}

        if has_user and has_status:
            if status_values & departure_values:
                table_type = TableType.HR_DEPARTURE
                score += 0.15
            elif status_values & active_values:
                table_type = TableType.HR_ACTIVE
                score += 0.15
            else:
                table_type = TableType.HR_STATUS
        elif has_user and not has_status:
            if has_hr and not has_access:
                table_type = TableType.HR_ACTIVE
            elif has_access and not has_hr:
                table_type = TableType.SYSTEM_ACCESS
            else:
                table_type = TableType.SYSTEM_ACCESS

        if has_user and key_cols:
            score += 0.05

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
