"""Tim Barrett's ILS Matrix Validation Deck Builder, copied unchanged (README.md is his).

`matrix_report.parse(path)` reads a matrix validation export into {section: {columns, rows}};
`matrix_deck`'s data functions (`detect_types`, `overrides_by_type`, `range_grid`, `trend_structure`,
`tier_summary`, ...) are what the pre-go-live deck's matrix chapter draws from, in Sheila's look. The one
edit is the import line: `from .matrix_report import parse`, so the package imports from build/.
"""
