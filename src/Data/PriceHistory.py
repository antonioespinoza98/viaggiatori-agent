import json
import logging
from datetime import date, timedelta

import boto3
from botocore.exceptions import ClientError

from Config.Settings import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    PRICE_HISTORY_DAYS,
    S3_BUCKET_NAME,
)

logger = logging.getLogger(__name__)

_s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)


def _key(profile_name: str, origin: str, destination: str, snapshot_date: date) -> str:
    slug = profile_name.lower().replace(" ", "-").replace("/", "-")
    return f"{slug}/{origin}-{destination}/{snapshot_date.isoformat()}.json"


def save_snapshot(
    profile_name: str,
    origin: str,
    destination: str,
    flights: list[dict],
    snapshot_date: date | None = None,
) -> None:
    snapshot_date = snapshot_date or date.today()
    key = _key(profile_name, origin, destination, snapshot_date)
    payload = json.dumps(
        {"date": snapshot_date.isoformat(), "flights": flights},
        ensure_ascii=False,
        indent=2,
    )
    _s3.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=key,
        Body=payload.encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Saved snapshot → s3://%s/%s", S3_BUCKET_NAME, key)


def load_history(
    profile_name: str,
    origin: str,
    destination: str,
    days: int | None = None,
) -> list[dict]:
    days = days or PRICE_HISTORY_DAYS
    today = date.today()
    history = []

    for offset in range(days):
        snapshot_date = today - timedelta(days=offset)
        key = _key(profile_name, origin, destination, snapshot_date)
        try:
            response = _s3.get_object(Bucket=S3_BUCKET_NAME, Key=key)
            data = json.loads(response["Body"].read().decode("utf-8"))
            history.append(data)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                continue
            raise

    history.sort(key=lambda x: x["date"])
    return history


def load_recent_prices(
    profile_name: str,
    origin: str,
    destination: str,
    days: int = 7,
) -> list[dict]:
    history = load_history(profile_name, origin, destination, days=days)

    summary = []
    for snapshot in history:
        prices = [f["price"] for f in snapshot.get("flights", []) if f.get("price")]
        if prices:
            summary.append({
                "date": snapshot["date"],
                "min_price": min(prices),
                "max_price": max(prices),
                "avg_price": round(sum(prices) / len(prices), 2),
            })

    return summary