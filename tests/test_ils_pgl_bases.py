"""ILS pre-go-live bases (build/ils_pipeline/pre_go_live/bases.py).

v5's two open-status sanity-guard tests (v5 tests/test_pgl_setup.py), on the RPE input folder.
"""
from ils_pipeline import pgl_input
from ils_pipeline.pre_go_live import bases as bases_mod
from ils_pipeline.pre_go_live import loader
from ils_pipeline.pre_go_live.codes import Codes
from test_ils_pgl_loader import root, write_extract  # noqa: F401 (fixture)


def test_open_reading_sanity_guard(root):
    """If the confirmed open codes capture almost none of the recently opened
    accounts, the status legend is probably not what we think -- warn loudly."""
    rows = []
    for i in range(20):   # 20 accounts opened recently, all coded C
        rows.append(f"9{i:02d},PERSONAL,NULL,003,600,700,C,Y,6/1/2026,8/6/2026,Same,1,27,2,NULL")
    rows.append("998,PERSONAL,NULL,003,600,700,O,Y,1/1/2015,8/6/2026,Same,1,27,2,NULL")
    p = write_extract(root, "1737_TxNat_PreGL_20260810.csv", rows)
    df, _ = loader.load(p)
    warns = []
    bases_mod.build(df, Codes(open_status="O", od_eligible="003", rege_opt_in="Y"), warns.append)
    assert any("open-status sanity check FAILED" in w for w in warns)


def test_open_reading_guard_quiet_when_plausible(root):
    found = pgl_input.find_extract("1737")
    df, _ = loader.load(found.path)
    warns = []
    bases_mod.build(df, Codes(open_status="O", od_eligible=["003", "005"], rege_opt_in="Y"),
                    warns.append)
    assert not any("sanity check FAILED" in w for w in warns)


def test_bases_count_the_known_extract(root):
    """v5's coded-run base counts (test_run_with_codes_builds_bases_and_persists), built directly."""
    df, _ = loader.load(pgl_input.find_extract("1737").path)
    df = bases_mod.drop_deleted(df, lambda _m: None)
    b = bases_mod.build(df, Codes(open_status="O", od_eligible=["003", "005"], rege_opt_in="Y"),
                        lambda _m: None)
    bases = dict((r[0], r[1]) for r in b.counts())
    assert bases["all"] == 5                                  # deleted row excluded
    assert bases["personal"] == 4 and bases["business"] == 1
    assert bases["open"] == 5
    assert bases["eligible"] == 3
    assert bases["opted_in"] == 2
