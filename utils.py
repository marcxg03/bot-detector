import pandas as pd
from pandas.api.types import is_object_dtype


# Column name substrings that disqualify a column from being Likert.
# Matched case-insensitively as substring of column name.
_METADATA_TERMS = (
    "id", "ip", "duration", "timestamp", "date", "time", "status",
    "progress", "finished", "recorded", "distribution", "channel",
    "token", "recipient", "location", "latitude", "longitude",
    "importid", "responseid", "score", "total", "count", "age",
    "weight", "index", "number", "num", "participant", "assignment",
    "project", "prolific", "mturk",
)


def get_likert_columns(df) -> list[str]:
    """Return the Likert-scale columns from a survey DataFrame."""
    return get_likert_columns_strict(df, max_value=7)


def get_likert_columns_strict(df: pd.DataFrame, max_value: int = 7) -> list[str]:
    """
    Return Likert-scale columns from a survey DataFrame.

    A column is included only if ALL of the following hold:
      1. Values are numeric after pd.to_numeric coercion.
      2. All non-null values are integers (no fractional part).
      3. All non-null values fall within 1–max_value inclusive.
      4. At least 2 unique non-null values (not all identical).
      5. Fewer than 8 unique non-null values.
      6. Column name does not contain a metadata keyword (case-insensitive).

    Args:
        df: Survey DataFrame.
        max_value: Upper bound of the Likert scale (default 7 for 1-7 scales;
                   pass 5 for 1-5 scales).
    """
    likert_columns: list[str] = []

    for column in df.columns:
        # Rule 6: exclude metadata columns by name substring
        col_lower = str(column).lower()
        if any(term in col_lower for term in _METADATA_TERMS):
            continue

        # Rule 1: coerce to numeric; drop non-numeric rows
        numeric = pd.to_numeric(df[column], errors="coerce")
        non_null = numeric.dropna()

        if non_null.empty:
            continue

        # Rule 2: integer values only (no fractional parts)
        if not (non_null == non_null.round()).all():
            continue

        # Rule 3: all values within 1–max_value
        if not non_null.between(1, max_value).all():
            continue

        # Rule 4: at least 2 distinct values (not all identical)
        if non_null.nunique() < 2:
            continue

        # Rule 5: fewer than 8 distinct values
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
