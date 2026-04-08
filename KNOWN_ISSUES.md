# KNOWN_ISSUES.md

## Qualtrics Format Fix
🟢 Low — If a legitimate survey response cell contains the string
   "ImportId", the tool will incorrectly treat a standard CSV as
   Qualtrics format and skip rows 1 and 2. Extremely unlikely in
   practice.
🟢 Low — Older Qualtrics export formats that don't include ImportId
   metadata may not be auto-detected. Fix 2 in detector.py still
   protects against label rows corrupting Likert detection.

## Slice 2D
🟢 Low — python3 in shell PATH may not resolve to venv interpreter.
   Fix: always activate venv before running (source venv/bin/activate)
🟢 Low — Real dataset runtime not yet benchmarked locally. Expected
   30-90s on MacBook with 8 cores at B=200 permutations.
🟢 Low — L1P1 exchangeability assumption may not hold for partially
   careless responders (bots on some items only). Known limitation
   documented in Ilagan & Falk (2024).

## Slice 4
🟢 Low — Empty/null text responses sent to Claude as empty strings
   rather than skipped. Claude scores them low, which is acceptable
   but semantically meaningless. Future fix: skip empty strings and
   inject score of 0 directly.
🟢 Low — Model ID claude-sonnet-4-20250514 hardcoded at call site.
   Extract to MODULE_MODEL constant for easier future maintenance.
🟢 Low — ai_text_score presence in downloads depends on qualitative
   mode being active at run time. Verify column appears in both CSVs
   when qualitative mode is on.

## Slice 3
🟢 Low — Flagged Responses tab shows original DataFrame row index
   numbers (e.g. 2, 4, 6) not sequential 1–N. Cosmetically minor,
   does not affect data accuracy.

## Slice 2C
✅ Resolved — entropy flag label noise on human rows (threshold → 0.70)
✅ Resolved — Mahalanobis centroid polluted by bot rows (Pass 1 filter)
🟢 Low — even_odd flag label appears on R008 and R015 due to negatively
   correlated even/odd item halves. Scores correct, labels cosmetically
   noisy. Accepted behavior for now.

## Slice 2B
🟡 Medium — entropy subscore fires on human rows with uniform response
   distributions, producing noisy flag labels even at low bot_scores.
   Consider raising flag label threshold from 0.5 to 0.7 in a future pass.
   → Resolved in Slice 2C
🟡 Medium — Mahalanobis centroid is computed on all rows including bots,
   which skews the reference matrix and can produce spurious flag labels
   on human rows. Scores remain correct but labels are cosmetically noisy.
   → Resolved in Slice 2C
🟢 Low — test_survey.csv bots all use 100% straight-lining so hard flags
   fire before composite runs. Real-world bots with subtler patterns will
   exercise the composite path more heavily; monitor in production use.

## Slice 2
🟢 Low — Text column detection mean-length threshold (>20 chars) can be unreliable
   on datasets with many very short responses. May miss open-ended columns.
🟢 Low — check_low_variance can flag human rows in very small datasets (< 10
   participants) because the 10th percentile collapses to the minimum std dev.
   Expected behavior but worth noting for small pilot studies.

## Slice 1
🟢 Low — utils.py uses list[str] PEP 585 syntax, requires Python 3.9+. Not an issue for current lab machines.
🟢 Low — No virtual environment configured. Worth adding before Slice 2 if dependency conflicts arise.
