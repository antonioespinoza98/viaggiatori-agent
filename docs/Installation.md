# Installation

## Prerequisites

- Python 3.14 (matches `.github/workflows/FlightAgent.yml`)
- A [SerpAPI](https://serpapi.com/) account/API key (Google Flights engine)
- An [Anthropic](https://console.anthropic.com/) API key
- An AWS account with an S3 bucket for price-history snapshots
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833)
  for SMTP sending (not your normal account password)

## 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2. Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

## 3. Configure secrets (`.env`)

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

`src/Config/Settings.py` reads every value below via `os.environ[...]`
(not `.get()`) — **all** of these must be set or the app fails immediately on
startup:

| Variable | Description |
|---|---|
| `SERPAPI_KEY` | SerpAPI key used for Google Flights searches |
| `ANTHROPIC_API_KEY` | Anthropic API key used to analyze flight deals |
| `AWS_ACCESS_KEY_ID` | AWS credential for the S3 price-history bucket |
| `AWS_SECRET_ACCESS_KEY` | AWS credential for the S3 price-history bucket |
| `AWS_REGION` | AWS region the S3 bucket lives in |
| `S3_BUCKET_NAME` | S3 bucket used to store daily price snapshots |
| `GMAIL_SENDER` | Gmail address alerts are sent from |
| `GMAIL_APP_PASSWORD` | Gmail App Password for `GMAIL_SENDER` |

## 4. Configure travel profiles (`config.yml`)

`config.yml` (repo root) defines the travel profiles to monitor and a few
global settings. See [Usage](Usage.md) for the full field reference and an
example profile.

## 5. Run the agent

From the repo root (so `src/` is on `sys.path` and the `Config.*` / `Data.*`
/ `Intelligence.*` imports resolve):

```bash
python src/main.py
```

A successful run logs each profile's search results, the analysis decision,
and (if a deal qualifies) that an alert email was sent.
