# Survey Bot Detector
Oishi Lab, University of Chicago

A local Streamlit app that flags bot-like responses in Qualtrics survey data using heuristic and statistical methods.

## What it does

Automated bots submit low-quality or fraudulent responses to online surveys, and those responses can distort the analysis. Survey Bot Detector flags suspicious response patterns so researchers can review and remove them before analysis, and it shows why each row was flagged.

It has two detection methods: a fast Classic heuristic engine and the L1P1 statistical permutation test (Ilagan & Falk, 2024). Both produce annotated CSVs with readable flag labels for researcher review. The General Bot Detection page works on any Qualtrics or standard survey CSV, and the FE Study page is preconfigured with rules for the Freedom of Expression instrument. Your data stays on your machine.

## Pages

| Page | Purpose |
|---|---|
| General Bot Detection | Works on any Qualtrics or standard survey CSV |
| FE Study | Preconfigured for the Freedom of Expression study instrument |

## Prerequisites

| Requirement | Why | Check |
|---|---|---|
| Python 3.9+ | Runs the app | `python3 --version` |
| pip3 | Installs packages | `pip3 --version` |
| Git | Downloads the tool | `git --version` |

## Installation

1. Clone the repository

```bash
git clone https://github.com/marcxg03/bot-detector.git
cd bot-detector
```

2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows
```

3. Install dependencies

```bash
pip3 install -r requirements.txt
```

4. Verify the installation

```bash
python3 -c "import streamlit, pandas, numpy, joblib, anthropic; print('All good!')"
```

## Launching the tool

```bash
source venv/bin/activate
python3 -m streamlit run app.py
```

The app opens at http://localhost:8501, with two pages in the left sidebar: General Bot Detection and FE Study.

Keep the terminal window open while you use the tool. Press `Ctrl+C` to stop it.

## Using the General Bot Detection page

### Step 1: upload your survey CSV

- Accepts any Qualtrics export or standard CSV.
- Qualtrics header rows (question labels and ImportId metadata) are stripped automatically.

### Step 1.5: select Likert columns

- Auto tab: the tool detects Likert-scale columns and shows a summary table. Click **Use Automatic Selection** to confirm.
- Manual tab: a checkbox table of all numeric columns, pre-checked with the auto-detected defaults. Uncheck any column that is not a Likert item, then click **Use Manual Selection**.

### Step 2: configure settings and run

Sidebar settings:

- Detection method
  - *Classic (Heuristic)*: fast and transparent; any single flag marks the row. The speeder threshold is adjustable (default 120s).
  - *L1P1 (Statistical)*: the permutation test from Ilagan & Falk (2024). The cutoff slider sets statistical sensitivity (default 95 = 95% sensitivity).
- Qualitative Analysis Mode *(optional)*: checks open-ended text for AI-generated content. Requires an Anthropic API key.

Click **🚀 Run Bot Detection**.

### Step 3: review results

- Metrics row: Total Participants / Flagged as Bots / Ineligible / Clean for Analysis
- 🚨 Flagged Bots tab: all flagged rows with their `bot_flags` labels
- ⚠️ Ineligible Participants tab: eligibility exclusions
- 📋 Full Results tab: all rows with the detection columns appended
- 📖 Flag Definitions expander: what each flag label means and what triggers it

### Step 4: download results

- Download Full Annotated CSV: all rows with detection columns appended, for manual review
- Download Cleaned CSV: bots and ineligible participants removed, ready for analysis
- Download Flagged Bots CSV: flagged rows only, for audit

## Using the FE Study page

### Step 1: upload the FE Study CSV

- Upload a Qualtrics export from the Freedom of Expression study.
- The page detects Wave 1 (FE2a) or Wave 2 from the column structure.
- It shows the participant count, the Likert columns detected, and how many participants answered Q82=3.

### Step 2: run

- The detection methods are the same as on the General page.
- L1P1 is marked as a work in progress here. Use the Classic method for production data cleaning.

### Step 3: review results

- Same four metrics and three result tabs.
- The ⚠️ Ineligible Participants tab shows the Q82=3 participants (who could not think of a qualifying intellectual group). They are excluded separately from detected bots.

### Step 4: download

| Button | Contents |
|---|---|
| Download Full Annotated CSV | All rows with detection columns appended |
| Download Cleaned CSV | Bots and ineligible participants removed |
| Download Flagged Bots CSV | Flagged rows only |

## Output columns

Every download appends these columns to the original data:

| Column | Type | Description |
|---|---|---|
| `bot_score` | Integer | Number of detection checks triggered (0 = clean, higher = more flags). For L1P1: mapped from the p-value as `int(round((1−p)×100))`. |
| `bot_flags` | String | Comma-separated list of triggered checks with details, e.g. `"longstring_absolute, speeder (45s < 120s)"` |
| `is_flagged` | Boolean | `True` if any check was triggered (Classic) or p-value ≥ alpha (L1P1) |
| `l1p1_pvalue` | Float | L1P1 method only. P-value from the permutation test (0 = certain bot, 1 = certain human) |
| `eligibility_flag` | String | `"ineligible_no_group"` if Q82=3, otherwise empty |

## Flag definitions

### Hard flags (any occurrence flags the row; each adds 1 to `bot_score`)

| Flag | What triggered it | What it means |
|---|---|---|
| `longstring_absolute` | Same answer on >90% of Likert items | The strongest bot signal. People almost never pick the same value across 90%+ of a long survey. |
| `exact_duplicate` | Identical Likert response pattern to another participant | Consistent with bots running the same script, or participants copying answers. |

### Soft flags (any occurrence flags the row; each adds 1 to `bot_score`)

| Flag | What triggered it | What it means |
|---|---|---|
| `speeder` | Completed in under the threshold (default 120s) | Nobody can read and answer a long survey this fast. The flag shows the actual time, e.g. `speeder (45s < 120s)`. |
| `low_variance` | Row SD in the bottom 10% of the sample | People vary their answers across items; very low variance suggests they weren't engaged. |
| `longstring_run` | Same answer consecutively on >50% of items | Repetition within sections. `longstring_absolute` checks the whole survey instead. |
| `range_avoidance` | Only 1 or 2 unique values used on a 1 to 7 scale | Real respondents usually use most of the scale. |
| `extreme_responding` | >80% of responses at the scale endpoints | Picking only 1s and 7s across most items is a common bot pattern. |
| `missing_data` | >50% of Likert items blank | May mean dropout or disengagement. A weak signal alone, stronger alongside other flags. |

### L1P1 statistical flags (L1P1 method only)

| Flag | What it means |
|---|---|
| `l1p1_permutation_test` | The response pattern is statistically consistent with random responding (Ilagan & Falk, 2024). See `l1p1_pvalue` for the exact p-value. |
| `fast_completion` | Context only: the participant also finished under the speeder threshold. |

### Eligibility flag

| Flag | What it means |
|---|---|
| `ineligible_no_group` | The participant answered Q82=3 (could not think of a qualifying intellectual group). Not a bot; excluded for eligibility and counted separately. |

## Detection methods

### Classic (heuristic)

- Any single check that fires flags the participant.
- Each triggered check adds 1 to `bot_score`; there is no weighting.
- The speeder threshold is adjustable in the sidebar (default 120s).
- Recommended for production data cleaning.
- Runs in seconds on any dataset size.

### L1P1 (statistical), work in progress

Implements the unsupervised permutation test from:

> Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised detection of bots in a Likert-type questionnaire. *Behavior Research Methods, 56*(5), 5068–5085. https://doi.org/10.3758/s13428-023-02246-7

- Outputs a p-value per participant; p ≥ 0.05 is flagged at 95% sensitivity (default cutoff 95).
- Uses 200 permutations per participant, with leave-one-out anchor computation.
- Runs in parallel across CPU cores via `joblib`.
- Currently being validated on Oishi Lab survey data.
- Use the Classic method for production data cleaning until L1P1 validation is done.

## Qualitative Analysis Mode

An optional feature on both pages. Requires an Anthropic API key.

- Uses the Claude API to check open-ended text responses for AI-generated content.
- Adds an `ai_text_score` column (0 to 100) to the output, separate from `bot_score`.
- Enter your API key in the sidebar. It is kept in session memory only and never saved to disk.

## Technical notes

- Runs entirely on your machine; no data is uploaded.
- Detects Qualtrics CSVs and strips their header rows automatically.
- Supports 1 to 5 and 1 to 7 Likert scales.
- Tested on datasets with 100 to 200 Likert items and 300 to 500 participants.
- Run it inside the virtual environment to avoid dependency conflicts.

## Getting updates

```bash
cd bot-detector
git pull
pip3 install -r requirements.txt
```

## Citation

If you use L1P1 detection in published work, please cite:

Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised detection of bots in a Likert-type questionnaire. *Behavior Research Methods, 56*(5), 5068–5085. https://doi.org/10.3758/s13428-023-02246-7

Falk, C. F., Huang, A., & Ilagan, M. J. (2025). Unsupervised detection of bots and inattentive respondents in survey data: Current methods and a new framework. *Psychological Methods.* Advance online publication. https://doi.org/10.1037/met0000750
