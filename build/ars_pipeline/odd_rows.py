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
import io
import os
import re
import zipfile
from types import SimpleNamespace


# ---------------------------------------------------------------- the ODD member
# ONE rule for which file inside an ODDD zip is the ODD extract. Several zips also carry
# the month's transaction file as a second .csv (1038, 1549, ...), sometimes the larger of
# the two; taking the first or the largest .csv reads the transaction dump instead and
# metrics_gen dies with 'itemgetter expected 1 argument, got 0'. Ten files each carried
# their own version of this rule and they disagreed (oddd_optimize matched "-ODD" in one
# case only and fell back to the FIRST member; the issue pages gave up without a fallback),
# so a zip whose ODD member is named in lower case would have been read by the deck and
# skipped by the pack. Pick by name ("-odd" or "_v2_", case-insensitive), else the
# largest .csv. `tests/test_odd_source.py` fails if the literal reappears anywhere else.
_ODD_NAME_MARKS = ("-odd", "_v2_")


def odd_member(zf):
    """The ODD extract member of an open ZipFile. Raises FileNotFoundError when it has no .csv."""
    members = [i for i in zf.infolist() if i.filename.lower().endswith(".csv") and not i.is_dir()]
    if not members:
        raise FileNotFoundError(f"no .csv inside {getattr(zf, 'filename', zf)}")
    named = [i for i in members
             if any(mark in os.path.basename(i.filename).lower() for mark in _ODD_NAME_MARKS)]
    pick = named[0] if named else max(members, key=lambda i: i.file_size)
    return pick.filename


def odd_source(path, encoding="latin-1"):
    """-> (factory, source_name). factory() opens a FRESH decoded text stream over the ODD
    extract: the member of a .zip, read in place and never extracted, or the plain file.
    `source_name` is the file's basename, whose "(MMDDYY_HHMMSS)" stamp month_complete reads."""
    path = str(path)
    if path.lower().endswith(".zip"):
        zf = zipfile.ZipFile(path)
        member = odd_member(zf)

        def factory():
            return io.TextIOWrapper(zf.open(member), encoding=encoding, errors="replace", newline="")
        return factory, os.path.basename(member)

    def factory():
        return open(path, encoding=encoding, errors="replace", newline="")
    return factory, os.path.basename(path)


def open_odd(path, encoding="latin-1"):
    """-> (open text handle, source_name). One-shot form of `odd_source`."""
    factory, name = odd_source(path, encoding=encoding)
    return factory(), name


def extract_odd(path, out_dir):
    """Extract ONLY the ODD member of a zip into `out_dir` and return its path. The other
    members (the transaction file) are never written to disk."""
    with zipfile.ZipFile(str(path)) as zf:
        return zf.extract(odd_member(zf), str(out_dir))


# ---------------------------------------------------------------- Reg E election
# ONE reading of the `<Mon> Reg E Desc` wording, shared by oddd_optimize (the pack and
# its unmapped-value flags) and metrics_gen (every Reg E figure in the deck). There
# were two, and they disagreed: metrics_gen matched only "opt in / opt-in / optin",
# so extracts worded "Opted In" / "Opted Out" (1776 CoastHills and about a dozen
# others) put every account in "no election" and the decks showed Reg E opt-in at
# 0.0% while the optimizer, reading the same file, found both (2026-09-16).
#
# Returns the canonical label, "" for not applicable (blank, ineligible, exempt —
# excluded like a blank), or None for wording no rule covers, which the caller must
# stop on and ask about rather than guess. Confirmed by Aaron, 2026-09-16: Yes/Y → in;
# No/N, Revoked → out; Failed to Respond, No Decision, Did Not Reply (1121), D (1147)
# → default; Ineligible, Exempt, "Tracking Type N Does Not Exist" (1807), "No Vaule -
# No Reg E" (1798) → not applicable. Aaron, 2026-09-17: "Anything else" (1217) → opt OUT
# (it was not applicable); Accepted → in, Declined → out.
REGE_IN, REGE_OUT, REGE_DEFAULT = "Reg E Opt In", "Reg E Opt Out", "Reg E Default"
_REGE_EXACT = {"yes": REGE_IN, "y": REGE_IN, "no": REGE_OUT, "n": REGE_OUT, "d": REGE_DEFAULT,
               "ineligible": "", "exempt": "", "no vaule no reg e": "", "anything else": REGE_OUT,
               "accepted": REGE_IN, "declined": REGE_OUT}
_REGE_NA = re.compile(r"^tracking type \d+ does not exist$")
_REGE_OUT_RX = re.compile(r"declin|opt out|optout|opted out|revoked")
_REGE_IN_RX = re.compile(r"accept|opt in|optin|opted in")
_REGE_DEFAULT_RX = re.compile(r"default|no response|no election|no elect|recevied|failed to respond|no decision|did not reply")


def rege_label(text):
    """Canonical Reg E label for one cell: REGE_IN / REGE_OUT / REGE_DEFAULT, "" (not applicable), or None (unmapped)."""
    t = " ".join(str(text or "").replace("\x00", "").lower().replace("-", " ").split())
    if not t:
        return ""
    if t in _REGE_EXACT:
        return _REGE_EXACT[t]
    if _REGE_NA.match(t):
        return ""
    if _REGE_OUT_RX.search(t):
        return REGE_OUT
    if _REGE_IN_RX.search(t):
        return REGE_IN
    if _REGE_DEFAULT_RX.search(t):
        return REGE_DEFAULT
    return None

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

    **These run tens of millions of times per client and the ODD is not the cost.**
    Decompressing and parsing a 49 MB / 52,853-row / 405-column extract takes 1.0s;
    `metrics_gen` over the same file took 9s, and a profile put 11.3s of cumulative
    time in `g` alone at 13.6M calls (2026-09-11). So the work here is arithmetic on
    rows, not I/O, and the optimisations below are all about not redoing per ROW what
    is constant per COLUMN:

      * constant columns ("Business?", "Debit?", "Stat Desc") resolve their index
        once, at bind time;
      * `swipes`/`spend`/`nsf` used to build an f-string column name on EVERY call
        ("Jul26 Sig #") and hash that long string into H. The five indices for a
        month are now resolved once and cached under the short month key;
      * `fnum` tries `float()` on the raw cell first, because the overwhelming
        majority of cells are already plain numbers, and only falls back to the
        strip/replace path when that raises.

    Every one of these is output-identical by construction, and `tests/test_odd_rows.py`
    pins the equivalence case by case. Do NOT "simplify" them back: this vocabulary
    is shared by metrics_gen, the slide builders and responder_activity, and the
    reason it exists at all is that three separate implementations drifted.
    """
    _hget = H.get                      # bound once: attribute lookup is not free at 13M calls

    def g(r, name):
        """Stripped cell value, or '' when the column or cell is absent."""
        i = _hget(name)
        return r[i].strip() if i is not None and i < len(r) else ""

    def _num_at(r, i):
        """`fnum` by INDEX. The fast path is `float()` on the raw cell: it already
        tolerates surrounding whitespace, and raises on exactly the inputs the slow
        path exists for ('', '-', '1,234', '$50', anything unparseable)."""
        if i is None or i >= len(r):
            return 0.0
        v = r[i]
        try:
            return float(v)
        except ValueError:
            pass
        v = v.strip().replace(",", "").replace("$", "")
        if v in ("", "-"):
            return 0.0
        try:
            return float(v)
        except ValueError:
            return 0.0

    def fnum(r, name):
        """Numeric cell value, 0.0 for blank/absent/unparseable.

        Behaviour is unchanged from the three implementations it replaces: they
        agreed on every input, differing only in whether '-' was special-cased
        before float() or allowed to fail into the same 0.0.
        """
        return _num_at(r, _hget(name))

    # month key -> the per-month column indices, resolved once. Building
    # "Jul26 Sig #" and hashing it was happening on every call, for every month,
    # for every row.
    _MC_SIGN, _MC_PINN, _MC_SIGD, _MC_PIND, _MC_MTD = range(5)
    _moncols = {}

    def _mc(m):
        t = _moncols.get(m)
        if t is None:
            t = (_hget(f"{m} Sig #"), _hget(f"{m} PIN #"),
                 _hget(f"{m} Sig $"), _hget(f"{m} PIN $"), _hget(f"{m} MTD"))
            _moncols[m] = t
        return t

    def swipes(r, m):
        """Signature + PIN transaction COUNT for month m ('Jul26')."""
        c = _mc(m)
        return _num_at(r, c[_MC_SIGN]) + _num_at(r, c[_MC_PINN])

    def spend(r, m):
        """Signature + PIN purchase DOLLARS for month m."""
        c = _mc(m)
        return _num_at(r, c[_MC_SIGD]) + _num_at(r, c[_MC_PIND])

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
        return _num_at(r, _mc(m)[_MC_MTD])

    _i_business = _hget("Business?")
    _i_debit = _hget("Debit?")
    _i_stat = _hget("Stat Desc")
    _i_code = _hget("Stat Code")
    _open_lower = frozenset(s.lower() for s in OPEN_STATUSES)
    # Only resolved when the extract carries Stat Code; importing oddd_optimize is not free.
    _open_codes = frozenset(_code_sets()[0]) if _i_code is not None else frozenset()

    def personal(r):
        """True only for an explicit 'No' in Business?.

        A blank is NOT personal — it is unknown, and falls into the same
        'other' bucket product_mix_slide reports. Comparison is
        case-insensitive; every ODD seen so far writes 'Yes'/'No' exactly, but
        the old exact-case test would have silently reclassified the whole book
        on a processor that wrote 'NO'.
        """
        i = _i_business
        return (r[i].strip().lower() == "no") if i is not None and i < len(r) else False

    def business(r):
        """True only for an explicit 'Yes' in Business?. A blank is not business."""
        i = _i_business
        return (r[i].strip().lower() == "yes") if i is not None and i < len(r) else False

    def hascard(r):
        i = _i_debit
        return (r[i].strip().lower() == "yes") if i is not None and i < len(r) else False

    def isopen(r):
        """Open by Stat Desc, compared case-insensitively; by Stat Code only when the
        description is blank, using the Aaron-confirmed STAT_CODE_MAP (O / A = Open).

        It used to be case-sensitive and never read the code, unlike `status_class` and
        oddd_optimize's classifier beside it. On 2026-09-14 that left six clients with no
        open account at all: 1637 writes 'open', 1680 'ACTIVE', 1759 'OPEN/ACTIVE', and
        1743, 1746 and 1815 leave Stat Desc blank with codes A / O. It also dropped 1,755
        'inactive' (lower case) 1509 Texas Bay accounts that its Product Mix slide counted.
        """
        i = _i_stat
        sd = r[i].strip() if i is not None and i < len(r) else ""
        if sd:
            low = sd.lower()
            return low.startswith("open") or low.startswith("active") or low in _open_lower
        j = _i_code
        return j is not None and j < len(r) and r[j].strip().upper() in _open_codes

    return SimpleNamespace(
        g=g, fnum=fnum, swipes=swipes, spend=spend, nsf=nsf,
        personal=personal, business=business, hascard=hascard, isopen=isopen,
    )
