"""
The chapters of the Transaction Intelligence cut, one module each, in deck order. `ti.cut.CHAPTERS`
is `ALL`, read on first use. The transaction chapters (`transaction_intelligence.py`,
`competition.py`) are thin modules over `ti/chapters_txn.py`; the ODD chapters (`attrition.py`,
`deposits.py`, `ics.py`) compute and draw on their own; `economics.py` draws the workbook and
deferral-tracker figures `ti_build.compute_pack` reads before the chapters run; `value.py` computes
v5's dctr, rege, interchange and value sections and the leak post-passes, in v5's order.
"""
from ti.chapters import (attrition, campaign, competition, deposits, economics, ics,
                         transaction_intelligence, value)

ALL = (transaction_intelligence.CHAPTER, competition.CHAPTER, attrition.CHAPTER, deposits.CHAPTER,
       ics.CHAPTER, economics.CHAPTER, value.CHAPTER, campaign.CHAPTER)
