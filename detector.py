"""
Survey bot detection using the L1P1 unsupervised permutation test.

Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised
detection of bots in a Likert-type questionnaire. Behavior Research
Methods, 56(5), 5068-5085. doi:10.3758/s13428-023-02246-7
"""

import pandas as pd
import numpy as np
from joblib import Parallel, delayed
import utils


DEFAULT_ALPHA = 0.05
DEFAULT_B = 200


def hard_flag_duplicate(df, likert_cols) -> pd.Series:
    if len(likert_cols) == 0:
        return pd.Series(False, index=df.index)
    return df.duplicated(subset=likert_cols, keep=False).fillna(False)


def hard_flag_longstring(responses: np.ndarray) -> bool:
    if len(responses) == 0:
        return False
    _, counts = np.unique(responses, return_counts=True)
    return bool((counts.max() / len(responses)) > 0.90)


def hard_flag_speeder(df, timing_col: str) -> pd.Series:
    timings = pd.to_numeric(df[timing_col], errors="coerce")
    valid = timings.dropna()
    if len(valid) < 10:
        return pd.Series(False, index=df.index)
    threshold = float(valid.quantile(0.05))
    return timings.lt(threshold).fillna(False)


def _process_participant(
    pos: int, clean_matrix: np.ndarray, B: int, alpha: float
) -> tuple[float, int, bool]:
    row = clean_matrix[pos]
    other_rows = np.delete(clean_matrix, pos, axis=0)
    if len(other_rows) < 2:
        return (1.0, 0, False)

    mu = other_rows.mean(axis=0)
    cov = np.atleast_2d(np.cov(other_rows.T))
    try:
        VI = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        VI = np.linalg.pinv(cov)

    row_diff = row - mu
    orig_md = float(
        np.sqrt(max(0.0, float(row_diff @ VI @ row_diff)))
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        corr_mat = np.corrcoef(row, mu)
    orig_ptc = float(corr_mat[0, 1]) if not np.isnan(corr_mat[0, 1]) else -1.0
    orig_nri = np.array([orig_md, orig_ptc], dtype=np.float64)

    perms = np.array([np.random.permutation(row) for _ in range(B)], dtype=np.float64)

    diff = perms - mu
    quad = np.einsum("bi,ij,bj->b", diff, VI, diff)
    md_all = np.sqrt(np.maximum(0.0, quad))

    perms_c = perms - perms.mean(axis=1, keepdims=True)
    mu_c = mu - mu.mean()
    numer = perms_c @ mu_c
    denom = np.linalg.norm(perms_c, axis=1) * np.linalg.norm(mu_c)
    ptc_all = np.where(denom > 1e-10, numer / denom, -1.0)

    perm_nris = np.column_stack([md_all, ptc_all])

    try:
        Vi = np.atleast_2d(np.cov(perm_nris.T))
        Vi_inv = np.linalg.inv(Vi)
    except np.linalg.LinAlgError:
        cov_fallback = (
            np.atleast_2d(np.cov(perm_nris.T))
            if perm_nris.std(axis=0).min() > 1e-10
            else np.eye(2)
        )
        Vi_inv = np.linalg.pinv(cov_fallback)

    ideal = np.array([0.0, 1.0], dtype=np.float64)

    d = orig_nri - ideal
    dist_orig = float(np.sqrt(max(0.0, float(d @ Vi_inv @ d))))

    d_all = perm_nris - ideal
    quad_all = np.einsum("bi,ij,bj->b", d_all, Vi_inv, d_all)
    dist_all = np.sqrt(np.maximum(0.0, quad_all))

    all_dists = np.append(dist_all, dist_orig)
    pval = float(np.mean(all_dists >= dist_orig))

    score = int(round((1 - pval) * 100))
    is_flag = pval >= alpha
    return (pval, score, is_flag)


def _compute_flag_reasons(row_values, likert_cols, all_values, timing_val=None):
    """
    Generate human-readable flag reasons for an L1P1-flagged participant.
    Called after the permutation test for rows where is_flagged=True.
    Defined at module level (not nested) for consistency with _process_participant.

    Returns a comma-separated string of reasons, always ending with
    'l1p1_permutation_test' to indicate the statistical basis.
    """
    reasons = []

    # 1. Low variance relative to the rest of the sample
    sd = np.std(row_values)
    all_sds = np.std(all_values, axis=1)
    percentile_10 = np.percentile(all_sds, 10)
    if sd < percentile_10:
        reasons.append(f"low_variance (SD={sd:.2f}, bottom 10%)")

    # 2. Long consecutive run of the same response value
    max_run = 1
    current_run = 1
    for i in range(1, len(row_values)):
        if row_values[i] == row_values[i - 1]:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    run_pct = max_run / len(row_values) * 100
    if max_run >= 5:
        reasons.append(
            f"longstring_run (longest_run={max_run}, {run_pct:.0f}% of items)"
        )

    # 3. Range avoidance — uses only 1-2 distinct values across all items
    n_unique = len(np.unique(row_values))
    if n_unique <= 2:
        reasons.append(f"range_avoidance (only {n_unique} unique value(s) used)")

    # 4. Extreme responding — >= 80% of responses at scale endpoints
    scale_min = int(all_values.min())
    scale_max = int(all_values.max())
    extreme_pct = np.mean(
        (row_values == scale_min) | (row_values == scale_max)
    ) * 100
    if extreme_pct >= 80:
        reasons.append(
            f"extreme_responding ({extreme_pct:.0f}% at endpoints {scale_min}/{scale_max})"
        )

    # 5. Fast completion — if timing data available and suspiciously short
    if timing_val is not None:
        try:
            t = float(timing_val)
            if not np.isnan(t) and t < 120:
                reasons.append(
                    f"fast_completion ({int(t)}s < 120s expected minimum)"
                )
        except (ValueError, TypeError):
            pass

    # Always append the statistical basis
    reasons.append("l1p1_permutation_test")

    return ", ".join(reasons)


def _compute_eligibility_flag(df: pd.DataFrame) -> pd.Series:
    """Return 'ineligible_no_group' if Q82==3, else '' for each row."""
    if "Q82" not in df.columns:
        return pd.Series("", index=df.index)
    q82 = pd.to_numeric(df["Q82"], errors="coerce")
    return q82.apply(lambda v: "ineligible_no_group" if v == 3 else "")


def run_detection_heuristic(
    df: pd.DataFrame,
    cutoff: int = 75,
    likert_cols=None,
) -> pd.DataFrame:
    """
    Fast heuristic bot detection engine.

    Hard flags (auto-score 100, skip remaining checks):
      1. longstring_absolute: >90% same answer
      2. exact_duplicate: identical Likert pattern to another row

    Soft checks (additive, capped at 100):
      3. speeder:            duration < 120s          → +30 points
      4. low_variance:       row SD in bottom 10%     → +25 points
      5. longstring_run:     longest run > 50% items  → +20 points
      6. range_avoidance:    only 1-2 unique values   → +15 points
      7. extreme_responding: >80% at scale endpoints  → +15 points
      8. missing_data:       >50% Likert items blank  → +10 points
    """
    if likert_cols is None:
        likert_cols = utils.get_likert_columns(df)

    n_rows = len(df)

    timing_col = next(
        (col for col in df.columns
         if any(term in str(col).lower() for term in ("duration", "seconds", "elapsed"))),
        None,
    )

    if len(likert_cols) == 0:
        result = df.copy()
        result["bot_score"] = 0
        result["bot_flags"] = "no_likert_columns"
        result["is_flagged"] = False
        result["eligibility_flag"] = _compute_eligibility_flag(df)
        return result

    likert_df = df[likert_cols].apply(pd.to_numeric, errors="coerce")
    n_items = len(likert_cols)

    # Hard flag 1: longstring_absolute (>90% same answer)
    def _ls_abs(row):
        vals = row.dropna().values
        if len(vals) == 0:
            return False
        _, counts = np.unique(vals, return_counts=True)
        return bool(counts.max() / len(vals) > 0.90)

    ls_abs_flags = likert_df.apply(_ls_abs, axis=1)

    # Hard flag 2: exact_duplicate (identical Likert pattern to another row)
    dup_flags = df.duplicated(subset=likert_cols, keep=False).fillna(False)

    hard_flagged = ls_abs_flags | dup_flags

    # Speeder: fixed 120s threshold
    if timing_col:
        timings = pd.to_numeric(df[timing_col], errors="coerce")
        speeder_flags = timings.lt(120).fillna(False)
    else:
        speeder_flags = pd.Series(False, index=df.index)

    # Row standard deviations for low_variance check
    row_sds = likert_df.std(axis=1, skipna=True)
    sd_10th = row_sds.quantile(0.10)

    # Scale endpoints
    flat = likert_df.values.astype(float)
    flat_valid = flat[~np.isnan(flat)]
    scale_min = int(flat_valid.min()) if len(flat_valid) > 0 else 1
    scale_max = int(flat_valid.max()) if len(flat_valid) > 0 else 7

    bot_scores = np.zeros(n_rows, dtype=int)
    flags_list = [""] * n_rows

    for i in range(n_rows):
        if hard_flagged.iloc[i]:
            bot_scores[i] = 100
            parts = []
            if ls_abs_flags.iloc[i]:
                parts.append("longstring_absolute")
            if dup_flags.iloc[i]:
                parts.append("exact_duplicate")
            flags_list[i] = ", ".join(parts)
            continue

        score = 0
        parts = []

        # speeder
        if speeder_flags.iloc[i]:
            score += 30
            try:
                t = int(pd.to_numeric(df.iloc[i][timing_col], errors="coerce"))
                parts.append(f"speeder ({t}s < 120s)")
            except (ValueError, TypeError):
                parts.append("speeder")

        # low_variance
        sd = row_sds.iloc[i]
        if pd.notna(sd) and pd.notna(sd_10th) and sd < sd_10th:
            score += 25
            parts.append(f"low_variance (SD={sd:.2f}, bottom 10%)")

        # longstring_run (longest consecutive run > 50% of items)
        non_null = likert_df.iloc[i].dropna().values
        if len(non_null) > 1:
            max_run = 1
            cur = 1
            for j in range(1, len(non_null)):
                if non_null[j] == non_null[j - 1]:
                    cur += 1
                    max_run = max(max_run, cur)
                else:
                    cur = 1
            if max_run > len(non_null) * 0.5:
                score += 20
                parts.append(f"longstring_run (run={max_run}/{len(non_null)} items)")

        # range_avoidance (only 1-2 unique values)
        n_unique = int(pd.Series(non_null).nunique()) if len(non_null) > 0 else 0
        if 0 < n_unique <= 2:
            score += 15
            parts.append(f"range_avoidance ({n_unique} unique value(s))")

        # extreme_responding (>80% at scale endpoints)
        if len(non_null) > 0:
            ep = float(np.mean((non_null == scale_min) | (non_null == scale_max)))
            if ep > 0.80:
                score += 15
                parts.append(
                    f"extreme_responding ({ep * 100:.0f}% at endpoints "
                    f"{scale_min}/{scale_max})"
                )

        # missing_data (>50% of Likert items blank)
        n_missing = int(likert_df.iloc[i].isna().sum())
        if n_items > 0 and n_missing / n_items > 0.50:
            score += 10
            parts.append(f"missing_data ({n_missing}/{n_items} blank)")

        bot_scores[i] = min(score, 100)
        flags_list[i] = ", ".join(parts)

    result = df.copy()
    result["bot_score"] = bot_scores
    result["bot_flags"] = flags_list
    result["is_flagged"] = pd.Series(bot_scores, index=df.index) >= cutoff
    result["eligibility_flag"] = _compute_eligibility_flag(df)
    return result


def run_detection(
    df: pd.DataFrame,
    cutoff: int = 95,
    B: int = DEFAULT_B,
    likert_cols=None,
) -> pd.DataFrame:
    """
    Run L1P1 bot detection as described in:

    Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised
    detection of bots in a Likert-type questionnaire. Behavior Research
    Methods, 56(5), 5068-5085. doi:10.3758/s13428-023-02246-7

    The UI cutoff maps to alpha = 1 - (cutoff / 100). The paper's
    recommended alpha=0.05 corresponds to cutoff=95.

    Args:
        likert_cols: If provided, use these columns instead of running
                     automatic detection via utils.get_likert_columns().
                     Allows researcher-selected columns from the UI.
    """
    if likert_cols is None:
        likert_cols = utils.get_likert_columns(df)
    alpha = 1.0 - (cutoff / 100.0)
    timing_col = next(
        (
            col
            for col in df.columns
            if any(term in str(col).lower() for term in ("duration", "seconds", "elapsed"))
        ),
        None,
    )

    if len(likert_cols) == 0:
        result = df.copy()
        result["bot_score"] = 0
        result["l1p1_pvalue"] = 1.0
        result["bot_flags"] = "no_likert_columns"
        result["is_flagged"] = False
        return result

    likert_df = df[likert_cols].apply(pd.to_numeric, errors="coerce")

    # Drop rows where fewer than 10% of Likert columns are numeric.
    # Catches Qualtrics label/metadata rows that slipped through app.py.
    # Threshold kept low so legitimate participants with many skipped
    # questions are not removed.
    numeric_counts = likert_df.notna().sum(axis=1)
    numeric_mask = numeric_counts >= (len(likert_cols) * 0.1)
    if not numeric_mask.all():
        df = df[numeric_mask].reset_index(drop=True)
        likert_df = likert_df[numeric_mask].reset_index(drop=True)

    for col in likert_df.columns:
        median = likert_df[col].median()
        likert_df[col] = likert_df[col].fillna(median if not np.isnan(median) else 4.0)
    likert_matrix = likert_df.values.astype(np.float64)
    n_rows, _ = likert_matrix.shape

    dup_flags = hard_flag_duplicate(df, likert_cols)
    ls_list = [hard_flag_longstring(likert_matrix[i]) for i in range(n_rows)]
    ls_flags = pd.Series(ls_list, index=df.index)
    if timing_col:
        spd_flags = hard_flag_speeder(df, timing_col)
    else:
        spd_flags = pd.Series(False, index=df.index)
    hard_flagged = dup_flags | ls_flags | spd_flags

    clean_mask = ~hard_flagged.values
    clean_indices = np.where(clean_mask)[0]
    clean_matrix = likert_matrix[clean_mask]

    bot_scores = np.zeros(n_rows, dtype=int)
    pvalues = np.ones(n_rows, dtype=float)
    flags_list = [""] * n_rows
    flagged_arr = np.zeros(n_rows, dtype=bool)

    for i in range(n_rows):
        if hard_flagged.iloc[i]:
            bot_scores[i] = 100
            pvalues[i] = 0.0
            flagged_arr[i] = True
            parts = []
            if dup_flags.iloc[i]:
                parts.append("exact_duplicate")
            if ls_flags.iloc[i]:
                parts.append("longstring_absolute")
            if spd_flags.iloc[i]:
                parts.append("speeder")
            flags_list[i] = ", ".join(parts)

    if len(clean_indices) >= 3:
        results = Parallel(n_jobs=-1, backend="loky")(
            delayed(_process_participant)(pos, clean_matrix, B, alpha)
            for pos in range(len(clean_indices))
        )
        for pos, (pval, score, is_flag) in enumerate(results):
            idx = clean_indices[pos]
            pvalues[idx] = pval
            bot_scores[idx] = score
            flagged_arr[idx] = is_flag
            if is_flag and flags_list[idx] == "":
                timing_val = None
                if timing_col and timing_col in df.columns:
                    try:
                        timing_val = float(df.iloc[idx][timing_col])
                    except (ValueError, TypeError):
                        timing_val = None
                flags_list[idx] = _compute_flag_reasons(
                    clean_matrix[pos],
                    likert_cols,
                    clean_matrix,
                    timing_val=timing_val,
                )

    result = df.copy()
    result["bot_score"] = bot_scores
    result["l1p1_pvalue"] = np.round(pvalues, 4)
    result["bot_flags"] = flags_list
    result["is_flagged"] = flagged_arr.astype(bool)
    result["eligibility_flag"] = _compute_eligibility_flag(df)
    return result
