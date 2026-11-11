"""Daily weather. Offline: monthly climate normals from the fixture + deterministic day-to-day jitter.
Live: Open-Meteo for dates within its 16-day forecast window, climate normals beyond that."""

import hashlib
import random
from datetime import date, timedelta

from tripmate.providers.catalog import resolve_place
from tripmate.tools import _http

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 16
MAX_DAYS = 31


def _summary(rain_pct: float, tmax: float) -> str:
    if rain_pct >= 60:
        return "rainy"
    if rain_pct >= 30:
        return "showers possible"
    return "hot and dry" if tmax >= 35 else "clear"


def climate_rows(rec: dict, start: date, end: date) -> list[dict]:
    rows = []
    d = start
    while d <= end:
        m = rec["climate"][d.month - 1]
        rng = random.Random(int(hashlib.sha1(f"wx|{rec['name']}|{d}".encode()).hexdigest(), 16))
        tmax = m["tmax"] + rng.uniform(-2, 2)
        tmin = m["tmin"] + rng.uniform(-2, 2)
        rain = max(0, min(100, m["rain_pct"] + rng.uniform(-15, 15)))
        rows.append(
            {
                "date": d.isoformat(),
                "tmax_c": round(tmax, 1),
                "tmin_c": round(tmin, 1),
                "rain_pct": round(rain),
                "summary": _summary(rain, tmax),
            }
        )
        d += timedelta(days=1)
    return rows


def parse_open_meteo(payload: dict | None) -> list[dict]:
    if not payload or "daily" not in payload:
        return []
    daily = payload["daily"]
    rows = []
    for i, day in enumerate(daily.get("time", [])):
        tmax = daily["temperature_2m_max"][i]
        rain = daily["precipitation_probability_max"][i] or 0
        rows.append(
            {
                "date": day,
                "tmax_c": tmax,
                "tmin_c": daily["temperature_2m_min"][i],
                "rain_pct": rain,
                "summary": _summary(rain, tmax),
            }
        )
    return rows


def forecast(place: str, start: date, end: date) -> tuple[list[dict], str]:
    if end < start:
        raise ValueError("end_date before start_date")
    if (end - start).days + 1 > MAX_DAYS:
        raise ValueError(f"at most {MAX_DAYS} days")
    _, rec = resolve_place(place)
    if not rec.get("climate"):
        raise ValueError(f"no climate data for {rec['name']}")
    if not _http.live():
        return climate_rows(rec, start, end), "fixture_climate_normals"
    horizon = date.today() + timedelta(days=FORECAST_DAYS - 1)
    if start > horizon:
        return climate_rows(rec, start, end), "climate_normals_beyond_forecast_window"
    live_end = min(end, horizon)
    params = {
        "latitude": rec["lat"],
        "longitude": rec["lon"],
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "start_date": start.isoformat(),
        "end_date": live_end.isoformat(),
        "timezone": "auto",
    }
    rows = parse_open_meteo(_http.get_json(OPEN_METEO, params))
    if not rows:
        return climate_rows(rec, start, end), "fixture_climate_normals (live call failed)"
    if live_end < end:
        rows += climate_rows(rec, live_end + timedelta(days=1), end)
        return rows, "open_meteo + climate_normals"
    return rows, "open_meteo"
