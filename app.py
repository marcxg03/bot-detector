import io

import pandas as pd
import streamlit as st

from detector import run_detection
from qualitative import run_qualitative


st.set_page_config(page_title="Survey Bot Detector", layout="wide")

st.title("Survey Bot Detector")
st.write("Upload a survey CSV to automatically detect and flag bot-like responses.")

if "cutoff" not in st.session_state:
    st.session_state.cutoff = 75

if "qualitative_mode" not in st.session_state:
    st.session_state.qualitative_mode = False

if "api_key" not in st.session_state:
    st.session_state.api_key = ""

uploaded_file = st.file_uploader("Upload Survey CSV", type=["csv"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    file_signature = (uploaded_file.name, len(file_bytes), hash(file_bytes))

    if st.session_state.get("uploaded_file_signature") != file_signature:
        st.session_state.df_raw = pd.read_csv(io.BytesIO(file_bytes))
        st.session_state.uploaded_file_signature = file_signature
        if "df_results" in st.session_state:
            del st.session_state.df_results

if "df_raw" in st.session_state:
    st.dataframe(st.session_state.df_raw.head())

if "df_raw" in st.session_state:
    st.subheader("Settings")
    st.session_state.cutoff = st.slider(
        "Suspicion Score Cutoff",
        min_value=0,
        max_value=100,
        value=st.session_state.cutoff,
        help="Responses at or above this score will be flagged.",
    )
    st.session_state.qualitative_mode = st.toggle(
        "Enable Qualitative Analysis Mode",
        value=st.session_state.qualitative_mode,
        help=(
            "Analyzes open-ended text responses for AI-generated content. "
            "Requires an Anthropic API key."
        ),
    )

    if st.session_state.qualitative_mode:
        st.session_state.api_key = st.text_input(
            "Anthropic API Key",
            value=st.session_state.api_key,
            type="password",
            help="Your key is used only during this session and never saved.",
        )

if "df_raw" in st.session_state:
    if st.button("Run Bot Detection"):
        if "df_raw" not in st.session_state:
            st.warning("Please upload a CSV file first.")
            st.stop()

        if st.session_state.qualitative_mode and not st.session_state.get("api_key"):
            st.warning("Please enter your Anthropic API key to use Qualitative Analysis Mode.")
            st.stop()

        with st.spinner("Analyzing responses..."):
            st.session_state.df_results = run_detection(
                st.session_state.df_raw,
                st.session_state.cutoff,
            )

            if st.session_state.qualitative_mode:
                try:
                    st.session_state.df_results = run_qualitative(
                        st.session_state.df_results,
                        st.session_state.api_key,
                    )
                except Exception as e:
                    st.error(str(e))

if "df_results" in st.session_state:
    df_results = st.session_state.df_results

    st.subheader("Results")
    total = len(df_results)
    flagged = df_results["is_flagged"].sum()
    pct = round((flagged / total) * 100, 1) if total > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Participants", total)
    col2.metric("Flagged", flagged)
    col3.metric("Flagged %", f"{pct}%")

    st.subheader("Flagged Responses Preview")
    flagged_df = df_results[df_results["is_flagged"] == True]
    if len(flagged_df) == 0:
        st.success("No suspicious responses detected.")
    else:
        st.dataframe(flagged_df)

    st.subheader("Downloads")

    full_buffer = io.StringIO()
    df_results.to_csv(full_buffer, index=False)
    full_csv_bytes = full_buffer.getvalue().encode("utf-8")
    st.download_button(
        label="Download Full Flagged CSV",
        data=full_csv_bytes,
        file_name="flagged_responses.csv",
        mime="text/csv",
    )

    cleaned_df = df_results[df_results["is_flagged"] == False]
    cleaned_buffer = io.StringIO()
    cleaned_df.to_csv(cleaned_buffer, index=False)
    cleaned_csv_bytes = cleaned_buffer.getvalue().encode("utf-8")
    st.download_button(
        label="Download Cleaned CSV",
        data=cleaned_csv_bytes,
        file_name="cleaned_responses.csv",
        mime="text/csv",
    )
