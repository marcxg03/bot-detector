# KNOWN_ISSUES.md

## Slice 2B
🟡 Medium — entropy subscore fires on human rows with uniform response
   distributions, producing noisy flag labels even at low bot_scores.
   Consider raising flag label threshold from 0.5 to 0.7 in a future pass.
🟡 Medium — Mahalanobis centroid is computed on all rows including bots,
   which skews the reference matrix and can produce spurious flag labels
   on human rows. Scores remain correct but labels are cosmetically noisy.
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
