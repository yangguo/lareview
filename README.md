---
title: Lareview
emoji: 🚀
colorFrom: yellow
colorTo: pink
sdk: streamlit
app_file: app.py
pinned: false
---

# LA Review

This repository now contains two experiences:

1. **Legacy Streamlit app** (`/app.py`) preserving the original upload-and-analyze workflow.
2. **Agent backend + Next.js frontend scaffold** for refactoring to an LLM-assisted LangGraph architecture.

## Target architecture

- **Frontend**: Next.js app in `/frontend`
- **Backend API**: FastAPI app in `/backend/api.py`
- **Agent workflow**: LangGraph pipeline in `/backend/workflow.py`
- **Deterministic analysis layer**: ingestion/profiling/matching/reporting modules in `/backend`

## Business outcomes preserved

The backend analysis still computes:
- system-access users missing in active HR list
- system-access users found in departure list
- duplicate/overlapping account IDs (exact/normalized/substring policy)

## Backend endpoints

- `POST /api/sessions`
- `POST /api/sessions/{session_id}/files`
- `POST /api/sessions/{session_id}/detect`
- `POST /api/sessions/{session_id}/confirm`
- `POST /api/sessions/{session_id}/analyze`
- `GET /api/sessions/{session_id}/jobs/{job_id}`
- `GET /api/sessions/{session_id}/jobs/{job_id}/download/{artifact}`
- `GET /api/sessions/{session_id}/runs`

## Running locally

### Python backend

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

### Next.js frontend

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` if backend is not running on `http://localhost:8000`.

## Tests

```bash
python -m pytest -q
```

Regression fixtures are under `/tests/fixtures`.
