# Live Review: what is in the review, and what is not

Aaron, 2026-11-03: *"go through them and pick the most impactful as if you're a banker in charge of retail performance."* Each candidate slide was judged the way a head of retail banking would judge it, in this order:

1. **Dollars.** Does it tie to revenue, profit, fee income, deposits or interchange?
2. **A decision.** Does it name one (where to mail, which branches to coach, what to fix in Reg E opt-in, which competitors take our members' spend, which accounts may leave)?
3. **Clear and comparable.** Is the finding clear without explanation, and set against a goal, the prior period, a control or the rest of the book?
4. **Not already on the page.**

Candidates: the 38 ARS Companion views (`combined_insights.compute`, `companion_deck.py`), the Transaction Intelligence cut as PR #106 (`feat/ti-deck-cleanup`) leaves it (151 slides in 8 chapters, `ti/slides.json`), and the 7 ARS screens the page already had. The page keeps **20 screens in 7 sections** (plus, for a client that has them, the other programs' results and a "How you compare" section; see the end); every other candidate is folded into one of them or left out, with the reason below.

## The storyline

| # | Section | Screen | Decision it supports | Compared with | Data it needs | Marine FCU 1539 | CoastHills 1776 |
|---|---|---|---|---|---|---|---|
| 1 | The program | ars:summary | Is the program paying its way? | the 2:1 guarantee | ARS workbook pack, metrics | ready | ready |
| 2 | The program | ars:financial | Does the guarantee hold, and by how much? | the 2:1 minimum | workbook Actuals tab | ready | ready |
| 3 | Revenue | ars:mailings | What response to expect from a mailing | the trailing mailings | ODD mailing fields | ready | ready |
| 4 | Revenue | analysis:waves | Which mailings keep paying | each other | ARS analysis pack, workbook | ready | ready |
| 5 | Revenue | analysis:offers | Where to mail: dollars per 1,000 offers | each other | ARS analysis pack | ready | ready |
| 6 | Revenue | analysis:response | What a response is worth | a control group | ARS analysis pack | ready | ready |
| 7 | Branches | ars:take | Which branches to coach on debit take | the book | ODD | ready | ready |
| 8 | Branches | ars:rege | What to fix in Reg E opt-in | the book, two cohorts | ODD | ready | ready |
| 9 | Branches | analysis:scorecard | Branch by branch: take, Reg E, closures | the whole book | ARS analysis pack | ready | ready |
| 10 | Members | ars:usage | Where swipes and spend sit; the NSF/OD trend | prior months (complete only) | ODD, workbook | ready | ready |
| 11 | Members | ars:lift | What moving up a tier is worth a month | the matrix | workbook Lift Matrix | ready | ready |
| 12 | Members | analysis:migration | Who is moving up and down | a year ago | ARS analysis pack | ready | ready |
| 13 | Competition | ti:competition | Which competitors take our members' spend | the book | TI pack with transaction files (about 25 minutes) | run the TI build with transaction files | ready |
| 14 | Competition | ti:leakage | Who else members borrow from and insure with | the book | TI pack with transaction files | run the TI build with transaction files | ready |
| 15 | Attrition | ti:attrition | Which branches lose accounts | the best branch | TI pack (ODD only) | ready | ready |
| 16 | Attrition | ti:at-risk | Which accounts to call: the deposits behind them | the book | TI pack (ODD only) | ready | ready |
| 17 | Attrition | ti:deposits | Where inflow is falling or idle | the book | TI pack with the deposits extract | run the TI build with the deposits extract | ready |
| 18 | Worth next | analysis:five-points | What five points of take and Reg E would earn | today's rates | ARS analysis pack (+ TI value) | ready | ready |
| 19 | Worth next | ti:value | What a card and an opt-in earn a year | accounts without | TI pack (ODD only) | ready | ready |
| 20 | Worth next | ti:branch-gap | Which branches under-earn | the best branch | TI pack (ODD only) | ready | ready |

TI figures are James Gilmore's v5 analyses as the cut ported them; nothing is recomputed on the page, and the page starts none of the heavy runs (the transaction pass is 12M rows and about 25 minutes per client).

## Every candidate, kept or left out

### ARS Companion views (38)

| Candidate | Decision | Where | Why |
|---|---|---|---|
| Swipe Tier Migration | kept | analysis:migration | who moved up and down in a year; a movement read against the book |
| Tier Movement by Response | left out |  | a cut of tier migration by response; the migration screen carries the book-wide movement |
| First Swipes: Program and Organic | left out |  | activation counts; names no dollar or decision beyond the response screen |
| PIN and Signature Mix | left out |  | PIN share is flat across the year (35.3% to 35.4%); an interchange premium is background, not a decision |
| Where Card Spend Goes | left out |  | category mix of card spend; no action attached |
| How the Money Moves | left out |  | needs the monthly transaction file inside the ODD zip; heavy, and the TI competition screens carry the leakage |
| Revenue by Mailing | kept | analysis:waves | dollars by mailing; says which mailings paid |
| Revenue Build by Mailing | folded | analysis:waves | same data as Revenue by Mailing, shown as a build curve |
| Revenue per 1,000 Offers | kept | analysis:offers | dollars per thousand offers: where to mail |
| Where This Month's Revenue Came From | kept | analysis:waves | this month's dollars by the mailing they trace to |
| Revenue per Fee Dollar by Mailing | left out |  | same ranking as revenue per 1,000 offers, on fee dollars |
| Offer Segments per 1,000 Mailed | folded | analysis:offers | the same measure cut by offer segment |
| Response by Offer Number | left out |  | response curve by offer number; secondary to what a response is worth |
| Sustained Activity: Non-User vs Threshold | left out |  | a persistence detail; the response screen already shows the lasting dollars |
| Responders vs Mailed Non-Responders | kept | analysis:response | a control, so the finding is comparable: net dollars a month |
| Responders vs Their Own Segment | left out |  | a second control; the mailed non-responder control is the cleaner comparison |
| Responders vs Non-Responders by Mailing | left out |  | per-mailing detail of the response screen |
| What a Response Is Worth | folded | analysis:response | the dollar reading of the same comparison |
| Where Take Rate Lags | left out |  | take is 91% book-wide and the branch screens show the spread |
| Where Cards Lag | left out |  | as above |
| Debit Spend per Cardholder | left out |  | already on the page (ars:usage, workbook Key Trends) |
| Cards in Use and Spend per Card | left out |  | shape of the same series as Debit Spend per Cardholder |
| Card Account Health | left out |  | states of cards; the at-risk screen carries the deposits dollars |
| What a Card and an Opt-In Earn | folded | ti:value | the TI Value slide carries the same dollars with the with/without comparison |
| Value by Account Age | left out |  | descriptive; no branch or offer to act on |
| Accounts Under Stress | left out |  | folded into Deposits at risk (ti:at-risk), which attaches deposits dollars |
| Reg E Elections Over Time | left out |  | a trend of one number the Reg E screen already states |
| Take Rate and Reg E Opt-In by Branch | folded | analysis:scorecard | already on the page as ars:take and ars:rege; the scorecard adds closures |
| Branch Scorecard | kept | analysis:scorecard | every branch on take, Reg E and closures: who to coach |
| Branch Value per Account | left out |  | folded into Branch value gap (ti:branch-gap) |
| Overdraft Limits by Reg E Election | left out |  | limits by election; the Reg E upside is on the five-points screen |
| Where Reg E Opt-In Lags | left out |  | folded into the branch scorecard |
| Program Cascade | left out |  | a funnel restating the program overview |
| ARS Scorecard | left out |  | a restatement of KPIs the summary shows |
| What Five Points Would Be Worth | kept | analysis:five-points | the sizing a banker asks for: cards and dollars per five points |
| Where the Balances Sit | left out |  | balance deciles; Deposits at risk names the accounts to call |
| Where Accounts Close | left out |  | folded into Attrition by branch (ti:attrition) |
| Card Spend Before a Close | left out |  | a detail of attrition; the at-risk screen carries the deposits |

### Transaction Intelligence cut, as PR #106 leaves it (151 slides)

| Chapter | Candidate | Decision | Where | Why |
|---|---|---|---|---|
| Transaction Intelligence | The book, narrowed | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | How the money moves | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Twelve months of flow | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Their financial life | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Where the money goes | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Where the leakage goes | kept | ti:leakage | names a decision, carries dollars and a comparison |
| Transaction Intelligence | Who they pay | folded | ti:leakage | its finding is carried by ti:leakage |
| Transaction Intelligence | How long the relationship has run | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Started and stopped | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | How deep the leakage runs | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Leakage by group | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Leakage by group and category | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | What leakers hold with us | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | How the leakage builds | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Which services travel together | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Still within reach | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | How members spend | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Card spend by category | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Ticket and intensity | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | When the card gets used | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Recurring payments on the card | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Card behaviour by lens | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Engagement breadth | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Merchants rising and falling | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | New and faded merchants | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | The MCC codes behind the categories | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | How broadly the card is used | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Card spend by member age | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Card use by account tenure | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | PIN or signature | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Who routes PIN | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | PIN-heavy accounts | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Where PIN gets pressed | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Channels used together | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | What a second channel is worth | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | The responder profile | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Every group against the book | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | What the banker actually opens | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | What the dictionary does not know yet | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | How external relationships age and turn over | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Card spend by age and by tenure | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Merchants moving in and out | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | Where card dollars go | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Transaction Intelligence | PIN and signature | left out |  | describes how members spend (rails, merchants, channels, ages); no decision or dollar the review acts on, and it needs the transaction files |
| Competition | Who competes for our members | kept | ti:competition | names a decision, carries dollars and a comparison |
| Competition | The local field | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Which competitors to work first | folded | ti:competition | its finding is carried by ti:competition |
| Competition | Filed growth | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Where the field sits | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Where we leak, by branch | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Where we lose and where we leak | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Gaining and losing | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Who leads each product | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Banks against the ecosystems | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Where the outflow goes | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Where the dollars go | folded | ti:competition | its finding is carried by ti:competition |
| Competition | Who owns the relationship | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | How much of the wallet has left | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Is the competitor money still moving | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | How many competitors each account uses | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Winback targets | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Depth against growth | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | The payment ecosystems, ranked | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Buy now, pay later | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | What competitors take and how much they own | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Competition | Payment apps and buy now, pay later | left out |  | another cut of the competitor list the kept competition screen already ranks; needs the transaction files |
| Attrition | Attrition by branch | kept | ti:attrition | names a decision, carries dollars and a comparison |
| Attrition | How much warning do we get | left out |  | survival and cohort curves: true but explanatory; the kept attrition screens name the branches and the deposits |
| Attrition | Accounts under several stresses | kept | ti:at-risk | names a decision, carries dollars and a comparison |
| Attrition | New accounts, cohort by cohort | left out |  | survival and cohort curves: true but explanatory; the kept attrition screens name the branches and the deposits |
| Attrition | Where closures cluster | folded | ti:attrition | its finding is carried by ti:attrition |
| Attrition | Where the risk sits | folded | ti:at-risk | its finding is carried by ti:at-risk |
| Attrition | Attrition by group | folded | ti:attrition | its finding is carried by ti:attrition |
| Attrition | Account retention — survival by tenure | left out |  | survival and cohort curves: true but explanatory; the kept attrition screens name the branches and the deposits |
| Attrition | Competitor spend before closure | left out |  | survival and cohort curves: true but explanatory; the kept attrition screens name the branches and the deposits |
| Attrition | Stresses across both files | folded | ti:at-risk | its finding is carried by ti:at-risk |
| Attrition | How long accounts stay open | left out |  | survival and cohort curves: true but explanatory; the kept attrition screens name the branches and the deposits |
| Deposits | What deposits look like | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | Who is paid here | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | Who stopped being paid here | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | When money last arrived | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | Where the deposits sit | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | Balance falling and inflow slowing | kept | ti:deposits | names a decision, carries dollars and a comparison |
| Deposits | What kind of income | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | Tax refunds | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | Who overdrafts, by how they are paid | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | Who banks here first | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | What arrives against what leaves | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | How members are paid | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| Deposits | When the pay stops | left out |  | how members are paid is descriptive; the kept deposits screen is the one with dollars at risk; needs the deposits extract |
| ICS Accounts | ICS acquisition | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS activation | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS never activated | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS cohorts | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS sustained activity | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS usage | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS quality | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS closure hazard | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS first-year closure | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS by branch | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS primacy | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS merchants | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS channel | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS composition | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS activation personas | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS retention | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| ICS Accounts | ICS summary | left out |  | the ICS lens: a separate deck and a different audience; the ICS program screens cover referrals |
| Economics | Program P&L by offer | on the page | ars:financial | already on the page as ars:financial |
| Economics | The 2:1 guarantee | on the page | ars:financial | already on the page as ars:financial |
| Economics | Where the month's revenue came from | folded | analysis:waves | its finding is carried by analysis:waves |
| Economics | What each offer has earned | folded | analysis:offers | its finding is carried by analysis:offers |
| Economics | What an account earns as it climbs | left out |  | program economics already on the page (ars:summary, ars:financial) |
| Value | What a card and an opt-in earn | kept | ti:value | names a decision, carries dollars and a comparison |
| Value | The value ladder | left out |  | a ladder or a per-segment restatement of the kept value screens |
| Value | Value per account by branch | kept | ti:branch-gap | names a decision, carries dollars and a comparison |
| Value | What a responder is worth | left out |  | a ladder or a per-segment restatement of the kept value screens |
| Value | Where cards do not follow volume | left out |  | a ladder or a per-segment restatement of the kept value screens |
| Value | Where branches diverge | folded | ti:branch-gap | its finding is carried by ti:branch-gap |
| Campaign | Program reach | on the page | ars:summary | already on the page as ars:summary |
| Campaign | Response and reach by offer | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Per-offer summary | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | The campaign hero | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Ladder and NU conversion by offer | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Segment trajectories | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | The penalty box | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | The counterfactual | folded | analysis:response | its finding is carried by analysis:response |
| Campaign | Which offer earns its postage | folded | analysis:offers | its finding is carried by analysis:offers |
| Campaign | Transaction increase over the ask | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Lift by response segment | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Depth of engagement — repeat responders | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Organic versus program activation | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | What a response does to spend | folded | analysis:response | its finding is carried by analysis:response |
| Campaign | Behavior by segment around the offer | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Responders versus control around the offer | folded | analysis:response | its finding is carried by analysis:response |
| Campaign | Sustained responder activity | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | First-time versus repeat responders | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Do partial responders convert? | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Who responds — the profile | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Tier movement by response status | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Swipe-tier migration | folded | analysis:migration | its finding is carried by analysis:migration |
| Campaign | Where the tiers moved | folded | analysis:migration | its finding is carried by analysis:migration |
| Campaign | The most recent mailer | on the page | ars:mailings | already on the page as ars:mailings |
| Campaign | The most recent mailer trajectory | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | The most recent offer | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Revenue frames | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Mailer * summary | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Mailer summaries | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Offer * by segment | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | *: responders versus their segment | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Reach and response | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |
| Campaign | Repeat responders | left out |  | per-offer and per-mailer detail; the kept revenue screens say which mailings pay and what a response is worth |

A slide PR #106 draws as one of a pair (`ti/deck/combine.py`) is listed under its own title and under the pair's.

## What is real and what needs a run first

- **Real on both test clients:** every ARS screen and every ARS analysis view (their packs are in `Build Artifacts/launcher/2026.10/<id>/companion/<id>/`).
- **Marine FCU 1539** has a TI pack but no transaction files and no deposits extract, so *Where members spend elsewhere*, *Who else members borrow from* and *Where deposit inflow is falling* show a *run the TI build* state with the command, never an empty chart. Its attrition, deposits-at-risk, value and branch-gap screens are real.
- **CoastHills 1776** (the TI cleanup's sample client) has the transaction files and deposits, so all 20 screens are real; it was used to develop and check the competition, leakage and deposits screens.
- Branch names come from the ARS pack's mapping; a branch the deck has no name for reads as *Branch <number>*.

## Other programs and peer comparisons

ICS, MRPC and CashPlease are programs of their own, not selections from the ARS candidates above. The page carries each as a first screen or two (results) and, after them, **How you compare**: the client against the other clients on the same program, anonymously.

| Program | Compared on | Normalised as | Left out |
|---|---|---|---|
| ICS | referrals | share of the monthly goal; per 1,000 DDAs where the DDA count is known | |
| MRPC | enrollments, cardholders still active, take rate among active accounts | share of goal; shares of cardholders and accounts | revenue (VIP's revenue is stale as of 2026-10-06) |
| CashPlease | loan volume, overdue and charge-off | loans per 1,000 DDAs (the ILS DDA count); shares of loans | |

Peers are all other clients on the program with current data; a client with no value for the month is not current for that metric and is counted in "left out". A pool or metric with fewer than five peers is stated and not shown. Nothing identifies another client.
