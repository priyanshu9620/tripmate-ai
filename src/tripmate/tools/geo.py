"""Geocoding: fixtures offline; Nominatim (OpenStreetMap) live, with the fixture as fallback."""

from tripmate.providers.catalog import resolve_place
from tripmate.tools import _http

NOMINATIM = "https://nominatim.openstreetmap.org/search"


def parse_nominatim(payload: list | None) -> dict | None:
    if not payload:
        return None
    hit = payload[0]
    return {
        "name": hit.get("display_name", ""),
        "lat": float(hit["lat"]),
        "lon": float(hit["lon"]),
        "country": (hit.get("address") or {}).get("country_code", "").upper(),
    }


def geocode(place: str) -> dict:
    key, rec = resolve_place(place)  # raises UnknownPlace: outside the catalogue there is no inventory anyway
    base = {
        "key": key,
        "name": rec["name"],
        "lat": rec["lat"],
        "lon": rec["lon"],
        "country": rec["country"],
        "airport": rec["airport"],
        "tz": rec["tz"],
        "source": "fixture",
    }
    if not _http.live():
        return base
    hit = parse_nominatim(
        _http.get_json(NOMINATIM, {"q": place, "format": "json", "limit": 1, "addressdetails": 1})
    )
    if hit is None:
        return {**base, "note": "live geocoding failed; fixture used"}
    return {**base, **{k: v for k, v in hit.items() if v}, "source": "nominatim"}
