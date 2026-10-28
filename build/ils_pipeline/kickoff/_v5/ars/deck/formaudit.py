# Ported from v5 02-Scripts/ars/deck/formaudit.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
"""Form census: the deck's visual variety, measured on every build.

Quantifies T3 of DESIGN/review-trends.md ("vary the form" — James's
most repeated design note: "too much blue, repeated layout"). Every
chart helper records the chart function that drew each slide; the
census walks the FINAL slide order and reports, per chapter, which
form each slide took. Concentration — long same-form runs, one form
carrying most of a chapter — is the anti-pattern the review rounds
kept flagging, so the build makes it visible instead of waiting for
the notes pane.

A slide that draws no chart (tables, tile grids, dashboards built
from shapes) is counted as "layout-only": the census measures CHART
form concentration; layout variety stays a review judgment.
"""

from __future__ import annotations


def census(final_slides, placed) -> list[dict]:
    """One row per content slide, in final deck order.

    Each row: {"chapter": str, "title": str, "form": str}.
    ``form`` is the drawing chart function's name ("+"-joined when a
    slide composes several), or "layout-only".
    """
    by_obj = {id(e["sl"]): e for e in placed}
    rows: list[dict] = []
    chapter = "Front matter"
    for sl in final_slides:
        e = by_obj.get(id(sl))
        if e is None:
            continue
        if e["kind"] == "chapter":
            chapter = e["title"]
            continue
        forms = e.get("forms") or []
        rows.append({"chapter": e.get("chapter") or chapter,
                     "title": e["title"],
                     "id": e.get("tracked") or e["title"],
                     "form": "+".join(forms) if forms else "layout-only"})
    return rows


def runs(rows: list[dict], min_len: int = 3) -> list[dict]:
    """Consecutive same-form stretches within a chapter, longest first.

    Runs of ``min_len`` or more are the T3 finding: adjacent slides
    that look alike. "layout-only" runs count too — a chapter of
    back-to-back table slides reads as flat as one of repeated bars.
    """
    found: list[dict] = []
    current: list[dict] = []
    for row in rows + [{"chapter": None, "form": None}]:        # sentinel
        if current and (row["chapter"] != current[0]["chapter"]
                        or row["form"] != current[0]["form"]):
            if len(current) >= min_len:
                found.append({"chapter": current[0]["chapter"],
                              "form": current[0]["form"],
                              "length": len(current),
                              "titles": [r["title"] for r in current]})
            current = []
        if row["form"] is not None:
            current.append(row)
    found.sort(key=lambda r: -r["length"])
    return found


def concentration(rows: list[dict]) -> list[tuple[str, int]]:
    """(form, slide count), most used first — the deck's form budget."""
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["form"]] = counts.get(r["form"], 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])
