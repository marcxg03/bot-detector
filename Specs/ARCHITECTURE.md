# ARCHITECTURE.md
# Survey Bot Detection Tool
# Oishi Lab — Marcus Gao

---

## Tech Stack Decision

| Layer | Choice | Rationale |
|---|---|---|
| UI Framework | Streamlit | Consistent with all existing Oishi Lab tools; runs locally with one terminal command |
| Language | Python 3 | Best ecosystem for data analysis; all detection checks use standard scientific libraries |
| Data processing | pandas | Industry standard for CSV manipulation and statistical operations |
| Statistical checks | numpy, scipy | Low variance, standard deviation, and pattern detection calculations |
| AI text detection | Anthropic Python SDK | Already used in other lab projects; claude-sonnet-4-20250514 for accuracy |
| Output | CSV via pandas | Simplest format for researchers to open in Excel, R, or Python |

No `.env` file or `python-dotenv` required — API key is entered by the user in the app UI and stored in session state only. It is never written to disk.

---

## File / Folder Structure

```
survey-bot-detector/
├── app.py                  # Main Streamlit app — UI only, no detection logic
├── detector.py             # Core quantitative bot detection engine
├── qualitative.py          # AI text detection module (P1)
├── utils.py                # Shared helpers: column inference, scoring normalization
├── requirements.txt        # All pip dependencies
├── .gitignore              # Excludes output/, __pycache__, .env, .DS_Store, etc.
├── README.md               # Setup and launch instructions
└── Docs/
    ├── MASTER_SPEC.md
    ├── ARCHITECTURE.md
    ├── CHANGELOG.md
    ├── DECISIONS.md
    └── KNOWN_ISSUES.md
```

---

## Module Map

| File | Single Responsibility |
|---|---|
| `app.py` | Renders the Streamlit UI. Handles file upload, settings controls, Run button, progress indicator, results summary, preview table, and download buttons. Contains zero detection logic. |
| `detector.py` | Runs all quantitative bot detection checks against a pandas DataFrame. Returns the DataFrame with `bot_score`, `bot_flags`, and `is_flagged` columns appended. |
| `qualitative.py` | Auto-detects text columns, batches responses into Claude API calls, returns `ai_text_score` column. Only called when qualitative mode is toggled on and API key is provided. |
| `utils.py` | Shared helper functions: Likert column inference, text column inference, composite score normalization from individual check results. |

---

## Detection Engine Design (`detector.py`)

Each check is an independent function that returns a score contribution (0–100) and a flag label string. The composite `bot_score` is a weighted average of all checks that ran (skipped checks are excluded from the denominator).

### Checks, weights, and skip conditions

| Check | Function | Weight | Skip condition |
|---|---|---|---|
| Straight-lining | `check_straight_lining()` | 30 | Fewer than 3 Likert columns detected |
| Low variance | `check_low_variance()` | 25 | Fewer than 3 Likert columns detected |
| Likert range avoidance | `check_range_avoidance()` | 15 | Scale range undetectable |
| All-extreme responding | `check_extreme_responding()` | 15 | Scale range undetectable |
| Speeder detection | `check_speeder()` | 25 | No duration/timing column found in CSV |
| Identical responses | `check_duplicate_patterns()` | 20 | Fewer than 2 participants |
| Missing data patterns | `check_missing_patterns()` | 10 | No systematic missingness detected |

### Composite scoring logic

```python
# Pseudocode
active_checks = [c for c in all_checks if not c.skipped]
weighted_sum = sum(c.score * c.weight for c in active_checks)
max_possible = sum(c.weight for c in active_checks)
bot_score = int((weighted_sum / max_possible) * 100)
```

Scores normalize to 0–100 regardless of which checks ran.

### Output columns appended by detector.py

| Column | Type | Description |
|---|---|---|
| `bot_score` | int | Composite suspicion score 0–100 |
| `bot_flags` | str | Comma-separated triggered check names, e.g. `"straight_lining, low_variance"` |
| `is_flagged` | bool | True if bot_score ≥ user-defined cutoff |

---

## Column Auto-Detection Logic (`utils.py`)

### Likert column detection
A column is classified as Likert if ALL of the following are true:
- `dtype` is numeric (`int64` or `float64`)
- All non-null values fall within the range 1–7
- Column has fewer than 8 unique non-null values

Scale range (1–5 vs 1–7) is inferred from the maximum value present in detected Likert columns.

### Text column detection (qualitative mode only)
A column is classified as open-ended text if ALL of the following are true:
- `dtype` is `object` (string)
- Mean response length > 20 characters (null values excluded)
- Column name does not match metadata name patterns: `id`, `timestamp`, `duration`, `email`, `date`, `time`, `ip`, `status`, `response_id`

---

## Qualitative Detection Design (`qualitative.py`)

Runs only when qualitative mode is toggled on and a valid API key is provided.

### Flow
1. Call `utils.get_text_columns(df)` to auto-detect open-ended text columns
2. For each text column, collect all non-null participant responses
3. Batch responses into API calls (max ~20 responses per call to stay within token limits)
4. Send each batch to Claude with a structured scoring prompt
5. Parse JSON response — an array of scores (0–100) per response
6. Average scores across all text columns per participant
7. Append `ai_text_score` column to DataFrame

### API prompt design
Each call sends a batch of responses and instructs Claude to return only a JSON array of integer scores — no explanation, no preamble. This keeps API calls minimal and responses parseable.

```
System: You are a research assistant detecting AI-generated text in survey responses.
        Respond ONLY with a valid JSON array of integers, one score per response.
        Score 0 = clearly human-written. Score 100 = clearly AI-generated.
        Do not include any explanation or text outside the JSON array.

User:   Score each of the following survey responses for likelihood of being AI-generated:
        1. [response text]
        2. [response text]
        ...
```

### Output column

| Column | Type | Description |
|---|---|---|
| `ai_text_score` | int | AI-generated text suspicion score 0–100. Independent of bot_score. |

---

## State Management

Streamlit rerenders the entire page on every user interaction. The following are persisted across rerenders using `st.session_state`:

| Key | Type | Contents |
|---|---|---|
| `df_raw` | DataFrame | Original uploaded CSV |
| `df_results` | DataFrame | DataFrame with all appended output columns after Run |
| `api_key` | str | Anthropic API key entered by user (session only, never written to disk) |
| `cutoff` | int | User-defined suspicion score cutoff (default 75) |
| `qualitative_mode` | bool | Whether qualitative analysis mode is toggled on |

No database. No persistent storage. All state is lost when the browser tab is closed.

---

## Auth Flow

None required. No login, no accounts.

Anthropic API key for qualitative mode:
- Entered by user in a password-type text input field in the UI
- Stored only in `st.session_state.api_key`
- Passed directly to the `anthropic.Anthropic(api_key=...)` client at runtime
- Never written to any file or logged anywhere

---

## API Contract

This is a local Streamlit app with no backend routes. All data flow is internal between Python modules.

### Internal function contracts

**`detector.run_detection(df: DataFrame) -> DataFrame`**
- Input: raw uploaded DataFrame
- Output: same DataFrame with `bot_score`, `bot_flags`, `is_flagged` columns appended

**`qualitative.run_qualitative(df: DataFrame, api_key: str) -> DataFrame`**
- Input: DataFrame (post-detection), valid Anthropic API key string
- Output: same DataFrame with `ai_text_score` column appended

**`utils.get_likert_columns(df: DataFrame) -> list[str]`**
- Input: any DataFrame
- Output: list of column names classified as Likert scale

**`utils.get_text_columns(df: DataFrame) -> list[str]`**
- Input: any DataFrame
- Output: list of column names classified as open-ended text

**`utils.normalize_score(weighted_sum: float, max_possible: float) -> int`**
- Input: weighted sum of triggered check scores, maximum possible weighted sum
- Output: integer score 0–100

---

## Key Dependencies

```
streamlit>=1.32.0       # UI framework
pandas>=2.0.0           # CSV handling and data manipulation
numpy>=1.26.0           # Numerical operations
scipy>=1.12.0           # Statistical calculations (std dev, z-scores)
anthropic>=0.21.0       # Claude API client for qualitative detection
```

Note: If using `anthropic>=0.28.0`, no httpx pinning is required. If using `anthropic==0.21.0`, pin `httpx>=0.23.0,<0.28.0` to avoid SDK conflicts (known issue from prior lab projects).
