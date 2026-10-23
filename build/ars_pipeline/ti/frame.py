"""
frame.py — the slide frame every Transaction Intelligence chapter draws on.

The same anatomy as the other programs' data slides (templates/STYLE.md): title top-left,
the selection under it, the period pill top-right, the client's logo bottom-right, a slide
number bottom-left. Built only from the shared layer (`brand`, `shapes`), never restyled
locally.

`notes()` is the one way a chapter writes speaker notes, and it refuses a note with no
Source line: CLAUDE.md makes the source in the notes a hard requirement, and catching it
at build time is cheaper than catching it in `validate_deck.source_note_findings`.
"""
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from brand import BODY, HEAD, NAVY_RGB, TICK_RGB
from shapes import data_logo, pill, textbox


def _layout(prs, name="BLANK"):
    for master in prs.slide_masters:
        for lay in master.slide_layouts:
            if lay.name == name:
                return lay
    raise SystemExit(f"no {name} layout in the template shell")


def new_slide(prs):
    """A slide on the shell's BLANK layout with every placeholder removed."""
    s = prs.slides.add_slide(_layout(prs))
    for sh in list(s.shapes):
        sh._element.getparent().remove(sh._element)
    return s


def numbered(slide):
    """Declare a content slide numbered. The value is written by
    `assemble_combined.renumber`, which numbers exactly the slides carrying a box."""
    import assemble_combined as ac
    tb = slide.shapes.add_textbox(*[Inches(v) for v in ac.NUM_LTWH])
    r = tb.text_frame.paragraphs[0].add_run()
    r.text = "0"
    r.font.name = BODY
    r.font.size = Pt(ac.NUM_PT)
    r.font.bold = True
    r.font.color.rgb = NAVY_RGB
    return slide


def head(slide, title, selection, pill_text):
    """Title, the selection under it (never touching it), and the period pill."""
    textbox(slide, 0.6, 0.38, 9.3, 0.62, title, 30, NAVY_RGB, True,
            PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    textbox(slide, 0.62, 1.06, 9.6, 0.46, selection, 16, TICK_RGB, False,
            PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    pill(slide, pill_text, L=10.15, W=2.70)


def logo(slide, client_id, art_dir=None):
    """The client's logo bottom-right, the lockup where there is none."""
    return data_logo(slide, client_id=client_id, assets_dir=art_dir)


def notes(slide, text):
    """Write the slide's speaker notes. A note with no Source line is refused."""
    text = (text or "").strip()
    if "source" not in text.lower():
        raise ValueError("a Transaction Intelligence slide's notes must name its source "
                         "(CLAUDE.md: every slide lists its data source in the notes)")
    slide.notes_slide.notes_text_frame.text = text
    return slide


def content_slide(ctx, title, selection):
    """A numbered data slide with the frame drawn: what every chapter starts from."""
    s = numbered(new_slide(ctx.prs))
    head(s, title, selection, ctx.pill)
    logo(s, ctx.pack["client_id"], ctx.art_dir)
    return s
