import pandas as pd
import numpy as np
from detector import run_detection_heuristic

print("=== Optional Checks Tests ===\n")

np.random.seed(42)
n_items = 20
cols = [f"Q{i}" for i in range(n_items)]

# Build a dataset with known properties:
# Row 0: low variance (all 4s) — should only be flagged when
#         use_low_variance=True
# Row 1: high missing data (>50% blank) — should only be flagged
#         when use_missing_data=True
# Rows 2-19: normal varied responses — should not be flagged
#             by these two checks

data = []

# Row 0: low variance — all 4s (SD=0, definitely bottom 10th pct)
data.append([4] * n_items)

# Row 1: missing data — only first 5 items answered, rest blank
row1 = [np.nan] * n_items
for i in range(5):
    row1[i] = np.random.randint(1, 8)
data.append(row1)

# Rows 2-19: normal human-like responses
for _ in range(18):
    row = np.random.choice(
        [1, 2, 3, 4, 5, 6, 7], size=n_items,
        p=[0.05, 0.10, 0.20, 0.30, 0.20, 0.10, 0.05]
    )
    data.append(row)

df_test = pd.DataFrame(data, columns=cols)

# ── Test 1: Both checks ON (default) ─────────────────────────────
print("Test 1: Both optional checks ON (default behavior)")
result_both_on = run_detection_heuristic(
    df_test, cutoff=75,
    use_low_variance=True,
    use_missing_data=True
)
row0_flags = result_both_on.loc[0, "bot_flags"]
row1_flags = result_both_on.loc[1, "bot_flags"]
assert "low_variance" in row0_flags, \
    f"FAIL: low_variance not in row 0 flags: {row0_flags}"
assert "missing_data" in row1_flags, \
    f"FAIL: missing_data not in row 1 flags: {row1_flags}"
print(f"  Row 0 flags: {row0_flags}")
print(f"  Row 1 flags: {row1_flags}")
print("  PASS: Both checks fire when enabled")

# ── Test 2: low_variance OFF ──────────────────────────────────────
print("\nTest 2: low_variance=False — no low_variance flags")
result_lv_off = run_detection_heuristic(
    df_test, cutoff=75,
    use_low_variance=False,
    use_missing_data=True
)
all_flags_lv_off = " ".join(
    result_lv_off["bot_flags"].fillna("").tolist()
)
assert "low_variance" not in all_flags_lv_off, \
    "FAIL: low_variance flag appeared when use_low_variance=False"
# missing_data should still work
assert "missing_data" in result_lv_off.loc[1, "bot_flags"], \
    "FAIL: missing_data stopped working when low_variance disabled"
print("  PASS: low_variance absent when disabled")
print("  PASS: missing_data still works independently")

# ── Test 3: missing_data OFF ──────────────────────────────────────
print("\nTest 3: use_missing_data=False — no missing_data flags")
result_md_off = run_detection_heuristic(
    df_test, cutoff=75,
    use_low_variance=True,
    use_missing_data=False
)
all_flags_md_off = " ".join(
    result_md_off["bot_flags"].fillna("").tolist()
)
assert "missing_data" not in all_flags_md_off, \
    "FAIL: missing_data flag appeared when use_missing_data=False"
# low_variance should still work
assert "low_variance" in result_md_off.loc[0, "bot_flags"], \
    "FAIL: low_variance stopped working when missing_data disabled"
print("  PASS: missing_data absent when disabled")
print("  PASS: low_variance still works independently")

# ── Test 4: Both checks OFF ───────────────────────────────────────
print("\nTest 4: Both optional checks OFF")
result_both_off = run_detection_heuristic(
    df_test, cutoff=75,
    use_low_variance=False,
    use_missing_data=False
)
all_flags_both_off = " ".join(
    result_both_off["bot_flags"].fillna("").tolist()
)
assert "low_variance" not in all_flags_both_off, \
    "FAIL: low_variance appeared when both disabled"
assert "missing_data" not in all_flags_both_off, \
    "FAIL: missing_data appeared when both disabled"
# Row 0 (all 4s) — low_variance must be absent from its flags even
# though it may still be flagged by other checks (longstring_absolute
# fires because all 4s = 100% same value, which is correct behavior)
row0_flags_off = result_both_off.loc[0, "bot_flags"]
assert "low_variance" not in row0_flags_off, \
    f"FAIL: low_variance in row 0 flags when both optional checks off: " \
    f"{row0_flags_off}"
assert "missing_data" not in result_both_off.loc[1, "bot_flags"], \
    f"FAIL: missing_data in row 1 flags when both optional checks off: " \
    f"{result_both_off.loc[1, 'bot_flags']}"
print("  PASS: Neither flag appears when both disabled")
print(f"  (Row 0 may still be flagged by other checks: {row0_flags_off})")

# ── Test 5: Output columns always present ─────────────────────────
print("\nTest 5: Output columns always present regardless of settings")
for lv, md in [(True, True), (True, False),
               (False, True), (False, False)]:
    r = run_detection_heuristic(
        df_test, cutoff=75,
        use_low_variance=lv,
        use_missing_data=md
    )
    for col in ["bot_score", "bot_flags", "is_flagged",
                "eligibility_flag"]:
        assert col in r.columns, \
            f"FAIL: {col} missing when lv={lv}, md={md}"
print("  PASS: All output columns present in all configurations")

print("\n=== All optional checks tests passed ===")
