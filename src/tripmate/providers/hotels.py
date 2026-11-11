"""Simulated hotel inventory from fixtures/hotels.csv. Rates vary by season and a seeded multiplier."""

import hashlib
import random
from datetime import date

from tripmate.providers import bookings
from tripmate.providers.catalog import hotels, resolve_place


def _season_mult(rec: dict, month: int) -> float:
    """Dry months are peak season: fewer rainy days → higher rates."""
    if not rec.get("climate"):
        return 1.0
    rain = rec["climate"][month - 1]["rain_pct"]
    return 1.25 if rain < 15 else 1.0 if rain < 50 else 0.8


def search_hotels(
    destination: str,
    checkin: date,
    checkout: date,
    guests: int = 2,
    max_rate_inr: float | None = None,
    tier: str | None = None,
) -> list[dict]:
    key, rec = resolve_place(destination)
    nights = (checkout - checkin).days
    if nights <= 0:
        return []
    rng = random.Random(int(hashlib.sha1(f"hotels|{key}|{checkin}".encode()).hexdigest(), 16))
    rooms = -(-guests // 2)  # 2 guests per room
    out = []
    for h in hotels():
        if h["destination"] != key or (tier and h["tier"] != tier):
            continue
        rate = h["base_rate_inr"] * _season_mult(rec, checkin.month) * (0.9 + rng.random() * 0.25)
        rate = round(rate / 50) * 50
        if max_rate_inr is not None and rate > max_rate_inr:
            continue
        row = {
            "hotel_id": h["hotel_id"],
            "name": h["name"],
            "tier": h["tier"],
            "area": h["area"],
            "rating": h["rating"],
            "checkin": checkin.isoformat(),
            "checkout": checkout.isoformat(),
            "nights": nights,
            "rooms": rooms,
            "rate_per_night_inr": rate,
            "total_inr": rate * nights * rooms,
            "rooms_left": rng.randint(1, 6),
        }
        out.append(row)
    return sorted(out, key=lambda r: r["total_inr"])


def find_hotel(hotel_id: str, checkin: date, checkout: date) -> dict | None:
    """Re-derive the offer for (hotel, dates); deterministic, so it survives a restart."""
    h = next((h for h in hotels() if h["hotel_id"] == hotel_id), None)
    if h is None:
        return None
    rows = search_hotels(h["destination"], checkin, checkout, guests=1)
    return next((r for r in rows if r["hotel_id"] == hotel_id), None)


def book_hotel(hotel_id: str, checkin: date, checkout: date, guest_names: list[str]) -> dict:
    row = find_hotel(hotel_id, checkin, checkout)
    if row is None:
        return {"ok": False, "error": f"unknown hotel_id/dates {hotel_id!r} {checkin}→{checkout}"}
    if not guest_names:
        return {"ok": False, "error": "guest_names must not be empty"}
    rooms = -(-len(guest_names) // 2)
    if rooms > row["rooms_left"]:
        return {"ok": False, "error": f"only {row['rooms_left']} rooms left at {hotel_id}"}
    total = row["rate_per_night_inr"] * row["nights"] * rooms
    rec = bookings.record("hotel", f"{hotel_id}|{checkin}", guest_names, {"total_inr": total, "hotel": row})
    return {"ok": True, **rec}
