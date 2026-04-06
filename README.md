# Survey Bot Detector

Survey Bot Detector is a local Streamlit app for the Oishi Lab that helps identify likely bot-generated survey responses in CSV datasets using quantitative survey-pattern checks and optional AI-assisted qualitative text review.

## Prerequisites

- Python 3.9+
- pip3

## Installation

```bash
git clone <repository-url>
cd bot_detector
pip3 install -r requirements.txt
```

## Launch

```bash
python3 -m streamlit run app.py
```

## Notes

- An API key is only needed for qualitative mode.
