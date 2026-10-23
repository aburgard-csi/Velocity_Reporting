# Ported from ARS v5 02-Scripts/core/market/sources.py at a491b5c (James Gilmore); logic unchanged.
"""Regulator reference data: every US bank and credit union branch.

Three public sources, cached on disk so a rebuild is offline and a refresh
is deliberate:

    FDIC BankFind      banks + branches, with latitude/longitude and website
    NCUA quarterly     credit unions + branches, by ZIP (no coordinates)
    Census gazetteer   ZIP -> centroid, which supplies the CU coordinates

ZIP-centroid accuracy (a few miles) is immaterial against the 25-50 mile
radius this data exists to serve.

Nothing here reaches the network unless the cache is missing or --refresh
was passed: the vintage recorded in _sources.json is what a rebuild uses,
so two rebuilds of the same vintage produce identical output.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

FDIC_BASE = "https://api.fdic.gov/banks"
FDIC_PAGE = 10_000
NCUA_URL = ("https://ncua.gov/files/publications/analysis/"
            "call-report-data-{quarter}.zip")
GAZETTEER_URL = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
                 "{year}_Gazetteer/{year}_Gaz_zcta_national.zip")

DEFAULT_NCUA_QUARTER = "2026-03"
DEFAULT_GAZETTEER_YEAR = "2024"

# A source that returns far fewer rows than this has changed shape or been
# truncated upstream; better to stop than to scan against a partial book.
MIN_ROWS = {"fdic_institutions": 3_000, "fdic_locations": 60_000,
            "fdic_financials": 15_000,
            "ncua_institutions": 3_000, "ncua_branches": 15_000,
            "ncua_financials": 3_000, "zip_centroids": 25_000}

_TIMEOUT = 120


class SourceError(RuntimeError):
    """A source was unreachable, or came back too small to trust."""


def _fetch(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
            return resp.read()
    except Exception as exc:
        raise SourceError(f"could not fetch {url}: {exc}") from exc


def _cached(cache: Path, name: str, refresh: bool, build) -> list[dict]:
    """Read name.json from cache, or build() it and write it there."""
    path = cache / f"{name}.json"
    if path.exists() and not refresh:
        rows = json.loads(path.read_text(encoding="utf-8"))
    else:
        rows = build()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows), encoding="utf-8")

    floor = MIN_ROWS.get(name)
    if floor and len(rows) < floor:
        raise SourceError(
            f"{name}: {len(rows):,} rows, expected at least {floor:,}. "
            f"The source changed shape or the download was truncated. "
            f"Delete {path} and re-run with --refresh."
        )
    return rows


# ---------------------------------------------------------------------------
# FDIC
# ---------------------------------------------------------------------------

def _fdic_pages(endpoint: str, fields: str, filters: str = "") -> list[dict]:
    """Every row of an FDIC endpoint, paged at FDIC_PAGE."""
    rows: list[dict] = []
    offset = 0
    while True:
        url = (f"{FDIC_BASE}/{endpoint}?fields={fields}&limit={FDIC_PAGE}"
               f"&offset={offset}&format=json")
        if filters:
            # A range filter carries spaces ("[20240101 TO *]"); urllib rejects a raw one.
            url += "&filters=" + urllib.parse.quote(filters, safe=":,*")
        payload = json.loads(_fetch(url))
        page = [r["data"] for r in payload.get("data", [])]
        rows.extend(page)
        total = payload.get("meta", {}).get("total", 0)
        offset += FDIC_PAGE
        if not page or offset >= total:
            return rows


def fdic_institutions(cache: Path, refresh: bool = False) -> list[dict]:
    """Active FDIC-insured institutions, with assets and website."""
    return _cached(cache, "fdic_institutions", refresh, lambda: _fdic_pages(
        "institutions",
        "NAME,CERT,CITY,STALP,ZIP,ASSET,WEBADDR,OFFICES,ACTIVE,REGAGNT,BKCLASS,CHRTAGNT",
        filters="ACTIVE:1",
    ))


def fdic_locations(cache: Path, refresh: bool = False) -> list[dict]:
    """Every bank branch, with coordinates.

    The locations endpoint rejects an ACTIVE filter, so the full table comes
    back and is narrowed to live certs by the caller.
    """
    return _cached(cache, "fdic_locations", refresh, lambda: _fdic_pages(
        "locations",
        "NAME,OFFNAME,ADDRESS,CITY,STALP,ZIP,COUNTY,LATITUDE,LONGITUDE,CERT",
    ))


FDIC_FINANCIAL_FIELDS = "CERT,REPDTE,ASSET,DEP,LNLSNET,ROA,EQV,NETINC"


def fdic_financials(cache: Path, refresh: bool = False,
                    since: str = "20240101") -> list[dict]:
    """Quarterly call-report figures per bank, from `since` (YYYYMMDD) forward.

    Five to nine quarters per CERT: enough for the latest quarter against the
    same quarter a year earlier, with slack for a late filer. Row floor 15,000
    is roughly 4,000 banks times four quarters.
    """
    return _cached(cache, "fdic_financials", refresh, lambda: _fdic_pages(
        "financials", FDIC_FINANCIAL_FIELDS, filters=f"REPDTE:[{since} TO *]"))


# ---------------------------------------------------------------------------
# NCUA
# ---------------------------------------------------------------------------

NCUA_FINANCIAL_FIELDS = ("CU_NUMBER", "CYCLE_DATE", "ACCT_010", "ACCT_018",
                         "ACCT_025B", "ACCT_997")
_NCUA_FILES = {"FOICU.txt": ("institutions", None),
               "Credit Union Branch Information.txt": ("branches", None),
               "TradeNames.txt": ("trade_names", None),
               "FS220.txt": ("financials", NCUA_FINANCIAL_FIELDS)}


def _read_ncua_zip(quarter: str) -> dict[str, list[dict]]:
    blob = _fetch(NCUA_URL.format(quarter=quarter))
    out: dict[str, list[dict]] = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = set(zf.namelist())
        for filename, (key, keep) in _NCUA_FILES.items():
            if filename not in names:
                raise SourceError(
                    f"NCUA {quarter} archive has no {filename!r}; "
                    f"it holds {sorted(names)}"
                )
            text = zf.read(filename).decode("latin-1")
            rows = csv.DictReader(io.StringIO(text))
            out[key] = ([{k: r.get(k) for k in keep} for r in rows] if keep
                        else list(rows))
    return out


def ncua(cache: Path, quarter: str = DEFAULT_NCUA_QUARTER,
         refresh: bool = False) -> dict[str, list[dict]]:
    """FOICU institutions, branch information and trade names."""
    parsed: dict[str, list[dict]] = {}

    def _pull(key):
        if not parsed:
            parsed.update(_read_ncua_zip(quarter))
        return parsed[key]

    return {
        "institutions": _cached(cache, "ncua_institutions", refresh,
                                lambda: _pull("institutions")),
        "branches": _cached(cache, "ncua_branches", refresh,
                            lambda: _pull("branches")),
        "trade_names": _cached(cache, "ncua_trade_names", refresh,
                               lambda: _pull("trade_names")),
        "financials": _cached(cache, "ncua_financials", refresh,
                              lambda: _pull("financials")),
    }


# ---------------------------------------------------------------------------
# Census ZIP centroids
# ---------------------------------------------------------------------------

def _read_gazetteer(year: str) -> list[dict]:
    blob = _fetch(GAZETTEER_URL.format(year=year))
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = next((n for n in zf.namelist() if n.lower().endswith(".txt")),
                    None)
        if name is None:
            raise SourceError(f"gazetteer {year} archive holds no .txt file")
        text = zf.read(name).decode("utf-8-sig")

    rows = []
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        clean = {k.strip(): (v.strip() if isinstance(v, str) else v)
                 for k, v in row.items() if k}
        zip_code = clean.get("GEOID")
        try:
            rows.append({"zip": str(zip_code).zfill(5),
                         "lat": float(clean["INTPTLAT"]),
                         "lon": float(clean["INTPTLONG"])})
        except (KeyError, TypeError, ValueError):
            continue
    return rows


def zip_centroids(cache: Path, year: str = DEFAULT_GAZETTEER_YEAR,
                  refresh: bool = False) -> dict[str, tuple[float, float]]:
    """ZIP code -> (lat, lon) centroid."""
    rows = _cached(cache, "zip_centroids", refresh,
                   lambda: _read_gazetteer(year))
    return {r["zip"]: (r["lat"], r["lon"]) for r in rows}


# ---------------------------------------------------------------------------
# Vintages
# ---------------------------------------------------------------------------

def vintages(cache: Path, quarter: str = DEFAULT_NCUA_QUARTER,
             year: str = DEFAULT_GAZETTEER_YEAR) -> dict:
    """What a rebuild from this cache is built on."""
    counts = {}
    for name in ("fdic_institutions", "fdic_locations", "fdic_financials",
                 "ncua_institutions", "ncua_branches", "ncua_trade_names",
                 "ncua_financials", "zip_centroids"):
        path = cache / f"{name}.json"
        if path.exists():
            counts[name] = len(json.loads(path.read_text(encoding="utf-8")))
    return {"ncua_quarter": quarter, "gazetteer_year": year,
            "cache": str(cache), "row_counts": counts}
