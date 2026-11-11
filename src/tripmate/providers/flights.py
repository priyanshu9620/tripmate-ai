"""Simulated flight inventory. Prices: airline base + per-km × distance × a seeded daily multiplier."""

import hashlib
import random
import re
from datetime import date, timedelta

from tripmate.providers import bookings
from tripmate.providers.catalog import _places, airlines, haversine_km, resolve_place


def _rng(*parts: object) -> random.Random:
    return random.Random(int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest(), 16))


def search_flights(origin: str, destination: str, travel_date: date, passengers: int = 1) -> list[dict]:
    okey, o = resolve_place(origin)
    dkey, d = resolve_place(destination)
    if okey == dkey or o["airport"] == d["airport"]:
        return []  # same city / same airport: nothing to fly
    km = haversine_km(o["lat"], o["lon"], d["lat"], d["lon"])
    international = o["country"] != d["country"]
    pool = [a for a in airlines() if (a["intl"] if international else a["domestic"])]
    rng = _rng("flights", okey, dkey, travel_date.isoformat())
    day_mult = 0.85 + rng.random() * 0.5
    if travel_date.weekday() >= 5:
        day_mult *= 1.10
    out = []
    for i, a in enumerate(rng.sample(pool, k=min(5, len(pool)))):
        num = 100 + rng.randint(0, 899)
        dep_h, dep_m = rng.randint(5, 21), rng.choice([0, 15, 30, 45])
        minutes = int(km / 12.5 + 40 + rng.randint(-10, 25))  # ~750 km/h + taxi/turnaround
        fare = (a["base_fare_inr"] + a["per_km_inr"] * km) * day_mult * (1 + 0.04 * i)
        fid = f"{a['code']}{num}-{o['airport']}-{d['airport']}-{travel_date.isoformat()}"
        flight = {
            "flight_id": fid,
            "airline": a["name"],
            "from": o["airport"],
            "to": d["airport"],
            "date": travel_date.isoformat(),
            "depart": f"{dep_h:02d}:{dep_m:02d}",
            "duration_min": minutes,
            "stops": 0 if km < 2500 or rng.random() < 0.6 else 1,
            "seats_left": rng.randint(2, 9),
            "price_per_person_inr": round(fare / 10) * 10,
            "total_inr": round(fare / 10) * 10 * passengers,
            "passengers": passengers,
        }
        out.append(flight)
    return sorted(out, key=lambda f: f["price_per_person_inr"])


def find_flight(flight_id: str) -> dict | None:
    """Re-derive a flight from its id (ids are self-describing: CODE123-DEL-GOI-YYYY-MM-DD). Search is
    deterministic, so this works after a restart and rejects ids no search ever produced."""
    m = re.fullmatch(r"([A-Z0-9]{2}\d{3})-([A-Z]{3})-([A-Z]{3})-(\d{4}-\d{2}-\d{2})", flight_id)
    if not m:
        return None
    _, src, dst, day = m.groups()
    try:
        origin, dest = _by_airport(src), _by_airport(dst)
        rows = search_flights(origin, dest, date.fromisoformat(day), 1)
    except ValueError:
        return None
    return next((f for f in rows if f["flight_id"] == flight_id), None)


def _by_airport(code: str) -> str:
    for key, rec in _places()["destinations"].items():
        if rec["airport"] == code:
            return key
    raise ValueError(code)


def book_flight(flight_id: str, traveller_names: list[str]) -> dict:
    flight = find_flight(flight_id)
    if flight is None:
        return {
            "ok": False,
            "error": f"unknown flight_id {flight_id!r}: use an id returned by search_flights",
        }
    if not traveller_names:
        return {"ok": False, "error": "traveller_names must not be empty"}
    if len(traveller_names) > flight["seats_left"]:
        return {"ok": False, "error": f"only {flight['seats_left']} seats left on {flight_id}"}
    total = flight["price_per_person_inr"] * len(traveller_names)
    rec = bookings.record("flight", flight_id, traveller_names, {"total_inr": total, "flight": flight})
    return {"ok": True, **rec}


def return_date(travel_date: date, nights: int) -> date:
    return travel_date + timedelta(days=nights)
