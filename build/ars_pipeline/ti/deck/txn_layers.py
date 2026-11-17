"""
txn_layers.py — the Competition layers slides: which banks and credit unions members and customers pay, by
layer and by group. New to RPE; not a v5 port. They read the `cl_*` figures
(`ti/transaction_intelligence/competition_layers.py`, `competition_layers_modules.py`) and are drawn after
the Competition chapter's own slides, which they sit beside and do not replace (docs/migration/DUPLICATES.md).

Every headline is computed from the figures it sits on; none is a constant. A view the client's files cannot
support declines with its reason and is hidden for that client, as every builder of the cut does.
"""
from __future__ import annotations

from ti.transaction_intelligence import competition_layers as CL

from . import charts_layers as CLY
from .txn_common import RAIL_EDGE, money

COMPUTED = ("the competition layers section (ti/transaction_intelligence/competition_layers.py), "
            "new to RPE and not ported from the ARS v5 engine")
TIERS_DRAWN = [CL.LOCAL, CL.REGIONAL, CL.NATIONAL, CL.DIGITAL, CL.OTHER]
LIST_PAGE = 15

LIST_TOPIC = "Every institution paid"
TOP_DOLLARS, TOP_ACCOUNTS = "The top institutions by dollars", "The top institutions by accounts"
TITLES: dict = {}          # builder name -> the fixed slide title (what a declined slide is stated under)
BUILDERS: list = []


def _reg(name, title):
    def wrap(fn):
        fn.__name__ = name
        TITLES[name] = title
        BUILDERS.append(fn)
        return fn
    return wrap


# ---------------------------------------------------------------------------------------------- helpers
def _have(t):
    return bool(t.get("cl_tiers") and t.get("cl_any") and t.get("cl_base"))


def _no(label, why="no layered competition figures for this client"):
    return f"{label} ({why})"


def _own(t):
    ct = ((t.get("cl_scope") or {}).get("client_type") or "")
    return "members" if ct == "Credit Union" else "customers" if ct == "Bank" else "accounts"


def _word(kind):
    return "members" if kind == "Credit Union" else "customers"


def _lens(h):
    return h.get("lens", "ars")


def _labels(t):
    return (t.get("cl_base") or {}).get("group_labels") or {}


def _main(t, lens):
    """The groups the headline charts draw: responders / mailed non-response / no mail, or ICS / not ICS."""
    want = ("ics", "not_ics") if lens == "ics" else ("responders", "mailed_nonresp", "not_mailed")
    g = (t.get("cl_base") or {}).get("groups") or {}
    return [k for k in want if k in g]


def _wide(t, lens):
    """The groups the heat table draws: the near-responder split in place of the aggregate when it exists."""
    g = (t.get("cl_base") or {}).get("groups") or {}
    want = (("ics", "ics_dm", "ics_ref", "not_ics") if lens == "ics" else
            ("responders", "mailed_nonresp_nu1_4", "mailed_nonresp_none", "not_mailed"))
    keys = [k for k in want if k in g]
    return keys if len(keys) >= 2 else _main(t, lens)


def _slide(h, head, sub, topic):
    s, top = h["slide"]((head, sub), topic)
    if "relabel" in h:
        h["relabel"](s, topic, COMPUTED)
    return s, top


def _pct(v):
    return f"{v:.1f}%"


def _tier_rows(t):
    return {r["tier"]: r for r in t.get("cl_tiers") or []}


def _insts(t, tier=None):
    rows = t.get("cl_institutions") or []
    return [r for r in rows if tier is None or r["tier"] == tier]


def _names(rows, n=3):
    return ", ".join(r["inst"] for r in rows[:n])


def _share(rows, total):
    return sum(r["dollars"] for r in rows) / total if total else 0


def _left_text(shape, cols):
    from pptx.enum.text import PP_ALIGN
    for row in shape.table.rows:
        for c in cols:
            for p in row.cells[c].text_frame.paragraphs:
                p.alignment = PP_ALIGN.LEFT


# ------------------------------------------------------------------------------------------- orientation
@_reg("layers_guide", "How to read the competition layers")
def layers_guide(h, t, base):
    if not _have(t):
        return _no("How to read the competition layers")
    sc = t.get("cl_scope") or {}
    th = sc.get("thresholds") or {}
    lens = _lens(h)
    s, top = _slide(h, "How to read the competition layers",
                    "Banks and credit unions only; payment apps, lenders and buy-now-pay-later are in the financial services slides", "How to read the competition layers")
    rows = [["Term", "What it means"],
            ["Competitor", "A bank or credit union that members or customers pay with the debit card: a loan, card or similar payment. Found by matching the card text to every FDIC bank and NCUA credit union."],
            ["Tier", f"National: a national name, or branches in {th.get('national_states', 10)}+ states. Digital: no branches. Local: a branch within {th.get('local_miles', 25):g} miles of a client branch. "
                     f"Regional: headquartered in the client's Fed district{' (' + str(sc['district']) + ')' if sc.get('district') else ''}. State and Other: further away. Card-issuing banks are shown apart for review."],
            ["Group", ("Responders, mailed non-response (near-responders swiped 1-4 times after a mailer; the rest not at all) and no mail." if lens != "ics"
                       else "ICS account (direct mail or referral) against accounts that are not ICS.") + " Groups were selected differently, so they describe who the accounts are, not what a program did."],
            ["Relationship", "One account paying one institution. Depth is the share of that account's card dollars the institution takes; 20% or more is primary-relationship competition."],
            ["A floor", f"Card rail only ({sc.get('rail', 'PIN, SIG')}), over {(t.get('cl_base') or {}).get('accounts', 0):,} transacting accounts. Accounts do not add across tiers: one de-duplicated total is shown."]]
    shape = h["table"](s, rows, 0.6, top + 0.1, 12.1, [1.6, 10.5], 12)
    _left_text(shape, (1,))


@_reg("layers_summary", "Competition by layer: the summary")
def layers_summary(h, t, base):
    if not _have(t):
        return _no("Competition by layer: the summary")
    a, b, cov = t["cl_any"], t["cl_base"], t.get("cl_coverage") or {}
    n = len(t.get("cl_institutions") or [])
    own = _own(t)
    s, top = _slide(h, f"{a['pct']:.1f}% of {own} pay a bank or credit union: {money(a['dollars'])} a year across {n} institutions",
                    f"{a['accounts']:,} of {b['accounts']:,} {base}; banks and credit unions only, card rail only, so a floor. Share of the dollars by tier at left",
                    "Competition by layer: the summary")
    items = [("Pay a competitor", f"{a['pct']:.1f}%", f"{a['accounts']:,} of {b['accounts']:,}"), ("Dollars a year", money(a["dollars"]), "to banks and credit unions"),
             ("Institutions placed", f"{n:,}", "in a layer")]
    if cov.get("pct") is not None:
        items.append(("Coverage", f"{cov['pct']:.1f}%", "of bank-like card dollars"))
    right = h["rail"](s, items, top=top)
    rows = [[r["tier"], r["dollars"]] for r in t["cl_tiers"] if r["dollars"] / max(a["dollars"], 1) >= 0.01]
    small = sum(r["dollars"] for r in t["cl_tiers"] if r["dollars"] / max(a["dollars"], 1) < 0.01)
    if small:
        rows.append(["Smaller tiers", small])
    path = h["chart"]("layers_summary_donut", CLY.donut_tiers, rows, center_value=money(a["dollars"]), center_label="a year")
    if path:
        h["chart_left"](s, path, top, right)


@_reg("layers_ladder", "The layer ladder")
def layers_ladder(h, t, base):
    if not _have(t):
        return _no("The layer ladder")
    rows = _tier_rows(t)
    tot = t["cl_any"]["dollars"] or 1
    nd = (rows.get(CL.NATIONAL, {}).get("dollars", 0) + rows.get(CL.DIGITAL, {}).get("dollars", 0)) / tot
    loc = (rows.get(CL.LOCAL, {}).get("dollars", 0) + rows.get(CL.LOCAL_MARKET, {}).get("dollars", 0)) / tot
    present = {r["tier"] for r in t["cl_tiers"]}
    has_local = bool(present & {CL.LOCAL, CL.LOCAL_MARKET})
    title = f"National and digital institutions take {nd:.0%} of competitor dollars; local institutions take {loc:.0%}" if has_local else         f"National and digital institutions take {nd:.0%} of competitor dollars; no local institution appears in the card spending"
    s, top = _slide(h, title,
                    f"Share of {base} paying each tier. Accounts do not add across tiers; the de-duplicated total is {t['cl_any']['pct']:.1f}%",
                    "The layer ladder")
    ordered = sorted(t["cl_tiers"], key=lambda r: -r["accounts"])
    items = [(r["tier"], money(r["dollars"]), f"{r['accounts']:,} accounts, {r['institutions']} institutions") for r in ordered[:5]]
    right = h["rail"](s, items, top=top)
    path = h["chart"]("layers_ladder", CLY.hbar, [[r["tier"], r["pct"], r["tier"]] for r in ordered], xlabel="% of accounts", fmt="{:.1f}%")
    if path:
        h["chart_left"](s, path, top, right)


@_reg("layers_map", "Competitors near the client's branches")
def layers_map(h, t, base):
    m = t.get("cl_map")
    if not m or not m.get("branches") or not m.get("client"):
        return _no("Competitors near the client's branches", "the client's branches have no coordinates, or the reference store has no branch nearby")
    near = {r[2] for r in m["branches"]}
    seen = {r[2] for r in m["branches"] if r[3]}
    s, top = _slide(h, f"{len(near)} institutions have branches within {m['radius']:g} miles of a client branch; {len(seen)} appear in card spending",
                    f"Stars are the client's {len(m['client'])} branches; each dot is a competitor branch, coloured by tier when its institution appears in the card spending",
                    "Competitors near the client's branches")
    path = h["chart"]("layers_map", CLY.branch_map, m, client_label="client branches")
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


@_reg("layers_universe", "How many exist and how many are paid")
def layers_universe(h, t, base):
    u = [r for r in t.get("cl_universe") or [] if r["registry"]]
    if not u:
        return _no("How many exist and how many are paid")
    reg, seen = sum(r["registry"] for r in u), sum(r["seen"] for r in u)
    paid = len(t.get("cl_institutions") or []) or seen
    extra = paid - seen                      # paid institutions with no registry branch: digital names and ambiguous names
    s, top = _slide(h, f"{paid:,} institutions appear in card spending; {seen} of them are among the {reg:,} banks and credit unions in the registry",
                    "FDIC and NCUA institutions by tier, against the institutions that members or customers actually pay"
                    + (f". The other {extra} are digital-only names with no branches, or names that fit several institutions" if extra > 0 else ""),
                    "How many exist and how many are paid")
    right = h["rail"](s, [("In the registry", f"{reg:,}", "banks and credit unions"), ("Paid", f"{paid:,}", f"{seen} matched to a registry institution"),
                          ("Branch within reach", f"{sum(r['within_local'] for r in u):,}", "within the local radius")], top=top)
    shown = [r for r in u if r["seen"] or r["within_local"]]
    path = h["chart"]("layers_universe", CLY.columns, [r["tier"].replace(" (", "\n(") for r in shown],
                      {"In the registry": [r["registry"] for r in shown], "Seen in card spending": [r["seen"] for r in shown]},
                      colors={"In the registry": CLY.LINE, "Seen in card spending": CLY.ORANGE}, full=False)
    if path:
        h["chart_left"](s, path, top, right)


# ---------------------------------------------------------------------------------------------- the list
def _top_slide(h, t, base, key, topic, label, fmt, divisor, unit):
    rows = sorted(_insts(t), key=lambda r: -r[key])[:20]
    if len(rows) < 3:
        return _no(topic, "too few institutions")
    tot = sum(r[key] for r in _insts(t)) or 1
    a, b, c = rows[0]["inst"], rows[1]["inst"], rows[2]["inst"]
    s, top = _slide(h, f"The top {len(rows)} institutions take {sum(r[key] for r in rows) / tot:.0%} of competitor {label}; {a}, {b} and {c} lead",
                    f"{unit}, coloured by tier. Open the descriptors on the profile cards before quoting a name: a national's name can carry a lender or card subsidiary", topic)
    path = h["chart"](f"layers_top_{key}", CLY.hbar, [[r["inst"], r[key] / divisor, r["tier"]] for r in rows], xlabel=unit, fmt=fmt, full=True)
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


@_reg("layers_top_dollars", TOP_DOLLARS)
def layers_top_dollars(h, t, base):
    return _top_slide(h, t, base, "dollars", TOP_DOLLARS, "dollars", "${:,.0f}K", 1000.0, "Dollars a year, in thousands")


@_reg("layers_top_accounts", TOP_ACCOUNTS)
def layers_top_accounts(h, t, base):
    return _top_slide(h, t, base, "accounts", TOP_ACCOUNTS, "accounts", "{:,.0f}", 1.0, "Accounts paying the institution")


@_reg("layers_full_list", LIST_TOPIC)
def layers_full_list(h, t, base):
    rows = sorted(_insts(t), key=lambda r: -r["dollars"])
    if not rows:
        return _no(LIST_TOPIC)
    n = len(rows)
    for k in range(0, n, LIST_PAGE):
        page = rows[k:k + LIST_PAGE]
        s, top = _slide(h, f"Every institution paid, ranked by dollars ({k + 1}-{k + len(page)} of {n})",
                        "Nearest branch is measured from any client branch; blank means no branch near. Depth is relationships taking 20% or more of the account's card dollars",
                        LIST_TOPIC)
        body = [["#", "Institution", "Tier", "Accounts", "% of base", "Dollars / yr", "Nearest mi", "20%+ depth"]]
        for i, r in enumerate(page, start=k + 1):
            body.append([i, r["inst"][:34], r["tier"], f"{r['accounts']:,}", f"{r['pct']:.2f}%", money(r["dollars"]),
                         "" if r.get("nearest_mi") is None else f"{r['nearest_mi']:g}", "" if r.get("heavy") is None else f"{r['heavy']:,}"])
        shape = h["table"](s, body, 0.6, top + 0.05, 12.1, [0.5, 3.4, 2.4, 1.1, 1.0, 1.3, 1.2, 1.2], 11)
        _left_text(shape, (1, 2))


# ----------------------------------------------------------------------------------------- per-tier blocks
def _slug(tier):
    return tier.split(" (")[0].lower()


def _tier_who(tier):
    topic = f"{tier}: who the money goes to"

    def build(h, t, base):
        rows = sorted(_insts(t, tier), key=lambda r: -r["dollars"])
        if len(rows) < 3:
            return _no(topic, f"fewer than three institutions in this tier")
        tot = sum(r["dollars"] for r in rows)
        s, top = _slide(h, f"{tier}: {_names(rows)} take {_share(rows[:3], tot):.0%} of the {money(tot)} a year",
                        f"{len(rows)} institutions, {sum(r['accounts'] for r in rows):,} account relationships. Dollars a year for the top 10, in thousands",
                        topic)
        tr = _tier_rows(t).get(tier, {})
        right = h["rail"](s, [("Institutions", f"{len(rows):,}", "paid in this tier"), ("Accounts", f"{tr.get('accounts', 0):,}", f"{tr.get('pct', 0):.1f}% of {base}"),
                              ("Dollars a year", money(tot), "card rail, a floor")], top=top)
        path = h["chart"](f"layers_{_slug(tier)}_who", CLY.hbar, [[r["inst"], r["dollars"] / 1000.0, tier] for r in rows[:10]], xlabel="$K a year", fmt="${:,.0f}K")
        if path:
            h["chart_left"](s, path, top, right)
    return build, topic


def _tier_groups(tier):
    topic = f"{tier}: who pays"

    def build(h, t, base):
        rows = sorted(_insts(t, tier), key=lambda r: -r["dollars"])[:8]
        main = _main(t, _lens(h))
        if len(rows) < 3 or len(main) < 2:
            return _no(topic, "fewer than three institutions in this tier, or no groups to split by")
        lab = _labels(t)
        den = t["cl_base"]["groups"]
        tot = sum(r["accounts"] for r in _insts(t, tier)) or 1
        best = None
        for g in main:
            sh = sum(r["by_group"].get(g, {}).get("accounts", 0) for r in _insts(t, tier)) / tot
            ratio = sh / max(den[g] / max(t["cl_base"]["accounts"], 1), 1e-9)
            if best is None or ratio > best[3]:
                best = (g, sh, den[g] / max(t["cl_base"]["accounts"], 1), ratio)
        g, sh, bs, ratio = best
        s, top = _slide(h, f"{tier}: {lab[g]} are {sh:.0%} of the relationships but {bs:.0%} of the base",
                        f"Accounts paying each of the top {len(rows)} institutions, by group. {lab[g]} are over-represented here by {ratio:.1f} times",
                        topic)
        path = h["chart"](f"layers_{_slug(tier)}_groups", CLY.hbar_stacked, [r["inst"] for r in rows],
                          {lab[k]: [r["by_group"].get(k, {}).get("accounts", 0) for r in rows] for k in main},
                          colors={lab[k]: CLY.GROUP_COLOR.get(k, CLY.STEEL) for k in main}, full=True)
        if path:
            h["picture"](s, path, top=top, max_h=4.9)
    return build, topic


def _tier_movement(tier):
    topic = f"{tier}: movement in the last 90 days"

    def build(h, t, base):
        mv = [r for r in t.get("cl_movement") or [] if r["tier"] == tier]
        if len(mv) < 3:
            return _no(topic, "fewer than three institutions in this tier, or no dated relationships")
        tn, ts, lv = (sum(r[k] for r in mv) for k in ("new_90", "stopped_90", "live_30"))
        gain = max(mv, key=lambda r: r["new_90"] - r["stopped_90"])
        s, top = _slide(h, f"{tier}: {tn:,} relationships started and {ts:,} stopped in 90 days; {gain['inst']} gained most",
                        f"{lv:,} of {sum(r['relationships'] for r in mv):,} relationships were live in the last 30 days. The window is 12 months, so new is a floor and stopped counts long-quiet ones",
                        topic)
        right = h["rail"](s, [("New", f"{tn:,}", "first seen in 90 days"), ("Stopped", f"{ts:,}", "last seen before that"), ("Live", f"{lv:,}", "paid in the last 30 days")], top=top)
        big = sorted(mv, key=lambda r: -r["relationships"])[:10]
        path = h["chart"](f"layers_{_slug(tier)}_movement", CLY.hbar_stacked, [r["inst"] for r in big],
                          {"New (90 days)": [r["new_90"] for r in big], "Stopped": [-r["stopped_90"] for r in big]},
                          colors={"New (90 days)": CLY.GREEN, "Stopped": CLY.ORANGE})
        if path:
            h["chart_left"](s, path, top, right)
    return build, topic


def _tier_depth(tier):
    topic = f"{tier}: how deep the relationship runs"

    def build(h, t, base):
        d = [r for r in t.get("cl_depth_institutions") or [] if r["tier"] == tier]
        dt = next((r for r in t.get("cl_depth_tiers") or [] if r["tier"] == tier), None)
        if len(d) < 3 or not dt:
            return _no(topic, "fewer than three institutions in this tier, or no relationships to measure")
        lead = max(d, key=lambda r: r["heavy"])
        s, top = _slide(h, f"{tier}: {dt['heavy_pct']:.0f}% of relationships take 20% or more of the account's card dollars; {lead['inst']} has the most",
                        f"Each bar splits an institution's relationships by the share of the account's card dollars it takes (top 8 by relationships); {lead['inst']} has {lead['heavy']:,}",
                        topic)
        big = sorted(d, key=lambda r: -r["relationships"])[:8]
        path = h["chart"](f"layers_{_slug(tier)}_depth", CLY.hbar_stacked, [r["inst"] for r in big],
                          {"20%+": [r["heavy"] for r in big], "5-20%": [r["mid"] for r in big],
                           "under 5%": [max(r["relationships"] - r["heavy"] - r["mid"], 0) for r in big]},
                          colors={"20%+": CLY.ORANGE, "5-20%": CLY.GOLD, "under 5%": CLY.LINE}, full=True)
        if path:
            h["picture"](s, path, top=top, max_h=4.9)
    return build, topic


def _tier_bubble(tier):
    topic = f"{tier}: reach against depth"

    def build(h, t, base):
        d = {r["inst"]: r for r in t.get("cl_depth_institutions") or [] if r["tier"] == tier}
        rows = [[r["inst"], r["accounts"], d[r["inst"]]["heavy"] / max(d[r["inst"]]["relationships"], 1) * 100, r["dollars"]]
                for r in _insts(t, tier) if r["inst"] in d]
        if len(rows) < 3:
            return _no(topic, "fewer than three institutions in this tier")
        wide = max(rows, key=lambda r: r[1])
        deep = max((r for r in rows if d[r[0]]["relationships"] >= 10), key=lambda r: r[2], default=max(rows, key=lambda r: r[2]))
        s, top = _slide(h, f"{tier}: {wide[0]} reaches the most accounts; {deep[0]} has the deepest relationships",
                        "Each bubble is an institution: across = accounts paying it, up = share of its relationships taking 20% or more of the card dollars, size = dollars",
                        topic)
        path = h["chart"](f"layers_{_slug(tier)}_bubble", CLY.bubble, rows, xlabel="Accounts paying the institution",
                          ylabel="% of relationships taking 20%+", color=CLY.tier_color(tier))
        if path:
            h["picture"](s, path, top=top, max_h=4.9)
    return build, topic


def _tier_cards(tier):
    topic = f"{tier}: profile cards"

    def build(h, t, base):
        rows = sorted(_insts(t, tier), key=lambda r: -r["dollars"])[:5]
        if len(rows) < 3:
            return _no(topic, "fewer than three institutions in this tier")
        s, top = _slide(h, f"{tier}: the top {len(rows)} institutions in full",
                        "Who they are, how big, how near, which way they are moving, how deep, and the card text they appear under. Open the text before quoting a figure",
                        topic)
        body = [["Institution", "Base", "Accounts", "Dollars / yr", "Nearest mi", "New / stopped", "20%+ depth", "Appears under"]]
        for r in rows:
            mv = "" if r.get("new_90") is None else f"{r['new_90']:,} / {r['stopped_90']:,}"
            body.append([r["inst"][:28], _word(r["type"]), f"{r['accounts']:,}", money(r["dollars"]), "" if r.get("nearest_mi") is None else f"{r['nearest_mi']:g}",
                         mv, "" if r.get("heavy") is None else f"{r['heavy']:,}", "; ".join(r.get("descriptors") or [])[:46]])
        shape = h["table"](s, body, 0.6, top + 0.05, 12.1, [2.4, 1.0, 1.0, 1.2, 1.0, 1.4, 1.0, 3.1], 11)
        _left_text(shape, (0, 1, 7))
    return build, topic


for _tier in TIERS_DRAWN:
    for _kind, _mk in (("who", _tier_who), ("groups", _tier_groups), ("movement", _tier_movement), ("depth", _tier_depth),
                       ("bubble", _tier_bubble), ("cards", _tier_cards)):
        _fn, _topic = _mk(_tier)
        _reg(f"layers_{_slug(_tier)}_{_kind}", _topic)(_fn)


# ----------------------------------------------------------------------------------------- whole book
HEAT_TOPIC = "Which groups pay which tiers"


@_reg("layers_heat", HEAT_TOPIC)
def layers_heat(h, t, base):
    if not _have(t):
        return _no(HEAT_TOPIC)
    lens = _lens(h)
    cols = _wide(t, lens)
    lab = _labels(t)
    main = _main(t, lens)
    if len(cols) < 2:
        return _no(HEAT_TOPIC, "the client has only one group")
    rows = [r for r in t["cl_tiers"] if r["pct"] >= 0.05]
    mat = [[r["tier"]] + [r["by_group"].get(g, {}).get("pct") for g in cols] + [r["pct"]] for r in rows]
    a = t["cl_any"]["by_group"]
    hi, lo = max(main, key=lambda g: a[g]["pct"]), min(main, key=lambda g: a[g]["pct"])
    s, top = _slide(h, f"{lab[hi]} pay a bank or credit union most ({a[hi]['pct']:.1f}%) and {lab[lo]} least ({a[lo]['pct']:.1f}%)",
                    "Share of each group's transacting accounts paying each tier (darker = more). Accounts do not add across tiers. Groups were selected differently: read it as who they are",
                    HEAT_TOPIC)
    path = h["chart"]("layers_heat", CLY.heat, mat, [lab[g] for g in cols] + ["All accounts"])
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


LENS_TOPIC = "Every group against every tier"


@_reg("layers_lens", LENS_TOPIC)
def layers_lens(h, t, base):
    if not _have(t):
        return _no(LENS_TOPIC)
    lens = _lens(h)
    main = _main(t, lens)
    lab = _labels(t)
    rows = [r for r in t["cl_tiers"] if r["pct"] >= 0.3][:6]
    if len(main) < 2 or not rows:
        return _no(LENS_TOPIC, "the client has only one group, or no tier reaches 0.3% of accounts")
    a = t["cl_any"]["by_group"]
    said = ", ".join(lab[g] + " " + format(a[g]["pct"], ".1f") + "%" for g in main)
    s, top = _slide(h, "Share of each group paying a competitor, by tier",
                    f"The largest tiers by reach; each colour is a group. Any tier: {said}", LENS_TOPIC)
    path = h["chart"]("layers_lens", CLY.columns, [r["tier"].replace(" (", "\n(") for r in rows],
                      {lab[g]: [r["by_group"].get(g, {}).get("pct", 0) for r in rows] for g in main},
                      colors={lab[g]: CLY.GROUP_COLOR.get(g, CLY.STEEL) for g in main}, fmt="{:.1f}", ylabel="% of the group's accounts")
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


NEAR_TOPIC = "Near-responders"


@_reg("layers_near_responders", NEAR_TOPIC)
def layers_near_responders(h, t, base):
    if _lens(h) == "ics":
        return _no(NEAR_TOPIC, "mailed non-response is an ARS group")
    g = (t.get("cl_base") or {}).get("groups") or {}
    if "mailed_nonresp_nu1_4" not in g or "mailed_nonresp_none" not in g:
        return _no(NEAR_TOPIC, "no mailed account swiped 1-4 times after a mailer, or none did not")
    a = t["cl_any"]["by_group"]
    order = [k for k in ("responders", "mailed_nonresp_nu1_4", "mailed_nonresp_none", "not_mailed") if k in a]
    lab = _labels(t)
    spend = None
    tr = [r for r in t.get("cl_trend") or [] if r["group"] in ("mailed_nonresp_nu1_4", "responders")]
    if tr:
        last = sorted({r["month"] for r in tr})[-3:]
        nu = [r["per_active"] for r in tr if r["group"] == "mailed_nonresp_nu1_4" and r["month"] in last]
        rs = [r["per_active"] for r in tr if r["group"] == "responders" and r["month"] in last]
        if nu and rs:
            spend = (sum(nu) / len(nu), sum(rs) / len(rs))
    s, top = _slide(h, f"Near-responders pay a competitor least ({a['mailed_nonresp_nu1_4']['pct']:.1f}%) against {a['responders']['pct']:.1f}% of responders",
                    "Share of each group paying any bank or credit union. Near-responders swiped 1-4 times after a mailer, below the response threshold",
                    NEAR_TOPIC)
    note = ""
    if spend:
        note = f"Last three months' card spend per active account a month: near-responders ${spend[0]:,.0f}, responders ${spend[1]:,.0f}."
    right = h["rail"](s, [(lab[k], f"{a[k]['pct']:.1f}%", f"{t['cl_base']['groups'][k]:,} accounts") for k in order[:4]], top=top)
    path = h["chart"]("layers_near", CLY.hbar, [[lab[k], a[k]["pct"], CLY.GROUP_COLOR.get(k, CLY.STEEL)] for k in order], xlabel=note or "% paying a competitor", fmt="{:.1f}%")
    if path:
        h["chart_left"](s, path, top, right)


def _span(months):
    """Every month from the first to the last, so a month with no rows is a visible gap, never a skipped tick."""
    if not months:
        return months
    y, m = map(int, months[0].split("-"))
    y2, m2 = map(int, months[-1].split("-"))
    out = []
    while (y, m) <= (y2, m2):
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _line_slide(h, t, topic, key, head, sub, fmt, ylabel):
    tr = t.get("cl_trend")
    lens = _lens(h)
    main = _main(t, lens)
    if not tr or not main:
        return _no(topic)
    months = _span(sorted({r["month"] for r in tr}))      # a month with no card rows stays on the axis as a gap
    if len(months) < 3:
        return _no(topic, "fewer than three months in the window")
    lab = _labels(t)
    series = {lab[g]: [next((r[key] for r in tr if r["group"] == g and r["month"] == m), None) for m in months] for g in main}
    s, top = _slide(h, head(tr, months), sub, topic)
    path = h["chart"](f"layers_{key}", CLY.lines, months, series, colors={lab[g]: CLY.GROUP_COLOR.get(g, CLY.STEEL) for g in main}, fmt=fmt, ylabel=ylabel)
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


SPEND_TOPIC, PIN_TOPIC, COMP_TOPIC = "Card spend per active account by group", "PIN share of card dollars by group", "Competitor share of card dollars by group"


def _all(tr, key, months):
    rows = {r["month"]: r[key] for r in tr if r["group"] == "all"}
    return rows.get(months[0]), rows.get(months[-1])


@_reg("layers_spend_trend", SPEND_TOPIC)
def layers_spend_trend(h, t, base):
    return _line_slide(h, t, SPEND_TOPIC, "per_active",
                       lambda tr, m: f"Card spend per active account went from ${_all(tr, 'per_active', m)[0]:,.0f} to ${_all(tr, 'per_active', m)[1]:,.0f} a month over the window",
                       "Dollars per account with any card transaction that month, whole base and by group; the lines show where each group's card spend sits", "{:,.0f}", "$ per active account")


@_reg("layers_pin_trend", PIN_TOPIC)
def layers_pin_trend(h, t, base):
    return _line_slide(h, t, PIN_TOPIC, "pin_pct",
                       lambda tr, m: f"PIN share of card dollars went from {_all(tr, 'pin_pct', m)[0]:.1f}% to {_all(tr, 'pin_pct', m)[1]:.1f}% over the window",
                       "Signature routing earns more interchange than PIN, so a falling PIN share raises interchange per dollar; read the groups against each other", "{:.1f}", "% of card dollars")


@_reg("layers_competitor_trend", COMP_TOPIC)
def layers_competitor_trend(h, t, base):
    return _line_slide(h, t, COMP_TOPIC, "competitor_pct",
                       lambda tr, m: f"The share of card dollars going to a bank or credit union went from {_all(tr, 'competitor_pct', m)[0]:.2f}% to {_all(tr, 'competitor_pct', m)[1]:.2f}%",
                       "Depository competitors only; payment apps, lenders and buy-now-pay-later are not counted here", "{:.2f}", "% of card dollars")


MULTI_TOPIC = "How many institutions each account pays"


@_reg("layers_multi", MULTI_TOPIC)
def layers_multi(h, t, base):
    mu = t.get("cl_multi")
    if not mu:
        return _no(MULTI_TOPIC)
    lab = _labels(t)
    groups = ["all"] + _main(t, _lens(h))
    pv = {(r["group"], r["institutions"]): r["pct"] for r in mu}
    two = pv.get(("all", "2"), 0) + pv.get(("all", "3+"), 0)
    s, top = _slide(h, f"{two:.1f}% of {_own(t)} pay two or more banks or credit unions", "Share of each group's transacting accounts paying 1, 2 or 3+ distinct institutions over 12 months",
                    MULTI_TOPIC)
    path = h["chart"]("layers_multi", CLY.columns, ["All accounts" if g == "all" else lab[g] for g in groups],
                      {"Pays 1": [pv.get((g, "1"), 0) for g in groups], "Pays 2": [pv.get((g, "2"), 0) for g in groups], "Pays 3+": [pv.get((g, "3+"), 0) for g in groups]},
                      colors={"Pays 1": CLY.GOLD, "Pays 2": CLY.ORANGE, "Pays 3+": CLY.NAVY}, stacked=True, fmt="{:.1f}", ylabel="% of the group's accounts")
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


RECENCY_TOPIC = "How recently each relationship was paid"


@_reg("layers_recency", RECENCY_TOPIC)
def layers_recency(h, t, base):
    rc = [r for r in t.get("cl_recency") or [] if r["relationships"] >= 5]
    if not rc:
        return _no(RECENCY_TOPIC)
    bands = [k for k in rc[0] if k not in ("tier", "relationships")]
    tot = sum(r["relationships"] for r in rc)
    live = sum(r[bands[0]] for r in rc) / tot
    s, top = _slide(h, f"{live:.0%} of competitor relationships were paid in the last 30 days", "Relationships by when the account last paid the institution; dormant means 180 days or more quiet",
                    RECENCY_TOPIC)
    path = h["chart"]("layers_recency", CLY.columns, [r["tier"].replace(" (", "\n(") for r in rc[:7]], {b: [r[b] for r in rc[:7]] for b in bands},
                      colors=dict(zip(bands, [CLY.GREEN, CLY.GOLD, CLY.STEEL, CLY.LINE])), stacked=True, ylabel="relationships")
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


DIST_TOPIC = "Distance from a client branch"


@_reg("layers_distance", DIST_TOPIC)
def layers_distance(h, t, base):
    d = t.get("cl_distance")
    if not d:
        return _no(DIST_TOPIC)
    tot = sum(r["dollars"] for r in d) or 1
    far = sum(r["dollars"] for r in d if r["band"] == "no branch near") / tot
    s, top = _slide(h, f"{far:.0%} of competitor dollars go to institutions with no branch near a client branch",
                    "Dollars a year (in $M) by the distance of the institution's nearest branch to any client branch; online-only names and institutions beyond the scan radius are in the last bar",
                    DIST_TOPIC)
    path = h["chart"]("layers_distance", CLY.columns, [r["band"] for r in d], {"$M a year": [r["dollars"] / 1e6 for r in d]}, colors={"$M a year": CLY.ORANGE}, fmt="{:.2f}", ylabel="$M a year")
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


ATTR_TOPIC = "Competition and attrition"


@_reg("layers_attrition", ATTR_TOPIC)
def layers_attrition(h, t, base):
    at = t.get("cl_attrition")
    if not at:
        return _no(ATTR_TOPIC, "the ODD has no closure dates")
    a = next((r for r in at if r["exposed_to"].startswith("ANY")), None)
    rows = sorted((r for r in at if not r["exposed_to"].startswith("ANY") and r["exposed"] >= 100 and r["relative_risk"] is not None), key=lambda r: -r["relative_risk"])
    if not a or a["relative_risk"] is None:
        return _no(ATTR_TOPIC, "no account closed in the second half of the window")
    s, top = _slide(h, f"Accounts that paid a competitor closed at {a['closure_pct']}% against {a['unexposed_closure_pct']}% for those that did not",
                    "Cohort: accounts active in the first half of the window. Exposed = paid that tier in the first half; outcome = closed in the second half. Bars: relative risk of closing (1.0 = no difference)",
                    ATTR_TOPIC)
    right = h["rail"](s, [("Paid a competitor", f"{a['exposed']:,}", f"{a['closed']:,} closed after"), ("Did not", f"{a['unexposed']:,}", f"{a['unexposed_closure_pct']}% closed"),
                          ("Relative risk", f"{a['relative_risk']}", "an association, not proof")], top=top)
    if rows:
        path = h["chart"]("layers_attrition", CLY.hbar, [[r["exposed_to"], r["relative_risk"], r["exposed_to"]] for r in rows],
                          xlabel="relative risk of closing", fmt="{:.2f}")
        if path:
            h["chart_left"](s, path, top, right)


BRANCH_TOPIC = "Branches: competitor share against closure"


@_reg("layers_branches", BRANCH_TOPIC)
def layers_branches(h, t, base):
    br = t.get("cl_branches")
    if not br or len(br) < 3:
        return _no(BRANCH_TOPIC, "the ODD has no branch or closure columns, or fewer than three branches have 50 accounts")
    top_b = max(br, key=lambda r: (r["any_pct"], r["closure_pct"]))
    s, top = _slide(h, f"Branch {top_b['branch']} pairs a {top_b['any_pct']}% competitor share with a {top_b['closure_pct']}% closure rate",
                    "Each bubble is an ODD branch with 50 or more transacting accounts (size = accounts): across = share paying a bank or credit union, up = share closed in 12 months",
                    BRANCH_TOPIC)
    path = h["chart"]("layers_branches", CLY.bubble, [[r["branch"], r["any_pct"], r["closure_pct"], r["accounts"]] for r in br], xlabel="% of the branch's accounts paying a bank or credit union",
                      ylabel="% of the branch's accounts closed in 12 months", label_top=len(br))
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


WIN_TOPIC = "Winback counts"


@_reg("layers_winback", WIN_TOPIC)
def layers_winback(h, t, base):
    wb = t.get("cl_winback")
    main = _main(t, _lens(h))
    if not wb:
        return _no(WIN_TOPIC, "no heavy relationship at a local, regional or state institution is still live")
    lab = _labels(t)
    w = wb[:10]
    s, top = _slide(h, f"Winback: {w[0]['inst']} has {w[0]['heavy_live']:,} heavy accounts still live; the next {len(w) - 1} add {sum(r['heavy_live'] for r in w[1:]):,}",
                    "Heavy = the institution takes 20% or more of the account's card dollars; live = paid in the last 30 days. Local, regional and state institutions. Counts only: no account list",
                    WIN_TOPIC)
    path = h["chart"]("layers_winback", CLY.hbar_stacked, [r["inst"] for r in w], {lab[g]: [r["by_group"].get(g, 0) for r in w] for g in main},
                      colors={lab[g]: CLY.GROUP_COLOR.get(g, CLY.STEEL) for g in main}, full=True)
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


REVIEW_TOPIC = "Coverage and the unplaced text"


@_reg("layers_review", REVIEW_TOPIC)
def layers_review(h, t, base):
    cov = t.get("cl_coverage")
    if not cov or cov.get("pct") is None:
        return _no(REVIEW_TOPIC)
    q = (t.get("cl_review_queue") or [])[:10]
    s, top = _slide(h, f"{cov['pct']:.1f}% of bank-like card dollars are placed; the unplaced {money(cov['review_dollars'])} is listed, not dropped",
                    f"The ten largest unplaced strings of {cov.get('review_names', len(q)):,}: where aliases and new institutions are fixed. {money(cov['ambiguous_dollars'])} of placed dollars sit in ambiguous names",
                    REVIEW_TOPIC)
    right = h["rail"](s, [("Placed", money(cov["placed_dollars"]), "in a tier"), ("Unplaced", money(cov["review_dollars"]), "bank-like, no match"), ("Ambiguous", money(cov["ambiguous_dollars"]), "fits several institutions")], top=top)
    if q:
        path = h["chart"]("layers_review", CLY.hbar, [[str(r[0])[:30], r[3] / 1000.0, CLY.ORANGE] for r in q], xlabel="$K a year", fmt="${:,.1f}K")
        if path:
            h["chart_left"](s, path, top, right)


ACTION_TOPIC = "Action register"


@_reg("layers_actions", ACTION_TOPIC)
def layers_actions(h, t, base):
    if not _have(t):
        return _no(ACTION_TOPIC)
    own = _own(t)
    loc = sorted(_insts(t, CL.LOCAL), key=lambda r: -r["accounts"])[:3]
    heavy_loc = sum(r["heavy_live"] for r in t.get("cl_winback") or [] if r["inst"] in {x["inst"] for x in loc})
    reg = sum(1 for r in _insts(t, CL.REGIONAL) if r["accounts"] >= 100)
    nat = len(_insts(t, CL.NATIONAL))
    dig = sum(r["accounts"] for r in _insts(t, CL.DIGITAL))
    cov = t.get("cl_coverage") or {}
    rows = [["Tier", "Action", "Owner", "Metric", "Today"]]
    if loc:
        rows.append(["Local", f"Winback outreach to {own} at {', '.join(r['inst'] for r in loc)}", "Client marketing", "Heavy accounts still live", f"{heavy_loc:,}"])
    rows.append(["Local", "Branch plays where competitor share and closure both run high", "Branch managers", "Branch slide, top right", "see branch slide"])
    if reg:
        rows.append(["Regional", "Review district institutions with 100 or more accounts", "CSM", "Institutions over 100 accounts", f"{reg:,}"])
    if nat:
        rows.append(["National", "Check each name's card text, then position auto and card products against it", "CSM", "Names to check", f"{nat:,}"])
    if dig:
        rows.append(["Digital", "Primary-account offers for digital-bank users (direct deposit)", "Client marketing", "Accounts at digital names", f"{dig:,}"])
    rows.append(["Trust", "Fix alias gaps; decide on card-issuing banks and ambiguous names", "CSM", "Unplaced dollars", money(cov.get("review_dollars", 0))])
    if len(rows) < 3:
        return _no(ACTION_TOPIC, "too few actions to list")
    s, top = _slide(h, "Action register: each tier gets an action, an owner, a metric and today's value", "Every row's figure is computed from this client's files; none is a standard", ACTION_TOPIC)
    shape = h["table"](s, rows, 0.6, top + 0.05, 12.1, [1.3, 5.6, 1.7, 2.4, 1.1], 11)
    _left_text(shape, (1, 2, 3))


# ------------------------------------------------------------------------------------- month over month
CHANGE_TOPIC, CHANGE_INST_TOPIC, TRIG_TOPIC = "This month's changes", "Who moved this month", "Triggers this month"


def _since(c):
    return c.get("prior_period") or "the prior month"


@_reg("layers_changes", CHANGE_TOPIC)
def layers_changes(h, t, base):
    c = t.get("cl_changes")
    if not c or not c.get("tiers"):
        return _no(CHANGE_TOPIC, "no prior month's pack was given, or it has no layered figures")
    big = c["tiers"][0]
    n = len(c.get("triggers") or [])
    rows = [r for r in c["tiers"] if r["change_points"]][:8]
    s, top = _slide(h, f"{big['tier']} moved {big['change_points']:+.2f} points since {_since(c)}; {n} trigger{'s' if n != 1 else ''} fired",
                    "Change in each tier's share of accounts, in points. The two 12-month windows overlap by eleven months: a change is what the newest month added and the oldest dropped",
                    CHANGE_TOPIC)
    cov = c.get("coverage") or {}
    items = [("Triggers fired", f"{n:,}", "see the triggers slide")]
    if cov.get("now") is not None and cov.get("prior") is not None:
        items.append(("Coverage", f"{cov['now']:.1f}%", f"{cov['prior']:.1f}% a month ago"))
    items.append(("New institutions", f"{sum(1 for r in c['institutions'] if r['status'] == 'new this month'):,}", "not seen last month"))
    items.append(("Not seen now", f"{sum(1 for r in c['institutions'] if r['status'] == 'not seen this month'):,}", "seen last month"))
    right = h["rail"](s, items, top=top)
    if rows:
        path = h["chart"]("layers_changes", CLY.hbar, [[r["tier"], r["change_points"], r["tier"]] for r in rows], xlabel="points", fmt="{:+.2f}")
        if path:
            h["chart_left"](s, path, top, right)


@_reg("layers_changes_institutions", CHANGE_INST_TOPIC)
def layers_changes_institutions(h, t, base):
    c = t.get("cl_changes")
    movers = [r for r in (c or {}).get("institutions") or [] if r["change"]][:10]
    if not movers:
        return _no(CHANGE_INST_TOPIC, "no institution changed since the prior month, or no prior pack was given")
    up = max(movers, key=lambda r: r["change"])
    s, top = _slide(h, f"{up['inst']} added {up['change']:,} accounts since {_since(c)}" if up["change"] > 0 else f"Accounts paying {up['inst']} changed by {up['change']:,} since {_since(c)}",
                    "The ten biggest changes in the number of accounts paying an institution (green = more, orange = fewer); an institution seen for the first time or no longer seen is named in its row",
                    CHANGE_INST_TOPIC)
    rows = []
    for r in movers:
        tag = " (new)" if r["status"] == "new this month" else " (not seen)" if r["status"] == "not seen this month" else ""
        rows.append([r["inst"][:26] + tag, r["change"], CLY.GREEN if r["change"] > 0 else CLY.ORANGE])
    path = h["chart"]("layers_changes_institutions", CLY.hbar, rows, xlabel="change in accounts", fmt="{:+,.0f}", full=True)
    if path:
        h["picture"](s, path, top=top, max_h=4.9)


@_reg("layers_triggers", TRIG_TOPIC)
def layers_triggers(h, t, base):
    c = t.get("cl_changes")
    trig = (c or {}).get("triggers") or []
    if not trig:
        return _no(TRIG_TOPIC, "nothing crossed a threshold this month, or no prior pack was given")
    th = (t.get("cl_scope") or {}).get("thresholds") or {}
    s, top = _slide(h, f"{len(trig)} thing{'s' if len(trig) != 1 else ''} crossed a threshold since {_since(c)}",
                    f"Thresholds: a new institution over {th.get('trigger_new_accounts', 50):g} accounts, a tier share moving {th.get('trigger_share_points', 0.3):g} points, coverage under {th.get('coverage_floor', 95):g}%",
                    TRIG_TOPIC)
    rows = [["Trigger", "Subject", "Detail"]] + [[r["trigger"], r["subject"][:40], r["detail"]] for r in trig[:12]]
    shape = h["table"](s, rows, 0.6, top + 0.05, 12.1, [3.6, 3.4, 5.1], 12)
    _left_text(shape, (1, 2))
