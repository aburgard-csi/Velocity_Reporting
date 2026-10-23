"""
The ODD-side chapters of the Transaction Intelligence cut, in deck order: Attrition, Deposits, ICS
accounts (one module each under `ti/chapters/`). `ti/chapters_txn.py` lists the transaction-side
chapters (Transaction Intelligence, Competition); `ti.cut.CHAPTERS` is the two lists in that order.
"""
from ti.chapters import attrition, deposits, ics

CHAPTERS = (attrition.CHAPTER, deposits.CHAPTER, ics.CHAPTER)
