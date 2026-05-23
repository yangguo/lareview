from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import uuid

import pandas as pd

from .models import CandidateTable, JobState

RUN_STORE = Path("/tmp/lareview_runs")
RUN_STORE.mkdir(parents=True, exist_ok=True)


@dataclass
class SessionState:
    session_id: str
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    candidates: list[CandidateTable] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)
    runs: list[str] = field(default_factory=list)
    jobs: dict[str, JobState] = field(default_factory=dict)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> SessionState:
        async with self._lock:
            session_id = str(uuid.uuid4())
            state = SessionState(session_id=session_id)
            self._sessions[session_id] = state
            return state

    def get(self, session_id: str) -> SessionState:
        return self._sessions[session_id]

    @staticmethod
    def next_run_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def next_job_id() -> str:
        return str(uuid.uuid4())
