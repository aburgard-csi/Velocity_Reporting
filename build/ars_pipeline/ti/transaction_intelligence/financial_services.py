# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/financial_services.py at a491b5c (James Gilmore); logic unchanged.
"""Financial services: money leaving the institution for someone else's
financial products -- and the adjacent flows that are not leakage but
matter (P2P, fintech wallets).

Detection is name-based against 0_Config/financial_services_patterns.json
(the legacy dictionary, ported as data, plus Online Banks / BNPL / P2P /
Fintech) and an optional per-client LocalFinancialServices block. Matching
runs on the cleaned merchant core over the DISTINCT strings, so a 5M-row
file costs a 130k-string match, once.

Kinds:
    leakage    a competitor financial product (auto loan, mortgage, card, ...)
    adjacency  P2P transfers and fintech wallets -- reported separately,
               never added into leakage dollars, never confused with debit
               spend (a PayPal card purchase stays merchant spend; a PayPal
               transfer over ACH is P2P)

Per account, per category: transactions, dollars, first and last date,
recency tier anchored to the data end, wallet share (category $ over the
account's total ACH+check $). Then: by lens, at-risk x leaking, new accounts
already leaking, leakers' balances and tenure from the ODD, provider
concentration, started / stopped, the unmatched review queue, and per-
category action lists written as CSVs (paths in outputs, never in metrics).
"""

from __future__ import annotations

import json
import re
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from .lens import Lenses
from .merchant import merchant_core, merchant_text

TOP_PROVIDERS = 8
TOP_CATEGORIES_BY_LENS = 8
REVIEW_QUEUE = 25
MIN_MONTHS_FOR_STOPPED = 3
REACHABLE_TIERS = ("active", "cooling")   # last payment within 90 days
MIN_TRANSFER_TXNS_FOR_GAP = 6      # a real transfer habit; conditions the responder gap
BLANK_DESCRIPTION_DECLINE_PCT = 95  # a file this blank names nobody; say so instead of drawing zero


# ---------------------------------------------------------------------------
# dictionary
# ---------------------------------------------------------------------------

def load_patterns(config_dir: Path, client_config: dict | None = None) -> dict:
    spec = json.loads((config_dir / "financial_services_patterns.json").read_text(encoding="utf-8"))
    cats = {name: dict(c) for name, c in spec["categories"].items()}
    local = (client_config or {}).get("LocalFinancialServices") or {}
    for name, pats in local.items():
        entry = cats.setdefault(name, {"kind": "leakage", "addressable": True, "patterns": []})
        entry["patterns"] = sorted(set(entry["patterns"]) | {str(p).upper() for p in pats})
    spec["categories"] = cats
    # The client's own names: internal transfers, never leakage, never queued. Each configured name
    # carries its depository spellings (RPE matching fixes, 2026-11-05): "FirstLight FCU" is also
    # FIRSTLIGHT CU and FIRSTLIGHT FEDERAL CREDIT UNION on a descriptor, the same family the
    # competition side generates for a local competitor.
    configured = [str(n).upper().strip() for n in (client_config or {}).get("SelfNames") or []]
    spec["self_names_configured"] = configured
    self_names = sorted({v for n in configured for v in depository_variants(n)})
    spec["self_names"] = self_names
    if self_names:
        spec["false_positives"] = sorted(set(spec.get("false_positives", [])) | set(self_names))
        spec["review_ignore"] = sorted(set(spec.get("review_ignore", [])) | set(self_names))
    return spec


# Both sides of every match are normalised the same way (#245). ACH and
# bill-pay descriptors abbreviate and glue punctuation to words; the
# dictionary is written out in full. The legacy notebook did this before
# matching and v5 did not carry it across, which is how "PROGRESSIVE
# *INSURANCE" missed a dictionary that holds PROGRESSIVE.
_NA = re.compile(r"\bN\.A\.?(?=\s|$)")
_NON_TOKEN = re.compile(r"[^A-Z0-9 ]+")
_ABBREVIATIONS = [(re.compile(r"\b" + a + r"\b"), b) for a, b in (
    ("FEDERAL CREDIT UNION", "FED CU"), ("CREDIT UNION", "CU"), ("FCU", "FED CU"),
    ("FEDERAL", "FED"), ("FINANCIAL", "FIN"), ("NATIONAL", "NATL"),
    ("BANK", "BK"), ("INSURANCE", "INS"))]
# A token between two pattern words may be a state code or a connector
# ("AAA CA INSURANCE", "BANK OF THE SIERRA"); a real word is another
# business, and an abbreviation the normaliser itself produces (FIN, INS,
# BK, CU ...) is part of a name, never a gap -- "ALLY FIN PAYMENT" is Ally
# Financial, not "ALLY PAYMENT" with a word skipped.
_GAP = r"(?:\s+(?:(?!(?:CU|BK|LN|WD|NA)\b)[A-Z]{2}|OF|THE|AND|DE|LA))?\s+"
UNNAMED_PROVIDER = "(unnamed)"
UNSPECIFIED = "Unspecified"         # a matched pattern in none of its category's subtypes


def normalize_core(s: str) -> str:
    s = _NA.sub("NA", str(s).upper().strip())
    s = " ".join(_NON_TOKEN.sub(" ", s).split())
    for rx, rep in _ABBREVIATIONS:
        s = rx.sub(rep, s)
    return s


# ---------------------------------------------------------------------------
# depository spellings (moved here from competition so SelfNames can use them)
# ---------------------------------------------------------------------------

_CU_TAILS = ("FEDERAL CREDIT UNION", "CREDIT UNION", "FCU", "CU", "FEDERAL")
_BANK_TAILS = ("BANK & TRUST", "BANK AND TRUST", "BANK & TRUST CO", "BANK, NATIONAL ASSOCIATION",
               "BANK NATIONAL ASSOCIATION", "NATIONAL BANK", "BANK", "BK")
_CU_FORMS = ("{r} CU", "{r} FCU", "{r} CREDIT UNION", "{r} FEDERAL CREDIT UNION", "{r} FEDERAL")
_BANK_FORMS = ("{r} BANK", "{r} BK")
_MIN_STEM = 4
# A root this common names no one institution: "First National Bank" must not become FIRST BANK,
# which every First-anything bank prints (RPE matching fixes, 2026-11-05: 1798's local "First
# National Bank" claimed a FIRST BANK LOAN PMT).
GENERIC_ROOTS = frozenset((
    "FIRST", "CITIZENS", "PEOPLES", "COMMUNITY", "SECURITY", "UNITED", "AMERICAN", "NATIONAL",
    "FARMERS", "MERCHANTS", "HOME", "STATE", "CITY", "COUNTY", "FIDELITY", "CENTRAL", "SOUTHERN",
    "NORTHERN", "WESTERN", "EASTERN", "PIONEER", "HERITAGE", "LIBERTY", "GUARANTY", "FIRST STATE",
    "FIRST NATIONAL", "FIRST FEDERAL", "FIRST COMMUNITY", "FIRST CITIZENS", "CITIZENS STATE",
    "FARMERS STATE", "TEACHERS", "EMPLOYEES", "FEDERAL", "SAVINGS", "TRUST", "VALLEY", "MUTUAL"))


def depository_variants(name: str) -> set[str]:
    """The spellings a card descriptor can carry for one configured name.

    14 of 1776's 24 locals shipped a single spelling, so SCHOOLSFIRST CU,
    FIRST TECH CU, PATELCO FCU and MONTECITO BK matched nothing (#261). The
    root is the name with its depository tail removed; the family is the
    root with every tail an acquirer prints. The bare root is never a
    pattern: "SESLOC" alone is fine, "FIRST" alone claims half the world --
    and a generic root gets no family at all (GENERIC_ROOTS).
    """
    base = " ".join(str(name).upper().replace(".", "").split())
    if base.startswith("THE "):
        base = base[4:]
    out = {base}
    for tails, forms in ((_CU_TAILS, _CU_FORMS), (_BANK_TAILS, _BANK_FORMS)):
        for tail in sorted(tails, key=len, reverse=True):
            if base.endswith(" " + tail):
                root = base[: -len(tail) - 1].strip(" ,")
                if root and root not in GENERIC_ROOTS and (len(root) >= _MIN_STEM or " " in root):
                    out.update(f.format(r=root) for f in forms)
                break
    for spelling in list(out):
        if " AND " in spelling:
            out.add(spelling.replace(" AND ", " & "))
        elif " & " in spelling:
            out.add(spelling.replace(" & ", " AND "))
    return {s for s in out if s}


# ---------------------------------------------------------------------------
# where a match sits in the descriptor (RPE matching fixes, 2026-11-05)
# ---------------------------------------------------------------------------
# The matchers run on the full text, city and state included (#261), so a
# name inside the town matched as an institution: SHELL OIL HUNTINGTON BEACH
# CA was Huntington, SHELL OIL 5744 LIVE OAK FL was Live Oak Bank. And a
# finance name followed by a venue word is the venue: CAPITAL ONE ARENA, US
# BANK STADIUM, PNC PARK, CITI TRENDS.

US_STATES = frozenset((
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
    "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR").split())
# A two-word town is taken only when its shape says so: SAN JOSE, NEW YORK (a first word that starts
# town names) or HUNTINGTON BEACH, LIVE OAK (a last word that ends them). Anything else keeps its
# second-to-last word, so MARCUS THEATRES MADISON WI keeps THEATRES beside MARCUS.
_CITY_FIRST = frozenset((
    "NEW SAN SANTA LOS LAS EL LA ST SAINT FT FORT PORT MT MOUNT NORTH SOUTH EAST WEST PALM BATON "
    "CEDAR SALT SIOUX GRAND LITTLE LONG CORPUS KANSAS OKLAHOMA CARSON JERSEY COLLEGE BOWLING HOT "
    "BATTLE BOWIE CAPE CORAL DEL DES ELK GREAT GLEN HIGH LAKE MOUNTAIN OCEAN OVERLAND PALO "
    "POMPANO ROUND ROCK SILVER SPRING STONE TWIN WHITE").split())
_CITY_LAST = frozenset((
    "CITY BEACH SPRINGS SPRING FALLS HILLS HEIGHTS VALLEY VILLAGE PARK LAKE LAKES RAPIDS HARBOR "
    "BAY CREEK ISLAND GROVE RIVER JUNCTION POINT RIDGE VISTA BLUFFS ROCK OAK OAKS WORTH ANGELES "
    "FRANCISCO DIEGO JOSE ANTONIO VEGAS YORK ORLEANS LOUIS PAUL CHARLES MESA GARDENS VIEW "
    "WOODS PINES PLAINS FORGE MILLS BEND HAVEN SHORES CANYON").split())


def _state_at(tokens: list[str], keep: frozenset) -> int | None:
    """Index of a trailing state code: "CA", "CA US", or the glued "CAUS" some acquirers print
    (GREENVILLE SCUS, FLOWOOD MSUS). A corporate tail is never a state: UPLIFT DESK CO."""
    if len(tokens) < 2:
        return None
    last = tokens[-1]
    if last == "US" and tokens[-2] in US_STATES and tokens[-2] not in keep:
        return len(tokens) - 2
    if last in US_STATES and last not in keep:
        return len(tokens) - 1
    if len(last) == 4 and last.endswith("US") and last[:2] in US_STATES:
        return len(tokens) - 1
    return None


def city_block(tokens: list[str], keep: frozenset = frozenset()) -> set[int]:
    """Token positions of the trailing "CITY ST" block, conservatively.

    The state must be a real one; the town is the word before it, and the word before that too
    only when the pair is shaped like a town (_CITY_FIRST / _CITY_LAST). A word in `keep` (a
    financial context word, a corporate tail) or a number is never part of a town: in
    PROGRESSIVE INS OH there is no town, and INS stays beside PROGRESSIVE."""
    s = _state_at(tokens, keep)
    if s is None or s < 2:
        return set()
    block = set(range(s, len(tokens)))
    i = s - 1
    if tokens[i] in keep or tokens[i].isdigit():
        return block
    block.add(i)
    j = i - 1
    if j >= 1 and tokens[j] not in keep and not tokens[j].isdigit() \
            and (tokens[j] in _CITY_FIRST or tokens[i] in _CITY_LAST):
        block.add(j)
    return block


def _token_regex(patterns: list[str]) -> re.Pattern:
    """Whole-token alternation over NORMALISED patterns, one short token
    allowed between pattern words. 'ALLY' must not match 'ALLY LOGISTICS'...
    it will, but the false-positive list catches the known ones; the
    boundary stops 'SOFI' matching 'SOFIA'."""
    normed = sorted({normalize_core(p) for p in patterns if p}, key=len, reverse=True)
    parts = [_GAP.join(re.escape(t) for t in p.split()) for p in normed if p]
    if not parts:
        return re.compile(r"(?!x)x")            # matches nothing
    return re.compile(r"(?<![A-Z0-9])(?:" + "|".join(parts) + r")(?![A-Z0-9])")


def _longest_match(s: str, compiled: list):
    """(category, kind, matched text) for the longest match, or None."""
    best = None
    for name, kind, rx in compiled:
        m = rx.search(s)
        if m and (best is None or len(m.group(0)) > len(best[2])):
            best = (name, kind, m.group(0))
    return best


def _context_rule(spec: dict) -> tuple[frozenset, frozenset]:
    block = spec.get("single_token_context") or {}
    return (frozenset(normalize_core(w) for w in (block.get("context") or ())),
            frozenset(normalize_core(w) for w in (block.get("neutral_tails") or ())))


# Street-address words. 1100's acquirer prints the merchant's street address after the name
# (COINBASE 248 3RD ST OAKLAND CAUS); an address says nothing about what the business is.
_ADDRESS_WORDS = frozenset((
    "ST STREET AVE AVENUE RD ROAD DR DRIVE BLVD HWY HIGHWAY STE SUITE WAY LN LANE CIR CIRCLE PL "
    "PLZA PKWY CT N S E W NE NW SE SW PO BOX FLOOR FL FIRST SECOND THIRD FOURTH FIFTH SIXTH "
    "SEVENTH EIGHTH NINTH TENTH").split())


def _is_address(tok: str) -> bool:
    return tok in _ADDRESS_WORDS or any(ch.isdigit() for ch in tok)


def _context_prefixes(context: frozenset) -> frozenset:
    """Every 4+ letter beginning of a 5+ letter context word: FINANCI, PAYM, MORTG, CAPITA."""
    return frozenset(w[:k] for w in context if len(w) > 4 for k in range(4, len(w)))


def _word_set(spec: dict, key: str) -> frozenset:
    return frozenset(normalize_core(w) for w in (spec.get(key) or ()) if w)


def _single_token_is_supported(rest: list[str], context: frozenset, tails: frozenset,
                               needs_context: bool = False,
                               prefixes: frozenset = frozenset()) -> bool:
    """Is a one-word match specific enough to keep, given the other words of the descriptor?

    A lone token names an institution far less reliably than the dictionary
    assumes: MERRILL GARDENS is a senior-living chain, MARCUS THEATRES is a
    cinema, ANTHEM SPORTS BAR is a bar. Seventeen of twenty realistic
    descriptors matched something before this rule existed.

    `rest` is every other word, without the town, the state and bare numbers (store numbers,
    references). Kept when it carries a financial context word, or when nothing but a corporate
    tail is left -- "COINBASE" and "COINBASE INC" are the provider; "KRAKEN BURGERS" is lunch.

    The town used to be removed with merchant.strip_city, which takes the last TWO words before a
    state and so took the business's own second word with it: MARCUS THEATRES MADISON WI came out
    as MARCUS alone and matched (RPE matching fixes, 2026-11-05). city_block takes one word unless
    the pair is shaped like a town.

    `prefixes` are context words cut short by the acquirer's field width: ONEMAIN FINANCI,
    SYNCB PHONE PAYM, TRUIST MORTG, COMENITY CAPITA (1100 and 1075, 2026-11-05).

    A token in the dictionary's needs_context list (a store whose card is a product, KOHLS, MACYS;
    a name that is mostly something else) is never kept alone: KOHLS #0123 SAN JOSE CA is shopping.
    """
    if not context:
        return True
    if any(t in context or t in prefixes for t in rest):
        return True
    if needs_context:
        return bool(rest) and all(t in tails for t in rest)
    return all(t in tails for t in rest)


_STAR_LEAD = re.compile(r"^\s*([A-Z0-9][A-Z0-9.&']*)\s*\*")


def classify_strings(cores: pd.Series, spec: dict) -> pd.DataFrame:
    """Distinct merchant cores -> (category, kind, provider).

    Named categories are consulted first; a category marked ``"fallback"`` in
    the config only when nothing named matched. Within each pass the longest
    matched text still wins, so a more specific named pattern beats a shorter
    one ("AMERICAN EXPRESS BUSINESS LOAN" stays Business Loans).

    The two passes exist because length was standing in for specificity and
    they are not the same thing. "Other Loans (lender unknown)" holds generic
    descriptors -- LOAN PAYMENT (12), LOAN PAYMT (10), LOAN PMT (8) -- every
    one of them longer than AVANT (5), so a single longest-wins pass filed
    named lenders as unknown and then published the generic descriptor as the
    provider. Competition passes no fallback categories, so its results are
    unchanged by construction.

    A false-positive phrase cancels only the match it overlaps (RPE matching fixes, 2026-11-05).
    It used to cancel the whole descriptor, so the AMAZON entry -- there to stop AMAZON STORE CARD
    swallowing every Amazon purchase -- also removed SYNCB/AMAZON, the Synchrony card payment.
    """
    fp = _token_regex(spec.get("false_positives", []))
    inbound = _token_regex(spec.get("inbound_words", []))
    # the client's own names still clear the whole descriptor: FIRSTLIGHT FCU LOAN PMT is the
    # member's own loan, and LOAN PMT beside the name must not survive as an outside lender
    own = _token_regex(spec.get("self_names", []))
    venue = _word_set(spec, "venue_words")
    needs = _word_set(spec.get("single_token_context") or {}, "needs_context")
    processors = _word_set(spec.get("single_token_context") or {}, "processor_tokens")
    strong = _word_set(spec.get("single_token_context") or {}, "strong_tokens")
    pay_prefixes = _word_set(spec.get("single_token_context") or {}, "payment_prefixes")
    named, fallback = [], []
    spelling: dict = {}          # normalised pattern -> how the dictionary spells it
    for name, c in spec["categories"].items():
        if c.get("patterns"):
            entry = (name, c.get("kind", "leakage"), _token_regex(c["patterns"]))
            (fallback if c.get("fallback") else named).append(entry)
            for p in c["patterns"]:
                # the fullest spelling wins: ALLY FINANCIAL over ALLY FIN
                key, full = normalize_core(p), str(p).upper().strip()
                if len(full) > len(spelling.get(key, "")):
                    spelling[key] = full
    context, tails = _context_rule(spec)
    keep = context | tails
    ctx_prefixes = _context_prefixes(context)

    def _label(text: str) -> str:
        """The provider as the dictionary spells it, not as the descriptor
        abbreviated it: BANK OF AMERICA, not BK OF AMERICA. A gap token
        inside the match is dropped to find the pattern."""
        if text in spelling:
            return spelling[text]
        toks = text.split()
        for i in range(1, len(toks) - 1):
            cand = " ".join(toks[:i] + toks[i + 1:])
            if cand in spelling:
                return spelling[cand]
        return text

    def _resolve(s: str, compiled: list, tokens: list[str], town: set[int], vetoed: list,
                 lead: str = ""):
        """The best match that is specific enough to keep, or None.

        Every occurrence of every category is a candidate, walked longest-first; a rejected one
        does not end the search, since a shorter pattern elsewhere may still hold. A candidate is
        rejected when it overlaps a false-positive phrase, sits in the town, is followed by a
        venue word, or is one word without support (_single_token_is_supported).
        """
        seen = []
        for name, kind, rx in compiled:
            for m in rx.finditer(s):
                seen.append((name, kind, m.group(0), m.start(), m.end()))
        for name, kind, text, a, b in sorted(seen, key=lambda c: (-len(c[2]), c[3])):
            if any(a < fb and fa < b for fa, fb in vetoed):
                continue                        # inside AMAZON, not beside it: SYNCB/AMAZON is Synchrony
            first = s.count(" ", 0, a)
            n_tok = text.count(" ") + 1
            idx = range(first, first + n_tok)
            if any(i in town for i in idx):
                continue                        # HUNTINGTON BEACH CA, LIVE OAK FL
            # PROVIDER *MERCHANT: the word before the star is the processor that took the payment --
            # AFFIRM *PELOTON, KLARNA*TARGET are buy-now-pay-later payments, as the BNPL tier
            # already counts them (R4), and VENMO *MARINA DIAZ is a Venmo payment to a person. A
            # processor_tokens word opening the descriptor is the same with the star lost:
            # KLARNA TIKTOK SHOP, KLARNA KLARNA. What follows is the merchant it paid, never context
            # and never a venue.
            head = text.split(" ")[0]
            is_processor = first == 0 and n_tok == 1 and (text == lead or text in processors)
            # a payment app opening the descriptor is followed by whoever it paid, never a venue:
            # CASH APP MARINA OAKLAND CA, PAYPAL INST XFER PIZZA HUT
            app_first = first == 0 and (head in processors or head == lead or kind == "adjacency")
            nxt = tokens[first + n_tok] if first + n_tok < len(tokens) else ""
            if nxt in venue and not app_first and not (n_tok == 1 and text in context):
                continue                        # CAPITAL ONE ARENA, US BANK STADIUM, CITI TRENDS
            if n_tok == 1 and not is_processor:
                before = tokens[:first]
                # the payee of a bill-pay processor: PNM SANTANDER, OPC*AVANT, CSI SYNCHRONY
                payee = bool(before) and before[-1] in pay_prefixes and \
                    all(t in pay_prefixes or t in context for t in before)
                # a coined brand name opening the descriptor is the institution whatever follows:
                # COINBASE ONE, ROBINHOOD DEBITS, SYNCB/JCPENNEY, CITIBANK, N.A. 701 E 60TH ST
                opens = all(t in context or t in pay_prefixes or (lead and t == lead) for t in before)
                if payee or (text in strong and opens):
                    return name, kind, text
                # rest leaves out the town, the street address, a repeat of the name
                # (SEZZLE INC. SEZZLE*...) and the processor before a star. Once a house number
                # follows the name, the rest is the address: CHIME 77 MAIDEN LN-SIXTH SAN FRANCISCO
                # (1100, $1.8M) -- MAIDEN is a street, not a word beside Chime.
                house = next((i for i in range(first + 1, len(tokens)) if tokens[i].isdigit()),
                             len(tokens))
                rest = [t for i, t in enumerate(tokens)
                        if i not in idx and i not in town and i < house and not _is_address(t)
                        and t != text and not (i == 0 and lead and t == lead)]
                if not _single_token_is_supported(rest, context, tails, text in needs, ctx_prefixes):
                    continue
            return name, kind, text
        return None

    rows = []
    for s in cores:
        n = normalize_core(s) if s else ""
        if not n or inbound.search(n) or own.search(n):
            # money coming back (a refund, a tax refund, a reversal) is not a payment to the
            # provider; the files carry no debit/credit flag, so the wording is all there is
            rows.append((s, None, None, None))
            continue
        tokens = n.split(" ")
        town = city_block(tokens, keep)
        vetoed = [(m.start(), m.end()) for m in fp.finditer(n)]
        star = _STAR_LEAD.match(str(s).upper())
        lead = normalize_core(star.group(1)) if star else ""
        best = _resolve(n, named, tokens, town, vetoed, lead) or \
            _resolve(n, fallback, tokens, town, vetoed, lead)
        if best:
            # a bare category word ("BROKERAGE") names the category, not a
            # provider -- publishing it as one put "BROKERAGE $633,466" at
            # the top of a who-they-pay table (#245)
            provider = UNNAMED_PROVIDER if best[2] in context else _label(best[2])
            rows.append((s, best[0], best[1], provider))
        else:
            rows.append((s, None, None, None))
    return pd.DataFrame(rows, columns=["core", "category", "kind", "provider"]).set_index("core")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _pct(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def blank_description_decline(text: pd.Series, in_base: np.ndarray, what: str) -> str | None:
    """The reason to decline, when the file names nobody, else None.

    1038 Sugar River's file (2026-11) carries a blank description, MCC, location and merchant id
    on all 187,902 rows. Every row went unmatched and the chapter published 0% leakage -- a
    finding of no leakage drawn from a file that cannot show any (RPE matching fixes, 2026-11-05).
    """
    n = int(in_base.sum())
    if not n:
        return None
    blank = int(((text.fillna("").astype(str).str.strip() == "").to_numpy() & in_base).sum())
    share = _pct(blank, n)
    if share < BLANK_DESCRIPTION_DECLINE_PCT:
        return None
    return (f"{share:.0f}% of the transaction rows carry no description, so {what} cannot be "
            f"read from this file; the section is declined rather than shown as zero")


def _recency_tier(days: pd.Series, spec: dict) -> pd.Series:
    r = spec.get("recency_days", {})
    a, c, d = r.get("active", 30), r.get("cooling", 90), r.get("dormant", 365)
    return pd.cut(days, bins=[-1, a, c, d, 10**6],
                  labels=["active", "cooling", "dormant", "lapsed"]).astype(str)


def _category_pairs(leak_acc: pd.DataFrame) -> list:
    """Legacy 13: unordered pairs of leakage categories that share an
    account, counted once per account. rows: [category_a, category_b, n]."""
    per_acct = leak_acc.groupby("acct")["category"].agg(lambda s: sorted(set(s)))
    counts: dict[tuple, int] = {}
    for cats in per_acct:
        for pair in combinations(cats, 2):
            counts[pair] = counts.get(pair, 0) + 1
    return [[a, b, n] for (a, b), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def _reach_by_category(addr_acc: pd.DataFrame) -> list:
    """Legacy 18: per addressable category, the accounts and dollars whose
    relationship is still active or cooling -- the part that can be won
    back with timely outreach. rows: [category, accounts, reachable_accounts,
    reachable_pct, dollars, reachable_dollars], largest reachable $ first."""
    rows = []
    for name, grp in addr_acc.groupby("category", observed=True):
        live = grp[grp["tier"].isin(REACHABLE_TIERS)]
        n_acc, n_live = int(grp["acct"].nunique()), int(live["acct"].nunique())
        rows.append([name, n_acc, n_live, _pct(n_live, n_acc),
                     round(float(grp["dollars"].sum())), round(float(live["dollars"].sum()))])
    rows.sort(key=lambda r: (-r[5], r[0]))
    return rows


# ---------------------------------------------------------------------------
# compute
# ---------------------------------------------------------------------------

_MARKETPLACE = re.compile(r"^(?:PAYPAL|PP)\s*\*\s*\S")


def marketplace_purchase(text: pd.Series) -> np.ndarray:
    """PAYPAL *MERCHANT is a purchase at that merchant settled through
    PayPal, not money moving into a wallet. The wallet forms -- PAYPAL,
    PAYPAL INST XFER, PAYPAL TRANSFER, VENMO, CASH APP, APPLE CASH -- are
    the ecosystem. On a card feed the two look alike until the star."""
    return text.str.match(_MARKETPLACE).to_numpy()


def classify_rows(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Per-row classification aligned to df.index: text, core, category,
    kind, provider, is_card. Matched on the full description text (the
    institution is found wherever it sits; the city after it does not
    matter), grouped by the core. Adjacency (P2P / fintech) is kept on every
    rail and reported apart from leakage and competitors; only a PayPal
    marketplace purchase is cleared, because that is merchant spend (#261).
    Computed once per run and shared by financial_services and competition."""
    typ = df["transaction_type"].astype(str).str.upper()
    is_card = typ.isin(["PIN", "SIG"]).to_numpy()
    text = merchant_text(df["merchant_name"])
    core = merchant_core(df["merchant_name"])
    table = classify_strings(pd.Index(text.unique()), spec)
    cat = text.map(table["category"])
    kind = text.map(table["kind"])
    provider = text.map(table["provider"])
    purchase = (kind == "adjacency").to_numpy() & marketplace_purchase(text)
    inbound_rx = _token_regex(spec.get("inbound_words", []))
    inb = {t: bool(inbound_rx.search(normalize_core(t))) for t in text.unique() if t}
    return pd.DataFrame({"text": text, "core": core, "category": cat.where(~purchase),
                         "kind": kind.where(~purchase), "provider": provider.where(~purchase),
                         "is_card": is_card, "inbound": text.map(inb).fillna(False).astype(bool)},
                        index=df.index)


def compute(df: pd.DataFrame, lenses: Lenses | None, spec: dict, anchor_end: pd.Timestamp,
            lists_dir: Path | None, warn, account_filter: pd.Index | None = None,
            key_prefix: str = "fin_", base_label: str = "all accounts",
            classification: pd.DataFrame | None = None) -> tuple[dict, dict]:
    """Returns (metrics, outputs). outputs holds CSV paths.

    account_filter restricts the base (e.g. personal accounts only); the
    by-lens table is always computed over every lens regardless, so the
    business and personal rows remain comparable. classification is the
    classify_rows() frame; computed here when not supplied.
    """
    out: dict = {}
    outputs: dict = {}
    if df.empty:
        return out, outputs
    out[key_prefix + "base_label"] = base_label

    if classification is None:
        classification = classify_rows(df, spec)
    core, cat, kind, provider = (classification["core"], classification["category"],
                                 classification["kind"], classification["provider"])
    is_card = classification["is_card"].to_numpy()
    is_transfer = ~is_card
    # nan_to_num: a blank amount is $0, never a NaN that poisons the
    # numpy sums (numpy does not skip NaN; round(nan) raises) -- 1585.
    amt = np.nan_to_num(df["amount"].abs().to_numpy())
    acct = df["primary_account_num"].astype(str)
    in_base = acct.isin(account_filter).to_numpy() if account_filter is not None \
        else np.ones(len(df), dtype=bool)
    matched = cat.notna().to_numpy()

    declined = blank_description_decline(classification["text"], in_base,
                                         "who the accounts pay")
    if declined:
        out[key_prefix + "declined"] = declined
        out[key_prefix + "accounts_total"] = int(acct[in_base].nunique())
        warn(f"financial services: {declined}")
        return out, outputs

    total_accounts = int(acct[in_base].nunique())
    transfer_dollars = float(amt[is_transfer & in_base].sum())

    # ---- internal transfers (SelfNames): reported, then excluded ----------
    # Whole book, once (on the fin_ pass), so the number is visible instead
    # of the rows silently vanishing into the false-positive list.
    self_names = spec.get("self_names") or []
    if self_names and key_prefix == "fin_":
        srx = _token_regex(self_names)
        hit_cores = pd.Index([c for c in core.unique() if c and srx.search(normalize_core(c))])
        if len(hit_cores):
            smask = core.isin(hit_cores).to_numpy()
            stab = classify_strings(hit_cores, {"categories": {
                n: {"kind": "self", "patterns": [n]} for n in self_names},
                "false_positives": []})
            # positional throughout: core's index is df's, which need not be 0..n-1 (the
            # old Series(range(n))[mask].groupby(labelled) paired rows by label and misfiled them)
            sname = core.map(stab["category"]).to_numpy()
            pos = np.flatnonzero(smask)
            acct_arr = acct.to_numpy()
            rows = []
            for n in pd.unique(sname[pos]):
                if not isinstance(n, str):
                    continue
                idx = pos[sname[pos] == n]
                rows.append([n, int(pd.unique(acct_arr[idx]).size), len(idx),
                             round(float(amt[idx].sum()))])
            rows.sort(key=lambda r: -r[3])
            out[key_prefix + "self"] = {
                "names_configured": spec.get("self_names_configured") or self_names,
                "accounts": int(acct[smask].nunique()),
                "txns": int(smask.sum()),
                "dollars": round(float(amt[smask].sum())),
                "pct_of_transfer_dollars": (
                    _pct(float(amt[smask & is_transfer].sum()),
                         float(amt[is_transfer].sum()))
                    if float(amt[is_transfer].sum()) else None),
                "by_name": rows,
                "note": "internal transfers -- excluded from every leakage, "
                        "competition and review table"}
    if "inbound" in classification:
        inbound = classification["inbound"].to_numpy() & in_base
        out[key_prefix + "inbound_excluded"] = {
            "txns": int(inbound.sum()), "dollars": round(float(amt[inbound].sum())),
            "note": "refunds, tax refunds, rebates and reversals by their wording -- money coming "
                    "back, never a payment to the provider; the files carry no debit/credit flag"}
    out[key_prefix + "categories_n"] = len(spec["categories"])
    out[key_prefix + "patterns_n"] = int(sum(len(c.get("patterns", [])) for c in spec["categories"].values()))
    out[key_prefix + "matched_rows"] = int((matched & in_base).sum())
    out[key_prefix + "matched_rows_pct"] = _pct(int((matched & in_base).sum()), int(in_base.sum()))
    leak = matched & (kind == "leakage").to_numpy()
    adj = matched & (kind == "adjacency").to_numpy()
    out[key_prefix + "leakage_dollars"] = round(float(amt[leak & in_base].sum()))
    # None, not 0.0, when the file carries no transfer rail: a share of a
    # denominator that does not exist is not a finding (#245)
    out[key_prefix + "leakage_pct_of_transfer_dollars"] = (
        _pct(float(amt[leak & is_transfer & in_base].sum()), transfer_dollars)
        if transfer_dollars else None)
    out[key_prefix + "adjacency_dollars"] = round(float(amt[adj & in_base].sum()))
    out[key_prefix + "accounts_total"] = total_accounts
    out[key_prefix + "accounts_total_note"] = (f"{base_label} in the window -- the "
                                               f"denominator of every headline rate "
                                               f"in this section")

    # ---- per account x category ------------------------------------------
    m = pd.DataFrame({
        "acct": acct.to_numpy()[matched], "category": cat.to_numpy()[matched],
        "kind": kind.to_numpy()[matched], "provider": provider.to_numpy()[matched],
        "amount": amt[matched], "date": df["transaction_date"].to_numpy()[matched],
        "card": is_card[matched],
    })
    if m.empty:
        warn("financial services: no transaction matched the dictionary")
        return out, outputs
    per_acct_total = pd.Series(amt[is_transfer]).groupby(acct.to_numpy()[is_transfer]).sum()

    g = m.groupby(["acct", "category"], observed=True)
    ac = g.agg(txns=("amount", "size"), dollars=("amount", "sum"),
               first=("date", "min"), last=("date", "max"),
               months=("date", lambda s: s.dt.to_period("M").nunique()),
               card_share=("card", "mean")).reset_index()
    ac["recency_days"] = (anchor_end - ac["last"]).dt.days
    ac["tier"] = _recency_tier(ac["recency_days"], spec)
    new_days = spec.get("new_leakage_days", 90)
    stop_days = spec.get("stopped_after_days", 90)
    ac["is_new"] = (anchor_end - ac["first"]).dt.days <= new_days
    ac["is_stopped"] = (ac["recency_days"] > stop_days) & (ac["months"] >= MIN_MONTHS_FOR_STOPPED)
    ac["wallet_share"] = (ac["dollars"] / ac["acct"].map(per_acct_total)).clip(upper=1.0) * 100
    kinds = {name: c.get("kind", "leakage") for name, c in spec["categories"].items()}
    addressable = {name for name, c in spec["categories"].items() if c.get("addressable")}
    ac["kind"] = ac["category"].map(kinds)

    # Full-book tables feed the by-lens comparison; the base (e.g. personal
    # only) feeds every headline table, profile, P2P block and list.
    ac_all, m_all = ac, m
    if account_filter is not None:
        ac = ac[ac["acct"].isin(account_filter)]
        m = m[m["acct"].isin(account_filter)]

    # ---- 1. by category --------------------------------------------------
    rows = []
    for name, grp in ac.groupby("category", observed=True):
        n_acc = int(grp["acct"].nunique())
        # wallet_share is 0/0 = NaN for zero-dollar accounts (blank source
        # amounts); an all-NaN group must report None, not NaN -- and
        # .median() on all-NaN spams numpy's 'Mean of empty slice' warning
        ws = grp["wallet_share"]
        rows.append([name, n_acc, _pct(n_acc, total_accounts), int(grp["txns"].sum()),
                     round(float(grp["dollars"].sum())),
                     round(float(grp["dollars"].sum()) / n_acc) if n_acc else 0,
                     kinds.get(name, "leakage"), name in addressable,
                     round(float(ws.median()), 1) if ws.notna().any() else None,
                     round(float(grp["card_share"].mean() * 100), 1)])
    rows.sort(key=lambda r: (r[6] != "leakage", -r[4]))
    out[key_prefix + "by_category"] = rows
    out[key_prefix + "by_category_columns"] = ["category", "accounts", "pct_of_accounts", "txns", "dollars",
                                      "dollars_per_acct", "kind", "addressable",
                                      "median_wallet_share_pct", "card_rail_pct"]

    # ---- subtypes: a category split by the line its provider writes (Insurance: auto / home /
    # life / health). From the dictionary's "subtypes"; a pattern in none is "Unspecified".
    subtype_rows = {}
    m_base = m if account_filter is None else m[m["acct"].isin(account_filter)]
    for name, c in spec["categories"].items():
        if not c.get("subtypes"):
            continue
        grp = m_base[m_base["category"] == name]
        if grp.empty:
            continue
        lookup = {}
        for sub, pats in c["subtypes"].items():
            for p in pats:
                lookup[str(p).upper().strip()] = sub
                lookup.setdefault(normalize_core(str(p)), sub)
        prov = grp["provider"].astype(str)
        sub_of = prov.map(lambda v: lookup.get(v.upper().strip(), lookup.get(normalize_core(v), UNSPECIFIED)))
        cat_accts, cat_dollars = grp["acct"].nunique(), float(grp["amount"].sum())
        rows_s = []
        for sub, g in grp.groupby(sub_of.to_numpy(), sort=False):
            top = g.groupby("provider", observed=True)["amount"].sum().sort_values(ascending=False)
            rows_s.append([sub, int(g["acct"].nunique()), _pct(int(g["acct"].nunique()), cat_accts),
                           int(len(g)), round(float(g["amount"].sum())),
                           _pct(float(g["amount"].sum()), cat_dollars),
                           [str(x) for x in top.index[:3]]])
        rows_s.sort(key=lambda r: (r[0] == UNSPECIFIED, -r[4]))
        subtype_rows[name] = rows_s
    if subtype_rows:
        out[key_prefix + "subtypes"] = subtype_rows
        out[key_prefix + "subtypes_columns"] = ["subtype", "accounts", "pct_of_category_accounts", "txns",
                                                "dollars", "pct_of_category_dollars", "top_providers"]
        out[key_prefix + "subtypes_note"] = ("an account can pay more than one line, so subtype accounts can "
                                             "add to more than the category's; dollars add exactly")

    leak_acc = ac[ac["kind"] == "leakage"]
    addr_acc = ac[ac["category"].isin(addressable)]
    leak_ids = pd.Index(leak_acc["acct"].unique())
    addr_ids = pd.Index(addr_acc["acct"].unique())
    out[key_prefix + "leaking_accounts"] = len(leak_ids)
    out[key_prefix + "leaking_pct"] = _pct(len(leak_ids), total_accounts)
    out[key_prefix + "addressable_accounts"] = len(addr_ids)
    out[key_prefix + "addressable_pct"] = _pct(len(addr_ids), total_accounts)
    out[key_prefix + "addressable_dollars"] = round(float(addr_acc["dollars"].sum()))
    active_addr = addr_acc[addr_acc["tier"].isin(["active", "cooling"])]
    out[key_prefix + "addressable_active_accounts"] = int(active_addr["acct"].nunique())

    # ---- 2. who they pay: top providers per category, concentration ------
    providers, concentration = {}, []
    for name, grp in m.groupby("category", observed=True):
        pg = grp.groupby("provider", observed=True).agg(accts=("acct", "nunique"), dollars=("amount", "sum"))
        pg = pg.sort_values("dollars", ascending=False)
        providers[name] = [[p, int(r.accts), round(float(r.dollars))] for p, r in pg.head(TOP_PROVIDERS).iterrows()]
        tot = float(pg["dollars"].sum())
        concentration.append([name, int(len(pg)), _pct(float(pg["dollars"].head(3).sum()), tot)])
    out[key_prefix + "top_providers"] = providers
    out[key_prefix + "provider_concentration"] = sorted(concentration, key=lambda r: -r[2])

    # ---- 3. recency; 4. new vs recurring vs stopped -----------------------
    rec, dyn = [], []
    for name, grp in ac.groupby("category", observed=True):
        t = grp["tier"].value_counts()
        rec.append([name] + [int(t.get(k, 0)) for k in ("active", "cooling", "dormant", "lapsed")])
        dyn.append([name, int(grp["is_new"].sum()), int((~grp["is_new"] & ~grp["is_stopped"]).sum()),
                    int(grp["is_stopped"].sum())])
    out[key_prefix + "recency"] = rec
    out[key_prefix + "new_recurring_stopped"] = dyn

    # ---- multi-category ------------------------------------------------------
    per_acct_cats = leak_acc.groupby("acct")["category"].nunique()
    out[key_prefix + "multi_category"] = [[int(k), int(v)] for k, v in per_acct_cats.value_counts().sort_index().items()]
    out[key_prefix + "multi_category_pct"] = _pct(int((per_acct_cats >= 2).sum()), len(leak_ids))

    # ---- which services travel together; what is still within reach ---------
    out[key_prefix + "category_pairs"] = _category_pairs(leak_acc)
    out[key_prefix + "category_pairs_columns"] = ["category_a", "category_b", "accounts"]
    reach = _reach_by_category(addr_acc)
    out[key_prefix + "reach"] = reach
    out[key_prefix + "reach_columns"] = ["category", "accounts", "reachable_accounts",
                                          "reachable_pct", "dollars", "reachable_dollars"]
    out[key_prefix + "reach_dollars"] = int(sum(r[5] for r in reach))

    # ---- 5. by lens ----------------------------------------------------------
    txn_accounts = pd.Index(acct.unique())
    if lenses is not None:
        by_lens, by_lens_cat = [], []
        top_cats = [r[0] for r in rows if r[6] == "leakage"][:TOP_CATEGORIES_BY_LENS]
        addr_all = ac_all[ac_all["category"].isin(addressable)]
        addr_ids_all = pd.Index(addr_all["acct"].unique())
        adj_ids = pd.Index(ac_all[ac_all["kind"] == "adjacency"]["acct"].unique())
        for ln in lenses.names():
            # Denominator: accounts in the lens that transact in the window,
            # not every account in the ODD (which includes closed ones).
            ids = lenses.ids(ln).intersection(txn_accounts)
            n = len(ids)
            if not n:
                continue
            leakers = addr_ids_all.intersection(ids)
            adj_in = adj_ids.intersection(ids)
            dollars = float(addr_all[addr_all["acct"].isin(leakers)]["dollars"].sum())
            by_lens.append([ln, lenses.label(ln), n, len(leakers), _pct(len(leakers), n),
                            round(dollars / len(leakers)) if len(leakers) else 0,
                            len(adj_in), _pct(len(adj_in), n)])
            for c in top_cats:
                cid = pd.Index(ac_all[ac_all["category"] == c]["acct"].unique()).intersection(ids)
                by_lens_cat.append([ln, c, len(cid), _pct(len(cid), n)])
        out[key_prefix + "by_lens"] = by_lens
        # The by-lens numerator is ADDRESSABLE categories only (the headline
        # leaking_pct counts any leakage) -- the columns say so.
        out[key_prefix + "by_lens_columns"] = ["lens", "label", "accounts", "addressable",
                                      "addressable_pct", "dollars_per_addressable_acct",
                                      "p2p_or_fintech", "p2p_or_fintech_pct"]
        out[key_prefix + "by_lens_note"] = ("addressable categories only; base = accounts "
                                            "in the lens that transacted in the window")
        out[key_prefix + "by_lens_category"] = by_lens_cat
        resp = next((r for r in by_lens if r[0] == "responders"), None)
        ctrl = next((r for r in by_lens if r[0] == "mailed_nonresp"), None)
        if resp and ctrl:
            out[key_prefix + "responder_leak_gap_pp"] = round(resp[4] - ctrl[4], 1)
            # The raw gap is partly an activity artifact: busier accounts hit
            # more counterparties on every rail. The conditioned gap compares
            # only accounts with a real transfer habit, so it is the one to
            # quote as a program contrast.
            xfer_counts = acct[is_transfer].value_counts()
            habitual = pd.Index(xfer_counts[xfer_counts >= MIN_TRANSFER_TXNS_FOR_GAP].index)
            cond = []
            for ln in ("responders", "mailed_nonresp"):
                ids = lenses.ids(ln).intersection(txn_accounts).intersection(habitual)
                if not len(ids):
                    cond = None
                    break
                cond.append(_pct(len(addr_ids_all.intersection(ids)), len(ids)))
            if cond:
                out[key_prefix + "responder_leak_gap_conditioned_pp"] = round(cond[0] - cond[1], 1)
                out[key_prefix + "responder_leak_gap_note"] = (
                    f"raw gap includes an activity artifact; conditioned gap compares "
                    f"accounts with >= {MIN_TRANSFER_TXNS_FOR_GAP} transfer txns in the "
                    f"window (responders {cond[0]}% vs control {cond[1]}%)")
        for special, key in (("recently_inactive", key_prefix + "at_risk_leaking"), ("new_accounts", key_prefix + "new_accounts_leaking")):
            if special in lenses.masks:
                ids = lenses.ids(special).intersection(txn_accounts)
                hit = addr_ids_all.intersection(ids)
                out[key] = {"accounts": len(ids), "leaking": len(hit), "pct": _pct(len(hit), len(ids))}

        # Private (popped before metrics.json): whole-book addressable rows
        # for the deposit-flight overlay.
        if key_prefix == "fin_":
            out["_addressable_accounts"] = addr_all[["acct", "category", "dollars"]]                 .values.tolist()

        # ---- leakers' profile from the ODD ------------------------------------
        attrs = lenses.attrs
        prof = []
        for name, grp in addr_acc.groupby("category", observed=True):
            ids = pd.Index(grp["acct"].unique()).intersection(attrs.index)
            if len(ids) < 20:
                continue
            a = attrs.loc[ids]
            bal = pd.to_numeric(a.get("Curr Bal"), errors="coerce") if "Curr Bal" in a.columns else None
            resp_flag = a["Response Grouping"].isin(["SO-SR", "MO-SR", "MR"]) if "Response Grouping" in a.columns else None
            prof.append([name, len(ids),
                         round(float(bal.median())) if bal is not None and bal.notna().any() else None,
                         round(float(bal.sum())) if bal is not None else None,
                         round(float(a["tenure_years"].median()), 1) if "tenure_years" in a.columns else None,
                         _pct(int(resp_flag.sum()), len(ids)) if resp_flag is not None else None])
        out[key_prefix + "leakers_profile"] = prof
        out[key_prefix + "leakers_profile_columns"] = ["category", "accounts", "median_balance",
                                              "total_balance", "median_tenure_yrs", "responder_pct"]

    # ---- P2P and fintech, singled out -------------------------------------------
    for label, key in (("P2P Transfers", key_prefix + "p2p"), ("Fintech / Neobanks", key_prefix + "fintech")):
        grp = ac[ac["category"] == label]
        if len(grp):
            ids = pd.Index(grp["acct"].unique())
            prov = m[m["category"] == label].groupby("provider", observed=True).agg(
                accts=("acct", "nunique"), dollars=("amount", "sum")).sort_values("dollars", ascending=False)
            out[key] = {"accounts": len(ids), "pct_of_accounts": _pct(len(ids), total_accounts),
                        "txns": int(grp["txns"].sum()), "dollars": round(float(grp["dollars"].sum())),
                        "dollars_per_acct": round(float(grp["dollars"].sum()) / len(ids)),
                        "providers": [[p, int(r.accts), round(float(r.dollars))] for p, r in prov.head(8).iterrows()]}
            if lenses is not None:
                out[key]["by_lens"] = [[ln, len(ids.intersection(lenses.ids(ln))),
                                        _pct(len(ids.intersection(lenses.ids(ln))),
                                             len(lenses.ids(ln).intersection(txn_accounts)))]
                                       for ln in lenses.names() if len(lenses.ids(ln).intersection(txn_accounts))]

    # ---- biggest unmatched transfer counterparties, regardless of tokens ------
    # (Capital One and Chase card payments carried no finserv token and were
    # invisible to the review queue on 1615's first run.)
    if "merchant_key" in df.columns:
        um = (~pd.Series(matched, index=df.index)) & pd.Series(is_transfer & in_base, index=df.index)
        keys = df["merchant_key"].astype(str)[um]
        top = pd.DataFrame({"k": keys, "amount": amt[um.to_numpy()]}).groupby("k").agg(
            txns=("amount", "size"), accts=("amount", "size"), dollars=("amount", "sum"))
        top = top[~top.index.isin(["(no description)", "nan", ""])].sort_values("dollars", ascending=False)
        out[key_prefix + "unmatched_top"] = [[k, int(r.txns), round(float(r.dollars))] for k, r in top.head(20).iterrows()]

    # ---- review queue: finserv-looking strings the dictionary missed ----------
    tokens = spec.get("review_tokens", [])
    if tokens:
        rx = _token_regex(tokens)
        ignore = spec.get("review_ignore") or []
        irx = _token_regex(ignore) if ignore else None
        unmatched = pd.Index(core[provider.isna()].unique())   # never matched (card-rail adjacency is matched)
        cand = [s for s in unmatched if s and rx.search(normalize_core(s))
                and not (irx and irx.search(normalize_core(s)))]
        if cand:
            mask = core.isin(cand) & ~pd.Series(matched, index=core.index) & pd.Series(in_base, index=core.index)
            q = pd.DataFrame({"core": core[mask], "amount": amt[mask.to_numpy()]}).groupby("core").agg(
                txns=("amount", "size"), dollars=("amount", "sum")).sort_values("dollars", ascending=False)
            out[key_prefix + "review_queue"] = [[s, int(r.txns), round(float(r.dollars))] for s, r in q.head(REVIEW_QUEUE).iterrows()]
            out[key_prefix + "review_queue_dollars"] = round(float(q["dollars"].sum()))

    # ---- action lists: CSV per addressable category, paths in outputs -----------
    if lists_dir is not None and lenses is not None:
        lists_dir.mkdir(parents=True, exist_ok=True)
        attrs = lenses.attrs
        written = {}
        for name in sorted(addressable & set(ac["category"].unique())):
            grp = ac[ac["category"] == name].copy()
            grp = grp.join(attrs, on="acct", how="left")
            grp = grp.sort_values(["tier", "dollars"], ascending=[True, False])
            path = lists_dir / f"finserv_{re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_').lower()}.csv"
            cols = ["acct", "txns", "dollars", "first", "last", "tier", "months", "wallet_share"] + \
                   [c for c in attrs.columns if c in grp.columns]
            grp[cols].to_csv(path, index=False)
            written[name] = str(path)
        outputs["finserv_lists"] = written
    return out, outputs
