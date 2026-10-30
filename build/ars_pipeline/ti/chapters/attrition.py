"""
The Attrition chapter: where and when accounts close, how much warning the data gives, which
accounts carry several stresses at once, and how long accounts stay open.

Figures: v5's retention, lifecycle, attrition, stressors and profile sections
(`ti/odd_sections.py`). Slides, in v5's order: attrition by branch and by group (one slide), the
five attrition-module slides, survival by tenure, then competitor spend before closure, which reads
the transaction file and comes with the transaction chapter's port. The group table splits by lens
group; the rest describe the whole book, so they read the same in both lens decks.

Two pairs of v5 slides are one slide each here (Sheila's 1798 review, 2026-10-30, combine groups I
and J): attrition by branch and by group (`attrition_inline.attrition_branch_and_group`), and
accounts under several stresses on the ODD alone and once the transaction file is counted
(`attrition_slides.concurrent_stressors`, both bases side by side). v5's separate slides are drawn
only when a client has just one half of a pair, so "Attrition by group" and "Stresses across both
files" stay "keep" in `ti/slides.json` for that case.
"""
from pathlib import Path

from ti import cut, odd_sections

TITLES = {
    "attrition_branch": "Attrition by branch",
    "attrition_branch_and_group": "Attrition by branch",
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
# Only the first of the transaction chapter's two attrition builders is drawn on its own: the
# stresses-across-both-files count is on the "Accounts under several stresses" slide beside the
# ODD-only count (combine group J).
TXN_TITLES = ("spend_before_closure",)


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
        # the ODD-only base, said so: the stress slide also shows the larger count once the
        # transaction file is counted (combine group J)
        out.append((f"{m['stress_2plus_n']:,}", "accounts under two or more ODD stresses"))
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
    deck = Deck(ctx, "the ODD extract (and, for competitor spend before closure and the "
                     "stresses counted with banking elsewhere, the transaction files)",
                Path(ctx.art_dir or ".") / "charts" / "attrition")
    builders = [I.attrition_branch_and_group, A.months_of_warning, A.concurrent_stressors,
                A.cohort_survival, A.product_and_hazard, A.where_the_risk_sits,
                I.survival_by_tenure]
    txn = _txn_builders()
    for name, fn in zip(TXN_TITLES, txn):
        fn.__name__ = name
    return deck.run(builders + txn, TITLES, ctx.pack.get("metrics") or {})


CHAPTER = cut.Chapter("TI_ATT", "Attrition", "Closures · Warning · Stresses",
                      "Where and when accounts close, and the warning signs", stats, build, compute)
