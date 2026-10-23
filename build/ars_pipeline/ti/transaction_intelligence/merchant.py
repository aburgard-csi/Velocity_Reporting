# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/merchant.py at a491b5c (James Gilmore); logic unchanged.
"""Merchant extraction from the raw transaction description.

The file's merchant field is a description, not a name. Observed on 1615:

    card:  XX9704 PURCHASE-RECUR 08/01 06:51 PAYPAL *PYPL PAY SAN JOSE CA 69424885 08010606
           XX1056 PURCHASE-SIG 01/24 13:17 PAYPAL EBAY US SAN JOSE CA 69424885 01240149300
    ACH:   National Grid vi CHECK PYMT 7017
           CHASE CREDIT CRD CHECK PYMT 000000000006182
    1192:  TYPE: MTG PYMTS ID: 16-1146859        (no counterparty name at all;
           the TYPE label IS the information -- the core becomes "MTG PYMTS")

Two passes. `merchant_core` strips the card prefix (mask, type token, date,
time), cuts at the first reference number (6+ digits) and drops a trailing
"CITY ST". `merchant_key` then collapses the remainder to a stable label for
grouping: the first two tokens, with PayPal-style "PAYPAL *NAME" kept as
"PAYPAL NAME" and leading punctuation removed. No hand-curated consolidation
list; the key is derived, so it is the same for every client.
"""

from __future__ import annotations

import re

import pandas as pd

_CARD_PREFIX = re.compile(
    r"^\s*XX\d{3,6}\s+[A-Z]+(?:-[A-Z]+)?\s+\d{2}/\d{2}\s+\d{2}:\d{2}\s+", re.I)
# 1192-style scaffolding: "TYPE: {label} ID: {ref}" -> keep the label.
_TYPE_ID = re.compile(r"^\s*TYPE:\s*(.*?)\s*ID:.*$", re.I)
_REF_TAIL = re.compile(r"\s+\d{6,}.*$")                 # first long reference number onward
# "... SAN JOSE CA" / "... HYANNIS MA" / "... AMZN.COM/BILL WA": a one- or
# two-word city followed by a two-letter state, at the end.
#
# Two guards, both from 1776 (#261). A word that names a depository is part
# of the institution's name, never a city: "SESLOC FCU ATASCADERO CA" lost
# FCU to the two-word branch and came out as "SESLOC", which no pattern can
# claim. And CU, BK, NA are the end of a name, not a state: "STAR ONE CU"
# came out as "STAR".
_DEPOSITORY_WORD = (r"(?!(?:BANK|BK|CU|FCU|CREDIT|UNION|FEDERAL|FED|TRUST|FIN|"
                    r"FINANCIAL|SAVINGS|INS|INSURANCE|NA)\b)")
_CITY_STATE = re.compile(
    r"\s+" + _DEPOSITORY_WORD + r"[A-Z][A-Z.'/-]*"
    r"(?:\s+" + _DEPOSITORY_WORD + r"[A-Z][A-Z.'/-]*)?"
    r"\s+(?!(?:CU|BK|NA)\s*$)[A-Z]{2}\s*$")
_PAYPAL = re.compile(r"^(PAYPAL|PP|SQ|SQUARE|TST|DD|DOORDASH)\s*\*\s*", re.I)
_PUNCT = re.compile(r"[^A-Z0-9&' ]+")
_SPACES = re.compile(r"\s+")
_TRAILING_DIGITS = re.compile(r"\s+\d{4,}\s*$")


def merchant_text(desc: pd.Series) -> pd.Series:
    """The description with the card scaffolding removed and nothing else:
    prefix, reference tail and trailing digits gone, upper-cased, the city
    and state still there. This is what the institution and product
    matchers run on. A cleaner cannot know where a name ends and a city
    begins; a token regex over the whole text does not need to (#261)."""
    s = desc.fillna("").astype(str).str.strip()
    s = s.str.replace(_TYPE_ID, r"\1", regex=True)
    s = s.str.replace(_CARD_PREFIX, "", regex=True)
    s = s.str.replace(_REF_TAIL, "", regex=True)
    s = s.str.replace(_TRAILING_DIGITS, "", regex=True)
    return s.str.upper().str.replace(_SPACES, " ", regex=True).str.strip()


def merchant_core(desc: pd.Series) -> pd.Series:
    """merchant_text with the trailing "CITY ST" dropped: the grouping label
    for merchant tables and review queues, not the matching text."""
    s = merchant_text(desc)
    s = s.str.replace(_CITY_STATE, "", regex=True)
    s = s.str.replace(_TRAILING_DIGITS, "", regex=True)
    return s.str.strip()


def strip_city(text: str) -> str:
    """One string, the same "CITY ST" rule as merchant_core."""
    return _TRAILING_DIGITS.sub("", _CITY_STATE.sub("", text)).strip()


_NOISE_TOKENS = {"THE", "&", "AND", "OF", "INC", "LLC", "CO", "CORP", "POS", "WWW"}
NO_DESCRIPTION = "(no description)"


def _two_tokens(text: str) -> str:
    """First two informative tokens: no store numbers, no 'THE', no '&'."""
    kept = []
    for tok in text.split(" "):
        if not tok or tok in _NOISE_TOKENS or tok.isdigit():
            continue
        # drop store-number suffixes glued to a word: "SHAWS1598" stays, "#2671" went with punctuation
        kept.append(tok)
        if len(kept) == 2:
            break
    return " ".join(kept) if kept else NO_DESCRIPTION


def merchant_key(desc: pd.Series) -> pd.Series:
    core = merchant_core(desc)
    core = core.str.replace(_PAYPAL, lambda m: m.group(1).upper() + " ", regex=True)
    core = core.str.replace(_PUNCT, " ", regex=True).str.replace(_SPACES, " ", regex=True).str.strip()
    # Map over the distinct values only: a 5M-row file has ~130k distinct cores.
    lookup = {v: _two_tokens(v) for v in core.unique()}
    return core.map(lookup)
