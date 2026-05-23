from __future__ import annotations

from io import BytesIO
from typing import Iterable

import pandas as pd

from .errors import EmptyDatasetError, InvalidFileError
from .models import CandidateTable

ALLOWED_SUFFIXES = {".csv", ".xlsx"}
MAX_FILE_SIZE = 10 * 1024 * 1024


def _safe_name(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum() or ch in {"_", "-", "."})


def load_tables(filename: str, raw_bytes: bytes) -> list[tuple[str, pd.DataFrame]]:
    if len(raw_bytes) > MAX_FILE_SIZE:
        raise InvalidFileError("file exceeds maximum allowed size")
    safe_name = _safe_name(filename)
    if safe_name.endswith(".csv"):
        df = pd.read_csv(BytesIO(raw_bytes))
        return [(f"{safe_name}::csv", df)]
    if safe_name.endswith(".xlsx"):
        excel = pd.ExcelFile(BytesIO(raw_bytes))
        return [(f"{safe_name}::{sheet}", pd.read_excel(BytesIO(raw_bytes), sheet_name=sheet)) for sheet in excel.sheet_names]
    raise InvalidFileError("unsupported file type")


def normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        raise EmptyDatasetError("table has no rows")
    normalized = df.copy()
    normalized.columns = [str(c).strip() for c in normalized.columns]
    return normalized.fillna("")


def to_candidates(source_name: str, tables: Iterable[tuple[str, pd.DataFrame]]) -> tuple[dict[str, pd.DataFrame], list[CandidateTable]]:
    frames: dict[str, pd.DataFrame] = {}
    candidates: list[CandidateTable] = []
    for table_id, frame in tables:
        normalized = normalize_frame(frame)
        frames[table_id] = normalized
        candidates.append(
            CandidateTable(
                source_name=source_name,
                table_id=table_id,
                columns=[str(c) for c in normalized.columns],
                sample_rows=normalized.astype(str).head(3).to_dict(orient="records"),
                row_count=normalized.shape[0],
            )
        )
    return frames, candidates
