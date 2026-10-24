---
name: round-forensics
description: "prediction-bot's raw archive read by hand: one round, one decision record, a redeploy's checks, the post-deploy bar, a deprecation record."
---

**When to load:** reading a round or a decision from the archive, verifying a redeploy, running the post-deploy check, writing a deprecation record.

# Round forensics and redeploys

**Load when**
- Reading one round, one block window or one decision record out of `/data/raw`.
- Releasing the bot or a collector, or judging what the release recorded.
- Running or reading `tools/postdeploy_check.py`; writing a `docs/data-deprecations/` record.

A router: the facts live in prediction-bot, and this skill names where. Paths are in the pb
tree; a value is read there, in the tree you are changing, never from memory or from here. The
framing itself is `blockchain-kit:record-format`; the seal is `blockchain-kit:research-surface`.

**Where the facts live**

| Before you | Read |
|---|---|
| Open a segment: the archive layout, open and sealed hours, the sidecar | `docs/specs/log-format.md` §2, §4; `ls /data/raw` for the trees |
| Read the decision log: the day file, the restart bracket, kind 200 and its JSON shape | `docs/specs/bot.md` §3; `internal/event/kind.go`; `cmd/etl/decode_bot.go` (`botDecisionRow`, the unmarshal to copy) |
| Classify a control record: the recorder brackets, `NodeReorg`, removed frames | `docs/specs/event-schema.md` §3, §6 |
| Read a decision record's fields and versions | `internal/strategy/strategy.go` (`DecisionSnapshot`, `Provenance`); the ETL table `bot_decisions` (`cmd/etl/decode.go`; sealed days only, under the seal) |
| Compare a live decision with replay's: the feed-timing class, why the perp mark differs by construction | `docs/operations.md` §2.1 (the crosscheck line and its classes) |
| Dump a segment: text rows, decoded payloads, what `-json` does not decode, the brace-walk pitfall | `docs/operations.md` §2.1 (Reading what a redeploy recorded, by hand); `cmd/segdump/main.go` (`writeRow`, `decodePayload`); `ls tools/` for the readers that exist |
| Release a unit: the class (`tools/deploy_diff.py`), the turn-length check before a bot deploy, the dry run, the release log's line per unit | `docs/operations.md` §2.1 (Deploy checklist; the r025-shadow check's steps); `deploy/host/release.sh` header |
| Judge a release: the post-deploy bar line by line, `--hours`, `--allow-version-seam`, what the check does not prove | `tools/postdeploy_check.py` docstring; `docs/operations.md` §2.1 |
| Record a restart: one record per collector and incident, the bracket window, the per-tree split, the `DatasetVersion` bump and the pin test | `docs/data-deprecations/README.md` §The format, §Cache invalidation, §Adding a record; `internal/exclusions/exclusions.go` (the prefix match) |
| Leave evidence: the report directory and its own table | `docs/discipline.md` rules 49, 50; any directory under `docs/reports/` |

**What only this skill says**
- Every product binary on the production host (`segdump` and `datatrust` included) runs through `scripts/replay-run.sh [--mem-max NG] [--cpus N] -- <bin> ...`; the kit's `guard-prod-run` hook refuses a bare run.
- Measure a bracket from the sealed hour's text rows, never from the release log alone: the release log is REPORTED, the segment is MEASURED.
- Check new data within minutes of a restart, from raw, never at the next nightly.
- A restart hole is expected, never a defect: record it and move on. A bot-only restart records no hole.
- A claim from this loop names the commit, the hour window and each verdict line as printed; every stamp from `date -u`.
