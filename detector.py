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


def hard_flag_duplicate(df, likert_cols, min_items=10) -> pd.Series:
    """
    Flag rows whose Likert response pattern is identical to at
    least one other row in the dataset.

    Two safeguards prevent false positives from legitimate dropouts:

    1. Near-constant column exclusion: columns where >80% of
       non-null values are the same single value are excluded from
       the comparison. These are screener or single-response items
       (e.g. consent, eligibility) where identical values are
       expected and carry no discriminating information.

    2. Minimum response threshold: a row must have at least
       min_items non-null values in the remaining comparison
       columns to be eligible. Rows with fewer substantive
       responses are too sparse for meaningful duplicate detection.

    Parameters
    ----------
    df : pd.DataFrame
    likert_cols : list of str
        Columns to use as the basis for duplicate detection.
        Typically the output of utils.get_likert_columns(df).
    min_items : int
        Minimum number of non-null responses in non-screener
        columns required for a row to be eligible.
        Default: 10.

    Returns
    -------
    pd.Series of bool, indexed like df.
        True where a row is a confirmed duplicate of another
        eligible row.

    References
    ----------
    Meade, A.W., & Craig, S.B. (2012). Identifying careless
    responses in survey data. Psychological Methods, 17(3),
    437-455. doi:10.1037/a0028085

    Chmielewski, M., & Kucker, S.C. (2020). An MTurk crisis?
    Social Psychological and Personality Science, 11(4), 464-473.
    doi:10.1177/1948550619875149
    """
    if len(likert_cols) == 0:
        return pd.Series(False, index=df.index)

    # Coerce all Likert columns to numeric
    likert_df = df[likert_cols].apply(pd.to_numeric, errors='coerce')

    # PART A: Identify and exclude near-constant (screener) columns
    # A column is a screener if >80% of its non-null values are
    # the same single value — these carry no discriminating info
    screener_cols = []
    for col in likert_cols:
        vals = likert_df[col].dropna()
        if len(vals) == 0:
            screener_cols.append(col)
            continue
        mode_pct = vals.value_counts().iloc[0] / len(vals)
        if mode_pct > 0.80:
            screener_cols.append(col)

    comparison_cols = [c for c in likert_cols if c not in screener_cols]

    if len(comparison_cols) == 0:
        return pd.Series(False, index=df.index)

    comparison_df = likert_df[comparison_cols]

    # PART B: Identify eligible rows (>= min_items non-null responses)
    response_counts = comparison_df.notna().sum(axis=1)
    eligible_mask = response_counts >= min_items

    # Initialize all rows as non-duplicate
    dup_flags = pd.Series(False, index=df.index)

    # Need at least 2 eligible rows to find any duplicate
    if eligible_mask.sum() < 2:
        return dup_flags

    # Run duplicate check only on eligible rows
    eligible_df = comparison_df[eligible_mask]
    dup_among_eligible = eligible_df.duplicated(keep=False)

    # Map results back to original index
    dup_flags[eligible_mask] = dup_among_eligible.values

    return dup_flags.fillna(False)


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
    cutoff: int = 75,  # retained for backward compatibility; not used in flagging
    likert_cols=None,
    speeder_threshold: int = 120,
    use_low_variance: bool = True,
    use_missing_data: bool = True,
) -> pd.DataFrame:
    """
    Fast heuristic bot detection engine.

    Any single check firing → is_flagged = True.
    bot_score = number of checks triggered (0, 1, 2, ...).

    Checks (all run for every participant — no early exit):
      1. longstring_absolute: >90% same answer
      2. exact_duplicate:     identical Likert pattern to another row
      3. speeder:             duration < speeder_threshold seconds
      4. low_variance:        row SD in bottom 10% of sample
      5. longstring_run:      longest consecutive run > 50% of items
      6. range_avoidance:     only 1–2 unique values used
      7. extreme_responding:  >80% of responses at scale endpoints
      8. missing_data:        >50% of Likert items blank
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

    # Pre-compute vectorised inputs
    dup_flags = hard_flag_duplicate(df, likert_cols, min_items=10)

    if timing_col:
        timings = pd.to_numeric(df[timing_col], errors="coerce")
    else:
        timings = pd.Series(np.nan, index=df.index)

    if use_low_variance:
        row_sds = likert_df.std(axis=1, skipna=True)
        sd_10th = row_sds.quantile(0.10)
    else:
        row_sds = None
        sd_10th = None

    flat = likert_df.values.astype(float)
    flat_valid = flat[~np.isnan(flat)]
    scale_min = int(flat_valid.min()) if len(flat_valid) > 0 else 1
    scale_max = int(flat_valid.max()) if len(flat_valid) > 0 else 7

    bot_scores = np.zeros(n_rows, dtype=int)
    flags_list = [""] * n_rows
    flagged_arr = np.zeros(n_rows, dtype=bool)

    for i in range(n_rows):
        flag_parts = []
        non_null = likert_df.iloc[i].dropna().values

        # 1. longstring_absolute (>90% same answer)
        if len(non_null) > 0:
            _, counts = np.unique(non_null, return_counts=True)
            if counts.max() / len(non_null) > 0.90:
                flag_parts.append("longstring_absolute")

        # 2. exact_duplicate
        if dup_flags.iloc[i]:
            flag_parts.append("exact_duplicate")

        # 3. speeder
        t_val = timings.iloc[i]
        if pd.notna(t_val):
            try:
                t = float(t_val)
                if t < speeder_threshold:
                    flag_parts.append(f"speeder ({int(t)}s < {speeder_threshold}s)")
            except (ValueError, TypeError):
                pass

        # 4. low_variance (row SD in bottom 10%) — optional
        if use_low_variance:
            sd = row_sds.iloc[i]
            if pd.notna(sd) and pd.notna(sd_10th) and sd < sd_10th:
                flag_parts.append(f"low_variance (SD={sd:.2f})")

        # 5. longstring_run (longest consecutive run > 50% of items)
        if len(non_null) > 1:
            max_run = 1
            cur = 1
            for j in range(1, len(non_null)):
                if non_null[j] == non_null[j - 1]:
                    cur += 1
                    max_run = max(max_run, cur)
                else:
                    cur = 1
            run_pct = max_run / len(non_null)
            if run_pct > 0.50:
                flag_parts.append(
                    f"longstring_run ({max_run} consecutive, {run_pct * 100:.0f}%)"
                )

        # 6. range_avoidance (only 1–2 unique values)
        n_unique = int(pd.Series(non_null).nunique()) if len(non_null) > 0 else 0
        if 0 < n_unique <= 2:
            flag_parts.append(f"range_avoidance ({n_unique} unique values)")

        # 7. extreme_responding (>80% at scale endpoints)
        if len(non_null) > 0:
            extreme_pct = float(
                np.mean((non_null == scale_min) | (non_null == scale_max))
            )
            if extreme_pct >= 0.80:
                flag_parts.append(
                    f"extreme_responding ({extreme_pct * 100:.0f}% at endpoints)"
                )

        # 8. missing_data (>50% of Likert items blank) — optional
        if use_missing_data:
            n_missing = int(likert_df.iloc[i].isna().sum())
            if n_items > 0 and n_missing / n_items > 0.50:
                flag_parts.append(f"missing_data ({n_missing}/{n_items} blank)")

        # Any flag = flagged; bot_score = flag count
        bot_scores[i] = len(flag_parts)
        flags_list[i] = ", ".join(flag_parts)
        flagged_arr[i] = len(flag_parts) > 0

    result = df.copy()
    result["bot_score"] = bot_scores
    result["bot_flags"] = flags_list
    result["is_flagged"] = flagged_arr.astype(bool)
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

    dup_flags = hard_flag_duplicate(df, likert_cols, min_items=10)
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
