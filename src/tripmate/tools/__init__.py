"""LangChain tools the agents call. Every tool returns a dict (never a bare list — some providers reject
empty list content) with `count`/`items` for list results and `source` saying fixture vs live."""

from datetime import date

from langchain_core.tools import tool

from tripmate.providers import flights as _flights
from tripmate.providers import hotels as _hotels
from tripmate.providers.catalog import UnknownPlace
from tripmate.tools import geo, pois, weather


def _listing(items: list[dict], source: str, note: str = "") -> dict:
    return {
        "count": len(items),
        "items": items,
        "source": source,
        "note": note or ("no results" if not items else ""),
    }


@tool
def geocode(place: str) -> dict:
    """Resolve a place name to coordinates, country, nearest airport and timezone."""
    try:
        return geo.geocode(place)
    except UnknownPlace as e:
        return {"ok": False, "error": str(e)}


@tool
def weather_forecast(place: str, start_date: str, end_date: str) -> dict:
    """Daily weather (max/min °C, rain chance %) for a place between two ISO dates (inclusive)."""
    try:
        rows, source = weather.forecast(place, date.fromisoformat(start_date), date.fromisoformat(end_date))
    except (UnknownPlace, ValueError) as e:
        return {"ok": False, "error": str(e)}
    return _listing(rows, source)


@tool
def points_of_interest(place: str, kinds: list[str] | None = None, limit: int = 16) -> dict:
    """Top sights for a place. kinds filters by category: beach, heritage, nature, market, museum, food,
    adventure, culture, landmark."""
    try:
        rows, source = pois.search(place, kinds, limit)
    except UnknownPlace as e:
        return {"ok": False, "error": str(e)}
    return _listing(rows, source)


@tool
def search_flights(origin: str, destination: str, travel_date: str, passengers: int = 1) -> dict:
    """Flights for one date, cheapest first. Prices in INR. Inventory is simulated."""
    try:
        rows = _flights.search_flights(origin, destination, date.fromisoformat(travel_date), passengers)
    except (UnknownPlace, ValueError) as e:
        return {"ok": False, "error": str(e)}
    return _listing(rows, "simulated")


@tool
def search_hotels(
    destination: str,
    checkin: str,
    checkout: str,
    guests: int = 2,
    max_rate_inr: float | None = None,
    tier: str | None = None,
) -> dict:
    """Hotels for a stay, cheapest total first. tier: budget | mid | premium. Inventory is simulated."""
    try:
        rows = _hotels.search_hotels(
            destination, date.fromisoformat(checkin), date.fromisoformat(checkout), guests, max_rate_inr, tier
        )
    except (UnknownPlace, ValueError) as e:
        return {"ok": False, "error": str(e)}
    return _listing(rows, "simulated")


@tool
def book_flight(flight_id: str, traveller_names: list[str]) -> dict:
    """Book a flight returned by search_flights. MUTATING: only after the user approved."""
    return _flights.book_flight(flight_id, traveller_names)


@tool
def book_hotel(hotel_id: str, checkin: str, checkout: str, guest_names: list[str]) -> dict:
    """Book a hotel returned by search_hotels. MUTATING: only after the user approved."""
    try:
        return _hotels.book_hotel(
            hotel_id, date.fromisoformat(checkin), date.fromisoformat(checkout), guest_names
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}


RESEARCH_TOOLS = [geocode, weather_forecast, points_of_interest]
BUDGET_TOOLS = [search_flights, search_hotels]
BOOKING_TOOLS = [book_flight, book_hotel]
ALL_TOOLS = RESEARCH_TOOLS + BUDGET_TOOLS + BOOKING_TOOLS
MUTATING_TOOL_NAMES = {t.name for t in BOOKING_TOOLS}
