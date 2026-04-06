# CHANGELOG.md

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
