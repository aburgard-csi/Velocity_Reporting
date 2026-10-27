"""The ARS Companion deck: James Gilmore's analysis slides, as a deck of their own.

Aaron, 2026-10-27: "Build functionality in Sheila (a new button) to build a ARS Companion Deck with James's
slides." The Executive Review is the approved deck and is never changed by these views. The companion is a
SEPARATE presentation, built the way the Transaction Intelligence deck is: the launcher builds the ARS deck
with every opt-in view switched on (RPE_JAMES_SLIDES, RPE_SPEND_SLIDES, RPE_COMPANION), `build_ars_gen`
records which slides those views added (`companion_slides.json`, by slide id), and this module keeps only
those: the cover, the added slides in the order the review would carry them, Questions & Discussion and
the Contact card.

Nothing is added to the package, so the "freed partname" hazard (CLAUDE.md, Combined decks) does not arise:
slides are only dropped, by removing their reference and relationship; python-pptx then writes only the parts
still reachable. `validate_deck.package_findings` is run on the result by the launcher all the same.

    python companion_deck.py <full_ars_deck.pptx> <companion_slides.json> <out.pptx>

Import-safe.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # build/: shapes

TAG = "COMP"
COVER_WORD = "Executive Review"
# "Companion" is a banned word on a slide (CLAUDE.md, Writing style); it names the deck in Sheila and in the file only.
COVER_REPLACEMENT = "Executive Review Analysis"


def title_of(slide):
    """The slide's title: its first non-empty text shape, first line (the pipeline's convention)."""
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0].strip()
    return ""


def _is_closing(title):
    t = title.lower()
    return t.startswith("questions") or t.startswith("contact")


def keep_plan(slides, added_ids):
    """Indexes of the slides to keep, in deck order: the cover, the views' slides, Questions, Contact.

    `slides` is [(slide_id, title)] in deck order. The cover is the first slide; a slide whose id the
    build recorded is a view; the closing slides are found by title, never by index.
    """
    ids = set(added_ids)
    return [i for i, (sid, title) in enumerate(slides) if i == 0 or sid in ids or _is_closing(title)]


def retitle_cover(prs):
    """The cover's "Executive Review • <month>" line says "Executive Review Analysis • <month>" instead.

    The line is kept in the same shape, run and paragraph, and still opens with "Executive Review":
    validate_deck reads the client and month from it (`_cover_client_and_month`), and a line with other
    words before that phrase would be read as the client's name."""
    done = False
    for sh in prs.slides[0].shapes:
        if not sh.has_text_frame:
            continue
        for p in sh.text_frame.paragraphs:
            if COVER_WORD in p.text and "•" in p.text:
                for r in p.runs:
                    if r.text.strip().startswith(COVER_WORD) and COVER_REPLACEMENT not in r.text:
                        r.text = r.text.replace(COVER_WORD, COVER_REPLACEMENT)
                        done = True
    return done


def build(full_deck, slides_json, out):
    """Write the companion deck at `out`. Returns the number of view slides it carries.

    Raises SystemExit when the build recorded no views: a companion of just a cover is not a deck."""
    from pptx import Presentation
    with open(slides_json, encoding="utf-8") as fh:
        info = json.load(fh)
    added = info.get("slide_ids") or []
    if not added:
        raise SystemExit("the build recorded no companion slides (companion_slides.json is empty)")
    prs = Presentation(full_deck)
    slides = list(prs.slides)
    by_id = {s.slide_id: title_of(s) for s in slides}       # before any slide is dropped: slide_id needs its rel
    plan = keep_plan(list(by_id.items()), added)
    if not any(slides[i].slide_id in set(added) for i in plan):
        raise SystemExit("none of the recorded companion slides is in the deck")
    lst = prs.slides._sldIdLst
    keep_ids = {slides[i].slide_id for i in plan}
    for el in list(lst):
        if el.id not in keep_ids:
            prs.part.drop_rel(el.rId)
            lst.remove(el)
    # Questions & Discussion and Contact close the deck: the ARS deck puts them before its appendix, and some of
    # the views are appendix slides, which would otherwise follow them.
    for el in [e for e in list(lst) if _is_closing(by_id[e.id])]:
        lst.remove(el)
        lst.append(el)
    if not retitle_cover(prs):
        raise SystemExit("the cover has no 'Executive Review' line to retitle")
    import shapes as S
    S.renumber(prs)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    prs.save(out)
    return sum(1 for i in plan if slides[i].slide_id in set(added))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    n = build(*sys.argv[1:4])
    print(f"companion deck: {n} slides -> {sys.argv[3]}")
