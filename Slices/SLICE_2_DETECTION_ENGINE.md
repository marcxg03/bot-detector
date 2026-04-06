# SLICE_2_DETECTION_ENGINE.md
# Survey Bot Detector
# Oishi Lab — Marcus Gao

---

## Goal

Implement the full quantitative bot detection logic in `utils.py` and `detector.py` so that the engine can accept a pandas DataFrame and return it with `bot_score`, `bot_flags`, and `is_flagged` columns appended.

---

## Acceptance Criteria

1. `utils.get_likert_columns(df)` correctly identifies Likert columns by value range and unique value count
2. `utils.get_text_columns(df)` correctly identifies open-ended text columns by dtype and average length
3. `utils.normalize_score()` returns a correct integer 0–100 for any weighted input
4. All seven check functions in `detector.py` return a correctly structured dict
5. Each check function correctly skips and sets `skipped: True` when its skip condition is met
6. `detector.run_detection(df, cutoff)` returns a DataFrame with `bot_score`, `bot_flags`, and `is_flagged` columns appended
7. `bot_score` values are integers in the range 0–100
8. `is_flagged` is True for any row where `bot_score >= cutoff`
9. `bot_flags` is a comma-separated string of triggered check names per row
10. Verified with a test script using a synthetic DataFrame with known bot-like and human-like rows

---

## Files to Modify

| File | Changes |
|---|---|
| `utils.py` | Implement all three helper functions |
| `detector.py` | Implement all seven check functions and `run_detection()` |

**Do not modify:** `app.py`, `qualitative.py`, `requirements.txt`, `README.md`

---

## Component / Function Contracts

### utils.py

```
get_likert_columns(df) -> list[str]
    A column is Likert if ALL of the following are true:
    - dtype is numeric (int64 or float64)
    - All non-null values fall within 1–7 (inclusive)
    - Column has fewer than 8 unique non-null values

get_text_columns(df) -> list[str]
    A column is open-ended text if ALL of the following are true:
    - dtype is object (string)
    - Mean response length > 20 characters (null values excluded)
    - Column name does not match metadata patterns:
      id, timestamp, duration, email, date, time, ip, status, response_id

normalize_score(weighted_sum: float, max_possible: float) -> int
    Returns int(round((weighted_sum / max_possible) * 100))
    If max_possible is 0, returns 0 (avoid division by zero)
```

### detector.py — check function return format

Every check function returns a dict with exactly these keys:

```python
{
    "scores": list[float],   # one value per row, 0.0–100.0
    "flags":  list[str],     # check name if triggered, "" if not
    "weight": int,           # this check's contribution weight
    "skipped": bool          # True if skip condition was met
}
```

If skipped is True, scores must be a list of 0.0 values (one per row) and flags must be a list of "" values (one per row).

### detector.py — check specifications

```
check_straight_lining(df, likert_cols) -> dict
    Weight: 30
    Skip if: fewer than 3 Likert columns
    Triggered for a row if: standard deviation across all Likert
    columns for that row == 0 (every answer identical)
    Score if triggered: 100.0

check_low_variance(df, likert_cols) -> dict
    Weight: 25
    Skip if: fewer than 3 Likert columns
    Triggered for a row if: standard deviation across all Likert
    columns for that row is below the 10th percentile of all
    participants' standard deviations
    Score if triggered: 100.0

check_range_avoidance(df, likert_cols) -> dict
    Weight: 15
    Skip if: scale range undetectable (fewer than 2 Likert columns)
    Auto-detect scale max: max value present across all Likert columns
    (typically 5 or 7)
    Middle values for 1–5 scale: [2, 3, 4]
    Middle values for 1–7 scale: [2, 3, 4, 5, 6]
    Triggered for a row if: none of the middle values appear in that
    row's Likert responses
    Score if triggered: 100.0

check_extreme_responding(df, likert_cols) -> dict
    Weight: 15
    Skip if: fewer than 2 Likert columns
    Triggered for a row if: 90% or more of Likert responses are
    scale endpoints (1 or scale_max)
    Score if triggered: 100.0

check_speeder(df) -> dict
    Weight: 25
    Skip if: no column matching duration/timing patterns found
    Duration column detection: look for column name containing any of:
    "duration", "time", "seconds", "elapsed" (case-insensitive)
    Triggered for a row if: duration value is below the 5th percentile
    of all participants' durations
    Score if triggered: 100.0

check_duplicate_patterns(df, likert_cols) -> dict
    Weight: 20
    Skip if: fewer than 2 participants or fewer than 2 Likert columns
    Triggered for a row if: that row's Likert response pattern
    (as a tuple) appears in more than one row
    Score if triggered: 100.0

check_missing_patterns(df, likert_cols) -> dict
    Weight: 10
    Skip if: fewer than 3 Likert columns
    Triggered for a row if: more than 50% of Likert columns are null/NaN
    Score if triggered: 100.0
```

### detector.py — run_detection() logic

```
run_detection(df: DataFrame, cutoff: int) -> DataFrame
    1. Call utils.get_likert_columns(df) to get likert_cols
    2. Run all seven check functions
    3. For each row i, compute:
       - active_checks = checks where skipped is False
       - weighted_sum = sum of (scores[i] * weight) for active checks
       - max_possible = sum of weights for active checks
       - bot_score[i] = utils.normalize_score(weighted_sum, max_possible)
       - bot_flags[i] = comma-separated string of non-empty flags[i] values
       - is_flagged[i] = True if bot_score[i] >= cutoff
    4. Append bot_score, bot_flags, is_flagged columns to df copy
    5. Return the new DataFrame (do not modify the original)
```

---

## Edge Cases to Handle

- CSV has no Likert columns detected → all checks that require Likert cols are skipped → bot_score = 0 for all rows
- All participants have the same duration → speeder check 5th percentile equals min → no one flagged for speeding
- Participant has all null Likert values → std dev is NaN → treat as 0 variance → trigger low variance check
- Only one unique Likert response pattern in dataset → duplicate check fires for everyone → expected behavior
- max_possible = 0 in normalize_score (all checks skipped) → return 0, do not divide

---

## Test Cases

Create a throwaway file `test_slice2.py` in the project root to verify:

```python
import pandas as pd
import numpy as np
from detector import run_detection
from utils import get_likert_columns, get_text_columns, normalize_score

# --- Test 1: get_likert_columns ---
df_test = pd.DataFrame({
    "Q1": [1, 2, 3, 4, 5],
    "Q2": [3, 3, 3, 3, 3],
    "Age": [22, 34, 45, 28, 31],        # numeric but range > 7
    "Comment": ["hello", "world", "foo", "bar", "baz"]
})
likert = get_likert_columns(df_test)
assert "Q1" in likert and "Q2" in likert, "Q1 and Q2 should be Likert"
assert "Age" not in likert, "Age should not be Likert"
assert "Comment" not in likert, "Comment should not be Likert"
print("Test 1 passed: get_likert_columns")

# --- Test 2: get_text_columns ---
df_test2 = pd.DataFrame({
    "open_response": ["This is a long response text", "Another lengthy response here",
                      "More text here yes", "Short", "Also quite long response text"],
    "email": ["a@b.com", "c@d.com", "e@f.com", "g@h.com", "i@j.com"],
    "Q1": [1, 2, 3, 4, 5]
})
text_cols = get_text_columns(df_test2)
assert "open_response" in text_cols, "open_response should be a text column"
assert "email" not in text_cols, "email should be excluded"
assert "Q1" not in text_cols, "Q1 should not be a text column"
print("Test 2 passed: get_text_columns")

# --- Test 3: normalize_score ---
assert normalize_score(100.0, 100.0) == 100
assert normalize_score(0.0, 100.0) == 0
assert normalize_score(50.0, 100.0) == 50
assert normalize_score(0.0, 0.0) == 0  # division by zero guard
print("Test 3 passed: normalize_score")

# --- Test 4: run_detection — bot row vs human row ---
df_detection = pd.DataFrame({
    "Q1": [3, 1],   # row 0: human-like, row 1: bot-like (straight-liner)
    "Q2": [4, 1],
    "Q3": [2, 1],
    "Q4": [5, 1],
    "Q5": [3, 1],
    "Duration (in seconds)": [300, 8]  # row 1: speeder
})
result = run_detection(df_detection, cutoff=75)
assert "bot_score" in result.columns, "bot_score column missing"
assert "bot_flags" in result.columns, "bot_flags column missing"
assert "is_flagged" in result.columns, "is_flagged column missing"
assert result.loc[1, "bot_score"] > result.loc[0, "bot_score"], \
    "Bot row should score higher than human row"
assert result.loc[1, "is_flagged"] == True, "Bot row should be flagged"
print("Test 4 passed: run_detection bot vs human")

print("\nAll Slice 2 tests passed.")
```

Run with: `python3 test_slice2.py`

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector" for
the Oishi Lab. The scaffold is complete (Slice 1 done). I now need to
implement the full quantitative bot detection logic in utils.py and
detector.py. The app detects bot-like behavior in survey CSV data where
each row is one participant. Tech stack: Python 3, pandas, numpy, scipy.

TASK:
Implement all functions in utils.py and detector.py as specified below.
Do not modify app.py, qualitative.py, requirements.txt, or README.md.

IMPLEMENT utils.py — three functions:

1. get_likert_columns(df) -> list[str]
   A column is Likert if ALL of:
   - dtype is numeric (int64 or float64)
   - All non-null values fall within 1–7 inclusive
   - Fewer than 8 unique non-null values
   Return list of qualifying column names.

2. get_text_columns(df) -> list[str]
   A column is open-ended text if ALL of:
   - dtype is object (string)
   - Mean response length > 20 characters (nulls excluded)
   - Column name does not contain (case-insensitive):
     id, timestamp, duration, email, date, time, ip, status, response_id
   Return list of qualifying column names.

3. normalize_score(weighted_sum: float, max_possible: float) -> int
   Returns int(round((weighted_sum / max_possible) * 100))
   If max_possible == 0, return 0.

IMPLEMENT detector.py — eight functions:

All check functions return a dict with exactly these keys:
{
    "scores": list[float],  # one per row, 0.0–100.0
    "flags":  list[str],    # check name if triggered, "" if not
    "weight": int,
    "skipped": bool
}
If skipped is True: scores = [0.0] * len(df), flags = [""] * len(df)

1. check_straight_lining(df, likert_cols) -> dict
   Weight: 30
   Skip if: fewer than 3 Likert columns
   Triggered per row if: std deviation across Likert cols == 0
   Score if triggered: 100.0
   Flag label: "straight_lining"

2. check_low_variance(df, likert_cols) -> dict
   Weight: 25
   Skip if: fewer than 3 Likert columns
   Triggered per row if: row std dev < 10th percentile of all row std devs
   Score if triggered: 100.0
   Flag label: "low_variance"

3. check_range_avoidance(df, likert_cols) -> dict
   Weight: 15
   Skip if: fewer than 2 Likert columns
   Auto-detect scale_max: max value across all Likert columns
   Middle values for scale 1–5: [2, 3, 4]
   Middle values for scale 1–7: [2, 3, 4, 5, 6]
   Triggered per row if: none of the middle values appear in that row
   Score if triggered: 100.0
   Flag label: "range_avoidance"

4. check_extreme_responding(df, likert_cols) -> dict
   Weight: 15
   Skip if: fewer than 2 Likert columns
   Triggered per row if: >= 90% of Likert responses are 1 or scale_max
   Score if triggered: 100.0
   Flag label: "extreme_responding"

5. check_speeder(df) -> dict
   Weight: 25
   Skip if: no column name containing "duration", "time", "seconds",
   or "elapsed" (case-insensitive)
   Triggered per row if: duration < 5th percentile of all durations
   Score if triggered: 100.0
   Flag label: "speeder"

6. check_duplicate_patterns(df, likert_cols) -> dict
   Weight: 20
   Skip if: fewer than 2 participants or fewer than 2 Likert columns
   Triggered per row if: that row's Likert tuple appears more than once
   Score if triggered: 100.0
   Flag label: "duplicate_pattern"

7. check_missing_patterns(df, likert_cols) -> dict
   Weight: 10
   Skip if: fewer than 3 Likert columns
   Triggered per row if: > 50% of Likert columns are null/NaN
   Score if triggered: 100.0
   Flag label: "missing_pattern"

8. run_detection(df, cutoff: int) -> pd.DataFrame
   Steps:
   a. Import and call utils.get_likert_columns(df)
   b. Run all seven check functions
   c. For each row i:
      - active = checks where skipped is False
      - weighted_sum = sum(scores[i] * weight for active checks)
      - max_possible = sum(weight for active checks)
      - bot_score = utils.normalize_score(weighted_sum, max_possible)
      - bot_flags = comma-separated non-empty flags[i] values
      - is_flagged = True if bot_score >= cutoff
   d. Append bot_score (int), bot_flags (str), is_flagged (bool) to a
      copy of df
   e. Return the new DataFrame. Do not modify the original.

EDGE CASES:
- Null/NaN Likert values: treat as 0 variance contribution, exclude from
  range/extreme checks
- All participants same duration: no one flagged for speeding (expected)
- max_possible == 0: normalize_score returns 0

CONSTRAINTS:
- Python 3, pandas, numpy, scipy only
- Do not modify app.py, qualitative.py, requirements.txt, README.md
- Do not use any external packages beyond requirements.txt
- Preserve all existing docstrings from Slice 1 stubs

ACCEPTANCE CRITERIA:
1. All seven check functions return correctly structured dicts
2. run_detection returns DataFrame with bot_score, bot_flags, is_flagged
3. bot_score values are integers 0–100
4. is_flagged is True when bot_score >= cutoff
5. test_slice2.py passes all assertions

DO NOT:
- Modify files outside utils.py and detector.py
- Add any UI logic
- Add any Anthropic API calls

OUTPUT:
Write complete implementations for utils.py and detector.py.
No explanations — just code. List assumptions made.
```

---

## Claude Code Debugging Prompt

Use this if test_slice2.py fails after Codex generates the logic:

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector."
Slice 2 implements quantitative bot detection in utils.py and
detector.py. I ran the Codex prompt and pasted the output. Now
test_slice2.py is failing.

CURRENT PROBLEM:
[Paste exact error or failed assertion here]

RELEVANT FILES:
- utils.py
- detector.py
- test_slice2.py

WHAT CODEX BUILT:
Full implementation of all check functions and run_detection().
Problem is in the logic or return format of one or more functions.

CONSTRAINTS:
- Python 3, pandas, numpy, scipy only
- Do not modify app.py, qualitative.py, requirements.txt
- Do not refactor working functions — fix only what is failing
- All check functions must return dict with keys:
  scores (list), flags (list), weight (int), skipped (bool)

ACCEPTANCE CRITERIA:
1. All assertions in test_slice2.py pass
2. bot_score values are integers 0–100
3. is_flagged is True when bot_score >= cutoff
4. bot_flags is a comma-separated string of triggered check names

DO NOT:
- Rewrite functions that are passing their tests
- Add any UI logic
- Change the folder structure

OUTPUT:
Fix the problem. Summarize what changed and why.
List follow-up issues for the next session.
```

---

## Slice Completion Checklist

- [ ] All test cases in test_slice2.py passing
- [ ] Claude Code debugging output reviewed and logged (if applicable)
- [ ] CHANGELOG.md updated
- [ ] KNOWN_ISSUES.md updated
- [ ] DECISIONS.md updated
- [ ] Delete test_slice2.py before committing: `rm test_slice2.py`
- [ ] Git commit: `git add . && git commit -m "Slice 2 complete — detection engine"`
- [ ] Pushed to GitHub: `git push`
