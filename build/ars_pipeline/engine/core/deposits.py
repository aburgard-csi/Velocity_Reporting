"""The rolling-365 deposits file is NOT ported in this branch (2026-09-18).

v5's `core/deposits` loads a per-account deposit file that no client sends through the
CSM_Reporting pipeline yet. Two ported sections quote its match-rate floor to say whether a
deposit figure is presentable; the floor is kept here so they read as "not built" rather
than failing to import. When the deposits file is ported, this module becomes the package.
"""
MIN_MATCH_PCT = 50.0
