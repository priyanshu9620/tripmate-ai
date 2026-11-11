"""Points of interest. Offline: curated fixture list. Live: Overpass (OSM) within 15 km, fixture fallback."""

from tripmate.providers.catalog import resolve_place
from tripmate.tools import _http

OVERPASS = "https://overpass-api.de/api/interpreter"
_OSM_KINDS = {
    "attraction": "landmark",
    "museum": "museum",
    "viewpoint": "nature",
    "beach_resort": "beach",
    "theme_park": "adventure",
    "zoo": "nature",
}


def overpass_query(lat: float, lon: float, radius_m: int = 10000) -> str:
    # nodes only, small radius: the public Overpass servers are slow and often time out (notes P-2);
    # the tool falls back to the curated fixture list whenever the call fails.
    return f"[out:json][timeout:8];node(around:{radius_m},{lat},{lon})[tourism~'attraction|museum|viewpoint'];out tags 40;"


def parse_overpass(payload: dict | None) -> list[dict]:
    rows = []
    for el in (payload or {}).get("elements", []):
        tags = el.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        rows.append({"name": name, "kind": _OSM_KINDS.get(tags.get("tourism", ""), "landmark")})
    seen, out = set(), []
    for r in rows:
        if r["name"] not in seen:
            seen.add(r["name"])
            out.append(r)
    return out


def search(place: str, kinds: list[str] | None = None, limit: int = 8) -> tuple[list[dict], str]:
    _, rec = resolve_place(place)
    rows, source = list(rec.get("pois") or []), "fixture"
    if _http.live():
        live_rows = parse_overpass(_http.get_json(OVERPASS, data=overpass_query(rec["lat"], rec["lon"])))
        if live_rows:
            rows, source = live_rows, "overpass"
    if kinds:
        wanted = {k.lower() for k in kinds}
        rows = [r for r in rows if r["kind"] in wanted]
    return rows[: max(1, limit)], source
