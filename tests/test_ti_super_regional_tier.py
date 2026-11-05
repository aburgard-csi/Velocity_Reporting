"""The shared competitor dictionary carries a Super-Regional Bank tier (James, 2026-09-30, on 1441:
"19 national banks seems wrong"). It sits between the national tier and a client's own
RegionalCompetitors / LocalCompetitors lists, which still take precedence by name."""
import json

from ti import dictionaries
from ti.transaction_intelligence import competition as C


def test_the_tier_exists_is_a_competitor_and_has_banks():
    c = json.loads((dictionaries.folder() / "competitors.json").read_text(encoding="utf-8"))
    assert c["tiers"]["Super-Regional Bank"]["kind"] == "competitor"
    names = [n for n, i in c["institutions"].items() if i.get("tier") == "Super-Regional Bank"]
    assert len(names) == 31 and "Comerica" in names and "First Citizens" in names
    for n in names:
        assert c["institutions"][n]["patterns"], n


def test_the_engine_loads_the_tier_and_a_description_matches_it():
    spec = C.load_config(dictionaries.folder(), {"LocalCompetitors": {}, "RegionalCompetitors": {}})
    assert spec["institutions"]["Comerica"]["tier"] == "Super-Regional Bank"
    assert "FROST BANK" in spec["institutions"]["Frost Bank"]["patterns"]


def test_no_super_regional_pattern_is_claimed_by_another_institution():
    c = json.loads((dictionaries.folder() / "competitors.json").read_text(encoding="utf-8"))
    owner = {}
    for name, inst in c["institutions"].items():
        for p in inst.get("patterns", []):
            assert p not in owner, f"{p!r} in both {owner.get(p)} and {name}"
            owner[p] = name
