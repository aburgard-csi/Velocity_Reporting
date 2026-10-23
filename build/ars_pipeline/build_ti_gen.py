#!/usr/bin/env python3
"""
build_ti_gen.py — build one client's Transaction Intelligence deck, in one lens.

The Transaction Intelligence cut (build/ars_pipeline/ti/) is a SEPARATE deck: it never
edits the ARS deck, its metrics or its template, and nothing in the monthly chain calls it
yet. Its shape is a single-product deck's: cover, Executive Summit, agenda, then one
section per chapter (divider + content slides), then Questions & Discussion and Contact Us.

The package starts from the ARS template shell, because the cut reads ARS data (the ODD and
the transaction files). The five shell slides are found by MEANING, as the CashPlease builder
finds them (cover, Summit, agenda, Questions, Contact); every other shell slide is dropped
from the slide list and then physically removed by `build/strip_dead.py`, so no orphaned
part is left in the package (CLAUDE.md, validation gate rule 3).

The data pack (written by the cut's compute step, not by hand):
    {"client_id": "1234", "client_name": "...",
     "period": "2026.10",          # the reporting month: the cover and the file name
     "data_month": "Sep26",        # the data month: the pills
     "sources": {"odd": "<ODD member name + pull stamp>"},
     "chapters": {"<code>": {...}}}   # each chapter's own figures

Usage:
    python build_ti_gen.py <pack.json> <ars_template.pptx> <out.pptx> --lens ars|ics
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
for p in (BUILD, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from pptx import Presentation                                    # noqa: E402

import cover_divider as CD                                       # noqa: E402
from periods import Period                                       # noqa: E402
from shapes import sldid_of                                      # noqa: E402
from ti import cut                                               # noqa: E402

# What a chapter's build() receives. `pill` is the data-month pill every content slide carries.
Ctx = namedtuple("Ctx", "prs pack lens pill art_dir")

REQUIRED = ("client_id", "client_name", "period", "data_month")


def load_pack(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if not str(d.get(k) or "").strip()]
    if not (d.get("sources") or {}).get("odd"):
        missing.append("sources.odd")
    if missing:
        raise SystemExit(f"{path}: the data pack is missing {', '.join(missing)}")
    return d


def reporting_month(pack):
    """'October 2026' from the pack's yyyy.mm period — never the clock (STYLE.md, the two months)."""
    return Period(str(pack["period"]).replace(".", "-")).label()


def _title(slide):
    return next((sh.text_frame.text.strip().split("\n")[0] for sh in slide.shapes
                 if sh.has_text_frame and sh.text_frame.text.strip()), "")


def _set_closing_line(slide, text):
    """Rewrite the Questions slide's '<client>  •  <month>' line in place, keeping its runs' format."""
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for para in sh.text_frame.paragraphs:
            if "•" in para.text and not para.text.strip().startswith("Questions & Discussion"):
                runs = para.runs
                runs[0].text = text
                for r in runs[1:]:
                    r.text = ""
                return True
    raise SystemExit("the Questions & Discussion slide carries no '<client>  •  <month>' line — "
                     "the shell changed")


def adapt_shell(prs, pack, ln, chapters, art_dir=None):
    """Find the shell's cover, Summit, agenda, Questions and Contact by meaning and
    rewrite them for this client, lens and chapter list."""
    import assemble_combined as ac

    found = {}
    for n, s in enumerate(prs.slides, 1):
        title = _title(s)
        if "cover" not in found and ac._is_cover(s):
            found["cover"] = s
        elif "summit" not in found and ac._is_summit(s, n):
            found["summit"] = s
        elif "agenda" not in found and title.startswith("Agenda"):
            found["agenda"] = s
        elif "questions" not in found and title.startswith("Questions & Discussion"):
            found["questions"] = s
        elif "contact" not in found and title.startswith("Contact Us"):
            found["contact"] = s
    missing = {"cover", "summit", "agenda", "questions", "contact"} - set(found)
    if missing:
        raise SystemExit(f"{sorted(missing)} not found in the template shell — it changed. "
                         f"Resolve by meaning, do not fall back to indexes.")

    cid, name, month = pack["client_id"], pack["client_name"], reporting_month(pack)
    products = [CD.PRODUCT_ARS] + ([CD.PRODUCT_ICS] if ln.key == "ics" else [])
    products.append(f"{cut.CUT_NAME} · {ln.label}")
    CD.draw_cover(found["cover"], products, name, month,
                  client_logo=CD.client_logo_for(cid, art_dir),
                  note=(f"Source: the ODD extract {pack['sources']['odd']} for client {cid} {name}. "
                        f"Cover of the {cut.CUT_NAME} cut, {ln.label}. No figures."))

    # One agenda row per chapter. Codes are registered the way the CashPlease builder registers
    # "CP": set_agenda reads its row names from assemble_combined.PRODUCT_NAME.
    for ch in chapters:
        ac.PRODUCT_NAME.setdefault(ch.code, ch.title)
    ac.set_agenda(found["agenda"], [ch.code for ch in chapters],
                  detail_overrides={ch.code: ch.agenda for ch in chapters})
    found["agenda"].notes_slide.notes_text_frame.text = (
        f"Source: the {cut.CUT_NAME} cut's chapter list, {ln.label} (static). No figures.")

    _set_closing_line(found["questions"], f"{name}  •  {month}")

    import rpe_env
    from shapes import fill_contact_card
    fill_contact_card(found["contact"], rpe_env.csm_contact(cid))
    return found


def divider(prs, ch, pack, ln):
    from ti import frame
    s = frame.new_slide(prs)
    CD.draw_divider(s, ch.title, ch.benefits, stats=ch.stats(pack, ln) or (),
                    note=(f"Section divider, {ln.label}. Source: the ODD extract "
                          f"{pack['sources']['odd']} for client {pack['client_id']} "
                          f"{pack['client_name']}; figures as on the chapter's slides."))
    return s


def build(prs, pack, lens_key, chapters, art_dir=None):
    """Assemble the deck in `prs` and return the slides in deck order. No save."""
    ln = cut.lens(lens_key)
    chapters = list(chapters)
    if not chapters:
        raise SystemExit(f"no chapter of the {cut.CUT_NAME} cut is built yet — "
                         f"nothing to put in a deck")
    keep = adapt_shell(prs, pack, ln, chapters, art_dir)
    ctx = Ctx(prs, pack, ln, Period(pack["data_month"]).data_pill(), art_dir)

    body = []
    for ch in chapters:
        body.append(divider(prs, ch, pack, ln))
        body.extend(ch.build(ctx))

    order = [keep["cover"], keep["summit"], keep["agenda"]] + body + [keep["questions"], keep["contact"]]
    lst = prs.slides._sldIdLst
    ids = [sldid_of(prs, s) for s in order]
    for el in list(lst):
        lst.remove(el)
    for el in ids:
        lst.append(el)
    assert len({id(e) for e in lst}) == len(order), "a slide is referenced twice"

    import summit_slide
    summit_slide.insert_summit_after_title(prs)
    import fit_layout
    fit_layout.fit(prs)
    import assemble_combined as ac
    ac.renumber(prs)
    return order


def save(prs, out):
    """Save, then strip the shell's orphaned slide parts and unused media."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ti_full_") as scratch:
        tmp = Path(scratch) / f"{out.stem}.__full.pptx"
        prs.save(str(tmp))
        subprocess.run([sys.executable, str(BUILD / "strip_dead.py"), str(tmp), str(out)], check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("pack")
    ap.add_argument("template")
    ap.add_argument("out")
    ap.add_argument("--lens", required=True, choices=sorted(cut.LENSES))
    a = ap.parse_args(argv)

    pack = load_pack(a.pack)
    art_dir = os.environ.get("TI_ARTIFACTS") or str(Path(a.out).parent / "ti_art")
    prs = Presentation(a.template)
    order = build(prs, pack, a.lens, cut.CHAPTERS, art_dir)
    save(prs, a.out)
    print(f"built {a.out} -> {len(order)} slides ({pack['client_id']} {pack['client_name']}, "
          f"{cut.lens(a.lens).label})")


if __name__ == "__main__":
    main()
