# SLICE_1_SCAFFOLD.md
# Survey Bot Detector
# Oishi Lab — Marcus Gao

---

## Goal

Set up the complete project scaffold: all files, folder structure, dependencies, and empty module stubs so the project is ready for feature development.

---

## Acceptance Criteria

1. `requirements.txt` exists with all dependencies listed
2. `README.md` exists with setup and launch instructions
3. `app.py` exists as an empty Streamlit stub that runs without errors
4. `detector.py` exists with empty function stubs matching the architecture
5. `qualitative.py` exists with empty function stubs matching the architecture
6. `utils.py` exists with empty function stubs matching the architecture
7. Running `python3 -m streamlit run app.py` launches without errors

---

## Files to Create

| File | Purpose |
|---|---|
| `requirements.txt` | All pip dependencies with version pins |
| `README.md` | Setup and launch instructions for lab members |
| `app.py` | Main Streamlit app — UI only, no logic yet |
| `detector.py` | Quantitative bot detection engine — stubs only |
| `qualitative.py` | AI text detection module — stubs only |
| `utils.py` | Shared helper functions — stubs only |

---

## Component / Function Contracts

### utils.py
```
get_likert_columns(df) -> list[str]
    Input: any pandas DataFrame
    Output: list of column names classified as Likert scale

get_text_columns(df) -> list[str]
    Input: any pandas DataFrame
    Output: list of column names classified as open-ended text

normalize_score(weighted_sum: float, max_possible: float) -> int
    Input: weighted sum of triggered check scores, max possible weighted sum
    Output: integer score 0–100
```

### detector.py
```
run_detection(df, cutoff: int) -> pd.DataFrame
    Input: raw uploaded DataFrame, user-defined suspicion score cutoff
    Output: DataFrame with bot_score, bot_flags, is_flagged columns appended

check_straight_lining(df, likert_cols) -> dict
check_low_variance(df, likert_cols) -> dict
check_range_avoidance(df, likert_cols) -> dict
check_extreme_responding(df, likert_cols) -> dict
check_speeder(df) -> dict
check_duplicate_patterns(df, likert_cols) -> dict
check_missing_patterns(df, likert_cols) -> dict

    Each check returns a dict with keys:
    - scores: list[float]  (one score per participant row, 0–100)
    - flags: list[str]     (flag label if triggered, empty string if not)
    - weight: int          (check's contribution weight)
    - skipped: bool        (True if skip condition was met)
```

### qualitative.py
```
run_qualitative(df, api_key: str) -> pd.DataFrame
    Input: DataFrame (post-detection), valid Anthropic API key string
    Output: same DataFrame with ai_text_score column appended
```

---

## Edge Cases to Handle

- CSV has no numeric columns → detection engine should return bot_score of 0 for all rows with a note in bot_flags
- CSV has fewer than 3 Likert columns → straight-lining and low variance checks are skipped
- No duration/timing column found → speeder check is skipped
- Only 1 participant row → duplicate pattern check is skipped
- Qualitative mode on but no text columns detected → skip qualitative analysis gracefully, no crash

---

## Test Cases

1. Run `pip3 install -r requirements.txt` — completes with no errors
2. Run `python3 -m streamlit run app.py` — browser opens, page loads, no crash
3. Import each module in a Python shell — no import errors:
   ```python
   import app
   import detector
   import qualitative
   import utils
   ```

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector" for
the Oishi Lab. It detects bot responses in survey CSV data. The tech
stack is Python 3, Streamlit, pandas, numpy, scipy, and the Anthropic
Python SDK. The app has four modules: app.py (UI), detector.py
(quantitative bot detection), qualitative.py (AI text detection),
utils.py (shared helpers).

TASK:
Create the complete project scaffold for Slice 1. All Python files
should contain only empty stubs — correct function signatures with
docstrings and `pass` bodies, no implementation logic yet.

FILES TO CREATE:

1. requirements.txt
   - streamlit>=1.32.0
   - pandas>=2.0.0
   - numpy>=1.26.0
   - scipy>=1.12.0
   - anthropic>=0.40.0

2. README.md
   - Title: Survey Bot Detector
   - One paragraph: what the tool does
   - Prerequisites section: Python 3.9+, pip3
   - Installation section: git clone, pip3 install -r requirements.txt
   - Launch section: python3 -m streamlit run app.py
   - Notes: API key only needed for qualitative mode

3. app.py
   - Import streamlit as st
   - st.title("Survey Bot Detector")
   - st.write("Upload a CSV to begin.")
   - No other logic

4. utils.py — stub these exact functions:
   - get_likert_columns(df) -> list[str]
   - get_text_columns(df) -> list[str]
   - normalize_score(weighted_sum: float, max_possible: float) -> int

5. detector.py — stub these exact functions:
   - run_detection(df, cutoff: int) -> pd.DataFrame
   - check_straight_lining(df, likert_cols) -> dict
   - check_low_variance(df, likert_cols) -> dict
   - check_range_avoidance(df, likert_cols) -> dict
   - check_extreme_responding(df, likert_cols) -> dict
   - check_speeder(df) -> dict
   - check_duplicate_patterns(df, likert_cols) -> dict
   - check_missing_patterns(df, likert_cols) -> dict
   Each check function returns a dict with keys: scores (list),
   flags (list), weight (int), skipped (bool)

6. qualitative.py — stub these exact functions:
   - run_qualitative(df, api_key: str) -> pd.DataFrame

CONSTRAINTS:
- Python 3 only
- No implementation logic — stubs only with docstrings and pass
- All imports at the top of each file
- Follow the exact function signatures above

ACCEPTANCE CRITERIA:
1. pip3 install -r requirements.txt completes without errors
2. python3 -m streamlit run app.py launches browser without errors

DO NOT:
- Implement any detection logic
- Add features outside this slice
- Leave TODOs without a docstring explaining the function's purpose

OUTPUT:
Write the complete files. No explanations — just code. List assumptions made.
```

---

## Claude Code Debugging Prompt

Use this if anything breaks after Codex generates the scaffold:

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector."
I just ran the Slice 1 Codex scaffold prompt and pasted the output
into my project files.

CURRENT PROBLEM:
[Paste exact error message here]

RELEVANT FILES:
- app.py
- detector.py
- qualitative.py
- utils.py
- requirements.txt

WHAT CODEX BUILT:
Scaffold only — empty stubs with docstrings and pass bodies.
No implementation logic. The app should launch and display a title.

CONSTRAINTS:
- Python 3, Streamlit, pandas, numpy, scipy, anthropic
- Do not implement any detection logic yet — stubs only
- Do not change function signatures or file structure

ACCEPTANCE CRITERIA:
1. pip3 install -r requirements.txt completes with no errors
2. python3 -m streamlit run app.py opens browser without crashing
3. All modules import without errors

DO NOT:
- Add any detection logic
- Change the folder structure
- Modify files that are working

OUTPUT:
Fix the problem. Summarize what changed and why. List any follow-up
issues for the next session.
```

---

## Slice Completion Checklist

- [ ] All test cases passing
- [ ] Claude Code debugging output reviewed and logged (if applicable)
- [ ] CHANGELOG.md updated
- [ ] KNOWN_ISSUES.md updated
- [ ] DECISIONS.md updated
- [ ] Git commit: `git add . && git commit -m "Slice 1 complete — project scaffold"`
- [ ] Pushed to GitHub: `git push -u origin main`
