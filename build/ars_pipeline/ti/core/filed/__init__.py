# Ported from ARS v5 02-Scripts/core/filed/__init__.py at a491b5c (James Gilmore); logic unchanged.
"""Filed: what a competitor reports to its regulator.

One quarterly series per institution key (`fdic:{CERT}` or `ncua:{CU_NUMBER}`),
read from the cache that `core.market.sources` fills. Nothing here reaches the
network. Vocabulary: Spend is what members pay out, Book is the client's own
accounts, Inflows is money arriving at the client, Filed is this.
"""
from .growth import FiledGrowth, filed_growth
from .store import FiledStore, Quarter

__all__ = ["FiledStore", "Quarter", "FiledGrowth", "filed_growth"]
