# CHANGELOG.md

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
