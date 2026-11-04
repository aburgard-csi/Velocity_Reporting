"""
slide_inventory.py — every program's slide list, from the templates and the builders, never from a
client's deck.

Aaron, 2026-10-29: "the decks all carry the same slides, because they're all built using the same
processes. We shouldn't need to scan the decks." CSM Sheila's Slide Review used to read each program's
list out of the newest decks in Outputs, which was slow over the share and, for ICS, gave the
referrals-only shape whenever the newest decks had no workbook. The list here is the build process:

    ARS, ICS, MRPC, CP   the template shell's slides (templates/<program>_template.pptx), with the
                         slides each builder adds spliced in where the builder puts them (ADDED)
    TI                   build/ars_pipeline/ti/slides.json, the cut's register of chapters and slides
    COMP                 the titles James's view modules give their slides (build/ars_pipeline/
                         combined_insight_slides.py, james_view_slides.py, spend_trend_slides.py,
                         sustained_split_slide.py), which the ARS Companion deck is made of

The shell slides every deck shares (cover, Summit, agenda, dividers, Questions, Contact) are left out,
as the Review never voted on them. A conditional slide (the Revenue Guarantee, a direct-mail list)
is listed with its condition in `source`, so a voter sees why their own deck may not carry it.

Import-safe: python-pptx on four repo files and a JSON read, cached until a file changes.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = {"ARS": "ars_template.pptx", "ICS": "ics_template.pptx", "MRPC": "mrpc_template.pptx",
             "CP": "cashplease_template.pptx"}
TI_REGISTER = REPO / "build" / "ars_pipeline" / "ti" / "slides.json"
COMPANION_MODULES = ("combined_insight_slides.py", "james_view_slides.py", "spend_trend_slides.py",
                     "sustained_split_slide.py")
PROGRAMS = ("ARS", "ICS", "MRPC", "CP", "TI", "COMP")

# The shell: in every deck, never voted on. A product name is the cover and the divider; "Appendix" on its
# own is the ARS appendix divider (an ICS "Appendix: Monthly Detail" page is a slide).
_SHELL_PREFIXES = ("questions", "contact us", "agenda", "the executive summit", "executive summit",
                   "account revenue solution", "invitation checking", "myrewards premium cards", "cashplease®",
                   "cashplease system")
_SHELL_EXACT = ("appendix", "cashplease")

# The slides a builder adds to its shell, where it puts them, and where that is written. An anchor is the
# shell title the builder itself anchors on (its after_title / before_title), so this list reads like the
# builder. `where` is "after" or "before".
ADDED = {
    "ARS": [
        ("Excluded Accounts", "after", "Product Mix & ARS Eligibility",
         "build/ars_pipeline/excluded_accounts_slide.py"),
        ("Revenue Guarantee", "after", "ARS Financial Performance",
         "build/ars_pipeline/revenue_guarantee_slide.py — on a deck whose ratio is below 3 : 1"),
        ("Branch Reference", "before", "Program Reach — Cumulative Responders",
         "build/ars_pipeline/build_ars_gen.py (add_branch_reference_slide) — when branch names resolve; "
         "the first appendix page"),
        # The branch-detail tables, after the Branch Reference and ahead of the shell's appendix pages; each
        # runs to as many pages as the branches need ("(1 of 2)"), so the title here is the family's.
        ("Appendix: Take Rate by Branch", "before", "Program Reach — Cumulative Responders",
         "build/ars_pipeline/branch_appendix_slides.py — the full branch list, moved from the main deck "
         "(2026-11-02)"),
        ("Appendix: Reg E Opt-In by Branch", "before", "Program Reach — Cumulative Responders",
         "build/ars_pipeline/branch_appendix_slides.py — all open personal debit-card holders, by branch"),
        ("Appendix: Reg E New Accounts by Branch", "before", "Program Reach — Cumulative Responders",
         "build/ars_pipeline/branch_appendix_slides.py — accounts opened in the last 12 months, by election"),
        ("How You Compare — ARS Clients", "before", "ARS Key Takeaways",
         "build/peer_slide.py — every build; the client against every other ARS client, anonymous (2026-11-03)"),
    ],
    "ICS": [
        ("Direct Mail New Accounts", "after", "Results by Branch — Year to Date",
         "build/ics_pipeline/build_ics_gen.py — a client with a list in Inputs/ICS Direct Mail"),
        ("Appendix: Monthly Detail", "after", "VIP Best Practices",
         "build/ics_pipeline/build_ics_gen.py — the workbook's Monthly Detail cohorts, ten a page"),
    ],
    "MRPC": [
        ("How You Compare — MRPC Clients", "after", "MRPC Current Program Status",
         "build/peer_slide.py — every build; the client against every other MRPC client, anonymous (2026-11-03)"),
    ],
    "CP": [
        ("CashPlease Program Settings", "after", "CashPlease Program Overview",
         "build/cashplease_pipeline/build_cp_gen.py"),
        ("How You Compare — CashPlease Clients", "after", "CashPlease Peer Comparison",
         "build/peer_slide.py — every build; the client against every other CashPlease client, anonymous (2026-11-03)"),
    ],
}

# A shell slide the builder does not put in the main deck: its content moved elsewhere (see ADDED).
DROPPED = {
    "ARS": ["12-Month Take Rate by Branch"],      # the table is now "Appendix: Take Rate by Branch"
}

# A shell slide a builder retitles when it fills it: the list carries the title a deck ends up with.
RENAMED = {
    "ARS": {"Responder Activity: Before vs After (Median)":
            ("Responder Activity: Before vs After by Offer",
             "build/ars_pipeline/build_ars_gen.py — the shell's Median slide, retitled when filled")},
}

_DUMMY_CLIENT = "Union Financial"
_MONTH = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* 20\d{2}\b")


def _shell(title):
    low = title.lower().replace("®", "").strip()
    return (not low or low.isdigit() or low in _SHELL_EXACT
            or low.startswith(_SHELL_PREFIXES) or low.startswith("cashplease system"))


def _display(title):
    """The template's dummy client and month read as placeholders, so a list never names Union Financial."""
    t = re.sub(r"\s+", " ", title.replace("\n", " / ")).strip()
    t = t.replace(f"to {_DUMMY_CLIENT}", "to the client").replace(_DUMMY_CLIENT, "the client")
    return _MONTH.sub("<month>", t)


def template_titles(program):
    """The shell's slide titles, in order, shell slides left out. The title is the slide's title placeholder
    when it has text, else its first text shape — the convention the builders and the validator read by."""
    from pptx import Presentation
    prs = Presentation(str(REPO / "templates" / TEMPLATES[program]))
    out = []
    for slide in prs.slides:
        title = ""
        t = slide.shapes.title
        if t is not None and t.has_text_frame and t.text_frame.text.strip():
            title = t.text_frame.text
        else:
            for sh in slide.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip():
                    title = sh.text_frame.text
                    break
        first = title.strip().splitlines()[0].strip() if title.strip() else ""
        if _shell(first):
            continue
        out.append(first)
    return out


def _same(a, b):
    """Titles match whatever dash the shell drew (an em dash, an en dash or a hyphen)."""
    norm = lambda t: re.sub(r"\s*[—–-]\s*", " - ", t.strip().lower())
    return norm(a) == norm(b)


def _splice(titles, added):
    """Each added slide placed by its anchor; an anchor the shell has lost puts the slide at the end, so
    a renamed shell title shows up in the test, not as a silently missing slide."""
    rows = [(t, "template shell") for t in titles]
    for title, where, anchor, source in added:
        at = next((i for i, (t, _) in enumerate(rows) if _same(t, anchor)), None)
        if at is None:
            rows.append((title, source + " — anchor not found in the shell: " + anchor))
            continue
        rows.insert(at + 1 if where == "after" else at, (title, source))
    return rows


def ti_titles():
    """The Transaction Intelligence cut's slides, by chapter, those the register keeps."""
    d = json.loads(TI_REGISTER.read_text(encoding="utf-8"))
    keep = d.get("slides") or {}
    out = []
    for chapter, titles in (d.get("_by_chapter") or {}).items():
        if (d.get("chapters") or {}).get(chapter, "keep") != "keep":
            continue
        for t in titles:
            if keep.get(t, "keep") == "keep":
                out.append((t, f"build/ars_pipeline/ti/slides.json — chapter {chapter}"))
    return out


_HEADER = re.compile(r'_header\(s, "([^"]+)"')
_TITLE_CONST = re.compile(r'^TITLE(?:_\d+)? = "([^"]+)"', re.M)


def companion_titles():
    """The ARS Companion's slides: the titles James's view modules give their slides, in module order."""
    out, seen = [], set()
    for name in COMPANION_MODULES:
        src = (REPO / "build" / "ars_pipeline" / name).read_text(encoding="utf-8")
        for t in _HEADER.findall(src) + _TITLE_CONST.findall(src):
            if t not in seen:
                seen.add(t)
                out.append((t, "build/ars_pipeline/" + name))
    return out


_cache = {"stamp": None, "doc": None}


def _stamp():
    files = [REPO / "templates" / v for v in TEMPLATES.values()] + [TI_REGISTER] + \
            [REPO / "build" / "ars_pipeline" / m for m in COMPANION_MODULES]
    return tuple((str(p), p.stat().st_mtime_ns) for p in files if p.exists())


def inventory():
    """{program: [{n, title, source}]} for every program, in deck order. Cached until a source file changes."""
    stamp = _stamp()
    if _cache["doc"] is not None and _cache["stamp"] == stamp:
        return _cache["doc"]
    doc = {}
    for prog in ("ARS", "ICS", "MRPC", "CP"):
        shell = [x for x in template_titles(prog)
                 if not any(_same(x, d) for d in DROPPED.get(prog, ()))]
        rows = _splice(shell, ADDED[prog])
        renamed = RENAMED.get(prog, {})
        rows = [renamed.get(t, (t, s)) for t, s in rows]
        doc[prog] = [{"n": i, "title": _display(t), "source": s} for i, (t, s) in enumerate(rows, 1)]
    doc["TI"] = [{"n": i, "title": t, "source": s} for i, (t, s) in enumerate(ti_titles(), 1)]
    doc["COMP"] = [{"n": i, "title": t, "source": s} for i, (t, s) in enumerate(companion_titles(), 1)]
    _cache.update(stamp=stamp, doc=doc)
    return doc


if __name__ == "__main__":
    for prog, rows in inventory().items():
        print(f"== {prog}: {len(rows)} slides")
        for r in rows:
            print(f"  {r['n']:3} {r['title']}")
