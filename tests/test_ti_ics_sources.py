# Ported from ARS v5 02-Scripts/tests/test_ics_sources.py at a491b5c (James Gilmore); logic unchanged.
# Left out: test_ics_section_splits_by_source (v5's ics.py, ported with the ICS chapter), and
# test_run_reads_lists_from_the_ics_tree / test_probe_reports_recipes_and_files (v5's 01-Data run
# and probe tool; here the lists are found by ti/lens.py, tested in test_ti_lens.py).
"""ICS source lists (#74): the DM and referral lists' account hashes map
onto the ODD and stamp each account's 'DM-REF Source' -- the column the
ICS section already waits for.

    python -m pytest tests/test_ics_sources.py -q

The MRDB hash recipe is NOT assumed: candidate recipes are tried against
the ODD and the one that actually matches is reported; zero matches
falls back to the DM list's account-mask + open-date join. Client files
never enter the repo -- fixtures fabricate the shapes (preamble rows,
header row mid-file, 40-hex hash column).
"""
import hashlib
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.monthly_analysis import ics_sources                       # noqa: E402


def _sha1(v) -> str:
    return hashlib.sha1(str(v).encode()).hexdigest().upper()


def _odd(n=40):
    ids = [str(1000 + i) for i in range(n)]
    return pd.DataFrame({
        "Acct ID": ids,
        "Date Opened": pd.to_datetime("2024-02-16"),
    })


def _write_dm(folder, ids, extra_hash=()):
    """The DM list shape: 9 preamble rows, then the header row, hash in
    the last column (real file: 1615 Direct Mail New Accounts PTD)."""
    rows = [[None] * 6 for _ in range(9)]
    rows.append(["# of Accounts", "Branch Number", "Name Line 1",
                 "Account Mask", "Open Date", None])
    for i, a in enumerate(list(ids) + list(extra_hash)):
        h = _sha1(a) if a not in extra_hash else a
        mask = "******" + str(a)[-4:] if a not in extra_hash else "******0000"
        rows.append([i + 1, 1, f"HOLDER {i}", mask,
                     "2024-02-16", h])
    p = folder / "1615-2026.08-ICS-Cape & Coast Bank-Direct Mail New Accounts Opened PTD.xlsx"
    pd.DataFrame(rows).to_excel(p, index=False, header=False)
    return p


def _write_ref(folder, ids):
    """The referral list shape: header on row 0, 'MRDB Account Hash'
    column (real file: 1615_ics_detailed referral_v9 1.xls)."""
    df = pd.DataFrame({
        "Referrer Name": [f"REFERRER {i}" for i in range(len(ids))],
        "Issue Date": "2023-10-21",
        "Branch": 18,
        "Account Holder": [f"HOLDER {i}" for i in range(len(ids))],
        "MRDB Account Hash": [_sha1(a) for a in ids],
        "Cert ID": range(90000000, 90000000 + len(ids)),
    })
    p = folder / "1615_ics_detailed referral_v9 1.xlsx"
    df.to_excel(p, index=False)
    return p


def test_finds_both_files_case_insensitively(tmp_path):
    _write_dm(tmp_path, ["1001"])
    _write_ref(tmp_path, ["1002"])
    found = ics_sources.find_files(tmp_path)
    assert found["DM"] is not None and "Direct Mail" in found["DM"].name
    assert found["REF"] is not None and "referral" in found["REF"].name


def test_attach_stamps_source_via_detected_hash_recipe(tmp_path):
    frame = _odd()
    _write_dm(tmp_path, ["1001", "1002"])
    _write_ref(tmp_path, ["1002", "1003", "1004"])
    warnings = []
    out = ics_sources.attach(frame, tmp_path, warnings.append)
    src = out["DM-REF Source"]
    by_id = dict(zip(out["Acct ID"], src))
    assert by_id["1001"] == "DM"
    assert by_id["1003"] == "REF"
    assert by_id["1002"] == "DM+REF"        # on both lists
    assert by_id["1010"] == ""              # untouched account stays blank
    # the join is REPORTED, never assumed: recipe + match counts
    joined = " ".join(warnings)
    assert "sha1" in joined.lower()
    assert "2 of 2" in joined and "3 of 3" in joined


def test_unmatched_list_rows_are_counted_loudly(tmp_path):
    frame = _odd()
    _write_dm(tmp_path, ["1001"], extra_hash=["F" * 40])   # one alien hash
    warnings = []
    ics_sources.attach(frame, tmp_path, warnings.append)
    assert any("1 of 2" in w for w in warnings)


def test_no_files_means_untouched_frame_and_silence(tmp_path):
    frame = _odd()
    warnings = []
    out = ics_sources.attach(frame, tmp_path, warnings.append)
    assert "DM-REF Source" not in out.columns
    assert warnings == []


def test_mask_and_date_fallback_when_no_recipe_matches(tmp_path):
    """Unknown MRDB recipe: hashes match nothing, but the DM list's
    account mask (last 4) + open date still identify accounts -- unique
    matches only, and the fallback is named in the warnings."""
    frame = _odd()
    rows = [[None] * 6 for _ in range(9)]
    rows.append(["# of Accounts", "Branch Number", "Name Line 1",
                 "Account Mask", "Open Date", None])
    rows.append([1, 1, "HOLDER", "******1005", "2024-02-16", "A" * 40])
    p = tmp_path / "1615-ICS-Direct Mail New Accounts.xlsx"
    pd.DataFrame(rows).to_excel(p, index=False, header=False)
    warnings = []
    out = ics_sources.attach(frame, tmp_path, warnings.append)
    by_id = dict(zip(out["Acct ID"], out["DM-REF Source"]))
    assert by_id["1005"] == "DM"
    assert any("mask" in w.lower() for w in warnings)


def test_duplicate_odd_ids_do_not_crash_the_join(tmp_path):
    """Real ODDs can carry the same account id on multiple rows; the
    hash index must not blow up on duplicate labels (James, 2026-08-24:
    'the ics account matching isnt working')."""
    frame = _odd()
    dup = frame.iloc[[1]].copy()
    frame = pd.concat([frame, dup], ignore_index=True)   # 1001 twice
    _write_dm(tmp_path, ["1001", "1002"])
    warnings = []
    out = ics_sources.attach(frame, tmp_path, warnings.append)
    src = dict(zip(out["Acct ID"], out["DM-REF Source"]))
    assert src["1001"] == "DM" and src["1002"] == "DM"
    assert not any("skipped" in w for w in warnings)


def test_recipe_set_covers_padded_and_digit_stripped_ids():
    ids = pd.Series(["001234", "5678"])
    names = set(ics_sources._recipes(ids))
    assert any("zero-padded" in n for n in names)
    assert any("no leading zeros" in n for n in names)
    assert any("digits only" in n for n in names)


def test_join_scans_every_account_shaped_column(tmp_path):
    """1615's run: recipes 0/1658 and mask+date 1/225 against 'Acct ID'
    -- which suggests the hashed number lives in a DIFFERENT column.
    The join must try every account-shaped column, not the first."""
    frame = _odd()
    # the hash recipe matches a second id column, not Acct ID
    frame["Card Acct Number"] = [str(900000 + i) for i in range(len(frame))]
    _write_dm(tmp_path, [str(900000 + i) for i in range(4)])
    warnings = []
    out = ics_sources.attach(frame, tmp_path, warnings.append)
    assert (out["DM-REF Source"] == "DM").sum() == 4
    joined = " ".join(warnings)
    assert "Card Acct Number" in joined       # the winning column is named


def test_mask_date_fallback_tolerates_small_date_skew(tmp_path):
    """ICS tracking dates can sit a day or two off the core's open date;
    the fallback matches within +-3 days (uniqueness still required)."""
    frame = _odd()
    rows = [[None] * 6 for _ in range(9)]
    rows.append(["# of Accounts", "Branch Number", "Name Line 1",
                 "Account Mask", "Open Date", None])
    rows.append([1, 1, "HOLDER", "******1007", "2024-02-18", "B" * 40])
    p = tmp_path / "1615-ICS-Direct Mail New Accounts.xlsx"
    pd.DataFrame(rows).to_excel(p, index=False, header=False)
    warnings = []
    out = ics_sources.attach(frame, tmp_path, warnings.append)
    by_id = dict(zip(out["Acct ID"], out["DM-REF Source"]))
    assert by_id["1007"] == "DM"              # opened 02-16, list says 02-18


def test_odd_own_hash_column_joins_directly(tmp_path):
    """James: the ODD itself carries the account hash (column C on
    1615). A 40-hex column in the ODD is the join of record -- direct
    hash-to-hash, no recipe, found by content whatever its header."""
    frame = _odd()
    frame["Acct ID"] = ["X" + str(i) for i in range(len(frame))]  # ids useless
    frame.insert(2, "Some Hash Header", [_sha1(1000 + i)
                                         for i in range(len(frame))])
    _write_dm(tmp_path, ["1001", "1002"])
    _write_ref(tmp_path, ["1002", "1003"])
    warnings = []
    out = ics_sources.attach(frame, tmp_path, warnings.append)
    src = dict(zip(out["Some Hash Header"], out["DM-REF Source"]))
    assert src[_sha1(1001)] == "DM"
    assert src[_sha1(1002)] == "DM+REF"
    assert src[_sha1(1003)] == "REF"
    joined = " ".join(warnings)
    assert "Some Hash Header" in joined and "2 of 2" in joined
