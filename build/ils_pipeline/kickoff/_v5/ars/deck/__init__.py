# Ported from v5 02-Scripts/ars/deck/__init__.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
from .build import build, DeckResult
__all__ = ["build", "DeckResult"]
