import io

import streamlit as st
import pandas as pd

import utils
from detector import run_detection
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
st.sidebar.subheader("Suspicion Score Cutoff")
cutoff = st.sidebar.slider(
    "Suspicion Score Cutoff",
    min_value=0,
    max_value=100,
    value=95,
    label_visibility="collapsed",
)
st.sidebar.caption(
    "Maps to statistical sensitivity: score 95 = alpha 0.05 "
    "(95% sensitivity, recommended by Ilagan & Falk, 2024). "
    "Lower score = more strict."
)
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
        "The detector needs to know which columns contain Likert-scale "
        "responses. You can let the tool detect them automatically, or "
        "select them manually if you know your survey structure."
    )

    mode = st.radio(
        "Column selection mode",
        options=["Automatic", "Manual"],
        horizontal=True,
        help=(
            "Automatic uses a heuristic (values 1–7, fewer than 8 unique values, "
            "no metadata keywords). Manual lets you choose exactly which columns to analyze."
        ),
    )

    if mode == "Automatic":
        auto_cols = utils.get_likert_columns(_df)
        if len(auto_cols) == 0:
            st.warning(
                "⚠️ No Likert columns detected automatically. Try Manual mode "
                "to select columns yourself."
            )
        else:
            st.success(f"✅ {len(auto_cols)} Likert columns detected automatically.")
        with st.expander(f"View detected columns ({len(auto_cols)})"):
            st.write(auto_cols)
        st.session_state.likert_cols = auto_cols
    else:
        st.caption(
            "Select all columns that contain Likert-scale responses "
            "(e.g. 1–5 or 1–7 scale items). Tip: auto-detected columns are pre-selected."
        )
        auto_cols = utils.get_likert_columns(_df)
        candidate_cols = [
            c for c in _df.columns
            if pd.to_numeric(_df[c], errors="coerce").notna().sum() > len(_df) * 0.5
        ]
        selected = st.multiselect(
            "Choose Likert columns",
            options=candidate_cols,
            default=[c for c in auto_cols if c in candidate_cols],
            help="Select all columns containing 1–5 or 1–7 scale responses.",
        )
        if len(selected) == 0:
            st.warning(
                "⚠️ No columns selected. Please select at least one Likert column to run detection."
            )
        else:
            st.success(f"✅ {len(selected)} columns selected.")
        st.session_state.likert_cols = selected

    st.markdown("---")

st.subheader("Step 2 — Run Bot Detection")
st.caption(
    "The detector analyzes response patterns across all Likert-scale items and assigns "
    "each participant a suspicion score from 0 (clean) to 100 (highly suspicious). "
    "Hard flags catch obvious bots; a composite of psychometric subscores handles subtler patterns."
)
if st.button("🚀 Run Bot Detection", type="primary"):
    if st.session_state.get("df_raw") is None:
        st.warning("⚠️ Please upload a CSV file first.")
        st.stop()
    if st.session_state.get("qualitative_mode") and not st.session_state.get("api_key", "").strip():
        st.warning("⚠️ Please enter your Anthropic API key in the sidebar to use Qualitative Analysis Mode.")
        st.stop()
    with st.spinner(
        "Running L1P1 bot detection — analyzing response patterns "
        "across all participants. Large datasets may take 1-2 minutes..."
    ):
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
