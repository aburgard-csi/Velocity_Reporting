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


@pytest.mark.parametrize("program,name", [("ics", "1705_ics.json"),
                                          ("mrpc", "1075_mrpc.json")])
def test_bare_filename_falls_back_to_the_repo_data_dir(program, name):
    expected = REPO / "build" / f"{program}_pipeline" / "data" / name
    if not expected.exists():
        pytest.skip(f"{name} not present in this checkout")
    assert rpe_env.resolve_client_json(name, program) == expected


@pytest.mark.parametrize("program,bare,name", [("ics", "1705", "1705_ics.json"),
                                               ("mrpc", "1075", "1075_mrpc.json")])
def test_bare_client_id_is_expanded(program, bare, name):
    expected = REPO / "build" / f"{program}_pipeline" / "data" / name
    if not expected.exists():
        pytest.skip(f"{name} not present in this checkout")
    assert rpe_env.resolve_client_json(bare, program) == expected


def test_shared_location_wins_over_the_repo(tmp_path, monkeypatch):
    """Once a client sheet has moved to Inputs/Client Data/, that copy is used."""
    shared = tmp_path / "Inputs" / rpe_env.CLIENT_DATA_DIRNAME
    shared.mkdir(parents=True)
    (shared / "1705_ics.json").write_text('{"from": "shared"}')
    monkeypatch.setattr(rpe_env, "client_data", lambda: shared)
    assert rpe_env.resolve_client_json("1705_ics.json", "ics") == shared / "1705_ics.json"


def test_missing_file_names_every_location_tried(tmp_path, monkeypatch):
    monkeypatch.setattr(rpe_env, "client_data", lambda: tmp_path)
    with pytest.raises(SystemExit) as e:
        rpe_env.resolve_client_json("9999", "ics")
    msg = str(e.value)
    assert "9999_ics.json" in msg
    assert str(tmp_path) in msg, "the shared location must be named"
    assert "ics_pipeline" in msg, "the repo fallback must be named"
    assert "available offline" in msg, "Drive streaming is the usual cause"


def test_empty_argument_is_refused():
    with pytest.raises(SystemExit):
        rpe_env.resolve_client_json("", "ics")


def test_client_data_never_raises():
    """Unlike inputs()/outputs() this is a migration target, so absence is normal."""
    assert rpe_env.client_data() is None or rpe_env.client_data().is_dir()


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
