import io

import streamlit as st
import pandas as pd

import utils
from detector import run_detection, run_detection_heuristic
from qualitative import run_qualitative


st.set_page_config(
    page_title="Survey Bot Detector",
    page_icon="🔍",
    layout="wide",
)

if "cutoff" not in st.session_state:
    st.session_state.cutoff = 95

if "qualitative_mode" not in st.session_state:
    st.session_state.qualitative_mode = False

if "api_key" not in st.session_state:
    st.session_state.api_key = ""

if "df_raw" not in st.session_state:
    st.session_state.df_raw = None

if "df_results" not in st.session_state:
    st.session_state.df_results = None

if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None

if "likert_cols" not in st.session_state:
    st.session_state.likert_cols = None

st.sidebar.title("⚙️ Settings")

with st.sidebar.expander("About this tool"):
    st.write(
        "Survey Bot Detector helps identify bot-like or low-quality survey responses "
        "using quantitative response-pattern checks and optional qualitative text analysis."
    )
    st.write(
        "Each participant receives a `bot_score` from 0 to 100, where 0 indicates "
        "a clean-looking response pattern and 100 indicates highly suspicious behavior."
    )
    st.write(
        "The full flagged download includes all original rows plus scoring columns, "
        "while the cleaned download keeps only responses below your chosen cutoff."
    )

st.sidebar.markdown("---")
st.sidebar.subheader("Detection Method")
detection_method = st.sidebar.radio(
    "Detection Method",
    options=["Classic (Heuristic)", "L1P1 (Statistical — WIP)"],
    label_visibility="collapsed",
    help=(
        "Classic: Fast heuristic detection using straightlining, duplicates, "
        "speeders, variance, and response pattern checks.\n\n"
        "L1P1: Peer-reviewed permutation test (Ilagan & Falk, 2024). "
        "Slower but statistically grounded."
    ),
)

if detection_method == "L1P1 (Statistical — WIP)":
    st.sidebar.warning(
        "⚠️ L1P1 is still being validated. Results should be compared "
        "against Classic method before use in analysis."
    )

# Reset cutoff default when method changes
if st.session_state.get("detection_method") != detection_method:
    st.session_state.detection_method = detection_method
    st.session_state.cutoff = 95 if detection_method == "L1P1 (Statistical — WIP)" else 75

st.sidebar.markdown("---")
st.sidebar.subheader("Suspicion Score Cutoff")
if detection_method == "L1P1 (Statistical — WIP)":
    cutoff_caption = (
        "Maps to statistical sensitivity: score 95 = alpha 0.05 "
        "(95% sensitivity, recommended by Ilagan & Falk, 2024). "
        "Lower score = more strict."
    )
else:
    cutoff_caption = (
        "Responses at or above this score are flagged as bots. "
        "Default 75 recommended for heuristic method. Lower score = more strict."
    )

cutoff = st.sidebar.slider(
    "Suspicion Score Cutoff",
    min_value=0,
    max_value=100,
    value=st.session_state.get("cutoff", 95),
    label_visibility="collapsed",
)
st.sidebar.caption(cutoff_caption)
st.session_state.cutoff = cutoff

st.sidebar.markdown("---")
st.sidebar.subheader("Qualitative Analysis Mode")
qualitative_mode = st.sidebar.toggle(
    "Enable Qualitative Mode",
    help=(
        "Analyzes open-ended text responses for AI-generated content. "
        "Requires an Anthropic API key."
    ),
)
st.sidebar.caption(
    "When enabled, open-ended text responses are scored for AI-generated content "
    "using the Claude API. Results appear as a separate ai_text_score column."
)
st.session_state.qualitative_mode = qualitative_mode
if qualitative_mode:
    api_key = st.sidebar.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
    )
    st.sidebar.caption("Used only during this session. Never saved to disk.")
    st.session_state.api_key = api_key
else:
    st.session_state.api_key = ""

st.title("🔍 Survey Bot Detector")
st.markdown(
    "Automatically detect and flag bot-like responses in survey data. Upload a CSV, "
    "run the analysis, and download your cleaned dataset."
)
st.markdown("---")

st.subheader("Step 1 — Upload Your Survey Data")
st.caption(
    "Upload a CSV export from Qualtrics, Google Forms, or any survey platform. "
    "Each row should represent one participant."
)
uploaded_file = st.file_uploader(
    "Upload Survey CSV",
    type=["csv"],
    label_visibility="collapsed",
)
if uploaded_file is not None:
    raw_bytes = uploaded_file.read()

    # First pass: peek at first 3 rows to detect Qualtrics format
    df_peek = pd.read_csv(io.BytesIO(raw_bytes), nrows=3)

    # Qualtrics adds two junk rows after the header:
    #   row 0: human-readable question labels
    #   row 1: ImportId metadata (e.g. {"ImportId":"QID23_113"})
    is_qualtrics = False
    if len(df_peek) >= 2:
        row1_str = df_peek.iloc[1].astype(str)
        row0_str = df_peek.iloc[0].astype(str)
        if (row1_str.str.contains("ImportId", na=False).any() or
                row0_str.str.contains("ImportId", na=False).any()):
            is_qualtrics = True

    # Second pass: read with correct skiprows
    if is_qualtrics:
        df = pd.read_csv(io.BytesIO(raw_bytes), skiprows=[1, 2])
    else:
        df = pd.read_csv(io.BytesIO(raw_bytes))

    if st.session_state.get("uploaded_filename") != uploaded_file.name:
        st.session_state.df_results = None
        st.session_state.likert_cols = None
        st.session_state.column_mode = None
        st.session_state.uploaded_filename = uploaded_file.name
    st.session_state.df_raw = df
    n_rows, n_cols = df.shape
    st.success(f"✅ {uploaded_file.name} loaded — {n_rows} rows, {n_cols} columns")
    st.dataframe(df.head(), use_container_width=True)
st.markdown("---")

if st.session_state.get("df_raw") is not None:
    _df = st.session_state.df_raw
    st.subheader("Step 1.5 — Select Likert-Scale Columns")
    st.caption(
        "The detector analyzes Likert-scale response columns. "
        "Auto mode detects them from your data. Manual mode lets "
        "you review and adjust the selection."
    )

    tab_auto, tab_manual = st.tabs(["Automatic Detection", "Manual Selection"])

    with tab_auto:
        auto_cols = utils.get_likert_columns(_df)
        if len(auto_cols) == 0:
            st.warning(
                "No Likert columns detected automatically. "
                "Switch to Manual Selection to choose columns yourself."
            )
        else:
            st.success(f"✅ {len(auto_cols)} Likert columns detected.")
            st.caption(
                "These columns have numeric values in the 1–7 range with "
                "fewer than 8 unique values. Non-survey columns (IDs, "
                "timestamps, metadata) are excluded automatically."
            )
            summary_rows = []
            for col in auto_cols:
                vals = pd.to_numeric(_df[col], errors="coerce").dropna()
                summary_rows.append({
                    "Column": col,
                    "Min": int(vals.min()) if len(vals) > 0 else "-",
                    "Max": int(vals.max()) if len(vals) > 0 else "-",
                    "Unique Values": int(vals.nunique()) if len(vals) > 0 else "-",
                    "Non-null Responses": int(vals.notna().sum()),
                })
            st.dataframe(
                pd.DataFrame(summary_rows),
                use_container_width=True,
                height=300,
            )

        if st.button("✅ Use Automatic Selection", key="use_auto", type="primary"):
            st.session_state.likert_cols = auto_cols
            st.session_state.column_mode = "auto"
            st.success(f"Using {len(auto_cols)} automatically detected columns.")

        if st.session_state.get("column_mode") == "auto":
            n_active = len(st.session_state.get("likert_cols") or [])
            st.info(f"Active: Automatic — {n_active} columns")

    with tab_manual:
        st.caption(
            "Review and adjust which columns to include. "
            "Auto-detected columns are pre-checked. "
            "Deselect any columns that are not Likert-scale items."
        )
        auto_cols_for_manual = utils.get_likert_columns(_df)
        candidate_cols = []
        for col in _df.columns:
            vals = pd.to_numeric(_df[col], errors="coerce").dropna()
            if len(vals) > len(_df) * 0.3:
                candidate_cols.append({
                    "Include": col in auto_cols_for_manual,
                    "Column": col,
                    "Sample Values": str(sorted(vals.unique()[:5].tolist())),
                    "Min": float(vals.min()),
                    "Max": float(vals.max()),
                    "Unique": int(vals.nunique()),
                })
        if len(candidate_cols) == 0:
            st.warning("No numeric columns found in this CSV.")
            selected_manual = []
        else:
            cand_df = pd.DataFrame(candidate_cols)
            edited_df = st.data_editor(
                cand_df,
                column_config={
                    "Include": st.column_config.CheckboxColumn(
                        "Include",
                        help="Check to include this column in bot detection",
                        default=False,
                    ),
                    "Column": st.column_config.TextColumn("Column Name"),
                    "Sample Values": st.column_config.TextColumn("Sample Values"),
                    "Min": st.column_config.NumberColumn("Min", format="%.0f"),
                    "Max": st.column_config.NumberColumn("Max", format="%.0f"),
                    "Unique": st.column_config.NumberColumn("# Unique"),
                },
                disabled=["Column", "Sample Values", "Min", "Max", "Unique"],
                use_container_width=True,
                height=400,
                hide_index=True,
            )
            selected_manual = edited_df[edited_df["Include"]]["Column"].tolist()
            if len(selected_manual) == 0:
                st.warning("No columns selected. Please check at least one column.")
            else:
                st.caption(f"{len(selected_manual)} columns checked.")

        if st.button("✅ Use Manual Selection", key="use_manual", type="primary"):
            st.session_state.likert_cols = selected_manual
            st.session_state.column_mode = "manual"
            st.success(f"Using {len(selected_manual)} manually selected columns.")

        if st.session_state.get("column_mode") == "manual":
            n_active = len(st.session_state.get("likert_cols") or [])
            st.info(f"Active: Manual — {n_active} columns")

    # Default: if no button has been clicked yet for this file, apply auto silently
    if st.session_state.get("likert_cols") is None:
        st.session_state.likert_cols = utils.get_likert_columns(_df)
        st.session_state.column_mode = "auto"

    st.markdown("---")

st.subheader("Step 2 — Run Bot Detection")
if detection_method == "Classic (Heuristic)":
    st.caption(
        "Heuristic detection: straightlining, duplicates, speeders, variance, "
        "and response pattern checks. Fast and recommended for most surveys."
    )
    spinner_msg = "Running heuristic bot detection..."
else:
    st.caption(
        "L1P1 permutation test (Ilagan & Falk, 2024). Analyzes response patterns "
        "across all participants. Large datasets may take 1-2 minutes."
    )
    spinner_msg = (
        "Running L1P1 — analyzing permutation structure across participants. "
        "This may take 1-2 minutes..."
    )

if st.button("🚀 Run Bot Detection", type="primary"):
    if st.session_state.get("df_raw") is None:
        st.warning("⚠️ Please upload a CSV file first.")
        st.stop()
    if st.session_state.get("qualitative_mode") and not st.session_state.get("api_key", "").strip():
        st.warning("⚠️ Please enter your Anthropic API key in the sidebar to use Qualitative Analysis Mode.")
        st.stop()
    with st.spinner(spinner_msg):
        if detection_method == "Classic (Heuristic)":
            result = run_detection_heuristic(
                st.session_state.df_raw,
                cutoff=st.session_state.get("cutoff", 75),
                likert_cols=st.session_state.get("likert_cols") or None,
            )
        else:
            result = run_detection(
                st.session_state.df_raw,
                st.session_state.get("cutoff", 95),
                likert_cols=st.session_state.get("likert_cols") or None,
            )
        if st.session_state.get("qualitative_mode"):
            try:
                result = run_qualitative(result, st.session_state.api_key)
            except Exception as e:
                st.error(
                    f"Qualitative analysis failed: {e}. Quantitative results are still available."
                )
        st.session_state.df_results = result
    st.success("✅ Analysis complete.")
st.markdown("---")

if st.session_state.get("df_results") is not None:
    st.subheader("Step 3 — Review Results")
    df_results = st.session_state.df_results
    total = len(df_results)
    flagged = int(df_results["is_flagged"].sum())
    pct = round((flagged / total) * 100, 1) if total > 0 else 0.0
    flagged_df = df_results[df_results["is_flagged"] == True]
    cleaned_df = df_results[df_results["is_flagged"] == False]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Participants", total)
    col2.metric(
        "Flagged",
        flagged,
        delta=f"{pct}% of responses",
        delta_color="inverse",
    )
    col3.metric(
        "Suspicion Cutoff",
        f"{st.session_state.get('cutoff', 95)}/100",
    )

    with st.expander("📖 Flag Definitions — what do these flags mean?", expanded=False):

        st.markdown("#### Hard Flags — score 100, immediate exclusion")
        st.markdown(
            "These patterns are strong enough to flag a participant "
            "automatically regardless of other responses."
        )
        st.dataframe(
            {
                "Flag": [
                    "longstring_absolute",
                    "exact_duplicate",
                ],
                "What triggered it": [
                    "Same answer on >90% of all Likert items",
                    "Identical Likert response pattern as another participant",
                ],
                "What it means": [
                    "A genuine human almost never selects the same value across 90%+ of a long "
                    "survey. This is the strongest single bot signal.",
                    "Two or more participants submitted identical response patterns — consistent "
                    "with bots running the same script or participants copying answers.",
                ],
            },
            use_container_width=True,
            hide_index=True,
            column_config={
                "Flag": st.column_config.TextColumn("Flag", width="medium"),
                "What triggered it": st.column_config.TextColumn("What triggered it", width="large"),
                "What it means": st.column_config.TextColumn("What it means", width="large"),
            },
        )

        st.markdown("---")
        st.markdown("#### Soft Flags — additive, contribute to bot\_score")
        st.markdown(
            "These checks are weaker signals individually. Multiple soft flags combine into "
            "a composite bot\_score (0–100). A participant is flagged when their score reaches "
            "the cutoff threshold."
        )
        st.dataframe(
            {
                "Flag": [
                    "speeder",
                    "low_variance",
                    "longstring_run",
                    "range_avoidance",
                    "extreme_responding",
                    "missing_data",
                ],
                "Points": ["+30", "+25", "+20", "+15", "+15", "+10"],
                "What triggered it": [
                    "Survey completed in under 120 seconds",
                    "Response SD in bottom 10% of all participants",
                    "Same answer on >50% of items in a consecutive run",
                    "Only 1–2 unique values used across all items",
                    ">80% of responses at scale endpoints (e.g. only 1s and 7s)",
                    ">50% of Likert items left blank",
                ],
                "What it means": [
                    "A survey with 100+ questions cannot be read and answered thoughtfully in "
                    "under 2 minutes. The actual time is shown in brackets, e.g. speeder (45s < 120s).",
                    "Humans naturally vary their answers across items. Very low variance suggests "
                    "the participant was not reading and responding to question content.",
                    "Consecutive identical answers across a section of the survey. Distinct from "
                    "longstring_absolute, which checks the whole survey — this catches patterned "
                    "repetition within blocks.",
                    "On a 1–7 scale, humans typically use most of the range. Using only one or two "
                    "values across the entire survey is a common bot pattern.",
                    "While some humans do respond at extremes, selecting only the highest and lowest "
                    "scale points across 80%+ of items is a common bot signature.",
                    "Submitting a mostly blank Likert survey. On its own a weak signal (may reflect "
                    "dropout), but combined with other flags contributes to the composite score.",
                ],
            },
            use_container_width=True,
            hide_index=True,
            column_config={
                "Flag": st.column_config.TextColumn("Flag", width="medium"),
                "Points": st.column_config.TextColumn("Points", width="small"),
                "What triggered it": st.column_config.TextColumn("What triggered it", width="large"),
                "What it means": st.column_config.TextColumn("What it means", width="large"),
            },
        )

        st.markdown("---")
        st.markdown("#### L1P1 Statistical Flags (L1P1 method only)")
        st.markdown(
            "These flags appear when the L1P1 permutation test method is selected. They are based "
            "on the peer-reviewed algorithm by Ilagan & Falk (2024), *Behavior Research Methods*."
        )
        st.dataframe(
            {
                "Flag": [
                    "l1p1_permutation_test",
                    "fast_completion",
                    "low_variance (L1P1 context)",
                    "longstring_run (L1P1 context)",
                    "range_avoidance (L1P1 context)",
                    "extreme_responding (L1P1 context)",
                ],
                "What it means": [
                    "The participant's response pattern is statistically consistent with random "
                    "responding. The algorithm permuted their responses 200 times and found that "
                    "their actual pattern is no more structured than a random shuffle — a strong "
                    "indicator of bot-like behavior. The l1p1_pvalue column shows the exact p-value "
                    "(flagged when p >= alpha, default alpha = 0.05).",
                    "Appears alongside l1p1_permutation_test when the participant also completed the "
                    "survey in under 120 seconds. Provides additional context for why the participant "
                    "was flagged.",
                    "Appears as a contextual diagnostic for L1P1-flagged participants whose SD falls "
                    "in the bottom 10% of the sample. Helps explain the statistical flag.",
                    "Appears as a contextual diagnostic when a long consecutive run of identical "
                    "answers is detected in an L1P1-flagged participant.",
                    "Appears as a contextual diagnostic when an L1P1-flagged participant used only "
                    "1–2 unique values across all items.",
                    "Appears as a contextual diagnostic when an L1P1-flagged participant responded "
                    "at scale endpoints for 80%+ of items.",
                ],
            },
            use_container_width=True,
            hide_index=True,
            column_config={
                "Flag": st.column_config.TextColumn("Flag", width="medium"),
                "What it means": st.column_config.TextColumn("What it means", width="large"),
            },
        )

        st.markdown("---")
        st.markdown("#### Eligibility Flag (FE Study specific)")
        st.markdown(
            "This flag is separate from bot detection. It identifies participants who may be "
            "genuine humans but do not meet the study's inclusion criteria."
        )
        st.dataframe(
            {
                "Flag": ["ineligible_no_group"],
                "What triggered it": [
                    "Participant answered Q82 = 3 (cannot think of a qualifying intellectual group)"
                ],
                "What it means": [
                    "This participant did not meet the study eligibility criterion. They are shown "
                    "in the Ineligible tab and excluded from the cleaned dataset separately from bots. "
                    "They are NOT counted as bots — they may be genuine human participants who simply "
                    "could not identify a qualifying group."
                ],
            },
            use_container_width=True,
            hide_index=True,
            column_config={
                "Flag": st.column_config.TextColumn("Flag", width="medium"),
                "What triggered it": st.column_config.TextColumn("What triggered it", width="large"),
                "What it means": st.column_config.TextColumn("What it means", width="large"),
            },
        )

        st.markdown("---")
        st.caption(
            "Reference: Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised detection "
            "of bots in a Likert-type questionnaire. *Behavior Research Methods, 56*(5), 5068–5085. "
            "https://doi.org/10.3758/s13428-023-02246-7"
        )

    tab1, tab2 = st.tabs(["🚨 Flagged Responses", "📋 Full Results"])
    with tab1:
        if len(flagged_df) > 0:
            st.caption(
                f"{flagged} response(s) flagged at cutoff {st.session_state.get('cutoff', 95)}."
            )
            st.dataframe(flagged_df, use_container_width=True)
        else:
            st.success(
                "✅ No suspicious responses detected at this cutoff. Try lowering the cutoff "
                "slider to see borderline cases."
            )
    with tab2:
        st.caption(
            "All participants with bot_score, bot_flags, and is_flagged columns appended to original data."
        )
        st.dataframe(df_results, use_container_width=True)
    st.markdown("---")

if st.session_state.get("df_results") is not None:
    st.subheader("Step 4 — Download Results")
    df_results = st.session_state.df_results
    cleaned_df = df_results[df_results["is_flagged"] == False]
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.caption(
            "All rows with suspicion scores and flag labels appended. Use this to review borderline cases."
        )
        st.download_button(
            label="📥 Download Full Flagged CSV",
            data=df_results.to_csv(index=False).encode("utf-8"),
            file_name="flagged_responses.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with dl_col2:
        st.caption(
            "Only rows below the suspicion cutoff. Ready to use directly in your statistical analysis."
        )
        st.download_button(
            label="✅ Download Cleaned CSV",
            data=cleaned_df.to_csv(index=False).encode("utf-8"),
            file_name="cleaned_responses.csv",
            mime="text/csv",
            use_container_width=True,
        )
