"""Checks on a built ILS analysis deck for the defects a slide-layout validator cannot see.

validate_deck reads layout, words and notes; it passes a table whose decline column is all zeros because the extract was
a year old, a peer slide that ranks an account type with no activity "Lowest" on every measure, and a deck whose
section quietly failed to build. These checks read the deck and its figures index for exactly those, so a build can be
judged by a script, not only by eye.

    FAIL    a section that failed to build (its slides are missing)
    REVIEW  a dated extract that ends well before the data date; a table column that is all zero or all n/a; a table
            with a header and no rows; a peer slide that is "Lowest" on every measure; a "No data for this chart" box

    python -m ils_review.deck_checks <deck.pptx> [figures_index.json]
"""
from __future__ import annotations

import json
import os
import re
import sys

ZEROISH = re.compile(r"^\s*(\$?\s*0(\.0+)?\s*%?|\$0\.00|0\.0%|0%)\s*$")
NA = re.compile(r"^\s*(n/a|—|-)\s*$", re.I)


def _cells(table):
    return [[c.text.strip() for c in r.cells] for r in table.rows]


def table_findings(rows, where):
    """A table with no data rows, or a data column (not the first) whose every value is zero or every value is n/a."""
    out = []
    if not rows:
        return out
    head, body = rows[0], [r for r in rows[1:] if any(c for c in r)]
    body = [r for r in body if not r[0].lower().startswith(("total", "all "))] or body
    if not body:
        return [("REVIEW", f"{where}: a table with a header and no rows")]
    if len(body) < 2:
        return out                      # one row cannot show a whole column empty
    for j in range(1, len(head)):
        col = [r[j] for r in body if j < len(r)]
        if not col:
            continue
        if all(NA.match(v) for v in col):
            out.append(("REVIEW", f"{where}: column '{head[j]}' is n/a in every row"))
        elif all(ZEROISH.match(v) for v in col):
            out.append(("REVIEW", f"{where}: column '{head[j]}' is zero in every row"))
    return out


def deck_findings(path):
    from pptx import Presentation
    out = []
    prs = Presentation(path)
    for i, s in enumerate(prs.slides, 1):
        texts = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame]
        title = next((t.strip() for t in texts if t.strip()), "")[:60]
        where = f"slide {i} ({title})"
        joined = " ".join(texts)
        if "No data for this chart" in joined:
            out.append(("REVIEW", f"{where}: a chart had no data and is stated as such"))
        ranks = re.findall(r"(Lowest|Highest|\d+(?:st|nd|rd|th) highest) of \d+ clients", joined)
        if len(ranks) >= 3 and all(r == "Lowest" for r in ranks):
            out.append(("REVIEW", f"{where}: 'Lowest' on every peer measure; check the account type has activity"))
        for sh in s.shapes:
            if getattr(sh, "has_table", False) and sh.has_table:
                out += table_findings(_cells(sh.table), where)
    return out


def index_findings(index_path):
    out = []
    try:
        with open(index_path, encoding="utf-8") as fh:
            idx = json.load(fh)
    except (OSError, ValueError):
        return [("REVIEW", f"figures index not readable: {index_path}")]
    for note in idx.get("skipped_or_noted") or []:
        n = str(note)
        if "failed to build" in n:
            out.append(("FAIL", n[:240]))
        elif " extract ends " in n or "holds no dated rows" in n or "produced no slides and gave no reason" in n \
                or n.startswith("Contact Us slide not added"):
            out.append(("REVIEW", n[:240]))
    return out


def check(deck_path, index_path=None):
    """[(level, message)] for a built deck; FAIL first."""
    found = deck_findings(deck_path)
    if index_path is None:
        guess = os.path.join(os.path.dirname(deck_path), "charts", "figures_index.json")
        index_path = guess if os.path.exists(guess) else None
    if index_path:
        found = index_findings(index_path) + found
    return sorted(found, key=lambda f: f[0] != "FAIL")


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    if not a:
        print(__doc__)
        return 2
    found = check(a[0], a[1] if len(a) > 1 else None)
    for level, msg in found:
        print(f"{level:6} {msg}")
    fails = sum(1 for f in found if f[0] == "FAIL")
    print(f"{fails} FAIL, {len(found) - fails} REVIEW")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
