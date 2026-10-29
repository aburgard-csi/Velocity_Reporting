# ILS Matrix Deck Generator

Generates the house-style **ILS Matrix Validation** PowerPoint for any client from
their matrix-validation `.txt` export (query 1822). Nothing is hard-coded per client —
account types, matrix codes, limits, tier counts, trending thresholds, factor grids and
the narrative notes are all read straight from the file.

**Both export styles are supported:**
- Newer exports with `=== SECTION NAME ===` banners (e.g. German American).
- Older banner-less exports where the tables run back to back (e.g. Space Coast,
  April 2026) — sections are identified from their column signatures.

It also copes with per-client format differences automatically: boolean fields written
as `1/0` **or** `True/False` **or** `Y/N`, tier tables with uniform score bands
(e.g. $25) **or** variable-width bands, and **whatever trending model a client uses** —
the trend repositories (Deposit Regularity, Windfall Deposit, OD Repayment, …) are
discovered from the file and their factor grids are inferred from the rule text, so a
new trend type doesn't need code changes. Each 2-D trend grid gets its own slide.

> Robustness note: some exports (e.g. First American) truncate very long rule text in
> the report. The tool detects this and reconstructs the affected axis labels
> positionally from the rows that survive intact; the **factor values are always exact**
> (they sit in the last column, which isn't truncated). Such slides carry a footnote.

## Use it (desktop app)

1. Double-click **`Generate Matrix Deck.bat`**.
2. Click **Browse…** and pick the client's `Matrixvalidation_YYYYMMDD.txt`.
3. Confirm the **client name** (auto-filled from the folder; edit as needed).
4. *(Optional)* set **Save to folder** — leave blank to save next to the source file.
5. *(Optional)* tick **"Would you like to replace MRPC with CashPlease?"** to relabel
   the `MRPC` columns/labels as `CashPlease` throughout the deck (off by default).
6. *(Optional)* tick **"Include extra component slides…"** to append a slide for each
   *active* supplementary component found in the file — Communication Strategies,
   Strategic Refunds, Deposit Score (off by default).
   - Sub-option **"Show all rows across multiple slides"**: when on, component
     tables that exceed one slide are paginated across as many slides as needed;
     when off, each is capped at 15 rows with a "showing N of M" note.
7. Click **Generate Deck**. The `.pptx` is auto-named
   `<Client> - ILS Matrix Validation - <Month Year>.pptx`.
8. Click **Open Deck** to review it.

The report date in titles/footers is taken from the `YYYYMMDD` in the filename.

## Use it (command line / batch)

```
python matrix_deck.py "path\to\Matrixvalidation_20260703.txt" --client "German American Bank"
```

Options: `--out "path\to\deck.pptx"` (full path), `--out-dir "path\to\folder"`
(folder only, file auto-named), `--date "July 3, 2026"`, `--replace-mrpc`
(relabel MRPC as CashPlease).

## What comes out (8 slides)

1. Title — client, account-type matrices, snapshot date
2. Account-type settings + OD status code mapping
3. Override criteria (one column per account type)
4. Actual Monthly Deposit Count factors
5. Actual Monthly Deposit Dollars factors
6. Age of Account factors + Monthly Debit Declines note
7. Trending — trigger thresholds (per type × repository) + 1-D factor tables (OD repayment)
8. One slide per 2-D trend grid found (Deposit Regularity, Windfall Deposit, …)
9. Tiered limits & rounding summary
10. Limit Notification settings — *only if the file has them*
11. CashPlease settings (Max $, Max %, Eligible) — *only if the file has them*
12+. *(only with the extra-components toggle, and only when active)* Communication
    Strategies · Strategic Refunds · Deposit Score

Any additional factor category found in the file gets its own extra slide automatically.
Slides 10+ appear only when the corresponding data is populated/active for the client.

CLI equivalents: `--replace-mrpc`, `--extra-components`, `--all-rows`.

## Files

- `matrix_report.py` — generic parser (`=== SECTION ===`, columns from dashed lines)
- `matrix_deck.py` — the deck engine (`build_deck(...)`) + CLI
- `matrix_deck_gui.py` — the desktop app
- `Generate Matrix Deck.bat` — double-click launcher

## Requirements

Python 3 with `python-pptx` (`pip install python-pptx`). `tkinter` ships with
standard Python on Windows.
