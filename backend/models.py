from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TableType(str, Enum):
    SYSTEM_ACCESS = "system_access"
    HR_ACTIVE = "hr_active"
    HR_DEPARTURE = "hr_departure"
    HR_STATUS = "hr_status"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CandidateTable(BaseModel):
    source_name: str
    table_id: str
    columns: list[str]
    sample_rows: list[dict[str, str]] = Field(default_factory=list)
    row_count: int


class ClassificationResult(BaseModel):
    table_id: str
    table_type: TableType
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    key_columns: list[str] = Field(default_factory=list)
    rationale: str
    missing_requirements: list[str] = Field(default_factory=list)


class ConfirmedMapping(BaseModel):
    system_access_table_id: str
    system_access_id_column: str
    hr_active_table_id: str
    hr_active_id_column: str
    hr_departure_table_id: str
    hr_departure_id_column: str


class DuplicatePolicy(str, Enum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    SUBSTRING = "substring"


class AnalysisRequest(BaseModel):
    mapping: ConfirmedMapping
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.NORMALIZED


class AnalysisResult(BaseModel):
    run_id: str
    missing_in_hr_count: int
    found_in_departure_count: int
    duplicate_group_count: int
    missing_in_hr_preview: list[dict[str, Any]] = Field(default_factory=list)
    found_in_departure_preview: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_groups: dict[str, list[int]] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class JobState(BaseModel):
    job_id: str
    status: JobStatus
    detail: str = ""
    result: AnalysisResult | None = None


class SessionCreateResponse(BaseModel):
    session_id: str


class DetectionResponse(BaseModel):
    session_id: str
    run_id: str
    status: str
    classifications: list[ClassificationResult] = Field(default_factory=list)
    suggested_mapping: ConfirmedMapping | None = None
    requires_confirmation: bool = False
