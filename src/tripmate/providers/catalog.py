"""Fixture catalogue: places (geo + climate + POIs), airlines, hotels."""

import csv
import json
import math
from functools import lru_cache
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class UnknownPlace(ValueError):
    pass


@lru_cache(maxsize=1)
def _places() -> dict:
    return json.loads((FIXTURES / "destinations.json").read_text())


@lru_cache(maxsize=1)
def airlines() -> list[dict]:
    with (FIXTURES / "airlines.csv").open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["base_fare_inr"] = float(r["base_fare_inr"])
        r["per_km_inr"] = float(r["per_km_inr"])
        r["intl"] = r["intl"] == "1"
        r["domestic"] = r["domestic"] == "1"
    return rows


@lru_cache(maxsize=1)
def hotels() -> list[dict]:
    with (FIXTURES / "hotels.csv").open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["base_rate_inr"] = float(r["base_rate_inr"])
        r["rating"] = float(r["rating"])
    return rows


def place_keys() -> list[str]:
    return sorted(_places()["destinations"])


def resolve_place(name: str) -> tuple[str, dict]:
    """'Goa', 'goa, india', 'Panjim' → ('goa', record). Raises UnknownPlace."""
    data = _places()
    q = name.strip().lower()
    q = data["aliases"].get(q, q)
    if q in data["destinations"]:
        return q, data["destinations"][q]
    head = q.split(",")[0].strip()
    head = data["aliases"].get(head, head)
    if head in data["destinations"]:
        return head, data["destinations"][head]
    for key, rec in data["destinations"].items():
        if key in q or q in rec["name"].lower():
            return key, rec
    raise UnknownPlace(f"unknown place '{name}'; known: {', '.join(place_keys())}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
