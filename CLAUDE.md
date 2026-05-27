# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

LA Review is an access-rights reconciliation tool that compares a system's logical-access user list against HR active/departure lists to detect: users with access but absent from HR, users found in the departure list, and duplicate account IDs. It uses a LangChain agent with heuristic (zero-token) classification and a Next.js chat frontend.

## Commands

```bash
cp .env.example .env  # edit with your OPENAI_API_KEY
pip install -r requirements.txt
python -m src.main -m http -p 8000        # starts agent FastAPI on :8000

cd frontend && npm install && npm run dev  # starts Next.js on :3000

python -m pytest -q                        # all tests
```

Set `NEXT_PUBLIC_API_URL` if the backend is not at `http://localhost:8000`.

## Architecture

**Agent** (`src/agents/agent.py`): LangChain agent with `ChatOpenAI`, 3 tools, `MemorySaver` checkpointer, sliding window of 40 messages.

**Tools** (`src/tools/`):
1. `ingest_files` — Parses uploaded CSV/XLSX/XLS files, filters irrelevant sheets, stores DataFrames in `frame_store`
2. `classify_tables` — Heuristic classifier (0 tokens) using column name keyword matching (Chinese + English)
3. `analyze_access_reconciliation` — Runs access reconciliation from in-memory cache

**Backend** (`backend/`):
- `ingestion.py`: File parsing with 10 MB limit, merged-cell title row detection, `.xls` support via xlrd
- `classifier.py`: `HeuristicClassifier` scores tables by column name keywords and value patterns
- `matching.py`: Normalizes IDs, left-joins system users against HR lists, detects duplicates
- `models.py`: Pydantic models — `CandidateTable`, `ClassificationResult`, `DuplicatePolicy`
- `errors.py`: Typed error hierarchy

**Frontend** (`frontend/`): Next.js 14 app router, single chat page (`app/page.tsx`) with SSE streaming, file upload, Markdown rendering.

**FastAPI server** (`src/main.py`): Endpoints — `/v1/chat/completions` (streaming), `/upload`, `/download/{job_id}/{artifact}`, `/health`

**Config** (`config/agent_llm_config.json`): System prompt, LLM settings, tool list.

## Key constraints

- File uploads limited to 10 MB, `.csv`/`.xlsx`/`.xls` only.
- Artifacts live under `/tmp/lareview_runs` (ephemeral).
- Heuristic classifier uses 0 LLM tokens — only final analysis/report goes to LLM.
- `frame_store` is an in-memory cache capped at 50 entries with FIFO eviction.
- Download endpoint validates `job_id` as UUID and checks path containment.
