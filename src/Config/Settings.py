import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "config.yml"


def _load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


_config = _load_config()


# --- Profiles ---

PROFILES: list[dict] = _config["profiles"]


# --- Global pipeline settings ---

ALERT_THRESHOLD_PCT: float = _config["settings"]["alert_threshold_pct"]
RUNS_PER_DAY: int = _config["settings"]["runs_per_day"]
PRICE_HISTORY_DAYS: int = _config["settings"]["price_history_days"]


# --- Anthropic ---

ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]


# --- AWS / S3 ---

AWS_ACCESS_KEY_ID: str = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY: str = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION: str = os.environ["AWS_REGION"]
S3_BUCKET_NAME: str = os.environ["S3_BUCKET_NAME"]


# --- Gmail ---

GMAIL_SENDER: str = os.environ["GMAIL_SENDER"]
GMAIL_APP_PASSWORD: str = os.environ["GMAIL_APP_PASSWORD"]