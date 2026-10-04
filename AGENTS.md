# Repository instructions

These instructions apply to the entire repository. Read `README.md`, `HISTORY.md`,
and `.agents/rules/privacy-policy.md` before changing the relevant behavior.

## Purpose and architecture

This is an extension of Ute2MQTT, retaining the original billing client
and adding measured quarter-hour consumption from the UTE self-service portal.
Keep the two flows independently runnable and preserve existing billing behavior.

- `main.py`: billing orchestration and MQTT publication.
- `scheduler.py`: daily randomized AM/PM billing schedule.
- `setup.py`: interactive authentication, account selection, and encrypted setup.
- `ute/auth.py`, `ute/session.py`, `ute/client.py`: OAuth, token renewal, and billing API.
- `ute/credentials.py`: encrypted credentials and tokens; reuse this implementation.
- `ute/tariffs.py`: tariff and consumption-band processing.
- `ute/mqtt.py`: shared MQTT connection and original billing discovery/state.
- `history_main.py`: history CLI, polling, and graceful shutdown.
- `ute/history/portal.py`: authenticated portal HTTP and thirty-day request batches.
- `ute/history/normalize.py`: validation and UTC normalization of measured intervals.
- `ute/history/store.py`: SQLite persistence scoped by service point and interval start.
- `ute/history/publish.py`: retained daily history payloads, index, and discovery.
- `tests/`: offline unit and orchestration tests using synthetic data and mocks.
- `Dockerfile`, `docker-compose.yml`: Python 3.11 container; billing and history services.

## Development

Run commands from the repository root. Use Python 3.11+ with OpenSSL for real
HTTP requests; the container provides that runtime. Use a local virtual environment:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python history_main.py --help
git diff --check
```

There is no configured formatter, linter, or packaging build. Do not claim checks
that are not present or introduce new tooling without a task-related reason.
Keep dependencies in `requirements.txt` and verify compatibility with Python 3.11
and the MQTT client versions it permits.

Configuration templates belong in `.env.example`; never put real values there.
Docker Compose reads `.env`. Native entry points expect exported environment
variables and do not load `.env` automatically. Document new configuration in the
appropriate README or `HISTORY.md`, including defaults and persistence requirements.

## Code quality

Use small functions, descriptive names, explicit module boundaries, and type hints
where useful. Follow nearby style; use four spaces and avoid unrelated formatting
changes to inherited code. Explain data semantics and non-obvious decisions in
docstrings, not every line. Keep HTTP, validation, storage, and publication separate.
Prefer targeted fixes to broad rewrites and maintain the original tariff behavior.

Use explicit HTTP timeouts, validate responses before writing measurements, and
close sessions and MQTT connections on failure. Report actionable errors without
including sensitive payloads. Preserve shutdown by SIGINT/SIGTERM and interruptible
polling. Do not swallow errors in a way that reports an unsuccessful sync as success.

## Measurement invariants

- Query portal grouping `QH` with magnitude `IMPORT_ACTIVE_ENERGY`.
- Values are measured energy in kWh over fifteen minutes, not instantaneous power.
- Query dates are inclusive in `America/Montevideo`; stored keys are aware UTC
  interval-start timestamps. Portal timestamps are Unix milliseconds.
- Accept real zero. Omit nulls and intervals not yet completed. Never interpolate,
  invent zero for missing data, or describe delayed readings as live/minute data.
- Reject negative/non-finite energy, booleans, misaligned timestamps, out-of-range
  dates, conflicting duplicate intervals, and absent/ambiguous energy series.
- Merge idempotently by service point and timestamp. New measured values replace
  old values; nulls do not currently erase an existing measurement.
- Save a successful download before MQTT publication so broker failure can be retried.
  Preserve service-point isolation and transactional writes.
- Schema changes need migration/backward compatibility; do not silently discard
  databases or retained history. Back up SQLite with the writer stopped.

## MQTT and Home Assistant contracts

Preserve billing topics and discovery IDs. History uses a separate `history`
namespace under the configured topic prefix and service ID. Daily chunks are
partitioned by UTC day, with local timezone metadata for display. Keep
`schema_version`, interval timestamps, units, index, and state consistent with
`HISTORY.md`; document incompatible changes and provide a migration strategy.

History messages use retained QoS 1 publication and wait for broker acknowledgement
before disconnecting. Empty downloads must not publish a false zero reading.
The last-interval sensor has `state_class: measurement`, not `total_increasing`.

MQTT sensor states cannot backfill Home Assistant recorder. Do not replay old
measurements as current readings. Importing historical statistics requires a
separate consumer/integration outside this repository. Do not claim this repo alone populates the Energy dashboard.

## Testing and verification

Run the offline suite after code changes. Add meaningful tests for behavior changes,
especially normalization, local/UTC and year boundaries, missing data, corrections,
service isolation, request batching, and publication failure/retry. Mock HTTP/MQTT
and use temporary databases; never require personal credentials in automated tests.
For documentation-only edits, check commands and paths and run `git diff --check`.

Only run real setup, authenticated requests, broker publications, deployment, or
Home Assistant changes when within the user's authorized scope. `setup.py` clears
existing credential configuration and prints private setup values; do not run it
as a harmless smoke test or expose its output. Do not start long-running services
for routine offline validation. State clearly which checks were simulated and which
used real services; do not infer live validation from passing mocks.

## Privacy and security

Follow `.agents/rules/privacy-policy.md` across all files, fixtures, logs, and reports.
Never commit real identity/account/service identifiers, addresses, passwords, keys,
tokens, cookies, raw API responses, consumption history, or unredacted setup output.
Use placeholders or unmistakably synthetic fixtures. Avoid logging HTTP bodies,
auth headers, exception URLs with sensitive parameters, and private billing values.
Keep TLS verification enabled and reuse encrypted credential storage.

`.env`, `credentials/`, `data/`, `.venv/`, SQLite files, and macOS metadata must stay
ignored. Keep secrets and runtime data out of Docker build contexts as well. Review
staged content before committing; never copy secrets from adjacent workspace projects.
