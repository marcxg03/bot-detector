# Survey Bot Detector — Handover Document

**Oishi Lab | University of Chicago**
Prepared by: Marcus Gao
Last updated: 2026-04-12

---

## 1. What This Tool Does

The tool is a local Streamlit web application that detects and flags bot-like or low-quality responses in Qualtrics survey CSV exports. It was built for the Oishi Lab to support data cleaning before analysis. It runs entirely on the researcher's local machine — no data is uploaded to any server.

The tool has two pages. The General Bot Detection page works on any survey CSV. The Freedom of Expression Study page is pre-configured for the FE study instrument and automatically detects whether the upload is Wave 1 (FE2a) or Wave 2 (FE2b). Both pages support two detection methods: Classic Heuristic (fast, rule-based) and L1P1 Statistical (peer-reviewed algorithm, currently work-in-progress).

---

## 2. Project Information

| Field | Details |
|---|---|
| GitHub repository | https://github.com/marcxg03/bot-detector |
| Primary developer | Marcus Gao (GitHub: marcxg03) |
| Contact | marcusgao@uchicago.edu |
| Lab | Oishi Lab, University of Chicago |
| Built with | Python 3.9+, Streamlit, pandas, numpy, joblib |
| Last major update | 2026-04-12 |

---

## 3. File Map

| File / Folder | What it does | Edit if you want to... |
|---|---|---|
| app.py | General Bot Detection page — the main page users see first | Change the general page UI, sidebar settings, or step layout |
| pages/FE_Study.py | Freedom of Expression Study page — pre-configured for FE instrument | Change FE-specific UI, wave detection, or eligibility rules |
| detector.py | All detection logic — both heuristic and L1P1 engines | Change what gets flagged, how flags are computed, or add new checks |
| utils.py | Likert column detection — decides which columns are survey items | Change which columns are treated as Likert scale items |
| qualitative.py | AI text analysis mode — uses Claude API to assess open-ended responses | Change how open-ended text is analyzed |
| requirements.txt | Python package dependencies | Add or remove Python packages |
| README.md | User-facing documentation — setup instructions and feature overview | Update when features change or setup steps change |
| HANDOVER.md | This file | Update when the codebase changes significantly |
| CHANGELOG.md | Running log of every feature and fix, newest first | Read to understand what changed and why |
| KNOWN_ISSUES.md | Running log of known limitations and follow-up items | Read before making changes — check if the issue is already noted |
| DECISIONS.md | Design decisions and rationale log | Read if you want to understand why something was built a certain way |
| pages/ | Folder containing additional Streamlit pages | Add new pages here — Streamlit auto-detects them |
| test_duplicate_fix.py | Regression tests for the exact_duplicate fix | Run after editing hard_flag_duplicate() to confirm it still works |
| test_slice2d.py | Regression tests for the L1P1 detection engine | Run after editing run_detection() to confirm it still works |
| test_survey.csv | Synthetic test dataset with known bot and human rows | Use for manual testing — 15 rows, 6 bots, 9 humans |
| Bot_Detection_Literature_Review.docx | Literature review document | Reference when evaluating detection methodology |
| Survey_Bot_Detector_User_Manual.docx | Extended user manual | Reference for end-user guidance beyond the README |
| Slices/ | Development planning documents organized by feature slice | Historical reference — not needed for day-to-day use |
| Specs/ | Formal feature specifications used during development | Historical reference — not needed for day-to-day use |
| Test Cases/ | Manual test case documents | Reference when verifying features after changes |
| venv/ | Python virtual environment — do not edit | Never edit — recreate with setup instructions below if broken |

---

## 4. How to Run the Tool

### First time setup

```bash
git clone https://github.com/marcxg03/bot-detector.git
cd bot-detector
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### Every subsequent time

```bash
cd bot-detector
source venv/bin/activate
python3 -m streamlit run app.py
```

Then open http://localhost:8501 in your browser.
Keep the terminal window open while using the tool.
Press Ctrl+C in the terminal to stop.

### If something breaks on startup

Most startup errors are caused by running the wrong Python.
Always activate the virtual environment first:

```bash
source venv/bin/activate
which python3   # should point inside your venv folder
```

---

## 5. How Each Detection Check Works

### 5.1 Classic Heuristic Method

**Hard flags — any single occurrence marks the participant as flagged:**

- **longstring_absolute**: Participant gave the same answer to more than 90% of all substantive Likert items. The strongest single bot signal — genuine humans almost never do this on a long survey. (Johnson, 2005)

- **exact_duplicate**: Participant's complete Likert response pattern is identical to at least one other participant, AND they answered at least 10 substantive items (screener-only responses like Q82 are excluded from this check). Consistent with bots running the same script. (Meade & Craig, 2012; Chmielewski & Kucker, 2020)

**Soft flags — any single occurrence also marks the participant as flagged. bot_score shows how many fired:**

- **speeder**: Completed the survey in under the threshold (default 120 seconds, adjustable in sidebar). A survey with 100+ questions cannot be read and answered genuinely that quickly. (Greszki et al., 2015)

- **low_variance** (optional — off by default recommended): Response standard deviation falls in the bottom 10th percentile of all participants. Warns of non-engagement with item content. ⚠️ This threshold is relative — it always flags approximately 10% of respondents. Review flagged cases manually before excluding. (Marjanovic et al., 2015)

- **longstring_run**: Same answer given consecutively on more than 50% of items in a row — consistent with holding down a key or automated responding. (Johnson, 2005)

- **range_avoidance**: Participant used only 1–2 unique values across all items on a 1–7 scale. Humans typically use most of the scale range. (Ward & Meade, 2023)

- **extreme_responding**: More than 80% of responses are at the scale endpoints (only 1s and 7s). A documented pattern of careless or automated responding. (Meade & Craig, 2012)

- **missing_data** (optional): More than 50% of Likert items left blank. ⚠️ Can capture legitimate early dropouts rather than bots — review manually before excluding. (Meade & Craig, 2012)

**Eligibility flag (separate from bot detection):**

- **ineligible_no_group**: Participant answered Q82 = 3 (could not think of a qualifying intellectual group). Not a bot signal — these participants are excluded for eligibility reasons and shown in a separate tab.

### 5.2 L1P1 Statistical Method (Work in Progress)

The L1P1 algorithm (Ilagan & Falk, 2024) is an unsupervised permutation test. For each participant, it randomly shuffles their responses 200 times to generate synthetic "bot-like" patterns and tests whether the participant's actual response pattern is statistically distinguishable from random responding. If it is not — meaning their responses look as random as a shuffle — they are flagged. The algorithm uses leave-one-out anchor computation to ensure each participant is tested against the rest of the sample fairly. It outputs a p-value per participant; participants with p ≥ 0.05 are flagged (95% sensitivity). The algorithm is parallelized across CPU cores via joblib for performance.

**L1P1 is currently work-in-progress and has not yet been validated on FE study data. Use the Classic method for all production data cleaning until L1P1 validation is complete.**

Open-access R implementation: osf.io/e5v3s
R package: github.com/michaeljohnilagan/detranli

---

## 6. How to Adjust Detection Settings (No Code Required)

**Classic Heuristic method — sidebar controls:**

- **Speeder Threshold (seconds):** number input, default 120s. Raise this if your survey is longer and 120s is too short to read. Lower it if your survey is very short.
- **Optional Checks expander (⚙️):** checkboxes for Low Variance and Missing Data. Uncheck to disable either check entirely.

**L1P1 method — sidebar controls:**

- **Suspicion Score Cutoff (0–100):** maps to statistical alpha. Score 95 = alpha 0.05 = 95% sensitivity (paper default). Lower the score to flag fewer participants more conservatively.

---

## 7. How to Adjust Detection Thresholds (Code Required)

Open `detector.py` in any text editor. Find and change these values. Each one is a constant near the top of the relevant function.

| Threshold | Current Value | Where to find it | What changing it does |
|---|---|---|---|
| Longstring absolute | 0.90 (90%) | `run_detection_heuristic()`, check 1 in per-row loop | Lower = flag participants with fewer repeated answers |
| Longstring run | 0.50 (50%) | `run_detection_heuristic()`, check 5 in per-row loop | Lower = flag shorter consecutive runs |
| Speeder default | 120 (seconds) | `run_detection_heuristic()` function signature, `speeder_threshold=120` | Change default — researcher can also override in UI |
| Low variance percentile | 10 (bottom 10%) | `run_detection_heuristic()`, `row_sds.quantile(0.10)` | Lower = flag fewer participants for variance |
| Extreme responding | 0.80 (80%) | `run_detection_heuristic()`, check 7 in per-row loop | Lower = flag less extreme response patterns |
| Missing data | 0.50 (50%) | `run_detection_heuristic()`, check 8 in per-row loop | Lower = flag participants with fewer blank items |
| Duplicate min items | 10 | `hard_flag_duplicate()`, `min_items=10` parameter | Raise = require more responses before flagging as duplicate |
| Screener column threshold | 0.80 (80%) | `hard_flag_duplicate()`, `mode_pct > 0.80` line | Lower = exclude more columns from duplicate comparison |
| L1P1 permutations | 200 | `DEFAULT_B = 200` at top of file | Raise for more replicable p-values (slower) |
| L1P1 default alpha | 0.05 | `DEFAULT_ALPHA = 0.05` at top of file | Change statistical sensitivity threshold |

After changing any value: save the file and restart the app (Ctrl+C in terminal, then `python3 -m streamlit run app.py`).

---

## 8. How to Add a New Detection Check

1. Open `detector.py`. Find `run_detection_heuristic()`.
2. Inside the per-participant loop (the `for i in range(n_rows):` block), add your check logic and append a label string to `flag_parts` if it fires. Example:

```python
# My new check
if some_condition:
    flag_parts.append("my_new_flag (details here)")
```

3. Open `app.py`. Find the flag definitions expander in Step 3. Add a new row to the appropriate table (`hard_flag_data` or `soft_flag_data`) with the flag name, trigger description, meaning, and citation.
4. Do the same in `pages/FE_Study.py` — the expander content must be identical on both pages.
5. Update `README.md` — add the new flag to the Flag Definitions section.
6. Update this `HANDOVER.md` — add the new threshold to the table in Section 7 if applicable.
7. Run the app and test with a real CSV to confirm the new flag fires correctly.

---

## 9. Known Issues and Limitations

| Issue | Severity | Notes |
|---|---|---|
| L1P1 not validated on FE data | 🟡 Medium | Use Classic method for production. L1P1 is available in UI but marked WIP. |
| low_variance uses relative threshold | 🟡 Medium | Always flags ~10% of sample. Made optional — uncheck in sidebar for conservative analysis. |
| missing_data can catch dropouts | 🟡 Medium | Made optional — uncheck if survey has known dropout patterns. |
| Speeder threshold is absolute (120s) | 🟢 Low | Literature recommends relative threshold (Greszki et al., 2015). 120s is researcher-set and adjustable in sidebar. |
| Wave detection uses column names | 🟢 Low | FE Study page detects Wave 1 via "Norm 1 - CP_1" and Wave 2 via "Norm_1". If Qualtrics renames columns, detection will show "Unknown wave". |
| Qualtrics detection uses "ImportId" | 🟢 Low | Auto-detection of Qualtrics header rows relies on "ImportId" string. Older Qualtrics exports may not be auto-detected. |
| L1P1 OSF links not clickable in UI | 🟢 Low | Streamlit dataframes render plain text. Links in the citation expander are not clickable. |
| Falk et al. (2025) DOI unconfirmed | 🟢 Low | Listed as advance online publication. Verify doi:10.1037/met0000746 before citing in manuscript. |
| min_items=10 hardcoded at call site | 🟢 Low | Not yet exposed in UI. Edit detector.py directly to change. |
| _compute_eligibility_flag() hardcodes Q82 | 🟢 Low | Column name Q82 is hardcoded. Would need editing if eligibility criterion changes. |

---

## 10. Key Citations

Johnson, J. A. (2005). Ascertaining the validity of individual protocols from web-based personality inventories. *Journal of Research in Personality, 39*, 103–129.
https://doi.org/10.1016/j.jrp.2004.09.009

Meade, A. W., & Craig, S. B. (2012). Identifying careless responses in survey data. *Psychological Methods, 17*(3), 437–455.
https://doi.org/10.1037/a0028085

Greszki, R., Meyer, M., & Schoen, H. (2015). Exploring the effects of removing "too fast" responses and respondents from web surveys. *Public Opinion Quarterly, 79*(2), 471–503.
https://doi.org/10.1093/poq/nfu058

Marjanovic, Z., Holden, R., Struthers, W., Cribbie, R., & Greenglass, E. (2015). The inter-item standard deviation (ISD): An index that discriminates between conscientious and random responders. *Personality and Individual Differences, 84*, 79–83.
https://doi.org/10.1016/j.paid.2014.08.021

Ward, M. K., & Meade, A. W. (2023). Dealing with careless responding in survey data: Prevention, identification, and recommended best practices. *Annual Review of Psychology, 74*, 577–596.
https://doi.org/10.1146/annurev-psych-040422-045007

Chmielewski, M., & Kucker, S. C. (2020). An MTurk crisis? Shifts in data quality and the impact on study results. *Social Psychological and Personality Science, 11*(4), 464–473.
https://doi.org/10.1177/1948550619875149

Ilagan, M. J., & Falk, C. F. (2024). Model-agnostic unsupervised detection of bots in a Likert-type questionnaire. *Behavior Research Methods, 56*(5), 5068–5085.
https://doi.org/10.3758/s13428-023-02246-7

Falk, C. F., Huang, A., & Ilagan, M. J. (2025). Unsupervised [randomly responding] survey bot detection: In search of high classification accuracy. *Psychological Methods*. Advance online publication.
https://doi.org/10.1037/met0000746

---

## 11. Getting Updates

```bash
cd bot-detector
source venv/bin/activate
git pull
pip3 install -r requirements.txt
```

If there are merge conflicts or the app breaks after pulling, contact Marcus Gao (marcusgao@uchicago.edu).

---

## 12. Contact and Support

| | |
|---|---|
| Developer | Marcus Gao |
| GitHub | github.com/marcxg03 |
| Email | marcusgao@uchicago.edu |
| Repository | https://github.com/marcxg03/bot-detector |

For questions about detection thresholds or methodology, refer to the citations in Section 10 or contact Marcus directly.
