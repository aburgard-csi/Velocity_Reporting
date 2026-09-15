"""The ARS database export parser keeps the code tables and nothing from the settings table."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ars_code_tables as A  # noqa: E402


def _table(header, rows):
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(header)]
    fmt = lambda cells: " ".join(c.ljust(w) for c, w in zip(cells, widths))
    return "\n".join([fmt(header), " ".join("-" * w for w in widths)] + [fmt(r) for r in rows]
                     + ["", "(%d rows affected)" % len(rows), ""])


EXPORT = "\n".join([
    _table(["client_id", "name", "ftp_password", "salt"], [["1615", "Example CU", "hunter2", "abc123"]]),
    _table(["product_code_id", "client_id", "product_code", "description", "is_business", "plays_debitcard",
            "actively_offered_product", "eligible_for_debit_card", "comments"],
           [["1", "1615", "20100", "Free Checking", "0", "1", "1", "1", "hunter2 note"],
            ["2", "1615", "20111", "NULL", "NULL", "1", "NULL", "0", "NULL"]]),
    _table(["rege_code_id", "client_id", "rege_code", "description", "optinstatus"],
           [["9", "1615", "Opt Out", "Opt Out", "0"], ["10", "1204", "1", "Opted in", "1"]]),
    _table(["mail_code_id", "client_id", "mail_code", "description", "send_mail", "send_points"],
           [["13", "1015", "A", "Air Mail", "0", "0"]]),
    _table(["status_code_id", "client_id", "status", "description", "active"],
           [["5", "1226", "", "blank", "1"], ["6", "1226", "ACTIVE", "Active", "1"]]),
])


def test_parse_keeps_only_the_code_tables_and_named_columns():
    t = A.parse_export(EXPORT)
    assert sorted(t) == ["product_codes", "rege_codes", "status_codes"]
    assert t["product_codes"]["1615"]["20100"] == {"description": "Free Checking", "is_business": "0",
                                                   "eligible_for_debit_card": "1", "actively_offered_product": "1"}
    assert t["product_codes"]["1615"]["20111"]["description"] is None, "NULL reads as None"
    assert t["rege_codes"]["1204"] == {"1": {"description": "Opted in", "optinstatus": "1"}}
    assert set(t["status_codes"]["1226"]) == {"", "ACTIVE"}, "a blank status is a mapped code"
    text = json.dumps(t)
    assert "hunter2" not in text and "abc123" not in text and "Air Mail" not in text


def test_a_missing_code_table_fails_rather_than_reading_as_nothing_unmapped():
    with pytest.raises(ValueError, match="rege_codes"):
        A.parse_export(EXPORT.replace("rege_code_id", "something_else"))


def test_main_writes_the_json_with_its_source(tmp_path):
    src = tmp_path / "export.txt"
    src.write_text(EXPORT, encoding="utf-8")
    out = tmp_path / "codes.json"
    A.main([str(src), "--out", str(out)])
    doc = A.load(out)
    assert doc["_source"]["export"] == "export.txt"
    assert doc["_source"]["tables"] == ["product_codes", "rege_codes", "status_codes"]
    assert "hunter2" not in out.read_text(encoding="utf-8")
