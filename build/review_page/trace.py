#!/usr/bin/env python3
"""trace.py — every figure on the page traces to the data pack (checked, not hoped for).

A program module never types a number. It reads a pack through `Pack.get(...)`, which records the
number (and every number inside a list it returns) in the Tracer's ledger, or it derives one with
`Tracer.derive(value, formula, *inputs)`, which records the result together with the inputs it came
from. `audit(model, tracer)` then walks the finished view model and reports

  * a number in the model that is in no pack and no derivation,
  * a number in a sentence (headline, caption, note) that no pack figure explains under any of the
    forms a sentence prints (1,234 / 12.3% / $1.2M / $832K), and
  * a banned word in anything the page authors itself ("lift" as prose; "Lift Matrix" is a name).

Source lines quoted from the deck notes are exempt from the number test (they are quoted, not
computed); the tests check they are present.

Import-safe.
"""
import math
import re

MISSING = object()


class Tracer:
    def __init__(self):
        self.vals = []        # every number a pack gave us
        self.derived = []     # {"value", "formula", "inputs"}
        self.reads = []       # (pack name, path) — the audit trail

    def see(self, v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            if not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                self.vals.append(float(v))
        elif isinstance(v, dict):
            for x in v.values():
                self.see(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                self.see(x)

    def has(self, x, tol=1e-9):
        return any(abs(x - v) <= tol * max(1.0, abs(v)) for v in self.vals)

    def derive(self, value, formula, *inputs):
        """Record a computed figure. Its inputs must already be in the ledger, so a derivation can
        only combine what a pack gave us."""
        for i in inputs:
            if isinstance(i, bool) or i is None:
                continue
            if isinstance(i, (int, float)) and not self.has(i):
                raise AssertionError(f"derive({formula!r}): input {i!r} is not a pack figure")
        self.derived.append({"value": value, "formula": formula, "inputs": list(inputs)})
        self.see(value)
        return value


class Pack:
    """A named data pack (the dict a JSON file held), read through the ledger."""

    def __init__(self, name, data, tracer, path=None):
        self.name, self.data, self.t, self.path = name, data or {}, tracer, path

    def _walk(self, path):
        cur = self.data
        for p in path:
            try:
                cur = cur[p]
            except (KeyError, IndexError, TypeError):
                return MISSING
        return cur

    def has(self, *path):
        v = self._walk(path)
        return v is not MISSING and v is not None

    def get(self, *path, default=None):
        v = self._walk(path)
        if v is MISSING:
            return default
        self.t.reads.append((self.name, ".".join(str(p) for p in path)))
        self.t.see(v)
        return v


# ----------------------------------------------------------------- sentences
BANNED = ["robust", "comprehensive", "leverage", "seamless", "delve", "engine", "lever",
          "ramping", "healthy", "predominantly", "companion", "seasoned book", "annuity"]
_BANNED_RX = re.compile(r"\b(" + "|".join(re.escape(b) for b in BANNED) + r")\b", re.I)
_LIFT_RX = re.compile(r"\blift\b", re.I)

# Policy constants a sentence may state without a pack figure behind them: the 2 : 1 revenue
# guarantee, the 3 : 1 line below which the guarantee is a live conversation, the trailing-12-month
# window the deck's cohorts use, and the 'per 1,000' unit of a rate.
POLICY = (2.0, 3.0, 12.0, 1000.0)

_MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
_DATEISH = [
    re.compile(_MONTHS + r"\.?\s*'?\d{2,4}\b"),                 # Sep 2026, Aug 26, Sep'26
    re.compile(_MONTHS + r"\s+\d{1,2}\b"),                      # Nov 4
    re.compile(r"\b\d{4}[-./]\d{2}(?:[-./]\d{2})?\b"),          # 2026-10, 2026.10
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b(?:19|20)\d{2}\b"),                          # a bare year
    re.compile(r"\b\d+\s*:\s*1\b"),                             # 2 : 1 (the guarantee floors)
    re.compile(r"\bBranch\s+\d+\b"),                              # a branch NUMBER is a name, not a figure
]
_NUM_RX = re.compile(r"(?<![\w.])-?\$?(\d[\d,]*(?:\.\d+)?)\s*(%|[kKmMbB]\b)?")


def numbers_in(text):
    s = str(text)
    for rx in _DATEISH:
        s = rx.sub(" ", s)
    out = []
    for m in _NUM_RX.finditer(s):
        raw = m.group(1).rstrip(",").replace(",", "")
        if not raw:
            continue
        dp = len(raw.split(".")[1]) if "." in raw else 0
        out.append((float(raw), dp, (m.group(2) or "").lower(), m.group(0).strip()))
    return out


def explained(n, dp, suffix, t):
    """Is the number a sentence printed some form of a pack figure (or its magnitude)?"""
    if n in POLICY:
        return True
    half = 0.5 * 10 ** (-dp) + 1e-9
    scale = {"k": 1e3, "m": 1e6, "b": 1e9}.get(suffix, 1.0)
    for v in t.vals:
        a = abs(v)
        if abs(a / scale - n) <= half:
            return True
        if suffix == "%" and abs(a * 100 - n) <= half:     # stored as 0.721, printed 72.1%
            return True
    return False


def _walk(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, path + (k,))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _walk(v, path + (i,))
    else:
        yield path, obj


# keys whose strings are quoted from a source (the deck's notes, a workbook name): not authored here
# "note" (singular) is a program's own state message (a path, an exception); "fix" a command to run; "generated" a stamp
QUOTED = {"sources", "note", "fix", "what", "generated", "deck"}
# keys whose strings are labels / identifiers, not sentences (a branch id, a tier, a month label)
LABELISH = {"id", "key", "fmt", "t", "tone", "color", "x", "name", "label", "cats", "cols", "rowsl",
            "unit", "drill", "program", "state", "kind", "series_name", "client", "period", "screen"}


# identifiers: ids of screens, blocks and variants. They are names, never read as prose or figures.
IDENT = {"id", "open", "go", "drill", "table", "program", "key", "t", "ref", "prog"}


def audit(model, t):
    """Problems found in a finished view model; empty means every figure traces."""
    problems = []
    for path, v in _walk(model):
        keys = [p for p in path if isinstance(p, str)]
        if any(k in QUOTED for k in keys) or (keys and keys[-1] in IDENT):
            continue
        if isinstance(v, bool) or v is None:
            continue
        where = ".".join(str(p) for p in path)
        if isinstance(v, (int, float)):
            if not t.has(v):
                problems.append(f"number not in any pack or derivation: {v!r} at {where}")
        elif isinstance(v, str):
            m = _BANNED_RX.search(v)
            if m:
                problems.append(f"banned word {m.group(0)!r} at {where}: {v[:60]!r}")
            for lm in _LIFT_RX.finditer(v):
                around = v[max(0, lm.start() - 1): lm.end() + 8].lower()
                if "lift matrix" not in around:
                    problems.append(f"'lift' as prose at {where}: {v[:60]!r}")
            if keys and keys[-1] in LABELISH and len(v) < 40:
                continue
            for n, dp, suf, raw in numbers_in(v):
                if not explained(n, dp, suf, t):
                    problems.append(f"figure {raw!r} in text at {where} matches no pack figure: {v[:80]!r}")
    return problems


# ----------------------------------------------------------------- movement wording
BAND = 2.0   # +/-2%


def change_pct(old, new):
    if old in (None, 0) or new is None:
        return None
    return 100.0 * (new - old) / abs(old)


def movement(measure, old, new, fmt, subject="the program"):
    """The +/-2% sentence rule (CLAUDE.md, 2026-08-31): the verb is DERIVED, never written.
    within +/-2% -> almost flat | positive -> state the increase | negative -> did not have an impact."""
    pct = change_pct(old, new)
    if pct is None:
        return f"{measure}: no earlier figure to compare with."
    if abs(pct) <= BAND:
        return f"{measure} is almost flat ({fmt(old)} → {fmt(new)})."
    if pct > 0:
        return f"{measure} increased {pct:.1f}% ({fmt(old)} → {fmt(new)})."
    return f"{subject} did not have an impact on {measure} ({fmt(old)} → {fmt(new)}, {pct:.1f}%)."
