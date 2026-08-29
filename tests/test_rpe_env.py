"""rpe_env — client data resolution.

ICS and MRPC read a per-client JSON that is REAL CLIENT DATA, correctly
gitignored. It therefore does not travel with the repo, so a fresh checkout on
the CSI machine has the code and none of the ICS/MRPC inputs — which makes PRD
success criterion 1 ("the same client built on both machines produces identical
decks") unreachable for two of the three programs. The resolver gives those
files a portable home while keeping the repo location working mid-migration.
"""
import os
import pytest
import rpe_env

REPO = rpe_env.REPO_ROOT


def test_a_literal_path_is_used_as_is(tmp_path):
    f = tmp_path / "anything.json"
    f.write_text("{}")
    assert rpe_env.resolve_client_json(str(f), "ics") == f


def test_manifest_loads_if_the_vip_store_is_present():
    rows = rpe_env.vip_manifest()
    if rows is None:
        pytest.skip("Inputs/VIP Data not mounted on this machine")
    assert rows and {"program", "client_id", "file"} <= set(rows[0])


def test_every_manifest_row_resolves():
    rows = rpe_env.vip_manifest()
    if rows is None:
        pytest.skip("Inputs/VIP Data not mounted on this machine")
    for r in rows:
        p = rpe_env.resolve_client_json(r["client_id"], r["program"].lower())
        assert p.exists(), f"{r['program']} {r['client_id']} did not resolve"


@pytest.mark.parametrize("arg,expected", [
    ("1705", "1705"), ("1705_ics.json", "1705"),
    ("1705-CoastLife Credit Union", "1705"), ("nonsense", ""),
])
def test_client_id_is_read_from_any_form(arg, expected):
    assert rpe_env._client_id_of(arg) == expected


def test_per_client_folder_beats_the_loose_stub(tmp_path, monkeypatch):
    """The loose data/<id>_ics.json stubs are SUPERSEDED by the per-client
    folders (VIP Data/README.md) and are an older pull — 1705's stub is the
    2026-07-13 capture against the folder's 2026-07-15. Searching them first
    silently returned the stale one."""
    monkeypatch.setattr(rpe_env, "vip_data", lambda: None)
    data = tmp_path / "build" / "ics_pipeline" / "data"
    (data / "1705-CoastLife Credit Union").mkdir(parents=True)
    (data / "1705_ics.json").write_text('{"which": "stub"}')
    (data / "1705-CoastLife Credit Union" / "1705_ics.json").write_text('{"which": "folder"}')
    monkeypatch.setattr(rpe_env, "REPO_ROOT", tmp_path)
    got = rpe_env.resolve_client_json("1705", "ics")
    assert got.parent.name == "1705-CoastLife Credit Union", "the stale stub won"


def test_vip_store_beats_the_repo(tmp_path, monkeypatch):
    store = tmp_path / "VIP Data"
    (store / "ICS" / "1705-CoastLife Credit Union").mkdir(parents=True)
    (store / "ICS" / "1705-CoastLife Credit Union" / "1705_ics.json").write_text("{}")
    monkeypatch.setattr(rpe_env, "vip_data", lambda: store)
    monkeypatch.setattr(rpe_env, "vip_manifest", lambda: None)   # exercise the glob path
    got = rpe_env.resolve_client_json("1705", "ics")
    assert str(got).startswith(str(store))


def test_manifest_is_preferred_over_the_glob(tmp_path, monkeypatch):
    store = tmp_path / "VIP Data"
    d = store / "ICS" / "1705-CoastLife Credit Union"
    d.mkdir(parents=True)
    (d / "1705_ics.json").write_text("{}")
    monkeypatch.setattr(rpe_env, "vip_data", lambda: store)
    monkeypatch.setattr(rpe_env, "vip_manifest", lambda: [
        {"program": "ICS", "client_id": "1705",
         "file": "ICS/1705-CoastLife Credit Union/1705_ics.json"}])
    assert rpe_env.resolve_client_json("1705", "ics") == d / "1705_ics.json"


def test_missing_file_names_every_location_tried(tmp_path, monkeypatch):
    monkeypatch.setattr(rpe_env, "vip_data", lambda: tmp_path)
    monkeypatch.setattr(rpe_env, "vip_manifest", lambda: None)
    with pytest.raises(SystemExit) as e:
        rpe_env.resolve_client_json("9999", "ics")
    msg = str(e.value)
    assert "9999_ics.json" in msg
    assert "ics_pipeline" in msg, "the repo fallback must be named"
    assert "available offline" in msg, "Drive streaming is the usual cause"


def test_empty_argument_is_refused():
    with pytest.raises(SystemExit):
        rpe_env.resolve_client_json("", "ics")


def test_vip_data_never_raises():
    """Unlike inputs()/outputs() this is a migration target, so absence is normal."""
    assert rpe_env.vip_data() is None or rpe_env.vip_data().is_dir()


# --- build artifacts ------------------------------------------------------
def test_build_artifacts_is_not_the_outputs_folder():
    """Outputs/ is the delivery folder; build evidence goes elsewhere."""
    art = rpe_env.build_artifacts()
    try:
        out = rpe_env.outputs()
    except SystemExit:
        pytest.skip("RPE_DATA_ROOT/Outputs not available on this machine")
    assert art != out
    assert art.is_dir(), "build_artifacts() creates the folder on demand"


def test_build_artifacts_never_raises(monkeypatch):
    """Unlike inputs()/outputs(), a build must not die for want of a scratch dir."""
    monkeypatch.setattr(rpe_env, "data_root",
                        lambda: (_ for _ in ()).throw(SystemExit("no root")))
    assert rpe_env.build_artifacts().name == "build_artifacts"
