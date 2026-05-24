# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

LA Review is an access-rights reconciliation tool that compares a system's logical-access user list against HR active/departure lists to detect: users with access but absent from HR, users found in the departure list, and duplicate account IDs. There are two co-existing experiences: a legacy Streamlit app (`app.py`) and a new agent-based FastAPI + Next.js architecture under active development.

## Commands

```bash
# Python backend
pip install -r requirements.txt
uvicorn backend.main:app --reload          # starts FastAPI on :8000

# Next.js frontend
cd frontend && npm install && npm run dev  # starts Next.js on :3000

# Tests
python -m pytest -q                        # all tests
python -m pytest -q tests/test_matching.py # single test file
```

Set `NEXT_PUBLIC_API_URL` if the backend is not at `http://localhost:8000`.

## Architecture

**Legacy path** — `app.py` is a standalone Streamlit app. `lareview.py` provides `find_duplicate_userid()` used by the Streamlit UI.

**New backend** (`backend/`) — FastAPI app with a LangGraph detection workflow:

1. **Ingestion** (`ingestion.py`): Parses uploaded `.csv`/`.xlsx` files into DataFrames with size limits (10 MB) and safe filename sanitization. Each sheet/table becomes a `CandidateTable`.
2. **Detection** (`workflow.py`): LangGraph `StateGraph` that profiles tables, classifies them via `HeuristicClassifier`, validates the classifications, and either auto-generates a `ConfirmedMapping` or requests manual confirmation. The graph persists its state to `/tmp/lareview_runs/{run_id}.json`.
3. **Classification** (`classifier.py` + `profiling.py`): Heuristic (non-LLM) classifier scores tables by column names and value patterns. Confidence thresholds: >=0.80 auto-proceed, 0.55-0.79 suggest, <0.55 block.
4. **Confirmation** (`POST /api/sessions/{id}/confirm`): Manual mapping override before analysis can run.
5. **Analysis** (`matching.py`): Async background task (`asyncio.create_task`) that normalizes IDs, left-joins system users against HR active/departure lists, and detects duplicates under the chosen policy (`exact`/`normalized`/`substring`). Results written as CSV artifacts under `/tmp/lareview_runs/{session_id}/{job_id}/`.
6. **Sessions** (`sessions.py`): In-memory `SessionStore` protected by an `asyncio.Lock`. Sessions hold uploaded DataFrames, candidates, mapping, runs, and jobs.

**Models** (`models.py`): All Pydantic models and enums — `CandidateTable`, `ClassificationResult`, `ConfirmedMapping`, `AnalysisRequest`/`AnalysisResult`, `JobState`/`JobStatus`, `DetectionResponse`, `DuplicatePolicy`.

**Frontend** (`frontend/`) — Next.js 14 app router with a single client-side page (`app/page.tsx`) that walks through the full workflow: create session → upload files → detect tables → confirm mapping → analyze. The page imports from `../lib/api` and `../lib/types` which are not yet scaffolded. `components/RunHistory.tsx` displays run IDs.

**API flow**: `POST /api/sessions` → `POST /api/sessions/{id}/files` → `POST /api/sessions/{id}/detect` → `POST /api/sessions/{id}/confirm` → `POST /api/sessions/{id}/analyze` → poll `GET /api/sessions/{id}/jobs/{job_id}` → `GET /api/sessions/{id}/jobs/{job_id}/download/{artifact}`

**Error handling** (`errors.py`): Typed hierarchy — `LareviewError` base with `InvalidFileError`, `MissingColumnError`, `AmbiguousTableError`, `EmptyDatasetError`.

**Logging** (`logging_utils.py`): JSON-formatted structured logs with automatic redaction of PII keys (`employee_name`, `name`, `email`, `phone`, `address`).

**Session/data security** (`api.py:_safe_identifier`): All path segments are validated through `UUID()` to prevent path traversal.

## Key constraints

- Analysis is gated on confirmed table mapping — required tables and ID columns must be validated before `analyze_access` runs.
- File uploads limited to 10 MB, `.csv`/`.xlsx` only.
- Run state and artifacts live under `/tmp/lareview_runs` (ephemeral).
- The heuristic classifier uses prompt version `v1` (tracked in `classifier.py:HeuristicClassifier.prompt_version`) for future LLM migration.
