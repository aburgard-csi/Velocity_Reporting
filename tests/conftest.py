"""Shared pytest fixtures and import paths for the RPE test suite."""
import os, subprocess, sys, json
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(REPO, "build")
ARS = os.path.join(BUILD, "ars_pipeline")
SCRIPTS = os.path.join(REPO, "scripts")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
ODD_CSV = os.path.join(FIXTURES, "synthetic_odd.csv")

for p in (BUILD, ARS, SCRIPTS):  # ARS_PIPE included
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def odd_csv():
    """Path to the synthetic ODD extract, generated on first use.

    The file is NOT committed: `.gitignore` excludes `*.csv` under "client data
    — nothing client-identifiable belongs in this repo", and that blanket rule
    is worth more than the convenience of shipping a 1.5 MB fixture. Punching an
    exception in it would be the first step to punching a second.

    It is regenerated instead. `make_odd.py` is seeded, so every machine and
    every run produces a byte-identical file.
    """
    if not os.path.exists(ODD_CSV):
        os.makedirs(FIXTURES, exist_ok=True)
        r = subprocess.run([sys.executable, os.path.join(FIXTURES, "make_odd.py"), ODD_CSV],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"could not generate the ODD fixture:\n{r.stderr[-2000:]}"
    return ODD_CSV


@pytest.fixture(scope="session")
def odd_rows_raw(odd_csv):
    """(header list, list of row lists) straight off the fixture."""
    import csv
    with open(odd_csv, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    hdr = [c.strip() for c in rows[4]]
    return hdr, rows[5:]


@pytest.fixture(scope="session")
def metrics(odd_csv, tmp_path_factory):
    """metrics.json produced by running the real metrics_gen on the fixture.

    metrics_gen reads sys.argv at module scope, so it cannot be imported — it is
    run as a subprocess, which is also how the pipeline invokes it.
    """
    out = tmp_path_factory.mktemp("metrics") / "metrics.json"
    r = subprocess.run([sys.executable, os.path.join(ARS, "metrics_gen.py"),
                        odd_csv, str(out)],
                       capture_output=True, text=True, cwd=ARS)
    assert r.returncode == 0, f"metrics_gen failed:\n{r.stderr[-3000:]}"
    return json.loads(out.read_text())
