# Ported from ARS v5 02-Scripts/core/market/__init__.py at a491b5c (James Gilmore); logic unchanged.
"""Client market intelligence: who a client is, and who competes with them.

    sources       regulator downloads, cached on disk
    institutions  FDIC + NCUA reconciled into one Institution/Branch book
    geo           distance and the radius query
    identity      name normalization, client matching, alias generation

Client facts (assets, DDA counts, products, CSM) come from Client-Master.xlsx
and stay authoritative; regulator figures here describe competitors.
"""

from .geo import BranchIndex, haversine
from .institutions import BANK, CREDIT_UNION, Book, Branch, Institution, load_book
from .sources import SourceError

__all__ = ["BranchIndex", "haversine", "Book", "Branch", "Institution",
           "load_book", "BANK", "CREDIT_UNION", "SourceError"]
