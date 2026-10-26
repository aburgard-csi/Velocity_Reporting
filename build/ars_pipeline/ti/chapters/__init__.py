"""
The chapters of the Transaction Intelligence cut, one module each, in deck order. `ti.cut.CHAPTERS`
is `ALL`, read on first use. The transaction chapters (`transaction_intelligence.py`,
`competition.py`) are thin modules over `ti/chapters_txn.py`; the ODD chapters (`attrition.py`,
`deposits.py`, `ics.py`) compute and draw on their own.
"""
from ti.chapters import attrition, competition, deposits, ics, transaction_intelligence

ALL = (transaction_intelligence.CHAPTER, competition.CHAPTER, attrition.CHAPTER, deposits.CHAPTER,
       ics.CHAPTER)
