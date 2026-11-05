"""Pack the "CSM Sheila" Claude Desktop extension: `CSM Sheila.mcpb`, the one file a CSM installs in Claude.

James Gilmore, 2026-10-30: none of the Claude set-up belongs in Sheila's launcher; Sheila reaches Claude as
a Claude Desktop extension. The release runs this and puts the file in the CSM_Reporting folder:

    python sheila_mcp/pack_extension.py --out "M:\\CSM_Reporting\\CSM Sheila.mcpb"

The extension carries no Sheila code. Its start script (`extension/server/sheila.cmd`) refreshes Python and
the code from the share as Sheila's page does, then serves `python -m sheila_mcp` from the PC's copy, so a
release reaches Claude the next time Claude starts and the .mcpb changes only when that script does.

The manifest (MCPB spec 0.3) is written here: its version is VERSION's, and its tool list is read from the
`@mcp.tool` functions in `__main__.py` (name and the first line of the docstring), so it cannot drift from
the server. An .mcpb is a zip with manifest.json at its root. Standard library only.
"""
import argparse
import ast
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
EXT = HERE / "extension"


def version():
    """VERSION's first line ("2.3") as the semver the spec asks for ("2.3.0")."""
    v = (REPO / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()
    parts = (v.split(".") + ["0", "0"])[:3]
    return ".".join(str(int(p)) for p in parts)


def tools():
    """[{name, description}] for each @mcp.tool function in __main__.py, in the file's order."""
    tree = ast.parse((HERE / "__main__.py").read_text(encoding="utf-8"))
    out = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and any(
                isinstance(d, ast.Attribute) and d.attr == "tool" for d in node.decorator_list):
            doc = (ast.get_docstring(node) or "").strip().splitlines()
            out.append({"name": node.name, "description": doc[0] if doc else node.name})
    return out


def manifest():
    return {
        "manifest_version": "0.3",
        "name": "csm-sheila",
        "display_name": "CSM Sheila",
        "version": version(),
        "description": "Ask CSM Sheila for your reporting: your month, client status, deck builds, "
                       "what is in a deck, where a number comes from, and the ILS analyses.",
        "long_description": "The same Sheila as her page, reached by asking. Every tool calls the function "
                            "her page's button calls, from the files on the CSM Reporting folder, and "
                            "finished decks go to Outputs. A deck already in Outputs is replaced only after "
                            "you say yes. Sheila never sends anything.",
        "author": {"name": "Velocity CSM Reporting"},
        "server": {
            "type": "binary",
            "entry_point": "server/sheila.cmd",
            "mcp_config": {
                "command": "cmd",
                "args": ["/d", "/c", "${__dirname}\\server\\sheila.cmd"],
                "env": {"SHEILA_ROOT": "${user_config.csm_reporting_folder}"},
            },
        },
        "tools": tools(),
        "compatibility": {"platforms": ["win32"]},
        "user_config": {
            "csm_reporting_folder": {
                "type": "directory",
                "title": "CSM Reporting folder",
                "description": "The shared CSM_Reporting folder Sheila builds from.",
                "default": "M:\\CSM_Reporting",
                "required": True,
            },
        },
    }


def pack(out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest(), indent=2) + "\n")
        for f in sorted(p for p in EXT.rglob("*") if p.is_file()):
            z.write(f, f.relative_to(EXT).as_posix())
    tmp.replace(out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pack the CSM Sheila Claude Desktop extension.")
    ap.add_argument("--out", required=True, help="the .mcpb to write")
    a = ap.parse_args(argv)
    p = pack(a.out)
    print(f"packed {p} (version {version()}, {len(tools())} tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
