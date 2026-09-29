"""Slide bake-off: Aaron's deck and James's v5 deck for the same client, side by side, one
row per question, with a pick per row that copies out as a table for the issue.

    python scripts/bakeoff/bakeoff_page.py <aaron.pptx> <aaron_png_dir> <james.pptx> <james_png_dir> <out_dir> [--pairs pairs.json]

Render the PNG folders first with scripts/bakeoff/render_slides.ps1. Titles are read from the
decks (first text on each slide) and paired by scripts/bakeoff/pairs.json (start-of-title,
case-insensitive), then by identical title; whatever is left is listed unpaired. Review tool
only, never part of a build: nothing here touches Inputs, Outputs or Build Artifacts.
"""
import argparse
import html
import json
import shutil
import sys
from pathlib import Path

from pptx import Presentation

HERE = Path(__file__).resolve().parent
PICKS = ("Aaron", "James", "Both", "Neither")


def slide_titles(pptx):
    """[(number, title)] with the first non-empty text on each slide as its title."""
    out = []
    for i, s in enumerate(Presentation(str(pptx)).slides, 1):
        title = ""
        for sh in s.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                title = sh.text_frame.text.strip().split("\n")[0].strip()
                break
        out.append((i, title or "(untitled)"))
    return out


def load_pairs(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))["pairs"]
    return [(a, b, topic) for a, b, topic in raw]


def _starts(title, prefix):
    return title.lower().startswith(prefix.lower())


def pair_slides(aaron, james, pairs):
    """-> (rows, left_only, right_only). rows: [(topic, a_slide, j_slide)]. Each slide is used
    at most once; explicit pairs first, identical titles second."""
    used_a, used_j, rows = set(), set(), []
    for a_pre, j_pre, topic in pairs:
        a = next((s for s in aaron if s[0] not in used_a and _starts(s[1], a_pre)), None)
        j = next((s for s in james if s[0] not in used_j and _starts(s[1], j_pre)), None)
        if a and j:
            used_a.add(a[0]); used_j.add(j[0]); rows.append((topic, a, j))
    for a in aaron:
        if a[0] in used_a:
            continue
        j = next((s for s in james if s[0] not in used_j and s[1].lower() == a[1].lower()), None)
        if j:
            used_a.add(a[0]); used_j.add(j[0]); rows.append(("Same title on both sides", a, j))
    left = [s for s in aaron if s[0] not in used_a]
    right = [s for s in james if s[0] not in used_j]
    return rows, left, right


def _png(png_dir, number):
    return png_dir / f"slide-{number:02d}.png"


def _copy_pngs(src_dir, dest_dir, slides):
    dest_dir.mkdir(parents=True, exist_ok=True)
    missing = []
    for n, _ in slides:
        p = _png(src_dir, n)
        if p.exists():
            shutil.copy2(p, dest_dir / p.name)
        else:
            missing.append(p.name)
    return missing


def _cell(side, slide, rel_dir):
    n, title = slide
    return (f'<figure><img src="{rel_dir}/slide-{n:02d}.png" alt="{html.escape(title)}" loading="lazy">'
            f'<figcaption><b>{side}</b> · slide {n} · {html.escape(title)}</figcaption></figure>')


def _row(i, topic, a, j):
    radios = "".join(
        f'<label><input type="radio" name="pick-{i}" value="{p}"> {p}</label>' for p in PICKS)
    return (f'<section class="row" data-row="{i}" data-topic="{html.escape(topic)}" '
            f'data-a="{html.escape(a[1])}" data-j="{html.escape(j[1])}">'
            f'<h2>{i}. {html.escape(topic)}</h2>'
            f'<div class="pair">{_cell("Aaron", a, "aaron")}{_cell("James", j, "james")}</div>'
            f'<div class="pick">{radios}<input type="text" class="note" placeholder="why / what to keep from the other one"></div>'
            f'</section>')


def _unpaired(side, slides, rel_dir):
    if not slides:
        return ""
    cells = "".join(_cell(side, s, rel_dir) for s in slides)
    return f'<h2>Only in {side}\'s deck ({len(slides)})</h2><div class="grid">{cells}</div>'


STYLE = """
body{font:14px/1.45 system-ui,Segoe UI,sans-serif;margin:0;padding:16px 24px;background:#f4f6f8;color:#1c2430}
h1{font-size:20px;margin:0 0 4px}.sub{color:#5b6472;margin:0 0 20px}
.row{background:#fff;border:1px solid #d9dee5;border-radius:8px;padding:12px 16px;margin:0 0 18px}
.row h2,h2{font-size:15px;margin:0 0 10px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px;margin-bottom:18px}
figure{margin:0}img{width:100%;height:auto;border:1px solid #c9d0d8;background:#fff}
figcaption{font-size:12px;color:#5b6472;margin-top:4px}
.pick{margin-top:10px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.pick label{cursor:pointer}.note{flex:1;min-width:240px;padding:5px 8px;border:1px solid #c9d0d8;border-radius:4px}
button{padding:7px 12px;border:1px solid #1c3f6e;background:#1c3f6e;color:#fff;border-radius:5px;cursor:pointer}
textarea{width:100%;height:220px;font:12px/1.4 ui-monospace,Consolas,monospace;margin-top:8px}
"""

SCRIPT = """
const KEY='bakeoff:'+location.pathname;
function load(){try{const s=JSON.parse(localStorage.getItem(KEY)||'{}');
 document.querySelectorAll('.row').forEach(r=>{const d=s[r.dataset.row];if(!d)return;
  const i=r.querySelector(`input[value="${d.pick}"]`);if(i)i.checked=true;r.querySelector('.note').value=d.note||'';});}catch(e){}}
function save(){const s={};document.querySelectorAll('.row').forEach(r=>{const c=r.querySelector('input:checked');
 s[r.dataset.row]={pick:c?c.value:'',note:r.querySelector('.note').value};});try{localStorage.setItem(KEY,JSON.stringify(s));}catch(e){}}
function table(){const L=['| # | Question | Aaron | James | Pick | Note |','| --- | --- | --- | --- | --- | --- |'];
 document.querySelectorAll('.row').forEach(r=>{const c=r.querySelector('input:checked');
  L.push(`| ${r.dataset.row} | ${r.dataset.topic} | ${r.dataset.a} | ${r.dataset.j} | ${c?c.value:''} | ${r.querySelector('.note').value.replace(/\\|/g,'/')} |`);});
 document.getElementById('out').value=L.join('\\n');}
document.addEventListener('change',save);document.addEventListener('input',save);load();
"""


def build_page(out_dir, client, period, rows, left, right, missing):
    parts = [f"<title>Slide bake-off {html.escape(client)} {html.escape(period)}</title><style>{STYLE}</style>",
             f"<h1>Slide bake-off: client {html.escape(client)}, {html.escape(period)}</h1>",
             "<p class='sub'>Same client, same month, same source files. Aaron's deck on the left, James's v5 deck on the right. "
             "Pick per row, add a note, then press the button and paste the table into the issue.</p>"]
    if missing:
        parts.append("<p class='sub'><b>Missing images:</b> " + html.escape(", ".join(missing)) + "</p>")
    parts += [_row(i, t, a, j) for i, (t, a, j) in enumerate(rows, 1)]
    parts.append(_unpaired("Aaron", left, "aaron"))
    parts.append(_unpaired("James", right, "james"))
    parts.append('<button onclick="table()">Build the picks table</button><textarea id="out" readonly></textarea>')
    parts.append(f"<script>{SCRIPT}</script>")
    (out_dir / "index.html").write_text("\n".join(parts), encoding="utf-8")
    return out_dir / "index.html"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("aaron_pptx"); ap.add_argument("aaron_png")
    ap.add_argument("james_pptx"); ap.add_argument("james_png")
    ap.add_argument("out_dir")
    ap.add_argument("--pairs", default=str(HERE / "pairs.json"))
    ap.add_argument("--client", default="?"); ap.add_argument("--period", default="?")
    a = ap.parse_args(argv)

    aaron, james = slide_titles(a.aaron_pptx), slide_titles(a.james_pptx)
    rows, left, right = pair_slides(aaron, james, load_pairs(a.pairs))
    out = Path(a.out_dir)
    missing = (_copy_pngs(Path(a.aaron_png), out / "aaron", aaron)
               + _copy_pngs(Path(a.james_png), out / "james", james))
    page = build_page(out, a.client, a.period, rows, left, right, missing)
    print(f"{len(rows)} paired, {len(left)} only Aaron, {len(right)} only James -> {page}")
    if missing:
        print(f"missing {len(missing)} images (render both decks first)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
