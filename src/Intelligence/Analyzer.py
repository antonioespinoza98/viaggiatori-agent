import json
import logging

import anthropic

from Config.Settings import ANTHROPIC_API_KEY, ALERT_THRESHOLD_PCT
from Data.PriceHistory import load_recent_prices
from Intelligence.Prompts import FEW_SHOT_EXAMPLES, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _strip_internal_fields(flight: dict) -> dict:
    return {
        k: v for k, v in flight.items()
        if k != "departure_token" and not k.startswith("_")
    }


def _build_user_message(profile: dict, flights: list[dict], price_history: list[dict]) -> str:
    visible_flights = [_strip_internal_fields(f) for f in flights]
    return f"""
Profile:
  name: {profile["name"]}
  origins: {profile["origins"]}
  destination: {profile["destination"]}
  budget: {profile["budget"]}
  currency: {profile["currency"]}
  passengers: {profile["passengers"]}
  max_stops: {profile["max_stops"]}
  alert_threshold_pct: {ALERT_THRESHOLD_PCT}

Flights found today:
{json.dumps(visible_flights, indent=2, ensure_ascii=False)}

Price history (last 7 days):
{json.dumps(price_history, indent=2, ensure_ascii=False)}
""".strip()


def _parse_response(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)


def _no_alert_result(reason: str) -> dict:
    return {
        "alert": False,
        "best_flight": None,
        "reason": reason,
        "trend": "insufficient_data",
        "total_cost": None,
    }


def analyze(profile: dict, flights: list[dict]) -> dict:
    origin = profile["origins"][0] if len(profile["origins"]) == 1 else "MULTI"
    destination = profile["destination"]
    profile_name = profile["name"]

    price_history = load_recent_prices(
        profile_name=profile_name,
        origin=origin,
        destination=destination,
        days=7,
    )

    user_message = _build_user_message(profile, flights, price_history)

    # Cache the static system prompt + few-shot prefix so repeated calls
    # (one per profile, per run) reuse it instead of re-processing it.
    last_example = FEW_SHOT_EXAMPLES[-1]
    messages = [
        *FEW_SHOT_EXAMPLES[:-1],
        {
            "role": last_example["role"],
            "content": [
                {
                    "type": "text",
                    "text": last_example["content"],
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        },
        {"role": "user", "content": user_message},
    ]

    logger.info("[%s] Sending %d flights to Claude for analysis", profile_name, len(flights))

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
        )
    except anthropic.APIError:
        logger.exception("[%s] Claude API call failed", profile_name)
        return _no_alert_result("Claude API call failed.")

    raw_content = response.content[0].text
    logger.debug("[%s] Claude raw response: %s", profile_name, raw_content)

    try:
        result = _parse_response(raw_content)
    except json.JSONDecodeError:
        logger.error("[%s] Failed to parse Claude response: %s", profile_name, raw_content)
        return _no_alert_result("Claude response could not be parsed.")

    logger.info(
        "[%s] Analysis complete — alert=%s trend=%s reason=%s",
        profile_name,
        result.get("alert"),
        result.get("trend"),
        result.get("reason"),
    )

    return result