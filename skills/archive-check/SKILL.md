---
name: archive-check
description: "prediction-bot's archive integrity run: one tool, tools/archive_check.py, for a redeploy's checks, the end-of-day pass, an archive-wide audit, or one stream's health; never a throwaway script."
---

**When to load:** the operator asks for integrity tests or a data check; a redeploy of a collector,
the bot or geth just happened; the end-of-day pass in the runbooks; a question about one stream's
recording (gaps, duplicates, corruption, cadence); before writing a deprecation record from a seam.

# The archive check

The recorder log is irreplaceable (pb CLAUDE.md, design-notes §2), so every question of the form "is
what we recorded intact, consistent and complete?" is answered by one tool and read from its report,
never by a script written for the occasion (operator, 2026-10-27). The tool is
`tools/archive_check.py`; its docstring is the contract (stages, verdict map, exit codes, flags).
`blockchain-kit:round-forensics` stays the skill for reading one round or one decision by hand and for
writing the deprecation record a seam needs.

**What one run does, per archive day** (the tool's stages 0–3): the sidecar census (records per
stream per hour, writer versions), `cmd/datatrust` per tree (the gap gate against the
`docs/data-deprecations` windows, the integrity gate over every byte, the feed-contract scan on bsc),
the ETL partitions at the decode level, and the Binance content checks (exchange-id contiguity and
arrival order, the 20-level books, snapshot cadence and the spot anchoring rule, diff continuity,
`stream_seq`, REST cadence, exchange-clock skew). One per-stream table: FLAG is a broken invariant,
INFO is a number with its range, ERROR is a reader that could not reach its verdict (rule 44).

**Which invocation** (always capped, always the DuckDB environment; the Makefile target does both):

| Occasion | Command |
|---|---|
| End of day (yesterday's sealed day, every tree, every byte) | `make archive-check DAYS=yesterday` |
| Right after a redeploy, before the hour seals | `make archive-check DAYS=$(date -u +%F) ARGS='--allow-open --hours HH,HH --tree <restarted trees>'` (stages 0–1 only; the content stage needs the ETL partition, so the full read is the next day's `DAYS=`) |
| The post-deploy bar on the next full day | `make postdeploy DAY=` (the live-vs-replay crosscheck) AND `make archive-check DAYS=` (the recording) |
| One stream's health over a window | `make archive-check DAYS=2026-10-20,2026-10-26 ARGS='--stream binance.bnbusdt.depth --no-integrity'` |
| The whole archive (hours; resumable, datatrust reports reused) | `make archive-check DAYS=all` |

**Reading the report.** `/data/reports/archive-check/<day>/result.json` holds every row;
`report-<from>-<to>.md` the per-stream table. Three readings the baseline settled
(`docs/measurements/2026-10-binance-archive-check/results.txt`, 2026-10-27): duplicate and
out-of-order spot fills and a decreasing `last_update_id` on `@depth20` are the SBE overlap rotation
by design and are deduplicated at read time, never a recorder defect; a `stream_seq` jump is judged
by datatrust's gap gate against the deprecation windows, not by the content stage; a perp
`prev_update_id` chain break is one per reconnect. A FLAG row is a finding: read the raw records
(`blockchain-kit:round-forensics`) and either fix the writer in the batch or write the deprecation
record. A new metric is INFO until it is added to `FLAG_METRICS` with the invariant it names, with
the test row beside it (`tools/tests/archive_check_test.py`).

**What it does not do.** It never changes the archive, never restarts a unit, and reads no payload a
round-level question needs (bets, prices, outcomes). It is not the replay-parity gate and not the
post-deploy crosscheck. A daily service around it is deferred (operator, 2026-10-27: the tool first).
