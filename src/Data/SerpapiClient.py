import os
import serpapi
from tenacity import retry, stop_after_attempt, wait_exponential

from Config.Settings import SERPAPI_KEY

_client = serpapi.Client(api_key=SERPAPI_KEY)

_STOPS_MAP = {
    0: 1,
    1: 2,
    2: 3,
}


def _map_stops(max_stops: int) -> int:
    return _STOPS_MAP.get(max_stops, 0)


def _build_params(
    origins: list[str],
    destination: str,
    outbound_date: str,
    return_date: str,
    passengers: int,
    currency: str,
    max_stops: int,
    **extra,
) -> dict:
    return {
        "engine": "google_flights",
        "departure_id": ",".join(origins),
        "arrival_id": destination,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "adults": passengers,
        "currency": currency,
        "hl": "en",
        "stops": _map_stops(max_stops),
        "type": 1,
        "sort_by": 2,
        "no_cache": True,
        **extra,
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def search_flights(
    origins: list[str],
    destination: str,
    outbound_date: str,
    return_date: str,
    passengers: int,
    currency: str,
    max_stops: int,
) -> dict:
    params = _build_params(
        origins, destination, outbound_date, return_date, passengers, currency, max_stops
    )
    result = _client.search(params)
    return dict(result)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def search_return_flights(
    origins: list[str],
    destination: str,
    outbound_date: str,
    return_date: str,
    passengers: int,
    currency: str,
    max_stops: int,
    departure_token: str,
) -> dict:
    """Second-step SerpAPI call: given the departure_token from an outbound
    itinerary, returns the matching return-leg itineraries."""
    params = _build_params(
        origins, destination, outbound_date, return_date, passengers, currency, max_stops,
        departure_token=departure_token,
    )
    result = _client.search(params)
    return dict(result)


def extract_flights(raw: dict, passengers: int) -> list[dict]:
    best = raw.get("best_flights", [])
    other = raw.get("other_flights", [])
    all_flights = best + other

    extracted = []
    for itinerary in all_flights:
        legs = itinerary.get("flights", [])
        if not legs:
            continue

        first_leg = legs[0]
        last_leg = legs[-1]
        layovers = itinerary.get("layovers", [])
        price = itinerary.get("price")

        extracted.append({
            # SerpAPI returns the total price for `passengers` adults;
            # normalize to per-person to match the rest of the pipeline.
            "price": round(price / passengers, 2) if price else None,
            "currency": raw.get("search_parameters", {}).get("currency", "EUR"),
            "total_duration_minutes": itinerary.get("total_duration"),
            "type": itinerary.get("type"),
            "stops": len(legs) - 1,
            "departure_airport": first_leg["departure_airport"]["id"],
            "departure_time": first_leg["departure_airport"]["time"],
            "arrival_airport": last_leg["arrival_airport"]["id"],
            "arrival_time": last_leg["arrival_airport"]["time"],
            "airlines": list({leg["airline"] for leg in legs}),
            "layovers": [
                {
                    "airport": lv.get("name"),
                    "duration_minutes": lv.get("duration"),
                    "overnight": lv.get("overnight", False),
                }
                for lv in layovers
            ],
            "departure_token": itinerary.get("departure_token"),
        })

    return extracted


def get_return_flight(profile: dict, best_flight: dict, flights: list[dict]) -> dict | None:
    """Given the outbound flight Claude picked, fetch its return leg.

    Matches `best_flight` back to one of the originally extracted `flights`
    (which carry the `departure_token` and the search window's dates),
    then makes the second SerpAPI call to retrieve the corresponding return
    itinerary. Returns None if no match or no return itinerary is found.
    """
    match = next(
        (
            f for f in flights
            if f.get("departure_airport") == best_flight.get("departure_airport")
            and f.get("departure_time") == best_flight.get("departure_time")
            and f.get("arrival_airport") == best_flight.get("arrival_airport")
            and f.get("arrival_time") == best_flight.get("arrival_time")
            and f.get("price") == best_flight.get("price")
        ),
        None,
    )
    if not match or not match.get("departure_token"):
        return None

    raw = search_return_flights(
        origins=profile["origins"],
        destination=profile["destination"],
        outbound_date=match["_outbound_date"],
        return_date=match["_return_date"],
        passengers=profile["passengers"],
        currency=profile["currency"],
        max_stops=profile["max_stops"],
        departure_token=match["departure_token"],
    )
    returns = extract_flights(raw, profile["passengers"])
    return returns[0] if returns else None