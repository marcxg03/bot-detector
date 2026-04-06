import pandas as pd


def run_detection(df, cutoff: int) -> pd.DataFrame:
    """Run the quantitative bot-detection pipeline on a survey DataFrame."""
    pass


def check_straight_lining(df, likert_cols) -> dict:
    """Check for respondents who give the same Likert response repeatedly."""
    pass


def check_low_variance(df, likert_cols) -> dict:
    """Check for respondents whose Likert responses show unusually low variance."""
    pass


def check_range_avoidance(df, likert_cols) -> dict:
    """Check for respondents who avoid using the full available Likert range."""
    pass


def check_extreme_responding(df, likert_cols) -> dict:
    """Check for respondents who overuse extreme Likert responses."""
    pass


def check_speeder(df) -> dict:
    """Check for respondents who appear to have completed the survey too quickly."""
    pass


def check_duplicate_patterns(df, likert_cols) -> dict:
    """Check for respondents who share duplicate Likert response patterns."""
    pass


def check_missing_patterns(df, likert_cols) -> dict:
    """Check for respondents with suspiciously patterned missing Likert data."""
    pass
