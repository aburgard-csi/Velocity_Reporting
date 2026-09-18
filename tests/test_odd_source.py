"""The ODD member inside an ODDD zip is chosen in ONE place (2026-09-18).

Several zips carry the month's transaction file as a second .csv, sometimes the larger of
the two. Ten files each carried their own rule for picking the ODD member, and they did not
agree: metrics_gen, combined_insights, responder_activity, lift_extract, tier_movement_slides,
perf_overview and rpe_env matched "-odd" or "_v2_" case-insensitively and fell back to the
largest .csv; oddd_optimize matched "-ODD" case-sensitively and fell back to the FIRST .csv;
the issue pages matched "-ODD" and gave up. A zip whose ODD member is named in lower case
would have been read by the deck and skipped by the pack. `odd_rows.odd_member` is now the
one rule, and this file fails if a second copy appears.
"""
import io
import re
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
import odd_rows  # noqa: E402

HEADER = "\n\n\n\n5,Acct ID,Acct Number\n1,A,1\n"


def _zip(tmp_path, members):
    p = tmp_path / "1441_ODDD.zip"
    with zipfile.ZipFile(p, "w") as z:
        for name, body in members.items():
            z.writestr(name, body)
    return p


def test_the_odd_member_is_picked_by_name_before_size(tmp_path):
    p = _zip(tmp_path, {
        "1441-2026.08-FNB Alaska-Monthly Transaction File.csv": "x" * 5000,
        "1441-2026.08-FNB Alaska-ODD v2_1 (090126_154106).csv": HEADER,
    })
    with zipfile.ZipFile(p) as z:
        assert odd_rows.odd_member(z) == "1441-2026.08-FNB Alaska-ODD v2_1 (090126_154106).csv"


def test_a_lower_case_odd_member_is_still_the_odd_member(tmp_path):
    p = _zip(tmp_path, {"big transactions.csv": "x" * 5000, "1441-odd extract.csv": HEADER})
    with zipfile.ZipFile(p) as z:
        assert odd_rows.odd_member(z) == "1441-odd extract.csv"


def test_without_a_named_member_the_largest_csv_wins(tmp_path):
    p = _zip(tmp_path, {"small.csv": HEADER, "large.csv": "x" * 5000, "readme.txt": "y" * 9000})
    with zipfile.ZipFile(p) as z:
        assert odd_rows.odd_member(z) == "large.csv"


def test_a_zip_with_no_csv_is_refused(tmp_path):
    p = _zip(tmp_path, {"readme.txt": "y"})
    with zipfile.ZipFile(p) as z, pytest.raises(FileNotFoundError):
        odd_rows.odd_member(z)


def test_open_odd_reads_the_member_in_stream_and_names_it(tmp_path):
    p = _zip(tmp_path, {"txn.csv": "x" * 5000, "1441-ODD (090126_154106).csv": HEADER})
    fh, name = odd_rows.open_odd(str(p))
    with fh:
        assert fh.read() == HEADER
    assert name == "1441-ODD (090126_154106).csv"


def test_open_odd_on_a_plain_csv_names_the_file(tmp_path):
    p = tmp_path / "1441-ODD (090126_154106).csv"
    p.write_text(HEADER, encoding="latin-1")
    fh, name = odd_rows.open_odd(str(p))
    with fh:
        assert fh.read() == HEADER
    assert name == p.name


def test_odd_source_gives_a_fresh_stream_each_time(tmp_path):
    p = _zip(tmp_path, {"1441-ODD.csv": HEADER})
    factory, name = odd_rows.odd_source(str(p))
    with factory() as a:
        first = a.read()
    with factory() as b:
        second = b.read()
    assert first == second == HEADER and name == "1441-ODD.csv"


def test_open_odd_can_extract_to_a_folder(tmp_path):
    p = _zip(tmp_path, {"txn.csv": "x" * 5000, "1441-ODD.csv": HEADER})
    out = odd_rows.extract_odd(str(p), tmp_path / "out")
    assert Path(out).name == "1441-ODD.csv"
    assert Path(out).read_text(encoding="latin-1") == HEADER
    assert not (tmp_path / "out" / "txn.csv").exists()


_MEMBER_RULE = re.compile(r"""['"]-odd['"]|['"]-ODD['"]|['"]_v2_['"]""")


def test_no_other_file_carries_the_member_rule():
    """The literal that picks the ODD member lives in odd_rows.py and nowhere else."""
    offenders = []
    for folder in ("build", "scripts", "validation"):
        for p in (REPO / folder).rglob("*.py"):
            if p.name == "odd_rows.py":
                continue
            src = p.read_text(encoding="utf-8", errors="replace")
            if _MEMBER_RULE.search(src):
                offenders.append(str(p.relative_to(REPO)))
    assert not offenders, f"the ODD member rule is copied in: {offenders}"


@pytest.mark.parametrize("rel", [
    "build/ars_pipeline/metrics_gen.py",
    "build/ars_pipeline/combined_insights.py",
    "build/ars_pipeline/responder_activity.py",
    "build/ars_pipeline/lift_extract.py",
    "build/ars_pipeline/tier_movement_slides.py",
    "build/rpe_env.py",
    "scripts/oddd_optimize.py",
    "scripts/perf_overview.py",
    "scripts/issue_pages/mail_flags.py",
    "scripts/issue_pages/business_flags.py",
    "scripts/issue_pages/noprog_odd_dates.py",
])
def test_every_odd_reader_goes_through_odd_rows(rel):
    src = (REPO / rel).read_text(encoding="utf-8", errors="replace")
    assert re.search(r"\b(open_odd|odd_source|odd_member|extract_odd)\b", src), \
        f"{rel} must pick the ODD member through odd_rows"
