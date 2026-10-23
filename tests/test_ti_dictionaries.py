"""The reference dictionaries the transaction analyses read (build/ars_pipeline/ti/dictionaries/).

Each file is present, parses, and carries the sections v5's loaders read; and none of them names
a client: client-specific names come from the client config, never from a shared dictionary.
"""
import json

from ti import dictionaries


def _load(name):
    return json.loads((dictionaries.folder() / name).read_text(encoding="utf-8"))


def test_every_dictionary_is_present_and_parses():
    for name in dictionaries.FILES:
        assert isinstance(_load(name), dict), name


def test_the_sections_v5_reads_are_there():
    assert {"tiers", "institutions"} <= set(_load("competitors.json"))
    assert "categories" in _load("financial_services_patterns.json")
    assert {"mcc_groups", "keyword_buckets"} <= set(_load("merchant_categories.json"))


def test_no_dictionary_carries_client_config_keys():
    client_keys = {"ClientID", "LocalCompetitors", "SelfNames", "EligibleProductCodes", "BranchMapping"}
    for name in dictionaries.FILES:
        text = (dictionaries.folder() / name).read_text(encoding="utf-8")
        assert not any(f'"{k}"' in text for k in client_keys), name
