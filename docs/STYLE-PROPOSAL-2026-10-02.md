# Executive Review redesign — proposal

*Aaron asked (2026-10-02): learn what the current PowerPoint design guidance says, throw out
the existing style guide except the colors, and describe a presentation that keeps the data
impact but is more appealing and flows better. This is that description. Nothing here is
built; `templates/STYLE.md` is still the contract until a decision is made.*

What was looked at: `templates/STYLE.md`, the Union Financial reference shell (79 slides)
and the newest shipped combined deck (Marine FCU 2026.09, 73 slides), both rendered to PNG
with PowerPoint, plus the sources listed at the end.

---

## 1. What the current decks do well, and where they lose the room

**Keep.** The palette is good and already disciplined (one navy, one orange, greys, teal only
over navy). The partial-month hatched bar is the clearest treatment of that problem I found
anywhere. Figures are auditable: selection on the face, source in the notes. The validator
catches real defects. None of that changes.

**Lose the room.** Rendered side by side, the slides have five habits that current guidance
is unanimous about, and every one of them is a hierarchy problem, not a taste problem:

1. **Titles are labels, not findings.** "Program Overview", "ARS Financial Performance",
   "Overall Debit Swipes & Spend". A reader scanning the deck learns nothing from the title
   row. The finding exists, but it is a grey 16 pt paragraph at the bottom of the slide, the
   lowest-weight text on the page. Consulting standards put the conclusion in the title
   (active voice, under 15 words, two lines max) and let the body prove it.
2. **Every number gets the same weight.** The default content block is a row of four or five
   identical navy tiles with drop shadows, then bullets restating the same numbers. On ARS
   Financial Performance the 5.4 : 1 is the story, and it shares the slide with four tiles and
   three bullets that repeat it. MRPC Enrollments by Channel shows one set of four
   percentages three times (donut, bars, caption). When everything is emphasised, nothing is.
3. **Orange competes with itself.** Orange is the period pill, the highlighted bar, the total
   row, the hero tile, the agenda badges and the opportunity strip. On most slides three or
   four orange things fight for the eye, so the one that carries data meaning (the current
   month, the branch that lags) is not the one you see first.
4. **No rhythm.** 73 slides share one layout: title, pill, grey subtitle, content, caption,
   logo, number. The only visual change is a navy divider every 10 to 20 slides. The deck
   also has no executive summary; the first finding appears on slide 7, after the cover, the
   Summit ad, the agenda, a divider, Product Mix and Excluded Accounts.
5. **Shadows and chrome.** Drop shadows on every tile, pill and badge, navy-filled table
   headers, rounded navy cards for a single sentence. This reads as 2012 PowerPoint. The
   current look across executive and dashboard design is flat cards on a grid.

What executives actually read, per every QBR guide checked: the summary and the ask. An
executive deck is 8 to 12 slides with large visuals; detail goes to an appendix. Ours puts
the summary at the end of each section and the appendix in the middle (the ICS education
slides sit between the ICS data and the CashPlease section).

---

## 2. The idea in one paragraph

**Lead with the finding, give it one hero, and keep orange for the data.** Every data slide
gets a headline that states what the figures show, one element that is unmistakably the
biggest thing on the slide, flat cards on a 12-column grid, and a single orange mark that
points at the finding. The deck opens with a one-page executive summary, every section
divider carries that section's three headline numbers, every section closes with
recommended actions, and the detail tables move to an appendix. Transitions are Morph only,
and only where a number grows into the slide that explains it.

---

## 3. The system

### 3.1 Palette — unchanged, roles reassigned

Every hex stays exactly as `build/brand.py` declares it. What changes is what each color
is *for*:

| Color | Now | Proposed |
| --- | --- | --- |
| `NAVY` | titles, tiles, bars, headers, numbers | titles, hero numbers, base series, structure (rules, kickers) |
| `ORANGE` | pill, highlighted bar, total row, hero tile, badges, strip | **the one data emphasis per slide**: the current month, the row or branch the headline is about, the delta chip when the move is positive. Never on furniture. |
| `TICK` | subtitles, body grey | body, axis text, footers, the "flat/down" delta chip |
| `ROWALT` / `TILE` | zebra rows, light card | card fill for every supporting cell, section-close slide background |
| `STEEL` / `STEEL_SOFT` / `LIGHT` | secondary series | secondary series, muted bars (everything that is not the point) |
| `TEAL` | lines over navy | lines over navy, and the ICS/MRPC line series on white |
| `PEACH` | one-pager text | 30% tint behind a highlighted table row |
| `GOLD` / `SLATE` | tiers | tiers, unchanged |

**The one-orange rule.** A slide carries at most one orange *data* mark (a bar, a point, a
row, a chip, a hero number) and no orange furniture. The period pill, agenda badges and
opportunity strip stop being orange. This is the single change that does the most work.

### 3.2 Type — same two faces, a real scale

Montserrat and Calibri stay (embedded, metric-safe, charts in Carlito). The scale is new:

| Role | Face | Size | Use |
| --- | --- | --- | --- |
| Hero | Montserrat ExtraBold | 84 pt (72 on a shared slide) | the one number the slide is about |
| Headline | Montserrat SemiBold | 28 pt navy, 2 lines max | the finding |
| Kicker | Montserrat Bold | 11 pt caps, +8% tracking, `TICK` | "ARS · DEBIT CARD" — the old topic title |
| Stat | Montserrat Bold | 32 pt navy | a supporting figure in a cell |
| Stat label / delta | Calibri | 13 pt `TICK` | "vs Aug 25", "program to date" |
| Body | Calibri | 16 pt | the rare sentence that is not a headline |
| Footer | Calibri | 10 pt `TICK` | selection, client, month, slide number |

**Massive typography is the 2026 look for title and statement slides** (80 pt and up, taking
half the slide). A hero number at 84 pt on white with a 13 pt label under it reads from the
back of the room and from a phone, which is where these decks are increasingly opened.

**The floor changes.** 16 pt stays the floor for anything the reader must read. Metadata
(kicker, footer, source, axis ticks) sits at 10 to 13 pt by design, because the point of a
footer is to be ignorable. The validator's floor rule needs a metadata class.

### 3.3 Grid and furniture

- **12 columns, 0.5" margins, 0.2" gutters** on the 13.333 x 7.5" slide. Every card, chart
  and cell snaps to column edges. The content band runs 1.45" to 6.75".
- **Top row (0.5" to 1.3"):** kicker left, period chip right. The chip is a navy outline
  capsule with navy text, 12 pt: `PTD · AUG 2026`. No fill, no shadow.
- **Headline** at 1.3", left-aligned, full width.
- **Footer (7.0" to 7.3"):** one 10 pt line, left to right: selection sentence · client ·
  "Executive Review · September 2026" · slide number. The lockup sits at the far right at
  1.1" wide. Everything a reader needs to orient is in one line, out of the way.
- **Cards are flat.** `TILE` fill, 0.1" corner radius, no outline, **no shadow anywhere in
  the deck**. A navy card is allowed only for the hero cell, at most one per slide.
- **Bento sizing.** Cards span 3, 4, 6, 8 or 12 columns. A hero cell is 4 x full-height or
  6 x half-height; a supporting cell is 3 x 1.4". Asymmetry is deliberate: the eye lands on
  the big cell first.

### 3.4 Headlines — the rule and the data behind it

The headline is derived, never typed as a constant, and it follows the existing +/-2% band
and the "no claim without a figure" rule from `CLAUDE.md`:

| Pattern | Example |
| --- | --- |
| movement | "Debit spend is up 11% on a year ago, $54.2M in August" |
| level vs threshold | "ARS has returned $8.80M at 5.4 : 1, above the 2 : 1 guarantee" |
| ranking | "Corporate carries the most cards and the lowest Reg E opt-in" |
| flat | "Average ticket is almost flat through response, $50 before and after" |
| missing data | "August is left out of this comparison: the extract was pulled mid-month" |

Twelve words or fewer, two lines at 28 pt, one verb, no superlatives (the banned list still
applies). If the headline needs "and", it is two slides.

**Pipeline note.** The builders, the swap gate and the validator resolve slides by *title*.
With findings as titles, the stable key moves to the kicker text or the slide's `name`
property. That is a builder change, not a style change, and it is the first thing to settle.

### 3.5 Charts — declutter, then point

- **Direct labels, no legend** when there are three series or fewer: the label sits at the
  line end or inside the bar.
- **No y-axis on a labelled bar chart.** The values are on the bars. Lines keep a light
  axis. No gridlines; one hairline baseline.
- **One orange mark.** The latest complete month, the branch in the headline, the cell in
  the Lift Matrix example. Everything else is navy, or `STEEL_SOFT` when it is context.
- **Annotate the finding on the chart.** A short orange label with a 0.75 pt leader at the
  point the headline is about ("+11% YoY"). This replaces the grey bottom caption.
- **No title inside the chart image.** The headline is the title. The image carries only a
  10 pt unit line ("$M, monthly").
- **Sparklines** (navy line, orange end dot, no axes, 1.2 x 0.4") beside any stat that has a
  12-month history, on the executive summary and the section dividers.
- **Delta chips**: `▲ 4.3%` in orange when the move is positive, `▼ 2.1%` or `≈ flat` in
  `TICK` otherwise. Up is never green: the palette has no green, and orange already means
  "look here".
- **Branch slides become ranked horizontal bars.** Twelve branch names read far better on
  the left of a horizontal bar than rotated under a column. The rate is the bar; the
  account count is a grey number column beside the name, so the denominator is still on
  the slide (Aaron's 2026-09-08 point stands). The branch the headline names is the one
  orange bar.
- **The bar-plus-line two-axis combo is retired.** It is the hardest chart in the deck to
  read at a glance.
- **Keep**: `MMM'YY` axes, the hatched partial month with its through-date, flat donuts,
  the Lift Matrix heat grid (move it up; a third of that slide is empty), render-at-box
  aspect, Carlito in charts.

### 3.6 Tables

Flat. Navy bold header text over a 1.5 pt navy rule, no header fill; zebra rows in `ROWALT`;
numbers right-aligned; the row the headline is about in navy bold on a 30% `PEACH` tint; no
orange total row. **Eight data rows maximum on a body slide**; anything longer is an
appendix table, and the body slide gets a chart of the same data. The 13-row Mailing
Response Summary is the first to move.

### 3.7 Icons

One line-icon set (navy, 1.5 pt stroke, Fluent or Lucide style), used structurally only:
one icon per program on the executive summary, the dividers and the kickers, so a reader
always knows which section they are in. No decorative icons on data slides.

### 3.8 Motion

- **Morph only**, 0.5 s, and only in two places: the executive summary's program cell grows
  into that program's divider, and an "overview" slide's chart moves into position on the
  "detail" slide that follows it. Every other transition is none.
- Morph is a transition element in the slide XML and can be injected by the builder; the
  decks still read correctly as static PDF, which is how many clients receive them.
- A **Summary Zoom** on the executive summary (click a program, jump to its section) is the
  non-linear navigation the 2026 guidance recommends for live Q&A. It is harder to author
  outside PowerPoint and should be a phase-four item.

---

## 4. The deck, slide by slide (combined ARS + ICS + MRPC + CP)

Target: about 40 body slides, down from 70+, with nothing lost; the difference is an appendix.
Headline figures below are Marine FCU 2026.09 where that deck was rendered (ARS, the ICS
referral slides, CashPlease, MRPC enrollments and program to date); the ICS branch, MRPC
goal, retention and revenue headlines are illustrative of the pattern, not that deck's values.

**1 · Cover (navy).** Left-aligned, not centered. Client logo top-left (we have them in
`Inputs/Logos/`). "Executive Review" in 20 pt white caps; "September 2026" in 84 pt
Montserrat ExtraBold white; the products as four small outline chips under it (ARS · ICS ·
MRPC · CashPlease). Lockup bottom-right. No card behind the logo.

**2 · Executive Summit.** Unchanged, by rule.

**3 · Executive Summary (NEW — the slide the CEO reads).** A bento grid: four program
cells across the top, each with the program icon, the one hero number (ARS 5.4 : 1
profitability · ICS 124% of referral goal · MRPC 93 enrollments · CP 39.6 loans per 1,000
DDAs), a delta chip and a 12-month sparkline. Below, a 6-column "What changed this month"
cell with three derived sentences, and a 6-column "What we recommend" cell with the one
or two actions the section-close slides carry. Right rail: the period chips for each
section, which is also where the CashPlease date is allowed to differ. This replaces the
Agenda; the four cells *are* the agenda, in order.

**4 · ARS divider (navy).** Section name in 60 pt, and underneath it the section's three
headline numbers in 40 pt white with 13 pt labels: profitability, profit PTD, latest
mailing response. A divider that carries numbers earns its slide. A thin progress track
along the bottom (ARS · ICS · MRPC · CP) with the current section in orange.

**ARS body, in narrative order: result, why, where, what next.**

5. *"ARS has returned $8.80M at 5.4 : 1, above the 2 : 1 guarantee."* Hero 5.4 : 1 at
   84 pt in a navy cell (4 columns, full height). Right: the Revenue Guarantee P&L as a
   flat 6-row table (revenue, cost lines, profit; last month and PTD) with the surplus over
   the guaranteed minimum as the one orange figure. This merges ARS Financial Performance
   and Revenue Guarantee, which today repeat each other.
6. *"The book: 37,629 of 71,466 open accounts are ARS-eligible."* Product Mix and Excluded
   Accounts become one slide: a horizontal waterfall from open accounts to eligible
   (status, product code, no card, eligible) with the eligible bar orange, and the product
   table (top 5 + roll-up) beside it. Program age and mailing count sit in the kicker row.
7. *"Response has held between 11% and 15% across the last twelve mailings."* Chart of
   response % by mailing with the trailing-12 average as a dashed navy line and the latest
   mailing orange; stat cells for responders and threshold-met. The 13-row table goes to
   the appendix.
8. *"Responders raised monthly debit spend from $495 to $829, a 67% increase."* Hero +67%;
   the before/after chart beside it with no legend (labels at the bar ends). The NSF/OD
   panel keeps its own headline on the next slide, because one finding per slide.
9. *"Ticket is almost flat through response; the gain is more swipes, not bigger ones."*
   The Average Ticket pair, with the derived verb in the headline instead of a caption.
10. *"The Lift Matrix: a 1-5 account that reaches 11-15 adds $12.26 a month."* Heat grid
    moved up to the content band; the example cell is the one orange element.
11. *"Debit spend is up 11% on a year ago."* Hero +11% with the delta chip; the 36-month
    bars with no y-axis, August orange, the annotation at the last bar.
12. *"91.0% of eligible personal accounts opened this year took a card."* Take rate as
    ranked horizontal bars by branch, count column beside the names; Call Center (81%)
    is the orange bar because the headline is about where it lags.
13. *"29.3% of personal card holders opted in; Corporate holds the most cards and sits at
    35%."* Reg E: donut as a small stat cell, ranked horizontal bars by branch, the branch
    named in the headline in orange.
14. *"What we recommend."* Section close on a `TILE` background: two or three action cards
    (icon, one-line action, the figure it rests on, the branch or segment). This replaces
    the three bullet columns and the orange strip.

**15 · ICS divider** with referrals PTD, YTD and September vs goal.
16. *"956 referrals year to date; September came in at 124% of goal."* Hero 124% with the
    goal as a thin navy target line on the monthly bars (goal line only when it is within
    range of the data, as now).
17. *"Referral volume peaked at 129 in June and has held above 90 since."* The trend chart
    with the one annotation. (Workbook slides follow here only when the workbook is for
    this period, as today.)
18. *"Five branches produced 71% of this year's referrals."* Results by Branch as ranked
    horizontal bars; Direct Mail New Accounts stays its own slide when present.
19. *What we recommend* (ICS).
    The six education slides (E-Learning, VIP guides, 2026 releases) move to the appendix
    as "Resources", after the data, not in the middle of it.

**20 · CashPlease divider** with loans booked, principal advanced, loans per 1,000 DDAs.
21. *"39.6 loans per 1,000 DDAs, against a 17.0 client average."* Hero 39.6, the
    cumulative curve, the peer comparison as two stat cells. The 50-word cohort footnote
    becomes a 10 pt footer and a full sentence in the notes.
22. Loan Volume by Month, Portfolio by Status, Program Settings: each with a headline, the
    settings tables flat.
23. *What we recommend* (CP).

**24 · MRPC divider** with cardholders enrolled, September enrollments, share of open debit.
25. *"7,942 cardholders enrolled, 19.1% of open debit accounts."* Program to Date, one hero.
26. *"93 enrollments in September; Platinum is 82% of them."* The stacked monthly chart
    with no legend (tier labels on the last bar), the tier cells to the right.
27. *"Enrollments ran at 104% of goal over the last six months."* Performance vs goal.
28. *"Retention: 94% of accounts enrolled a year ago are still active."* Retention.
29. *"MRPC paid Marine FCU $X this year, on pace for $Y."* Revenue by month with the
    projected year as a dotted extension.
30. *What we recommend* (MRPC).

**31 · Questions & Discussion + Contact (one slide, navy).** "Questions & Discussion" at
60 pt, the CSM's card as a white flat card at the lower right: name, role, phone, email.
Two closing slides become one.

**32+ · Appendix (white, kicker "APPENDIX").** The ARS profile slides, the Mailing
Response Summary table, Enrollments by Channel (as one ranked bar chart, not three
renderings), the ICS resources, the MRPC cancellations. Each still carries a headline;
nothing in the appendix is unexplained.

**Rhythm:** navy (cover) · Summit · white summary · navy divider · 9 white · `TILE` close ·
navy divider · 4 white · `TILE` close · … · navy close. The eye gets a reset every section.

---

## 5. Before and after, on the slides that change most

| Slide today | What a reader sees first | Proposed |
| --- | --- | --- |
| ARS Financial Performance: orange hero, 4 navy tiles, 3 bullets | the orange box, then four equal boxes, then re-reading it all in bullets | hero 5.4 : 1, the P&L table, the surplus figure in orange; headline says it once |
| Program Overview: 5 navy tiles, 3 bullets | five equal numbers | removed as a slide; program age and mailings go in the kicker row, the figures go where they are used |
| Mailing Response Summary: 13-row table with orange total | a wall of numbers | a response-rate chart with the trailing average; the table in the appendix |
| 12-Month Take Rate: 4 tiles over a bar+line two-axis chart | the tile row; the chart needs explaining | one hero, ranked horizontal bars, count column, one orange bar |
| Enrollments by Channel: donut + bars + caption, same four numbers | three versions of one fact | one ranked bar chart in the appendix; the fact is a line on the MRPC summary |
| ARS Key Takeaways: three grey cards of bullets, orange strip | twelve bullets | three action cards, each with its figure and its branch |
| Agenda | a table of contents | the executive summary's four program cells |
| Questions + Contact (two slides) | a lone navy card on white | one navy closing slide with the contact card |

---

## 6. What this would take

The style guide can be thrown out; the machinery cannot, and most of it carries over.

| Area | Change |
| --- | --- |
| `build/brand.py` | no new hex values; add the type scale and the delta-chip styles |
| `build/shapes.py` | remove `shadow` from every primitive; add `stat_cell`, `hero_cell`, `delta_chip`, `kicker`, `footer_line`, flat `add_table` |
| `build/slide_geometry.py` | the 12-column grid as the contract; cards snap to columns |
| headlines | a `headline()` derivation per slide beside the figure derivation, using the +/-2% band and `claim_consistency` rules; the slide key moves from title to kicker/`name` |
| chart renderers | no legends ≤ 3 series, no y-axis on labelled bars, annotation API, sparkline renderer, ranked horizontal branch chart in `chart_lib` |
| `templates/*.pptx` | re-materialised shells; executive summary, numbered dividers, section-close and merged closing slides; `layout_baseline.json` re-snapped |
| `validation/validate_deck.py` | new rules: no `outerShdw` anywhere; at most one orange data mark per slide; headline ≤ 12 words / 2 lines; metadata font class for the floor; action title present on every data slide |
| `assemble_combined.py` | the executive summary and progress track are assembled from the section decks' figure sidecars |
| ILS prep slides, Summit one-pager | out of scope; they live in other people's decks |

**Phasing, so each step ships a better deck than the last:**

1. **No template change:** remove every shadow; period pill to a navy outline chip; the
   grey bottom caption becomes the headline; footer line. This alone fixes points 1, 3 and 5
   in section 1.
2. **Structure:** executive summary, dividers with numbers, section-close action slides,
   merged closing slide, detail tables and education slides to the appendix.
3. **Grid and charts:** 12-column bento cards, hero cells, chart declutter, ranked branch
   bars, sparklines and delta chips.
4. **Motion:** Morph between summary and dividers; Summary Zoom if it can be authored
   reliably.

Open questions for Aaron before phase 1: (a) is the executive summary allowed to carry a
recommendation, or only findings; (b) does the Agenda slide need to survive for any client
who expects it; (c) the slide-key change from title to kicker touches the swap gate, which
is the one piece of this that can silently ship a wrong number if done carelessly.

---

## Sources

Consulting and executive-deck standards:
[Deckary — Consulting slide standards](https://deckary.com/blog/consulting-slide-standards) ·
[Deckary — Slide deck design principles](https://deckary.com/blog/slide-deck-design-tips) ·
[StrategyU — Consulting presentations](https://strategyu.co/consulting-presentations/) ·
[A1 Slides — Pyramid Principle](https://a1slides.com/mckinsey-presentation-framework/)

What executives read in a review deck:
[Deckary — QBR template](https://deckary.com/blog/quarterly-business-review-template) ·
[Decky — QBR deck guide 2026](https://decky.ai/blog/qbr-deck-template-guide) ·
[Sybill — QBR best practices 2026](https://www.sybill.ai/blogs/qbr-templates-agendas-and-best-practices) ·
[Presentations.ai — Presenting a QBR](https://www.presentations.ai/blog/present-a-quarterly-business-review)

2026 design guidance and trends:
[Microsoft — PowerPoint design ideas 2026](https://powerpoint.cloud.microsoft/create/en/blog/powerpoint-design-ideas/) ·
[SlideEgg — 7 design trends 2026](https://www.slideegg.com/blog/presentation-tips/the-7-presentation-design-trends-dominating-2026-data-backed/) ·
[Envato — 30 PowerPoint tips](https://elements.envato.com/learn/powerpoint-presentation-tips-2) ·
[Envato — Design trends 2026](https://elements.envato.com/learn/presentation-design-trends-ppt) ·
[InkPPT — Trends for CXOs](https://www.inkppt.com/post/presentation-design-trends-the-complete-guide) ·
[Orbix — Bento grid dashboards](https://www.orbix.studio/blogs/bento-grid-dashboard-design-aesthetics) ·
[SaaSFrame — Bento grids that work](https://www.saasframe.io/blog/designing-bento-grids-that-actually-work-a-2026-practical-guide)

Data storytelling:
[Storytelling with Data — Focus attention (O'Reilly)](https://www.oreilly.com/library/view/storytelling-with-data/9781119621492/c04.xhtml) ·
[Storytelling with Data summary](https://medium.com/@alaaelnakeeb81/book-summary-storytelling-with-data-5934c3082e01) ·
[BizInfograph — Presenting data 2026](https://www.bizinfograph.com/blog/how-to-present-data-effectively-a-guide-for-2026/)

Motion:
[BrightCarbon — Using PowerPoint Morph](https://www.brightcarbon.com/blog/using-powerpoint-morph/) ·
[SlideModel — Morph explained](https://slidemodel.com/morph-transition-in-powerpoint/) ·
[Deckary — Transitions guide](https://deckary.com/blog/powerpoint-transitions)

The Instagram tag Aaron pointed at
([instagram.com/popular/powerpoint-presentations](https://www.instagram.com/popular/powerpoint-presentations/))
is behind a sign-in wall beyond the first screen; the visible posts are from fastppt_,
lourrutiappt (Luis Urrutia, a Microsoft MVP), amsonppt, jacob_ppt, pptgem and slidesapiens,
and the techniques they trade in are the ones above: Morph reveals, zoom covers, big-number
slides, frosted cards, and one idea per slide.
