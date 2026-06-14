# Architecture

`viaggiatori-agent` is a personal flight-price-alert agent. For each configured
travel profile it searches Google Flights, stores a daily price snapshot,
asks Claude whether today's results are a good enough deal to alert on, and
emails the result via Gmail.

## Pipeline

`src/main.py` drives the pipeline for every profile in `config.yml`:

1. **Configuration — `Config/Settings.py`**
   Loads `config.yml` into `PROFILES` (the travel profiles) plus global
   settings (`alert_threshold_pct`, `runs_per_day`, `price_history_days`), and
   loads all secrets from the environment (via `python-dotenv`). Every other
   module imports config values from here rather than reading `config.yml` or
   `os.environ` directly.

2. **Search — `Data/SearchOrchestrator.py`**
   `run_profile()`:
   - Computes outbound/return date "windows" from `date_from`, `date_to`,
     `trip_duration_days`, and `window_step_days`.
   - Fans out one search per window concurrently (`ThreadPoolExecutor`,
     4 workers) via `Data/SerpapiClient.search_flights`.
   - Merges all results and sorts them by price.
   - Saves a snapshot of the day's results via `Data/PriceHistory.save_snapshot`.

   `run_all_profiles()` runs this for every profile, sequentially.

3. **Flight search — `Data/SerpapiClient.py`**
   Wraps the SerpAPI `google_flights` engine:
   - `search_flights()` builds the request (origins, destination, dates,
     passengers, currency, stop-count filter) and retries up to 3 times with
     exponential backoff (`tenacity`).
   - `extract_flights()` flattens the raw SerpAPI response (`best_flights` +
     `other_flights`) into a simplified flight dict: `price`, `stops`,
     `departure_airport`, `arrival_airport`, `airlines`, `layovers`, etc.
   - A profile's `max_stops` (the most stops the user will accept) is mapped
     to SerpAPI's `stops` parameter, where `0` = any, `1` = nonstop only,
     `2` = 1 stop or fewer, `3` = 2 stops or fewer.

4. **Price history — `Data/PriceHistory.py`**
   Reads/writes JSON price snapshots to S3, keyed as
   `{profile-slug}/{origin}-{destination}/{date}.json`. `load_recent_prices()`
   reads the last 7 days and produces a daily min/avg/max summary used as
   context for the analysis step.

5. **Analysis — `Intelligence/Analyzer.py` + `Intelligence/Prompts.py`**
   `analyze()` sends Claude (`claude-sonnet-4-6`) the profile, today's
   flights, and the 7-day price history, using a fixed `SYSTEM_PROMPT` and
   hardcoded few-shot examples (`Prompts.py`). The system prompt and the
   static few-shot prefix are marked `cache_control: ephemeral` so repeated
   calls within a run (one per profile) reuse the cached prefix.

   Claude must respond with a strict JSON object: `alert`, `best_flight`,
   `reason`, `trend`, `total_cost`. If the API call fails or the response
   can't be parsed as JSON, analysis degrades gracefully to a no-alert result.

6. **Notification — `Intelligence/Notifications/GmailNotifier.py`**
   If `analysis["alert"]` is true and a `best_flight` exists, formats and
   sends a plain-text email via Gmail SMTP (STARTTLS) to `profile["notify"]`.

## Data flow

```
config.yml ──► Settings ──► SearchOrchestrator ──► SerpapiClient (SerpAPI)
                                  │                        │
                                  ▼                        ▼
                          PriceHistory (S3) ◄────── flight results
                                  │
                                  ▼
                          Analyzer (Claude, claude-sonnet-4-6)
                                  │
                                  ▼
                          GmailNotifier (Gmail SMTP)
```

## Scheduling

The pipeline is meant to run on a schedule via
`.github/workflows/FlightAgent.yml` (daily cron + manual
`workflow_dispatch`) on `ubuntu-latest`. See [Usage](Usage.md) for setup
and a known case-sensitivity caveat with this workflow.
