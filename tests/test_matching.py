from pathlib import Path

import pandas as pd

from backend.matching import analyze_access, duplicate_groups
from backend.models import DuplicatePolicy


FIX = Path(__file__).parent / "fixtures"


def test_duplicate_groups_normalized_and_substring() -> None:
    values = ["A100", "a-100", "EMPB200", "B200"]
    normalized = duplicate_groups(values, DuplicatePolicy.NORMALIZED)
    assert "a100" in normalized
    assert normalized["a100"] == [0, 1]

    substring = duplicate_groups(values, DuplicatePolicy.SUBSTRING)
    assert any(set(indexes) == {2, 3} for indexes in substring.values())


def test_analyze_access_preserves_business_outcomes() -> None:
    system_df = pd.read_csv(FIX / "system_access.csv")
    hr_df = pd.read_csv(FIX / "hr_active.csv")
    dep_df = pd.read_csv(FIX / "hr_departure.csv")

    missing, departure, duplicates = analyze_access(
        system_df,
        "user_id",
        hr_df,
        "employee_id",
        dep_df,
        "employee_id",
        DuplicatePolicy.NORMALIZED,
    )

    assert set(missing["user_id"].tolist()) == {"C300"}
    assert set(departure["user_id"].tolist()) == {"C300"}
    assert "a100" in duplicates
