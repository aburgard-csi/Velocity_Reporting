#!/usr/bin/env python3
"""registry.py — the programs the page can present, and the one function that builds the view model.

A program is a module in `programs/` with four names:

    KEY, LABEL      "ars", "ARS"
    load(ctx)       read the program's data pack through the Tracer; raise PackMissing when it is not there
    build(ctx, p)   -> {"screens": [...], "summary": {"headline", "kpis", "open"}}

`REGISTRY` lists them in the order the page shows them. A program that is registered but not built
yet is a STUB entry: it appears in the switcher, greyed, saying so, rather than being absent — so a
client's product list is visible on the page even where a screen does not exist yet. `Combined` is
not a program: it is the page's overview, one card per program that built, each opening that
program's first screen.

Import-safe.
"""
import datetime
import importlib

from review_page import PRODUCT_NAME
from review_page import blocks as B
from review_page import packs as PK
from review_page import story
from review_page.common import Ctx
from review_page.trace import audit

# key, label, module under review_page.programs (None = not built yet)
REGISTRY = [
    ("ars", "ARS", "ars"),
    ("analysis", "ARS analysis", "companion"),
    ("ti", "Transaction Intelligence", "ti"),
    ("ics", "ICS", "ics"),
    ("mrpc", "MRPC", "mrpc"),
    ("cashplease", "CashPlease", "cashplease"),
]


def build_program(ctx, key, label, module):
    entry = {"key": key, "label": label, "state": "ready", "note": None, "fix": None, "screens": [], "summary": None, "hidden": False}
    if module is None:
        entry.update(state="stub", note=f"{label} is not on the page yet.")
        return entry
    mod = importlib.import_module(f"review_page.programs.{module}")
    entry["hidden"] = bool(getattr(mod, "HIDDEN", False))
    try:
        p = mod.load(ctx)
    except PK.PackMissing as e:
        entry.update(state="missing", note=f"{label} is not on the page: {e.what}.", fix=e.fix)
        return entry
    except Exception as e:                      # a reader that fails must not take the other programs down
        entry.update(state="error", note=f"{label} could not be read: {type(e).__name__}: {e}")
        return entry
    try:
        built = mod.build(ctx, p)
    except Exception as e:
        entry.update(state="error", note=f"{label} could not be built: {type(e).__name__}: {e}")
        return entry
    entry["screens"] = built["screens"]
    entry["summary"] = built["summary"]
    entry["deck"] = p.get("deck")
    entry["client_name"] = built.get("client_name")
    return entry


def build_model(client, period, root=None, programs=None):
    """(model, tracer, problems). `problems` is the traceability audit; the server refuses to serve a
    model with any, and says what they are."""
    PK.check_ids(client, period)
    ctx = Ctx(client=str(client), period=period, root=root)
    out = []
    for key, label, module in REGISTRY:
        if programs and key not in programs:
            continue
        out.append(build_program(ctx, key, label, module))
    name = next((e.get('client_name') for e in out if e.get('client_name')), None) or str(client)
    ready = [e for e in out if e["state"] == "ready" and not e["hidden"] and e["summary"]]
    combined = {"screens": [_overview(ready)]} if len(ready) > 1 else None
    model = {"product": PRODUCT_NAME, "client": {"id": str(client), "name": name}, "period": period, "month": ctx.month_long,
             "generated": datetime.datetime.now().isoformat(timespec="minutes"),
             "programs": out, "combined": combined, "story": _story(out)}
    problems = audit(model, ctx.tracer)
    return model, ctx.tracer, problems


def _story(programs):
    """The storyline, when the page has the program the story starts from (ARS)."""
    if not any(e["key"] == "ars" and e["state"] == "ready" for e in programs):
        return None
    return story.resolve(programs)


def _overview(ready):
    cards = []
    for e in ready:
        s = e["summary"]
        cards.append({"program": e["key"], "label": e["label"], "headline": s["headline"], "kpis": s["kpis"], "open": s["open"]})
    return {"id": "overview", "title": "All programs", "kicker": "Combined view",
            "headline": "Every program on this client, one tile each. Open any tile to go to its first screen.",
            "blocks": [{"t": "cards", "cards": cards}], "notes": [],
            "sources": [{"title": "Where these figures come from",
                         "text": "Each tile reads from the screen it opens. Open any screen and press S for the source lines of the deck slides that screen mirrors."}]}
