# SLICE_4_QUALITATIVE_MODE.md
# Survey Bot Detector
# Oishi Lab — Marcus Gao

---

## Goal

Implement the qualitative AI text detection logic in `qualitative.py`.
When called, the function auto-detects open-ended text columns, sends
participant responses to the Claude API in batches, receives a suspicion
score (0–100) per response indicating likelihood of AI-generated content,
and appends a single `ai_text_score` column to the DataFrame.

---

## Acceptance Criteria

1. `run_qualitative(df, api_key)` returns a DataFrame with `ai_text_score`
   column appended
2. `ai_text_score` is an integer 0–100 per participant
3. Text columns are auto-detected using `utils.get_text_columns(df)`
4. Responses are sent to Claude in batches of 20 or fewer
5. Scores are averaged across all text columns per participant
6. Rows with no text responses receive `ai_text_score = 0`
7. API errors are raised as exceptions (caught by app.py)
8. Claude model used: `claude-sonnet-4-20250514`
9. API key passed at runtime — never hardcoded
10. Verified manually by running the full app with qualitative mode on
    and a real API key

---

## Files to Modify

| File | Changes |
|---|---|
| `qualitative.py` | Full implementation replacing the Slice 1 stub |

**Do not modify:** `app.py`, `detector.py`, `utils.py`,
`requirements.txt`, `README.md`

---

## Component / Function Contracts

### run_qualitative(df, api_key) -> pd.DataFrame

```
Input:
  df: pandas DataFrame — output of run_detection(), already has
      bot_score, bot_flags, is_flagged columns present
  api_key: str — Anthropic API key entered by user in session

Output:
  Same DataFrame with one new column appended:
  - ai_text_score: int, 0–100 per participant

Steps:
1. Import anthropic, call anthropic.Anthropic(api_key=api_key)
2. Call utils.get_text_columns(df) to get text_cols
3. If text_cols is empty:
   - Append ai_text_score = 0 for all rows
   - Return df copy with column appended
4. For each text column in text_cols:
   - Collect all responses as a list (preserve row order)
   - Replace NaN/None with empty string ""
   - Split into batches of 20
   - For each batch:
     a. Build numbered list of responses for the prompt
     b. Call Claude API with the scoring prompt (see below)
     c. Parse JSON array of integers from response
     d. If parse fails: assign 50 (neutral) to all in batch
   - Collect all scores for this column as a list (one per row)
5. Average scores across all text columns per participant:
   - For each row: mean of that row's scores across all text columns
   - Round to nearest integer
   - If a row had empty string for all text columns: score = 0
6. Append ai_text_score column to df.copy()
7. Return new DataFrame — do not modify original
```

---

## API Prompt Design

### System prompt
```
You are a research assistant helping detect AI-generated text in
survey responses. You will be given a numbered list of survey
responses. For each response, output a single integer from 0 to 100
representing the likelihood that the response was written by an AI
rather than a human participant.

Scoring guide:
0   = Clearly human-written (personal, specific, informal, emotional)
25  = Probably human (some generic phrasing but feels authentic)
50  = Uncertain (could be either)
75  = Probably AI-generated (generic, polished, impersonal)
100 = Clearly AI-generated (formulaic, explicitly identifies as AI,
      or uses corporate/academic boilerplate with no personal detail)

Respond ONLY with a valid JSON array of integers, one per response,
in the same order as the input. Do not include any explanation,
preamble, or text outside the JSON array.

Example input:
1. I really struggled with the food at first but eventually loved it
2. Study abroad programs offer invaluable cross-cultural experiences

Example output:
[5, 82]
```

### User prompt (built per batch)
```
Score each of the following survey responses for likelihood of being
AI-generated:

1. {response_1}
2. {response_2}
...
N. {response_N}
```

### API call parameters
```python
client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1000,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": user_prompt}]
)
```

### Response parsing
```
1. Extract text from response.content[0].text
2. Strip whitespace
3. Parse with json.loads()
4. Validate: result must be a list of integers same length as batch
5. Clamp each value to 0–100
6. On any parse/validation error: assign 50 to all responses in batch
```

---

## Edge Cases to Handle

- No text columns detected → ai_text_score = 0 for all, return early
- Participant has empty/null response in a text column → treat as ""
  → score 0 for that cell (empty string = no signal)
- API returns malformed JSON → catch json.JSONDecodeError, assign 50
  to entire batch
- API returns array of wrong length → assign 50 to entire batch
- API raises authentication error → let exception propagate to app.py
  (app.py catches and shows st.error())
- All text columns have empty responses → ai_text_score = 0 for all
- Single text column with one row → batch of 1, still works

---

## Test Cases

Manual verification — no automated script needed for API calls:

1. Run app with qualitative mode OFF → ai_text_score column absent
   from output CSVs (expected — qualitative not called)
2. Run app with qualitative mode ON, wrong API key →
   st.error() appears after run, quantitative results still visible
3. Run app with qualitative mode ON, valid API key, test_survey.csv:
   - Analysis completes without error
   - Full Results tab shows ai_text_score column
   - Known AI rows (R003, R005, R007, R009, R011, R013) should score
     higher than human rows on ai_text_score
   - Download Full Flagged CSV → confirm ai_text_score column present
   - Download Cleaned CSV → confirm ai_text_score column present

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector" for
the Oishi Lab. The Streamlit UI (app.py) and detection engine
(detector.py, utils.py) are fully implemented. I now need to implement
qualitative.py — the AI text detection module. It sends survey
open-ended text responses to the Anthropic Claude API and returns a
suspicion score per participant indicating likelihood of AI-generated
content. Tech stack: Python 3, pandas, anthropic SDK, json.

TASK:
Implement run_qualitative() in qualitative.py. Replace the Slice 1
stub entirely. Do not modify any other file.

IMPLEMENT qualitative.py:

IMPORTS:
import pandas as pd
import numpy as np
import anthropic
import json
import utils

CONSTANT — SYSTEM_PROMPT (define at module level):
"""
You are a research assistant helping detect AI-generated text in
survey responses. You will be given a numbered list of survey
responses. For each response, output a single integer from 0 to 100
representing the likelihood that the response was written by an AI
rather than a human participant.

Scoring guide:
0   = Clearly human-written (personal, specific, informal, emotional)
25  = Probably human (some generic phrasing but feels authentic)
50  = Uncertain (could be either)
75  = Probably AI-generated (generic, polished, impersonal)
100 = Clearly AI-generated (formulaic, explicitly identifies as AI,
      or uses corporate/academic boilerplate with no personal detail)

Respond ONLY with a valid JSON array of integers, one per response,
in the same order as the input. Do not include any explanation,
preamble, or text outside the JSON array.

Example input:
1. I really struggled with the food at first but eventually loved it
2. Study abroad programs offer invaluable cross-cultural experiences

Example output:
[5, 82]
"""

IMPLEMENT run_qualitative(df: pd.DataFrame, api_key: str) -> pd.DataFrame:

Docstring: Analyze open-ended text columns for AI-generated content
using the Claude API. Returns df copy with ai_text_score column appended.

Steps:
1. client = anthropic.Anthropic(api_key=api_key)
2. text_cols = utils.get_text_columns(df)
3. If len(text_cols) == 0:
   result = df.copy()
   result["ai_text_score"] = 0
   return result

4. all_col_scores = []  # list of lists, one per text column

5. For each col in text_cols:
   responses = df[col].fillna("").astype(str).tolist()
   col_scores = []
   batch_size = 20
   For i in range(0, len(responses), batch_size):
     batch = responses[i : i + batch_size]
     # Build numbered prompt
     numbered = "\n".join(
       f"{j+1}. {resp}" for j, resp in enumerate(batch)
     )
     user_prompt = (
       "Score each of the following survey responses for likelihood "
       "of being AI-generated:\n\n" + numbered
     )
     try:
       response = client.messages.create(
         model="claude-sonnet-4-20250514",
         max_tokens=1000,
         system=SYSTEM_PROMPT,
         messages=[{"role": "user", "content": user_prompt}]
       )
       raw = response.content[0].text.strip()
       scores = json.loads(raw)
       # Validate
       if not isinstance(scores, list) or len(scores) != len(batch):
         raise ValueError("Unexpected response format")
       scores = [int(max(0, min(100, s))) for s in scores]
     except Exception:
       scores = [50] * len(batch)
     col_scores.extend(scores)
   all_col_scores.append(col_scores)

6. # Average across columns per participant
   scores_matrix = np.array(all_col_scores)  # shape: (n_cols, n_rows)
   # For rows where response was empty string, score is already
   # reflected in col_scores (will be low if Claude sees empty input)
   avg_scores = scores_matrix.mean(axis=0)
   ai_text_scores = [int(round(s)) for s in avg_scores]

7. result = df.copy()
   result["ai_text_score"] = ai_text_scores
   return result

CONSTRAINTS:
- Python 3, pandas, numpy, anthropic SDK, json only
- Model must be claude-sonnet-4-20250514
- Batch size must be 20 or fewer responses per API call
- API errors from authentication must propagate (not be caught here)
  so app.py can display them to the user
- JSON parse errors and format errors must be caught and return 50
  for affected batch
- Do not modify any other file

ACCEPTANCE CRITERIA:
1. run_qualitative returns DataFrame with ai_text_score column (int 0–100)
2. Works correctly when text_cols is empty (returns ai_text_score=0)
3. Handles NaN responses without crashing
4. Known AI rows score higher than human rows on test_survey.csv
5. API auth errors propagate to app.py correctly

DO NOT:
- Modify app.py, detector.py, utils.py, requirements.txt
- Hardcode any API key
- Use any model other than claude-sonnet-4-20250514
- Catch anthropic.AuthenticationError (let it propagate)

OUTPUT:
Write the complete qualitative.py. No explanations — just code.
List assumptions made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am building "Survey Bot Detector." Slice 4 implements qualitative
AI text detection in qualitative.py. I ran the Codex output and am
testing manually with the app running.

CURRENT PROBLEM:
[Describe exactly what is broken — error message, wrong behavior,
or which manual test step failed and what happened instead]

RELEVANT FILES:
- qualitative.py
- utils.py (do not modify)
- app.py (do not modify)

WHAT CODEX BUILT:
run_qualitative() that auto-detects text columns, batches responses,
calls Claude API, parses JSON scores, and appends ai_text_score column.

CONSTRAINTS:
- Do not modify app.py, detector.py, utils.py, requirements.txt
- Model must be claude-sonnet-4-20250514
- Batch size 20 or fewer
- Auth errors must propagate — do not catch anthropic.AuthenticationError
- JSON parse errors must be caught and return 50 for affected batch
- Fix only what is broken

ACCEPTANCE CRITERIA:
1. run_qualitative returns DataFrame with ai_text_score (int 0–100)
2. Works with empty text columns (ai_text_score = 0)
3. Known AI rows score higher than human rows
4. API auth errors show as st.error() in the app

DO NOT:
- Rewrite parts that are working
- Change the folder structure
- Modify any file except qualitative.py

OUTPUT:
Fix the problem. Summarize what changed and why.
List follow-up issues for next session.
```

---

## Slice Completion Checklist

- [ ] Manual test steps 1, 2, and 3 all verified
- [ ] ai_text_score column appears in both download CSVs
- [ ] Known AI rows score higher than human rows on ai_text_score
- [ ] Wrong API key shows st.error(), quantitative results still visible
- [ ] Claude Code debugging reviewed and logged (if applicable)
- [ ] CHANGELOG.md updated
- [ ] KNOWN_ISSUES.md updated
- [ ] DECISIONS.md updated
- [ ] Git commit: `git add . && git commit -m "Slice 4 complete — qualitative analysis mode"`
- [ ] Pushed to GitHub: `git push`
