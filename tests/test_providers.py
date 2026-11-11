from datetime import date

import pytest

from tripmate.providers import bookings, flights, hotels
from tripmate.providers.catalog import UnknownPlace, haversine_km, resolve_place

D = date(2026, 12, 18)


def setup_function():
    bookings.reset()


def test_resolve_place_aliases_and_partials():
    assert resolve_place("Goa")[0] == "goa"
    assert resolve_place("goa, india")[0] == "goa"
    assert resolve_place("Panjim")[0] == "goa"
    assert resolve_place("Kerala")[0] == "kochi"
    assert resolve_place("Bangalore")[0] == "bengaluru"
    with pytest.raises(UnknownPlace):
        resolve_place("Atlantis")


def test_haversine_delhi_goa_is_about_1500km():
    assert 1400 < haversine_km(28.6139, 77.2090, 15.2993, 74.1240) < 1600


def test_flights_are_deterministic_sorted_and_scale_with_passengers():
    a = flights.search_flights("Delhi", "Goa", D, 1)
    b = flights.search_flights("delhi", "goa", D, 1)
    assert a == b and len(a) == 5
    prices = [f["price_per_person_inr"] for f in a]
    assert prices == sorted(prices)
    two = flights.search_flights("Delhi", "Goa", D, 2)
    assert two[0]["total_inr"] == 2 * two[0]["price_per_person_inr"]
    assert flights.search_flights("Goa", "Goa", D) == []


def test_airline_pool_matches_route_type():
    for f in flights.search_flights("Mumbai", "Dubai", D):
        assert f["airline"] not in {"SpiceJet", "Akasa Air"}
    for f in flights.search_flights("Delhi", "Goa", D):
        assert f["airline"] not in {"Emirates", "Singapore Airlines", "Thai Airways"}


def test_book_flight_requires_search_and_is_idempotent():
    assert flights.book_flight("XX999-DEL-GOI-2026-12-18", ["A"])["ok"] is False
    assert flights.book_flight("garbage", ["A"])["ok"] is False
    f = flights.search_flights("Delhi", "Goa", D)[0]
    first = flights.book_flight(f["flight_id"], ["Asha", "Ravi"])
    again = flights.book_flight(f["flight_id"], ["ravi", "Asha "])
    assert first["ok"] and first["total_inr"] == 2 * f["price_per_person_inr"]
    assert again["reference"] == first["reference"] and again["already_booked"] is True
    assert len(bookings.all_bookings()) == 1
    assert flights.book_flight(f["flight_id"], [])["ok"] is False


def test_booking_survives_a_fresh_process():
    """ids are self-describing; book without a prior search in this process (restart scenario)."""
    fid = flights.search_flights("Delhi", "Goa", D)[0]["flight_id"]
    hid = hotels.search_hotels("Goa", D, date(2026, 12, 22))[0]["hotel_id"]
    bookings.reset()
    assert flights.find_flight(fid)["flight_id"] == fid
    assert flights.book_flight(fid, ["Asha"])["ok"]
    assert hotels.book_hotel(hid, D, date(2026, 12, 22), ["Asha"])["ok"]


def test_hotels_filter_tier_and_budget_and_book():
    rows = hotels.search_hotels("Goa", D, date(2026, 12, 22), guests=2)
    assert rows and all(r["nights"] == 4 and r["rooms"] == 1 for r in rows)
    assert [r["total_inr"] for r in rows] == sorted(r["total_inr"] for r in rows)
    assert all(
        r["tier"] == "budget" for r in hotels.search_hotels("Goa", D, date(2026, 12, 22), tier="budget")
    )
    cheap = hotels.search_hotels("Goa", D, date(2026, 12, 22), max_rate_inr=2500)
    assert all(r["rate_per_night_inr"] <= 2500 for r in cheap)
    assert hotels.search_hotels("Goa", D, D) == []
    b = hotels.book_hotel(rows[0]["hotel_id"], D, date(2026, 12, 22), ["Asha", "Ravi", "Meera"])
    assert b["ok"] and b["total_inr"] == rows[0]["rate_per_night_inr"] * 4 * 2  # 3 guests → 2 rooms
    assert hotels.book_hotel("H999", D, date(2026, 12, 22), ["A"])["ok"] is False


def test_peak_season_costs_more_than_monsoon_in_goa():
    dec = hotels.search_hotels("Goa", date(2026, 12, 10), date(2026, 12, 11), tier="mid")
    jul = hotels.search_hotels("Goa", date(2026, 7, 10), date(2026, 7, 11), tier="mid")
    assert sum(r["rate_per_night_inr"] for r in dec) > sum(r["rate_per_night_inr"] for r in jul)
