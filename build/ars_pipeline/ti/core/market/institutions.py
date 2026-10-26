# Ported from ARS v5 02-Scripts/core/market/institutions.py at a491b5c (James Gilmore); logic unchanged.
"""One book of every US depository, from two regulators that disagree.

FDIC and NCUA publish different shapes: FDIC gives branch coordinates and a
website but reports assets in thousands; NCUA gives neither coordinates nor
a website, reports assets in dollars, and keeps trade names in a separate
file. This module reconciles them into one Institution/Branch model so the
radius scan never has to care which regulator a competitor answers to.

Institution keys are regulator-scoped and stable: "fdic:12854",
"ncua:1234". They are what a client's market file records, so a roster can
be re-resolved after a name change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import sources
from .geo import BranchIndex

BANK = "Bank"
CREDIT_UNION = "Credit Union"


@dataclass(frozen=True, slots=True)
class Branch:
    inst_key: str
    inst_name: str
    fi_type: str
    name: str
    city: str
    state: str
    zip_code: str
    lat: float
    lon: float
    coord_source: str          # "exact" (FDIC) | "zip" (centroid)


@dataclass(slots=True)
class Institution:
    key: str
    name: str
    fi_type: str
    city: str
    state: str
    zip_code: str
    assets_thousands: int | None
    website: str | None
    trade_names: tuple[str, ...] = ()
    branches: list[Branch] = field(default_factory=list)

    @property
    def branch_count(self) -> int:
        return len(self.branches)


@dataclass(slots=True)
class Book:
    institutions: dict[str, Institution]
    branches: list[Branch]
    index: BranchIndex
    unplaced: list[dict]       # branches no coordinate could be found for

    def by_key(self, key: str) -> Institution | None:
        return self.institutions.get(key)


def _num(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _zip5(value) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits[:5].zfill(5) if digits else ""


def _clean_url(value) -> str | None:
    url = str(value or "").strip()
    if not url:
        return None
    return url if url.startswith(("http://", "https://")) else f"https://{url}"


# ---------------------------------------------------------------------------
# FDIC
# ---------------------------------------------------------------------------

def _fdic(cache, refresh, centroids, unplaced) -> dict[str, Institution]:
    insts = {}
    for row in sources.fdic_institutions(cache, refresh):
        cert = _num(row.get("CERT"))
        if cert is None:
            continue
        insts[f"fdic:{cert}"] = Institution(
            key=f"fdic:{cert}",
            name=str(row.get("NAME") or "").strip(),
            fi_type=BANK,
            city=str(row.get("CITY") or "").strip(),
            state=str(row.get("STALP") or "").strip(),
            zip_code=_zip5(row.get("ZIP")),
            assets_thousands=_num(row.get("ASSET")),
            website=_clean_url(row.get("WEBADDR")),
        )

    for row in sources.fdic_locations(cache, refresh):
        cert = _num(row.get("CERT"))
        inst = insts.get(f"fdic:{cert}")
        if inst is None:          # inactive or merged since the last index
            continue
        zip_code = _zip5(row.get("ZIP"))
        lat, lon = row.get("LATITUDE"), row.get("LONGITUDE")
        source = "exact"
        if lat is None or lon is None:
            lat, lon = centroids.get(zip_code, (None, None))
            source = "zip"
        if lat is None or lon is None:
            unplaced.append({"inst": inst.name, "zip": zip_code,
                             "reason": "no coordinate and no ZIP centroid"})
            continue
        inst.branches.append(Branch(
            inst_key=inst.key, inst_name=inst.name, fi_type=BANK,
            name=str(row.get("OFFNAME") or "").strip(),
            city=str(row.get("CITY") or "").strip(),
            state=str(row.get("STALP") or "").strip(),
            zip_code=zip_code, lat=float(lat), lon=float(lon),
            coord_source=source,
        ))
    return insts


# ---------------------------------------------------------------------------
# NCUA
# ---------------------------------------------------------------------------

def _ncua(cache, refresh, centroids, unplaced, quarter) -> dict[str, Institution]:
    data = sources.ncua(cache, quarter, refresh)

    assets = {}
    for row in data["financials"]:
        cu = _num(row.get("CU_NUMBER"))
        dollars = _num(row.get("ACCT_010"))
        if cu is not None and dollars is not None:
            assets[cu] = dollars // 1000          # dollars -> thousands

    names: dict[int, list[str]] = {}
    for row in data["trade_names"]:
        cu = _num(row.get("CU_NUMBER"))
        trade = str(row.get("TradeName") or "").strip()
        if cu is not None and trade:
            names.setdefault(cu, []).append(trade)

    insts = {}
    for row in data["institutions"]:
        cu = _num(row.get("CU_NUMBER"))
        if cu is None:
            continue
        insts[f"ncua:{cu}"] = Institution(
            key=f"ncua:{cu}",
            name=str(row.get("CU_NAME") or "").strip(),
            fi_type=CREDIT_UNION,
            city=str(row.get("CITY") or "").strip(),
            state=str(row.get("STATE") or "").strip(),
            zip_code=_zip5(row.get("ZIP_CODE")),
            assets_thousands=assets.get(cu),
            website=None,                          # NCUA publishes none
            trade_names=tuple(sorted(set(names.get(cu, ())))),
        )

    for row in data["branches"]:
        cu = _num(row.get("CU_NUMBER"))
        inst = insts.get(f"ncua:{cu}")
        if inst is None:
            continue
        zip_code = _zip5(row.get("PhysicalAddressPostalCode"))
        lat, lon = centroids.get(zip_code, (None, None))
        if lat is None:
            unplaced.append({"inst": inst.name, "zip": zip_code,
                             "reason": "ZIP not in gazetteer"})
            continue
        inst.branches.append(Branch(
            inst_key=inst.key, inst_name=inst.name, fi_type=CREDIT_UNION,
            name=str(row.get("SiteName") or "").strip(),
            city=str(row.get("PhysicalAddressCity") or "").strip(),
            state=str(row.get("PhysicalAddressStateCode") or "").strip(),
            zip_code=zip_code, lat=float(lat), lon=float(lon),
            coord_source="zip",
        ))
    return insts


# ---------------------------------------------------------------------------

def load_book(cache, refresh: bool = False,
              quarter: str = sources.DEFAULT_NCUA_QUARTER,
              gazetteer_year: str = sources.DEFAULT_GAZETTEER_YEAR) -> Book:
    """Every bank and credit union, with every branch that could be placed."""
    centroids = sources.zip_centroids(cache, gazetteer_year, refresh)
    unplaced: list[dict] = []

    insts = _fdic(cache, refresh, centroids, unplaced)
    insts.update(_ncua(cache, refresh, centroids, unplaced, quarter))

    branches = [b for inst in insts.values() for b in inst.branches]
    return Book(institutions=insts, branches=branches,
                index=BranchIndex(branches), unplaced=unplaced)
