"""The cut's two lenses on a client's ODD frame (build/ars_pipeline/ti/lens.py).

The ICS lists are found where RPE files them (Inputs/ICS Direct Mail, Inputs/ICS Referrals),
staged for v5's join unchanged, and joined by account hash. A lens with no accounts raises
LensUnavailable with the sentence the deck states.
"""
import hashlib

import pandas as pd
import pytest

from ti import lens, odd
from ti.monthly_analysis import ics_sources


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs/ICS Direct Mail", "Inputs/ICS Referrals", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture(scope="module")
def frame(odd_csv):
    f, _ = odd.load(odd_csv)
    return f


def _dm_list(path, ids):
    """A direct-mail export: a preamble, then a header row carrying the account hash."""
    rows = [["Direct Mail New Accounts Opened PTD"], [], ["Account Mask", "MRDB Account Hash"]]
    rows += [[f"****{i[-4:]}", hashlib.sha1(i.encode()).hexdigest().upper()] for i in ids]
    pd.DataFrame(rows).to_excel(path, header=False, index=False)


def test_ars_lens_groups_are_the_response_groups(frame):
    masks = lens.lens_masks(frame, "ars", pd.Timestamp("2026-09-30"))
    assert list(masks) == [k for k in ("responders", "mailed_nonresp", "not_mailed") if k in masks]
    assert masks and all(m.any() for m in masks.values())


def test_ics_lens_without_lists_is_stated_not_rendered(frame, root):
    said = []
    f = lens.attach_ics(frame, "9999", said.append, expected=True)
    assert "DM-REF Source" not in f.columns and said and "no direct-mail" in said[0]
    with pytest.raises(lens.LensUnavailable, match="No ICS accounts"):
        lens.lens_masks(f, "ics", pd.Timestamp("2026-09-30"))


def test_ics_lists_are_found_by_client_id_and_joined(frame, root):
    ids = ics_sources._account_ids(frame).head(25).tolist()
    _dm_list(root / "Inputs/ICS Direct Mail" / "9999-2026.10-ICS-Test Bank-Direct Mail New Accounts Opened PTD.xlsx", ids)
    _dm_list(root / "Inputs/ICS Direct Mail" / "1234-2026.10-ICS-Other-Direct Mail New Accounts Opened PTD.xlsx", ids[:3])
    files = lens.ics_list_files("9999")
    assert files["DM"].name.startswith("9999-") and files["REF"] is None
    said = []
    f = lens.attach_ics(frame, "9999", said.append, expected=True)
    masks = lens.lens_masks(f, "ics", pd.Timestamp("2026-09-30"))
    assert int(masks["ics"].sum()) == 25 and int(masks["ics_dm"].sum()) == 25
    assert "ics_ref" not in masks, "a channel with no accounts is left out, not shown as zero"
    assert any("DM list matched 25 of 25" in s for s in said)


def test_unknown_lens_is_refused(frame):
    with pytest.raises(SystemExit):
        lens.lens_masks(frame, "mrpc", pd.Timestamp("2026-09-30"))
