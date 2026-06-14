import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from Data.SerpapiClient import extract_flights, search_flights
from Data.PriceHistory import save_snapshot

logger = logging.getLogger(__name__)


def _date_windows(
    date_from: str,
    date_to: str,
    trip_duration_days: int,
    window_step_days: int,
) -> list[tuple[str, str]]:
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    windows = []
    outbound = start
    while outbound <= end - timedelta(days=trip_duration_days):
        return_date = outbound + timedelta(days=trip_duration_days)
        windows.append((outbound.isoformat(), return_date.isoformat()))
        outbound += timedelta(days=window_step_days)
    return windows


def _search_window(
    profile: dict,
    outbound_date: str,
    return_date: str,
) -> list[dict]:
    origins = profile["origins"]
    destination = profile["destination"]

    try:
        raw = search_flights(
            origins=origins,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            passengers=profile["passengers"],
            currency=profile["currency"],
            max_stops=profile["max_stops"],
        )
        flights = extract_flights(raw, profile["passengers"])
        for flight in flights:
            flight["_outbound_date"] = outbound_date
            flight["_return_date"] = return_date
        logger.info(
            "[%s] %s → %s | %s → %s | %d results",
            profile["name"],
            ",".join(origins),
            destination,
            outbound_date,
            return_date,
            len(flights),
        )
        return flights
    except Exception:
        logger.exception(
            "[%s] Search failed for %s → %s (%s / %s)",
            profile["name"],
            ",".join(origins),
            destination,
            outbound_date,
            return_date,
        )
        return []


def run_profile(profile: dict) -> dict:
    name = profile["name"]
    origins = profile["origins"]
    destination = profile["destination"]
    date_from = profile["date_from"]
    date_to = profile["date_to"]
    trip_duration_days = profile["trip_duration_days"]
    window_step_days = profile["window_step_days"]

    windows = _date_windows(date_from, date_to, trip_duration_days, window_step_days)
    logger.info("[%s] Running %d date windows", name, len(windows))

    all_flights: list[dict] = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_search_window, profile, ob, ret): (ob, ret)
            for ob, ret in windows
        }
        for future in as_completed(futures):
            flights = future.result()
            all_flights.extend(flights)

    all_flights.sort(key=lambda f: f["price"] or float("inf"))

    primary_origin = origins[0]
    save_snapshot(
        profile_name=name,
        origin=primary_origin if len(origins) == 1 else "MULTI",
        destination=destination,
        flights=all_flights,
    )

    return {
        "profile": name,
        "origins": origins,
        "destination": destination,
        "flights": all_flights,
        "date_from": date_from,
        "date_to": date_to,
    }


def run_all_profiles(profiles: list[dict]) -> list[dict]:
    results = []
    for profile in profiles:
        logger.info("Starting profile: %s", profile["name"])
        result = run_profile(profile)
        results.append(result)
        logger.info(
            "Completed profile: %s — %d flights found",
            profile["name"],
            len(result["flights"]),
        )
    return results