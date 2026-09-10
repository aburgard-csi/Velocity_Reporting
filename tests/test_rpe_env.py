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


def test_there_is_no_repo_fallback(tmp_path, monkeypatch):
    """One fact, one store (Aaron, 2026-08-29).

    build/<program>_pipeline/data/ held copies that drifted — the Inputs/ store
    carried 2026-08-29 pulls while the repo still had 2026-08-10, and a build
    reading the repo shipped month-old figures that validated perfectly because
    they were internally consistent.
    """
    store = tmp_path / "VIP Data"; store.mkdir()
    monkeypatch.setattr(rpe_env, "vip_data", lambda: store)
    monkeypatch.setattr(rpe_env, "vip_manifest", lambda: None)
    repo_copy = tmp_path / "build" / "ics_pipeline" / "data"
    repo_copy.mkdir(parents=True)
    (repo_copy / "1705_ics.json").write_text("{}")
    monkeypatch.setattr(rpe_env, "REPO_ROOT", tmp_path)
    with pytest.raises(SystemExit):
        rpe_env.resolve_client_json("1705", "ics")


def test_absent_vip_store_says_how_to_fix_it(monkeypatch):
    monkeypatch.setattr(rpe_env, "vip_data", lambda: None)
    with pytest.raises(SystemExit) as e:
        rpe_env.resolve_client_json("1705", "ics")
    msg = str(e.value)
    assert "RPE_DATA_ROOT" in msg and "Inputs/VIP Data" in msg


def test_vip_store_resolves_by_glob(tmp_path, monkeypatch):
    store = tmp_path / "VIP Data"
    d = store / "ICS" / "1705-CoastLife Credit Union"; d.mkdir(parents=True)
    (d / "1705_ics.json").write_text("{}")
    monkeypatch.setattr(rpe_env, "vip_data", lambda: store)
    monkeypatch.setattr(rpe_env, "vip_manifest", lambda: None)
    assert rpe_env.resolve_client_json("1705", "ics") == d / "1705_ics.json"


def test_manifest_is_preferred_over_the_glob(tmp_path, monkeypatch):
    store = tmp_path / "VIP Data"
    d = store / "ICS" / "1705-CoastLife Credit Union"; d.mkdir(parents=True)
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
    assert "README" in msg, "the fix should point at the refresh procedure"
    assert "VIP" in msg, "the fix is a refresh from VIP, and the message should say so"


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
