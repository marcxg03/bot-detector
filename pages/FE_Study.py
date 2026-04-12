import io

import streamlit as st
import pandas as pd
import numpy as np

import utils
from detector import run_detection, run_detection_heuristic

st.set_page_config(
    page_title="FE Study — Bot Detection",
    page_icon="🔬",
    layout="wide",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("⚙️ FE Study Settings")

with st.sidebar.expander("About this page"):
    st.write(
        "This page is configured specifically for the Freedom of Expression study "
        "(Oishi Lab, University of Chicago). It auto-detects the survey wave, applies "
        "study-specific eligibility rules, and runs bot detection with settings optimized "
        "for this instrument. For other surveys, use the General Bot Detection page."
    )

st.sidebar.markdown("---")
st.sidebar.subheader("Detection Method")
detection_method = st.sidebar.radio(
    "Detection Method",
    options=["Classic (Heuristic)", "L1P1 (Statistical — WIP)"],
    label_visibility="collapsed",
    help=(
        "Classic: Fast heuristic detection. Recommended for current use.\n\n"
        "L1P1: Peer-reviewed permutation test (Ilagan & Falk, 2024). Currently being "
        "validated on FE study data. Results may not yet be reliable."
    ),
)

if detection_method == "L1P1 (Statistical — WIP)":
    st.sidebar.warning(
        "⚠️ L1P1 is still being validated on FE study data. Results should be compared "
        "against Classic method before use in analysis."
    )

st.sidebar.markdown("---")

if detection_method == "Classic (Heuristic)":
    st.sidebar.subheader("Speeder Threshold")
    speeder_threshold = st.sidebar.number_input(
        "Speeder Threshold (seconds)",
        min_value=30,
        max_value=600,
        value=st.session_state.get("fe_speeder_threshold", 120),
        step=10,
        help=(
            "Participants completing faster than this are flagged "
            "as speeders. Default 120s. Adjust based on survey length."
        ),
    )
    st.session_state.fe_speeder_threshold = speeder_threshold

    with st.sidebar.expander("⚙️ Optional Checks", expanded=False):
        use_low_variance = st.checkbox(
            "Low Variance",
            value=st.session_state.get("fe_use_low_variance", True),
            key="fe_use_low_variance",
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
            value=st.session_state.get("fe_use_missing_data", True),
            key="fe_use_missing_data",
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
        "Your lab manager reviews bot_flags and makes the "
        "final exclusion decision."
    )
    cutoff = 75  # unused by heuristic; kept so downstream references don't break
else:
    st.sidebar.subheader("Suspicion Score Cutoff")
    cutoff = st.sidebar.slider(
        "Suspicion Score Cutoff",
        min_value=0,
        max_value=100,
        value=st.session_state.get("fe_cutoff", 95),
        label_visibility="collapsed",
    )
    st.session_state.fe_cutoff = cutoff
    st.sidebar.caption("Maps to alpha: score 95 = 95% sensitivity (Ilagan & Falk, 2024).")
    speeder_threshold = st.session_state.get("fe_speeder_threshold", 120)

st.sidebar.markdown("---")
st.sidebar.subheader("Qualitative Analysis Mode")
qual_mode = st.sidebar.toggle(
    "Enable Qualitative Mode",
    help="Requires Anthropic API key.",
)
if qual_mode:
    api_key = st.sidebar.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
    )
    st.sidebar.caption("Session only. Never saved.")
    st.session_state.fe_api_key = api_key
else:
    st.session_state.fe_api_key = ""

# ── Main area ─────────────────────────────────────────────────────────────────

st.title("🔬 Freedom of Expression Study")
st.markdown(
    "Bot detection configured for the Oishi Lab Freedom of Expression survey instrument. "
    "Uploads are auto-detected as Wave 1 (FE2a) or Wave 2 based on column structure."
)
st.info(
    "💡 This page applies study-specific rules: participants who answered Q82=3 "
    "(could not think of a qualifying group) are flagged as **ineligible** rather "
    "than as bots, and are excluded from the cleaned dataset separately."
)
st.markdown("---")

# ── Step 1: Upload ────────────────────────────────────────────────────────────

st.subheader("Step 1 — Upload FE Study CSV")
st.caption(
    "Upload a Qualtrics CSV export from the Freedom of Expression study. "
    "Qualtrics header rows are stripped automatically."
)

uploaded_file = st.file_uploader(
    "Upload FE Study CSV",
    type=["csv"],
    label_visibility="collapsed",
)

if uploaded_file is not None:
    raw_bytes = uploaded_file.read()
    df_peek = pd.read_csv(io.BytesIO(raw_bytes), nrows=3)
    is_qualtrics = (
        len(df_peek) >= 2
        and df_peek.iloc[1].astype(str).str.contains("ImportId", na=False).any()
    )
    if is_qualtrics:
        df = pd.read_csv(io.BytesIO(raw_bytes), skiprows=[1, 2], low_memory=False)
    else:
        df = pd.read_csv(io.BytesIO(raw_bytes), low_memory=False)

    # Auto-detect wave from known landmark columns
    n_cols = len(df.columns)
    if "Norm 1 - CP_1" in df.columns:
        wave = "Wave 1 (FE2a)"
        expected_participants = 350
    elif "Norm_1" in df.columns:
        wave = "Wave 2"
        expected_participants = 422
    else:
        wave = "Unknown wave"
        expected_participants = None

    if st.session_state.get("fe_uploaded_filename") != uploaded_file.name:
        st.session_state.fe_df_results = None

    st.session_state.fe_df_raw = df
    st.session_state.fe_uploaded_filename = uploaded_file.name

    st.success(
        f"✅ {uploaded_file.name} loaded — "
        f"{len(df)} participants, {n_cols} columns — "
        f"**{wave}** detected"
    )

    # Auto-detect Likert columns and store in session state
    auto_likert = utils.get_likert_columns(df)
    st.session_state.fe_likert_cols = auto_likert

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Participants", len(df))
    col_b.metric("Likert Columns Detected", len(auto_likert))
    q82 = pd.to_numeric(df.get("Q82", pd.Series(dtype=float)), errors="coerce")
    col_c.metric("Cannot Think of Group (Q82=3)", int((q82 == 3).sum()))

    st.dataframe(df.head(3), use_container_width=True)

st.markdown("---")

# ── Step 2: Run ───────────────────────────────────────────────────────────────

st.subheader("Step 2 — Run Bot Detection")

if detection_method == "L1P1 (Statistical — WIP)":
    st.caption(
        "Running L1P1 permutation test (Ilagan & Falk, 2024). "
        "This may take 1-2 minutes. Results should be compared to Classic method before use."
    )
    spinner_msg = (
        "Running L1P1 — analyzing permutation structure across participants. "
        "This may take 1-2 minutes..."
    )
else:
    st.caption(
        "Running heuristic detection: straightlining, duplicates, speeders, "
        "variance, and response pattern checks."
    )
    spinner_msg = "Running heuristic bot detection..."

if st.button("🚀 Run Bot Detection", type="primary", key="fe_run_btn"):
    if st.session_state.get("fe_df_raw") is None:
        st.warning("⚠️ Please upload a CSV file first.")
        st.stop()
    if qual_mode and not st.session_state.get("fe_api_key", "").strip():
        st.warning("⚠️ Please enter your API key for qualitative mode.")
        st.stop()

    with st.spinner(spinner_msg):
        likert_cols = st.session_state.get("fe_likert_cols") or None

        if detection_method == "Classic (Heuristic)":
            result = run_detection_heuristic(
                st.session_state.fe_df_raw,
                cutoff=75,
                likert_cols=likert_cols,
                speeder_threshold=st.session_state.get("fe_speeder_threshold", 120),
                use_low_variance=st.session_state.get("fe_use_low_variance", True),
                use_missing_data=st.session_state.get("fe_use_missing_data", True),
            )
        else:
            result = run_detection(
                st.session_state.fe_df_raw,
                cutoff=st.session_state.get("fe_cutoff", 95),
                likert_cols=likert_cols,
            )
            if qual_mode:
                try:
                    from qualitative import run_qualitative
                    result = run_qualitative(result, st.session_state.fe_api_key)
                except Exception as e:
                    st.error(f"Qualitative failed: {e}")

        st.session_state.fe_df_results = result

    st.success("✅ Analysis complete.")

    if detection_method == "L1P1 (Statistical — WIP)":
        st.info(
            "💡 L1P1 complete. Consider also running Classic method to compare exclusions "
            "— use the sidebar to switch methods."
        )

st.markdown("---")

# ── Step 3: Results ───────────────────────────────────────────────────────────

if st.session_state.get("fe_df_results") is not None:
    st.subheader("Step 3 — Review Results")
    result = st.session_state.fe_df_results

    total = len(result)
    flagged_bots = int(result["is_flagged"].sum())
    if "eligibility_flag" in result.columns:
        ineligible = int((result["eligibility_flag"] != "").sum())
    else:
        ineligible = 0
    pct_bots = round(flagged_bots / total * 100, 1) if total > 0 else 0
    clean_n = total - flagged_bots - ineligible

    if detection_method == "Classic (Heuristic)":
        st.caption(f"Detection method: **{detection_method}**  |  Speeder threshold: {speeder_threshold}s")
    else:
        st.caption(f"Detection method: **{detection_method}**  |  Cutoff: {cutoff}/100")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Participants", total)
    c2.metric(
        "Flagged as Bots",
        flagged_bots,
        delta=f"{pct_bots}% of total",
        delta_color="inverse",
    )
    c3.metric("Ineligible (Q82=3)", ineligible)
    c4.metric("Clean for Analysis", clean_n)

    if detection_method == "Classic (Heuristic)":
        st.caption(
            "Classic mode: any flagged check = excluded. "
            "Review the bot_flags column for specific reasons. "
            "bot_score shows the number of checks triggered per participant."
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

    tab_bots, tab_ineligible, tab_full = st.tabs([
        "🚨 Flagged Bots",
        "⚠️ Ineligible Participants",
        "📋 Full Results",
    ])

    with tab_bots:
        bots_df = result[result["is_flagged"]]
        if len(bots_df) > 0:
            st.caption(
                f"{len(bots_df)} participants flagged as bots. "
                "Review bot_flags column for specific reasons."
            )
            st.dataframe(bots_df, use_container_width=True)
        else:
            st.success("✅ No bots detected at this cutoff.")

    with tab_ineligible:
        if "eligibility_flag" in result.columns:
            inel_df = result[result["eligibility_flag"] != ""]
            if len(inel_df) > 0:
                st.caption(
                    f"{len(inel_df)} participants marked ineligible "
                    "(Q82=3: could not think of a qualifying group). "
                    "These are excluded from the cleaned dataset separately from bots."
                )
                st.dataframe(inel_df, use_container_width=True)
            else:
                st.success("✅ No ineligible participants found.")
        else:
            st.info("No eligibility_flag column in results.")

    with tab_full:
        st.caption("All participants with detection columns appended.")
        st.dataframe(result, use_container_width=True)

    st.markdown("---")

    # ── Step 4: Downloads ─────────────────────────────────────────────────────

    st.subheader("Step 4 — Download Results")

    if "eligibility_flag" in result.columns:
        cleaned_df = result[
            (~result["is_flagged"]) & (result["eligibility_flag"] == "")
        ]
    else:
        cleaned_df = result[~result["is_flagged"]]

    bots_only_df = result[result["is_flagged"]]
    filename_base = st.session_state.get("fe_uploaded_filename", "results")

    dl1, dl2, dl3 = st.columns(3)

    with dl1:
        st.caption(
            "All rows with bot_score, bot_flags, eligibility_flag appended. "
            "Use for manual review."
        )
        st.download_button(
            "📥 Download Full Annotated CSV",
            data=result.to_csv(index=False).encode("utf-8"),
            file_name=f"FE_annotated_{filename_base}",
            mime="text/csv",
            use_container_width=True,
        )

    with dl2:
        st.caption(
            f"Cleaned dataset: {len(cleaned_df)} participants. "
            "Bots and ineligible participants removed. Ready for analysis."
        )
        st.download_button(
            "✅ Download Cleaned CSV",
            data=cleaned_df.to_csv(index=False).encode("utf-8"),
            file_name=f"FE_cleaned_{filename_base}",
            mime="text/csv",
            use_container_width=True,
        )

    with dl3:
        st.caption(
            f"Flagged bots only: {len(bots_only_df)} participants. "
            "For audit and review."
        )
        st.download_button(
            "🚨 Download Flagged Bots CSV",
            data=bots_only_df.to_csv(index=False).encode("utf-8"),
            file_name=f"FE_bots_{filename_base}",
            mime="text/csv",
            use_container_width=True,
        )
