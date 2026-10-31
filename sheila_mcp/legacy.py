"""Take out the "sheila" entry the launcher used to write into Claude Desktop's config (2026-10-30, a few hours).

Sheila now reaches Claude only as the "CSM Sheila" extension (`sheila_mcp/extension`), installed in Claude
(James Gilmore, 2026-10-30: none of the Claude set-up belongs in Sheila's launcher). A PC that opened Sheila
on the release that registered her still has that entry, so Claude would run two Sheilas. The extension's
start script runs this first; it removes only an entry that is ours (its script is `sheila_start.py`),
saves the file as it was beside it as .bak, keeps every other entry, and does nothing when there is none.

    python sheila_mcp/legacy.py

Self-contained on purpose (no package imports): it runs by path, before the server is loaded.
"""
import json
import os
import sys
from pathlib import Path

NAME = "sheila"


def claude_configs():
    """Every Claude Desktop config on this PC: the installer's, and the Microsoft Store package's."""
    out = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        out.append(Path(appdata, "Claude", "claude_desktop_config.json"))
    pk = Path(os.environ.get("LOCALAPPDATA") or "", "Packages")
    if pk.is_dir():
        out.extend(d / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
                   for d in pk.glob("Claude_*"))
    return [c for c in out if c.is_file()]


def _ours(entry):
    args = entry.get("args") if isinstance(entry, dict) else None
    return bool(args) and str(args[-1]).lower().endswith("sheila_start.py")


def remove(configs=None, local=None):
    """{config path: "removed" | "none" | "skipped: why"}; deletes the old sheila_start.py too."""
    out = {}
    for cfg in (claude_configs() if configs is None else [Path(c) for c in configs]):
        try:
            text = cfg.read_text(encoding="utf-8")
            doc = json.loads(text) if text.strip() else {}
        except (OSError, ValueError) as e:
            out[str(cfg)] = f"skipped: {e}"
            continue
        servers = doc.get("mcpServers") if isinstance(doc, dict) else None
        if not isinstance(servers, dict) or not _ours(servers.get(NAME)):
            out[str(cfg)] = "none"
            continue
        del servers[NAME]
        try:
            Path(str(cfg) + ".bak").write_text(text, encoding="utf-8")
            tmp = Path(str(cfg) + ".part")
            tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, cfg)
            out[str(cfg)] = "removed"
        except OSError as e:
            out[str(cfg)] = f"skipped: {e}"
    start = Path(local or Path(os.environ.get("LOCALAPPDATA") or "", "RPE"), "sheila_start.py")
    try:
        start.unlink()
    except OSError:
        pass
    return out


def main():
    for cfg, state in remove().items():
        if state != "none":
            print(f"sheila legacy entry: {state}: {cfg}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
