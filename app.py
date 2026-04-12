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

st.sidebar.markdown("---")

if detection_method == "Classic (Heuristic)":
    st.sidebar.subheader("Speeder Threshold")
    speeder_threshold = st.sidebar.number_input(
        "Speeder Threshold (seconds)",
        min_value=30,
        max_value=600,
        value=st.session_state.get("speeder_threshold", 120),
        step=10,
        help=(
            "Participants who completed the survey faster than this "
            "threshold will be flagged as speeders. Default 120s "
            "(2 minutes). Adjust based on your survey length."
        ),
    )
    st.session_state.speeder_threshold = speeder_threshold

    with st.sidebar.expander("⚙️ Optional Checks", expanded=False):
        use_low_variance = st.checkbox(
            "Low Variance",
            value=st.session_state.get("use_low_variance", True),
            key="use_low_variance",
            help=(
                "Flag participants whose response standard deviation "
                "falls in the bottom 10th percentile of the sample.\n\n"
                "⚠️ Caution: This is a relative threshold. It will "
                "always flag approximately 10% of respondents "
                "regardless of actual data quality. Based on: "
                "Marjanovic et al. (2015), Personality and Individual "
                "Differences, 84, 79-83. "
                "doi:10.1016/j.paid.2014.08.021\n\n"
                "Review flagged cases manually before excluding."
            ),
        )
        use_missing_data = st.checkbox(
            "Missing Data (>50% blank)",
            value=st.session_state.get("use_missing_data", True),
            key="use_missing_data",
            help=(
                "Flag participants who left more than 50% of Likert "
                "items blank.\n\n"
                "⚠️ Caution: This can capture legitimate early "
                "dropouts rather than bots — participants who could "
                "not complete the survey for genuine reasons. "
                "Based on: Meade & Craig (2012), Psychological "
                "Methods, 17(3), 437-455. doi:10.1037/a0028085\n\n"
                "Review flagged cases manually before excluding."
            ),
        )

    st.sidebar.caption(
        "All participants triggering any check are flagged. "
        "Your lab manager reviews bot_flags and makes final "
        "exclusion decisions."
    )
    cutoff = 75  # unused by heuristic; kept so downstream references don't break
else:
    st.sidebar.subheader("Suspicion Score Cutoff")
    cutoff = st.sidebar.slider(
        "Suspicion Score Cutoff",
        min_value=0,
        max_value=100,
        value=st.session_state.get("cutoff", 95),
        label_visibility="collapsed",
    )
    st.sidebar.caption(
        "Maps to statistical sensitivity: score 95 = alpha 0.05 "
        "(95% sensitivity, recommended by Ilagan & Falk, 2024). "
        "Lower score = more strict."
    )
    st.session_state.cutoff = cutoff
    speeder_threshold = st.session_state.get("speeder_threshold", 120)

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
                cutoff=75,
                likert_cols=st.session_state.get("likert_cols") or None,
                speeder_threshold=st.session_state.get("speeder_threshold", 120),
                use_low_variance=st.session_state.get("use_low_variance", True),
                use_missing_data=st.session_state.get("use_missing_data", True),
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

    if detection_method == "Classic (Heuristic)":
        st.caption(
            "Classic mode: any flagged check = excluded. "
            "Review the bot_flags column for specific reasons. "
            "bot_score shows the number of checks triggered per participant."
        )

    with st.expander("📖 Flag Definitions — what do these flags mean?", expanded=False):

        st.info(
            "**Methodological note:** Each criterion below is grounded "
            "in the peer-reviewed careless responding and bot detection "
            "literature. However, specific thresholds (e.g. 90% for "
            "straightlining, 120s for speeders) are researcher-set "
            "parameters not always directly specified in the cited "
            "papers. Flagged participants should be reviewed manually "
            "before exclusion, particularly for softer signals. The "
            "lab manager makes the final exclusion decision."
        )

        st.markdown("#### Hard Flags — any occurrence = flagged")
        st.markdown(
            "These patterns are strong enough to flag a participant "
            "regardless of all other responses. bot\\_score += 1 per "
            "flag triggered."
        )

        hard_flag_data = {
            "Flag": [
                "longstring_absolute",
                "exact_duplicate",
            ],
            "What triggered it": [
                "Same answer on >90% of substantive Likert items",
                "Identical Likert response pattern to another "
                "participant (requires ≥10 non-null substantive "
                "responses; screener-only columns excluded)",
            ],
            "What it means": [
                "A genuine human almost never selects the same "
                "value across 90%+ of a long survey. The longstring "
                "index is the most widely used single indicator of "
                "non-genuine responding.",
                "Two or more participants submitted identical response "
                "patterns across substantive items — consistent with "
                "bots running the same script. Early dropouts who "
                "only answered screener questions are excluded from "
                "this check.",
            ],
            "Citation & Basis": [
                "Johnson (2005), J. Research in Personality, 39, "
                "103-129. doi:10.1016/j.jrp.2004.09.009\n"
                "Meade & Craig (2012), Psychological Methods, 17(3), "
                "437-455. doi:10.1037/a0028085\n"
                "NOTE: 90% threshold is researcher-set. Johnson "
                "proposes the index; does not specify a universal "
                "cutoff.",
                "Meade & Craig (2012), Psychological Methods, 17(3), "
                "437-455. doi:10.1037/a0028085\n"
                "Chmielewski & Kucker (2020), Social Psychological "
                "and Personality Science, 11(4), 464-473. "
                "doi:10.1177/1948550619875149",
            ],
        }

        st.dataframe(
            hard_flag_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Flag": st.column_config.TextColumn(
                    "Flag", width="medium"),
                "What triggered it": st.column_config.TextColumn(
                    "What triggered it", width="large"),
                "What it means": st.column_config.TextColumn(
                    "What it means", width="large"),
                "Citation & Basis": st.column_config.TextColumn(
                    "Citation & Basis", width="large"),
            },
        )

        st.markdown("---")
        st.markdown(
            "#### Soft Flags — any occurrence = flagged, "
            "bot\\_score += 1 each"
        )
        st.markdown(
            "These checks are weaker signals individually. Any single "
            "flag marks the participant as flagged. The bot\\_score "
            "column shows how many checks fired — higher = more "
            "suspicious. Soft flags should be reviewed manually "
            "before exclusion."
        )

        soft_flag_data = {
            "Flag": [
                "speeder",
                "low_variance ⚙️",
                "longstring_run",
                "range_avoidance",
                "extreme_responding",
                "missing_data ⚙️",
            ],
            "What triggered it": [
                "Completed survey under threshold seconds "
                "(adjustable in sidebar, default 120s)",
                "Response SD in bottom 10% of sample "
                "(optional — toggle in sidebar)",
                "Same answer consecutively on >50% of items",
                "Only 1-2 unique values used across all items "
                "on a 1-7 scale",
                ">80% of responses at scale endpoints "
                "(e.g. only 1s and 7s)",
                ">50% of Likert items left blank "
                "(optional — toggle in sidebar)",
            ],
            "What it means": [
                "Very short response times indicate insufficient "
                "time to read and consider item content.",
                "Low intra-individual response variability "
                "suggests non-engagement with item content. "
                "⚠️ Relative threshold — always flags ~10% of "
                "sample. Review manually.",
                "Consecutive identical responses across a section "
                "of the survey — consistent with key-holding or "
                "automated responding.",
                "Using only 1-2 values across a 7-point scale "
                "suggests non-engagement with the full response "
                "range.",
                "Selecting only the highest and lowest scale "
                "points across 80%+ of items is a documented "
                "pattern of careless or automated responding.",
                "More than half of Likert items left blank. "
                "⚠️ May reflect legitimate dropout rather than "
                "bot behavior. Review manually.",
            ],
            "Citation & Basis": [
                "Greszki, Meyer & Schoen (2015), Public Opinion "
                "Quarterly, 79(2), 471-503. "
                "doi:10.1093/poq/nfu058\n"
                "NOTE: Paper recommends a relative threshold "
                "(50% of median survey time per page). Our "
                "absolute 120s default is researcher-set and "
                "adjustable in the sidebar.",
                "Marjanovic et al. (2015), Personality and "
                "Individual Differences, 84, 79-83. "
                "doi:10.1016/j.paid.2014.08.021\n"
                "Meade & Craig (2012), doi:10.1037/a0028085\n"
                "NOTE: Bottom 10th percentile cutoff is a "
                "relative threshold — always flags some "
                "participants. Use with caution.",
                "Johnson (2005), J. Research in Personality, "
                "39, 103-129. doi:10.1016/j.jrp.2004.09.009\n"
                "Meade & Craig (2012), Psychological Methods, "
                "17(3), 437-455. doi:10.1037/a0028085\n"
                "NOTE: 50% run threshold is researcher-set.",
                "Ward & Meade (2023), Annual Review of "
                "Psychology, 74, 577-596. "
                "doi:10.1146/annurev-psych-040422-045007\n"
                "NOTE: ≤2 unique values threshold is "
                "researcher-set.",
                "Meade & Craig (2012), Psychological Methods, "
                "17(3), 437-455. doi:10.1037/a0028085\n"
                "NOTE: 80% endpoint threshold is "
                "researcher-set.",
                "Meade & Craig (2012), Psychological Methods, "
                "17(3), 437-455. doi:10.1037/a0028085\n"
                "NOTE: 50% missing threshold is researcher-set. "
                "May capture legitimate dropouts.",
            ],
        }

        st.dataframe(
            soft_flag_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Flag": st.column_config.TextColumn(
                    "Flag", width="medium"),
                "What triggered it": st.column_config.TextColumn(
                    "What triggered it", width="large"),
                "What it means": st.column_config.TextColumn(
                    "What it means", width="large"),
                "Citation & Basis": st.column_config.TextColumn(
                    "Citation & Basis", width="large"),
            },
        )

        st.markdown("---")
        st.markdown("#### L1P1 Statistical Flags (L1P1 method only)")
        st.markdown(
            "These flags appear when the L1P1 permutation test method "
            "is selected. The algorithm is peer-reviewed and "
            "statistically grounded — see citation below."
        )

        l1p1_flag_data = {
            "Flag": [
                "l1p1_permutation_test",
                "fast_completion",
                "low_variance (L1P1 context)",
                "longstring_run (L1P1 context)",
                "range_avoidance (L1P1 context)",
                "extreme_responding (L1P1 context)",
            ],
            "What it means": [
                "The participant's response pattern is statistically "
                "consistent with random responding. The algorithm "
                "generated 200 permutations of their responses and "
                "found their actual pattern is no more structured "
                "than a random shuffle. The l1p1_pvalue column shows "
                "the exact p-value. Flagged when p ≥ alpha "
                "(default alpha=0.05, i.e. 95% sensitivity).",
                "Contextual: participant also completed the survey "
                "under the speeder threshold. Provides additional "
                "context for the statistical flag.",
                "Contextual diagnostic: flagged participant's SD "
                "falls in the bottom 10% of the sample.",
                "Contextual diagnostic: long consecutive run of "
                "identical answers detected in a flagged participant.",
                "Contextual diagnostic: flagged participant used "
                "only 1-2 unique values across all items.",
                "Contextual diagnostic: flagged participant "
                "responded at scale endpoints for 80%+ of items.",
            ],
            "Citation & Basis": [
                "Ilagan & Falk (2024), Behavior Research Methods, "
                "56(5), 5068-5085. "
                "doi:10.3758/s13428-023-02246-7\n"
                "Falk, Huang & Ilagan (2025), Psychological "
                "Methods. doi:10.1037/met0000746\n"
                "Open-access code: osf.io/e5v3s\n"
                "R package: github.com/michaeljohnilagan/detranli",
                "Greszki et al. (2015), Public Opinion Quarterly, "
                "79(2), 471-503. doi:10.1093/poq/nfu058",
                "Marjanovic et al. (2015), Personality and "
                "Individual Differences, 84, 79-83. "
                "doi:10.1016/j.paid.2014.08.021",
                "Johnson (2005), J. Research in Personality, 39, "
                "103-129. doi:10.1016/j.jrp.2004.09.009",
                "Ward & Meade (2023), Annual Review of Psychology, "
                "74, 577-596. "
                "doi:10.1146/annurev-psych-040422-045007",
                "Meade & Craig (2012), Psychological Methods, "
                "17(3), 437-455. doi:10.1037/a0028085",
            ],
        }

        st.dataframe(
            l1p1_flag_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Flag": st.column_config.TextColumn(
                    "Flag", width="medium"),
                "What it means": st.column_config.TextColumn(
                    "What it means", width="large"),
                "Citation & Basis": st.column_config.TextColumn(
                    "Citation & Basis", width="large"),
            },
        )

        st.markdown("---")
        st.markdown("#### Eligibility Flag")
        st.markdown(
            "Separate from bot detection. Identifies participants "
            "who do not meet study inclusion criteria."
        )

        elig_flag_data = {
            "Flag": ["ineligible_no_group"],
            "What triggered it": [
                "Participant answered Q82 = 3 (cannot think of a "
                "qualifying intellectual group)"
            ],
            "What it means": [
                "This participant did not meet the study eligibility "
                "criterion. They are NOT counted as bots — they may "
                "be genuine human participants who simply could not "
                "identify a qualifying group. Shown in the Ineligible "
                "tab and excluded from the cleaned dataset separately."
            ],
            "Citation & Basis": [
                "Study-specific eligibility criterion. Not a bot "
                "detection method — no external citation applicable."
            ],
        }

        st.dataframe(
            elig_flag_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Flag": st.column_config.TextColumn(
                    "Flag", width="medium"),
                "What triggered it": st.column_config.TextColumn(
                    "What triggered it", width="large"),
                "What it means": st.column_config.TextColumn(
                    "What it means", width="large"),
                "Citation & Basis": st.column_config.TextColumn(
                    "Citation & Basis", width="large"),
            },
        )

        st.markdown("---")
        st.caption(
            "**Key references:** "
            "Johnson (2005) doi:10.1016/j.jrp.2004.09.009 · "
            "Meade & Craig (2012) doi:10.1037/a0028085 · "
            "Greszki et al. (2015) doi:10.1093/poq/nfu058 · "
            "Marjanovic et al. (2015) doi:10.1016/j.paid.2014.08.021 · "
            "Ward & Meade (2023) doi:10.1146/annurev-psych-040422-045007 · "
            "Chmielewski & Kucker (2020) doi:10.1177/1948550619875149 · "
            "Ilagan & Falk (2024) doi:10.3758/s13428-023-02246-7 · "
            "Falk et al. (2025) doi:10.1037/met0000746"
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
