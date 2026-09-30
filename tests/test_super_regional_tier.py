"""The shared competitor dictionary carries a Super-Regional Bank tier (James, 2026-09-30:
"19 national banks seems wrong"). A client's own RegionalCompetitors / LocalCompetitors
still take precedence by name; the tier fills the gap between national and a CSM's list."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]

CFG = REPO / "build" / "ars_pipeline" / "engine" / "config"


def test_the_tier_exists_is_a_competitor_and_has_banks():
    c = json.loads((CFG / "competitors.json").read_text(encoding="utf-8"))
    assert c["tiers"]["Super-Regional Bank"]["kind"] == "competitor"
    names = [n for n, i in c["institutions"].items() if i.get("tier") == "Super-Regional Bank"]
    assert len(names) >= 25 and "Comerica" in names and "First Citizens" in names
    for n in names:
        assert c["institutions"][n]["patterns"], n


def test_the_engine_loads_the_tier_and_a_description_matches_it():
    from engine.transaction_intelligence import competition as C
    spec = C.load_config(CFG, {"LocalCompetitors": {}, "RegionalCompetitors": {}})
    assert spec["institutions"]["Comerica"]["tier"] == "Super-Regional Bank"
    assert "FROST BANK" in spec["institutions"]["Frost Bank"]["patterns"]
