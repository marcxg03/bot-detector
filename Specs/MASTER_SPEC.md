# MASTER_SPEC.md
# Survey Bot Detection Tool
# Oishi Lab — Marcus Gao

---

## 1. Problem Statement

Online surveys are vulnerable to bot responses that contaminate research data. These bots exhibit statistical patterns that differ from human respondents — such as never using middle Likert values, having suspiciously low variance, or responding in impossibly short times. Researchers currently have no simple tool to automatically detect and remove these responses. This tool provides a local, uploadable CSV solution that flags and scores suspicious responses so researchers can clean their data with confidence.

---

## 2. Target Users

- **Primary user:** Marcus and Oishi Lab researchers
- **Technical level:** Comfortable running terminal commands and using Streamlit apps; not software developers
- **Context:** Cleaning survey data before statistical analysis

---

## 3. User Stories

1. As a researcher, I want to upload a CSV of survey responses so that I can analyze them for bot-like behavior without writing code.
2. As a researcher, I want each participant row flagged with a suspicion score so that I can see at a glance who is suspicious and why.
3. As a researcher, I want to set my own suspicion score cutoff so that I can control how aggressively bots are excluded.
4. As a researcher, I want to download a flagged CSV (all rows, with scores) so that I can inspect the full dataset with annotations.
5. As a researcher, I want to download a cleaned CSV (bots removed above my cutoff) so that I can use it directly in my analysis.
6. As a researcher, I want to optionally flag open-ended text responses for AI-generated content so that I can catch bots that write plausible-sounding text.
7. As a researcher, I want the AI text score kept separate from the quantitative score so that I can evaluate each dimension independently.
8. As a researcher, I want to enter my Anthropic API key in the app during my session so that I don't need to configure environment files on my machine.

---

## 4. Feature List

### P0 — Core (must have at launch)
- CSV upload interface with 5-row preview
- Fully automated column detection (Likert and text) — no manual selection required
- Quantitative bot detection engine (multiple statistical checks)
- Per-participant suspicion score (0–100)
- Per-participant flag labels listing which checks were triggered
- Adjustable suspicion score cutoff slider (default: 75)
- Download: flagged CSV — all rows with `bot_score`, `bot_flags`, `is_flagged` columns appended
- Download: cleaned CSV — rows at or above cutoff removed

### P1 — Secondary (nice to have)
- Qualitative Analysis Mode toggle
- Session-level Anthropic API key input field (appears when qualitative mode is on)
- Auto-detection of open-ended text columns
- AI-generated text scoring via Claude API
- Separate `ai_text_score` column in output (independent of `bot_score`)

### P2 — Future (out of scope for now)
- Saved detection presets
- Visual charts of score distributions
- Multi-file batch processing
- Support for Excel or SPSS file formats

---

## 5. Screens / Pages / Flows

Single-page Streamlit app with these logical sections, top to bottom:

```
[ 1. Upload ]
   → User uploads CSV
   → Tool previews first 5 rows

[ 2. Settings ]
   → Suspicion score cutoff slider (default: 75)
   → Toggle: "Enable Qualitative Analysis Mode"
     → If toggled: text input field appears for Anthropic API key
       → Key is stored in session state only, never written to disk

[ 3. Run ]
   → "Run Bot Detection" button
     → If qualitative mode is on and no API key entered: show warning, block run
   → Progress indicator while running

[ 4. Results ]
   → Summary: X participants analyzed, Y flagged (Z%)
   → Preview table of flagged rows
   → Download Button 1: Full flagged CSV (all rows + score + flag columns)
   → Download Button 2: Cleaned CSV (rows at or above cutoff removed)
```

---

## 6. Data Model

### Input
Any CSV where each row = one participant's survey responses.

### Auto-detected column types (no manual selection required)

**Likert columns** — treated as Likert if:
- dtype is numeric (int or float)
- All non-null values fall within 1–7
- Column has fewer than 8 unique values

**Text columns** (qualitative mode only) — treated as open-ended text if:
- dtype is object (string)
- Average response length > 20 characters
- Column name does not match metadata patterns (e.g. `id`, `timestamp`, `duration`, `email`)

### Appended output columns

| Column | Type | Description |
|---|---|---|
| `bot_score` | Integer 0–100 | Composite quantitative suspicion score |
| `bot_flags` | String | Comma-separated list of triggered detection checks |
| `is_flagged` | Boolean | True if bot_score ≥ user-defined cutoff |
| `ai_text_score` | Integer 0–100 | AI-generated text suspicion score (P1 only, kept separate from bot_score) |

### Detection checks

| Check | What it detects | Weight |
|---|---|---|
| Straight-lining | Participant gives identical answer to every Likert item | 30 |
| Low variance | Standard deviation across Likert responses is extremely low | 25 |
| Likert range avoidance | Never uses middle values (e.g. 3, 4 on a 1–7 scale) | 15 |
| All-extreme responding | Only uses scale endpoints (e.g. 1s and 7s only) | 15 |
| Speeder detection | Response time is suspiciously short (if timing column exists) | 25 |
| Identical responses | Response pattern duplicates another participant exactly | 20 |
| Missing data patterns | Systematic skipping of specific question types | 10 |

**Composite scoring:**
```
bot_score = weighted_sum(triggered_checks) / max_possible_weighted_sum * 100
```
Scores normalize to 0–100 regardless of which checks ran or were skipped.

---

## 7. External Integrations

- **Anthropic Claude API** — used for qualitative AI text detection (P1 feature only)
- Model: `claude-sonnet-4-20250514`
- API key entered by user in the app UI during session; never stored to disk
- No other external services required

---

## 8. Non-Functional Requirements

- Runs entirely locally via `python3 -m streamlit run app.py`
- No internet connection required for P0 core features
- Internet required only when Qualitative Analysis Mode is enabled (API call to Claude)
- CSV files up to ~5,000 rows should process in under 30 seconds
- No data is stored — everything lives in Streamlit session memory only
- Must run on Mac (primary) and Windows (secondary)
- No user accounts, no login, no cloud deployment

---

## 9. Out of Scope

- User accounts or authentication
- Cloud deployment
- Database storage of any results
- Real-time collaboration
- Support for non-CSV file formats (Excel, SPSS, etc.)
- Detecting bots based on IP address or metadata not present in the CSV
- Manual column selection by the user
- Adjustable detection check weights in the UI

---

## 10. Open Questions

| # | Question | Resolution |
|---|---|---|
| 1 | Should detection weights be adjustable in the UI? | No — fixed in code, tunable by developer if needed later |
| 2 | Should speeder detection be built if no timing column exists? | Yes — build it but skip gracefully if no duration/timing column is found |
| 3 | Should the tool auto-detect 1–5 vs 1–7 Likert scale? | Yes — auto-detect scale range from column values |
| 4 | Which model for AI text detection? | `claude-sonnet-4-20250514` — consistent with other lab tools |
