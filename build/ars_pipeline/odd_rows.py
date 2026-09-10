#!/usr/bin/env python3
"""
odd_rows.py — the ODD row vocabulary, defined once.

Every ARS script reads the same ODD with the same handful of predicates, and
until now each one re-declared them. They had drifted:

    metrics_gen.py:97   personal(r) = g(r,'Business?') == 'No'
    ticket_calc.py:20   personal(row) = row[...].strip().lower() != 'yes'

A blank `Business?` cell was PERSONAL to ticket_calc and NOT personal to
metrics_gen, so two slides of the same deck were built on different
denominators. Blanks are real: 1218 carries 271, 1204 carries 57, 1038 carries
2 (1075, 1174, 1437 and 1705 carry none, which is why it stayed hidden).

`product_mix_slide.py:200-202` already settled the house rule by splitting the
book three ways — Yes → business, No → personal, anything else → other — so a
blank is NEITHER. metrics_gen's reading is the correct one and ticket_calc's is
the outlier; this module makes that the single definition.

IMPORT-SAFE ON PURPOSE. metrics_gen reads sys.argv at module scope, so importing
it runs it — which is why responder_activity re-implemented these helpers
standalone rather than importing them. Nothing here executes at import time.

Usage:

    from odd_rows import accessors
    odd = accessors(H)          # H = {column name: index}
    if odd.personal(row) and odd.hascard(row):
        n += odd.swipes(row, "Jul26")
"""
from types import SimpleNamespace

# Stat Desc wording that counts as an open account. Core lifecycle vocabulary
# varies by processor; both spellings of each phrase are carried.
OPEN_STATUSES = {
    "Open", "Active", "Open/Active", "Dormant", "Inactive", "Restricted",
    "No Close on Zero Balance", "No Post: Force Pay Items Only",
    "New This Cycle", "Pending Activation",
}
CLOSED_STATUSES = {
    "Closed", "Charge-off", "Charge-Off", "Charged Off", "Charged-Off",
    "Purge at Yearend", "Purge at Year End", "Pending Closeout",
    "Pending Close Out",
}



# Status wording is the shared vocabulary from CLAUDE.md / oddd_optimize. Kept
# HERE, with the status sets it belongs to, because more than one slide needs it
# and a status rule copied into a second file is a rule that drifts — which is
# exactly what happened. `product_mix_slide` carried its own `_CLOSED = {"Closed"}`
# and so counted 90 CHARGED-OFF 1204 accounts inside a total labelled
# "Excl. Closed", while `excluded_accounts_slide` classified the same rows closed.
#
# Clients do not agree on which status field they populate: 1509 Texas Bay fills
# `Stat Desc`, 1549 Wellworth fills `Stat Code` (O/C/X) and leaves `Stat Desc`
# BLANK on every non-open account. So use the description when it carries text,
# else fall back to the code.
_CLOSED_PREFIX = ("closed", "charge", "purge", "pending close")
_OPEN_PREFIX = ("open", "active")


def _code_sets():
    """STAT_CODE_MAP lives in scripts/; import it lazily so importing this module
    never depends on scripts/ being on the path."""
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                      _os.pardir, _os.pardir, "scripts"))
    from oddd_optimize import STAT_CODE_MAP
    return ({k for k, v in STAT_CODE_MAP.items() if v == "Open"},
            {k for k, v in STAT_CODE_MAP.items() if v in ("Closed", "Charged Off")})


def status_class(desc, code):
    """-> 'open' | 'closed' | 'other'.

    'other' is deliberately NOT assumed to mean dormant: an unmapped code is
    surfaced as a flag, never guessed (CLAUDE.md). Dormant and Inactive land here
    — they are neither closed nor answering "why is this OPEN account excluded".
    """
    d = (desc or "").strip().lower()
    if d:
        if d.startswith(_CLOSED_PREFIX):
            return "closed"
        if d.startswith(_OPEN_PREFIX):
            return "open"
        return "other"
    c = (code or "").strip().upper()
    open_codes, closed_codes = _code_sets()
    if c in closed_codes:
        return "closed"
    if c in open_codes:
        return "open"
    return "other"


def accessors(H):
    """Bind the ODD vocabulary to one header map `H` = {column name: index}.

    Returned as a namespace rather than module functions because each script
    builds its own header map (and responder_activity builds it inside a
    function), so there is no single global to close over.
    """

    def g(r, name):
        """Stripped cell value, or '' when the column or cell is absent."""
        i = H.get(name)
        return r[i].strip() if i is not None and i < len(r) else ""

    def fnum(r, name):
        """Numeric cell value, 0.0 for blank/absent/unparseable.

        Behaviour is unchanged from the three implementations it replaces: they
        agreed on every input, differing only in whether '-' was special-cased
        before float() or allowed to fail into the same 0.0.
        """
        v = g(r, name).replace(",", "").replace("$", "")
        if v in ("", "-"):
            return 0.0
        try:
            return float(v)
        except ValueError:
            return 0.0

    def swipes(r, m):
        """Signature + PIN transaction COUNT for month m ('Jul26')."""
        return fnum(r, f"{m} Sig #") + fnum(r, f"{m} PIN #")

    def spend(r, m):
        """Signature + PIN purchase DOLLARS for month m."""
        return fnum(r, f"{m} Sig $") + fnum(r, f"{m} PIN $")

    def nsf(r, m):
        """NSF/OD ITEM COUNT for month m (the MTD column).

        ITEMS, not dollars. The ODD carries no OD-fee dollar column at all —
        NSF revenue comes from the client workbook ('Total NSF Revenue'), never
        from here. This docstring used to say "fee income", which contradicted
        every consumer: charts_gen titles it "NSF/OD Items", metrics_gen names
        it items12/nsf_last_items, and build_lift_matrix multiplies it BY a
        per-item fee. Confirmed against six 2026.08 extracts (1539, 1705, 1204,
        1075, 1549, 1218): every populated `{m} MTD` cell is a non-negative
        INTEGER — 0/1/2/3/... with smoothly decaying frequency, not one value
        carrying cents, and no clustering on multiples of any fee amount. `{m} YTD` is
        the calendar-year cumulative of the same integers (19,552 of 19,573
        sampled 1539 accounts reconcile exactly).
        """
        return fnum(r, f"{m} MTD")

    def personal(r):
        """True only for an explicit 'No' in Business?.

        A blank is NOT personal — it is unknown, and falls into the same
        'other' bucket product_mix_slide reports. Comparison is
        case-insensitive; every ODD seen so far writes 'Yes'/'No' exactly, but
        the old exact-case test would have silently reclassified the whole book
        on a processor that wrote 'NO'.
        """
        return g(r, "Business?").lower() == "no"

    def business(r):
        """True only for an explicit 'Yes' in Business?. A blank is not business."""
        return g(r, "Business?").lower() == "yes"

    def hascard(r):
        return g(r, "Debit?").lower() == "yes"

    def isopen(r):
        sd = g(r, "Stat Desc")
        return sd.startswith("Open") or sd.startswith("Active") or sd in OPEN_STATUSES

    return SimpleNamespace(
        g=g, fnum=fnum, swipes=swipes, spend=spend, nsf=nsf,
        personal=personal, business=business, hascard=hascard, isopen=isopen,
    )
