import json
import os
import sys
import uuid
from pathlib import Path

import pandas as pd
from langchain.tools import tool

_workdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _workdir not in sys.path:
    sys.path.insert(0, _workdir)

from backend.matching import analyze_access
from backend.models import DuplicatePolicy
from src.tools.frame_store import get as frame_get
import src.tools.classify_tables as _ct

RUN_STORE = Path("/tmp/lareview_runs")
RUN_STORE.mkdir(parents=True, exist_ok=True)


@tool
def analyze_access_reconciliation(mapping_json: str, duplicate_policy: str = "normalized") -> str:
    """
    Run the access reconciliation analysis.

    Must be called after classify_tables and after the user confirms the mapping.
    Reads DataFrames from the in-memory cache (no file re-reading needed).

    hr_active fields are OPTIONAL — leave empty ("") if no HR active list is available.
    In that case only departure reconciliation and duplicate detection are performed.

    Args:
        mapping_json: JSON string with the confirmed mapping:
            {
              "system_access_table_id": "...",     (required)
              "system_access_id_column": "...",     (required)
              "hr_active_table_id": "...",          (optional, "" to skip)
              "hr_active_id_column": "...",         (optional, "" to skip)
              "hr_departure_table_id": "...",       (required)
              "hr_departure_id_column": "..."       (required)
            }
        duplicate_policy: "exact" / "normalized" / "substring". Default "normalized".

    Returns:
        JSON string with analysis results (counts, previews, artifact paths).
    """
    try:
        mapping = json.loads(mapping_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "invalid mapping JSON"}, ensure_ascii=False)

    # Merge with stored mapping from classify_tables — recovers table_ids
    # if the agent lost them across conversation rounds
    if _ct._last_mapping:
        for key in ["system_access_table_id", "hr_active_table_id", "hr_departure_table_id"]:
            agent_val = mapping.get(key, "")
            stored_val = _ct._last_mapping.get(key, "")
            # Use stored table_id if agent didn't provide one or provided a bad one
            if not agent_val:
                mapping[key] = stored_val
            elif agent_val != stored_val:
                # Check if agent's table_id exists in frame_store
                try:
                    frame_get(agent_val)
                except KeyError:
                    mapping[key] = stored_val
        # Agent's column name choices always take priority
        for key in ["system_access_id_column", "hr_active_id_column", "hr_departure_id_column"]:
            if not mapping.get(key):
                mapping[key] = _ct._last_mapping.get(key, "")

    # Validate required fields (hr_active is optional)
    required = [
        "system_access_table_id", "system_access_id_column",
        "hr_departure_table_id", "hr_departure_id_column",
    ]
    missing = [k for k in required if not mapping.get(k)]
    if missing:
        return json.dumps({"error": f"missing mapping fields: {missing}", "hint": "请至少提供系统账号表和HR离职表"}, ensure_ascii=False)

    has_active = bool(mapping.get("hr_active_table_id") and mapping.get("hr_active_id_column"))

    # Load DataFrames from in-memory cache
    try:
        system_df = frame_get(mapping["system_access_table_id"])
        if has_active:
            hr_df = frame_get(mapping["hr_active_table_id"])
        else:
            hr_df = pd.DataFrame({mapping["system_access_id_column"]: []})
        dep_df = frame_get(mapping["hr_departure_table_id"])
    except KeyError as e:
        return json.dumps({
            "error": str(e),
            "hint": "DataFrame 缓存中找不到对应表，请确保 ingest_files 已先执行。"
        }, ensure_ascii=False)

    # Validate ID columns exist
    for df, col, label in [
        (system_df, mapping["system_access_id_column"], "系统账号表"),
        (dep_df, mapping["hr_departure_id_column"], "HR离职表"),
    ]:
        if col not in df.columns:
            return json.dumps({
                "error": f"{label}中找不到列 '{col}'，请检查ID列名是否正确",
                "available_columns": list(df.columns),
                "mapping_used": mapping,
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
            hr_df, mapping.get("hr_active_id_column", mapping["system_access_id_column"]),
            dep_df, mapping["hr_departure_id_column"],
            policy,
        )
    except Exception as e:
        return json.dumps({"error": f"分析执行失败: {e}", "mapping_used": mapping}, ensure_ascii=False)

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
        "missing_in_hr_count": missing.shape[0] if has_active else -1,
        "found_in_departure_count": found_dep.shape[0],
        "duplicate_group_count": len(dup),
        "missing_in_hr_preview": missing.astype(str).head(20).to_dict(orient="records") if has_active else [],
        "found_in_departure_preview": found_dep.astype(str).head(20).to_dict(orient="records"),
        "duplicate_groups": dup,
        "artifact_downloads": {
            "missing_in_hr": f"/download/{job_id}/missing_in_hr" if has_active else None,
            "found_in_departure": f"/download/{job_id}/found_in_departure",
        },
    }, ensure_ascii=False, indent=2)
