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
    params = {
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
    }

    result = _client.search(params)
    return dict(result)


def extract_flights(raw: dict) -> list[dict]:
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

        extracted.append({
            "price": itinerary.get("price"),
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