import json
import os
import sys
from pathlib import Path

from langchain.tools import tool

_workdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _workdir not in sys.path:
    sys.path.insert(0, _workdir)

from backend.ingestion import load_tables, to_candidates
from src.tools.frame_store import put_all

# Keywords suggesting a table contains access/HR identity data
_ID_KEYS = {
    "user", "account", "login", "email", "emp", "员工", "用户", "账号", "工号",
    "name", "姓名", "depart", "离职", "入职",
    "role", "权限", "permission", "access", "entitle",
    "hire", "termination", "departure", "dept", "部门",
}
_MIN_RELEVANT_ROWS = 5


def _is_relevant(candidate: dict) -> bool:
    """Quick heuristic: does this table look like access/HR identity data?"""
    cols_lower = " ".join(candidate.get("columns", [])).lower()
    rows = candidate.get("row_count", 0)
    if rows < _MIN_RELEVANT_ROWS:
        return False
    named_cols = [c for c in candidate.get("columns", []) if not c.startswith("Col_") and c]
    if len(named_cols) < 2:
        return False
    for kw in _ID_KEYS:
        if kw in cols_lower:
            return True
    if rows >= 100:
        return True
    return False


def _compact(candidate: dict) -> dict:
    """Return a compact version without sample_rows for LLM context."""
    return {
        "table_id": candidate["table_id"],
        "source_name": candidate.get("source_name", ""),
        "columns": candidate.get("columns", []),
        "row_count": candidate.get("row_count", 0),
    }


@tool
def ingest_files(file_paths: str) -> str:
    """
    Parse uploaded CSV/XLSX/XLS files into candidate tables.

    Automatically filters out meta/reference sheets. Stores DataFrame cache
    for downstream tools (classify_tables, analyze_access_reconciliation).

    Args:
        file_paths: Comma-separated list of relative file paths.

    Returns:
        JSON with compact candidate info (no sample_rows — saved to cache instead).
    """
    workspace_path = os.getenv("COZE_WORKSPACE_PATH", os.getcwd())
    paths = [p.strip() for p in file_paths.split(",") if p.strip()]

    all_candidates: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    all_frames: dict[str, object] = {}

    for rel_path in paths:
        full_path = Path(workspace_path, rel_path).resolve()
        workspace_resolved = Path(workspace_path).resolve()
        if not str(full_path).startswith(str(workspace_resolved)):
            errors.append({"path": rel_path, "error": "path traversal detected"})
            continue
        if not full_path.exists():
            errors.append({"path": rel_path, "error": f"file not found: {full_path}"})
            continue

        try:
            raw_bytes = full_path.read_bytes()
            source_name = os.path.basename(rel_path)
            tables = load_tables(source_name, raw_bytes)
            frames, candidates = to_candidates(source_name, tables)
            all_frames.update(frames)
            for c in candidates:
                cd = c.model_dump()
                if _is_relevant(cd):
                    all_candidates.append(cd)
                else:
                    skipped.append({
                        "table_id": cd["table_id"],
                        "reason": f"filtered: {cd['row_count']} rows, cols={cd['columns'][:3]}",
                    })
        except Exception as e:
            errors.append({"path": rel_path, "error": str(e)})

    # Store DataFrames in cache for downstream tools (no file re-reading needed)
    put_all(all_frames)

    # Return compact version for LLM — no sample_rows saves ~33% tokens
    compact_candidates = [_compact(c) for c in all_candidates]

    return json.dumps({
        "candidates": compact_candidates,
        "count": len(compact_candidates),
        "skipped": len(skipped),
        "errors": [e["error"] for e in errors] if errors else [],
    }, ensure_ascii=False, indent=2)
