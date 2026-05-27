"""In-memory store for parsed DataFrames, shared across tools.

Avoids re-reading files and eliminates file-name matching issues.
"""
import pandas as pd

_store: dict[str, pd.DataFrame] = {}
_MAX_ENTRIES = 50


def put(table_id: str, df: pd.DataFrame) -> None:
    _store[table_id] = df
    _evict_if_needed()


def get(table_id: str) -> pd.DataFrame:
    if table_id not in _store:
        available = list(_store.keys())[:10]
        raise KeyError(f"table_id not found: {table_id}. Available: {available}")
    return _store[table_id]


def put_all(frames: dict[str, pd.DataFrame]) -> None:
    _store.update(frames)
    _evict_if_needed()


def clear() -> None:
    _store.clear()


def _evict_if_needed() -> None:
    while len(_store) > _MAX_ENTRIES:
        oldest_key = next(iter(_store))
        del _store[oldest_key]
