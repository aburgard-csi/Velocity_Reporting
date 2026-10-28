# Ported from v5 02-Scripts/deckkit/__init__.py at 7ba1e63. Logic unchanged; ars.deck.{build,charts,labels} are this package's own subsets of them, and the chart-form imports and the CHART_FORMS / __all__ lists are left out (PGL draws none of the forms).
"""Product-neutral deck surface.

Every product's deck builder imports its slide helpers and styling from
here, never from another product's namespace. Today the implementations
live in ars/deck (the first deck built); this facade is the contract --
when a second product's needs diverge, the code moves here and ars.deck
imports back, with no caller changing.

    from deckkit import (NAVY, ORANGE, GREY, money, clean_axes, save_chart,
                         text, title, headed, divider, rail, chart_left,
                         kpi, picture, table, strip_placeholders)
"""
from .build import HEAD_FONT, LAYOUT_BLANK  # noqa: F401
from .build import GREY as SLIDE_GREY  # noqa: F401
from .build import RED_D as SLIDE_RED  # noqa: F401
from .build import NAVY as SLIDE_NAVY  # noqa: F401
from .build import ORANGE as SLIDE_ORANGE  # noqa: F401
from .charts import GREY, NAVY, ORANGE  # noqa: F401
# The two content bands, as the canvas that fills them. A product picking a
# slot for a form names these rather than inventing a figsize.
from .charts import FIG_W_RAIL, FIG_H_RAIL  # noqa: F401
from .charts import FIG_W_FULL, FIG_H_FULL  # noqa: F401

# NAVY/ORANGE/GREY are hex strings for matplotlib charts; SLIDE_* are the
# pptx RGBColor twins for text/rail/kpi. Same brand, two color systems.
from .charts import _clean as clean_axes  # noqa: F401
from .charts import _save as save_chart  # noqa: F401
from .build import _chart_left as chart_left  # noqa: F401
from .build import _divider as divider  # noqa: F401
from .build import _headed as headed  # noqa: F401
from .build import _kpi as kpi  # noqa: F401
from .labels import money  # noqa: F401
from .build import _kicker as kicker  # noqa: F401
from .build import _picture as picture  # noqa: F401
from .build import _rail as rail  # noqa: F401
from .build import _rule as rule  # noqa: F401
# THE GRID. A product laying out a slide reads these rather than repeating
# the numbers -- ils/kickoff_analysis/deck/slides.py was importing them from
# ars.deck.build directly, which is the one thing this facade exists to stop.
from .build import CONTENT_W, MARGIN_L, RIGHT_EDGE  # noqa: F401
from .build import RAIL_BOTTOM, RAIL_GUTTER, RAIL_LEFT  # noqa: F401
from .build import SLIDE_H, SLIDE_W  # noqa: F401
from .build import _strip_placeholders as strip_placeholders  # noqa: F401
from .build import _table as table  # noqa: F401
from .build import _text as text  # noqa: F401
from .build import _title as title  # noqa: F401



def open_template(template):
    """Presentation from the shared template with the demo slides detached;
    returns (prs, new) where new() adds a stripped blank-layout slide."""
    from pptx import Presentation
    prs = Presentation(str(template))
    xml_slides = prs.slides._sldIdLst
    rel_id = ("{http://schemas.openxmlformats.org/officeDocument/2006/"
              "relationships}id")
    for sld in list(xml_slides):
        prs.part.drop_rel(sld.get(rel_id))
        xml_slides.remove(sld)

    def new(layout=LAYOUT_BLANK):
        slide = prs.slides.add_slide(prs.slide_layouts[layout])
        strip_placeholders(slide)
        return slide

    return prs, new
