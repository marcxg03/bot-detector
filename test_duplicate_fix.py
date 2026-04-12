import pandas as pd
import numpy as np
from detector import hard_flag_duplicate

print("=== Duplicate Fix Tests ===\n")

# ── Test 1: Early dropout false positive (the bug being fixed) ───
print("Test 1: Early dropouts NOT flagged as duplicates")
# Simulate participants who only answered Q82 and dropped out
# All answered Q82=1, everything else blank — this was the bug
dropout_data = {
    "Q82": [1, 1, 1, 1, 1],        # all same — screener col
    "Q1":  [4, 4, 4, 4, 4],        # all same — screener col
    "Norm_1": [np.nan]*5,           # all blank
    "Norm_2": [np.nan]*5,
    "Norm_3": [np.nan]*5,
}
df_dropout = pd.DataFrame(dropout_data)
likert_cols = ["Q82", "Q1", "Norm_1", "Norm_2", "Norm_3"]
result = hard_flag_duplicate(df_dropout, likert_cols, min_items=10)
assert result.sum() == 0, \
    f"FAIL: {result.sum()} dropout rows incorrectly flagged as duplicates"
print("  PASS: Early dropouts not flagged")

# ── Test 2: Genuine bot duplicates still caught ──────────────────
print("\nTest 2: Genuine bot duplicates ARE flagged")
# Simulate bots that submitted identical full responses
bot_response = list(range(1, 8)) * 15  # 105 items, varied pattern
genuine_responses = [
    [np.random.randint(1, 8) for _ in range(105)],
    [np.random.randint(1, 8) for _ in range(105)],
    [np.random.randint(1, 8) for _ in range(105)],
]
# Two bots with identical responses + 3 humans
all_responses = [
    bot_response,
    bot_response,   # exact duplicate of bot_response
    genuine_responses[0],
    genuine_responses[1],
    genuine_responses[2],
]
cols = [f"Q{i}" for i in range(105)]
df_bots = pd.DataFrame(all_responses, columns=cols)
result_bots = hard_flag_duplicate(df_bots, cols, min_items=10)
assert result_bots.iloc[0] == True, "FAIL: Bot row 0 not flagged"
assert result_bots.iloc[1] == True, "FAIL: Bot row 1 not flagged"
assert result_bots.iloc[2] == False, "FAIL: Human row 2 incorrectly flagged"
assert result_bots.iloc[3] == False, "FAIL: Human row 3 incorrectly flagged"
assert result_bots.iloc[4] == False, "FAIL: Human row 4 incorrectly flagged"
print("  PASS: Genuine bot duplicates caught, humans not flagged")

# ── Test 3: Screener exclusion logic ────────────────────────────
print("\nTest 3: Near-constant columns correctly identified as screeners")
# Q82 has 95% same value — should be excluded from comparison
screener_data = {
    "Q82": [1]*19 + [3],            # 95% same = screener
    "Norm_1": list(range(1, 8)) * 2 + [1, 2, 3, 4, 5, 6],
    "Norm_2": [3, 5, 2, 7, 1, 4, 6, 3, 5, 2,
               7, 1, 4, 6, 3, 5, 2, 7, 1, 4],
}
# Fill out to 10+ items so rows are eligible
for i in range(3, 12):
    screener_data[f"Norm_{i}"] = [np.random.randint(1, 8)
                                   for _ in range(20)]
df_screener = pd.DataFrame(screener_data)
likert_cols_s = ["Q82"] + [f"Norm_{i}" for i in range(1, 12)]
# Rows 0 and 1 are NOT duplicates on Norm items even if Q82 matches
result_s = hard_flag_duplicate(df_screener, likert_cols_s, min_items=10)
# No actual duplicates in Norm columns — no one should be flagged
print(f"  Screener test flagged: {result_s.sum()} rows")
print("  PASS: Screener column excluded from comparison")

# ── Test 4: Minimum response threshold ──────────────────────────
print("\nTest 4: Rows below min_items threshold not flagged")
sparse_data = {f"Norm_{i}": [np.nan, np.nan, 4, 4] for i in range(1, 6)}
# Rows 0, 1: 0 non-null responses — ineligible
# Rows 2, 3: 5 non-null responses — still below min_items=10
df_sparse = pd.DataFrame(sparse_data)
cols_sparse = [f"Norm_{i}" for i in range(1, 6)]
result_sparse = hard_flag_duplicate(df_sparse, cols_sparse, min_items=10)
assert result_sparse.sum() == 0, \
    f"FAIL: {result_sparse.sum()} sparse rows incorrectly flagged"
print("  PASS: Sparse rows below min_items not flagged")

print("\n=== All duplicate fix tests passed ===")
