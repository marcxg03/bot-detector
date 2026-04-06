import pandas as pd
import numpy as np
import anthropic
import json

import utils


SYSTEM_PROMPT = """
You are a research assistant helping detect AI-generated text in
survey responses. You will be given a numbered list of survey
responses. For each response, output a single integer from 0 to 100
representing the likelihood that the response was written by an AI
rather than a human participant.

Scoring guide:
0   = Clearly human-written (personal, specific, informal, emotional)
25  = Probably human (some generic phrasing but feels authentic)
50  = Uncertain (could be either)
75  = Probably AI-generated (generic, polished, impersonal)
100 = Clearly AI-generated (formulaic, explicitly identifies as AI,
      or uses corporate/academic boilerplate with no personal detail)

Respond ONLY with a valid JSON array of integers, one per response,
in the same order as the input. Do not include any explanation,
preamble, or text outside the JSON array.

Example input:
1. I really struggled with the food at first but eventually loved it
2. Study abroad programs offer invaluable cross-cultural experiences

Example output:
[5, 82]
"""


def run_qualitative(df: pd.DataFrame, api_key: str) -> pd.DataFrame:
    """Analyze open-ended text columns for AI-generated content using the
    Claude API. Returns df copy with ai_text_score column appended."""
    client = anthropic.Anthropic(api_key=api_key)
    text_cols = utils.get_text_columns(df)

    if len(text_cols) == 0:
        result = df.copy()
        result["ai_text_score"] = 0
        return result

    all_col_scores = []

    for col in text_cols:
        responses = df[col].fillna("").astype(str).tolist()
        col_scores = []
        batch_size = 20

        for i in range(0, len(responses), batch_size):
            batch = responses[i : i + batch_size]
            numbered = "\n".join(f"{j + 1}. {resp}" for j, resp in enumerate(batch))
            user_prompt = (
                "Score each of the following survey responses for likelihood "
                "of being AI-generated:\n\n" + numbered
            )
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                raw = response.content[0].text.strip()
                scores = json.loads(raw)
                if not isinstance(scores, list) or len(scores) != len(batch):
                    raise ValueError("Unexpected response format")
                scores = [int(max(0, min(100, s))) for s in scores]
            except anthropic.AuthenticationError:
                raise
            except Exception:
                scores = [50] * len(batch)
            col_scores.extend(scores)

        all_col_scores.append(col_scores)

    scores_matrix = np.array(all_col_scores)
    avg_scores = scores_matrix.mean(axis=0)
    ai_text_scores = [int(round(s)) for s in avg_scores]

    result = df.copy()
    result["ai_text_score"] = ai_text_scores
    return result
