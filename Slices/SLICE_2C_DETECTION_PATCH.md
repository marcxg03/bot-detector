# SLICE_2C_DETECTION_PATCH.md
# Survey Bot Detector
# Oishi Lab — Marcus Gao

---

## Goal

Patch two cosmetic accuracy issues in `detector.py`'s `run_detection()`
function: (1) raise the flag label threshold to reduce noise on human rows,
and (2) exclude hard-flagged rows from the Mahalanobis reference matrix so
the centroid reflects genuine human response patterns.

---

## What Changes and Why

### Fix 1 — Flag label threshold (entropy noise)
**Problem:** The flag label threshold is currently 0.5, meaning any subscore
above 0.5 gets added to `bot_flags`. Humans with uniform response distributions
were getting `entropy` in their flag labels even though their `bot_score` was
well below 75. This is cosmetically noisy and could confuse researchers
inspecting the flagged CSV.

**Fix:** Raise the flag label threshold from `> 0.5` to `> 0.65` in
`run_detection()`. Scores are unchanged — only the label inclusion threshold
moves. This is one line.

### Fix 2 — Mahalanobis reference matrix pollution
**Problem:** `all_likert_matrix` is currently computed from all rows including
hard-flagged bots. This skews the group centroid and covariance matrix, causing
some human rows to receive spurious `mahalanobis` flag labels even though their
composite scores are correct.

**Fix:** Compute `all_likert_matrix` using only rows that did NOT receive a
hard flag. This requires a two-pass approach: compute hard flags for all rows
first, then build the reference matrix from non-hard-flagged rows only.

---

## Acceptance Criteria

1. No human rows in test_survey.csv have `entropy` in their `bot_flags`
2. No human rows in test_survey.csv have `mahalanobis` in their `bot_flags`
3. All 6 known bot rows still flagged with `bot_score = 100`
4. All 9 known human rows still clean with `bot_score < 75`
5. `bot_score` values are unchanged from Slice 2B results
6. Verified with test_slice2c.py

---

## Files to Modify

| File | Changes |
|---|---|
| `detector.py` | Two targeted changes to `run_detection()` only |

**Do not modify:** `app.py`, `qualitative.py`, `utils.py`,
`requirements.txt`, `README.md`

---

## Exact Changes Required

### Change 1 — Flag label threshold
In `run_detection()`, find the line that builds `flag_labels`:

```python
# OLD
flag_labels = [k for k, v in subscores.items()
               if not np.isnan(v) and v > 0.5]

# NEW
flag_labels = [k for k, v in subscores.items()
               if not np.isnan(v) and v > 0.65]
```

### Change 2 — Clean reference matrix for Mahalanobis
In `run_detection()`, the current approach computes `all_likert_matrix`
before the per-row loop using all rows. Replace this with a two-pass approach:

```
Pass 1 (before the main loop):
  - Compute duplicate_flags for all rows
  - Compute longstring_hard for all rows
  - Build a boolean Series: hard_flagged = duplicate OR longstring_hard
  - Build all_likert_matrix from rows where hard_flagged is False:
    clean_rows = df[~hard_flagged][likert_cols].dropna()
    all_likert_matrix = clean_rows.values
  - If all_likert_matrix has fewer than 2 rows (e.g. almost all bots):
    fall back to using all rows (same as before)

Pass 2 (the existing per-row loop — unchanged):
  - Use the cleaned all_likert_matrix when calling subscore_mahalanobis()
```

---

## Test Cases

Create `test_slice2c.py` in the project root:

```python
import pandas as pd
import numpy as np
from detector import run_detection

df = pd.read_csv("test_survey.csv")
result = run_detection(df, cutoff=75)

print("\n--- Scores and Flags ---")
for _, row in result.iterrows():
    status = "🔴 FLAGGED" if row["is_flagged"] else "🟢 clean"
    print(f"{row['ResponseId']}: score={row['bot_score']:3d} | "
          f"flags={str(row['bot_flags']):<50} | {status}")

known_bots   = ["R003", "R005", "R007", "R009", "R011", "R013"]
known_humans = ["R001", "R002", "R004", "R006",
                "R008", "R010", "R012", "R014", "R015"]

print("\n--- Bot Assertions ---")
for bot_id in known_bots:
    row = result[result["ResponseId"] == bot_id].iloc[0]
    assert row["is_flagged"] == True, \
        f"FAIL: {bot_id} should be flagged (score={row['bot_score']})"
    print(f"PASS: {bot_id} flagged (score={row['bot_score']})")

print("\n--- Human Assertions ---")
for human_id in known_humans:
    row = result[result["ResponseId"] == human_id].iloc[0]
    assert row["is_flagged"] == False, \
        f"FAIL: {human_id} should be clean (score={row['bot_score']})"
    # Check no spurious entropy or mahalanobis labels
    flags = str(row["bot_flags"])
    assert "entropy" not in flags, \
        f"FAIL: {human_id} has spurious entropy flag (score={row['bot_score']})"
    assert "mahalanobis" not in flags, \
        f"FAIL: {human_id} has spurious mahalanobis flag (score={row['bot_score']})"
    print(f"PASS: {human_id} clean, no spurious flags (score={row['bot_score']})")

print("\nAll Slice 2C assertions passed.")
```

Run with: `python3 test_slice2c.py`

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector."
The detection engine in detector.py is fully implemented (Slice 2B).
I need to make two small targeted fixes to the run_detection() function
only. No other functions change. No other files change.

TASK:
Make exactly two changes to run_detection() in detector.py:

CHANGE 1 — Flag label threshold
Find the line that builds flag_labels from subscores.
Change the threshold from > 0.5 to > 0.65:

OLD:
flag_labels = [k for k, v in subscores.items()
               if not np.isnan(v) and v > 0.5]

NEW:
flag_labels = [k for k, v in subscores.items()
               if not np.isnan(v) and v > 0.65]

CHANGE 2 — Clean Mahalanobis reference matrix
Currently all_likert_matrix is built from all rows before the main loop.
Replace with a two-pass approach:

Pass 1 (before the main per-row loop):
  a. Compute duplicate_flags = hard_flag_duplicate(df, likert_cols)
  b. For each row, compute longstring_hard using hard_flag_longstring()
     Build a boolean list: longstring_hard_flags
  c. Build hard_flagged boolean Series:
     hard_flagged = duplicate_flags | pd.Series(longstring_hard_flags,
     index=df.index)
  d. Build clean reference matrix:
     clean_df = df[~hard_flagged][likert_cols].dropna()
     if len(clean_df) >= 2:
         all_likert_matrix = clean_df.values
     else:
         all_likert_matrix = df[likert_cols].dropna().values
         (fallback to all rows if not enough clean rows)

Pass 2 (the existing per-row loop):
  Use the same all_likert_matrix variable — no changes needed inside
  the loop itself since subscore_mahalanobis() already receives it
  as a parameter.

CONSTRAINTS:
- Only modify run_detection() inside detector.py
- Do not modify any other function in detector.py
- Do not modify utils.py, app.py, qualitative.py, requirements.txt
- Do not refactor or rename any functions
- Preserve all existing docstrings

ACCEPTANCE CRITERIA:
1. test_slice2c.py passes all assertions
2. Human rows have no entropy or mahalanobis in bot_flags
3. All 6 bot rows still flagged with bot_score = 100
4. All 9 human rows still clean with bot_score < 75
5. bot_score values are integers 0–100

DO NOT:
- Change any subscore functions
- Change the flag label threshold anywhere except the one line specified
- Modify files outside detector.py
- Add any new functions

OUTPUT:
Write the complete updated run_detection() function only — not the
entire file. No explanations — just code. List assumptions made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am patching run_detection() in detector.py with two small fixes:
(1) raise flag label threshold from 0.5 to 0.65, and (2) exclude
hard-flagged rows from the Mahalanobis reference matrix. I ran
test_slice2c.py and it is failing.

CURRENT PROBLEM:
[Paste exact error or failed assertion here]

RELEVANT FILES:
- detector.py
- test_slice2c.py
- test_survey.csv

WHAT CODEX BUILT:
Updated run_detection() with two-pass hard flag computation and
raised flag label threshold. All other functions in detector.py
are unchanged and working.

CONSTRAINTS:
- Only fix run_detection() — do not modify other functions
- Do not modify utils.py, app.py, qualitative.py, requirements.txt
- bot_score must remain integer 0–100
- All subscore functions must remain unchanged

ACCEPTANCE CRITERIA:
1. All assertions in test_slice2c.py pass
2. No entropy or mahalanobis in bot_flags for human rows
3. All 6 bot rows flagged, all 9 human rows clean

DO NOT:
- Rewrite subscore functions
- Modify any file except detector.py
- Change the folder structure

OUTPUT:
Fix the problem. Summarize what changed and why.
List follow-up issues for next session.
```

---

## Slice Completion Checklist

- [ ] test_slice2c.py passes all assertions
- [ ] No entropy or mahalanobis flags on human rows
- [ ] Bot scores unchanged from Slice 2B
- [ ] Claude Code debugging reviewed and logged (if applicable)
- [ ] CHANGELOG.md updated
- [ ] KNOWN_ISSUES.md updated (mark Issues 1 and 2 resolved)
- [ ] DECISIONS.md updated
- [ ] Delete test file: `rm test_slice2c.py`
- [ ] Git commit: `git add . && git commit -m "Slice 2C complete — detection engine patch"`
- [ ] Pushed to GitHub: `git push`
