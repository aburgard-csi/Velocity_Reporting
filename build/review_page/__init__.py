"""review_page — an Executive Review presented from a web page (prototype, Aaron 2026-11-02).

The page is a VIEW of the same data pack the deck builders write, never a second computation:
`build/review_page/programs/<program>.py` reads the pack a build left in
`Build Artifacts/launcher/<period>/<id>/` (and, for ICS / MRPC / CashPlease, the sheets the deck
builders read) and returns a plain JSON view model; `static/` draws it in the browser; and
`scripts/live_review.py` serves it on 127.0.0.1 with the same token and Host checks as CSM Sheila.

Import-safe: nothing here reads the share or starts a server at import.
"""
