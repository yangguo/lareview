import pandas as pd

from backend.ingestion import to_candidates
from backend.sessions import RUN_STORE
from backend.workflow import DetectionWorkflow


def test_detection_workflow_generates_mapping_when_confident() -> None:
    system = pd.DataFrame({"user_id": ["A100", "B200"], "entitlement": ["x", "y"]})
    hr = pd.DataFrame({"employee_id": ["A100", "B200"], "status": ["active", "active"]})

    frames, candidates = to_candidates("fixture", [("system", system), ("hr", hr)])
    flow = DetectionWorkflow(run_store=RUN_STORE)
    resp = flow.run(session_id="s1", run_id="r1", candidates=candidates, frames=frames)

    assert resp.run_id == "r1"
    assert len(resp.classifications) == 2
    assert resp.status in {"ready", "needs_confirmation"}
