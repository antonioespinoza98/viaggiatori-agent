# Usage

## Configuring travel profiles

Travel profiles live in `config.yml` under `profiles:`. Each profile is read
by `SearchOrchestrator`, `SerpapiClient`, `Analyzer`, and `GmailNotifier`, and
must include all of the following keys:

| Key | Description |
|---|---|
| `name` | Display name for the profile (used in logs, emails, and the S3 key prefix) |
| `origins` | List of departure airport IATA codes to search from |
| `destination` | Destination airport IATA code |
| `date_from` | Earliest possible outbound date (`YYYY-MM-DD`) |
| `date_to` | Latest possible return date (`YYYY-MM-DD`) |
| `trip_duration_days` | Length of the trip in days |
| `window_step_days` | Step size (in days) between search date windows |
| `budget` | Target price per person, in `currency` |
| `currency` | ISO currency code (e.g. `EUR`) |
| `passengers` | Number of passengers |
| `max_stops` | Most stops the user will accept (`0` = nonstop, `1` = up to 1 stop, `2` = up to 2 stops) |
| `notify` | Email address to send alerts to |

Example:

```yaml
profiles:
  - name: "You - Costa Rica"
    origins:
      - AMS
      - BRU
      - DUS
    destination: SJO
    date_from: "2026-12-18"
    date_to: "2027-01-30"
    trip_duration_days: 14
    window_step_days: 14
    budget: 500
    currency: EUR
    passengers: 2
    max_stops: 2
    notify: you@example.com

settings:
  alert_threshold_pct: 10
  runs_per_day: 1
  price_history_days: 90
```

Global `settings`:

| Key | Description |
|---|---|
| `alert_threshold_pct` | Alert if price is within this percentage above `budget` |
| `runs_per_day` | Informational — how many times per day the schedule runs the agent |
| `price_history_days` | Max number of days of S3 snapshot history `PriceHistory.load_history` can read |

To add a new destination, add another entry under `profiles:` with all of the
keys above.

## Running manually

```bash
python src/main.py
```

For each profile, the agent:
1. Searches Google Flights across all date windows for the profile.
2. Saves a price snapshot to S3.
3. If flights were found, sends them (plus the 7-day price history) to Claude
   for analysis.
4. If Claude decides the result is a good enough deal (`alert: true` with a
   `best_flight`), sends an email to `notify`.

## Alert rules

Claude (`Intelligence/Analyzer.py` + `Intelligence/Prompts.py`) decides
whether to alert based on:

- Price at or below `budget`, or within `alert_threshold_pct` percent above it
- Fewer stops, shorter duration, and reasonable layovers are preferred
- No alert if the only options have layovers longer than 8 hours (unless
  overnight) or more stops than `max_stops`
- `trend` (`rising` / `falling` / `stable` / `insufficient_data`) is derived
  from comparing today's price to the 7-day average

## Running on a schedule

`.github/workflows/FlightAgent.yml` runs the agent daily via cron (and
supports manual triggering via `workflow_dispatch`). It expects the same
secrets listed in [Installation](Installation.md) to be configured as GitHub
Actions repository secrets.

**Known issue:** the workflow currently invokes `python src/Main.py`
(capital `M`), but the file is `src/main.py`. This only works on
case-insensitive filesystems and will fail on the `ubuntu-latest` runner the
workflow uses — update the workflow to `python src/main.py` before relying on
the scheduled run.
