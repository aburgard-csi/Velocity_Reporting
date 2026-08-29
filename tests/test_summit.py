"""summit_slide — the Executive Summit date as the reporting month.

STYLE.md draws a hard line between two months, and it is easy to get backwards:

  * the cover and one-pager header carry the month the report is PRESENTED
    (STYLE.md:85);
  * the period pills and PTD figures carry the DATA month (STYLE.md:44,
    explicitly "NOT the report/generation month").

These decks are prepared FOR the Summit, so the Summit's month is the month they
are presented in. Read from the shared Summit slide rather than hardcoded, so it
moves when that slide does.
"""
import datetime
import pytest
from summit_slide import summit_date, summit_period, _SUMMIT_DATE_RE, ASSET


def test_the_asset_carries_a_parseable_summit_date():
    d = summit_date()
    assert d is not None, f"no Summit date found in {ASSET}"
    assert isinstance(d, datetime.date)


def test_summit_period_is_yyyy_dot_mm():
    p = summit_period()
    assert p and len(p) == 7 and p[4] == "."
    assert p[:4].isdigit() and p[5:].isdigit()


def test_summit_period_matches_the_deck_filenames():
    """Delivered decks are named <id>-2026.08-ARS-...; the Summit is Aug 31 2026."""
    assert summit_period() == "2026.08"


@pytest.mark.parametrize("text,expected", [
    ("Boston, MA  August 31-September 1, 2026", (2026, 8, 31)),
    ("Chicago, IL  September 9-10, 2027", (2027, 9, 9)),
    ("Austin, TX  May 4, 2028", (2028, 5, 4)),
    ("Boston, MA  August 31 – September 1, 2026", (2026, 8, 31)),
    ("Boston, MA  August 31—September 1, 2026", (2026, 8, 31)),
])
def test_a_date_range_takes_its_start(text, expected):
    m = _SUMMIT_DATE_RE.search(" ".join(text.split()))
    assert m, f"did not parse {text!r}"
    months = ["January","February","March","April","May","June","July",
              "August","September","October","November","December"]
    got = (int(m.group(3)), months.index(m.group(1)) + 1, int(m.group(2)))
    assert got == expected


def test_unparseable_asset_returns_none_rather_than_raising(tmp_path):
    """Callers decide whether a missing Summit date is fatal."""
    assert summit_date(str(tmp_path / "no-such-file.pptx")) is None
    assert summit_period(str(tmp_path / "no-such-file.pptx")) is None


def test_stale_summit_warns_but_still_returns(tmp_path, monkeypatch, capsys):
    """The slide is printed ahead of each Summit and not revised until the next.

    The August 2026 slides went to print 2026-08-29, so the asset keeps saying
    August until the November materials land. A build falling back to it after
    the Summit is reading a stale date and should be told — but the clock is
    used only to WARN, never to derive the value.
    """
    import summit_slide as ss
    monkeypatch.setattr(ss, "summit_date", lambda asset=None: datetime.date(2020, 5, 1))
    out = ss.summit_period()
    captured = capsys.readouterr()
    assert out == "2020.05", "the value is still returned"
    assert "has passed" in captured.err


def test_future_summit_does_not_warn(monkeypatch, capsys):
    import summit_slide as ss
    monkeypatch.setattr(ss, "summit_date", lambda asset=None: datetime.date(2099, 11, 1))
    ss.summit_period()
    assert "has passed" not in capsys.readouterr().err


def test_warning_can_be_suppressed(monkeypatch, capsys):
    import summit_slide as ss
    monkeypatch.setattr(ss, "summit_date", lambda asset=None: datetime.date(2020, 5, 1))
    ss.summit_period(warn_if_past=False)
    assert "has passed" not in capsys.readouterr().err
