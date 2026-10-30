"""CSM Sheila in Claude: the same Sheila, reached by asking instead of clicking (James, 2026-10-30).

Every tool calls the function Sheila's page calls for the same button (`scripts/ars_launcher_web.py`), so
the page and Claude can never disagree. `python -m sheila_mcp` runs the server; `python -m
sheila_mcp.register` adds it to this PC's Claude Desktop.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "build", REPO / "scripts"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
