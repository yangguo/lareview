from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .errors import EmptyDatasetError, InvalidFileError, MissingColumnError
from .ingestion import load_tables, to_candidates
from .matching import analyze_access
from .models import AnalysisRequest, AnalysisResult, ConfirmedMapping, JobState, JobStatus, SessionCreateResponse
from .sessions import RUN_STORE, SessionStore
from .workflow import DetectionWorkflow

app = FastAPI(title="lareview-agent-backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
store = SessionStore()
detection = DetectionWorkflow(run_store=RUN_STORE)


def _safe_identifier(value: str) -> str:
    return str(UUID(value))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sessions", response_model=SessionCreateResponse)
async def create_session() -> SessionCreateResponse:
    session = await store.create()
    return SessionCreateResponse(session_id=session.session_id)


@app.post("/api/sessions/{session_id}/files")
async def upload_files(session_id: UUID, files: list[UploadFile] = File(...)) -> dict[str, object]:
    session_key = _safe_identifier(str(session_id))
    try:
        session = store.get(session_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    all_candidates = []
    parsed_frames: dict[str, object] = {}
    for file in files:
        raw = await file.read()
        try:
            tables = load_tables(file.filename or "upload.csv", raw)
            frames, candidates = to_candidates(file.filename or "upload", tables)
        except (InvalidFileError, EmptyDatasetError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        parsed_frames.update(frames)
        all_candidates.extend(candidates)

    async with session.lock:
        session.tables.update(parsed_frames)
        session.candidates = all_candidates

    return {"session_id": session_key, "candidates": [c.model_dump() for c in all_candidates]}


@app.post("/api/sessions/{session_id}/detect")
async def detect_tables(session_id: UUID) -> dict[str, object]:
    session_key = _safe_identifier(str(session_id))
    try:
        session = store.get(session_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    run_id = store.next_run_id()
    async with session.lock:
        session.runs.append(run_id)
    detection_resp = detection.run(
        session_id=session_key,
        run_id=run_id,
        candidates=session.candidates,
        frames=session.tables,
    )
    return detection_resp.model_dump()


@app.post("/api/sessions/{session_id}/confirm")
async def confirm_mapping(session_id: UUID, mapping: ConfirmedMapping) -> dict[str, str]:
    session_key = _safe_identifier(str(session_id))
    try:
        session = store.get(session_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    async with session.lock:
        session.mapping = mapping
        session.mapping_confirmed = True
    return {"session_id": session_key, "status": "mapping_saved"}


async def _run_analysis(session_id: str, job_id: str, payload: AnalysisRequest) -> None:
    """Run access- reconciliation analysis as a background task.

    Design: analysis always reads the mapping from session.mapping (set by
    /confirm), not from the request payload.  The /analyze endpoint gate-
    checks session.mapping_confirmed, so a confirmed mapping must exist
    before execution reaches this point.  The payload contributes only the
    duplicate_policy — the mapping is the single confirmed source of truth.
    """
    session = store.get(session_id)

    async with session.lock:
        if not session.mapping_confirmed:
            session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.FAILED, detail="mapping not confirmed")
            return
        session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.RUNNING, detail="analysis running")

    mapping = session.mapping
    assert mapping is not None  # guaranteed by mapping_confirmed check above
    try:
        system_df = session.tables[mapping.system_access_table_id]
        hr_df = session.tables[mapping.hr_active_table_id]
        dep_df = session.tables[mapping.hr_departure_table_id]
    except KeyError as exc:
        async with session.lock:
            session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.FAILED, detail=f"missing table: {exc}")
        return

    for table, col in (
        (system_df, mapping.system_access_id_column),
        (hr_df, mapping.hr_active_id_column),
        (dep_df, mapping.hr_departure_id_column),
    ):
        if col not in table.columns:
            async with session.lock:
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

    try:
        run_dir = RUN_STORE / _safe_identifier(session_id) / _safe_identifier(job_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        missing_path = run_dir / "missing_in_hr.csv"
        departure_path = run_dir / "found_in_departure.csv"
        missing.to_csv(missing_path, index=False)
        found_dep.to_csv(departure_path, index=False)
    except (OSError, IOError) as exc:
        async with session.lock:
            session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.FAILED, detail=f"io error: {exc}")
        return

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
    async with session.lock:
        session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.DONE, detail="analysis complete", result=result)


@app.post("/api/sessions/{session_id}/analyze")
async def start_analysis(session_id: UUID, payload: AnalysisRequest) -> dict[str, str]:
    session_key = _safe_identifier(str(session_id))
    try:
        session = store.get(session_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    job_id = store.next_job_id()
    async with session.lock:
        if not session.mapping_confirmed:
            raise HTTPException(status_code=400, detail="mapping must be confirmed before analysis")
        session.jobs[job_id] = JobState(job_id=job_id, status=JobStatus.PENDING, detail="queued")
    asyncio.create_task(_run_analysis(session_key, job_id, payload))
    return {"session_id": session_key, "job_id": job_id, "status": JobStatus.PENDING.value}


@app.get("/api/sessions/{session_id}/jobs/{job_id}")
async def get_job(session_id: UUID, job_id: UUID) -> dict[str, object]:
    session_key = _safe_identifier(str(session_id))
    job_key = _safe_identifier(str(job_id))
    try:
        session = store.get(session_key)
        job = session.jobs[job_key]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    return job.model_dump()


@app.get("/api/sessions/{session_id}/jobs/{job_id}/download/{artifact}")
async def download_artifact(session_id: UUID, job_id: UUID, artifact: str) -> FileResponse:
    session_key = _safe_identifier(str(session_id))
    job_key = _safe_identifier(str(job_id))
    try:
        session = store.get(session_key)
        job = session.jobs[job_key]
        if not job.result:
            raise KeyError("result unavailable")
        path = Path(job.result.artifacts[artifact]).resolve()
        path.relative_to(RUN_STORE.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="invalid artifact path")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact file missing")
    return FileResponse(path=path, filename=path.name)


@app.get("/api/sessions/{session_id}/runs")
async def list_runs(session_id: UUID) -> dict[str, object]:
    session_key = _safe_identifier(str(session_id))
    try:
        session = store.get(session_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    return {"session_id": session_key, "runs": session.runs}
