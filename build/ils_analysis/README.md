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
| `branch_metrics`, `dbic`, `ds_analysis`, `ds_logic`, `matrix_data`, `matrix_report`, `branch_slides`, `dbic_slides`, `ds_slides` | their logic; colours, fonts and geometry go through the new `theme.py`; the DS scoring colours are brand colours; the branch rankings are drawn at 60% width with a figures panel |
| `matrix_slides` | cut down to the communication-strategies slide (active strategies only, one line each in large type); the rest of the matrix section is replaced by `matrix_prep_slides`; strategic refunds are not shown |
| `matrix_prep_slides` | **new**: per account type, a limits-and-scoring slide (limit cards, one bar chart and one caption per factor) and an overrides-and-trends slide (override list, trend On / Off chips), both 12 pt and above, from the matrix validation extract only; the dense prep-deck page with every factor band is an appendix slide |
| `story_slides`, `analysis_slides` | **new**: the narrative (calculating, performing, pulling back) and the slides carried over from the analysis team's delivered decks that the extracts can generate (year over year, who generates the fees) with parity comparisons |
| `peers_slides`, `peer_pull` | **new**: the peer comparison on `build/peer_compare.py` (Live Review's arithmetic, five peers at least); `peer_pull` reads other ILS clients' own ZAccounts extracts from the analysis share (read-only) into `Build Artifacts/ils_analysis/peers/` |
| `standard_slides` | **new**: the agenda, and the industry / regulatory slides read from the cycle's `industry_<yyyy-mm>.json` in `Build Artifacts/ils_analysis/standard/` |
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
exception items by channel (the DBIC's paid and returned items with ZTrend's median item amount, one slide; the treemaps when
there is no DBIC channel table), eligibility, Reg E tables, debit-decline segmentation and the Scoring Summary tables
reproduce the deck's figures from the extracts; the not-repaid chart, branch bubbles, alluvial, windfall predictor and
the deck's "open active" population are close but depend on definitions that are not in the extracts; the peer NSF / OD
fee slides need ILS-wide data and are labelled placeholders.

## Definitions that differ from the analysis team's README (all stated on the Data Notes slide)

* **Scoring Summary default.** The analysis notebook's rule (`ILS Analysis - Python Script.ipynb`, the `CURE` flag), the
  default since 2026-11-13 (`default_basis="notebook"`): a notice on a charged-off account dated on or after the
  account's last positive date (the largest `Last_Positive_Date` over all its notices) is a default; losses are the
  account's `Chargeoff_Amt_365`, once, on the notice nearest that date; the window is 425 to 60 days before the newest
  notice, notices with a limit at or under the matrix maximum (the notebook's `risk_set`). It reproduces Tim Barrett's
  Northwest Bank 1245 tables (2026.11) band for band, Achieva's 10.1% first Days On Book band, and William's Dannemora
  1781 band counts and fees. The earlier fit, 40 days with never-repaid excluded (`--default-basis deck`, 9.8% on
  Achieva), and the README rule (`--default-basis readme`, 30 days with never-repaid counted, 40% on Achieva) remain as
  options.
* **Not repaid (fatal notices).** The notebook's `FATAL2` (cells 30-34, `MasterQueryReordered2025.R` in R): a
  charged-off account's ONE notice nearest its last positive date. The monthly table is its `198_NEWTS_BETA`; on 1781
  all twelve months equal William's slide 35 on a pull cut at his data date. The 60-day cure slides (`performing`) are
  out of the default story since 2026-11-17 (Aaron: "Your cure rate slides are wrong").
* **Charge-off data that cannot be right**: more than half the accounts flagged, or a loss rate (365-day charge-offs
  over collected fees) above 100%, where programs run 4% to 12% and about 20% at the high end (Aaron, 2026-11-17).
  1781 fails both (99% flagged; a 303,433% loss rate). Charge-off dollars and loss rates read n/a; rates follow the
  flag as the notebook's do, and say so on the slide. The 1781 match with William proves the logic is ported, not
  that its rates are right: rate validation rests on Northwest 1245 and Achieva 1544.
* **Notice.** One account on one notice date (ZTrend has one row per item): Achieva's window holds 317,064 item rows and
  216,062 account-days, and the deck's bands sum to 216,034.
* **Window.** 365 days ending 60 days before the data as-of date (Achieva 2025-07-12 to 2026-07-12), not "trailing 12 months from the snapshot".
* **Days OD.** In the deck it is days since the account last had a positive balance (`noticedate` minus
  `Last_Positive_Date`; 157,932 notices, an exact count match), not days to repayment as the README says.
* **Data as-of.** The data's maximum `lastupdate` (2026-09-10), not the file stamp (2026-09-11), which goes in the notes.
* **Open active accounts.** Open, with more than $50 deposited or at least one NSF/OD item in 365 days: the notebook's
  `ACTIVITY` flag (cell 38), which reproduces the analyst decks' figure exactly. It replaced a 240-day deposit window fitted
  on Achieva, which ran -3% to +9% on twelve other clients.
* **Bands.** `scoring_summary.DECK_BANDS` overrides the three predictors whose bands differ in the deck (Days OD, Windfall Ratio,
  ILS Limit); `predictors("readme")` is the analysis registry.

The 40-day default was fitted to one client (Achieva) and tested on a second (Affinity, built with no code change); it
held to about 0.6 pt on mature accounts but not on accounts under 30 days old. Treat it as unconfirmed with the analysis
team, not as their rule.

## Run

```powershell
$env:RPE_DATA_ROOT = '\\PADMIS105\Velocity_company\CSM_Reporting'
cd <checkout>\build\ils_analysis
..\..\.venv\Scripts\python.exe -m ils_review.cli --from-folder "<...>\DataPull_20260911" `
    --client "Achieva Credit Union" --client-id 1544 `
    --out-dir "$env:RPE_DATA_ROOT\Build Artifacts\ils_analysis\out"
```

Run it from the checkout, never with a client's data folder (or the analysis share) as the working directory.
`--as-of YYYY-MM-DD` builds as of an earlier date, to match a review already given: notices, debit declines and refunds after
it are left out, while the ZAccounts fields and the DBIC stay as pulled ("About this data" says so). Dannemora 1781 is built
`--as-of 2026-10-25`, William's data date, because the not-repaid table's newest month moves as data lands.
The deck is named `<id>-<yyyy.mm>-ILS-<Client> ILS Analysis.pptx` (`ILS` is not an RPE program tag; `promote_month` never reads it
as one), where `yyyy.mm` is the data pull's file stamp, never the clock. A `parity_reference.json` beside the charts
(Achieva's hand-built figures, kept in the work folder, never in git) switches on the sidecars' comparison with the hand-built deck.

Tests: `tests/test_ils_analysis.py` (synthetic data only).
