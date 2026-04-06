# SLICE_3_STREAMLIT_UI.md
# Survey Bot Detector
# Oishi Lab — Marcus Gao

---

## Goal

Build the complete, polished Streamlit UI in `app.py`. Wire the detection
engine from Slice 2C into a clean, paneled interface that guides the
researcher step by step from upload to download.

---

## Acceptance Criteria

1. App launches with `python3 -m streamlit run app.py` — no errors
2. Sidebar contains all settings: cutoff slider, qualitative toggle, API key field
3. Main area is divided into four clearly labelled steps
4. CSV upload shows a 5-row preview of the uploaded file
5. Run button shows warning if no file is uploaded
6. Run button shows warning if qualitative mode is on but no API key entered
7. After running, results summary shows total participants, flagged count, flagged %
8. Two tabs appear: "Flagged Responses" and "Full Results"
9. Flagged tab shows only is_flagged == True rows, or a success message if none
10. Full Results tab shows all rows with appended score columns
11. Download Full Flagged CSV produces a valid CSV with all rows and score columns
12. Download Cleaned CSV produces a valid CSV with flagged rows removed
13. Uploading a new file clears previous results
14. App runs cleanly on test_survey.csv with correct flagged/clean counts

---

## Files to Modify

| File | Changes |
|---|---|
| `app.py` | Full replacement of current stub |

**Do not modify:** `detector.py`, `qualitative.py`, `utils.py`,
`requirements.txt`, `README.md`

---

## UI Layout Specification

```
┌─────────────────────────────────────────────────────────────┐
│  SIDEBAR                                                     │
│  ─────────────────────────────────────────────────────────  │
│  ⚙️ Settings                                                 │
│  About this tool [expander]                                  │
│  ─────────────────────────────────────────────────────────  │
│  Suspicion Score Cutoff                                      │
│  [slider 0–100, default 75]                                  │
│  caption: what the cutoff does                               │
│  ─────────────────────────────────────────────────────────  │
│  Qualitative Analysis Mode                                   │
│  [toggle]                                                    │
│  caption: what this does                                     │
│  If toggled: [API key password input]                        │
│              caption: session only, never saved              │
├─────────────────────────────────────────────────────────────┤
│  MAIN AREA                                                   │
│                                                              │
│  🔍 Survey Bot Detector                                      │
│  subtitle                                                    │
│  ───────────────────────────────────────────────────────    │
│  Step 1 — Upload Your Survey Data                            │
│  caption: what to upload                                     │
│  [file uploader — CSV only]                                  │
│  If uploaded: ✅ filename loaded — N rows, M columns         │
│               [5-row preview table]                          │
│  ───────────────────────────────────────────────────────    │
│  Step 2 — Run Bot Detection                                  │
│  caption: what the engine does                               │
│  [🚀 Run Bot Detection button]                               │
│  ───────────────────────────────────────────────────────    │
│  Step 3 — Review Results     (shown after run)               │
│  [Total] [Flagged] [Cutoff] metrics                          │
│  [🚨 Flagged Responses] [📋 Full Results] tabs               │
│  ───────────────────────────────────────────────────────    │
│  Step 4 — Download Results   (shown after run)               │
│  [📥 Download Full Flagged CSV] [✅ Download Cleaned CSV]    │
└─────────────────────────────────────────────────────────────┘
```

---

## Component / Function Contracts

### Session state keys

| Key | Type | Default | Set when |
|---|---|---|---|
| `df_raw` | DataFrame | None | File uploaded |
| `df_results` | DataFrame | None | Run completes |
| `cutoff` | int | 75 | Slider moved |
| `qualitative_mode` | bool | False | Toggle changed |
| `api_key` | str | "" | Key field filled |
| `uploaded_filename` | str | None | File uploaded |

### Sidebar

```
1. st.sidebar.title("⚙️ Settings")

2. with st.sidebar.expander("About this tool"):
   3–4 sentences: what the tool does, what bot_score means
   (0 = clean, 100 = suspicious), what the two output files contain.

3. st.sidebar.markdown("---")
   st.sidebar.subheader("Suspicion Score Cutoff")
   cutoff = st.sidebar.slider(min=0, max=100, value=75,
                               label_visibility="collapsed")
   st.sidebar.caption("Responses at or above this score are flagged.
   Lower = stricter. Default 75 works well for most datasets.")

4. st.sidebar.markdown("---")
   st.sidebar.subheader("Qualitative Analysis Mode")
   qualitative_mode = st.sidebar.toggle("Enable Qualitative Mode")
   st.sidebar.caption("When enabled, open-ended text responses are
   scored for AI-generated content via the Claude API. Results appear
   as a separate ai_text_score column.")
   If qualitative_mode:
     api_key = st.sidebar.text_input("Anthropic API Key",
                                      type="password",
                                      placeholder="sk-ant-...")
     st.sidebar.caption("Used only during this session. Never saved.")
```

### Main area — Step 1 (Upload)

```
st.subheader("Step 1 — Upload Your Survey Data")
st.caption("Upload a CSV export from Qualtrics, Google Forms, or any
survey platform. Each row should represent one participant.")
uploaded_file = st.file_uploader(type=["csv"],
                                  label_visibility="collapsed")
On upload:
  - If new file (different from uploaded_filename in session):
    clear st.session_state.df_results
    update st.session_state.uploaded_filename
  - Read into df_raw, store in st.session_state.df_raw
  - st.success(f"✅ {name} loaded — {n} rows, {m} columns")
  - st.dataframe(df_raw.head(), use_container_width=True)
```

### Main area — Step 2 (Run)

```
st.subheader("Step 2 — Run Bot Detection")
st.caption("The detector analyzes response patterns across Likert-scale
items and assigns each participant a suspicion score from 0 to 100.
Hard flags catch obvious bots; a composite of psychometric subscores
handles subtler patterns.")
If st.button("🚀 Run Bot Detection", type="primary"):
  Validate file uploaded → st.warning() + st.stop() if missing
  Validate API key if qualitative → st.warning() + st.stop() if missing
  with st.spinner("Analyzing responses..."):
    result = run_detection(df_raw, cutoff)
    If qualitative_mode:
      try: result = run_qualitative(result, api_key)
      except: st.error(f"Qualitative failed: {e}. Showing quantitative results.")
    st.session_state.df_results = result
  st.success("✅ Analysis complete.")
```

### Main area — Step 3 (Results) — conditional on df_results

```
st.subheader("Step 3 — Review Results")
Metrics using st.columns(3):
  col1: st.metric("Total Participants", total)
  col2: st.metric("Flagged", flagged,
                   delta=f"{pct}% of responses",
                   delta_color="inverse")
  col3: st.metric("Suspicion Cutoff", f"{cutoff}/100")

tab1, tab2 = st.tabs(["🚨 Flagged Responses", "📋 Full Results"])
tab1:
  If flagged rows: st.dataframe(flagged_df, use_container_width=True)
  Else: st.success("✅ No suspicious responses at this cutoff.
        Try lowering the cutoff to see borderline cases.")
tab2:
  st.caption("All participants with bot_score, bot_flags, and
  is_flagged appended.")
  st.dataframe(df_results, use_container_width=True)
```

### Main area — Step 4 (Downloads) — conditional on df_results

```
st.subheader("Step 4 — Download Results")
dl_col1, dl_col2 = st.columns(2)
dl_col1:
  st.caption("All rows with scores and flag labels. Use to review
  borderline cases.")
  st.download_button("📥 Download Full Flagged CSV",
    data=df_results.to_csv(index=False).encode("utf-8"),
    file_name="flagged_responses.csv", mime="text/csv",
    use_container_width=True)
dl_col2:
  st.caption("Rows below the cutoff only. Ready for analysis.")
  st.download_button("✅ Download Cleaned CSV",
    data=cleaned_df.to_csv(index=False).encode("utf-8"),
    file_name="cleaned_responses.csv", mime="text/csv",
    use_container_width=True)
```

---

## Edge Cases to Handle

- New file uploaded after results exist → clear df_results
- All rows flagged → cleaned CSV is empty but still downloads
- No rows flagged → flagged tab shows success message
- Qualitative API call fails → catch exception, show error, keep
  quantitative results
- CSV has no Likert columns → scores all 0, no flags, show st.info()

---

## Test Cases

Manual verification — work through each step:

1. `python3 -m streamlit run app.py` → page loads, sidebar visible
2. Sidebar expander "About this tool" opens and shows explanation
3. Cutoff slider moves 0–100, default is 75
4. Qualitative toggle off → no API key field visible
5. Qualitative toggle on → API key field appears with caption
6. Click Run without uploading → warning appears, nothing runs
7. Toggle qualitative on, leave key blank, click Run → warning appears
8. Upload test_survey.csv → "✅ test_survey.csv loaded — 15 rows, 12 columns"
9. 5-row preview table appears below success message
10. Click Run → spinner appears, then "✅ Analysis complete."
11. Metrics show: Total=15, Flagged=6, Cutoff=75/100
12. Flagged Responses tab shows 6 rows
13. Full Results tab shows all 15 rows with bot_score/bot_flags/is_flagged
14. Download Full Flagged CSV → open in Excel, confirm 15 rows and score columns
15. Download Cleaned CSV → open in Excel, confirm 9 rows, no is_flagged=True rows
16. Upload a second CSV → results clear, new preview appears

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Survey Bot Detector" for
the Oishi Lab. The detection engine is fully implemented in detector.py
and qualitative.py. I now need to build the complete polished Streamlit
UI in app.py. The UI uses a sidebar for settings and a main area with
four labelled steps. Tech stack: Python 3, Streamlit, pandas.

TASK:
Replace the current app.py stub with a complete polished Streamlit
UI. Do not modify any other file.

IMPORTS:
import streamlit as st
import pandas as pd
from detector import run_detection
from qualitative import run_qualitative

PAGE CONFIG:
st.set_page_config(
    page_title="Survey Bot Detector",
    page_icon="🔍",
    layout="wide"
)

SIDEBAR — implement in this exact order:

1. st.sidebar.title("⚙️ Settings")

2. with st.sidebar.expander("About this tool"):
   Write 3–4 sentences explaining what the tool does, what bot_score
   means (0=clean, 100=suspicious), and what the two download files
   contain.

3. st.sidebar.markdown("---")
   st.sidebar.subheader("Suspicion Score Cutoff")
   cutoff = st.sidebar.slider(
     "Suspicion Score Cutoff", min_value=0, max_value=100, value=75,
     label_visibility="collapsed"
   )
   st.sidebar.caption("Responses at or above this score are flagged
   as suspicious. Lower = stricter. Default 75 works for most datasets.")
   Store cutoff in st.session_state.cutoff

4. st.sidebar.markdown("---")
   st.sidebar.subheader("Qualitative Analysis Mode")
   qualitative_mode = st.sidebar.toggle(
     "Enable Qualitative Mode",
     help="Analyzes open-ended text responses for AI-generated content.
     Requires an Anthropic API key."
   )
   st.sidebar.caption("When enabled, open-ended text responses are
   scored for AI-generated content using the Claude API. Results appear
   as a separate ai_text_score column.")
   Store in st.session_state.qualitative_mode
   If qualitative_mode is True:
     api_key = st.sidebar.text_input(
       "Anthropic API Key", type="password", placeholder="sk-ant-..."
     )
     st.sidebar.caption("Used only during this session. Never saved to disk.")
     Store in st.session_state.api_key
   Else:
     st.session_state.api_key = ""

MAIN AREA — implement in this exact order:

1. Title block:
   st.title("🔍 Survey Bot Detector")
   st.markdown("Automatically detect and flag bot-like responses in
   survey data. Upload a CSV, run the analysis, and download your
   cleaned dataset.")
   st.markdown("---")

2. STEP 1 — UPLOAD:
   st.subheader("Step 1 — Upload Your Survey Data")
   st.caption("Upload a CSV export from Qualtrics, Google Forms, or
   any survey platform. Each row should represent one participant.")
   uploaded_file = st.file_uploader(
     "Upload Survey CSV", type=["csv"], label_visibility="collapsed"
   )
   If uploaded_file is not None:
     df = pd.read_csv(uploaded_file)
     If st.session_state.get("uploaded_filename") != uploaded_file.name:
       st.session_state.df_results = None
       st.session_state.uploaded_filename = uploaded_file.name
     st.session_state.df_raw = df
     n_rows, n_cols = df.shape
     st.success(f"✅ {uploaded_file.name} loaded — {n_rows} rows, {n_cols} columns")
     st.dataframe(df.head(), use_container_width=True)
   st.markdown("---")

3. STEP 2 — RUN:
   st.subheader("Step 2 — Run Bot Detection")
   st.caption("The detector analyzes response patterns across all
   Likert-scale items and assigns each participant a suspicion score
   from 0 (clean) to 100 (highly suspicious). Hard flags catch obvious
   bots; a composite of psychometric subscores handles subtler patterns.")
   If st.button("🚀 Run Bot Detection", type="primary"):
     If st.session_state.get("df_raw") is None:
       st.warning("⚠️ Please upload a CSV file first.")
       st.stop()
     If st.session_state.get("qualitative_mode") and \
        not st.session_state.get("api_key", "").strip():
       st.warning("⚠️ Please enter your Anthropic API key in the
       sidebar to use Qualitative Analysis Mode.")
       st.stop()
     with st.spinner("Analyzing responses — this may take a moment
     for large datasets..."):
       result = run_detection(
         st.session_state.df_raw,
         st.session_state.get("cutoff", 75)
       )
       If st.session_state.get("qualitative_mode"):
         try:
           result = run_qualitative(result, st.session_state.api_key)
         except Exception as e:
           st.error(f"Qualitative analysis failed: {e}. Quantitative
           results are still available.")
       st.session_state.df_results = result
     st.success("✅ Analysis complete.")
   st.markdown("---")

4. STEP 3 — RESULTS (only if st.session_state.get("df_results") is not None):
   st.subheader("Step 3 — Review Results")
   df_results = st.session_state.df_results
   total = len(df_results)
   flagged = int(df_results["is_flagged"].sum())
   pct = round((flagged / total) * 100, 1) if total > 0 else 0.0
   flagged_df = df_results[df_results["is_flagged"] == True]
   cleaned_df = df_results[df_results["is_flagged"] == False]
   col1, col2, col3 = st.columns(3)
   col1.metric("Total Participants", total)
   col2.metric("Flagged", flagged,
               delta=f"{pct}% of responses",
               delta_color="inverse")
   col3.metric("Suspicion Cutoff",
               f"{st.session_state.get('cutoff', 75)}/100")
   tab1, tab2 = st.tabs(["🚨 Flagged Responses", "📋 Full Results"])
   With tab1:
     If len(flagged_df) > 0:
       st.caption(f"{flagged} response(s) flagged at cutoff
       {st.session_state.get('cutoff', 75)}.")
       st.dataframe(flagged_df, use_container_width=True)
     Else:
       st.success("✅ No suspicious responses detected at this cutoff.
       Try lowering the cutoff slider to see borderline cases.")
   With tab2:
     st.caption("All participants with bot_score, bot_flags, and
     is_flagged columns appended to original data.")
     st.dataframe(df_results, use_container_width=True)
   st.markdown("---")

5. STEP 4 — DOWNLOADS (only if st.session_state.get("df_results") is not None):
   st.subheader("Step 4 — Download Results")
   dl_col1, dl_col2 = st.columns(2)
   With dl_col1:
     st.caption("All rows with suspicion scores and flag labels
     appended. Use this to review borderline cases.")
     st.download_button(
       label="📥 Download Full Flagged CSV",
       data=df_results.to_csv(index=False).encode("utf-8"),
       file_name="flagged_responses.csv",
       mime="text/csv",
       use_container_width=True
     )
   With dl_col2:
     st.caption("Only rows below the suspicion cutoff. Ready to use
     directly in your statistical analysis.")
     st.download_button(
       label="✅ Download Cleaned CSV",
       data=cleaned_df.to_csv(index=False).encode("utf-8"),
       file_name="cleaned_responses.csv",
       mime="text/csv",
       use_container_width=True
     )

CONSTRAINTS:
- Use st.session_state for all persistent values
- Steps 3 and 4 only render if st.session_state.df_results is not None
- No detection logic in app.py — only call run_detection() and
  run_qualitative()
- Do not use st.form()
- All download data must be .encode("utf-8") bytes

ACCEPTANCE CRITERIA:
1. App launches without errors
2. Sidebar shows all settings with correct defaults
3. All four steps render correctly
4. Warnings show correctly on validation failures
5. Results show correct metrics, two tabs, two download buttons
6. New file upload clears previous results

DO NOT:
- Add detection logic to app.py
- Modify detector.py, utils.py, qualitative.py, requirements.txt
- Use st.form()
- Add features outside this slice

OUTPUT:
Write the complete app.py. No explanations — just code.
List assumptions made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am building "Survey Bot Detector." Slice 3 implements the full
polished Streamlit UI in app.py. I ran the Codex output and am
testing manually.

CURRENT PROBLEM:
[Describe exactly what is broken — error, wrong behavior, or which
manual test step failed and what happened instead]

RELEVANT FILES:
- app.py
- detector.py (do not modify)
- qualitative.py (do not modify)
- utils.py (do not modify)

WHAT CODEX BUILT:
Full Streamlit UI with sidebar settings, four labelled steps,
tabbed results preview, and two download buttons.

CONSTRAINTS:
- Do not modify detector.py, utils.py, or qualitative.py
- No detection logic in app.py
- Use st.session_state for all persistent values
- Fix only what is broken — do not refactor working sections

ACCEPTANCE CRITERIA:
1. App launches without errors
2. All 16 manual test steps pass
3. Warnings appear correctly on validation failures
4. Both download buttons produce valid CSV files
5. New file upload clears stale results

DO NOT:
- Rewrite sections that are working
- Add features outside this slice
- Change the folder structure

OUTPUT:
Fix the problem. Summarize what changed and why.
List follow-up issues for next session.
```

---

## Slice Completion Checklist

- [ ] All 16 manual test steps verified
- [ ] Claude Code debugging reviewed and logged (if applicable)
- [ ] CHANGELOG.md updated
- [ ] KNOWN_ISSUES.md updated
- [ ] DECISIONS.md updated
- [ ] Git commit: `git add . && git commit -m "Slice 3 complete — Streamlit UI"`
- [ ] Pushed to GitHub: `git push`
