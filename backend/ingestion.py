from __future__ import annotations

from io import BytesIO
from typing import Iterable

import pandas as pd

from .errors import EmptyDatasetError, InvalidFileError
from .models import CandidateTable

ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}
MAX_FILE_SIZE = 10 * 1024 * 1024


def _safe_name(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum() or ch in {"_", "-", "."})


def _read_excel(raw_bytes: bytes, filename: str) -> list[tuple[str, pd.DataFrame]]:
    """Read all sheets from an Excel file, skipping empty ones.

    Handles .xls (xlrd engine) and .xlsx (openpyxl engine).
    Auto-detects header rows when the first row appears to be data rather than column names.
    """
    safe_name = _safe_name(filename)
    engine = "xlrd" if safe_name.endswith(".xls") else "openpyxl"

    try:
        excel = pd.ExcelFile(BytesIO(raw_bytes), engine=engine)
    except Exception:
        raise InvalidFileError(f"cannot open file as {engine}")

    tables: list[tuple[str, pd.DataFrame]] = []

    for sheet in excel.sheet_names:
        try:
            raw = pd.read_excel(BytesIO(raw_bytes), sheet_name=sheet, dtype=str, engine=engine)
        except Exception:
            continue
        if raw.empty:
            continue

        # Detect if the first row looks like a title row rather than real headers.
        #   (a) "Unnamed: N" or pure digits → pandas didn't find headers
        #   (b) Many ".N" suffixes → pandas deduplicated identical title-row values
        cols_raw = [str(c) for c in raw.columns]
        import re as _re
        unnamed_count = sum(1 for c in cols_raw if "unnamed" in str(c).lower() or str(c).isdigit())
        deduped_count = sum(1 for c in cols_raw if _re.search(r"\.\d+$", str(c)))

        if unnamed_count >= len(raw.columns) * 0.7 or deduped_count >= len(raw.columns) * 0.5:
            # Re-read without header, then scan for the real header row
            df = pd.read_excel(BytesIO(raw_bytes), sheet_name=sheet, header=None, dtype=str, engine=engine)
            header_row = 0
            for row_idx in range(min(15, len(df))):
                row_vals = [str(v).strip() for v in df.iloc[row_idx].tolist()]
                non_empty = sum(1 for v in row_vals if v and v != "nan")
                non_numeric = sum(1 for v in row_vals if v and v != "nan" and not v.replace(".", "").replace("-", "").replace("%", "").isdigit())
                if non_empty < 2:
                    continue
                # Skip merged-cell title rows: if most non-empty values are identical, it's a title not a header
                unique_vals = {v for v in row_vals if v and v != "nan"}
                if len(unique_vals) <= non_empty * 0.4:
                    continue
                if non_numeric >= non_empty * 0.5:
                    header_row = row_idx
                    break

            if header_row > 0:
                df.columns = [
                    str(v).strip() if str(v).strip() != "nan" and str(v).strip() != "" else f"Col_{i}"
                    for i, v in enumerate(df.iloc[header_row].tolist())
                ]
                df = df.iloc[header_row + 1:].reset_index(drop=True)
            else:
                df.columns = [f"Col_{i}" for i in range(len(df.columns))]

            if df.empty:
                continue
        else:
            df = raw

        tables.append((f"{safe_name}::{sheet}", df))

    if not tables:
        raise InvalidFileError("no readable sheets with data found in file")
    return tables


def load_tables(filename: str, raw_bytes: bytes) -> list[tuple[str, pd.DataFrame]]:
    if len(raw_bytes) > MAX_FILE_SIZE:
        raise InvalidFileError("file exceeds maximum allowed size")
    safe_name = _safe_name(filename)
    if safe_name.endswith(".csv"):
        df = pd.read_csv(BytesIO(raw_bytes))
        return [(f"{safe_name}::csv", df)]
    if safe_name.endswith((".xlsx", ".xls")):
        return _read_excel(raw_bytes, filename)
    raise InvalidFileError("unsupported file type")


def normalize_frame(df: pd.DataFrame) -> pd.DataFrame | None:
    if df.empty:
        return None
    normalized = df.copy()
    normalized.columns = [str(c).strip() for c in normalized.columns]
    return normalized.fillna("")


def to_candidates(source_name: str, tables: Iterable[tuple[str, pd.DataFrame]]) -> tuple[dict[str, pd.DataFrame], list[CandidateTable]]:
    frames: dict[str, pd.DataFrame] = {}
    candidates: list[CandidateTable] = []
    for table_id, frame in tables:
        normalized = normalize_frame(frame)
        if normalized is None:
            continue
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
