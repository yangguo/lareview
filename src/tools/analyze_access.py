import json
import os
import sys
import uuid
from pathlib import Path

from langchain.tools import tool

_workdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _workdir not in sys.path:
    sys.path.insert(0, _workdir)

from backend.matching import analyze_access
from backend.models import DuplicatePolicy
from src.tools.frame_store import get as frame_get

RUN_STORE = Path("/tmp/lareview_runs")
RUN_STORE.mkdir(parents=True, exist_ok=True)


@tool
def analyze_access_reconciliation(mapping_json: str, duplicate_policy: str = "normalized") -> str:
    """
    Run the access reconciliation analysis.

    Must be called after classify_tables and after the user confirms the mapping.
    Reads DataFrames from the in-memory cache (no file re-reading needed).

    Args:
        mapping_json: JSON string with the confirmed mapping:
            {
              "system_access_table_id": "...",
              "system_access_id_column": "...",
              "hr_active_table_id": "...",
              "hr_active_id_column": "...",
              "hr_departure_table_id": "...",
              "hr_departure_id_column": "..."
            }
        duplicate_policy: "exact" / "normalized" / "substring". Default "normalized".

    Returns:
        JSON string with analysis results (counts, previews, artifact paths).
    """
    try:
        mapping = json.loads(mapping_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "invalid mapping JSON"}, ensure_ascii=False)

    # Validate mapping has all required fields
    required = [
        "system_access_table_id", "system_access_id_column",
        "hr_active_table_id", "hr_active_id_column",
        "hr_departure_table_id", "hr_departure_id_column",
    ]
    missing = [k for k in required if not mapping.get(k)]
    if missing:
        return json.dumps({"error": f"missing mapping fields: {missing}", "hint": "请先运行 classify_tables 并确认映射关系"}, ensure_ascii=False)

    # Load DataFrames from in-memory cache (populated by ingest_files)
    try:
        system_df = frame_get(mapping["system_access_table_id"])
        hr_df = frame_get(mapping["hr_active_table_id"])
        dep_df = frame_get(mapping["hr_departure_table_id"])
    except KeyError as e:
        return json.dumps({
            "error": str(e),
            "hint": "DataFrame 缓存中找不到对应表，请确保 ingest_files 已先执行。尝试重新上传文件后再试。"
        }, ensure_ascii=False)

    # Validate ID columns exist
    for df, col, label in [
        (system_df, mapping["system_access_id_column"], "系统账号表"),
        (hr_df, mapping["hr_active_id_column"], "HR在职表"),
        (dep_df, mapping["hr_departure_id_column"], "HR离职表"),
    ]:
        if col not in df.columns:
            return json.dumps({
                "error": f"{label}中找不到列 '{col}'",
                "available_columns": list(df.columns),
            }, ensure_ascii=False)

    # Validate duplicate policy
    try:
        policy = DuplicatePolicy(duplicate_policy)
    except ValueError:
        return json.dumps({
            "error": f"无效的重复检测策略: {duplicate_policy}",
            "valid_values": ["exact", "normalized", "substring"],
        }, ensure_ascii=False)

    # Run the analysis
    try:
        missing, found_dep, dup = analyze_access(
            system_df, mapping["system_access_id_column"],
            hr_df, mapping["hr_active_id_column"],
            dep_df, mapping["hr_departure_id_column"],
            policy,
        )
    except Exception as e:
        return json.dumps({"error": f"分析执行失败: {e}"}, ensure_ascii=False)

    # Write output XLSX
    job_id = uuid.uuid4().hex
    run_dir = RUN_STORE / job_id
    run_dir.mkdir(parents=True, exist_ok=True)

    missing_path = run_dir / "missing_in_hr.xlsx"
    departure_path = run_dir / "found_in_departure.xlsx"

    try:
        missing.to_excel(missing_path, index=False, engine="openpyxl")
        found_dep.to_excel(departure_path, index=False, engine="openpyxl")
    except Exception as e:
        return json.dumps({"error": f"结果文件写入失败: {e}"}, ensure_ascii=False)

    return json.dumps({
        "job_id": job_id,
        "duplicate_policy": duplicate_policy,
        "missing_in_hr_count": missing.shape[0],
        "found_in_departure_count": found_dep.shape[0],
        "duplicate_group_count": len(dup),
        "missing_in_hr_preview": missing.astype(str).head(20).to_dict(orient="records"),
        "found_in_departure_preview": found_dep.astype(str).head(20).to_dict(orient="records"),
        "duplicate_groups": dup,
        "artifact_downloads": {
            "missing_in_hr": f"/download/{job_id}/missing_in_hr",
            "found_in_departure": f"/download/{job_id}/found_in_departure",
        },
    }, ensure_ascii=False, indent=2)
