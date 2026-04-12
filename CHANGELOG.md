# CHANGELOG.md

## Fix: exact_duplicate false positives on early dropouts
- Rewrote hard_flag_duplicate() with two safeguards:
  1. Near-constant column exclusion (>80% same value = screener)
  2. Minimum response threshold (min_items=10 substantive responses)
- Fixed secondary bug: run_detection_heuristic() was calling
  df.duplicated() directly, bypassing hard_flag_duplicate() entirely
- Early dropout participants (answered only Q82/Q1 and stopped)
  no longer incorrectly flagged as exact_duplicate
- Genuine bot duplicates (identical responses across 10+ items)
  still correctly flagged

## Column Selection Feature + Likert Detection Fix
- utils.py: Rewrote get_likert_columns() with 6 strict rules —
  numeric coercion, integer-only values, 1-7 range, >=2 unique values,
  <8 unique values, metadata name exclusion (29 blocked substrings).
  Added get_likert_columns_strict(df, max_value) for 1-5 scale support.
- detector.py: Added likert_cols parameter to run_detection() —
  researcher-selected columns used when provided, auto-detection as
  fallback. Strengthened Qualtrics row guard to >=50% numeric threshold.
- app.py: Added Step 1.5 — Column Selection with Auto/Manual modes.
  Auto shows detected columns in expandable list. Manual shows
  multiselect pre-populated with auto-detected defaults. likert_cols
  stored in session state, reset on new file upload.

## Qualtrics Format Fix (post Slice 2D)
- app.py: Added two-pass CSV read to auto-detect and skip Qualtrics
  extra header rows (question labels + ImportId metadata). Uses
  io.BytesIO(raw_bytes) pattern for reliable re-read without seek().
- detector.py: Added defensive numeric_mask guard to drop any
  residual label rows that slipped through app.py detection.
- Participant count now correct (350, not 352 including junk rows).
- Standard non-Qualtrics CSVs unaffected.

## Slice 2D — L1P1 Detection Engine (Vectorized + Parallel)
- Replaced heuristic composite engine with L1P1 (Ilagan & Falk, 2024)
- Implements permutation test with leave-one-out anchor computation
- Vectorized NRI computation using np.einsum across all 200 permutations
- Parallel participant processing via joblib Parallel(n_jobs=-1)
- Output: bot_score (0-100), l1p1_pvalue (float), bot_flags, is_flagged
- All 5 automated tests passing (10/10 bots detected in synthetic test)
- Real dataset validation pending local path setup
- python3 PATH resolved to wrong interpreter — fixed via venv

## Slice 4 — Qualitative Mode (verified with real API key)
- ai_text_score column confirmed present in Flagged Responses tab
- Known AI rows scoring 85–100 on ai_text_score
- Known human rows not shown in flagged tab (correct)
- Invalid API key correctly shows st.error() with quantitative
  results still available
- Full end-to-end pipeline verified: bot_score + ai_text_score
  both present and correct in output

## Slice 4 — Qualitative Analysis Mode
- Implemented run_qualitative() in qualitative.py
- Auto-detects text columns via utils.get_text_columns()
- Batches responses (max 20) to claude-sonnet-4-20250514
- Returns ai_text_score column (int 0–100) averaged across text columns
- AuthenticationError explicitly re-raised before general except block
  so app.py catches and displays it correctly (deviation from spec —
  improvement over bare except Exception)
- All three manual test steps passing

## Slice 3 — Streamlit UI
- Built complete polished UI in app.py
- Sidebar: settings panel, about expander, cutoff slider,
  qualitative mode toggle, API key input
- Main area: four labelled steps with captions and dividers
- Results: metric row (Total/Flagged/Cutoff), tabbed preview
  (Flagged Responses + Full Results), two download buttons
- Tested on test_survey.csv — 15 participants, 6 flagged, 9 clean
- All 16 manual test steps passing

## Slice 2C — Detection Engine Patch
- Raised flag label threshold from 0.5 → 0.70 (Codex set 0.65,
  Claude Code corrected to 0.70 after entropy score math validated)
- Mahalanobis reference matrix now excludes hard-flagged rows (Pass 1
  pre-filtering)
- All 15 assertions passing, no spurious entropy or mahalanobis labels
  on human rows
- even_odd flag still appears on R008 and R015 — accepted behavior

## Slice 2B — Detection Engine V2
- Replaced binary detection engine with continuous subscore algorithm
- Added hard flags: exact_duplicate, longstring_absolute (auto-score 100)
- Added subscores: longstring, irv, mahalanobis, even_odd, entropy, speeder, missing
- All 6 known bot rows flagged, all 9 human rows clean on test_survey.csv
- test_survey.csv and test_slice2b.py created by Claude Code (not Codex)
- detector.py required no changes after Codex generation

## Slice 2 — Detection Engine
- Implemented get_likert_columns(), get_text_columns(), normalize_score() in utils.py
- Implemented all seven check functions and run_detection() in detector.py
- All four test_slice2.py assertions passing
- test_slice2.py created by Claude Code from spec (was not written to disk by Codex)

## Slice 1 — Project Scaffold
- Created requirements.txt with all dependencies
- Created README.md with setup and launch instructions
- Created app.py as empty Streamlit stub
- Created detector.py with all check function stubs
- Created qualitative.py with run_qualitative stub
- Created utils.py with helper function stubs
- scipy was not pre-installed; pip3 install -r requirements.txt resolved it
