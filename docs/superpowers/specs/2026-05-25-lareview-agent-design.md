# LA Review Agent — Design Spec

## Summary

Replace lareview's 5-step wizard with a LangChain agent behind a chat UI. User uploads files, the agent identifies table types, maps ID columns, runs reconciliation, and returns results — all through conversation.

## Architecture

Follows the audit-workpaper-agent pattern:
- `src/agents/agent.py` — `create_agent()` with ChatOpenAI, system prompt, and tools
- `src/tools/` — Three `@tool` functions wrapping existing lareview logic
- `src/main.py` — FastAPI with `/upload`, `/run`, `/stream_run`, `/v1/chat/completions`
- `config/agent_llm_config.json` — LLM settings and system prompt
- Frontend: chat UI with file upload

## Directory Structure

```
lareview/
├── config/
│   └── agent_llm_config.json
├── src/
│   ├── main.py
│   ├── agents/
│   │   └── agent.py
│   ├── tools/
│   │   ├── ingest_files.py
│   │   ├── classify_tables.py
│   │   └── analyze_access.py
│   ├── storage/
│   │   └── memory_saver.py
│   ├── utils/
│   │   └── context.py
│   └── api/
│       └── upload.py
├── backend/  (existing, reused by tools)
└── frontend/ (simplified to chat-only)
```

## Data Flow

User uploads files + sends message → Chat UI (SSE) → FastAPI /stream_run → Agent → Tools → Results streamed back as markdown.

## Tools

1. **ingest_files** — Parses CSV/XLSX via existing `backend/ingestion.py`, returns candidate tables with columns + sample rows
2. **classify_tables** — LLM reads column names and sample data, classifies tables into system_access/hr_active/hr_departure, maps ID columns
3. **analyze_access** — Takes mapping, calls existing `backend/matching.py`, returns reconciliation results

## LLM Config

Uses generic OpenAI-format env vars: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`.

## Key Decisions

- Agent decides workflow autonomously — no hard-coded wizard steps
- Tools wrap existing `backend/ingestion.py` and `backend/matching.py` — no rewrite
- Chat frontend with SSE streaming — user sees agent progress in real time
- InMemorySaver for checkpoints, graceful fallback to MemorySaver
