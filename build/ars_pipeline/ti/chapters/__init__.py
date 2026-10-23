"""
The chapters of the Transaction Intelligence cut, in deck order (`ti.cut.CHAPTERS` is this tuple).

Each chapter module exposes `CHAPTER`, a `ti.cut.Chapter`: its figures (`compute`, run once per
client on the shared context) and its slides (`build`, run once per lens deck). Chapters land one
pull request at a time; the order here is the deck's: transaction intelligence, competition,
attrition, deposits, ICS accounts.
"""
from ti.chapters import attrition, competition, deposits, transaction_intelligence

ALL = (transaction_intelligence.CHAPTER, competition.CHAPTER, attrition.CHAPTER, deposits.CHAPTER)
