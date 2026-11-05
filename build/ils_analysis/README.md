# ILS Program Analysis deck (`ils_review`), on RPE styling

Builds a client's ILS Program Analysis deck from the extracts in a data-pull folder (ZAccounts, ZTrend,
DebitDecline, RefundHistory, DBIC, MatrixVal). **Not an Executive Review and not part of the monthly run:**
nothing here is wired into `build_month`, Sheila, `deliveries.json` or `Outputs/`. A build writes to
`Build Artifacts\ils_analysis\out\` (deck) and a charts folder beside it (PNGs and a JSON sidecar per figure).

## Provenance

`ils_review/` is the analysis team's own package, copied from
`\\ilsdbsrvr2.csi.corp\ClientAnalysis\Python Code\ILS Program Performance Review Deck Builder\ils_review\`
(their README is kept as `UPSTREAM_README.md`). Their module names are kept so it can be diffed.

| Module | State |
| --- | --- |
| `branch_metrics`, `dbic`, `ds_analysis`, `ds_logic`, `matrix_data`, `matrix_report`, `branch_slides`, `dbic_slides`, `ds_slides`, `matrix_slides` | their logic; colours, fonts and geometry go through the new `theme.py`; the DS scoring colours are brand colours; long matrix tables stop where the content band ends (`matrix_slides._cap`) |
| `theme`, `charts`, `ds_charts`, `template`, `config`, `build`, `cli` | rewritten for the RPE canvas and styling (see below) |
| `scoring_summary` | `compute_predictor` implemented (it was a placeholder); registry kept, deck bands added |
| `ils_data` | the load kept; the data as-of date is now the data's own maximum `lastupdate`; DebitDecline and RefundHistory loaders added |
| `r_common`, `r_fees`, `r_accounts`, `r_scoring`, `client_slides` | **new**: the charts the team pastes in each cycle from R, Power BI and Excel, computed from the extracts |
| `rebrand`, `gui` | **not carried**: the deck is built from blank slides, so there is no previous client's name to rewrite; no desktop app |

## Styling decisions

* **Canvas and shell.** 13.333 x 7.5 in on blank slides of `templates/ars_template.pptx` (master, theme, layouts and
  embedded fonts), its demo slides detached before the first slide is added, so the package holds no orphan or
  duplicated part. Not a stripped ILS shell: the hand-built deck is a fixed 75 slides of which only the
  client-data slides change, and those are the ones built here, so a shell would hold nothing but the
  layouts the RPE shell already has. Not the CSI ILS template: its 20 x 11.25 canvas and Source Sans Pro are not RPE.
* **Anatomy** (`templates/STYLE.md` section 4): Montserrat 28 pt navy title, Calibri 16 pt selection subtitle, the orange
  "As of Mon D, YYYY" pill, content band 1.70 to 6.72 in, slide number at (0.45, 7.05), the client logo bottom right,
  source in the speaker notes of every slide. Cover, dividers and the closing slide come from `cover_divider`
  (the brand template's). The cover reads "ILS Program Analysis  •  <month>", not "Executive Review". There is
  no Summit slide, agenda or Contact Us slide.
* **Type.** Fonts are set by role when each shape is made; `restyle_fonts.py` is **not** run, because it floors every
  run at 16 pt and the analysis tables would overflow. Titles 18-28 pt (stepping down to fit one line), bullets start at
  16 pt and shrink only as far as the box needs (never below 11), tables are the **declared dense-table exception**
  at 10-12 pt, and the matrix tables with 30+ rows drop to 8 pt (`STYLE.md` section 9 lets a table go to 7.5). Text inside
  chart pictures is exempt, as in `STYLE.md`.
* **Ported slides** are still written in the analysis team's 20 x 11.25 design coordinates. `theme.X/Y/W/H` map
  them onto the RPE content band at placement time; font sizes are mapped by role, not scaled.
* **Charts.** Ranked branch charts stay native PowerPoint charts (Calibri, brand colours). Everything that was a
  picture is matplotlib with Carlito (`rpe_env.use_font`, which raises rather than substitute), brand palette,
  `MMM'YY` month axes through `periods.mon_yy` (the axis guard is installed), TEAL / NAVY / ORANGE per `STYLE.md`.
* **Skip and explain.** Every section is wrapped; a missing input or a raised error never stops the build, and the
  reason goes on the Data Notes slide (and into `figures_index.json`).

## What replaces the pasted pictures

See `Build Artifacts\ils_analysis\out\INVENTORY.md` for the slide-by-slide map, with the data file and columns behind each
figure and how closely it matches the hand-built Achieva deck. In short: KPI rollup, fee trending, paid vs returned,
exception-item treemaps, eligibility, Reg E tables, debit-decline segmentation and the Scoring Summary tables
reproduce the deck's figures from the extracts; the not-repaid chart, branch bubbles, alluvial, windfall predictor and
the deck's "open active" population are close but depend on definitions that are not in the extracts; the peer NSF / OD
fee slides need ILS-wide data and are labelled placeholders.

## Definitions that differ from the analysis team's README (all stated on the Data Notes slide)

* **Scoring Summary default.** README: repayment over 30 days, never-repaid counted as a default. That gives 40% in
  Achieva's first Days On Book band; the hand-built deck prints 10.1%. A scan of the threshold against the deck's
  tables lands on **40 days with never-repaid excluded** (Days On Book within 0.3 pt in every band), which is the default
  (`default_basis="deck"`). `--default-basis readme` restores the README rule.
* **Notice.** One account on one notice date (ZTrend has one row per item): Achieva's window holds 317,064 item rows and
  216,062 account-days, and the deck's bands sum to 216,034.
* **Window.** 365 days ending 60 days before the data as-of date (Achieva 2025-07-12 to 2026-07-12), not "trailing 12 months from the snapshot".
* **Days OD.** In the deck it is days since the account last had a positive balance (`noticedate` minus
  `Last_Positive_Date`; 157,932 notices, an exact count match), not days to repayment as the README says.
* **Data as-of.** The data's maximum `lastupdate` (2026-09-10), not the file stamp (2026-09-11), which goes in the notes.
* **Open active accounts.** A deposit in the last 240 days or an NSF/OD item in the last 365; calibrated on Achieva (93,670
  against the deck's 93,668).
* **Bands.** `scoring_summary.DECK_BANDS` overrides the three predictors whose bands differ in the deck (Days OD, Windfall Ratio,
  ILS Limit); `predictors("readme")` is the analysis registry.

The 40-day and 240-day values were fitted to one client (Achieva) and tested on a second (Affinity, built with no code
change). The 240-day open-active window held (personal population within 0.1% of the hand-built deck); the 40-day default
held to about 0.6 pt on mature accounts but not on accounts under 30 days old. Treat both as unconfirmed with the
analysis team, not as their rules.

## Run

```powershell
$env:RPE_DATA_ROOT = '\\PADMIS105\Velocity_company\CSM_Reporting'
cd <checkout>\build\ils_analysis
..\..\.venv\Scripts\python.exe -m ils_review.cli --from-folder "<...>\DataPull_20260911" `
    --client "Achieva Credit Union" --client-id 1544 `
    --out-dir "$env:RPE_DATA_ROOT\Build Artifacts\ils_analysis\out"
```

Run it from the checkout, never with a client's data folder (or the analysis share) as the working directory.
The deck is named `<id>-<yyyy.mm>-ILS-<Client> ILS Analysis.pptx` (`ILS` is not an RPE program tag; `promote_month` never reads it
as one), where `yyyy.mm` is the data pull's file stamp, never the clock. A `parity_reference.json` beside the charts
(Achieva's hand-built figures, kept in the work folder, never in git) switches on the sidecars' comparison with the hand-built deck.

Tests: `tests/test_ils_analysis.py` (synthetic data only).
