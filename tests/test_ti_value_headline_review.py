"""Sheila's slide review of 1798 FirstLight FCU's Transaction Intelligence deck (2026-10-30): the
Value chapter and the headline copy.

Slide 95 printed a rate card with no unit ("1.86 to 30.58 a month"); slides 97 and 98 ran 101 and 94
words; slides 98, 99, 101 and 102 said value per account four times (group Q, now two slides); the
Value footnotes were 9.5pt; and headline copy shipped "the newest offer 1", "earned $1.9M of program
profit in 29 months", "not customers: book: cards 72%" and "branch gaps" that were account-age bands.
"""
from pptx import Presentation

from ti.chapters import value as C
from ti.deck import headlines as H

from test_ti_value_chapter import _Ctx, _prs, _text

LIFT = {"wb_lift_cols": ["1-5", "6-10"], "wb_lift_rows": [["NU", 1.86, 8.74], ["1-5", None, 30.58]]}


def test_the_rate_card_title_always_states_its_unit():
    # 1798's caption names revenue but carries no "$": v5 printed the numbers bare
    head = H.lift_matrix(dict(LIFT, wb_lift_caption="Monthly Incremental Revenue Lift"))[0]
    assert head == "Every segment climbs, $1.86 to $30.58 a month"
    assert H.lift_matrix(dict(LIFT, wb_lift_caption="Revenue per account per month ($)"))[0] \
        == "Every segment climbs, $1.86 to $30.58 a month"
    assert H.lift_matrix(dict(LIFT))[0] == "Every segment climbs, $1.86 to $30.58 a month"
    assert H.lift_matrix(dict(LIFT, wb_lift_caption="Monthly swipe lift"))[0] \
        == "Every segment climbs, 1.86 to 30.58 swipes a month"
    other = H.lift_matrix(dict(LIFT, wb_lift_caption="Points per month"))[0]
    assert other == "Every segment climbs, 1.86 to 30.58 points a month"
    assert H.lift_unit({"wb_lift_caption": "()"}) == "units"


def test_counts_take_their_noun_in_the_right_number():
    assert H._count(1, "month") == "1 month" and H._count(27, "month") == "27 months"
    assert H._count(1, "branch", "branches") == "1 branch" and H._count(3, "branch", "branches") == "3 branches"
    waves = {"wb_wave_revenue": [["Jun24", "2024-06", 100.0], ["Jun24", "2024-07", 100.0],
                                 ["Sep26", "2026-09", 5.0]]}
    sub = H.wave_totals(waves)[1]
    assert "the newest offer 1 month;" in sub and "Jun24 has had 2 months" in sub


def test_the_hero_says_profit_once():
    head = H.hero({"wb_profit_ltd": 1_900_000, "wb_months_in_program": 29, "wb_revenue_ltd": 3_300_000})[0]
    assert head == "$1.9M of program profit earned over 29 months"
    assert H.hero({"wb_profit_ltd": 10, "wb_months_in_program": 1})[0].endswith("over 1 month")


def test_card_gaps_are_called_branch_gaps_only_when_they_are_branches():
    def row(dim, seg):
        return {"dimension": dim, "segment": seg, "share_of_volume": 45.5, "share_of_outcome": 42.4}
    mixed = {"dctr_leaks": [row("account age", "10+ yr"), row("account age", "5-10 yr"), row("branch", "301")],
             "dctr_leak_total": 3915, "dctr_leak_value": 723570}
    head, sub = H.leaks(mixed)
    assert head == "Closing the three widest card gaps is worth $724K a year"
    assert sub.startswith("The 10+ yr account age band holds 46%")
    branches = dict(mixed, dctr_leaks=[row("branch", "301"), row("branch", "410")])
    head, sub = H.leaks(branches)
    assert "branch gaps" in head and sub.startswith("Branch 301 holds")
    assert "widest card gaps" in H.closing(mixed)[1]


def test_awkward_constructions_are_gone():
    sub = H.divergence({"branch_divergence": [["410", 4438, 82.7, 26.6, 10.8, -10.2]],
                        "dctr_overall": 71.9, "rege_pct": 36.8})[1]
    assert "—" not in sub and "; the book runs cards 72%, Reg E 37%" in sub
    head = H.value_ladder({"value_by_account_age": [{"value_per_acct": 82}, {"value_per_acct": 180}],
                           "value_age_biggest_step": {"from": "< 1 yr", "to": "1-2 yr", "step": 97.6}})[0]
    assert head == "Value per account climbs $98 from under 1 yr to 1-2 yr"
    ba = H.before_after({"ba_lift_net": 524, "ba_control_before": 308, "ba_control_after": 279,
                         "ba_spend_before": 604, "ba_spend_after": 1100})[0]
    assert "three months after" in ba    # its window, beside the 12-month cohort figure
    assert H.health({"retention_carded_n": 5, "retention_at_risk_n": 1,
                     "retention_health": [["Never activated", 1]]})[0] == "1 card has been issued and never used"


M1798 = {"value_debit_delta": 185.2, "value_rege_delta": 77.4, "value_debit_n_without": 23825,
         "value_rege_n_without": 39153, "take_new_pct": 96.5, "rege_pct": 36.8, "value_per_card": 185.2,
         "value_per_optin": 77.4, "value_debit_pot_l12m": 4247789,
         "value_by_account_age": [{"group": "< 1 yr", "rev_with": 83.8, "rev_without": 28.2, "value_per_acct": 81.9},
                                  {"group": "1-2 yr", "rev_with": 188.4, "rev_without": 56.2, "value_per_acct": 179.5}],
         "value_age_biggest_step": {"from": "< 1 yr", "to": "1-2 yr", "step": 97.61},
         "value_debit_pot_hist": 3.2e6, "value_debit_pot_full": 4.4e6,
         "value_rege_pot_elected": 1.2e6, "value_rege_pot_full": 3.0e6,
         "dctr_leaks": [{"dimension": "account age", "segment": "10+ yr", "accounts_lost": 2033,
                         "share_of_volume": 45.5, "share_of_outcome": 42.4},
                        {"dimension": "branch", "segment": "301", "accounts_lost": 809,
                         "share_of_volume": 7.4, "share_of_outcome": 5.4}],
         "dctr_leak_total": 2842, "dctr_leak_value": 723570,
         "value_branch_best": {"group": "410", "value_per_acct": 175.6},
         "value_branch_worst": {"group": "314", "value_per_acct": 89.84},
         "value_branch_spread": 85.76, "value_branch_penetration_share": 45.4,
         "branch_divergence": [["410", 4438, 82.7, 26.6, 10.8, -10.2]],
         "dctr_overall": 71.9}


def _built(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("TI_SLIDES", str(tmp_path / "none.json"))     # every slide kept
    slides = C.build(_Ctx(_prs(), M1798, tmp_path))
    return dict(zip(C.TITLES.values(), slides))


def _words(slide):
    n = 0
    for sh in slide.shapes:
        if sh.has_text_frame:
            n += len(sh.text_frame.text.split())
        if getattr(sh, "has_table", False) and sh.has_table:
            n += sum(len(c.text.split()) for row in sh.table.rows for c in row.cells)
    return n


def test_the_card_slide_and_the_ladder_hold_to_sixty_words_and_keep_what_was_cut_in_notes(tmp_path, monkeypatch):
    by = _built(tmp_path, monkeypatch)
    card, ladder = by["What a card and an opt-in earn"], by["The value ladder"]
    assert _words(card) <= 60, _text(card)
    assert _words(ladder) <= 60, _text(ladder)
    for s, kept in ((card, "39,153 not opted in"), (ladder, "Per card: $185")):
        notes = s.notes_slide.notes_text_frame.text
        assert notes.startswith("Source:") and kept in notes, notes


def test_group_q_puts_the_branch_findings_on_the_card_gap_slide(tmp_path, monkeypatch):
    gaps = _text(_built(tmp_path, monkeypatch)["Where cards do not follow volume"])
    assert "$724K" in gaps and "$86" in gaps and "410 $176 vs 314 $90" in gaps
    assert "45%" in gaps and "-10.2 pts" in gaps
    assert set(C.GROUP_Q_TOSS) <= set(C.TITLES.values())


def test_value_footnotes_are_at_least_ten_and_a_half_point(tmp_path, monkeypatch):
    for title, s in _built(tmp_path, monkeypatch).items():
        sizes = [r.font.size.pt for sh in s.shapes if sh.has_text_frame
                 for p in sh.text_frame.paragraphs for r in p.runs
                 if r.font.size and sh.top > 6.3 * 914400 and sh.text_frame.text.strip()
                 and not sh.text_frame.text.strip().isdigit()]
        assert all(pt >= 10.5 for pt in sizes), (title, sizes)
