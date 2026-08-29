"""summit_slide — reading the Executive Summit's date off its own slide.

The Summit and the monthly client reviews are TWO DIFFERENT DELIVERIES: a Summit
runs a couple of times a year and only for attendees, while the reviews go out
monthly (Aaron, 2026-08-29). So this date describes the Summit slide and nothing
else — in particular it does NOT drive a deck's reporting month, which comes from
ARS_PERIOD or the output filename.
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


def test_summit_period_reads_the_current_slide():
    """Aug 31 - Sep 1 2026, per the slide as printed. That the 2026.08 decks share
    the month is coincidence, not a relationship — the next Summit is November."""
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


# --- where the slide comes from ------------------------------------------
def test_the_repo_copy_is_the_default():
    """The common path touches no network and cannot drift."""
    import summit_slide as ss
    assert ss._asset() == ss._REPO_ASSET or "Inputs/Summit" in ss._asset()


def test_drive_overrides_the_repo_copy(tmp_path, monkeypatch):
    """The slide is replaced by hand before each Summit, by someone who should
    not need a commit to ship it."""
    import summit_slide as ss
    drive = tmp_path / "Summit"; drive.mkdir()
    slide = drive / "summit_slide.pptx"
    shutil_src = ss._REPO_ASSET
    import shutil; shutil.copy(shutil_src, slide)
    monkeypatch.setattr(ss, "inputs", lambda: tmp_path, raising=False)
    import rpe_env
    monkeypatch.setattr(rpe_env, "inputs", lambda: tmp_path)
    assert ss._asset() == str(slide)


def test_a_missing_drive_folder_falls_back_silently(monkeypatch):
    """A build must not fail because the optional override is absent."""
    import summit_slide as ss, rpe_env
    monkeypatch.setattr(rpe_env, "inputs",
                        lambda: (_ for _ in ()).throw(SystemExit("no root")))
    assert ss._asset() == ss._REPO_ASSET
