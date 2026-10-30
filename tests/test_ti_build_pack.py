"""ti_build's deck-only redraw (James Gilmore, 2026-10-29: "we obviously need to find a better, more efficient way
to review large txn files"): `--from-pack` reuses the last full build's figures, and refuses a pack for another
client or period, or one whose ODD extract or transaction files changed. And the merchant cleaning, run once per
distinct description, gives every row what the row-by-row version gave it."""
import json
import os
import sys

import pandas as pd
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "build", "ars_pipeline"), os.path.join(HERE, "..", "build")]
import ti_build  # noqa: E402
from ti.transaction_intelligence import merchant as M  # noqa: E402


def _inputs(root, cid="9999"):
    (root / "Inputs" / "ODDD").mkdir(parents=True)
    (root / "Inputs" / "ODDD" / f"{cid}_ODDD.zip").write_bytes(b"odd")
    (root / "Inputs" / "Txn Files" / cid).mkdir(parents=True)
    t = root / "Inputs" / "Txn Files" / cid / f"{cid}_2026.09_txn.zip"
    t.write_bytes(b"txn")
    return t


def test_a_pack_is_reused_only_for_its_own_client_period_and_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    txn = _inputs(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(SystemExit, match="no ti_pack.json"):
        ti_build.pack_for_reuse(out, "9999", "2026.10")
    pack = {"client_id": "9999", "period": "2026.10", "inputs": ti_build.input_fingerprint("9999")}
    (out / "ti_pack.json").write_text(json.dumps(pack), encoding="utf-8")
    assert ti_build.pack_for_reuse(out, "9999", "2026.10")["client_id"] == "9999"
    with pytest.raises(SystemExit, match="not 9999 2026.11"):
        ti_build.pack_for_reuse(out, "9999", "2026.11")
    txn.write_bytes(b"a corrected month")
    with pytest.raises(SystemExit, match="have changed"):
        ti_build.pack_for_reuse(out, "9999", "2026.10")


def test_a_pack_from_before_the_check_is_never_reused(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    _inputs(tmp_path)
    (tmp_path / "ti_pack.json").write_text(json.dumps({"client_id": "9999", "period": "2026.10"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="predates the check"):
        ti_build.pack_for_reuse(tmp_path, "9999", "2026.10")


def test_merchant_cleaning_per_distinct_description_matches_row_by_row():
    desc = pd.Series(["XX9704 PURCHASE-RECUR 08/01 06:51 PAYPAL *PYPL PAY SAN JOSE CA 69424885 08010606",
                      None, "TYPE: MTG PYMTS ID: 16-1146859", "SESLOC FCU ATASCADERO CA", float("nan"),
                      "  star one cu  ", "XX9704 PURCHASE-RECUR 08/01 06:51 PAYPAL *PYPL PAY SAN JOSE CA 69424885 08010606",
                      12345678, ""], index=[5, 3, 9, 1, 0, 2, 8, 7, 4], name="merchant_name")
    assert M.merchant_text(desc).equals(M._text_rows(desc))
    assert M.merchant_core(desc).equals(M._core_rows(desc))
    assert list(M.merchant_text(desc).index) == list(desc.index) and M.merchant_core(desc).name == "merchant_name"
    assert M.merchant_text(desc.iloc[:0]).empty


def test_a_month_on_hand_twice_is_staged_once_from_the_copy_already_staged(tmp_path):
    from ti import txn_stage as S
    name = "1798_32175_[2026.09.01][12.31.11]_velocity_monthly_transactions.csv"
    staged = tmp_path / name
    staged.write_bytes(b"x" * 10)
    os.utime(staged, (1_700_000_000, 1_700_000_000))
    a = (name, 10, 1_700_000_000.0, "the copy staged")
    b = (name, 10, 1_800_000_000.0, "a newer copy")
    other = ("1798_32175_[2026.10.01][12.31.15]_velocity_monthly_transactions.csv", 5, 1.0, "only copy")
    chosen, dupes = S.one_per_name([b, a, other], tmp_path)
    assert [c[3] for c in chosen] == ["the copy staged", "only copy"] and dupes == {name: 2}
    staged.unlink()
    chosen, _ = S.one_per_name([a, b], tmp_path)
    assert [c[3] for c in chosen] == ["a newer copy"]
