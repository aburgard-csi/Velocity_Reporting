"""The Contact Us slide: the Questions & Discussion gradient, full bleed, the contact centred (Aaron, 2026-11-02).

"Add this gradient to the contact card", then "too much space between the lines on the contact card. we need
to do something else with that slide", then the choice of the full-bleed design over a compact card and a wide
card. `shapes.draw_contact_slide` draws it: the closing slide's gradient (build/assets/csi_brand/closing_fill.xml,
the one place the stops live), the white CSI logo, "Contact Us" under it and the contact beneath, in one column
or two (the ICS program contact). The shell's static slide (`fill_contact_slide`) and the slides the ICS, MRPC and
ARS builders draw themselves all go through it.

Every contact is synthetic.
"""
import os

import pytest
from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

import shapes

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOSING_FILL = os.path.join(REPO, "build", "assets", "csi_brand", "closing_fill.xml")
CONTACT = {"name": "Pat Cell", "role": "Client Service Manager", "phone": "555-010-0002", "email": "pat.cell@example.com"}
PROGRAM = {"name": "Program Contact", "role": "ICS Program Manager", "phone": "555-010-0100", "email": "program.contact@example.com"}
LINES = ("Contact name", "Contact role", "Contact phone", "Contact email")


def _stops(grad):
    return sorted((int(gs.get("pos")), gs[0].get("val")) for gs in grad.iter(qn("a:gs")))


def _slide():
    prs = Presentation(os.path.join(REPO, "templates", "ics_template.pptx"))
    return prs.slides.add_slide(prs.slide_layouts[-1])


def _named(slide, *names):
    return [sh for sh in slide.shapes if sh.name in names]


def _inches(v):
    return v / 914400


def test_the_stops_are_the_closing_slides():
    grad = etree.parse(CLOSING_FILL).getroot()
    assert _stops(grad) == [(37000, "00274C"), (100000, "035B95")]          # navy to CSI light blue
    assert grad.find(qn("a:path")).get("path") == "circle"                  # radial, focus at the top-left


def _assert_the_slide(slide, contacts):
    texts = [sh for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
    assert texts[0].text_frame.text == "Contact Us"                           # the title comes first: every lookup reads it
    fill = _named(slide, shapes.CONTACT_TAG_FILL)
    assert len(fill) == 1
    assert (round(_inches(fill[0].width), 2), round(_inches(fill[0].height), 2)) == (13.33, 7.5)      # full bleed
    grads = fill[0]._element.spPr.findall(qn("a:gradFill"))
    assert len(grads) == 1 and _stops(grads[0]) == _stops(etree.parse(CLOSING_FILL).getroot())
    assert not fill[0]._element.spPr.findall(qn("a:solidFill"))
    assert [sh for sh in slide.shapes if sh.shape_type == 13], "the white CSI logo"
    names = [sh.text_frame.text for sh in _named(slide, *LINES)]
    for c in contacts:
        assert c["name"] in names and c["role"] in names and c["email"] in names
        assert (c["phone"] in names) == bool(c.get("phone"))
    for sh in _named(slide, *LINES) + _named(slide, "Contact title"):          # the 16 pt floor
        assert min(r.font.size.pt for p in sh.text_frame.paragraphs for r in p.runs) >= 16


@pytest.mark.parametrize("template", ["ars_template.pptx", "mrpc_template.pptx", "cashplease_template.pptx"])
def test_a_shell_slide_is_redrawn_whole(template):
    prs = Presentation(os.path.join(REPO, "templates", template))
    slide = shapes.find_contact_slide(prs)
    assert slide is not None
    shapes.fill_contact_slide(slide, CONTACT)
    _assert_the_slide(slide, [CONTACT])
    everything = " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)
    assert "csiweb" not in everything.lower(), "the shell's static card survived"
    assert slide.notes_slide.notes_text_frame.text == shapes.contact_card_note(CONTACT)
    assert shapes.find_contact_slide(prs) is slide                         # still found by its title


@pytest.mark.parametrize("contacts", [[CONTACT], [CONTACT, PROGRAM], [dict(CONTACT, phone="")]])
def test_one_or_two_contacts_are_centred_and_level(contacts):
    slide = _slide()
    shapes.draw_contact_slide(slide, contacts)
    _assert_the_slide(slide, contacts)
    names = sorted(_named(slide, "Contact name"), key=lambda s: s.left)
    assert len(names) == len(contacts)
    assert len({sh.top for sh in names}) == 1                                  # level
    span = _inches(names[-1].left + names[-1].width) - _inches(names[0].left)
    assert abs(_inches(names[0].left) - (13.333 - span) / 2) < 0.01            # centred on the slide


def test_phone_and_email_sit_together_and_a_missing_phone_closes_the_gap():
    slide = _slide()
    shapes.draw_contact_slide(slide, [CONTACT])
    top = {sh.name: _inches(sh.top) for sh in _named(slide, *LINES)}
    assert top["Contact email"] - top["Contact phone"] <= 0.45                 # grouped, not spread
    slide = _slide()
    shapes.draw_contact_slide(slide, [dict(CONTACT, phone="")])
    top = {sh.name: _inches(sh.top) for sh in _named(slide, *LINES)}
    assert "Contact phone" not in top
    assert abs(top["Contact email"] - shapes.CONTACT_TOPS["phone"]) < 0.001    # the email takes the phone's row


def test_phone_and_email_carry_small_icons_clear_of_their_text():
    slide = _slide()
    shapes.draw_contact_slide(slide, [CONTACT])
    icons = _named(slide, shapes.CONTACT_TAG_ICON)
    assert len(icons) == 5                                       # phone body + home bar, envelope + two flap lines
    for name in ("Contact phone", "Contact email"):
        txt = _named(slide, name)[0]
        for ic in icons:
            overlap_x = min(ic.left + ic.width, txt.left + txt.width) - max(ic.left, txt.left)
            overlap_y = min(ic.top + ic.height, txt.top + txt.height) - max(ic.top, txt.top)
            assert not (overlap_x > Inches(0.02) and overlap_y > Inches(0.02)), "an icon sits on its text"


def test_the_contact_slide_is_never_mistaken_for_a_section_divider():
    """It is full bleed with a 44 pt title, like a divider; the ARS builder redraws every divider in place and
    once turned this slide into one, keeping the title and the first line (the golden deck caught it)."""
    import cover_divider
    slide = _slide()
    shapes.draw_contact_slide(slide, [CONTACT])
    assert cover_divider._is_fullbleed(slide) and not cover_divider.is_divider(slide)


def test_the_slide_is_redrawn_whole_not_added_to():
    slide = _slide()
    shapes.draw_contact_slide(slide, [CONTACT])
    shapes.draw_contact_slide(slide, [CONTACT, PROGRAM])                       # a second call replaces the first
    assert len(_named(slide, shapes.CONTACT_TAG_FILL)) == 1 and len(_named(slide, "Contact name")) == 2


def test_three_contacts_do_not_fit_and_stop_the_build():
    with pytest.raises(SystemExit):
        shapes.draw_contact_slide(_slide(), [CONTACT, PROGRAM, PROGRAM])


@pytest.mark.parametrize("path", ["build/ics_pipeline/build_ics_gen.py", "build/mrpc_pipeline/build_mrpc_gen.py",
                                  "build/ars_pipeline/build_ars_gen.py"])
def test_every_builder_that_draws_the_slide_uses_the_helper(path):
    src = open(os.path.join(REPO, path), encoding="utf-8").read()
    assert "draw_contact_slide" in src or "_dcs" in src, f"{path} draws a Contact Us slide its own way"
    for old in ("draw_contact_cards", "contact_card_fill", "contact_card_lines", "CONTACT_CARD_H"):
        assert old not in src


def test_the_text_stays_readable_on_the_gradient():
    """White is the bulk of the slide; the orange role line is the weakest text. It is bold 18 pt (large text, 3:1).
    The gradient is darkest at the top-left focus; the second column's role line sits about 70% of the way out."""
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    def lum(rgb):
        r, g, b = rgb
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

    def ratio(a, b):
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)
    navy, blue, orange, white = (0x00, 0x27, 0x4C), (0x03, 0x5B, 0x95), (0xF1, 0x5D, 0x22), (255, 255, 255)
    t = (0.70 - 0.37) / (1 - 0.37)
    there = tuple(round(navy[i] + t * (blue[i] - navy[i])) for i in range(3))
    assert ratio(orange, there) >= 3.0
    assert ratio(white, blue) >= 7.0            # white at the lightest corner of the slide
