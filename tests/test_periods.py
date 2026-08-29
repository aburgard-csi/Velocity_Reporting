"""periods — one derivation for every date phrase a deck renders.

A literal month is legitimate when it is the month being described. What this
module removes is HAND-DERIVED phrasing: windows, spans and month counts
computed inside an f-string, which go stale the next time the data moves and
have to be found by reading slides.
"""
import datetime
import pytest
from periods import Period, parse_month, month_diff, shift


# --- parsing every form the pipeline uses --------------------------------
@pytest.mark.parametrize("token", ["Jul26", "Jul 2026", "July 2026", "Jul. 2026",
                                   "2026-07", "07-2026"])
def test_parse_month_accepts_pipeline_forms(token):
    assert parse_month(token) == datetime.date(2026, 7, 1)


@pytest.mark.parametrize("bad", ["", None, "Smarch 2026", "2026", "13-2026", "xx99"])
def test_parse_month_rejects_nonsense(bad):
    assert parse_month(bad) is None


# --- inclusive arithmetic -------------------------------------------------
def test_month_diff_is_inclusive():
    """Jul 2023 through Jun 2026 is 36 months, not 35."""
    assert month_diff(datetime.date(2023, 7, 1), datetime.date(2026, 6, 1)) == 36


def test_month_diff_same_month_is_one():
    assert month_diff(datetime.date(2026, 7, 1), datetime.date(2026, 7, 1)) == 1


@pytest.mark.parametrize("n,expected", [
    (0, (2026, 7)), (-1, (2026, 6)), (1, (2026, 8)),
    (-7, (2025, 12)), (-12, (2025, 7)), (6, (2027, 1)),
])
def test_shift_crosses_year_boundaries(n, expected):
    d = shift(datetime.date(2026, 7, 1), n)
    assert (d.year, d.month) == expected


# --- the rendered phrases -------------------------------------------------
@pytest.fixture
def p():
    return Period.from_pack({"latest_month": "Jul26"})


def test_point_in_time_phrases(p):
    assert p.label() == "July 2026"
    assert p.short() == "Jul 2026"
    assert p.token() == "Jul26"
    assert p.as_of() == "as of July 2026"
    assert p.data_pill() == "July 2026 Data"
    assert p.ptd() == "PTD · July 2026"


def test_window_ends_at_the_snapshot(p):
    assert p.window(12) == ("Aug25", "Jul26")
    assert p.window(1) == ("Jul26", "Jul26")
    assert p.window(36) == ("Aug23", "Jul26")


def test_span_label_derives_its_own_count(p):
    """The count is computed from the endpoints, never typed beside them."""
    assert p.span_label(36) == "Aug 2023 – Jul 2026 (36 months)"
    assert p.span_label(12) == "Aug 2025 – Jul 2026 (12 months)"
    assert p.span_label(1) == "Jul 2026 – Jul 2026 (1 month)"


@pytest.mark.parametrize("n", [1, 2, 3, 6, 12, 24, 36, 50])
def test_span_label_count_always_matches_its_endpoints(p, n):
    import re
    label = p.span_label(n)
    a, b, claimed = re.match(
        r"(\w+ \d{4}) – (\w+ \d{4}) \((\d+) month", label).groups()
    assert month_diff(parse_month(a), parse_month(b)) == int(claimed) == n


def test_trailing_collapses_the_year_within_one_year(p):
    assert p.trailing(3) == "May–Jul 2026"


def test_trailing_keeps_both_years_across_a_boundary(p):
    assert p.trailing(12) == "Aug 2025–Jul 2026"


def test_months_since(p):
    assert p.months_since("Jul23") == 37
    assert p.months_since("Jul26") == 1


# --- the pack is the only source -----------------------------------------
def test_from_pack_prefers_latest_month():
    p = Period.from_pack({"latest_month": "Jul26", "period": "2026-08"})
    assert p.token() == "Jul26"


def test_from_pack_falls_back_to_period():
    assert Period.from_pack({"period": "2026-08"}).token() == "Aug26"


def test_from_pack_never_defaults_to_today():
    """A deck built in September from a July extract still reports July."""
    with pytest.raises(ValueError):
        Period.from_pack({})


def test_unparseable_month_is_refused_not_guessed():
    with pytest.raises(ValueError):
        Period("Smarch 2026")


def test_window_of_zero_is_refused(p):
    with pytest.raises(ValueError):
        p.window(0)


# --- the reporting month (STYLE.md:85), as opposed to the data month ------
def test_reporting_month_prefers_the_filename_period():
    import build_ars_onepager as op
    assert op._reporting_month("/x/1204-2026.08-ARS-Client.pdf") == "August 2026"


def test_reporting_month_refuses_rather_than_guessing(monkeypatch):
    """No clock, and no Summit either.

    date.today() was the original bug — right only in the month a deck ships.
    The Executive Summit's month is not a substitute: a Summit runs a couple of
    times a year and only for attendees, while this is the MONTHLY delivery.
    """
    import build_ars_onepager as op
    monkeypatch.delenv("RPE_PERIOD", raising=False)
    monkeypatch.delenv("ARS_PERIOD", raising=False)
    with pytest.raises(SystemExit) as e:
        op._reporting_month("/x/onepager-with-no-period.pdf")
    assert "RPE_PERIOD" in str(e.value)


def test_reporting_month_env_overrides_everything(monkeypatch):
    import build_ars_onepager as op
    monkeypatch.setenv("RPE_PERIOD", "2027.03")
    assert op._reporting_month("/x/1204-2026.08-ARS-Client.pdf") == "March 2027"
