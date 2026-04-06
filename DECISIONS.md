# DECISIONS.md

## Slice 2B
- reverse_consist excluded — requires pre-defined reverse-scored item pairs
  that vary per instrument; deferred to future enhancement
- Hard flags bypass composite entirely so egregious bots don't get
  diluted by clean subscores
- all_likert_matrix currently includes bot rows — accepted tradeoff for
  now; filtering hard-flagged rows would improve Mahalanobis accuracy
  but adds complexity (chicken-and-egg: need to detect bots to exclude
  them from the reference matrix)

## Slice 2
- check_low_variance uses 10th percentile threshold across all participants —
  means small datasets (< 10 rows) may produce unexpected flagging behavior
- All check scores are binary (0.0 or 100.0) rather than graduated —
  keeps scoring simple and auditable for researchers

## Slice 1
- anthropic>=0.40.0 chosen over 0.21.0 to avoid known httpx conflict from prior lab projects
- No virtual environment set up yet — packages installed to user site-packages (acceptable for lab use, revisit if dependency conflicts arise)
