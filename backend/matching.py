from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .models import DuplicatePolicy


def normalize_identity(value: str) -> str:
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def duplicate_groups(values: list[str], policy: DuplicatePolicy) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    if policy == DuplicatePolicy.EXACT:
        for idx, val in enumerate(values):
            grouped[str(val)].append(idx)
    elif policy == DuplicatePolicy.NORMALIZED:
        for idx, val in enumerate(values):
            grouped[normalize_identity(val)].append(idx)
    else:
        for idx, val in enumerate(values):
            key = normalize_identity(val)
            if not key:
                continue
            matched = False
            for existing in list(grouped.keys()):
                if key in existing or existing in key:
                    grouped[existing].append(idx)
                    matched = True
                    break
            if not matched:
                grouped[key].append(idx)
    return {k: v for k, v in grouped.items() if len(v) > 1 and k}


def analyze_access(
    system_df: pd.DataFrame,
    system_id: str,
    hr_df: pd.DataFrame,
    hr_id: str,
    departure_df: pd.DataFrame,
    departure_id: str,
    duplicate_policy: DuplicatePolicy,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[int]]]:
    left = system_df.copy()
    active = hr_df.copy()
    departure = departure_df.copy()

    left["_normalized_system_id"] = left[system_id].astype(str).map(normalize_identity)
    active["_normalized_hr_id"] = active[hr_id].astype(str).map(normalize_identity)
    departure["_normalized_departure_id"] = departure[departure_id].astype(str).map(normalize_identity)

    merged_hr = pd.merge(
        left,
        active,
        left_on="_normalized_system_id",
        right_on="_normalized_hr_id",
        how="left",
    )
    merged_departure = pd.merge(
        left,
        departure,
        left_on="_normalized_system_id",
        right_on="_normalized_departure_id",
        how="inner",
    )
    missing_in_hr = merged_hr[merged_hr[hr_id].isnull()]
    duplicates = duplicate_groups(system_df[system_id].astype(str).tolist(), duplicate_policy)
    return (
        missing_in_hr.drop(columns=["_normalized_system_id", "_normalized_hr_id"], errors="ignore"),
        merged_departure.drop(columns=["_normalized_system_id", "_normalized_departure_id"], errors="ignore"),
        duplicates,
    )
