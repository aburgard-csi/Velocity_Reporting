"""The slide ledger: every slide of the Transaction Intelligence and Competition chapters (the competition layers included), and what
became of it in this build (fs-06). Nothing leaves the deck without a line saying why.

Status, in order of precedence:
    tossed   `ti/slides.json` says toss (a reviewed decision, for every client)
    hidden   the chapter declined it for this client (its figures are not in the client's files)
    merged   drawn as one slide with another (`ti/deck/combine.py`)
    drawn    in the deck

Written beside the decks as `ti_slide_ledger.csv` by `ti_build`.
"""
from __future__ import annotations

import csv
from pathlib import Path

COLUMNS = ["chapter", "slide", "status", "reason"]


def rows(pack: dict | None = None, selection_path=None) -> list[list[str]]:
    from ti import chapters_txn as X
    from ti import selection
    from ti.deck import txn_layers

    hidden: dict[str, str] = {}
    for lens_hidden in ((pack or {}).get("hidden_declined") or {}).values():
        for h in lens_hidden:
            hidden.setdefault(h["title"], h["reason"])
    merged: dict[str, tuple[str, str]] = {}
    for a, b, topic, *_rest in tuple(X.TI_COMBINED) + tuple(X.COMP_COMBINED):
        merged[a] = (topic, X.TITLES[b])
        merged[b] = (topic, X.TITLES[a])

    out = []
    # the layers slides are Competition slides too: a slide the layers section declines or the register tosses is listed
    for chapter, builders in (("Transaction Intelligence", X.TI_BUILDERS),
                              ("Competition", list(X.COMP_BUILDERS) + list(txn_layers.BUILDERS))):
        for builder in builders:
            name = builder.__name__
            title = X.TITLES[name]
            topic, other = merged.get(name, (title, None))
            names = {title, topic}
            if any(not selection.slide_kept(t, selection_path) for t in names):
                out.append([chapter, title, "tossed", "tossed in ti/slides.json"])
            elif any(t in hidden for t in names):
                why = hidden.get(title) or hidden.get(topic)
                out.append([chapter, title, "hidden", why])
            elif other:
                out.append([chapter, title, "merged", f"drawn with '{other}' as '{topic}'"])
            else:
                out.append([chapter, title, "drawn", ""])
    return out


def write(path, ledger_rows) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(ledger_rows)
    return str(path)


def summary(ledger_rows) -> str:
    n = {}
    for r in ledger_rows:
        n[r[2]] = n.get(r[2], 0) + 1
    return ", ".join(f"{n[k]} {k}" for k in ("drawn", "merged", "hidden", "tossed") if k in n)
