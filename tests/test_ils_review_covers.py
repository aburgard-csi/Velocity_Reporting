"""The ILS review reader takes the client and the date from every cover style the analysis team has used (Aaron, 2026-11-09:
"teach the reader the other review layouts"), and says so when a review's figures are pictures.

Of the 46 reviews landed on 2026-11-06 only 5 had text tables; the other 41 are decks whose tables are pasted in as
images. Fixing the covers recovered none of them (their figures are not in the text layer), so the reader now says that
plainly instead of "this does not look like an ILS Program Analysis". The cover text below is invented: no real client.
"""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]

from review_page import ils_review_pack as R        # noqa: E402

NOTICE = "This document constitutes the confidential and proprietary information (and includes trade secrets) of Velocity Solutions, LLC"
FILE = "9001-2026.09-ILS-Test Bank ILS Review.pdf"


def title(*pages, source=FILE):
    return R._title_block(list(pages), source)


# ----------------------------------------------------------------- the cover styles
def test_the_original_cover():
    assert title(f"Partnering for Success Test Bank September 3, 2026") == ("Test Bank", "2026-09-03", "cover")


def test_the_2026_cover_with_stray_spaces_in_its_words():
    t = f"PA RTNERING FO R SUCCESS · ANNUAL REVIEW ILS® Program Analysis Test Bank & Trust October 6, 2026 Prepared by Velocity Solutions, LLC {NOTICE}"
    assert title(t) == ("Test Bank & Trust", "2026-10-06", "cover")


def test_the_2026_cover_names_the_client_as_it_prints_it_not_as_the_file_does():
    t = "PARTNERING FOR SUCCESS · ANNUAL REVIEW ILS® Program Analysis FirstTest September 3, 2026 Prepared by Velocity Solutions, LLC"
    assert title(t)[0] == "FirstTest"


def test_the_2018_cover():
    assert title("ILS Program Analysis Test and Marine Bank June 18, 2018", source="9001-2018.06-ILS-Test & Marine Bank ILS Review.pdf") == (
        "Test and Marine Bank", "2018-06-18", "cover")


def test_both_phrases_on_one_cover_leave_no_marker_in_the_name():
    got = title("ILS Program Analysis Partnering for Success Test Bank June 24, 2026")
    assert got == ("Test Bank", "2026-06-24", "cover")


def test_a_title_may_sit_on_the_second_or_third_page():
    assert title(f"| v {NOTICE}", "Partnering for Success Test Bank March 12, 2024") == ("Test Bank", "2024-03-12", "cover")


# ----------------------------------------------------------------- a cover with no title
@pytest.mark.parametrize("cover", [
    f"| v {NOTICE}",
    f"Partnering for Success INTELLIGENT LIMIT SYSTEM® Program Performance Analysis {NOTICE}",
])
def test_a_cover_with_no_client_or_date_takes_the_file_name_and_gives_no_day(cover):
    assert title(cover) == ("Test Bank", None, "file name")


def test_a_later_page_is_not_mistaken_for_a_title():
    page2 = "INDUSTRY UPDATE ILS® Program Analysis 2 Confidential and proprietary information • Recent client alerts April 21, 2022"
    assert title(f"| v {NOTICE}", page2) == ("Test Bank", None, "file name")


def test_a_cover_with_no_title_and_a_file_name_that_does_not_give_the_client_is_refused():
    with pytest.raises(R.ReviewReadError):
        title(f"| v {NOTICE}", source="review.pdf")


def test_the_file_name_gives_the_client_and_nothing_else():
    assert R._name_from_file("1204-2026.09-ILS-FSB Michigan ILS Review.pdf") == "FSB Michigan"
    assert R._name_from_file("1075-2024.03-ILS-Austin Bank ILS Review") == "Austin Bank"
    assert R._name_from_file("notes.pdf") is None


# ----------------------------------------------------------------- the pack records what the cover could not
DEMOGRAPHICS = ("FI DEMOGRAPHIC INFORMATION HQ: Testville, KY • Asset Size: $400M • Branches: 4 • Active DDA Accounts: 9,000 • "
                "Primary Federal Regulator: FDIC • Core Provider: Core • Core Product: Prod • ILS® Version: 24.1 • "
                "ILS® Go Live Date: 01/05/2026 • Contract Start: 01/01/2026 • Contract End: 12/31/2028 • Data Analyzed Through: 08/31/2026")
OPPORTUNITY = "Confidential and proprietary information OPPORTUNITY ANALYSIS • Eligibility: ILS can produce lists • Reg E: opt-in is 40%"


def test_a_review_whose_tables_are_pictures_is_refused_with_the_reason():
    pages = [f"| v {NOTICE}", DEMOGRAPHICS, OPPORTUNITY]
    with pytest.raises(R.ReviewReadError) as e:
        R.parse(pages, FILE, "9001")
    assert "pictures" in str(e.value) and "only 2" in str(e.value)
    assert "does not look like" not in str(e.value)


def test_a_dateless_cover_pack_carries_the_month_and_no_day(monkeypatch):
    # three readable tables: the stubs stand in for the real tables so only the title handling is under test
    for key in ("_peer_comparison", "_utilization", "_mature", "_monthly"):
        monkeypatch.setattr(R, key, lambda pages, _k=key: ({"stub": True}, 3) if _k == "_utilization" else (None, None))
    pages = [f"| v {NOTICE}", DEMOGRAPHICS, OPPORTUNITY]
    pack = R.parse(pages, FILE, "9001")
    assert pack["client_name"] == "Test Bank"
    assert pack["review_date"] is None
    assert pack["review_period"] == "2026-09"
    assert pack["title_from"] == "file name"
    assert {"institution", "utilization", "opportunity"} <= set(pack["pages"])


def test_a_dated_cover_pack_carries_both(monkeypatch):
    for key in ("_peer_comparison", "_utilization", "_mature", "_monthly"):
        monkeypatch.setattr(R, key, lambda pages, _k=key: ({"stub": True}, 3) if _k == "_utilization" else (None, None))
    pages = ["Partnering for Success Test Bank September 3, 2026", DEMOGRAPHICS, OPPORTUNITY]
    pack = R.parse(pages, FILE, "9001")
    assert (pack["review_date"], pack["review_period"], pack["title_from"]) == ("2026-09-03", "2026-09", "cover")
