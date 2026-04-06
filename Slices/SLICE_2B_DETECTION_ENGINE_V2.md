# SLICE_2B_DETECTION_ENGINE_V2.md
# Survey Bot Detector
# Oishi Lab — Marcus Gao

---

## Goal

Replace the binary detection engine in `detector.py` and `utils.py` with a
redesigned algorithm that uses continuous subscores, hard-flag overrides, and
psychometrically validated checks. The new engine is significantly more
sensitive and catches bots that the binary approach misses.

---

## What Changes and Why

The original Slice 2 engine used binary triggers — a check either fired at
100 or didn't fire at all. This caused obvious bots (e.g. all-4s responders,
all-7s responders) to score below the 75 cutoff because they narrowly missed
multiple thresholds. The new engine fixes this by:

1. Making every check continuous (0–1) so near-misses still contribute
2. Adding hard flags that auto-assign score 100 for egregious cases
3. Adding psychometric checks (entropy, even/odd consistency, Mahalanobis)
   that catch patterns the original checks missed entirely

---

## Acceptance Criteria

1. `detector.py` implements all hard flags and continuous subscores as specified
2. Hard-flagged rows receive `bot_score = 100` and bypass the composite
3. Composite score is a weighted average of available continuous subscores
4. `bot_score` is an integer 0–100
5. `bot_flags` lists all triggered hard flags and high-scoring subscores
6. `is_flagged` is True when `bot_score >= cutoff`
7. `utils.py` retains `get_likert_columns()`, `get_text_columns()`,
   `normalize_score()` — update normalize_score to handle 0–1 input scale
8. All known bot rows in test_survey.csv score above 75 at default cutoff
9. All known human rows in test_survey.csv score below 75 at default cutoff
10. Verified with test_slice2b.py

---

## Files to Modify

| File | Changes |
|---|---|
| `detector.py` | Full replacement of all check functions and run_detection() |
| `utils.py` | Update normalize_score(); retain column detection functions |

**Do not modify:** `app.py`, `qualitative.py`, `requirements.txt`, `README.md`

---

## New Algorithm Specification

### Hard Flags (auto-assign bot_score = 100, skip composite)

```
hard_flag_duplicate(df, likert_cols) -> list[bool]
    Flag if a row's Likert response vector is identical to any other row
    Uses pandas duplicated(subset=likert_cols, keep=False)
    Flag label: "exact_duplicate"

hard_flag_longstring(responses) -> bool (per row)
    Flag if the same answer appears in more than 90% of Likert items
    longstring_ratio = responses.value_counts().max() / len(responses)
    Flag if longstring_ratio > 0.90
    Flag label: "longstring_absolute"
```

If either hard flag is True for a row:
- `bot_score = 100`
- `bot_flags` = the hard flag label(s)
- `is_flagged = True` (regardless of cutoff)
- Skip all continuous subscore calculation for that row

---

### Continuous Subscores (0.0–1.0 scale, higher = more suspicious)

```
subscore_longstring(responses) -> float
    Captures the longest unbroken run of identical consecutive responses
    max_run = longest consecutive sequence of the same value
    return max_run / len(responses)
    Use itertools.groupby to find runs

subscore_irv(responses, scale_min, scale_max) -> float
    Inter-item variance score
    sd = numpy std of responses (ignore NaN)
    max_possible_sd = (scale_max - scale_min) / 2
    return 1 - (sd / max_possible_sd)
    Clamp result to [0.0, 1.0]
    Returns 1.0 if sd is 0 (zero variance = maximally suspicious)

subscore_mahalanobis(response_vector, all_responses) -> float
    Measures how far a response vector is from the group centroid
    accounting for inter-item covariance
    Steps:
    1. Compute covariance matrix of all_responses
    2. Compute group mean vector
    3. Try to invert covariance matrix (np.linalg.inv)
    4. Compute d_squared = diff @ VI @ diff.T
    5. Convert to p-value using scipy.stats.chi2.cdf(d2, df=n_items)
    6. Return 1 - p_value (high score = outlier)
    On LinAlgError (singular matrix): return np.nan
    On any other error: return np.nan

subscore_even_odd(responses) -> float
    Within-person split-half consistency
    Split Likert responses into even-indexed and odd-indexed items
    Compute Pearson correlation between the two halves
    return (1 - r) / 2   # maps [1,-1] -> [0,1], high = inconsistent
    If r is NaN: return 0.5 (neutral)

subscore_entropy(responses, scale_min, scale_max) -> float
    Measures response distribution entropy
    Both extremes are suspicious:
    - entropy = 0 (all same answer, straight-liner)
    - entropy = max (perfectly uniform random)
    Human-like entropy peaks around 0.6 normalized
    Steps:
    1. Count occurrences of each scale value (scale_min to scale_max)
    2. Convert to probabilities
    3. Compute Shannon entropy: -sum(p * log(p)) for p > 0
    4. Normalize: normalized = entropy / log(n_options)
    5. Return abs(normalized - 0.6) / 0.6
    Clamp to [0.0, 1.0]

subscore_speeder(response_time, expected_min_seconds=120) -> float
    Continuous speeder score
    If response_time is None or NaN: return np.nan
    If response_time >= expected_min_seconds: return 0.0
    return 1 - (response_time / expected_min_seconds)
    Clamp to [0.0, 1.0]

subscore_missing(responses) -> float
    Proportion of Likert items that are null/NaN
    return responses.isna().mean()
```

---

### Weights for Composite Score

```python
WEIGHTS = {
    'longstring':   0.20,
    'irv':          0.15,
    'mahalanobis':  0.15,
    'even_odd':     0.15,
    'entropy':      0.10,
    'speeder':      0.15,   # only if timing column exists
    'missing':      0.05,
}
```

Note: `reverse_consist` from the spec is excluded — it requires pre-defined
reverse-scored item pairs that vary by instrument. Excluded from this
implementation; can be added as a future enhancement.

---

### Composite Scoring Logic

```python
def composite_score(subscores: dict) -> float:
    """
    subscores: dict of {check_name: float} — np.nan if check didn't run
    Returns: float 0–100
    """
    total_weight = 0
    weighted_sum = 0
    for check, score in subscores.items():
        if np.isnan(score):
            continue
        w = WEIGHTS[check]
        weighted_sum += score * w
        total_weight += w
    if total_weight == 0:
        return 0.0
    return (weighted_sum / total_weight) * 100
```

---

### run_detection() Orchestration Logic

```
run_detection(df: DataFrame, cutoff: int) -> DataFrame

Steps:
1. Get likert_cols from utils.get_likert_columns(df)
2. Find timing column: first column name containing
   "duration", "time", "seconds", or "elapsed" (case-insensitive)
   Set timing_col = None if not found

3. Compute hard flags for all rows:
   - duplicate_flags = hard_flag_duplicate(df, likert_cols)
   - For each row: compute longstring_ratio, set longstring_hard = ratio > 0.90

4. For each row i:
   a. Check hard flags first:
      - If duplicate_flags[i] or longstring_hard[i]:
        bot_score[i] = 100
        bot_flags[i] = comma-separated hard flag labels that fired
        is_flagged[i] = True
        Continue to next row (skip subscores)

   b. Compute continuous subscores:
      responses = df.iloc[i][likert_cols] (drop NaN for calculations)
      subscores = {
        'longstring':  subscore_longstring(responses),
        'irv':         subscore_irv(responses, scale_min, scale_max),
        'mahalanobis': subscore_mahalanobis(responses, all_likert_matrix),
        'even_odd':    subscore_even_odd(responses),
        'entropy':     subscore_entropy(responses, scale_min, scale_max),
        'speeder':     subscore_speeder(row[timing_col]) if timing_col else np.nan,
        'missing':     subscore_missing(df.iloc[i][likert_cols]),
      }

   c. Compute composite:
      raw_score = composite_score(subscores)
      bot_score[i] = int(round(raw_score))

   d. Determine flags:
      Flag any subscore that contributed and scored > 0.5
      bot_flags[i] = comma-separated names of subscores > 0.5

   e. is_flagged[i] = True if bot_score[i] >= cutoff

5. Compute scale_min and scale_max from all Likert columns before the loop:
   scale_min = int(df[likert_cols].min().min())  # typically 1
   scale_max = int(df[likert_cols].max().max())  # typically 5 or 7

6. Pre-compute all_likert_matrix for Mahalanobis:
   all_likert_matrix = df[likert_cols].dropna().values

7. Append bot_score (int), bot_flags (str), is_flagged (bool) to a copy of df
8. Return new DataFrame — do not modify original
```

---

## Edge Cases to Handle

- Fewer than 2 Likert columns → skip Mahalanobis and even_odd (return np.nan)
- Fewer than 3 Likert columns → skip entropy (return np.nan)
- Singular covariance matrix → Mahalanobis returns np.nan (caught by LinAlgError)
- All rows identical → duplicate hard flag fires for all rows (expected)
- No timing column → speeder returns np.nan for all rows (excluded from composite)
- Fewer than 2 rows → skip Mahalanobis (can't compute covariance)
- All subscores are np.nan → composite returns 0.0

---

## Test Cases

Create `test_slice2b.py` in the project root:

```python
import pandas as pd
import numpy as np
from detector import run_detection

# Load the real test CSV
df = pd.read_csv("test_survey.csv")
result = run_detection(df, cutoff=75)

print("\n--- Bot Scores ---")
for _, row in result.iterrows():
    status = "🔴 FLAGGED" if row["is_flagged"] else "🟢 clean"
    print(f"{row['ResponseId']}: score={row['bot_score']:3d} | "
          f"flags={row['bot_flags']:<40} | {status}")

# Known bots — should all be flagged
known_bots = ["R003", "R005", "R007", "R009", "R011", "R013"]
# Known humans — should all be clean
known_humans = ["R001", "R002", "R004", "R006", "R008", "R010", "R012", "R014", "R015"]

print("\n--- Assertions ---")
for bot_id in known_bots:
    row = result[result["ResponseId"] == bot_id].iloc[0]
    assert row["is_flagged"] == True, \
        f"FAIL: {bot_id} should be flagged but got score {row['bot_score']}"
    print(f"PASS: {bot_id} correctly flagged (score={row['bot_score']})")

for human_id in known_humans:
    row = result[result["ResponseId"] == human_id].iloc[0]
    assert row["is_flagged"] == False, \
        f"FAIL: {human_id} should be clean but got score {row['bot_score']}"
    print(f"PASS: {human_id} correctly clean (score={row['bot_score']})")

print("\nAll assertions passed.")
```

Run with: `python3 test_slice2b.py`

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector" for
the Oishi Lab. The scaffold (Slice 1) and a first-pass detection engine
(Slice 2) are complete. I am now replacing the detection engine with a
redesigned algorithm that uses continuous subscores and hard-flag
overrides instead of binary triggers. App runs locally with Python 3,
pandas, numpy, scipy, and itertools.

TASK:
Fully replace detector.py and update utils.py as specified below.
Do not modify app.py, qualitative.py, requirements.txt, or README.md.

IMPLEMENT detector.py — complete replacement:

IMPORTS NEEDED:
import pandas as pd
import numpy as np
from itertools import groupby
from scipy.stats import chi2
import utils

WEIGHTS constant at module level:
WEIGHTS = {
    'longstring':   0.20,
    'irv':          0.15,
    'mahalanobis':  0.15,
    'even_odd':     0.15,
    'entropy':      0.10,
    'speeder':      0.15,
    'missing':      0.05,
}

HARD FLAG FUNCTIONS:

1. hard_flag_duplicate(df, likert_cols) -> pd.Series of bool
   Returns boolean Series, True where row's Likert pattern duplicates
   another row. Use df.duplicated(subset=likert_cols, keep=False).

2. hard_flag_longstring(responses) -> bool
   responses: pandas Series of Likert values for one row
   Return True if same value appears in > 90% of non-null responses
   longstring_ratio = responses.dropna().value_counts().max() / len(responses.dropna())
   return longstring_ratio > 0.90

CONTINUOUS SUBSCORE FUNCTIONS:

3. subscore_longstring(responses) -> float
   responses: array-like of Likert values (NaN dropped before call)
   Find longest consecutive run of identical values using itertools.groupby
   return max_run / len(responses)

4. subscore_irv(responses, scale_min, scale_max) -> float
   sd = np.std(responses)
   max_possible_sd = (scale_max - scale_min) / 2
   if max_possible_sd == 0: return 0.0
   result = 1 - (sd / max_possible_sd)
   return float(np.clip(result, 0.0, 1.0))

5. subscore_mahalanobis(response_vector, all_responses) -> float
   response_vector: 1D numpy array for one row
   all_responses: 2D numpy array of all rows x Likert cols (NaN rows dropped)
   if len(all_responses) < 2 or len(response_vector) < 2: return np.nan
   try:
     cov = np.cov(all_responses.T)
     mean = all_responses.mean(axis=0)
     VI = np.linalg.inv(cov)
     diff = response_vector - mean
     d2 = float(diff @ VI @ diff.T)
     p = 1 - chi2.cdf(d2, df=len(response_vector))
     return float(np.clip(1 - p, 0.0, 1.0))
   except (np.linalg.LinAlgError, Exception):
     return np.nan

6. subscore_even_odd(responses) -> float
   responses: array-like, NaN dropped
   even = responses[::2]
   odd = responses[1::2]
   min_len = min(len(even), len(odd))
   if min_len < 2: return 0.5
   r = np.corrcoef(even[:min_len], odd[:min_len])[0, 1]
   if np.isnan(r): return 0.5
   return float((1 - r) / 2)

7. subscore_entropy(responses, scale_min, scale_max) -> float
   if len(responses) < 3: return np.nan
   n_options = scale_max - scale_min + 1
   counts = np.bincount(
     np.array(responses, dtype=int) - scale_min,
     minlength=n_options
   )
   probs = counts / counts.sum()
   probs = probs[probs > 0]
   observed_entropy = -np.sum(probs * np.log(probs))
   max_entropy = np.log(n_options)
   if max_entropy == 0: return 0.0
   normalized = observed_entropy / max_entropy
   result = abs(normalized - 0.6) / 0.6
   return float(np.clip(result, 0.0, 1.0))

8. subscore_speeder(response_time, expected_min_seconds=120) -> float
   if response_time is None or (isinstance(response_time, float)
   and np.isnan(response_time)): return np.nan
   if response_time >= expected_min_seconds: return 0.0
   return float(np.clip(1 - (response_time / expected_min_seconds), 0.0, 1.0))

9. subscore_missing(responses) -> float
   return float(responses.isna().mean())

COMPOSITE FUNCTION:

10. composite_score(subscores: dict) -> float
    Weighted average of non-NaN subscores using WEIGHTS dict
    total_weight = sum of WEIGHTS[k] for k where subscores[k] is not NaN
    weighted_sum = sum of subscores[k] * WEIGHTS[k] for non-NaN
    if total_weight == 0: return 0.0
    return (weighted_sum / total_weight) * 100

MAIN ORCHESTRATION:

11. run_detection(df: pd.DataFrame, cutoff: int) -> pd.DataFrame
    Steps:
    a. likert_cols = utils.get_likert_columns(df)
    b. Find timing_col: first column whose name (lower) contains
       "duration", "time", "seconds", or "elapsed". None if not found.
    c. If len(likert_cols) == 0:
       Append bot_score=0, bot_flags="no_likert_columns",
       is_flagged=False to all rows and return.
    d. Compute scale_min and scale_max from df[likert_cols]
    e. Compute all_likert_matrix:
       all_likert_matrix = df[likert_cols].dropna().values
    f. Compute duplicate_flags = hard_flag_duplicate(df, likert_cols)
    g. For each row i, build result:
       - Get responses = df.iloc[i][likert_cols]
       - responses_clean = responses.dropna().values.astype(float)
       - Check hard flags:
         dup = duplicate_flags.iloc[i]
         ls_hard = hard_flag_longstring(responses)
         hard_flag_labels = []
         if dup: hard_flag_labels.append("exact_duplicate")
         if ls_hard: hard_flag_labels.append("longstring_absolute")
         if hard_flag_labels:
           bot_score = 100
           bot_flags = ", ".join(hard_flag_labels)
           is_flagged = True
           continue to next row
       - Compute subscores dict:
         'longstring': subscore_longstring(responses_clean)
           if len(responses_clean) >= 2 else np.nan
         'irv': subscore_irv(responses_clean, scale_min, scale_max)
           if len(responses_clean) >= 2 else np.nan
         'mahalanobis': subscore_mahalanobis(
           responses_clean, all_likert_matrix)
           if len(responses_clean) >= 2 else np.nan
         'even_odd': subscore_even_odd(responses_clean)
           if len(responses_clean) >= 4 else np.nan
         'entropy': subscore_entropy(responses_clean, scale_min, scale_max)
           if len(responses_clean) >= 3 else np.nan
         'speeder': subscore_speeder(df.iloc[i][timing_col])
           if timing_col else np.nan
         'missing': subscore_missing(responses)
       - raw = composite_score(subscores)
       - bot_score = int(round(raw))
       - flag_labels = [k for k,v in subscores.items()
         if not np.isnan(v) and v > 0.5]
       - bot_flags = ", ".join(flag_labels) if flag_labels else ""
       - is_flagged = bot_score >= cutoff
    h. Append bot_score, bot_flags, is_flagged columns to df.copy()
    i. Return new DataFrame

CONSTRAINTS:
- Python 3, pandas, numpy, scipy, itertools only
- Do not modify app.py, qualitative.py, requirements.txt, README.md
- utils.get_likert_columns() and utils.get_text_columns() stay unchanged
- All subscore functions must handle edge cases without raising exceptions
- bot_score must always be an integer 0–100

ACCEPTANCE CRITERIA:
1. test_slice2b.py passes all assertions
2. Known bot rows (R003, R005, R007, R009, R011, R013) all flagged
3. Known human rows all clean
4. bot_score is always an integer 0–100
5. No unhandled exceptions on the test CSV

DO NOT:
- Keep any of the old binary check functions
- Modify app.py or qualitative.py
- Add UI logic to detector.py
- Leave functions that raise exceptions on edge cases

OUTPUT:
Write complete implementations for detector.py and utils.py.
No explanations — just code. List assumptions made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am building "Survey Bot Detector." I replaced the detection engine
in detector.py with a redesigned algorithm using continuous subscores
and hard-flag overrides. I ran test_slice2b.py and it is failing.

CURRENT PROBLEM:
[Paste exact error or failed assertion here]

RELEVANT FILES:
- detector.py
- utils.py
- test_slice2b.py
- test_survey.csv

WHAT CODEX BUILT:
Full replacement of detector.py with continuous subscores:
subscore_longstring, subscore_irv, subscore_mahalanobis,
subscore_even_odd, subscore_entropy, subscore_speeder,
subscore_missing, composite_score, run_detection.
Hard flags: hard_flag_duplicate, hard_flag_longstring.

CONSTRAINTS:
- Python 3, pandas, numpy, scipy, itertools only
- Do not modify app.py, qualitative.py, requirements.txt
- Fix only what is failing — do not refactor working functions
- bot_score must be integer 0–100
- All subscore functions must handle edge cases without raising exceptions

ACCEPTANCE CRITERIA:
1. All assertions in test_slice2b.py pass
2. R003, R005, R007, R009, R011, R013 all flagged at cutoff 75
3. R001, R002, R004, R006, R008, R010, R012, R014, R015 all clean
4. No unhandled exceptions

DO NOT:
- Rewrite functions that are passing
- Modify app.py or qualitative.py
- Change the folder structure

OUTPUT:
Fix the problem. Summarize what changed and why.
List follow-up issues for the next session.
```

---

## Slice Completion Checklist

- [ ] test_slice2b.py passes all assertions for all 15 rows
- [ ] Claude Code debugging output reviewed and logged (if applicable)
- [ ] CHANGELOG.md updated
- [ ] KNOWN_ISSUES.md updated
- [ ] DECISIONS.md updated
- [ ] Delete test files before committing: `rm test_slice2b.py`
- [ ] Git commit: `git add . && git commit -m "Slice 2B complete — detection engine v2"`
- [ ] Pushed to GitHub: `git push`
