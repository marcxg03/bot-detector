import pandas as pd
import numpy as np
from itertools import groupby
from scipy.stats import chi2

import utils


WEIGHTS = {
    "longstring": 0.20,
    "irv": 0.15,
    "mahalanobis": 0.15,
    "even_odd": 0.15,
    "entropy": 0.10,
    "speeder": 0.15,
    "missing": 0.05,
}


def hard_flag_duplicate(df, likert_cols) -> pd.Series:
    """Return True for rows whose Likert response pattern is duplicated."""
    if len(likert_cols) == 0:
        return pd.Series(False, index=df.index)

    return df.duplicated(subset=likert_cols, keep=False)


def hard_flag_longstring(responses) -> bool:
    """Return True when one value dominates more than 90% of non-null responses."""
    non_null = responses.dropna()
    if len(non_null) == 0:
        return False

    longstring_ratio = non_null.value_counts().max() / len(non_null)
    return bool(longstring_ratio > 0.90)


def subscore_longstring(responses) -> float:
    """Return the longest identical consecutive run ratio for a response sequence."""
    if len(responses) == 0:
        return np.nan

    max_run = max((sum(1 for _ in group) for _, group in groupby(responses)), default=0)
    return float(max_run / len(responses))


def subscore_irv(responses, scale_min, scale_max) -> float:
    """Return an inverted within-person variability score."""
    if len(responses) == 0:
        return np.nan

    sd = np.std(responses)
    max_possible_sd = (scale_max - scale_min) / 2
    if max_possible_sd == 0:
        return 0.0

    result = 1 - (sd / max_possible_sd)
    return float(np.clip(result, 0.0, 1.0))


def subscore_mahalanobis(response_vector, all_responses) -> float:
    """Return a Mahalanobis-based anomaly subscore for one response vector."""
    if len(all_responses) < 2 or len(response_vector) < 2:
        return np.nan

    try:
        matrix = np.asarray(all_responses, dtype=float)
        vector = np.asarray(response_vector, dtype=float)

        if matrix.ndim != 2 or vector.ndim != 1:
            return np.nan

        if matrix.shape[1] != len(vector):
            return np.nan

        cov = np.cov(matrix.T)
        mean = matrix.mean(axis=0)
        VI = np.linalg.inv(cov)
        diff = vector - mean
        d2 = float(diff @ VI @ diff.T)
        p = 1 - chi2.cdf(d2, df=len(vector))
        return float(np.clip(1 - p, 0.0, 1.0))
    except (np.linalg.LinAlgError, Exception):
        return np.nan


def subscore_even_odd(responses) -> float:
    """Return the mismatch between even and odd item sequences."""
    even = responses[::2]
    odd = responses[1::2]
    min_len = min(len(even), len(odd))
    if min_len < 2:
        return 0.5

    try:
        r = np.corrcoef(even[:min_len], odd[:min_len])[0, 1]
    except Exception:
        return 0.5

    if np.isnan(r):
        return 0.5

    return float((1 - r) / 2)


def subscore_entropy(responses, scale_min, scale_max) -> float:
    """Return a normalized response-entropy irregularity score."""
    if len(responses) < 3:
        return np.nan

    scale_min = int(scale_min)
    scale_max = int(scale_max)
    n_options = scale_max - scale_min + 1
    counts = np.bincount(
        np.array(responses, dtype=int) - scale_min,
        minlength=n_options,
    )
    probs = counts / counts.sum()
    probs = probs[probs > 0]
    observed_entropy = -np.sum(probs * np.log(probs))
    max_entropy = np.log(n_options)
    if max_entropy == 0:
        return 0.0

    normalized = observed_entropy / max_entropy
    result = abs(normalized - 0.6) / 0.6
    return float(np.clip(result, 0.0, 1.0))


def subscore_speeder(response_time, expected_min_seconds=120) -> float:
    """Return a speed-based suspicion score relative to an expected minimum time."""
    try:
        value = pd.to_numeric(response_time, errors="coerce")
    except Exception:
        return np.nan

    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan

    if value >= expected_min_seconds:
        return 0.0

    return float(np.clip(1 - (value / expected_min_seconds), 0.0, 1.0))


def subscore_missing(responses) -> float:
    """Return the proportion of missing Likert responses."""
    return float(responses.isna().mean())


def composite_score(subscores: dict) -> float:
    """Return a weighted composite score from available non-missing subscores."""
    total_weight = sum(
        WEIGHTS[key] for key, value in subscores.items() if not np.isnan(value)
    )
    weighted_sum = sum(
        value * WEIGHTS[key] for key, value in subscores.items() if not np.isnan(value)
    )
    if total_weight == 0:
        return 0.0

    return float((weighted_sum / total_weight) * 100)


def run_detection(df: pd.DataFrame, cutoff: int) -> pd.DataFrame:
    """Run the redesigned quantitative bot-detection pipeline."""
    likert_cols = utils.get_likert_columns(df)
    timing_col = next(
        (
            column
            for column in df.columns
            if any(term in str(column).lower() for term in ("duration", "time", "seconds", "elapsed"))
        ),
        None,
    )

    result_df = df.copy()

    if len(likert_cols) == 0:
        result_df["bot_score"] = 0
        result_df["bot_flags"] = "no_likert_columns"
        result_df["is_flagged"] = False
        return result_df

    likert_numeric = df[likert_cols].apply(pd.to_numeric, errors="coerce")
    all_values = likert_numeric.to_numpy(dtype=float)
    scale_min = int(np.nanmin(all_values))
    scale_max = int(np.nanmax(all_values))
    duplicate_flags = hard_flag_duplicate(df, likert_cols)
    longstring_hard_flags = [
        hard_flag_longstring(likert_numeric.iloc[i]) for i in range(len(df))
    ]
    hard_flagged = duplicate_flags | pd.Series(longstring_hard_flags, index=df.index)
    clean_df = likert_numeric[~hard_flagged].dropna()
    if len(clean_df) >= 2:
        all_likert_matrix = clean_df.values
    else:
        all_likert_matrix = likert_numeric.dropna().values

    bot_scores = []
    bot_flags = []
    is_flagged = []

    for i in range(len(df)):
        responses = likert_numeric.iloc[i]
        responses_clean = responses.dropna().to_numpy(dtype=float)

        dup = bool(duplicate_flags.iloc[i])
        ls_hard = hard_flag_longstring(responses)
        hard_flag_labels = []

        if dup:
            hard_flag_labels.append("exact_duplicate")
        if ls_hard:
            hard_flag_labels.append("longstring_absolute")

        if hard_flag_labels:
            bot_scores.append(100)
            bot_flags.append(", ".join(hard_flag_labels))
            is_flagged.append(True)
            continue

        subscores = {
            "longstring": subscore_longstring(responses_clean) if len(responses_clean) >= 2 else np.nan,
            "irv": subscore_irv(responses_clean, scale_min, scale_max) if len(responses_clean) >= 2 else np.nan,
            "mahalanobis": subscore_mahalanobis(responses_clean, all_likert_matrix)
            if len(responses_clean) >= 2
            else np.nan,
            "even_odd": subscore_even_odd(responses_clean) if len(responses_clean) >= 4 else np.nan,
            "entropy": subscore_entropy(responses_clean, scale_min, scale_max)
            if len(responses_clean) >= 3
            else np.nan,
            "speeder": subscore_speeder(df.iloc[i][timing_col]) if timing_col else np.nan,
            "missing": subscore_missing(responses),
        }

        raw = composite_score(subscores)
        bot_score = int(round(np.clip(raw, 0.0, 100.0)))
        flag_labels = [
            key for key, value in subscores.items() if not np.isnan(value) and value > 0.70
        ]

        bot_scores.append(bot_score)
        bot_flags.append(", ".join(flag_labels) if flag_labels else "")
        is_flagged.append(bot_score >= cutoff)

    result_df["bot_score"] = bot_scores
    result_df["bot_flags"] = bot_flags
    result_df["is_flagged"] = is_flagged
    return result_df
