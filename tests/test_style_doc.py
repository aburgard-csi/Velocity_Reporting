"""The style guide names files that exist.

STYLE.md carried `style_tables.py` (retired 2026-07-24), `kickoff_lib`, and
`build_gen`/`build_gen_b` for six weeks after they left the repo, and the ICS
shadow it said "matched" the standard was two points lighter. A guide that names
a file nobody can open is not the single source of truth it claims to be. This
checks the cheap half: every repo path the docs cite resolves.
"""
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = ["templates/STYLE.md", "templates/TEMPLATES.md", "build/README.md"]
PATH = re.compile(r"`((?:build|validation|tests|scripts|templates|fonts)/[\w./ -]+?\.(?:py|md|pptx|json|png|jpg|ttf))`")


@pytest.mark.parametrize("doc", DOCS)
def test_every_cited_repo_path_exists(doc):
    text = open(os.path.join(REPO, doc), encoding="utf-8").read()
    cited = sorted(set(PATH.findall(text)))
    if doc.startswith("templates/"):
        assert cited, f"{doc} cites no repo paths — the pattern or the doc changed"
    missing = [p for p in cited if not os.path.exists(os.path.join(REPO, p))]
    assert not missing, f"{doc} names files that do not exist: {missing}"


def test_retired_modules_are_not_presented_as_current():
    text = open(os.path.join(REPO, "templates/STYLE.md"), encoding="utf-8").read()
    for retired in ("style_tables.py", "kickoff_lib", "build_gen_b"):
        assert retired not in text, f"STYLE.md still cites retired module {retired}"
