# Ported from ARS v5 02-Scripts/core/market/geo.py at a491b5c (James Gilmore); logic unchanged.
"""Distance and the radius query the whole scan rests on.

Scanning 315 clients against ~100k branches is 30M+ pairs if done naively.
A one-degree grid cuts each query to the handful of cells the radius can
reach, so a full-book scan runs in seconds rather than minutes.
"""

from __future__ import annotations

import math
from collections import defaultdict

EARTH_RADIUS_MI = 3958.7613
MILES_PER_DEG_LAT = 69.0

# Cosine floor for the longitude span: past ~85 degrees the correction
# explodes, and no US branch is anywhere near it.
_MIN_COS_LAT = 0.09


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


def _lon_span(lat: float, radius_mi: float) -> float:
    """Degrees of longitude that radius_mi spans at this latitude."""
    cos_lat = max(abs(math.cos(math.radians(lat))), _MIN_COS_LAT)
    return radius_mi / (MILES_PER_DEG_LAT * cos_lat)


class BranchIndex:
    """Branches bucketed into one-degree cells, queryable by radius.

    Each branch is any object exposing .lat and .lon; what else it carries
    is the caller's business.
    """

    def __init__(self, branches):
        self._cells: dict[tuple[int, int], list] = defaultdict(list)
        self.count = 0
        for branch in branches:
            lat, lon = getattr(branch, "lat", None), getattr(branch, "lon", None)
            if lat is None or lon is None:
                continue
            self._cells[(math.floor(lat), math.floor(lon))].append(branch)
            self.count += 1

    def near(self, lat: float, lon: float, radius_mi: float) -> list:
        """Every indexed branch within radius_mi, unsorted, exact."""
        lat_span = radius_mi / MILES_PER_DEG_LAT
        lon_span = _lon_span(lat, radius_mi)

        hits = []
        for cell_lat in range(math.floor(lat - lat_span),
                              math.floor(lat + lat_span) + 1):
            for cell_lon in range(math.floor(lon - lon_span),
                                  math.floor(lon + lon_span) + 1):
                for branch in self._cells.get((cell_lat, cell_lon), ()):
                    if haversine(lat, lon, branch.lat, branch.lon) <= radius_mi:
                        hits.append(branch)
        return hits

    def nearest_by_key(self, points, radius_mi: float, key) -> dict:
        """Scan from several origins at once, keeping the closest hit.

        Returns {key(branch): (distance_mi, branch)} -- the shortest distance
        from ANY of the origin points, which is what "within 25 miles of this
        client" means when the client has 13 branches.
        """
        best: dict = {}
        for lat, lon in points:
            for branch in self.near(lat, lon, radius_mi):
                dist = haversine(lat, lon, branch.lat, branch.lon)
                k = key(branch)
                if k not in best or dist < best[k][0]:
                    best[k] = (dist, branch)
        return best
