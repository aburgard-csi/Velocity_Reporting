"""
ILS Program Performance Review deck builder.

Adds ZAccounts / ZTrend analysis — branch deposit behaviour, ILS scoring
summary, deposit score output, and matrix validation — into the CSI house
template for an ILS client review.

Consolidates three earlier tools:
  * Matrix Deck Generator      (matrix validation slides)
  * Deposit Score Validation   (deposit score logic + output analysis)
  * deck_builder               (branch deposit-behaviour slides)

Public entry point:
    from ils_review import build_review, BuildConfig
"""
__version__ = "1.0.0"

from .config import BuildConfig, SECTIONS, DEFAULT_SECTIONS   # noqa: F401

__all__ = ["BuildConfig", "SECTIONS", "DEFAULT_SECTIONS", "build_review"]


def __getattr__(name):
    """Import the build pipeline (and with it pandas/matplotlib) only on use,
    so `import ils_review` stays cheap for the GUI's startup path."""
    if name == "build_review":
        from .build import build_review
        return build_review
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
