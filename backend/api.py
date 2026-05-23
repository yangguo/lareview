from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .errors import EmptyDatasetError, InvalidFileError, MissingColumnError
from .ingestion import load_tables, to_candidates
from .matching import analyze_access
from .models import AnalysisRequest, AnalysisResult, JobState, JobStatus, SessionCreateResponse
from .sessions import RUN_STORE, SessionStore
from .workflow import DetectionWorkflow

app = FastAPI(title="lareview-agent-backend", version="0.1.0")
store = SessionStore()
detection = DetectionWorkflow(run_store=RUN_STORE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sessions", response_model=SessionCreateResponse)
async def create_session() -> SessionCreateResponse:
    session = await store.create()
    return SessionCreateResponse(session_id=session.session_id)


@app.post("/api/sessions/{session_id}/files")
async def upload_files(session_id: str, files: list[UploadFile] = File(...)) -> dict[str, object]:
    try:
        session = store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    all_candidates = []
    for file in files:
        raw = await file.read()
        try:
            tables = load_tables(file.filename or "upload.csv", raw)
            frames, candidates = to_candidates(file.filename or "upload", tables)
        except (InvalidFileError, EmptyDatasetError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session.tables.update(frames)
        all_candidates.extend(candidates)

    session.candidates = all_candidates
    return {"session_id": session_id, "candidates": [c.model_dump() for c in all_candidates]}


@app.post("/api/sessions/{session_id}/detect")
async def detect_tables(session_id: str) -> dict[str, object]:
    try:
        session = store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    run_id = store.next_run_id()
    session.runs.append(run_id)
    detection_resp = detection.run(
        session_id=session_id,
        run_id=run_id,
        candidates=session.candidates,
        frames=session.tables,
    )
    return detection_resp.model_dump()


@app.post("/api/sessions/{session_id}/confirm")
async def confirm_mapping(session_id: str, mapping: dict[str, str]) -> dict[str, str]:
    try:
        session = store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    session.mapping = mapping
    return {"session_id": session_id, "status": "mapping_saved"}


async def _run_analysis(session_id: str, job_id: str, payload: AnalysisRequest) -> None:
    session = store.get(session_id)
    session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.RUNNING, detail="analysis running")

    mapping = payload.mapping
    try:
        system_df = session.tables[mapping.system_access_table_id]
        hr_df = session.tables[mapping.hr_active_table_id]
        dep_df = session.tables[mapping.hr_departure_table_id]
    except KeyError as exc:
        session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.FAILED, detail=f"missing table: {exc}")
        return

    for table, col in (
        (system_df, mapping.system_access_id_column),
        (hr_df, mapping.hr_active_id_column),
        (dep_df, mapping.hr_departure_id_column),
    ):
        if col not in table.columns:
            session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.FAILED, detail=str(MissingColumnError(col)))
            return

    missing, found_dep, dup = analyze_access(
        system_df,
        mapping.system_access_id_column,
        hr_df,
        mapping.hr_active_id_column,
        dep_df,
        mapping.hr_departure_id_column,
        payload.duplicate_policy,
    )

    run_dir = RUN_STORE / session_id / job_id
    run_dir.mkdir(parents=True, exist_ok=True)
    missing_path = run_dir / "missing_in_hr.csv"
    departure_path = run_dir / "found_in_departure.csv"
    missing.to_csv(missing_path, index=False)
    found_dep.to_csv(departure_path, index=False)

    result = AnalysisResult(
        run_id=job_id,
        missing_in_hr_count=missing.shape[0],
        found_in_departure_count=found_dep.shape[0],
        duplicate_group_count=len(dup),
        missing_in_hr_preview=missing.astype(str).head(20).to_dict(orient="records"),
        found_in_departure_preview=found_dep.astype(str).head(20).to_dict(orient="records"),
        duplicate_groups=dup,
        artifacts={"missing_in_hr": str(missing_path), "found_in_departure": str(departure_path)},
    )
    session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.DONE, detail="analysis complete", result=result)


@app.post("/api/sessions/{session_id}/analyze")
async def start_analysis(session_id: str, payload: AnalysisRequest) -> dict[str, str]:
    try:
        session = store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    job_id = store.next_job_id()
    session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.PENDING, detail="queued")
    asyncio.create_task(_run_analysis(session_id, job_id, payload))
    return {"session_id": session_id, "job_id": job_id, "status": JobStatus.PENDING.value}


@app.get("/api/sessions/{session_id}/jobs/{job_id}")
async def get_job(session_id: str, job_id: str) -> dict[str, object]:
    try:
        session = store.get(session_id)
        job = session.jobs[job_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    return job.model_dump()


@app.get("/api/sessions/{session_id}/jobs/{job_id}/download/{artifact}")
async def download_artifact(session_id: str, job_id: str, artifact: str) -> FileResponse:
    try:
        session = store.get(session_id)
        job = session.jobs[job_id]
        if not job.result:
            raise KeyError("result unavailable")
        path = Path(job.result.artifacts[artifact])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact file missing")
    return FileResponse(path=path, filename=path.name)


@app.get("/api/sessions/{session_id}/runs")
async def list_runs(session_id: str) -> dict[str, object]:
    try:
        session = store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    return {"session_id": session_id, "runs": session.runs}
