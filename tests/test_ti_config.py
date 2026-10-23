"""The client config the ported analyses read (build/ars_pipeline/ti/config.py).

A v5-shaped file wins when it carries the client; otherwise the entry is derived from the
ARS database code tables and the derivation is stated, never silent.
"""
import json

import pytest

from ti import config


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs/ARS Settings", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("TI_CLIENT_CONFIG", raising=False)
    tables = {"status_codes": {"9999": {"O": {"active": "1"}, "C": {"active": "0"}, "D": {"active": "1"}}},
              "product_codes": {"9999": {"10": {"actively_offered_product": "1"},
                                         "11": {"actively_offered_product": "0"}}},
              "rege_codes": {"9999": {"Opt In": {"optinstatus": "1"}, "Opt Out": {"optinstatus": "2"},
                                      "Mandatory": {"optinstatus": "0"}}}}
    (tmp_path / "Inputs/ARS Settings/ars_code_tables.json").write_text(json.dumps(tables), encoding="utf-8")
    return tmp_path


def test_derived_from_the_code_tables_and_said_so(root):
    said = []
    c = config.client_config("9999", warn=said.append)
    assert c["EligibleStatusCodes"] == ["D", "O"] and c["IneligibleStatusCodes"] == ["C"]
    assert c["EligibleProductCodes"] == ["10"]
    assert c["RegEOptInCode"] == ["Opt In"] and c["RegEOptOutCode"] == ["Mandatory", "Opt Out"]
    assert "ICRate" not in c, "a rate is never invented"
    assert said and "derived" in said[0]


def test_a_v5_config_file_wins_and_is_returned_as_stored(root, tmp_path, monkeypatch):
    f = tmp_path / "v5.json"
    f.write_text(json.dumps({"_meta": {}, "9999": {"EligibleStatusCodes": ["O"], "ICRate": "0.0079",
                                                     "IneligibleProductCodes": "['20101']"}}),
                 encoding="utf-8")
    monkeypatch.setenv("TI_CLIENT_CONFIG", str(f))
    said = []
    c = config.client_config("9999", warn=said.append)
    assert c["EligibleStatusCodes"] == ["O"] and c["ICRate"] == "0.0079"
    assert c["IneligibleProductCodes"] == "['20101']" and c["_source"] == "v5.json"
    assert said == []


def test_an_excluded_client_is_refused(root, tmp_path, monkeypatch):
    f = tmp_path / "v5.json"
    f.write_text(json.dumps({"9999": {"exclude": True, "exclude_reason": "cancelled"}}), encoding="utf-8")
    monkeypatch.setenv("TI_CLIENT_CONFIG", str(f))
    with pytest.raises(SystemExit, match="cancelled"):
        config.client_config("9999")
