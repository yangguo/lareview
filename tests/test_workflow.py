import pandas as pd
import pytest

from backend.ingestion import to_candidates
from backend.models import TableType
from backend.sessions import RUN_STORE
from backend.workflow import DetectionWorkflow


def test_detection_workflow_two_tables_without_departure_needs_confirmation() -> None:
    system = pd.DataFrame({"user_id": ["A100", "B200"], "entitlement": ["x", "y"]})
    hr = pd.DataFrame({"employee_id": ["A100", "B200"], "status": ["active", "active"]})

    frames, candidates = to_candidates("fixture", [("system", system), ("hr", hr)])
    flow = DetectionWorkflow(run_store=RUN_STORE)
    resp = flow.run(session_id="s1", run_id="r1", candidates=candidates, frames=frames)

    assert resp.run_id == "r1"
    assert len(resp.classifications) == 2
    assert resp.status == "needs_confirmation"
    assert resp.requires_confirmation is True


def test_all_three_tables_produces_ready_state() -> None:
    system = pd.DataFrame({"user_id": ["A100", "B200"], "role": ["x", "y"]})
    hr_active = pd.DataFrame({"employee_id": ["A100", "B200"], "name": ["Alice", "Bob"]})
    hr_dep = pd.DataFrame({"employee_id": ["C300"], "status": ["departed"]})

    frames, candidates = to_candidates("fixture", [
        ("system", system), ("hr_active", hr_active), ("hr_departure", hr_dep),
    ])
    flow = DetectionWorkflow(run_store=RUN_STORE)
    resp = flow.run(session_id="s1", run_id="r1", candidates=candidates, frames=frames)

    assert resp.run_id == "r1"
    assert len(resp.classifications) == 3
    assert resp.status == "ready"
    assert resp.requires_confirmation is False
    assert resp.suggested_mapping is not None
    assert resp.suggested_mapping.hr_departure_table_id == "hr_departure"
    assert resp.suggested_mapping.hr_active_table_id == "hr_active"
    assert resp.suggested_mapping.system_access_table_id == "system"


def test_missing_hr_tables_requires_confirmation() -> None:
    system = pd.DataFrame({"user_id": ["A100"], "entitlement": ["x"]})

    frames, candidates = to_candidates("fixture", [("system", system)])
    flow = DetectionWorkflow(run_store=RUN_STORE)
    resp = flow.run(session_id="s1", run_id="r1", candidates=candidates, frames=frames)

    assert resp.status == "needs_confirmation"
    assert resp.requires_confirmation is True
    assert resp.suggested_mapping is None


def test_low_confidence_triggers_confirmation() -> None:
    system = pd.DataFrame({"col1": ["A", "B"], "col2": ["x", "y"], "col3": ["z", "w"]})
    hr = pd.DataFrame({"col4": ["A", "B"], "col5": ["active", "active"], "col6": ["p", "q"]})

    frames, candidates = to_candidates("fixture", [("system", system), ("hr", hr)])
    flow = DetectionWorkflow(run_store=RUN_STORE)
    resp = flow.run(session_id="s1", run_id="r1", candidates=candidates, frames=frames)

    assert resp.status == "needs_confirmation"
    assert resp.requires_confirmation is True


def test_only_active_no_departure_no_status_needs_confirmation() -> None:
    system = pd.DataFrame({"user_id": ["A100", "B200"], "entitlement": ["x", "y"]})
    hr = pd.DataFrame({"employee_id": ["A100", "B200"], "department": ["eng", "sales"]})

    frames, candidates = to_candidates("fixture", [("system", system), ("hr", hr)])
    flow = DetectionWorkflow(run_store=RUN_STORE)
    resp = flow.run(session_id="s1", run_id="r1", candidates=candidates, frames=frames)

    assert resp.status == "needs_confirmation"
    assert resp.requires_confirmation is True


def test_departure_table_with_terminated_status() -> None:
    system = pd.DataFrame({"user_id": ["A100", "B200"], "role": ["x", "y"]})
    hr_active = pd.DataFrame({"employee_id": ["A100", "B200"], "name": ["Alice", "Bob"]})
    hr_dep = pd.DataFrame({"emp_id": ["C300"], "status": ["terminated"]})

    frames, candidates = to_candidates("fixture", [
        ("system", system), ("hr_active", hr_active), ("hr_dep", hr_dep),
    ])
    flow = DetectionWorkflow(run_store=RUN_STORE)
    resp = flow.run(session_id="s1", run_id="r1", candidates=candidates, frames=frames)

    dep_class = next(c for c in resp.classifications if c.table_id == "hr_dep")
    assert dep_class.table_type == TableType.HR_DEPARTURE
    assert dep_class.confidence_level == "high"
    assert resp.status == "ready"
    assert resp.requires_confirmation is False


def test_classifier_types_for_fixture_data() -> None:
    system = pd.DataFrame({"user_id": ["A100", "B200"], "entitlement": ["x", "y"]})
    hr_active = pd.DataFrame({"employee_id": ["A100", "B200"], "department": ["eng", "sales"]})
    hr_dep = pd.DataFrame({"emp_id": ["C300"], "status": ["terminated"]})

    frames, candidates = to_candidates("fixture", [
        ("system", system), ("hr_active", hr_active), ("hr_dep", hr_dep),
    ])
    flow = DetectionWorkflow(run_store=RUN_STORE)
    resp = flow.run(session_id="s1", run_id="r1", candidates=candidates, frames=frames)

    types = {c.table_id: c.table_type for c in resp.classifications}
    assert types["system"] == TableType.SYSTEM_ACCESS
    assert types["hr_active"] == TableType.HR_ACTIVE
    assert types["hr_dep"] == TableType.HR_DEPARTURE
    for c in resp.classifications:
        assert c.confidence_level == "high", f"{c.table_id} has {c.confidence_level} confidence"
