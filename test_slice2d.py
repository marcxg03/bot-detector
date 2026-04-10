import pandas as pd
import numpy as np
import time
from detector import run_detection

print("=== Slice 2D Tests: L1P1 Engine (Optimized) ===\n")

# ── Test 1: Output columns and types ─────────────────────────────────────────
print("Test 1: Output structure")
np.random.seed(42)
n_items = 20
cols = [f"Q{i}" for i in range(n_items)]

human_rows = np.random.choice([1,2,3,4,5,6,7], size=(30, n_items),
                               p=[0.05,0.1,0.2,0.3,0.2,0.1,0.05])
bot_rows = np.random.randint(1, 8, size=(10, n_items))
data = np.vstack([human_rows, bot_rows])
labels = ["human"]*30 + ["bot"]*10

df_test = pd.DataFrame(data, columns=cols)
df_test["true_label"] = labels
result = run_detection(df_test, cutoff=95)

assert "bot_score" in result.columns, "bot_score column missing"
assert "l1p1_pvalue" in result.columns, "l1p1_pvalue column missing"
assert "is_flagged" in result.columns, "is_flagged column missing"
assert "bot_flags" in result.columns, "bot_flags column missing"
assert result["bot_score"].dtype in [int, "int64", "int32"], "bot_score should be int"
assert result["bot_score"].between(0, 100).all(), "bot_score out of range"
assert result["l1p1_pvalue"].between(0.0, 1.0).all(), "p-values out of range"
print("  PASS: All output columns present with correct types")

# ── Test 2: Bot detection rate — sensitivity AND specificity ──────────────────
print("\nTest 2: Bot detection rate (sensitivity + specificity)")
np.random.seed(42)
n_items = 20
n_humans = 50   # more humans for stable specificity estimate
n_bots = 20
cols = [f"Q{i}" for i in range(n_items)]

# Structured humans: simulate latent trait + item loadings + noise
# Each participant has a latent score theta drawn from N(0,1)
# Each item has a loading of ~0.7, so responses are correlated
# Final response = round(4 + 1.5*theta + noise) clipped to 1-7
# This produces the inter-item correlation structure L1P1 needs

theta = np.random.normal(0, 1, n_humans)          # latent scores
loadings = np.random.uniform(0.5, 0.9, n_items)   # item loadings
human_data = np.zeros((n_humans, n_items))
for i in range(n_humans):
    for j in range(n_items):
        signal = 4 + 1.5 * loadings[j] * theta[i]
        noise = np.random.normal(0, 0.5)
        human_data[i, j] = np.clip(round(signal + noise), 1, 7)

# Random bots: independent uniform draws — no factor structure
# (exchangeable by design — exactly what L1P1 targets)
bot_data = np.random.randint(1, 8, size=(n_bots, n_items)).astype(float)

data = np.vstack([human_data, bot_data])
labels = ["human"] * n_humans + ["bot"] * n_bots
df_test2 = pd.DataFrame(data, columns=cols)
df_test2["true_label"] = labels

# Run at cutoff=95 (alpha=0.05, paper default)
result2 = run_detection(df_test2, cutoff=95)

assert "bot_score" in result2.columns
assert result2["bot_score"].between(0, 100).all()
assert result2["l1p1_pvalue"].between(0.0, 1.0).all()

# Print distribution for diagnostics
bot_pvals = result2[result2["true_label"]=="bot"]["l1p1_pvalue"].values
human_pvals = result2[result2["true_label"]=="human"]["l1p1_pvalue"].values
print(f"  Bot p-values:   mean={bot_pvals.mean():.3f}, "
      f"min={bot_pvals.min():.3f}, max={bot_pvals.max():.3f}")
print(f"  Human p-values: mean={human_pvals.mean():.3f}, "
      f"min={human_pvals.min():.3f}, max={human_pvals.max():.3f}")

# Sensitivity: >= 80% of bots flagged
# (paper guarantees 95% on real data; synthetic may be slightly lower
# due to small sample — 80% is a reasonable lower bound for 20 bots)
bot_results2 = result2[result2["true_label"] == "bot"]
flagged_bots2 = bot_results2["is_flagged"].sum()
sensitivity = flagged_bots2 / n_bots
print(f"  Bots flagged: {flagged_bots2}/{n_bots} ({sensitivity*100:.0f}%)")
assert sensitivity >= 0.80, \
    f"FAIL sensitivity: only {flagged_bots2}/{n_bots} bots flagged"
print("  PASS sensitivity")

# Specificity: <= 30% of humans incorrectly flagged
# L1P1 with alpha=0.05 should have ~5% false positive rate on
# well-structured human data; 30% gives generous margin for small n
human_results2 = result2[result2["true_label"] == "human"]
false_positives2 = human_results2["is_flagged"].sum()
fpr = false_positives2 / n_humans
print(f"  Humans incorrectly flagged: {false_positives2}/{n_humans} ({fpr*100:.0f}%)")
assert fpr <= 0.30, \
    f"FAIL specificity: {false_positives2}/{n_humans} humans incorrectly flagged " \
    f"({fpr*100:.0f}% > 30% threshold)"
print("  PASS specificity")

# Directional check: bots should have HIGHER p-values than humans on average
# (L1P1: high p-value = looks random = bot-like)
assert bot_pvals.mean() > human_pvals.mean(), \
    f"FAIL directionality: bot mean p ({bot_pvals.mean():.3f}) should exceed " \
    f"human mean p ({human_pvals.mean():.3f})"
print("  PASS directionality: bots have higher mean p-value than humans")

# ── Test 3: Hard flag — longstring ────────────────────────────────────────────
print("\nTest 3: Longstring hard flag")
df_ls = pd.DataFrame({f"Q{i}": [3]*10 for i in range(10)})
df_ls2 = pd.DataFrame({f"Q{i}": [4,2,5,1,6,3,4,2,5,1] for i in range(10)})
df_hard = pd.concat([df_ls, df_ls2], ignore_index=True)
result_hard = run_detection(df_hard, cutoff=95)
assert result_hard.loc[0, "is_flagged"] == True, "All-3s row should be flagged"
assert "longstring" in result_hard.loc[0, "bot_flags"], "longstring label missing"
assert result_hard.loc[0, "l1p1_pvalue"] == 0.0, "Hard-flagged p-value should be 0.0"
print("  PASS: Longstring hard flag works")

# ── Test 4: Hard flag — exact duplicate ───────────────────────────────────────
print("\nTest 4: Duplicate hard flag")
row_data = {f"Q{i}": [3,5,2,4,1,6,3,5,2,4][i] for i in range(10)}
df_dup = pd.DataFrame([row_data, row_data, row_data])
result_dup = run_detection(df_dup, cutoff=95)
assert result_dup["is_flagged"].all(), "All duplicate rows should be flagged"
assert all("exact_duplicate" in f for f in result_dup["bot_flags"]), \
    "exact_duplicate label missing"
print("  PASS: Duplicate hard flag works")

# ── Test 5: Score-pvalue mapping consistency ──────────────────────────────────
print("\nTest 5: Score-pvalue mapping")
result_map = run_detection(pd.DataFrame(
    {f"Q{i}": np.random.choice(range(1,8), 15) for i in range(12)}
), cutoff=95)
for _, row in result_map.iterrows():
    if row["bot_score"] != 100:  # skip hard-flagged
        expected = int(round((1 - row["l1p1_pvalue"]) * 100))
        assert abs(row["bot_score"] - expected) <= 1, \
            f"Mapping error: score={row['bot_score']}, pval={row['l1p1_pvalue']:.3f}"
print("  PASS: bot_score correctly maps from l1p1_pvalue")

# ── Test 6: Real Oishi Lab datasets with timing ───────────────────────────────
print("\nTest 6: Real Oishi Lab datasets")
datasets = [
    ('/mnt/user-data/uploads/FE2a_-_Survey_validation_March_25__2026_22_50.csv',
     'FE2a', 350, 50),
    ('/mnt/user-data/uploads/26__March_29__2026_17_43.csv',
     'Dataset26', 422, 50),
]
for fpath, label, expected_n, min_likert in datasets:
    try:
        df_real = pd.read_csv(fpath, skiprows=[1, 2], low_memory=False)
        print(f"\n  {label}: {len(df_real)} participants")

        t0 = time.time()
        result_real = run_detection(df_real, cutoff=95)
        elapsed = time.time() - t0

        assert "bot_score" in result_real.columns
        assert "l1p1_pvalue" in result_real.columns
        assert result_real["bot_score"].between(0, 100).all()
        assert result_real["l1p1_pvalue"].between(0.0, 1.0).all()

        n_flagged = result_real["is_flagged"].sum()
        n_hard = (result_real["bot_score"] == 100).sum()
        pct = n_flagged / len(result_real) * 100

        print(f"  Runtime: {elapsed:.1f}s")
        print(f"  Flagged: {n_flagged}/{len(result_real)} ({pct:.1f}%)")
        print(f"  Hard-flagged (score=100): {n_hard}")
        print(f"  Mean p-value: {result_real['l1p1_pvalue'].mean():.3f}")
        print(f"  Flagged p-values: {result_real[result_real['is_flagged']]['l1p1_pvalue'].describe().to_dict()}")

        assert elapsed < 300, f"Too slow: {elapsed:.0f}s (limit 300s)"
        print(f"  PASS: {label} processed correctly in {elapsed:.1f}s")
    except FileNotFoundError:
        print(f"  SKIP: {label} file not found")

print("\n=== All Slice 2D tests passed ===")
