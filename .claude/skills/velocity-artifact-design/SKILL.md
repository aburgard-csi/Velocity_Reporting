---
name: velocity-artifact-design
description: Design an HTML Artifact or web page for CSI / Velocity in Aaron's house style - a brand guide, catalog, dashboard, report, comparison or any shared page. Use when asked to build, restyle, clean up or republish an artifact for the team, or to add a page to the Velocity Design Library. Layers the Velocity palette, type and an Apple-style page system on top of the bundled artifact-design and artifact-capabilities skills.
---

# Velocity artifact design

The bundled `artifact-design` skill owns the page contract: the `<title>`, the CDN allowlist, theming tokens, phone width,
the 16 MB limit, how to publish. `artifact-capabilities` owns anything that stores state. **Load them first and obey them.**
This skill adds one thing: what a Velocity page looks like, so every page Aaron shares reads as one product.

The look is Apple-style, in the sense that matters for a page people read: one idea per screen, large quiet type, whitespace
instead of rules, one accent colour, depth only where something lifts. It is not a copy of apple.com; it keeps the CSI palette
and faces.

## Start from the stylesheet

`assets/velocity-page.css` is the whole system: tokens (light and dark), the nav, hero, sections, cards, stat figures, notes,
tables, swatches, ramps and the footer. Inline it in the page's `<style>` (the CSP blocks every other stylesheet host except
Google Fonts), then write markup with the `v-` classes. Do not re-declare a colour or a font in a page.

| Class | Use |
| --- | --- |
| `v-nav` (`.in`, `.brand`, `a[aria-current]`) | Translucent sticky bar, 48 px. `wide` modifier for 1240 px pages |
| `v-hero` (`v-eyebrow`, `h1`, `v-lede`, `v-meta`) | Centred, one headline, one sentence, a few chips |
| `v-sec` / `v-sec alt` | A section. Alternate the grounds; never separate sections with a border |
| `v-wrap` (`v-narrow`, `v-wide`) | The content column |
| `v-cards` / `v-card` / `a.v-card` | Flat rounded tiles. A card that links ends with `<span class="more">Open it ›</span>` |
| `v-stats` / `v-stat` (`hot`) | Large figures with a label. Orange only for the one that matters |
| `v-note` (`warn`) | A tinted box. Not a ruled-off quote |
| `v-table` | Hairlines only, uppercase muted headers, first column in ink |
| `v-sw`, `v-ramp`, `v-pillars`, `v-chip`, `v-foot` | Swatches, colour ramps, principle tiles, chips, footer |

## The rules

1. **One idea per screen.** A section has an eyebrow, a headline of at most about eight words, optionally one sentence, then the
   evidence. If a section needs a paragraph to explain itself, split it.
2. **Type does the structure.** Headlines are large, tight (`letter-spacing` about -0.03em) and `text-wrap: balance`. Body is
   17-18 px. Use two weights. Never use bold for emphasis inside a heading.
3. **Whitespace is the divider.** Sections get 56-104 px of padding and alternate between `--ground` and `--surface`. No
   horizontal rules, no outlined boxes. A hairline belongs only inside a table.
4. **One accent.** Navy carries the page, orange (`#F15D22`) marks the single finding. A page with three orange things has none.
   Links use the CSI light blue, `#035B95`.
5. **Show, then say.** Lead with the figure or the picture; the sentence under it states what it means. Cut any sentence that
   repeats the heading or the number beside it.
6. **Depth only for what lifts.** A soft shadow on a card, a translucent nav. Nothing else casts one.
7. **Honour both themes.** Every colour is a token. Check the page in dark mode and at 400 px before publishing.
8. **Motion is optional and quiet.** A 200 ms lift on a link card, switched off under `prefers-reduced-motion`.
9. **Real content.** Real figures, real names of things, no lorem. State a snapshot's date on the page.

## Brand values

Take values from `build/brand.py` and `templates/STYLE.md`, never from memory or an old page. The ones that have moved:

- **CSI Orange is `#F15D22`** (PMS 179) since the September 2026 brand template. It was `#F47A29`. A page still drawing the old
  value is out of date. Warm ramp: `#F15D22`, `#F47D4E`, `#F79E7A`.
- Navy `#00274C`, `TICK` grey `#5A6670`, `ROWALT` `#EEF2F7`, `GRID` `#E4EAF1`. CSI light blue `#035B95`, gold `#F8971D`, red
  `#EB2A2E` exist in `brand.py` for pages; the decks do not use them yet.
- Display face Montserrat, body Calibri (Carlito where Calibri is missing). Both are in the stylesheet's font stacks; load
  Montserrat from Google Fonts.
- The deck drop shadow is `0 4px 7px rgba(0,0,0,.28)` on a screen at 96 px per inch. A mockup drawn at 60 px per inch scales it
  (`0 3px 5px`). That is the same shadow, not a mismatch.

## Copy

- Short, plain, in the user's words. Name a thing by what people recognise, not how it is built.
- Writing rules from `CLAUDE.md` apply to anything a client could read: no banned words, movement within +/-2% is "almost flat",
  comparisons use complete months, missing data is stated and never zeroed, and a claim that something rose or fell carries its
  figures.
- Remove provenance clutter (file paths, "was X.html", build-script names) unless the reader needs it to act.
- An artifact is private until Aaron shares it. Say so in the hand-over when someone else is meant to read it. Keep client
  figures to what the page needs.

## Several pages, one artifact

A library is one artifact with an `index.html` front door and supporting pages.

- Publish the main file with `file_path`; map the others in `files` (`{"standards.html": "<abs path>"}`). Reference them by
  relative name.
- The main page is wrapped in the document skeleton at publish time, so it starts at `<title>`. **Every supporting page is
  served as written**: give it `<!doctype html>`, charset, a viewport with `viewport-fit=cover`, a `<title>` and `body` styles.
- Put the same `v-nav` at the top of every page, with `aria-current="page"` on the active link. Add `wide` when the page uses a
  1240 px column so the bar lines up with the content.
- Update in place by passing the artifact's `url`; a different `file_path` without `url` makes a separate artifact.
- When you port an existing page, take **every** `<script>` block. The Chart Catalog has two; taking the first left every chart
  blank and raised no error.

## Verify before publishing

1. Build the pages from a script, not by hand, so a rebuild is one command.
2. Render each page: `chrome --headless=new --hide-scrollbars --user-data-dir=<fresh temp dir> --window-size=1280,3000
   --virtual-time-budget=5000 --screenshot=<png> file:///<path>`. Use a **new** profile directory each run and keep the window
   under about 3400 px tall; in practice a reused profile or a taller window sometimes produced no file and no error. Edge was flakier than Chrome.
3. Look at the picture. A page driven by script can render its chrome and nothing else.
4. Check dark mode (render a copy with `data-theme="dark"` on `<html>`) and a 400 px width.
5. Search the saved page for the old orange, `#F47A29`, and for stale dates.

## The Velocity Design Library

https://claude.ai/artifact/LBkJaCqhouPRBWhcAsXoSV holds the Brand Guide (follows `build/brand.py` and `templates/STYLE.md`), the
Chart Catalog and the James vs Aaron comparison, on this system. When `brand.py` or `STYLE.md` change, update the Brand Guide in
the same sitting. The comparison is a snapshot of 2026-09-17 and needs a re-run against current decks before anyone relies on
its statuses.
