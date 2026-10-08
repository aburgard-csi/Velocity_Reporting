"""Random cell access over an openpyxl read-only workbook, without the rescans.

`ws.cell(r, c)` on a read-only worksheet streams the sheet's XML from the top to reach row r, every
call. The ARS extractors read a workbook cell by cell (label searches, header rows, the Mail Response
loop), so a 10 MB workbook was parsed again and again: 2.7 million cells and ~19 s for a client whose
figures sit in a few hundred cells (profiled 2026-10-08, 1038 Sugar River).

`load()` returns the workbook with each sheet read ONCE, on first use, into a list of rows. Everything
the extractors use is kept: `wb[name]`, `wb.sheetnames`, `ws.cell(r, c).value`, `ws.max_row`,
`ws.max_column` and `ws.iter_rows(values_only=True)`. A cell outside the sheet reads as None, as before.
Import-safe; the work happens in `load()`.
"""
import openpyxl


class _Cell:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class Sheet:
    def __init__(self, ws):
        self._ws = ws
        self._rows = None

    def _load(self):
        if self._rows is None:
            self._rows = [tuple(r) for r in self._ws.iter_rows(values_only=True)]
        return self._rows

    @property
    def max_row(self):
        return self._ws.max_row

    @property
    def max_column(self):
        return self._ws.max_column

    def cell(self, row, column):
        rows = self._load()
        if 1 <= row <= len(rows):
            r = rows[row - 1]
            if 1 <= column <= len(r):
                return _Cell(r[column - 1])
        return _Cell(None)

    def iter_rows(self, values_only=True, **kw):
        if not values_only or kw:
            return self._ws.iter_rows(values_only=values_only, **kw)
        return iter(self._load())


class Workbook:
    def __init__(self, wb):
        self._wb = wb
        self._sheets = {}

    @property
    def sheetnames(self):
        return self._wb.sheetnames

    def __getitem__(self, name):
        if name not in self._sheets:
            self._sheets[name] = Sheet(self._wb[name])
        return self._sheets[name]

    def __contains__(self, name):
        return name in self._wb.sheetnames

    def close(self):
        self._wb.close()


def load(path):
    """The workbook at `path`, read-only, values not formulas, with cached cell access."""
    return Workbook(openpyxl.load_workbook(path, read_only=True, data_only=True))
