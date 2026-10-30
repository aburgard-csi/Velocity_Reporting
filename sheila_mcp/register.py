"""Put Sheila in this PC's Claude Desktop. Run by scripts/launchers/runtime.cmd every time Sheila opens, so no
CSM sets anything up (James Gilmore, 2026-10-30: "it should be built once, no csm has to do it").

    python sheila_mcp/register.py --root "M:\\CSM_Reporting\\"

Self-contained on purpose (no package imports): it runs by path, before anything else is loaded.

It writes two things, and only when they would change:
  %LOCALAPPDATA%\\RPE\\sheila_start.py   what Claude runs: refresh Sheila's code from the share (runtime.cmd,
                                       as her page does), then serve from the local copy. Kept outside
                                       RPE\\Code so a refresh never rewrites the file that is running.
  claude_desktop_config.json           a "sheila" entry under mcpServers; every other entry is kept, and
                                       the file as it was is saved beside it as .bak first.
A PC without Claude Desktop is left alone. Claude picks the entry up the next time it starts.
"""
import argparse
import json
import os
import sys
from pathlib import Path

NAME = "sheila"

START = r'''"""Started by Claude Desktop: Sheila's connector. Written by sheila_mcp/register.py; do not edit."""
import os, runpy, subprocess, sys
root = os.environ.get("ROOT") or ""
rt = os.path.join(os.environ["LOCALAPPDATA"], "RPE")
cmd = os.path.join(root, "Tools", "RPE", "scripts", "launchers", "runtime.cmd")
if root and os.path.isfile(cmd):
    # The same refresh Sheila's page does when it opens; its messages go to Claude's log, never to stdout,
    # which is the protocol's. A share that does not answer leaves the local copy as it is.
    try:
        subprocess.run(["cmd", "/d", "/c", "call", cmd], stdout=sys.stderr, stderr=sys.stderr,
                       env=dict(os.environ, ROOT=root), timeout=600)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"sheila: could not refresh from the share ({e}); using this PC's copy", file=sys.stderr)
sys.path.insert(0, os.path.join(rt, "Code"))
os.chdir(os.path.join(rt, "Code"))
runpy.run_module("sheila_mcp", run_name="__main__", alter_sys=True)
'''


def claude_configs():
    """Every Claude Desktop config folder on this PC: the installer's, and the Microsoft Store package's."""
    out = []
    appdata = os.environ.get("APPDATA")
    if appdata and Path(appdata, "Claude").is_dir():
        out.append(Path(appdata, "Claude", "claude_desktop_config.json"))
    pk = Path(os.environ.get("LOCALAPPDATA") or "", "Packages")
    if pk.is_dir():
        for d in pk.glob("Claude_*"):
            c = d / "LocalCache" / "Roaming" / "Claude"
            if c.is_dir():
                out.append(c / "claude_desktop_config.json")
    return out


def entry(root, local):
    data_root = root.rstrip("\\/")
    return {"command": str(Path(local, "Python", "python.exe")),
            "args": ["-X", "utf8", str(Path(local, "sheila_start.py"))],
            "env": {"ROOT": data_root + "\\", "RPE_DATA_ROOT": data_root,
                    "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}}


def _write_if_changed(path, text):
    try:
        if Path(path).read_text(encoding="utf-8") == text:
            return False
    except OSError:
        pass
    tmp = Path(str(path) + ".part")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return True


def register(root, local=None, configs=None):
    """{config path: "added" | "updated" | "unchanged" | "skipped: why"}."""
    local = Path(local or Path(os.environ["LOCALAPPDATA"], "RPE"))
    local.mkdir(parents=True, exist_ok=True)
    _write_if_changed(local / "sheila_start.py", START)
    want = entry(root, local)
    out = {}
    for cfg in (claude_configs() if configs is None else configs):
        cfg = Path(cfg)
        try:
            text = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
            doc = json.loads(text) if text.strip() else {}
        except ValueError:
            out[str(cfg)] = "skipped: not valid JSON, left as it is"
            continue
        except OSError as e:
            out[str(cfg)] = f"skipped: {e}"
            continue
        servers = doc.setdefault("mcpServers", {})
        if servers.get(NAME) == want:
            out[str(cfg)] = "unchanged"
            continue
        state = "updated" if NAME in servers else "added"
        servers[NAME] = want
        if text:
            Path(str(cfg) + ".bak").write_text(text, encoding="utf-8")
        _write_if_changed(cfg, json.dumps(doc, indent=2) + "\n")
        out[str(cfg)] = state
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add Sheila to this PC's Claude Desktop.")
    ap.add_argument("--root", default=os.environ.get("ROOT") or "", help="the CSM_Reporting folder")
    a = ap.parse_args(argv)
    if not a.root:
        print("sheila register: no --root given", file=sys.stderr)
        return 2
    for cfg, state in register(a.root).items():
        print(f"sheila register: {state}: {cfg}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
