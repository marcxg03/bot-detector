import pandas as pd
from pandas.api.types import is_numeric_dtype, is_object_dtype


def get_likert_columns(df) -> list[str]:
    """Return the Likert-scale columns from a survey DataFrame."""
    likert_columns: list[str] = []

    for column in df.columns:
        series = df[column]
        if not is_numeric_dtype(series):
            continue

        non_null = series.dropna()
        if non_null.empty:
            continue

        if not non_null.between(1, 7).all():
            continue

        if non_null.nunique() >= 8:
            continue

        likert_columns.append(column)

    return likert_columns


def get_text_columns(df) -> list[str]:
    """Return the free-text response columns from a survey DataFrame."""
    excluded_terms = (
        "id",
        "timestamp",
        "duration",
        "email",
        "date",
        "time",
        "ip",
        "status",
        "response_id",
    )
    text_columns: list[str] = []

    for column in df.columns:
        series = df[column]
        if not is_object_dtype(series):
            continue

        column_name = str(column).lower()
        if any(term in column_name for term in excluded_terms):
            continue

        non_null = series.dropna()
        if non_null.empty:
            continue

        mean_length = non_null.astype(str).str.len().mean()
        if pd.notna(mean_length) and mean_length > 20:
            text_columns.append(column)

    return text_columns


def normalize_score(weighted_sum: float, max_possible: float) -> int:
    """Normalize a weighted score to an integer scale."""
    if max_possible == 0:
        return 0

    return int(round((weighted_sum / max_possible) * 100))
