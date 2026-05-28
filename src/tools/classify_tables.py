import json
import os
import sys

from langchain.tools import tool

_workdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _workdir not in sys.path:
    sys.path.insert(0, _workdir)

from backend.models import CandidateTable
from backend.profiling import profile_table
from backend.classifier import HeuristicClassifier, build_classification
from src.tools.frame_store import get as frame_get

classifier = HeuristicClassifier()

# Module-level store so analyze_access_reconciliation can recover table_ids
_last_mapping: dict[str, str] = {}


@tool
def classify_tables(candidates_json: str) -> str:
    """
    Classify candidate tables by type and identify the user/employee ID column.

    Uses fast heuristic classifier (0 tokens). Reads DataFrames from cache
    populated by ingest_files — no file re-reading needed.

    Args:
        candidates_json: JSON string from ingest_files output.

    Returns:
        JSON with classifications, suggested mapping, and confidence levels.
    """
    try:
        data = json.loads(candidates_json)
        if isinstance(data, dict) and "candidates" in data:
            candidates = data["candidates"]
        else:
            candidates = data
    except json.JSONDecodeError:
        return json.dumps({"error": "invalid JSON input"}, ensure_ascii=False)

    if not candidates:
        return json.dumps({"error": "no candidate tables to classify"}, ensure_ascii=False)

    classifications = []
    for cd in candidates:
        table_id = cd["table_id"]
        try:
            df = frame_get(table_id)
            profile = profile_table(df)
            candidate_obj = CandidateTable(
                source_name=cd.get("source_name", ""),
                table_id=table_id,
                columns=cd.get("columns", []),
                sample_rows=[],  # not needed — profiler uses the DataFrame directly
                row_count=cd.get("row_count", 0),
            )
            result = classifier.classify(candidate_obj, profile)
            classification = build_classification(candidate_obj, result)
            cdump = classification.model_dump()
            cdump["row_count"] = cd.get("row_count", 0)
            classifications.append(cdump)
        except KeyError:
            classifications.append({
                "table_id": table_id,
                "table_type": "unknown",
                "confidence": 0.0,
                "confidence_level": "low",
                "key_columns": [],
                "rationale": "DataFrame not found in cache — ingest_files may not have processed this file",
                "missing_requirements": ["frame not in cache"],
            })
        except Exception as e:
            classifications.append({
                "table_id": table_id,
                "table_type": "unknown",
                "confidence": 0.0,
                "confidence_level": "low",
                "key_columns": [],
                "rationale": f"classification failed: {e}",
                "missing_requirements": [str(e)],
            })

    # Build suggested mapping from highest-confidence table per type
    mapping: dict[str, str] = {
        "system_access_table_id": "",
        "system_access_id_column": "",
        "hr_active_table_id": "",
        "hr_active_id_column": "",
        "hr_departure_table_id": "",
        "hr_departure_id_column": "",
    }

    best: dict[str, dict] = {}
    for c in classifications:
        ttype = c.get("table_type", "unknown")
        if ttype == "unknown":
            continue
        if ttype not in best:
            best[ttype] = c
        else:
            curr = best[ttype]
            new_conf = c.get("confidence", 0)
            old_conf = curr.get("confidence", 0)
            if new_conf > old_conf + 0.15:
                best[ttype] = c
            elif abs(new_conf - old_conf) <= 0.15 and c.get("row_count", 0) > curr.get("row_count", 0):
                best[ttype] = c

    for ttype, key in [
        ("system_access", ("system_access_table_id", "system_access_id_column")),
        ("hr_active", ("hr_active_table_id", "hr_active_id_column")),
        ("hr_departure", ("hr_departure_table_id", "hr_departure_id_column")),
    ]:
        if ttype in best:
            mapping[key[0]] = best[ttype]["table_id"]
            mapping[key[1]] = (best[ttype].get("key_columns", [""]) or [""])[0]

    # Store mapping so analyze_access_reconciliation can recover table_ids
    # even if the agent loses them across conversation rounds
    global _last_mapping
    _last_mapping = dict(mapping)

    requires_confirmation = any(
        c.get("confidence_level") in ("low", "medium") for c in classifications
    )

    return json.dumps({
        "classifications": classifications,
        "suggested_mapping": mapping,
        "requires_confirmation": requires_confirmation,
    }, ensure_ascii=False, indent=2)
