"""Sheila cleans up after herself: the Transaction Intelligence cache stays inside a size and an age limit.

Aaron, 2026-11-03: "my harddrive is nearly full. make sure sheila cleans up after herself." A cache that only ever grew
held 5.6 GB across three clients. Everything in it is rebuilt from the share, so a client the cache lets go costs that
client's next build a re-read and nothing else.
"""
import os
import sys
import time

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build"), os.path.join(REPO, "scripts"), os.path.join(REPO, "build", "ars_pipeline")]

import local_cache as LC   # noqa: E402

DAY = 86400


def fill(root, cid, mb, used_days_ago, now):
    for sub in LC.SUBDIRS:
        d = root / sub / cid
        d.mkdir(parents=True)
        f = d / "file.bin"
        f.write_bytes(b"x" * int(mb * 1e6 / len(LC.SUBDIRS)))
        os.utime(f, (now - used_days_ago * DAY, now - used_days_ago * DAY))
    LC.touch(cid, root=root, now=now - used_days_ago * DAY)


@pytest.fixture
def cache(tmp_path):
    return tmp_path / "ti_cache"


def test_the_least_recently_used_clients_go_until_the_cache_is_under_its_size(cache):
    now = time.time()
    for cid, mb, age in (("1075", 2400, 5), ("1615", 900, 3), ("1776", 2100, 1)):
        fill(cache, cid, mb / 1000, age, now)                                   # scaled down: 2.4, 0.9, 2.1 "GB" as MB
    r = LC.trim_ti_cache(max_gb=0.0025, max_age_days=999, root=cache, now=now)
    assert r["removed"] == ["1075", "1615"]                                     # the oldest used first, until it fits
    assert os.path.isdir(cache / "txn_raw" / "1776") and not os.path.isdir(cache / "txn_raw" / "1075")
    assert r["freed"] > 0 and r["left"] <= 0.0025 * 1e9


def test_a_client_not_used_for_weeks_goes_whatever_the_size(cache):
    now = time.time()
    fill(cache, "1075", 1, 30, now)
    fill(cache, "1776", 1, 2, now)
    r = LC.trim_ti_cache(max_gb=50, max_age_days=21, root=cache, now=now)
    assert r["removed"] == ["1075"] and not (cache / "used" / "1075").exists()


def test_the_client_being_built_is_never_evicted_even_when_it_alone_is_over_the_limit(cache):
    now = time.time()
    fill(cache, "1776", 5, 90, now)
    fill(cache, "1615", 1, 1, now)
    r = LC.trim_ti_cache(keep="1776", max_gb=0.001, max_age_days=21, root=cache, now=now)
    assert "1776" not in r["removed"] and os.path.isdir(cache / "txn_raw" / "1776")


def test_an_empty_client_folder_is_cleared_and_the_deposits_cache_counts(cache):
    now = time.time()
    (cache / "txn_raw" / "1539").mkdir(parents=True)                           # a client with a folder and no files
    d = cache / "deposits_raw" / "1776"
    d.mkdir(parents=True)
    (d / "x.csv").write_bytes(b"x" * 3000)
    said = []
    r = LC.trim_ti_cache(max_gb=50, max_age_days=999, root=cache, now=now, log=said.append)
    assert r["removed"] == ["1539"] and any("empty" in m for m in said)
    assert LC.clients(cache)["1776"]["bytes"] == 3000                           # counted toward the limit


def test_a_missing_cache_is_not_an_error(tmp_path):
    assert LC.trim_ti_cache(root=tmp_path / "nothing") == {"removed": [], "freed": 0, "left": 0}


def test_the_limits_can_be_set_from_the_environment(cache, monkeypatch):
    now = time.time()
    fill(cache, "1075", 1, 10, now)
    monkeypatch.setenv("TI_CACHE_MAX_AGE_DAYS", "5")
    assert LC.trim_ti_cache(root=cache, now=now)["removed"] == ["1075"]


def test_staging_a_client_trims_the_cache_first_and_keeps_that_client(monkeypatch, tmp_path):
    pytest.importorskip("pandas")
    from ti import txn_stage
    monkeypatch.setenv("TI_CACHE_DIR", str(tmp_path / "c"))
    now = time.time()
    fill(tmp_path / "c", "1075", 1, 40, now)                                   # stale: goes
    monkeypatch.setattr(txn_stage, "_sources", lambda cid: [])
    txn_stage.stage("1776", log=lambda m: None)
    assert not os.path.isdir(tmp_path / "c" / "txn_raw" / "1075")
    assert os.path.isdir(tmp_path / "c" / "txn_raw" / "1776") and (tmp_path / "c" / "used" / "1776").is_file()


def test_sheila_tidies_at_startup_and_by_hand():
    src = open(os.path.join(REPO, "scripts", "ars_launcher_web.py"), encoding="utf-8").read()
    assert "def tidy(" in src and '"--tidy"' in src and "threading.Thread(target=tidy" in src
    from unittest import mock
    import ars_launcher_web as W
    with mock.patch.object(W.R, "sweep_temp", return_value=(0, 0)), mock.patch.object(LC, "trim_ti_cache", return_value={"removed": ["1"], "freed": 2_000_000_000, "left": 0}):
        said = []
        assert W.tidy(said.append) == 2_000_000_000
        assert any("cleaned up 2.0 GB" in m for m in said)
