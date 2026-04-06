import pandas as pd
import numpy as np
from detector import run_detection

df = pd.read_csv("test_survey.csv")
result = run_detection(df, cutoff=75)

print("\n--- Scores and Flags ---")
for _, row in result.iterrows():
    status = "🔴 FLAGGED" if row["is_flagged"] else "🟢 clean"
    print(f"{row['ResponseId']}: score={row['bot_score']:3d} | "
          f"flags={str(row['bot_flags']):<50} | {status}")

known_bots   = ["R003", "R005", "R007", "R009", "R011", "R013"]
known_humans = ["R001", "R002", "R004", "R006",
                "R008", "R010", "R012", "R014", "R015"]

print("\n--- Bot Assertions ---")
for bot_id in known_bots:
    row = result[result["ResponseId"] == bot_id].iloc[0]
    assert row["is_flagged"] == True, \
        f"FAIL: {bot_id} should be flagged (score={row['bot_score']})"
    print(f"PASS: {bot_id} flagged (score={row['bot_score']})")

print("\n--- Human Assertions ---")
for human_id in known_humans:
    row = result[result["ResponseId"] == human_id].iloc[0]
    assert row["is_flagged"] == False, \
        f"FAIL: {human_id} should be clean (score={row['bot_score']})"
    # Check no spurious entropy or mahalanobis labels
    flags = str(row["bot_flags"])
    assert "entropy" not in flags, \
        f"FAIL: {human_id} has spurious entropy flag (score={row['bot_score']})"
    assert "mahalanobis" not in flags, \
        f"FAIL: {human_id} has spurious mahalanobis flag (score={row['bot_score']})"
    print(f"PASS: {human_id} clean, no spurious flags (score={row['bot_score']})")

print("\nAll Slice 2C assertions passed.")
