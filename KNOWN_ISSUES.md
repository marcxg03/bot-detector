# KNOWN_ISSUES.md

## Slice 2
🟢 Low — Text column detection mean-length threshold (>20 chars) can be unreliable
   on datasets with many very short responses. May miss open-ended columns.
🟢 Low — check_low_variance can flag human rows in very small datasets (< 10
   participants) because the 10th percentile collapses to the minimum std dev.
   Expected behavior but worth noting for small pilot studies.

## Slice 1
🟢 Low — utils.py uses list[str] PEP 585 syntax, requires Python 3.9+. Not an issue for current lab machines.
🟢 Low — No virtual environment configured. Worth adding before Slice 2 if dependency conflicts arise.
