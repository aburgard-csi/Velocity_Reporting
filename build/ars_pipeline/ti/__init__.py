"""
ti — the Transaction Intelligence cut: transaction intelligence, competition, attrition and
deposits, migrated one analysis at a time from James Gilmore's ARS v5 engine.

It is a SEPARATE deck, built by `build/ars_pipeline/build_ti_gen.py`, in two lenses: ARS
(responders, mailed non-responders, not mailed) and ICS (ICS accounts by source). Nothing
here edits or replaces an existing ARS slide, metric or template: where a migrated analysis
overlaps one already in the ARS deck, both are kept and the overlap is recorded for a later
decision. Opt-in until that decision is made.

  cut.py    what the cut is: its lenses, its chapters (in deck order), its file name
  frame.py  the slide frame every chapter draws on (title, selection, pill, logo, number,
            and a source note it refuses to leave out)

Import-safe: nothing in this package reads sys.argv or the share at import.
"""
