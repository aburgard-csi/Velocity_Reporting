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
