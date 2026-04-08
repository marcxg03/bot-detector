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


def run_detection(
    df: pd.DataFrame, cutoff: int = 95, B: int = DEFAULT_B
) -> pd.DataFrame:
    """
    Run L1P1 bot detection as described in:

    Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised
    detection of bots in a Likert-type questionnaire. Behavior Research
    Methods, 56(5), 5068-5085. doi:10.3758/s13428-023-02246-7

    The UI cutoff maps to alpha = 1 - (cutoff / 100). The paper's
    recommended alpha=0.05 corresponds to cutoff=95.
    """
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

    result = df.copy()
    result["bot_score"] = bot_scores
    result["l1p1_pvalue"] = np.round(pvalues, 4)
    result["bot_flags"] = flags_list
    result["is_flagged"] = flagged_arr.astype(bool)
    return result
