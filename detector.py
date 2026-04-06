import numpy as np
import pandas as pd

import utils


def _build_skipped_result(row_count: int, weight: int) -> dict:
    return {
        "scores": [0.0] * row_count,
        "flags": [""] * row_count,
        "weight": weight,
        "skipped": True,
    }


def _build_result(triggered, weight: int, flag_label: str) -> dict:
    trigger_list = [bool(value) for value in triggered]
    return {
        "scores": [100.0 if is_triggered else 0.0 for is_triggered in trigger_list],
        "flags": [flag_label if is_triggered else "" for is_triggered in trigger_list],
        "weight": weight,
        "skipped": False,
    }


def _row_std_scores(df, likert_cols) -> pd.Series:
    likert_frame = df[likert_cols].apply(pd.to_numeric, errors="coerce")

    def compute_std(row: pd.Series) -> float:
        values = row.to_numpy(dtype=float)
        if np.isnan(values).all():
            return 0.0
        return float(np.nanstd(values))

    return likert_frame.apply(compute_std, axis=1)


def run_detection(df, cutoff: int) -> pd.DataFrame:
    """Run the quantitative bot-detection pipeline on a survey DataFrame."""
    likert_cols = utils.get_likert_columns(df)
    checks = [
        check_straight_lining(df, likert_cols),
        check_low_variance(df, likert_cols),
        check_range_avoidance(df, likert_cols),
        check_extreme_responding(df, likert_cols),
        check_speeder(df),
        check_duplicate_patterns(df, likert_cols),
        check_missing_patterns(df, likert_cols),
    ]

    result_df = df.copy()
    bot_scores: list[int] = []
    bot_flags: list[str] = []
    is_flagged_values: list[bool] = []

    for index in range(len(df)):
        active_checks = [check for check in checks if not check["skipped"]]
        weighted_sum = sum(check["scores"][index] * check["weight"] for check in active_checks)
        max_possible = sum(check["weight"] * 100 for check in active_checks)
        bot_score = utils.normalize_score(weighted_sum, max_possible)

        row_flags = [check["flags"][index] for check in active_checks if check["flags"][index]]
        joined_flags = ",".join(row_flags)

        bot_scores.append(bot_score)
        bot_flags.append(joined_flags)
        is_flagged_values.append(bot_score >= cutoff)

    result_df["bot_score"] = bot_scores
    result_df["bot_flags"] = bot_flags
    result_df["is_flagged"] = is_flagged_values
    return result_df


def check_straight_lining(df, likert_cols) -> dict:
    """Check for respondents who give the same Likert response repeatedly."""
    weight = 30
    if len(likert_cols) < 3:
        return _build_skipped_result(len(df), weight)

    row_stds = _row_std_scores(df, likert_cols)
    triggered = row_stds.eq(0.0).tolist()
    return _build_result(triggered, weight, "straight_lining")


def check_low_variance(df, likert_cols) -> dict:
    """Check for respondents whose Likert responses show unusually low variance."""
    weight = 25
    if len(likert_cols) < 3:
        return _build_skipped_result(len(df), weight)

    row_stds = _row_std_scores(df, likert_cols)
    threshold = float(np.percentile(row_stds.to_numpy(dtype=float), 10))
    triggered = row_stds.lt(threshold).tolist()
    return _build_result(triggered, weight, "low_variance")


def check_range_avoidance(df, likert_cols) -> dict:
    """Check for respondents who avoid using the full available Likert range."""
    weight = 15
    if len(likert_cols) < 2:
        return _build_skipped_result(len(df), weight)

    likert_frame = df[likert_cols].apply(pd.to_numeric, errors="coerce")
    non_null_values = likert_frame.to_numpy(dtype=float)
    if np.isnan(non_null_values).all():
        return _build_skipped_result(len(df), weight)

    scale_max = int(np.nanmax(non_null_values))
    if scale_max <= 5:
        middle_values = {2, 3, 4}
    else:
        middle_values = {2, 3, 4, 5, 6}

    triggered = []
    for _, row in likert_frame.iterrows():
        values = {int(value) for value in row.dropna().tolist()}
        triggered.append(not any(value in middle_values for value in values))

    return _build_result(triggered, weight, "range_avoidance")


def check_extreme_responding(df, likert_cols) -> dict:
    """Check for respondents who overuse extreme Likert responses."""
    weight = 15
    if len(likert_cols) < 2:
        return _build_skipped_result(len(df), weight)

    likert_frame = df[likert_cols].apply(pd.to_numeric, errors="coerce")
    non_null_values = likert_frame.to_numpy(dtype=float)
    if np.isnan(non_null_values).all():
        return _build_skipped_result(len(df), weight)

    scale_max = float(np.nanmax(non_null_values))
    triggered = []

    for _, row in likert_frame.iterrows():
        non_null = row.dropna()
        if non_null.empty:
            triggered.append(False)
            continue

        extreme_ratio = ((non_null == 1) | (non_null == scale_max)).mean()
        triggered.append(bool(extreme_ratio >= 0.9))

    return _build_result(triggered, weight, "extreme_responding")


def check_speeder(df) -> dict:
    """Check for respondents who appear to have completed the survey too quickly."""
    weight = 25
    duration_terms = ("duration", "time", "seconds", "elapsed")
    duration_columns = [
        column
        for column in df.columns
        if any(term in str(column).lower() for term in duration_terms)
    ]

    if not duration_columns:
        return _build_skipped_result(len(df), weight)

    duration_series = pd.to_numeric(df[duration_columns[0]], errors="coerce")
    valid_durations = duration_series.dropna()
    if valid_durations.empty:
        return _build_skipped_result(len(df), weight)

    threshold = float(np.percentile(valid_durations.to_numpy(dtype=float), 5))
    if valid_durations.nunique() == 1:
        triggered = [False] * len(df)
    else:
        triggered = duration_series.lt(threshold).fillna(False).tolist()

    return _build_result(triggered, weight, "speeder")


def check_duplicate_patterns(df, likert_cols) -> dict:
    """Check for respondents who share duplicate Likert response patterns."""
    weight = 20
    if len(df) < 2 or len(likert_cols) < 2:
        return _build_skipped_result(len(df), weight)

    likert_frame = df[likert_cols].apply(pd.to_numeric, errors="coerce")
    pattern_series = likert_frame.astype(object).where(likert_frame.notna(), "__nan__").agg(tuple, axis=1)
    pattern_counts = pattern_series.value_counts()
    triggered = pattern_series.map(pattern_counts).gt(1).tolist()
    return _build_result(triggered, weight, "duplicate_pattern")


def check_missing_patterns(df, likert_cols) -> dict:
    """Check for respondents with suspiciously patterned missing Likert data."""
    weight = 10
    if len(likert_cols) < 3:
        return _build_skipped_result(len(df), weight)

    likert_frame = df[likert_cols]
    missing_ratio = likert_frame.isna().mean(axis=1)
    triggered = missing_ratio.gt(0.5).tolist()
    return _build_result(triggered, weight, "missing_pattern")
