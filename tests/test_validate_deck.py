"""validate_deck — the figure-identity rule.

Reproduces the 2026-08-28 Wellworth defect in miniature: one measure rendered
with two different values on two different slides, where the older rule 7 was
blind because "responder" was not among its four hardcoded label words and the
values are not percentages.
"""
import os, sys
import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation"))
import validate_deck as vd


def deck(slides):
    """slides = [(title, [body strings]), ...] -> an in-memory Presentation."""
    prs = Presentation()
    blank = prs.slide_layouts[6]
    for title, bodies in slides:
        s = prs.slides.add_slide(blank)
        tb = s.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.8))
        tb.text_frame.text = title
        for j, b in enumerate(bodies):
            box = s.shapes.add_textbox(Inches(0.5), Inches(1.4 + j), Inches(9), Inches(0.8))
            box.text_frame.text = b
    return prs


def labels(findings):
    return " | ".join(f[2] for f in findings)


# --- the defect it exists to catch ---------------------------------------
def test_conflicting_responder_count_is_flagged():
    prs = deck([
        ("Mailing Response Summary", ["The drop reached 1,077 responders in total."]),
        ("Program Reach", ["The drop reached 1,026 responders in total."]),
    ])
    out = vd.figure_identity_findings(prs)
    assert out, "the 1,077 / 1,026 conflict was not detected"
    assert "1,077" in labels(out) and "1,026" in labels(out)


def test_conflicting_percentage_is_flagged():
    prs = deck([
        ("Mailing Response Summary", ["Sustained activity held at 16.3% of the group."]),
        ("Sustained Respondent Activity", ["Sustained activity held at 10.7% of the group."]),
    ])
    assert vd.figure_identity_findings(prs), "the 16.3% / 10.7% split was not detected"


def test_agreeing_values_are_not_flagged():
    prs = deck([
        ("Mailing Response Summary", ["The drop reached 1,026 responders in total."]),
        ("Program Reach", ["The drop reached 1,026 responders in total."]),
    ])
    assert vd.figure_identity_findings(prs) == []


# --- the guards that keep it quiet on a correct deck ----------------------
def test_title_discriminator_prevents_a_false_conflict():
    """Personal and Business take rates share caption wording, correctly."""
    prs = deck([
        ("12-Month Eligible Take Rate — Personal",
         ["Dashed line marks the largest branches at 75.9% overall."]),
        ("12-Month Eligible Take Rate — Business",
         ["Dashed line marks the largest branches at 35.0% overall."]),
    ])
    assert vd.figure_identity_findings(prs) == []


def test_mean_and_median_slides_are_not_compared():
    prs = deck([
        ("Responder Activity: Before vs After (Mean)",
         ["Average monthly debit spend rose to 4,368 dollars per responder."]),
        ("Responder Activity: Before vs After (Median)",
         ["Average monthly debit spend rose to 2,915 dollars per responder."]),
    ])
    assert vd.figure_identity_findings(prs) == []


def test_per_mailing_labels_are_skipped():
    """A per-mailing figure is SUPPOSED to differ between mailings."""
    prs = deck([
        ("Mailing Response Ranking", ["Responders per mailing reached 1,077 that month."]),
        ("Mailing Insights",         ["Responders per mailing reached 1,026 that month."]),
    ])
    assert vd.figure_identity_findings(prs) == []


def test_month_qualified_figures_are_not_compared():
    """Different periods keep different labels, so they are never compared."""
    prs = deck([
        ("Program Reach", ["Responders in Jun 2026 totalled 1,077 across the book."]),
        ("Program Reach Detail", ["Responders in Jul 2026 totalled 1,026 across the book."]),
    ])
    out = vd.figure_identity_findings(prs)
    assert out == [], f"month-qualified figures were compared: {labels(out)}"


def test_counts_are_never_compared_against_percentages():
    prs = deck([
        ("Summary A", ["Debit adoption across the book stands at 4,368 accounts."]),
        ("Summary B", ["Debit adoption across the book stands at 78.0%."]),
    ])
    assert vd.figure_identity_findings(prs) == []


def test_two_values_on_one_slide_is_not_a_conflict():
    prs = deck([("Summary", ["Total reached 1,077 accounts.", "Total reached 1,026 accounts."])])
    assert vd.figure_identity_findings(prs) == []


def test_table_rows_are_not_read():
    """A mailing table varies by row by design; reading it makes every table noisy."""
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.8))
    tb.text_frame.text = "Mailing Response Summary"
    gf = s.shapes.add_table(3, 2, Inches(0.5), Inches(1.5), Inches(6), Inches(2))
    for i, v in enumerate(("1,077", "1,026")):
        gf.table.cell(i + 1, 0).text = "responders in total"
        gf.table.cell(i + 1, 1).text = v
    assert vd.figure_identity_findings(prs) == []


# --- the rule is advisory -------------------------------------------------
def test_findings_are_review_not_fail():
    """Identity is INFERRED from wording; inference must not block a ship."""
    prs = deck([
        ("Mailing Response Summary", ["The drop reached 1,077 responders in total."]),
        ("Program Reach", ["The drop reached 1,026 responders in total."]),
    ])
    assert {f[0] for f in vd.figure_identity_findings(prs)} == {"REVIEW"}


# =========================================================================
# period consistency
# =========================================================================
PACK = {"latest_month": "Jul26"}


def test_correct_captions_are_clean():
    prs = deck([("Program Overview", ["PTD · July 2026", "Reg E opt-in status as of July 2026"])])
    assert vd.period_findings(prs, PACK) == []


# --- the 2026-08-28 stale-caption bugs ------------------------------------
@pytest.mark.parametrize("caption", [
    "Monthly debit spend as of June 2026",
    "June 2026 Data",
    "PTD · June 2026",
    "Client ODD (June 2026 snapshot)",
])
def test_stale_month_caption_is_raised(caption):
    """A Jul-2026 client shipped about a dozen captions naming June 2026."""
    prs = deck([("Program Overview", [caption])])
    out = vd.period_findings(prs, PACK)
    assert out, f"stale caption not caught: {caption}"
    assert out[0][0] == "REVIEW"


def test_future_month_caption_fails():
    """Data cannot come from the future — this is never legitimate."""
    prs = deck([("Program Overview", ["PTD · August 2026"])])
    out = vd.period_findings(prs, PACK)
    assert out and out[0][0] == "FAIL"


def test_carried_forward_ics_figure_is_review_not_fail():
    """CoastLife's ICS section correctly reads an older month than its ARS section.

    ICS financials are quarterly and carry forward, so an older month is right.
    The check raises it for confirmation; it must not block the ship.
    """
    prs = deck([("ICS Financial Summary", ["PTD · June 2026"])])
    out = vd.period_findings(prs, PACK)
    assert out and {f[0] for f in out} == {"REVIEW"}


# --- span arithmetic (needs no data pack) ---------------------------------
def test_span_count_mismatch_fails():
    prs = deck([("Overall Debit Swipes & Spend", ["Jul 2023 – Jun 2026 (30 months)"])])
    out = vd.period_findings(prs, None)
    assert out and out[0][0] == "FAIL"
    assert "36" in out[0][2], "the finding should state the true span"


def test_correct_span_is_clean():
    prs = deck([("Overall Debit Swipes & Spend", ["Jul 2023 – Jun 2026 (36 months)"])])
    assert vd.period_findings(prs, None) == []


def test_span_is_checked_without_a_pack():
    """Pure arithmetic — it holds even when no oddd_metrics.json is found."""
    prs = deck([("Trend", ["Aug 2025 – Jul 2026 (6 months)"])])
    assert any(f[0] == "FAIL" for f in vd.period_findings(prs, None))


def test_single_month_span_is_clean():
    prs = deck([("Trend", ["Jul 2026 – Jul 2026 (1 month)"])])
    assert vd.period_findings(prs, None) == []


# --- a literal month is not itself a defect -------------------------------
def test_a_matching_literal_month_is_never_flagged():
    """Writing the month out is fine when it IS the month being described."""
    prs = deck([("Product Mix & ARS Eligibility",
                 ["July 2026 Data", "Snapshot taken in July 2026 across the book"])])
    assert vd.period_findings(prs, PACK) == []


def test_prose_mentioning_a_month_without_a_caption_pattern_is_ignored():
    """Only point-in-time CAPTIONS are period claims; narrative prose is not."""
    prs = deck([("ARS Key Takeaways",
                 ["The program has run since June 2024 and continues to grow."])])
    assert vd.period_findings(prs, PACK) == []


# =========================================================================
# source-note provenance
# =========================================================================
def deck_with_notes(slides):
    """slides = [(title, [bodies], note), ...]. Adds a wide picture-sized table
    so the slide reads as a DATA slide."""
    from pptx.util import Inches as In
    prs = Presentation()
    blank = prs.slide_layouts[6]
    for title, bodies, note in slides:
        s = prs.slides.add_slide(blank)
        tb = s.shapes.add_textbox(In(0.5), In(0.3), In(9), In(0.8))
        tb.text_frame.text = title
        for j, b in enumerate(bodies):
            box = s.shapes.add_textbox(In(0.5), In(1.4 + j), In(9), In(0.8))
            box.text_frame.text = b
        s.shapes.add_table(2, 2, In(0.5), In(3), In(6), In(1.5))   # marks it as data
        if note is not None:
            s.notes_slide.notes_text_frame.text = note
    return prs


def test_data_slide_without_a_note_fails(tmp_path):
    prs = deck_with_notes([("Monthly Summary — Last 12 Months", ["Chart"], None)])
    out = vd.source_note_findings(str(tmp_path / "1204-2026.08-ARS-Client.pptx"), prs)
    assert any(f[0] == "FAIL" and "no speaker note" in f[2] for f in out)


def test_note_without_a_source_line_fails(tmp_path):
    prs = deck_with_notes([("Monthly Summary — Last 12 Months", ["Chart"],
                            "Talk through the trend here.")])
    out = vd.source_note_findings(str(tmp_path / "1204-2026.08-ARS-Client.pptx"), prs)
    assert any(f[0] == "FAIL" and "no Source line" in f[2] for f in out)


def test_note_with_a_source_line_passes(tmp_path):
    prs = deck_with_notes([("Monthly Summary — Last 12 Months", ["Chart"],
                            "Source: client ODD, July 2026 snapshot.")])
    assert vd.source_note_findings(str(tmp_path / "1204-2026.08-ARS-Client.pptx"), prs) == []


def test_structural_slides_need_no_source(tmp_path):
    """Agenda, Q&A and Contact carry no data, so they cite nothing."""
    prs = deck_with_notes([("Agenda", ["1 2 3"], None),
                           ("Questions & Discussion", [], None),
                           ("Contact Us", ["team@example.com"], None)])
    assert vd.source_note_findings(str(tmp_path / "1204-2026.08-ARS-Client.pptx"), prs) == []


# --- the CoastLife-defaults defect ---------------------------------------
def test_note_naming_another_client_fails(tmp_path):
    """build_ars_gen defaulted ODD_SRC/WB_SRC to CoastLife 1705, so every other
    client inherited CoastLife's source notes. reference_leak_findings reads
    slide TEXT only, so a leak living in the NOTES was invisible."""
    prs = deck_with_notes([("Monthly Summary — Last 12 Months", ["Chart"],
                            "Source: client ODD, July 2026 (1705-CoastLife Credit Union-ODD.csv).")])
    out = vd.source_note_findings(str(tmp_path / "1204-2026.08-ARS-FSB Michigan.pptx"), prs)
    assert any(f[0] == "FAIL" and "CoastLife" in f[2] for f in out)


def test_the_decks_own_client_is_not_a_leak(tmp_path):
    """CoastLife's OWN deck may name CoastLife in its notes."""
    prs = deck_with_notes([("Monthly Summary — Last 12 Months", ["Chart"],
                            "Source: client ODD, July 2026 (1705-CoastLife Credit Union-ODD.csv).")])
    out = vd.source_note_findings(
        str(tmp_path / "1705-2026.08-ARS-CoastLife Credit Union ARS Results.pptx"), prs)
    assert out == []


def test_template_shells_are_exempt_from_source_notes(tmp_path):
    """A shell has no notes yet by definition — the builder writes them."""
    prs = deck_with_notes([("Monthly Summary — Last 12 Months", ["Chart"], None)])
    assert vd.source_note_findings(str(tmp_path / "ars_template.pptx"), prs) == []
    assert vd.source_note_findings(
        str(tmp_path / "multi-product_reference_deck.pptx"), prs) == []
    # ...but a real client deck is not exempt
    assert vd.source_note_findings(str(tmp_path / "1204-2026.08-ARS-Client.pptx"), prs)


def test_a_screenshot_slide_owes_no_source(tmp_path):
    """ICS resource slides are full-bleed screenshots with nothing derived."""
    from pptx.util import Inches as In
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(In(0.5), In(0.3), In(9), In(0.8))
    tb.text_frame.text = "E-Learning Library Guide"
    body = s.shapes.add_textbox(In(0.5), In(1.5), In(9), In(0.6))
    body.text_frame.text = "Modules available to every client team."
    assert vd.source_note_findings(str(tmp_path / "1204-2026.08-ARS-Client.pptx"), prs) == []


# =========================================================================
# figure sidecar — the FAIL-grade identity check
# =========================================================================
def write_sidecar(tmp_path, rows, deck_name="1204-2026.08-ARS-Client.pptx"):
    import json
    deck = tmp_path / deck_name
    (tmp_path / (deck_name + ".figures.json")).write_text(json.dumps({"figures": rows}))
    return str(deck)


def test_sidecar_conflict_fails(tmp_path):
    """The Wellworth shape, now provable rather than inferred."""
    deck = write_sidecar(tmp_path, [
        {"measure": "responders_jun2026", "value": "1,077",
         "slide": "Mailing Response Summary", "note": ""},
        {"measure": "responders_jun2026", "value": "1,026",
         "slide": "Program Reach", "note": ""},
    ])
    out = vd.figure_sidecar_findings(deck)
    assert out and out[0][0] == "FAIL"
    assert "responders_jun2026" in out[0][2]
    assert "1,077" in out[0][2] and "1,026" in out[0][2]
    assert "Program Reach" in out[0][2], "the finding should name where each value rendered"


def test_sidecar_agreement_is_clean(tmp_path):
    deck = write_sidecar(tmp_path, [
        {"measure": "responders_jun2026", "value": "1,026",
         "slide": "Mailing Response Summary", "note": ""},
        {"measure": "responders_jun2026", "value": "1,026",
         "slide": "Program Reach", "note": ""},
    ])
    assert vd.figure_sidecar_findings(deck) == []


def test_distinct_measures_sharing_a_value_are_clean(tmp_path):
    deck = write_sidecar(tmp_path, [
        {"measure": "reach_total", "value": "3,629", "slide": "Program Reach", "note": ""},
        {"measure": "dot_n", "value": "3,629", "slide": "Transaction Increase", "note": ""},
    ])
    assert vd.figure_sidecar_findings(deck) == []


def test_absent_sidecar_is_not_a_finding(tmp_path):
    """Only build_ars_gen emits one; older decks must still validate."""
    assert vd.figure_sidecar_findings(str(tmp_path / "no-sidecar.pptx")) == []


def test_unreadable_sidecar_is_review_not_fail(tmp_path):
    deck = tmp_path / "deck.pptx"
    (tmp_path / "deck.pptx.figures.json").write_text("{not json")
    out = vd.figure_sidecar_findings(str(deck))
    assert out and out[0][0] == "REVIEW"


def test_sidecar_rule_is_fail_where_the_inferred_rule_is_review(tmp_path):
    """The distinction that justifies both rules existing.

    figure_identity_findings guesses from wording and can be wrong, so it
    advises. The sidecar carries the builder's own naming, so it blocks.
    """
    deck = write_sidecar(tmp_path, [
        {"measure": "m", "value": "1", "slide": "A", "note": ""},
        {"measure": "m", "value": "2", "slide": "B", "note": ""},
    ])
    assert {f[0] for f in vd.figure_sidecar_findings(deck)} == {"FAIL"}


def test_credit_union_financials_is_not_a_union_financial_leak(tmp_path):
    """'CoastLife Credit Union financials' contains 'Union Financial' as a raw
    substring. A plain `in` test flagged every credit union's own correct note."""
    prs = deck_with_notes([("ARS Key Takeaways", ["Chart"],
        "Source: summary of ARS Workbook 1705 — CoastLife Credit Union financials "
        "+ ODD extract 1705 CoastLife Credit Union, Jul 2026 snapshot.")])
    out = vd.source_note_findings(
        str(tmp_path / "1705-2026.08-ARS-CoastLife Credit Union ARS Results.pptx"), prs)
    assert out == [], f"false positive: {out}"


def test_a_real_union_financial_leak_is_still_caught(tmp_path):
    prs = deck_with_notes([("ARS Key Takeaways", ["Chart"],
        "Source: ARS Workbook — Union Financial financials, Jul 2026 snapshot.")])
    out = vd.source_note_findings(
        str(tmp_path / "1705-2026.08-ARS-CoastLife Credit Union ARS Results.pptx"), prs)
    assert out and "Union Financial" in out[0][2]


# --- the ODD pack governs ARS captions only ------------------------------
def test_period_pack_is_not_applied_to_an_mrpc_deck(tmp_path):
    """An ODD snapshot says nothing about VIP-sourced MRPC currency.

    Marine 1539's MRPC deck reads "as of August 2026" against a Jul 2026 ODD and
    is right to — different data, different cadence. Judging it against the ARS
    pack produced eight FAILs on a correct deck.
    """
    import json
    (tmp_path / "oddd_metrics.json").write_text(json.dumps({"latest_month": "Jul26"}))
    deck = tmp_path / "1539-2026.08-MRPC-Marine FCU MRPC Results.pptx"
    assert vd.find_period_pack(str(deck)) is None


def test_period_pack_is_not_applied_to_a_combined_deck(tmp_path):
    import json
    (tmp_path / "oddd_metrics.json").write_text(json.dumps({"latest_month": "Jul26"}))
    deck = tmp_path / "1539-2026.08-ARS-ICS-MRPC-Marine FCU Results.pptx"
    assert vd.find_period_pack(str(deck)) is None, "one pack cannot arbitrate three programs"


def test_period_pack_is_applied_to_an_ars_only_deck(tmp_path):
    import json
    (tmp_path / "oddd_metrics.json").write_text(json.dumps({"latest_month": "Jul26"}))
    deck = tmp_path / "1204-2026.08-ARS-FSB Michigan ARS Results.pptx"
    assert vd.find_period_pack(str(deck)) == {"latest_month": "Jul26"}


def test_span_arithmetic_still_applies_without_a_pack():
    prs = deck([("Trend", ["Jul 2023 – Jun 2026 (30 months)"])])
    assert any(f[0] == "FAIL" for f in vd.period_findings(prs, None))


# =========================================================================
# ICS Comparisons — both sides of a row share one precision
# =========================================================================
def test_average_life_of_account_uses_one_decimal_on_both_sides():
    """A row whose whole purpose is comparing a pair must not print the pair at
    two precisions. "%g" gives the shortest form, so the Velocity average
    rendered "6.9 Years" against a client "6.21 Years", and a client at exactly
    7 rendered "7 Years" (Aaron, 2026-08-30).
    """
    import sys, os
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "build", "ics_pipeline"))
    # cfmt is defined inside build(), so exercise the format it now uses.
    for v, expected in ((6.9, "6.9 Years"), (6.21, "6.2 Years"),
                        (7.0, "7.0 Years"), (7.25, "7.2 Years")):
        assert f"{v:.1f} Years" == expected


def test_the_years_format_is_one_decimal_in_the_builder():
    """Pins the formatter itself, so the row cannot quietly go back to %g."""
    import os
    src = open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "build", "ics_pipeline", "build_ics_gen.py"), encoding="utf-8").read()
    assert 'if f=="years": return f"{v:.1f} Years"' in src, \
        "the Comparisons years format is no longer one decimal"


# --- text drawn over text ---------------------------------------------------
# Ported from the CashPlease project's cp_qa.py (2026-09-02). The Peer Comparison
# footnote was authored at 6.62"; fit_layout pulled it up to 6.14" to clear the
# number band, where it landed 0.56" on top of a row of capsule pills, and this
# validator returned 0 FAIL, 0 REVIEW — every overlap rule it had looked for text
# over a CHART. The rule compares estimated GLYPH boxes, not frames, which is what
# keeps it quiet on the house stacking pattern (the other four tests here).
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN


def _wide():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs, prs.slides.add_slide(prs.slide_layouts[6])


def _text(slide, L, T, W, H, lines, pts, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT,
          shape=None):
    """A text box (or a filled rounded rectangle carrying text) with explicit run sizes."""
    if shape:
        sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                    Inches(L), Inches(T), Inches(W), Inches(H))
    else:
        sh = slide.shapes.add_textbox(Inches(L), Inches(T), Inches(W), Inches(H))
    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, (ln, pt) in enumerate(zip(lines, pts)):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(pt)
    return sh


def test_footnote_pulled_onto_a_row_of_pills_fails():
    prs, s = _wide()
    for i in range(4):
        _text(s, 1.0 + i * 3.0, 6.05, 2.4, 0.5, ["6.7%"], [16],
              anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER, shape=True)
    _text(s, 0.5, 6.14, 12.0, 0.6,
          ["Cohort: the workbook's all-clients rollup — 96,014 CashPlease loans across all 73 "
           "tabs, WesBanco Bank included."], [16])
    out = vd.text_collision_findings(prs)
    assert out and all(f[0] == "FAIL" for f in out), out
    assert "text drawn over text" in out[0][2]


def test_title_frame_touching_the_selection_line_is_quiet():
    """Every ARS title box ends 0.10\" below the top of the selection line's box."""
    prs, s = _wide()
    _text(s, 0.5, 0.28, 12.33, 0.9, ["Overall Debit Swipes & Spend"], [26])
    _text(s, 0.5, 1.12, 12.3, 0.5, ["Selection: all debit-card-holding accounts, program-wide."], [16])
    assert vd.text_collision_findings(prs) == []


def test_oversized_top_anchored_title_box_is_quiet():
    """The ICS 'VIP Best Practices' title sits in a 2.61\" box; its one line does not."""
    prs, s = _wide()
    _text(s, 0.95, 0.33, 10.0, 2.61, ["VIP Best Practices"], [26])
    _text(s, 0.5, 1.18, 12.3, 0.5, ["Five habits that keep referral performance consistent."], [16])
    _text(s, 1.9, 1.98, 10.35, 0.68, ["Identify & Recognize Influencers", "Spotlight the staff who refer."],
          [16, 16], anchor=MSO_ANCHOR.MIDDLE)
    assert vd.text_collision_findings(prs) == []


def test_stacked_callouts_priced_per_paragraph_are_quiet():
    """An ICS callout stacks a 40 pt value over a 16 pt label; pricing both lines at
    40 pt made two stacked callouts overlap by 0.60\" on every ICS deck."""
    prs, s = _wide()
    for i in range(3):
        _text(s, 9.7, 1.6 + i * 1.65, 3.2, 1.45, ["46,979", "Referrals Program-to-Date"], [40, 16],
              anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER, shape=True)
    assert vd.text_collision_findings(prs) == []


def test_a_label_inside_its_own_capsule_is_quiet():
    prs, s = _wide()
    _text(s, 1.0, 2.0, 3.0, 1.5, ["Gold"], [30], anchor=MSO_ANCHOR.MIDDLE,
          align=PP_ALIGN.CENTER, shape=True)
    _text(s, 1.1, 2.1, 2.8, 0.4, ["callout label"], [12], align=PP_ALIGN.CENTER)
    assert vd.text_collision_findings(prs) == []


def test_slide_number_collisions_are_left_to_the_geometry_rule():
    prs, s = _wide()
    _text(s, 0.45, 7.05, 0.7, 0.3, ["12"], [10])
    _text(s, 0.4, 6.95, 6.0, 0.4, ["A footnote that runs under the slide number."], [16])
    assert vd.text_collision_findings(prs) == []
    assert any("slide number" in f[2] for f in vd.geometry_findings(prs))


# --- the runner -------------------------------------------------------------
def test_every_rule_is_registered_and_named_as_a_finding():
    assert all(r.__name__.endswith("_findings") for r in vd.RULES)
    assert vd.text_collision_findings in vd.RULES


def test_run_sorts_fails_before_reviews_on_a_shell():
    tpl = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "templates", "mrpc_template.pptx")
    out = vd.run(tpl)
    levels = [f[0] for f in out]
    assert levels == sorted(levels, key={"FAIL": 0, "REVIEW": 1}.get)
    assert "FAIL" not in levels


# --- package integrity ------------------------------------------------------
# These carry more weight since the LibreOffice render smoke test was removed on
# 2026-09-11: it could never run on the build machine, so what it would have
# caught has to be caught structurally or not at all.
def _pptx(tmp_path, name="deck.pptx"):
    tpl = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "templates", "mrpc_template.pptx")
    out = str(tmp_path / name)
    import shutil
    shutil.copy2(tpl, out)
    return out


def test_a_sound_package_reports_nothing(tmp_path):
    assert vd.package_findings(_pptx(tmp_path)) == []


def test_a_part_written_twice_is_a_fail(tmp_path):
    """python-pptx reads a duplicated part back without complaint, so every text
    and geometry rule still passes. It happened on 2026-09-11 cloning the Summit
    slide: relating the asset's image Part carried its partname along, and a deck
    that already held /ppt/media/image2.png got the entry twice. The slide-part
    checks above cannot see it — these are MEDIA parts.
    """
    import warnings, zipfile
    good = _pptx(tmp_path)
    bad = str(tmp_path / "dupe.pptx")
    zin = zipfile.ZipFile(good)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)   # forging the defect on purpose
        with zipfile.ZipFile(bad, "w", zipfile.ZIP_DEFLATED) as zout:
            for n in zin.namelist():
                zout.writestr(n, zin.read(n))
            dupe = next(n for n in zin.namelist() if n.startswith("ppt/"))
            zout.writestr(dupe, zin.read(dupe))
    zin.close()
    out = vd.package_findings(bad)
    assert any(f[0] == "FAIL" and "more than once" in f[2] for f in out), out


def test_a_corrupt_member_is_a_fail(tmp_path):
    """testzip()'s CRC check — a truncated part opens as a zip and fails to read."""
    import zipfile
    good = _pptx(tmp_path)
    bad = str(tmp_path / "corrupt.pptx")
    raw = bytearray(open(good, "rb").read())
    # Flip bytes inside the compressed payload, leaving the central directory intact.
    first = zipfile.ZipFile(good).infolist()[0]
    off = first.header_offset + 200
    for i in range(off, min(off + 64, len(raw))):
        raw[i] ^= 0xFF
    open(bad, "wb").write(bytes(raw))
    out = vd.package_findings(bad)
    assert any(f[0] == "FAIL" for f in out), out


# --- the Summit slide's date ------------------------------------------------
def _summit_deck(text):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(0.5))
    tb.text_frame.text = "Executive Summit is an action-packed event!"
    tb2 = s.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(0.5))
    tb2.text_frame.text = text
    return prs


def test_a_future_summit_is_silent():
    import datetime
    d = datetime.date.today() + datetime.timedelta(days=60)
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    txt = "Somewhere, XX  %s %d-%d, %d" % (months[d.month - 1], d.day, d.day, d.year)
    assert vd.summit_date_findings(_summit_deck(txt)) == []


def test_a_summit_that_has_passed_is_flagged():
    """Eighteen delivered 2026.09 decks advertised a Summit eleven days gone and
    nothing failed (2026-09-11). summit_period() warned on stderr, but only when a
    build called it for a reporting month — a warning in a log is not a gate."""
    import datetime
    d = datetime.date.today() - datetime.timedelta(days=11)
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    txt = "Boston, MA  %s %d, %d" % (months[d.month - 1], d.day, d.year)
    out = vd.summit_date_findings(_summit_deck(txt))
    assert len(out) == 1 and out[0][0] == "REVIEW", out
    assert "has passed" in out[0][2] and "11 days ago" in out[0][2], out[0][2]


def test_the_summit_rule_is_review_not_fail():
    """A deck built the day before an event is indistinguishable from one built the
    day after it ended, and a rebuild of an older period must not be blocked."""
    import datetime
    d = datetime.date.today() - datetime.timedelta(days=400)
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    txt = "Old Town, XX  %s %d, %d" % (months[d.month - 1], d.day, d.year)
    assert all(f[0] == "REVIEW" for f in vd.summit_date_findings(_summit_deck(txt)))


def test_the_summit_rule_is_registered():
    assert vd.summit_date_findings in vd.RULES
