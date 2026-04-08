# SLICE_2D_L1P1_ENGINE.md
# Survey Bot Detector
# Oishi Lab — Marcus Gao

---

## Goal

Replace the current detection engine in `detector.py` with the
scientifically validated L1P1 algorithm (Ilagan & Falk, 2024,
*Behavior Research Methods*), optimized for performance using
vectorized NumPy operations and joblib parallelism across CPU cores.

Target runtime: under 60 seconds for datasets up to 500 participants
with 200 Likert items (compared to 3–5 minutes for a naive loop).

---

## Scientific Basis

**Primary citation:**
Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised
detection of bots in a Likert-type questionnaire. *Behavior Research
Methods, 56*(5), 5068–5085. https://doi.org/10.3758/s13428-023-02246-7

**Validation citation:**
Falk, C. F., Huang, A., & Ilagan, M. J. (2025). Unsupervised [randomly
responding] survey bot detection: In search of high classification
accuracy. *Psychological Methods*. https://doi.org/10.1037/met0000746

**Open source reference implementation:**
R package `detranli` — github.com/michaeljohnilagan/detranli
OSF code — osf.io/e5v3s

---

## What Changes From Slice 2C

The Slice 2B/2C engine used a composite of heuristic subscores with
arbitrary weights. L1P1 replaces this with a permutation test that
outputs a proper p-value with guaranteed 95% sensitivity.

This slice also adds two performance optimizations not in the original
spec:
1. **Vectorized permutation NRI computation** — all B=200 permutations
   computed in one NumPy matrix operation rather than a Python loop
2. **Joblib parallel processing** — each participant's permutation test
   runs on a separate CPU core simultaneously

Combined, these reduce runtime from ~5 minutes to ~30–60 seconds on
real Oishi Lab datasets (350–422 participants, 100–177 Likert items).

---

## Acceptance Criteria

1. `detector.py` implements L1P1 with LOO anchors and permutations
2. All permutation NRI computations are vectorized (no Python for-loop
   over individual permutations)
3. Participant-level parallelism uses `joblib.Parallel` with
   `n_jobs=-1` (all available CPU cores)
4. Hard flags (exact duplicate, longstring absolute, speeder) retained
   as Layer 1 — bypass L1P1, auto-assign is_flagged=True
5. Output columns: `bot_score` (int 0–100), `l1p1_pvalue` (float),
   `bot_flags` (str), `is_flagged` (bool)
6. `utils.py` unchanged
7. Qualtrics two-header-row format handled gracefully
8. Runtime on FE2a (350 participants, 106 items) under 90 seconds
9. Runtime on Dataset 26 (422 participants, 177 items) under 90 seconds
10. test_slice2d.py passes all assertions

---

## Files to Modify

| File | Changes |
|---|---|
| `detector.py` | Full replacement with optimized L1P1 |
| `requirements.txt` | Add `joblib>=1.3.0` |

**Do not modify:** `app.py`, `qualitative.py`, `utils.py`, `README.md`

---

## Performance Design

### Why the naive loop is slow

The original spec looped over permutations one at a time in Python:

```python
for b in range(200):                          # Python loop — slow
    perm = np.random.permutation(row)
    nri = compute_nri(perm, mu, cov)          # one at a time
```

Python loops over NumPy arrays are slow because each iteration has
overhead. The fix is to generate all permutations as a matrix and
compute all NRIs simultaneously using matrix operations.

### Optimization 1 — Vectorized permutation NRI computation

Instead of looping over 200 permutations, generate them as a matrix
`(B, n_items)` and compute all Mahalanobis distances in one shot:

```python
# Generate all B permutations at once — shape (B, n_items)
perms = np.array([np.random.permutation(row) for _ in range(B)])

# Vectorized Mahalanobis: diff shape (B, n_items)
diff = perms - mu                             # broadcast subtract mean
# MD for all B perms in one matrix op:
MD_all = np.sqrt(np.einsum('bi,ij,bj->b', diff, VI, diff))

# Vectorized person-total correlation:
# Pearson r between each row of perms and mu
perms_centered = perms - perms.mean(axis=1, keepdims=True)
mu_centered = mu - mu.mean()
numerator = perms_centered @ mu_centered
denom = np.linalg.norm(perms_centered, axis=1) * np.linalg.norm(mu_centered)
PTC_all = np.where(denom > 0, numerator / denom, -1.0)
```

`np.einsum('bi,ij,bj->b', diff, VI, diff)` computes the quadratic
form `diff @ VI @ diff.T` for all B rows simultaneously — this is the
key vectorization that eliminates the inner loop.

### Optimization 2 — Joblib parallel processing across participants

Each participant's permutation test is independent of every other
participant's (except for sharing the LOO anchor computation). This
makes it embarrassingly parallel — perfect for joblib:

```python
from joblib import Parallel, delayed

def _process_one_participant(pos, row, clean_matrix, B, alpha):
    """Process one participant's L1P1 test. Runs in parallel."""
    other_rows = np.delete(clean_matrix, pos, axis=0)
    mu = other_rows.mean(axis=0)
    cov = np.cov(other_rows.T)
    # ... vectorized NRI computation ...
    return pval, bot_score, is_flagged

results = Parallel(n_jobs=-1, backend="loky")(
    delayed(_process_one_participant)(pos, clean_matrix[pos], clean_matrix, B, alpha)
    for pos in range(len(clean_indices))
)
```

`n_jobs=-1` uses all available CPU cores automatically.
`backend="loky"` is the most robust backend for numerical computation.

### Expected performance

| Dataset | Participants | Items | Naive (est.) | Optimized (est.) |
|---|---|---|---|---|
| FE2a | 350 | 106 | ~4 min | ~45 sec |
| Dataset 26 | 422 | 177 | ~6 min | ~60 sec |

---

## Full Algorithm Specification

### Architecture: Two-Layer Detection

```
Layer 1 — Hard Flags (fast, no permutations needed)
  a. exact_duplicate: Likert vector identical to another row
  b. longstring_absolute: same answer on > 90% of Likert items
  c. speeder: duration < 5th percentile (if timing column found)

  Hard-flagged rows:
    bot_score = 100, l1p1_pvalue = 0.0, is_flagged = True

Layer 2 — L1P1 (parallel, vectorized)
  For each non-hard-flagged participant, in parallel:
    1. LOO anchors: mu and cov from all other non-hard-flagged rows
    2. Generate B=200 permutations as matrix (B, n_items)
    3. Compute NRIs for original + all perms — vectorized
    4. Compute distance from ideal point [0, +1] for all — vectorized
    5. p-value = proportion of (original + B perms) with dist >= original
    6. is_flagged = p_value >= alpha
    7. bot_score = int(round((1 - p_value) * 100))
```

### Score mapping

```python
bot_score = int(round((1 - p_value) * 100))
# p=0.00 → score=100  (certain bot)
# p=0.05 → score=95   (at alpha threshold)
# p=0.50 → score=50   (uncertain)
# p=1.00 → score=0    (certain human)
```

UI cutoff maps to alpha: `alpha = 1 - (cutoff / 100)`
Default cutoff=95 → alpha=0.05 → 95% sensitivity (paper default).

---

## Complete run_detection() Specification

```
run_detection(df: pd.DataFrame, cutoff: int = 95, B: int = 200)
-> pd.DataFrame

a. likert_cols = utils.get_likert_columns(df)
b. alpha = 1 - (cutoff / 100)
c. timing_col = first col whose name.lower() contains
   "duration" or "seconds" or "elapsed". None if not found.
d. If len(likert_cols) == 0:
   Return df.copy() with bot_score=0, l1p1_pvalue=1.0,
   bot_flags="no_likert_columns", is_flagged=False for all rows.

e. Build Likert matrix:
   Convert df[likert_cols] to numeric (errors='coerce')
   Impute NaN with column median
   Convert to float64 numpy array: shape (n_rows, n_items)

f. Compute hard flags:
   dup_flags = hard_flag_duplicate(df, likert_cols)      — pd.Series bool
   ls_flags = [hard_flag_longstring(likert_matrix[i]) for i in range(n)]
   ls_flags = pd.Series(ls_flags, index=df.index)
   spd_flags = hard_flag_speeder(df, timing_col) if timing_col else False Series
   hard_flagged = dup_flags | ls_flags | spd_flags

g. Build clean matrix (exclude hard-flagged rows):
   clean_mask = ~hard_flagged
   clean_indices = np.where(clean_mask.values)[0]
   clean_matrix = likert_matrix[clean_mask.values]  — shape (n_clean, n_items)

h. Initialize output arrays (length n_rows):
   bot_scores = np.zeros(n_rows, dtype=int)
   pvalues = np.ones(n_rows, dtype=float)
   flags = [""] * n_rows
   flagged = np.zeros(n_rows, dtype=bool)

i. Fill hard-flagged rows:
   For each row index i where hard_flagged is True:
     bot_scores[i] = 100
     pvalues[i] = 0.0
     flagged[i] = True
     flags[i] = comma-separated labels of which hard flags fired

j. Run L1P1 in parallel (if len(clean_indices) >= 3):
   results = Parallel(n_jobs=-1, backend="loky")(
       delayed(_process_participant)(pos, clean_matrix, B, alpha)
       for pos in range(len(clean_indices))
   )
   For each pos, (pval, score, is_flag) in enumerate(results):
     idx = clean_indices[pos]
     pvalues[idx] = pval
     bot_scores[idx] = score
     flagged[idx] = is_flag

k. Assemble and return:
   result = df.copy()
   result["bot_score"] = bot_scores
   result["l1p1_pvalue"] = pvalues
   result["bot_flags"] = flags
   result["is_flagged"] = flagged
   return result
```

### _process_participant() specification

```
_process_participant(pos: int, clean_matrix: np.ndarray,
                     B: int, alpha: float) -> tuple[float, int, bool]

This function runs in a worker process. Must be defined at module
level (not nested) for joblib pickling to work.

a. row = clean_matrix[pos]                    — shape (n_items,)
b. other_rows = np.delete(clean_matrix, pos, axis=0)  — shape (n-1, n_items)
c. If len(other_rows) < 2: return (1.0, 0, False)
d. mu = other_rows.mean(axis=0)               — shape (n_items,)
e. cov = np.cov(other_rows.T)                 — shape (n_items, n_items)
f. Try VI = np.linalg.inv(cov)
   Except LinAlgError: VI = np.linalg.pinv(cov)

g. Compute NRIs for original row:
   orig_md = sqrt(max(0, (row-mu) @ VI @ (row-mu)))
   orig_ptc = np.corrcoef(row, mu)[0,1] — if undefined set -1.0
   orig_nri = np.array([orig_md, orig_ptc])   — shape (2,)

h. Generate all B permutations — VECTORIZED:
   perms = np.array([np.random.permutation(row) for _ in range(B)])
                                               — shape (B, n_items)

i. Compute Mahalanobis for all B perms — VECTORIZED:
   diff = perms - mu                           — shape (B, n_items)
   md_all = np.sqrt(np.maximum(0,
       np.einsum('bi,ij,bj->b', diff, VI, diff)))  — shape (B,)

j. Compute person-total correlation for all B perms — VECTORIZED:
   perms_c = perms - perms.mean(axis=1, keepdims=True)
   mu_c = mu - mu.mean()
   numer = perms_c @ mu_c                     — shape (B,)
   denom = np.linalg.norm(perms_c, axis=1) * np.linalg.norm(mu_c)
   ptc_all = np.where(denom > 1e-10, numer / denom, -1.0)  — shape (B,)

k. Stack perm NRIs: perm_nris = np.column_stack([md_all, ptc_all])
                                               — shape (B, 2)

l. Compute Vi (covariance of perm NRI vectors):
   Try Vi = np.cov(perm_nris.T)               — shape (2, 2)
   Try Vi_inv = np.linalg.inv(Vi)
   Except: Vi_inv = np.linalg.pinv(Vi)

m. Ideal point: c = np.array([0.0, 1.0])

n. Distance from ideal for original:
   d = orig_nri - c
   dist_orig = sqrt(max(0, d @ Vi_inv @ d))

o. Distance from ideal for all B perms — VECTORIZED:
   d_all = perm_nris - c                      — shape (B, 2)
   dist_all = np.sqrt(np.maximum(0,
       np.einsum('bi,ij,bj->b', d_all, Vi_inv, d_all)))  — shape (B,)

p. P-value (Equation 3 from paper — original counted in null):
   all_dists = np.append(dist_all, dist_orig)  — shape (B+1,)
   pval = float(np.mean(all_dists >= dist_orig))

q. Return:
   bot_score = int(round((1 - pval) * 100))
   is_flagged = pval >= alpha
   return (pval, bot_score, is_flagged)

CRITICAL: This function must be defined at MODULE LEVEL (not inside
run_detection or any other function) for joblib to pickle it correctly.
If it is nested, joblib will raise a PicklingError.
```

---

## Edge Cases

- No Likert columns → return all bot_score=0, no flagging
- Fewer than 3 clean rows → skip L1P1, return bot_score=0
- Singular covariance matrix → use np.linalg.pinv() as fallback
- Zero-variance row (all same value) → PTC undefined, set -1.0
- Singular Vi (NRI covariance) → use pinv
- NaN Likert values → imputed with column median before processing
- timing_col values non-numeric → coerce, ignore NaN in percentile
- All rows are hard-flagged → skip L1P1 entirely

---

## Test Cases

Create `test_slice2d.py` in the project root:

```python
import pandas as pd
import numpy as np
import time
from detector import run_detection

print("=== Slice 2D Tests: L1P1 Engine (Optimized) ===\n")

# ── Test 1: Output columns and types ─────────────────────────────────────────
print("Test 1: Output structure")
np.random.seed(42)
n_items = 20
cols = [f"Q{i}" for i in range(n_items)]

human_rows = np.random.choice([1,2,3,4,5,6,7], size=(30, n_items),
                               p=[0.05,0.1,0.2,0.3,0.2,0.1,0.05])
bot_rows = np.random.randint(1, 8, size=(10, n_items))
data = np.vstack([human_rows, bot_rows])
labels = ["human"]*30 + ["bot"]*10

df_test = pd.DataFrame(data, columns=cols)
df_test["true_label"] = labels
result = run_detection(df_test, cutoff=95)

assert "bot_score" in result.columns, "bot_score column missing"
assert "l1p1_pvalue" in result.columns, "l1p1_pvalue column missing"
assert "is_flagged" in result.columns, "is_flagged column missing"
assert "bot_flags" in result.columns, "bot_flags column missing"
assert result["bot_score"].dtype in [int, "int64", "int32"], "bot_score should be int"
assert result["bot_score"].between(0, 100).all(), "bot_score out of range"
assert result["l1p1_pvalue"].between(0.0, 1.0).all(), "p-values out of range"
print("  PASS: All output columns present with correct types")

# ── Test 2: Bot detection rate ────────────────────────────────────────────────
print("\nTest 2: Bot detection rate (sensitivity)")
bot_results = result[result["true_label"] == "bot"]
flagged_bots = bot_results["is_flagged"].sum()
print(f"  Bots flagged: {flagged_bots}/10 ({flagged_bots*10:.0f}%)")
assert flagged_bots >= 7, f"Too few bots flagged: {flagged_bots}/10"
print("  PASS: Sufficient bot detection rate")

# ── Test 3: Hard flag — longstring ────────────────────────────────────────────
print("\nTest 3: Longstring hard flag")
df_ls = pd.DataFrame({f"Q{i}": [3]*10 for i in range(10)})
df_ls2 = pd.DataFrame({f"Q{i}": [4,2,5,1,6,3,4,2,5,1] for i in range(10)})
df_hard = pd.concat([df_ls, df_ls2], ignore_index=True)
result_hard = run_detection(df_hard, cutoff=95)
assert result_hard.loc[0, "is_flagged"] == True, "All-3s row should be flagged"
assert "longstring" in result_hard.loc[0, "bot_flags"], "longstring label missing"
assert result_hard.loc[0, "l1p1_pvalue"] == 0.0, "Hard-flagged p-value should be 0.0"
print("  PASS: Longstring hard flag works")

# ── Test 4: Hard flag — exact duplicate ───────────────────────────────────────
print("\nTest 4: Duplicate hard flag")
row_data = {f"Q{i}": [3,5,2,4,1,6,3,5,2,4][i] for i in range(10)}
df_dup = pd.DataFrame([row_data, row_data, row_data])
result_dup = run_detection(df_dup, cutoff=95)
assert result_dup["is_flagged"].all(), "All duplicate rows should be flagged"
assert all("exact_duplicate" in f for f in result_dup["bot_flags"]), \
    "exact_duplicate label missing"
print("  PASS: Duplicate hard flag works")

# ── Test 5: Score-pvalue mapping consistency ──────────────────────────────────
print("\nTest 5: Score-pvalue mapping")
result_map = run_detection(pd.DataFrame(
    {f"Q{i}": np.random.choice(range(1,8), 15) for i in range(12)}
), cutoff=95)
for _, row in result_map.iterrows():
    if row["bot_score"] != 100:  # skip hard-flagged
        expected = int(round((1 - row["l1p1_pvalue"]) * 100))
        assert abs(row["bot_score"] - expected) <= 1, \
            f"Mapping error: score={row['bot_score']}, pval={row['l1p1_pvalue']:.3f}"
print("  PASS: bot_score correctly maps from l1p1_pvalue")

# ── Test 6: Real Oishi Lab datasets with timing ───────────────────────────────
print("\nTest 6: Real Oishi Lab datasets")
datasets = [
    ('/mnt/user-data/uploads/FE2a_-_Survey_validation_March_25__2026_22_50.csv',
     'FE2a', 350, 50),
    ('/mnt/user-data/uploads/26__March_29__2026_17_43.csv',
     'Dataset26', 422, 50),
]
for fpath, label, expected_n, min_likert in datasets:
    try:
        df_real = pd.read_csv(fpath, skiprows=[1, 2], low_memory=False)
        print(f"\n  {label}: {len(df_real)} participants")

        t0 = time.time()
        result_real = run_detection(df_real, cutoff=95)
        elapsed = time.time() - t0

        assert "bot_score" in result_real.columns
        assert "l1p1_pvalue" in result_real.columns
        assert result_real["bot_score"].between(0, 100).all()
        assert result_real["l1p1_pvalue"].between(0.0, 1.0).all()

        n_flagged = result_real["is_flagged"].sum()
        n_hard = (result_real["bot_score"] == 100).sum()
        pct = n_flagged / len(result_real) * 100

        print(f"  Runtime: {elapsed:.1f}s")
        print(f"  Flagged: {n_flagged}/{len(result_real)} ({pct:.1f}%)")
        print(f"  Hard-flagged (score=100): {n_hard}")
        print(f"  Mean p-value: {result_real['l1p1_pvalue'].mean():.3f}")
        print(f"  Flagged p-values: {result_real[result_real['is_flagged']]['l1p1_pvalue'].describe().to_dict()}")

        assert elapsed < 300, f"Too slow: {elapsed:.0f}s (limit 300s)"
        print(f"  PASS: {label} processed correctly in {elapsed:.1f}s")
    except FileNotFoundError:
        print(f"  SKIP: {label} file not found")

print("\n=== All Slice 2D tests passed ===")
```

Run with: `python3 test_slice2d.py`

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector" for
the Oishi Lab. I am replacing detector.py with the L1P1 algorithm
(Ilagan & Falk, 2024, Behavior Research Methods) — an unsupervised
permutation test that outputs a p-value per participant. The
implementation must be optimized for performance using vectorized
NumPy operations and joblib parallelism. Tech stack: Python 3,
pandas, numpy, joblib. No other files change.

TASK:
Fully replace detector.py. Do not modify utils.py, app.py,
qualitative.py, or requirements.txt.

IMPORTS:
import pandas as pd
import numpy as np
from joblib import Parallel, delayed
import utils

MODULE-LEVEL CONSTANTS:
DEFAULT_ALPHA = 0.05
DEFAULT_B = 200

MODULE DOCSTRING: Include full citation:
Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised
detection of bots in a Likert-type questionnaire. Behavior Research
Methods, 56(5), 5068-5085. doi:10.3758/s13428-023-02246-7

─────────────────────────────────────────────────────────────
IMPLEMENT THESE FUNCTIONS IN THIS EXACT ORDER:
─────────────────────────────────────────────────────────────

1. hard_flag_duplicate(df, likert_cols) -> pd.Series
   Return boolean Series, True where Likert pattern duplicates another row.
   df.duplicated(subset=likert_cols, keep=False).fillna(False)

2. hard_flag_longstring(responses: np.ndarray) -> bool
   responses: 1D float array, NaN already removed.
   Return True if any single value appears in > 90% of responses.
   If len(responses) == 0: return False.

3. hard_flag_speeder(df, timing_col: str) -> pd.Series
   Coerce timing_col to numeric. Flag rows below 5th percentile.
   If fewer than 10 valid values: return all-False Series.

4. _process_participant(pos: int, clean_matrix: np.ndarray,
                         B: int, alpha: float) -> tuple[float, int, bool]

   *** CRITICAL: This function MUST be defined at MODULE LEVEL ***
   *** (not nested inside run_detection) for joblib to pickle it ***

   This is the core L1P1 computation for one participant.
   Must be fully self-contained — no global state.

   Implementation:
   a. row = clean_matrix[pos]
   b. other_rows = np.delete(clean_matrix, pos, axis=0)
   c. If len(other_rows) < 2: return (1.0, 0, False)
   d. mu = other_rows.mean(axis=0)
   e. cov = np.cov(other_rows.T)
      Try VI = np.linalg.inv(cov)
      Except LinAlgError: VI = np.linalg.pinv(cov)

   f. Compute original row NRIs:
      orig_md = float(np.sqrt(max(0.0,
          float((row - mu) @ VI @ (row - mu)))))
      corr_mat = np.corrcoef(row, mu)
      orig_ptc = float(corr_mat[0, 1]) if not np.isnan(corr_mat[0,1]) else -1.0
      orig_nri = np.array([orig_md, orig_ptc])

   g. Generate B permutations — VECTORIZED, shape (B, n_items):
      perms = np.array([np.random.permutation(row) for _ in range(B)])

   h. Mahalanobis for all B perms — VECTORIZED:
      diff = perms - mu                           # shape (B, n_items)
      quad = np.einsum('bi,ij,bj->b', diff, VI, diff)  # shape (B,)
      md_all = np.sqrt(np.maximum(0.0, quad))     # shape (B,)

   i. Person-total correlation for all B perms — VECTORIZED:
      perms_c = perms - perms.mean(axis=1, keepdims=True)
      mu_c = mu - mu.mean()
      numer = perms_c @ mu_c                      # shape (B,)
      denom = (np.linalg.norm(perms_c, axis=1) *
               np.linalg.norm(mu_c))              # shape (B,)
      ptc_all = np.where(denom > 1e-10,
                         numer / denom, -1.0)     # shape (B,)

   j. Stack: perm_nris = np.column_stack([md_all, ptc_all])
                                                  # shape (B, 2)

   k. Vi = covariance of perm_nris:
      Try: Vi = np.cov(perm_nris.T); Vi_inv = np.linalg.inv(Vi)
      Except: Vi_inv = np.linalg.pinv(np.cov(perm_nris.T)
                if perm_nris.std(axis=0).min() > 1e-10
                else np.eye(2))

   l. ideal = np.array([0.0, 1.0])

   m. Distance for original:
      d = orig_nri - ideal
      dist_orig = float(np.sqrt(max(0.0, float(d @ Vi_inv @ d))))

   n. Distance for all B perms — VECTORIZED:
      d_all = perm_nris - ideal                   # shape (B, 2)
      quad_all = np.einsum('bi,ij,bj->b',
                            d_all, Vi_inv, d_all) # shape (B,)
      dist_all = np.sqrt(np.maximum(0.0, quad_all))  # shape (B,)

   o. P-value (Equation 3 — include original in null distribution):
      all_dists = np.append(dist_all, dist_orig)  # shape (B+1,)
      pval = float(np.mean(all_dists >= dist_orig))

   p. Return:
      score = int(round((1 - pval) * 100))
      is_flag = pval >= alpha
      return (pval, score, is_flag)

5. run_detection(df: pd.DataFrame, cutoff: int = 95,
                  B: int = DEFAULT_B) -> pd.DataFrame

   Docstring: Include full citation to Ilagan & Falk (2024).
   Note that cutoff maps to alpha = 1 - (cutoff / 100), and that
   the paper's recommended alpha=0.05 corresponds to cutoff=95.

   Implementation:
   a. likert_cols = utils.get_likert_columns(df)
   b. alpha = 1.0 - (cutoff / 100.0)
   c. timing_col: first col whose name.lower() contains
      "duration" or "seconds" or "elapsed". None if not found.
   d. If len(likert_cols) == 0:
      result = df.copy()
      result["bot_score"] = 0
      result["l1p1_pvalue"] = 1.0
      result["bot_flags"] = "no_likert_columns"
      result["is_flagged"] = False
      return result

   e. Build Likert matrix:
      likert_df = df[likert_cols].apply(
          pd.to_numeric, errors='coerce')
      # Impute NaN with column median
      for col in likert_df.columns:
          median = likert_df[col].median()
          likert_df[col] = likert_df[col].fillna(
              median if not np.isnan(median) else 4.0)
      likert_matrix = likert_df.values.astype(np.float64)
      n_rows, n_items = likert_matrix.shape

   f. Hard flags:
      dup_flags = hard_flag_duplicate(df, likert_cols)
      ls_list = [hard_flag_longstring(likert_matrix[i])
                 for i in range(n_rows)]
      ls_flags = pd.Series(ls_list, index=df.index)
      if timing_col:
          spd_flags = hard_flag_speeder(df, timing_col)
      else:
          spd_flags = pd.Series(False, index=df.index)
      hard_flagged = (dup_flags | ls_flags | spd_flags)

   g. Clean matrix (non-hard-flagged rows only):
      clean_mask = ~hard_flagged.values
      clean_indices = np.where(clean_mask)[0]
      clean_matrix = likert_matrix[clean_mask]

   h. Initialize output arrays:
      bot_scores = np.zeros(n_rows, dtype=int)
      pvalues = np.ones(n_rows, dtype=float)
      flags_list = [""] * n_rows
      flagged_arr = np.zeros(n_rows, dtype=bool)

   i. Fill hard-flagged rows:
      For each i where hard_flagged.iloc[i] is True:
        bot_scores[i] = 100
        pvalues[i] = 0.0
        flagged_arr[i] = True
        parts = []
        if dup_flags.iloc[i]: parts.append("exact_duplicate")
        if ls_flags.iloc[i]: parts.append("longstring_absolute")
        if spd_flags.iloc[i]: parts.append("speeder")
        flags_list[i] = ", ".join(parts)

   j. Run L1P1 in parallel:
      If len(clean_indices) >= 3:
        results = Parallel(n_jobs=-1, backend="loky")(
            delayed(_process_participant)(pos, clean_matrix, B, alpha)
            for pos in range(len(clean_indices))
        )
        for pos, (pval, score, is_flag) in enumerate(results):
            idx = clean_indices[pos]
            pvalues[idx] = pval
            bot_scores[idx] = score
            flagged_arr[idx] = is_flag

   k. Assemble output:
      result = df.copy()
      result["bot_score"] = bot_scores
      result["l1p1_pvalue"] = np.round(pvalues, 4)
      result["bot_flags"] = flags_list
      result["is_flagged"] = flagged_arr.astype(bool)
      return result

─────────────────────────────────────────────────────────────

CONSTRAINTS:
- _process_participant MUST be at module level — not nested
- Use np.einsum for vectorized quadratic forms (fastest approach)
- n_jobs=-1 uses all CPU cores; backend="loky" is most robust
- No scipy — numpy only for linear algebra
- bot_score always integer 0-100
- l1p1_pvalue always float 0.0-1.0
- Do not modify utils.py, app.py, qualitative.py, requirements.txt

ACCEPTANCE CRITERIA:
1. test_slice2d.py passes all assertions
2. _process_participant is at module level (not nested)
3. Both real Oishi Lab CSVs process in under 5 minutes
4. Vectorized einsum used for Mahalanobis computation
5. Parallel(n_jobs=-1, backend="loky") used for participant loop

DO NOT:
- Nest _process_participant inside run_detection
- Use scipy
- Use a Python for-loop over individual permutations for NRI computation
- Modify any file except detector.py

OUTPUT:
Write complete detector.py. No explanations — just code.
List assumptions made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am building "Survey Bot Detector." Slice 2D implements the L1P1
algorithm in detector.py with vectorized NumPy and joblib parallelism.
I ran Codex and now test_slice2d.py is failing.

CURRENT PROBLEM:
[Paste exact error or failed assertion here]

RELEVANT FILES:
- detector.py
- utils.py (do not modify)
- test_slice2d.py

WHAT CODEX BUILT:
- hard_flag_duplicate, hard_flag_longstring, hard_flag_speeder
- _process_participant at module level (parallel worker)
- run_detection with Parallel(n_jobs=-1, backend="loky")
- Vectorized NRI computation using np.einsum

COMMON ISSUES TO CHECK:
- PicklingError: _process_participant must be at MODULE LEVEL not nested
- LinAlgError: ensure np.linalg.pinv fallback is in place everywhere
- NaN in pvalues: check median imputation and zero-variance guards
- bot_score not int: ensure int(round(...)) wrapping
- joblib import missing: add "from joblib import Parallel, delayed"

CONSTRAINTS:
- _process_participant must remain at module level
- No scipy — numpy only
- Do not modify utils.py, app.py, qualitative.py, requirements.txt
- n_jobs=-1, backend="loky" must be preserved

ACCEPTANCE CRITERIA:
1. All test_slice2d.py assertions pass
2. Both Oishi Lab CSVs process without errors
3. Runtime under 5 minutes for either dataset

DO NOT:
- Move _process_participant inside run_detection
- Remove parallelism
- Modify any file except detector.py

OUTPUT:
Fix the problem. Summarize what changed and why.
List follow-up issues for next session.
```

---

## requirements.txt Update

Add this line to `requirements.txt`:
```
joblib>=1.3.0
```

Note: joblib is already installed in most Python environments (it is
a dependency of scikit-learn). The explicit pin ensures it is present
in clean environments.

---

## app.py Updates After Slice 2D Passes

Two small changes to `app.py` to reflect the new algorithm:

**1. Update cutoff slider default from 75 to 95:**
```python
# OLD
cutoff = st.sidebar.slider(..., value=75, ...)

# NEW
cutoff = st.sidebar.slider(..., value=95, ...)
```

**2. Update slider caption:**
```python
st.sidebar.caption(
    "Maps to statistical sensitivity: score 95 = alpha 0.05 "
    "(95% sensitivity, recommended by Ilagan & Falk, 2024). "
    "Lower score = more strict."
)
```

**3. Update spinner message:**
```python
with st.spinner(
    "Running L1P1 bot detection — analyzing response patterns "
    "across all participants. Large datasets may take 1-2 minutes..."
):
```

---

## Slice Completion Checklist

- [ ] test_slice2d.py passes all assertions
- [ ] _process_participant confirmed at module level
- [ ] Hard flags (longstring, duplicate, speeder) verified
- [ ] Real datasets process correctly and under 5 minutes each
- [ ] requirements.txt updated with joblib>=1.3.0
- [ ] app.py cutoff slider default updated to 95
- [ ] app.py slider caption updated
- [ ] app.py spinner message updated
- [ ] Claude Code debugging reviewed and logged (if applicable)
- [ ] CHANGELOG.md updated
- [ ] KNOWN_ISSUES.md updated
- [ ] DECISIONS.md updated
- [ ] Delete test file: `rm test_slice2d.py`
- [ ] Git commit: `git add . && git commit -m "Slice 2D complete — L1P1 detection engine (vectorized + parallel)"`
- [ ] Pushed to GitHub: `git push`
