# viaggiatori-agent

A personal flight-price-alert agent. For each configured travel profile
(origin airports, destination, date range, budget), it searches Google
Flights via SerpAPI, stores daily price snapshots in S3, asks Claude to
decide whether the results are a good enough deal to alert on, and emails
the result via Gmail. It's designed to run daily on a schedule.

## Documentation

- [Architecture](docs/Architecture.md) — pipeline overview and data flow
- [Installation](docs/Installation.md) — setup, dependencies, and credentials
- [Usage](docs/Usage.md) — configuring travel profiles, running the agent, and alert rules