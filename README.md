# Survey Bot Detector
**Oishi Lab — University of Chicago**

A local Streamlit app that detects and flags bot-like responses in Qualtrics survey data using heuristic and statistical methods.

---

## What This Tool Does

Online survey data is increasingly contaminated by automated bots that submit low-quality or fraudulent responses. These responses can distort statistical analyses and undermine research validity. Survey Bot Detector provides automated, transparent flagging of suspicious response patterns so researchers can identify and remove problematic data before analysis.

The tool runs two detection methods — a fast **Classic Heuristic** engine and a peer-reviewed **L1P1 Statistical** permutation test (Ilagan & Falk, 2024) — and produces annotated CSVs with human-readable flag labels for researcher review. It has two pages: **General Bot Detection** works on any Qualtrics or standard survey CSV, and **FE Study** is pre-configured with study-specific rules for the Freedom of Expression instrument. No data leaves your machine.

---

## Pages

| Page | Purpose |
|---|---|
| General Bot Detection | Works on any Qualtrics or standard survey CSV |
| FE Study | Pre-configured for the Freedom of Expression study instrument |

---

## Prerequisites

| Requirement | Why | Check |
|---|---|---|
| Python 3.9+ | Runs the app | `python3 --version` |
| pip3 | Installs packages | `pip3 --version` |
| Git | Downloads the tool | `git --version` |

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/marcxg03/bot-detector.git
cd bot-detector
```

**2. Create a virtual environment (recommended)**

```bash
python3 -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows
```

**3. Install dependencies**

```bash
pip3 install -r requirements.txt
```

**4. Verify installation**

```bash
python3 -c "import streamlit, pandas, numpy, joblib, anthropic; print('All good!')"
```

---

## Launching the Tool

```bash
source venv/bin/activate
python3 -m streamlit run app.py
```

Opens at **http://localhost:8501**. Two pages appear in the left sidebar: **General Bot Detection** and **FE Study**.

Keep the terminal window open while using the tool. Press `Ctrl+C` to stop.

---

## How to Use — General Bot Detection Page

### Step 1 — Upload Your Survey CSV

- Accepts any Qualtrics export or standard CSV
- Qualtrics header rows (question labels + ImportId metadata) are stripped automatically

### Step 1.5 — Select Likert Columns

- **Auto tab**: the tool detects Likert-scale columns automatically and shows a summary table. Click **Use Automatic Selection** to confirm.
- **Manual tab**: checkbox table of all numeric columns, pre-checked with auto-detected defaults. Deselect any columns that are not Likert items, then click **Use Manual Selection** to confirm.

### Step 2 — Configure Settings and Run

**Sidebar settings:**

- **Detection Method**
  - *Classic (Heuristic)*: fast, any flag = flagged, transparent criteria. Speeder threshold is adjustable (default 120s).
  - *L1P1 (Statistical)*: peer-reviewed permutation test (Ilagan & Falk, 2024). Cutoff slider maps to statistical sensitivity (default 95 = 95% sensitivity).
- **Qualitative Analysis Mode** *(optional)*: analyzes open-ended text for AI-generated content. Requires an Anthropic API key.

Click **🚀 Run Bot Detection**.

### Step 3 — Review Results

- **Metrics row**: Total Participants / Flagged as Bots / Ineligible / Clean for Analysis
- **🚨 Flagged Bots tab**: all flagged rows with `bot_flags` labels
- **⚠️ Ineligible Participants tab**: eligibility exclusions
- **📋 Full Results tab**: all rows with appended detection columns
- **📖 Flag Definitions expander**: reference panel explaining all flag labels and what triggered them

### Step 4 — Download Results

- **Download Full Annotated CSV**: all rows with detection columns appended — use for manual review
- **Download Cleaned CSV**: bots and ineligible participants removed — ready for analysis
- **Download Flagged Bots CSV**: flagged rows only — for audit and review

---

## How to Use — FE Study Page

### Step 1 — Upload FE Study CSV

- Upload a Qualtrics export from the Freedom of Expression study
- Auto-detects **Wave 1 (FE2a)** or **Wave 2** from column structure
- Shows participant count, Likert columns detected, and the number of participants who answered Q82=3

### Step 2 — Run

- Same detection method options as the General page
- L1P1 is marked as Work in Progress on this page — run Classic method for production data cleaning

### Step 3 — Review Results

- Same four metrics and three result tabs
- The **⚠️ Ineligible Participants tab** specifically shows Q82=3 participants (could not think of a qualifying intellectual group), who are excluded separately from detected bots

### Step 4 — Download

| Button | Contents |
|---|---|
| Download Full Annotated CSV | All rows with detection columns appended |
| Download Cleaned CSV | Bots and ineligible participants removed |
| Download Flagged Bots CSV | Flagged rows only |

---

## Output Columns

These columns are appended to the original data in every download:

| Column | Type | Description |
|---|---|---|
| `bot_score` | Integer | Number of detection checks triggered (0 = clean, higher = more flags). For L1P1: mapped from p-value as `int(round((1−p)×100))`. |
| `bot_flags` | String | Comma-separated list of triggered checks with details, e.g. `"longstring_absolute, speeder (45s < 120s)"` |
| `is_flagged` | Boolean | `True` if any check was triggered (Classic) or p-value ≥ alpha (L1P1) |
| `l1p1_pvalue` | Float | L1P1 method only. P-value from permutation test (0 = certain bot, 1 = certain human) |
| `eligibility_flag` | String | `"ineligible_no_group"` if Q82=3, else empty |

---

## Flag Definitions

### Hard Flags — any occurrence = flagged, `bot_score` += 1 each

| Flag | What triggered it | What it means |
|---|---|---|
| `longstring_absolute` | Same answer on >90% of Likert items | Strongest bot signal. Genuine humans almost never select the same value across 90%+ of a long survey. |
| `exact_duplicate` | Identical Likert response pattern as another participant | Consistent with bots running the same script or participants copying answers. |

### Soft Flags — any occurrence = flagged, `bot_score` += 1 each

| Flag | What triggered it | What it means |
|---|---|---|
| `speeder` | Completed in under threshold seconds (default 120s) | A long survey cannot be read and answered genuinely this quickly. Actual time shown in flag, e.g. `speeder (45s < 120s)`. |
| `low_variance` | Row SD in bottom 10% of sample | Humans naturally vary responses across items; very low variance suggests non-engagement. |
| `longstring_run` | Same answer consecutively on >50% of items | Patterned repetition within sections — distinct from `longstring_absolute`, which checks the whole survey. |
| `range_avoidance` | Only 1–2 unique values used on a 1–7 scale | Genuine respondents typically use most of the scale range. |
| `extreme_responding` | >80% of responses at scale endpoints | Selecting only 1s and 7s across most items is a common bot pattern. |
| `missing_data` | >50% of Likert items blank | May reflect dropout or non-engagement; weaker signal on its own, stronger in combination. |

### L1P1 Statistical Flags (L1P1 method only)

| Flag | What it means |
|---|---|
| `l1p1_permutation_test` | Response pattern is statistically consistent with random responding per Ilagan & Falk (2024). See `l1p1_pvalue` for the exact p-value. |
| `fast_completion` | Contextual diagnostic: participant also completed the survey in under the speeder threshold. |

### Eligibility Flag

| Flag | What it means |
|---|---|
| `ineligible_no_group` | Participant answered Q82=3 (could not think of a qualifying intellectual group). Not a bot — excluded for eligibility reasons and counted separately. |

---

## Detection Methods

### Classic (Heuristic)

- Any single check firing marks the participant as flagged
- No weighted scoring — each triggered check contributes equally to `bot_score`
- Speeder threshold adjustable in the sidebar (default 120s)
- Recommended for production data cleaning
- Fast — runs in seconds on any dataset size

### L1P1 (Statistical) — Work in Progress

Implements the unsupervised permutation test from:

> Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised detection of bots in a Likert-type questionnaire. *Behavior Research Methods, 56*(5), 5068–5085. https://doi.org/10.3758/s13428-023-02246-7

- Outputs a p-value per participant — p ≥ 0.05 → flagged at 95% sensitivity (default cutoff 95)
- Uses 200 permutations per participant with leave-one-out anchor computation
- Parallelized across CPU cores via `joblib`
- Currently being validated on Oishi Lab survey data
- **Use Classic method for production data cleaning until L1P1 validation is complete**

---

## Qualitative Analysis Mode

Optional feature available on both pages. Requires an Anthropic API key.

- Analyzes open-ended text responses for AI-generated content using the Claude API
- Adds an `ai_text_score` column (0–100) to the output
- Score is independent of `bot_score`
- Enter your API key in the sidebar — stored in session memory only, never saved to disk

---

## Technical Notes

- Runs entirely locally — no data is uploaded anywhere
- Qualtrics CSVs are auto-detected and header rows stripped automatically
- Supports 1–5 and 1–7 Likert scales
- Tested on datasets with 100–200 Likert items and 300–500 participants
- Always run inside the virtual environment to avoid dependency conflicts

---

## Getting Updates

```bash
cd bot-detector
git pull
pip3 install -r requirements.txt
```

---

## Citation

If you use L1P1 detection in published work, please cite:

Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised detection of bots in a Likert-type questionnaire. *Behavior Research Methods, 56*(5), 5068–5085. https://doi.org/10.3758/s13428-023-02246-7

Falk, C. F., Huang, A., & Ilagan, M. J. (2025). Unsupervised detection of bots and inattentive respondents in survey data: Current methods and a new framework. *Psychological Methods.* Advance online publication. https://doi.org/10.1037/met0000750
