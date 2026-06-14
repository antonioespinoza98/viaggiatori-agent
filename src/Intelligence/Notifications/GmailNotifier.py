import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from Config.Settings import GMAIL_APP_PASSWORD, GMAIL_SENDER

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def _format_duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m"


def _format_layovers(layovers: list[dict]) -> str:
    if not layovers:
        return "None"
    parts = []
    for lv in layovers:
        duration = _format_duration(lv.get("duration_minutes", 0))
        airport = lv.get("airport", "Unknown")
        overnight = " (overnight)" if lv.get("overnight") else ""
        parts.append(f"{airport} — {duration}{overnight}")
    return "\n      ".join(parts)


def _build_subject(flight: dict) -> str:
    price = flight["price"]
    currency = flight["currency"]
    airlines = ", ".join(flight["airlines"])
    departure = flight["departure_airport"]
    arrival = flight["arrival_airport"]
    return f"🚨 Deal found · {departure}→{arrival} · {currency} {price}/person · {airlines}"


def _build_body(profile: dict, flight: dict, analysis: dict) -> str:
    price = flight["price"]
    currency = flight["currency"]
    total_cost = analysis.get("total_cost")
    passengers = profile["passengers"]
    budget = profile["budget"]
    airlines = ", ".join(flight["airlines"])
    stops = flight["stops"]
    stops_label = "Nonstop" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
    duration = _format_duration(flight.get("total_duration_minutes", 0))
    layovers = _format_layovers(flight.get("layovers", []))
    trend = analysis.get("trend", "unknown").replace("_", " ").capitalize()
    reason = analysis.get("reason", "")
    departure_airport = flight["departure_airport"]
    arrival_airport = flight["arrival_airport"]
    departure_time = flight["departure_time"]
    arrival_time = flight["arrival_time"]

    over_budget = price > budget
    budget_note = (
        f"  ⚠️  {currency} {price - budget:.0f} over budget — within 10% alert threshold\n"
        if over_budget else ""
    )

    return f"""
Flight Alert — {profile["name"]}
{"=" * 48}

✈️  {departure_airport} → {arrival_airport}
    Departure : {departure_time}
    Arrival   : {arrival_time}
    Airlines  : {airlines}
    Routing   : {stops_label} · {duration} total
    Layovers  : {layovers}

💶  Price
    Per person : {currency} {price}
    Passengers : {passengers}
    Total      : {currency} {total_cost}
    Budget     : {currency} {budget}/person
{budget_note}
📈  Price trend  : {trend}
🧠  Analysis     : {reason}

{"=" * 48}
This alert was generated automatically. Book directly
with the airline — do not use third-party aggregators.
""".strip()


def send_alert(profile: dict, flight: dict, analysis: dict) -> None:
    recipient = profile["notify"]
    subject = _build_subject(flight)
    body = _build_body(profile, flight, analysis)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = recipient
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, recipient, msg.as_string())
        logger.info(
            "[%s] Alert sent to %s — %s",
            profile["name"],
            recipient,
            subject,
        )
    except smtplib.SMTPException:
        logger.exception(
            "[%s] Failed to send alert to %s",
            profile["name"],
            recipient,
        )