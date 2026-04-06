# DECISIONS.md

## Slice 3
- Sidebar used for settings to keep main area clean and focused
  on the step-by-step workflow
- st.tabs() used for results preview instead of separate expanders —
  cleaner UX for switching between flagged and full views
- download_button data encoded as UTF-8 bytes directly from DataFrame
  to avoid needing io.StringIO intermediary

## Slice 2C
- Flag label threshold set to 0.70 (not 0.65 as originally specced)
  Reason: humans with perfectly uniform 1–7 distributions produce
  entropy subscore of exactly 0.667, which sits above 0.65.
  Threshold raised to 0.70 to clear this edge case cleanly.
- even_odd labels on R008 and R015 are accepted — these rows have
  genuinely negatively correlated even/odd halves (r ≈ -0.48), which
  is an unusual but valid human response pattern. Not a false positive
  in the scoring sense — bot_score remains well below 75.

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
