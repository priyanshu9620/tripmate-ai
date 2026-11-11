from datetime import date

from tripmate.tools import (
    ALL_TOOLS,
    MUTATING_TOOL_NAMES,
    book_flight,
    geo,
    geocode,
    points_of_interest,
    pois,
    search_flights,
    search_hotels,
    weather,
    weather_forecast,
)

NOMINATIM_SAMPLE = [
    {"display_name": "Goa, India", "lat": "15.3", "lon": "74.1", "address": {"country_code": "in"}}
]
OPEN_METEO_SAMPLE = {
    "daily": {
        "time": ["2026-12-18", "2026-12-19"],
        "temperature_2m_max": [31.2, 30.8],
        "temperature_2m_min": [21.0, 20.5],
        "precipitation_probability_max": [5, 70],
    }
}
OVERPASS_SAMPLE = {
    "elements": [
        {"tags": {"name": "Fort Aguada", "tourism": "attraction"}},
        {"tags": {"name": "Fort Aguada", "tourism": "attraction"}},
        {"tags": {"tourism": "museum"}},
        {"tags": {"name": "Goa State Museum", "tourism": "museum"}},
    ]
}


def test_tool_registry_shape():
    names = {t.name for t in ALL_TOOLS}
    assert names == {
        "geocode", "weather_forecast", "points_of_interest", "search_flights", "search_hotels",
        "book_flight", "book_hotel",
    }  # fmt: skip
    assert MUTATING_TOOL_NAMES == {"book_flight", "book_hotel"}


def test_tools_return_dicts_never_bare_lists():
    assert geocode.invoke({"place": "Goa"})["airport"] == "GOI"
    assert geocode.invoke({"place": "Nowhere"})["ok"] is False
    wx = weather_forecast.invoke({"place": "Goa", "start_date": "2026-12-18", "end_date": "2026-12-21"})
    assert wx["count"] == 4 and wx["source"] == "fixture_climate_normals"
    assert (
        weather_forecast.invoke({"place": "Goa", "start_date": "2026-12-21", "end_date": "2026-12-18"})["ok"]
        is False
    )
    beaches = points_of_interest.invoke({"place": "Goa", "kinds": ["beach"]})
    assert beaches["count"] >= 2 and all(p["kind"] == "beach" for p in beaches["items"])
    empty = search_flights.invoke({"origin": "Goa", "destination": "Goa", "travel_date": "2026-12-18"})
    assert empty == {"count": 0, "items": [], "source": "simulated", "note": "no results"}
    assert (
        search_hotels.invoke({"destination": "Goa", "checkin": "2026-12-18", "checkout": "2026-12-20"})[
            "count"
        ]
        > 0
    )
    assert (
        search_flights.invoke({"origin": "Delhi", "destination": "Goa", "travel_date": "not-a-date"})["ok"]
        is False
    )
    assert book_flight.invoke({"flight_id": "nope", "traveller_names": ["A"]})["ok"] is False


def test_live_parsers_without_network():
    assert geo.parse_nominatim(NOMINATIM_SAMPLE)["country"] == "IN"
    assert geo.parse_nominatim([]) is None
    rows = weather.parse_open_meteo(OPEN_METEO_SAMPLE)
    assert [r["summary"] for r in rows] == ["clear", "rainy"]
    assert weather.parse_open_meteo(None) == []
    got = pois.parse_overpass(OVERPASS_SAMPLE)
    assert [p["name"] for p in got] == ["Fort Aguada", "Goa State Museum"]  # de-duplicated, unnamed dropped
    assert "around:10000" in pois.overpass_query(15.3, 74.1)


def test_live_mode_falls_back_to_fixture_when_http_fails(monkeypatch):
    monkeypatch.setattr(geo._http, "live", lambda: True)
    monkeypatch.setattr(geo._http, "get_json", lambda *a, **k: None)
    g = geocode.invoke({"place": "Goa"})
    assert g["source"] == "fixture" and "failed" in g["note"]
    monkeypatch.setattr(weather._http, "live", lambda: True)
    monkeypatch.setattr(weather._http, "get_json", lambda *a, **k: None)
    today = date.today()
    rows, source = weather.forecast("Goa", today, today)
    assert len(rows) == 1 and "live call failed" in source
