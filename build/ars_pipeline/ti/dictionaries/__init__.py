"""
The reference dictionaries the transaction analyses classify against, copied from ARS v5
`0_Config/` at a491b5c (James Gilmore):

  competitors.json                  ~100 institutions in seven tiers, the payment ecosystems,
                                    BNPL providers, false positives and review tokens
  financial_services_patterns.json  the financial-service categories (loans, cards, brokerage,
                                    P2P, fintech, …) as description patterns
  merchant_categories.json          MCC groups and keyword buckets for card spend

They carry public institution and merchant names, nothing about any client, so they live in the
repo beside the code that reads them. Client-specific names (a client's local competitors and its
own names) come from the client config (`ti/config.py`), never from here.

v5's loaders take the FOLDER that holds these files (`config_dir`); `folder()` is that folder.
"""
from pathlib import Path

FILES = ("competitors.json", "financial_services_patterns.json", "merchant_categories.json")


def folder() -> Path:
    return Path(__file__).resolve().parent
