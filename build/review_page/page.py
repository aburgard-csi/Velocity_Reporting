#!/usr/bin/env python3
"""page.py — the one HTML page, assembled from `static/`: the stylesheet and script inline, the view
model embedded as JSON, and the per-run token in a <meta>. Fonts are served by the server from the
repo's bundled `fonts/` (Montserrat, Carlito), so the page needs nothing from the network.

Import-safe.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
FONTS = HERE.parent.parent / "fonts"

# the only font files the server will hand out: name in the URL -> file on disk
FONT_FILES = {
    "Montserrat-VariableFont_wght.ttf": FONTS / "Montserrat" / "Montserrat-VariableFont_wght.ttf",
    "Carlito-Regular.ttf": FONTS / "Carlito" / "Carlito-Regular.ttf",
    "Carlito-Bold.ttf": FONTS / "Carlito" / "Carlito-Bold.ttf",
}

_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="token" content="__TOKEN__">
<meta name="color-scheme" content="light dark">
<title>Live review</title>
<style>
__CSS__
</style>
</head>
<body>
<header class="top" id="top"></header>
<div class="shell">
  <aside class="rail" id="rail"></aside>
  <main id="stage" tabindex="-1"></main>
</div>
<div class="foot" id="foot"></div>
<div class="scrim" id="scrim"></div>
<aside class="panel" id="panel" aria-hidden="true"></aside>
<div class="tip" id="tip" role="tooltip"></div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script type="application/json" id="model">__MODEL__</script>
<script>
__JS__
</script>
</body>
</html>
"""


def model_json(model):
    """JSON safe to embed in a <script>: no closing tag and no comment opener can end it early."""
    return (json.dumps(model, separators=(",", ":"), default=str)
            .replace("</", "<\\/").replace("<!--", "<\\!--").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def render_page(model, token):
    css = (STATIC / "live.css").read_text(encoding="utf-8")
    js = (STATIC / "live.js").read_text(encoding="utf-8")
    # placeholders are swapped on the shell first and the inserted text last, so a figure or a
    # client name containing "__JS__" can never be re-expanded
    out = (_SHELL.replace("__TOKEN__", token)
           .replace("__CSS__", "\x00CSS\x00").replace("__MODEL__", "\x00MODEL\x00").replace("__JS__", "\x00JS\x00"))
    return out.replace("\x00CSS\x00", css).replace("\x00MODEL\x00", model_json(model)).replace("\x00JS\x00", js)
