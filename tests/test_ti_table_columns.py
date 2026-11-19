"""The column names for the cut's tables that v5 never named (build/ars_pipeline/ti/table_columns.py).

Pinned: the pack's figures are never touched; a table's own declaration wins; a business-side table
takes the names its personal-side sibling declares, and is left unwritten (and named) when they are
absent rather than given invented ones; the unlabelled migration matrix is never written.
"""
from ti import table_columns as TC
from ti.monthly_analysis import tables


def _write(metrics, tmp_path):
    warnings = []
    return tables.write(TC.with_columns(metrics), tmp_path, warnings.append), warnings


def test_the_pack_is_not_touched():
    m = {"survival": [["6 mo", 98.5]]}
    TC.with_columns(m)
    assert m == {"survival": [["6 mo", 98.5]]}


def test_a_named_table_is_written_under_its_names(tmp_path):
    written, _ = _write({"survival": [["6 mo", 98.5], ["12 mo", 97.3]]}, tmp_path)
    head = open(written["survival"], encoding="utf-8-sig").readline().strip()
    assert head == "horizon,survival_pct"


def test_a_table_that_declares_its_own_columns_keeps_them():
    m = {"survival": [["6 mo", 98.5]], "survival_columns": ["point", "pct"]}
    assert TC.with_columns(m)["survival_columns"] == ["point", "pct"]


def test_a_business_table_takes_its_personal_siblings_declared_names():
    names = ["institution", "tier", "accounts", "pct_of_accounts", "txns", "dollars",
             "dollars_per_acct", "products", "new_90d", "stopped"]
    m = {"compb_institutions": [["Charles Schwab"] + [0] * 9], "comp_institutions_columns": names}
    assert TC.with_columns(m)["compb_institutions_columns"] == names


def test_without_the_siblings_names_the_table_is_named_not_invented(tmp_path):
    written, warnings = _write({"finb_by_category": [["Insurance"] + [0] * 9]}, tmp_path)
    assert written == {}
    assert any("declare no columns" in w and "finb_by_category" in w for w in warnings)


def test_the_unlabelled_migration_matrix_is_never_written(tmp_path):
    written, _ = _write({"tier_migration_matrix": [[5321] + [0] * 8],
                         "tier_migration_windows": [["Apr26", "May26", "Jun26"]]}, tmp_path)
    assert written == {}
    assert "tier_migration_matrix" not in TC.COLUMNS and "tier_migration_matrix" not in TC.ALIASES


def test_no_key_is_both_named_and_aliased():
    assert not set(TC.COLUMNS) & set(TC.ALIASES)
