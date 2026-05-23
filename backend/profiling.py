from __future__ import annotations

import re

import pandas as pd

USER_HINTS = {"user", "userid", "account", "login", "email", "employee", "empid"}
STATUS_HINTS = {"status", "state", "active", "termination", "depart", "left"}


def profile_table(df: pd.DataFrame) -> dict[str, object]:
    columns = [c.lower() for c in df.columns]
    col_score = {
        "user_like_columns": [c for c in columns if any(h in c for h in USER_HINTS)],
        "status_like_columns": [c for c in columns if any(h in c for h in STATUS_HINTS)],
    }
    values = df.astype(str).head(50)
    id_shape = 0
    status_values: set[str] = set()
    for col in values.columns:
        for val in values[col].tolist():
            if re.fullmatch(r"[A-Za-z]{1,4}\d{2,}", str(val).strip()):
                id_shape += 1
            lower = str(val).strip().lower()
            if lower in {"active", "inactive", "terminated", "departed", "left"}:
                status_values.add(lower)
    return {
        "column_features": col_score,
        "id_shape_hits": id_shape,
        "status_values": sorted(status_values),
        "row_count": len(df),
    }
