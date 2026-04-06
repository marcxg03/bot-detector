# SLICE_3_STREAMLIT_UI.md
# Survey Bot Detector
# Oishi Lab — Marcus Gao

---

## Goal

Build the complete Streamlit user interface in `app.py`, wiring the
detection engine from Slice 2 into a fully functional research tool
with file upload, settings, results display, and CSV download buttons.

---

## Acceptance Criteria

1. Researcher can upload a CSV file and see a 5-row preview table
2. Suspicion score cutoff slider is visible with default value of 75
3. Qualitative Analysis Mode toggle is visible
4. When qualitative mode is toggled on, an API key input field appears
5. Clicking "Run Bot Detection" without a file uploaded shows a warning
6. Clicking "Run Bot Detection" with qualitative mode on but no API key
   shows a warning and does not run
7. Clicking "Run Bot Detection" with a valid CSV runs the detection
   engine and displays a results summary
8. Results summary shows: total participants, number flagged, percentage
9. A preview table shows only the flagged rows with all columns visible
10. Download Button 1 produces a CSV with all rows and appended columns
11. Download Button 2 produces a CSV with flagged rows removed
12. App runs without errors on a real survey CSV file

---

## Files to Modify

| File | Changes |
|---|---|
| `app.py` | Full UI implementation — replaces the Slice 1 stub entirely |

**Do not modify:** `detector.py`, `qualitative.py`, `utils.py`,
`requirements.txt`, `README.md`

---

## Component / Function Contracts

### app.py structure (top to bottom)

```
1. Imports
   - streamlit as st
   - pandas as pd
   - detector.run_detection
   - qualitative.run_qualitative

2. Page config
   - st.set_page_config(title="Survey Bot Detector", layout="wide")

3. Title and description
   - st.title("Survey Bot Detector")
   - Brief one-sentence description of what the tool does

4. Section 1 — Upload
   - st.file_uploader() accepting .csv files only
   - If file uploaded: read into DataFrame, store in st.session_state.df_raw
   - Show st.dataframe() preview of first 5 rows

5. Section 2 — Settings (only shown if file is uploaded)
   - st.slider() for cutoff, min=0, max=100, default=75,
     stored in st.session_state.cutoff
   - st.toggle() for qualitative mode,
     stored in st.session_state.qualitative_mode
   - If qualitative mode on: st.text_input() for API key (type="password"),
     stored in st.session_state.api_key

6. Section 3 — Run (only shown if file is uploaded)
   - st.button("Run Bot Detection")
   - On click:
     a. Validate: file uploaded → else st.warning() and stop
     b. Validate: if qualitative mode on, API key entered → else st.warning() and stop
     c. Show st.spinner("Analyzing responses...")
     d. Call detector.run_detection(df_raw, cutoff)
     e. If qualitative mode on: call qualitative.run_qualitative(df_results, api_key)
     f. Store result in st.session_state.df_results

7. Section 4 — Results (only shown if df_results exists in session state)
   - Summary metrics row:
     - Total participants analyzed
     - Number flagged
     - Percentage flagged
   - st.subheader("Flagged Responses Preview")
   - st.dataframe() showing only rows where is_flagged == True
   - If no rows flagged: st.success("No suspicious responses detected.")
   - st.download_button() for flagged CSV (all rows, appended columns)
     label: "Download Full Flagged CSV"
     filename: "flagged_responses.csv"
   - st.download_button() for cleaned CSV (is_flagged == False rows only)
     label: "Download Cleaned CSV"
     filename: "cleaned_responses.csv"
```

### Session state keys used

| Key | Type | Set when |
|---|---|---|
| `df_raw` | DataFrame | File uploaded |
| `df_results` | DataFrame | Run button clicked and detection complete |
| `cutoff` | int | Slider moved (default 75) |
| `qualitative_mode` | bool | Toggle changed |
| `api_key` | str | API key field filled |

---

## Edge Cases to Handle

- User uploads a new file after already running detection →
  clear df_results from session state so stale results don't display
- CSV has no Likert columns detected → detection runs, all bot_scores
  are 0, no rows flagged → show st.info() message explaining this
- All rows are flagged → cleaned CSV is empty → still allow download
  (empty CSV is valid output)
- Qualitative mode on but run_qualitative raises an API error →
  catch exception, show st.error() with the error message, do not crash
- Very large CSV (1000+ rows) → spinner keeps UI responsive during processing

---

## Test Cases

Manual verification steps (no automated script needed for UI slice):

1. Launch app: `python3 -m streamlit run app.py` — page loads with title
2. Upload a CSV → 5-row preview appears
3. Slider defaults to 75, can be moved
4. Toggle qualitative mode on → API key field appears
5. Toggle qualitative mode off → API key field disappears
6. Click Run without uploading file → warning appears, nothing runs
7. Toggle qualitative mode on, leave API key blank, click Run →
   warning appears, nothing runs
8. Upload a real CSV, click Run → spinner appears, results load
9. Results show correct participant count and flagged count
10. Download Full Flagged CSV → file downloads, open in Excel,
    confirm bot_score / bot_flags / is_flagged columns are present
11. Download Cleaned CSV → file downloads, confirm flagged rows are absent

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector" for
the Oishi Lab. Slices 1 and 2 are complete. detector.py and utils.py
are fully implemented. qualitative.py has a run_qualitative(df, api_key)
stub. I now need to build the complete Streamlit UI in app.py.

TASK:
Replace the current app.py stub with a full Streamlit UI implementation.
Do not modify any other file.

IMPLEMENT app.py with these exact sections top to bottom:

1. IMPORTS
   import streamlit as st
   import pandas as pd
   import io
   from detector import run_detection
   from qualitative import run_qualitative

2. PAGE CONFIG
   st.set_page_config(page_title="Survey Bot Detector", layout="wide")

3. TITLE
   st.title("Survey Bot Detector")
   st.write("Upload a survey CSV to automatically detect and flag
   bot-like responses.")

4. SECTION 1 — FILE UPLOAD
   - st.file_uploader() that accepts .csv only
   - On upload: read CSV into pandas DataFrame, store as
     st.session_state.df_raw
   - When a new file is uploaded, clear st.session_state.df_results
     if it exists (prevents stale results from showing)
   - Show st.dataframe(df.head()) preview below uploader

5. SECTION 2 — SETTINGS
   Only render this section if st.session_state.df_raw exists.
   - st.subheader("Settings")
   - Cutoff slider:
     st.slider("Suspicion Score Cutoff", min_value=0, max_value=100,
     value=75, help="Responses at or above this score will be flagged.")
     Store value in st.session_state.cutoff
   - Qualitative mode toggle:
     st.toggle("Enable Qualitative Analysis Mode",
     help="Analyzes open-ended text responses for AI-generated content.
     Requires an Anthropic API key.")
     Store in st.session_state.qualitative_mode
   - If qualitative_mode is True:
     st.text_input("Anthropic API Key", type="password",
     help="Your key is used only during this session and never saved.")
     Store in st.session_state.api_key

6. SECTION 3 — RUN BUTTON
   Only render if st.session_state.df_raw exists.
   - st.button("Run Bot Detection")
   - On click:
     a. If df_raw not in session state: st.warning("Please upload a
        CSV file first.") and st.stop()
     b. If qualitative_mode is True and api_key is empty or None:
        st.warning("Please enter your Anthropic API key to use
        Qualitative Analysis Mode.") and st.stop()
     c. with st.spinner("Analyzing responses..."):
        - Call run_detection(st.session_state.df_raw,
          st.session_state.cutoff)
        - Store result as st.session_state.df_results
        - If qualitative_mode True: call run_qualitative(
          st.session_state.df_results, st.session_state.api_key)
          wrapped in try/except — on exception show st.error(str(e))
          and continue with quantitative results only

7. SECTION 4 — RESULTS
   Only render if st.session_state.df_results exists.
   - st.subheader("Results")
   - Compute:
     total = len(df_results)
     flagged = df_results["is_flagged"].sum()
     pct = round((flagged / total) * 100, 1) if total > 0 else 0
   - Display using st.columns(3) with st.metric():
     col1: "Total Participants" = total
     col2: "Flagged" = flagged
     col3: "Flagged %" = f"{pct}%"
   - st.subheader("Flagged Responses Preview")
   - flagged_df = df_results[df_results["is_flagged"] == True]
   - If len(flagged_df) == 0: st.success("No suspicious responses
     detected.")
   - Else: st.dataframe(flagged_df)
   - st.subheader("Downloads")
   - Download Button 1 — Full Flagged CSV:
     Convert df_results to CSV bytes using io.StringIO
     st.download_button(label="Download Full Flagged CSV",
     data=csv_bytes, file_name="flagged_responses.csv",
     mime="text/csv")
   - Download Button 2 — Cleaned CSV:
     cleaned_df = df_results[df_results["is_flagged"] == False]
     Convert to CSV bytes
     st.download_button(label="Download Cleaned CSV",
     data=csv_bytes, file_name="cleaned_responses.csv",
     mime="text/csv")

CONSTRAINTS:
- Use st.session_state for all persistent values
- All sections after upload must be conditional on df_raw existing
- Results section must be conditional on df_results existing
- Do not implement any detection logic in app.py — only call
  run_detection() and run_qualitative()
- Use io.StringIO to convert DataFrames to CSV bytes for download
- Do not modify any file except app.py

ACCEPTANCE CRITERIA:
1. App launches with python3 -m streamlit run app.py
2. File upload, settings, run button, results, and downloads all work
3. Warning shown if Run clicked without file or without API key
4. Both download buttons produce valid CSV files
5. Stale results cleared when new file is uploaded

DO NOT:
- Add any detection logic to app.py
- Modify detector.py, utils.py, qualitative.py, requirements.txt
- Add any features outside this slice's scope
- Use st.form() — use direct button and widget event handling only

OUTPUT:
Write the complete app.py implementation. No explanations — just code.
List assumptions made.
```

---

## Claude Code Debugging Prompt

Use this if anything fails during manual testing:

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector."
Slice 3 implements the full Streamlit UI in app.py. I ran the Codex
prompt, pasted the output into app.py, and am now testing manually.

CURRENT PROBLEM:
[Describe exactly what is broken — error message, wrong behavior,
or which test step failed]

RELEVANT FILES:
- app.py
- detector.py (do not modify)
- qualitative.py (do not modify)
- utils.py (do not modify)

WHAT CODEX BUILT:
Full Streamlit UI with file upload, settings, run button, results
summary, flagged preview table, and two download buttons.

CONSTRAINTS:
- Do not modify detector.py, utils.py, or qualitative.py
- Do not add detection logic to app.py
- Use st.session_state for all persistent values
- Fix only what is broken — do not refactor working sections

ACCEPTANCE CRITERIA:
1. App launches without errors
2. Upload, settings, run, results, and downloads all work correctly
3. Warnings appear when validation conditions are not met
4. Both download buttons produce valid CSV files

DO NOT:
- Rewrite sections that are working
- Add features outside this slice
- Change the folder structure

OUTPUT:
Fix the problem. Summarize what changed and why.
List follow-up issues for the next session.
```

---

## Slice Completion Checklist

- [ ] All 11 manual test steps verified
- [ ] Claude Code debugging output reviewed and logged (if applicable)
- [ ] CHANGELOG.md updated
- [ ] KNOWN_ISSUES.md updated
- [ ] DECISIONS.md updated
- [ ] Git commit: `git add . && git commit -m "Slice 3 complete — Streamlit UI"`
- [ ] Pushed to GitHub: `git push`
