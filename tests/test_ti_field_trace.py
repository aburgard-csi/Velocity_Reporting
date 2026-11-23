"""The transaction field trace (roadmap R10): `docs/ti_field_trace.md` is generated from the code by
`scripts/ti_field_trace.py`, and these tests keep it honest.

James Gilmore: "id really like to trace each individual field in the transaction file by analysis."
A trace kept by hand goes stale the first time an analysis changes, so the trace is rebuilt from the
code here and compared with the checked-in copy: an analysis that starts reading a field, a new pack
key, a slide that draws a new key all fail this test until the trace is regenerated.
"""
import pytest

import ti_field_trace as FT

# Columns an analysis may read off the transaction frame although they are not in the loader's
# KEEP list. Each needs a reason; an entry nothing reads any more fails test_allowlist_is_used.
DERIVED_COLUMNS = {
    "merchant_key": "added to every frame by loader.read_file (merchant.merchant_key of merchant_name): "
                    "the grouping label the merchant, card and relationship sections rank by",
}

# Kept fields that no analysis is expected to read, with the reason. Empty today: every kept field
# is read somewhere.
UNREAD_OK = {}

REGENERATE = "run `python scripts/ti_field_trace.py` and commit docs/ti_field_trace.md and .json"


@pytest.fixture(scope="module")
def trace():
    return FT.build()


def _norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def test_checked_in_trace_is_current(trace):
    md, js = FT.render_md(trace), FT.render_json(trace)
    for path, fresh in ((FT.OUT_MD, md), (FT.OUT_JSON, js)):
        assert path.exists(), f"{path.name} is missing: {REGENERATE}"
        assert _norm(path.read_bytes()) == _norm(fresh.encode("utf-8")), \
            f"{path.name} is stale (the analyses, pack keys or slides changed): {REGENERATE}"


def test_markdown_is_crlf(trace):
    md = FT.render_md(trace)
    assert "\r\n" in md and "\n" not in md.replace("\r\n", "")


def test_every_kept_field_is_read(trace):
    keep = trace["loader"]["keep"]
    unread = [c for c in keep if not trace["fields"][c]["read_in"] and c not in UNREAD_OK]
    assert not unread, (f"the loader keeps {unread} but no analysis reads them: drop them from "
                        f"KEEP, or add them to UNREAD_OK with the reason")


def _txn_reads(trace):
    reads = {c for c, v in trace["fields"].items() if v["read_in"]}
    reads |= {c for c, v in trace["added_fields"].items() if v["read_in"]}
    reads |= set(trace["other_txn_columns"])
    return reads


def test_no_analysis_reads_a_column_the_loader_does_not_keep(trace):
    keep = set(trace["loader"]["keep"])
    stray = sorted(c for c in _txn_reads(trace) if c not in keep and c not in DERIVED_COLUMNS)
    where = {c: (trace["fields"].get(c) or trace["added_fields"].get(c)
                 or trace["other_txn_columns"].get(c))["read_in"] for c in stray}
    assert not stray, (f"analyses read transaction columns the loader never produces: {where}. "
                       f"Keep the column in the loader, or list it in DERIVED_COLUMNS with the reason")


def test_allowlist_is_used(trace):
    reads = _txn_reads(trace)
    unused = sorted(set(DERIVED_COLUMNS) - reads)
    assert not unused, f"DERIVED_COLUMNS lists {unused}, which no analysis reads: remove them"


# ---------------------------------------------------------------- the scanner itself
def test_sections_are_the_chapter_order(trace):
    assert trace["sections"][:3] == ["portfolio", "financial_services", "competition"]
    assert "hotspots" in trace["sections"] and "filed" in trace["sections"]


def test_prefixes_are_expanded_and_business_subsets_filtered(trace):
    from ti import txn_sections as T
    keys = trace["pack_keys"]
    for prefix, subset in (("finb_", T.FINB_KEYS), ("compb_", T.COMPB_KEYS), ("mchb_", T.MCHB_KEYS)):
        assert {k for k in keys if k.startswith(prefix)} == set(subset), prefix
    for prefix in ("fin_", "comp_", "mch_", "beh_", "ic_", "rel_"):
        assert any(k.startswith(prefix) for k in keys), prefix
    assert not any("{" in k for k in keys)


def test_a_known_path_end_to_end(trace):
    k = trace["pack_keys"]["fin_leakage_dollars"]
    assert {"amount", "merchant_name", "primary_account_num"} <= set(k["txn_fields"])
    assert "financial_services" in k["sections"]
    assert "deck.txn_leakage.their_financial_life" in k["slides"]
    # a hand-off carries its fields into the section that reads it
    curve = trace["pack_keys"]["leak_curve"]
    assert "amount" in curve["txn_fields"] and "Date Closed" in curve["odd_fields"]
    assert "shared:competitor_monthly" in curve["via"]
    # a loop over a literal table resolves its keys (portfolio's positional fields)
    assert "merchant_id" in trace["pack_keys"]["txn_field9_values"]["txn_fields"]


def test_every_slide_builder_reads_some_key(trace):
    empty = [q for q, s in trace["slides"].items() if not s["keys"]]
    assert not empty, f"slide builders with no pack key traced: {empty}"


def test_hand_offs_are_not_pack_keys(trace):
    for k, v in trace["pack_keys"].items():
        assert v["handoff"] == k.startswith("_")
    assert {"_competitor_accounts", "_competitor_monthly", "_addressable_accounts"} <= set(trace["pack_keys"])
