"""
The Attrition chapter: where and when accounts close, how much warning the data gives, which
accounts carry several stresses at once, and how long accounts stay open.

Figures: v5's retention, lifecycle, attrition, stressors and profile sections
(`ti/odd_sections.py`). Slides, in v5's order: attrition by branch, the five attrition-module
slides, attrition by group, survival by tenure, then the two slides that read the transaction file
(competitor spend before closure, stresses across both files), which come with the transaction
chapter's port and are stated until it is in the build. The "by group" slide splits by lens group;
the rest describe the whole book, so they read the same in both lens decks.
"""
from pathlib import Path

from ti import cut, odd_sections

TITLES = {
    "attrition_branch": "Attrition by branch",
    "months_of_warning": "How much warning do we get",
    "concurrent_stressors": "Accounts under several stresses",
    "cohort_survival": "New accounts, cohort by cohort",
    "product_and_hazard": "Where closures cluster",
    "where_the_risk_sits": "Where the risk sits",
    "attrition_by_group": "Attrition by group",
    "survival_by_tenure": "Account retention — survival by tenure",
    "spend_before_closure": "Competitor spend before closure",
    "stresses_across_files": "Stresses across both files",
}
TXN_TITLES = ("spend_before_closure", "stresses_across_files")


def compute(ctx):
    out = {}
    for section in (odd_sections.retention, odd_sections.lifecycle, odd_sections.attrition,
                    odd_sections.stressors, odd_sections.profile):
        out.update(section(ctx))
    return out


def stats(pack, _lens):
    m = pack.get("metrics") or {}
    out = []
    if m.get("attrition_rate") is not None:
        out.append((f"{m['attrition_rate']}%", "of the book closed in 12 months"))
    if m.get("stress_2plus_n"):
        out.append((f"{m['stress_2plus_n']:,}", "accounts under two or more stresses"))
    return out


def _txn_builders():
    """The two transaction-file slides, from the transaction chapter's port
    (`ti/chapters_txn.ATTRITION_BUILDERS`, v5's txn_attrition builders) once it is in the build."""
    try:
        from ti import chapters_txn
        found = {getattr(b, "__name__", ""): b for b in chapters_txn.ATTRITION_BUILDERS}
    except (ImportError, AttributeError):
        found = {}
    out = []
    for name in TXN_TITLES:
        fn = found.get(name)
        if fn is None:
            out.append(lambda h, m: "it reads the transaction file, which is not in this build")
        else:
            out.append(lambda h, m, _fn=fn: _fn(h, m, m.get("fin_base_label", "accounts")))
    return out


def build(ctx):
    from ti.deck import attrition_inline as I
    from ti.deck import attrition_slides as A
    from ti.deck.helpers import Deck
    deck = Deck(ctx, "the ODD extract (and, for the last two slides, the transaction files)",
                Path(ctx.art_dir or ".") / "charts" / "attrition")
    builders = [I.attrition_branch, A.months_of_warning, A.concurrent_stressors,
                A.cohort_survival, A.product_and_hazard, A.where_the_risk_sits,
                I.attrition_by_group, I.survival_by_tenure]
    txn = _txn_builders()
    for name, fn in zip(TXN_TITLES, txn):
        fn.__name__ = name
    return deck.run(builders + txn, TITLES, ctx.pack.get("metrics") or {})


CHAPTER = cut.Chapter("TI_ATT", "Attrition", "Closures · Warning · Stresses",
                      "Where and when accounts close, and the warning signs", stats, build, compute)
