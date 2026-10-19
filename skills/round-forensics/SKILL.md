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

Pointers into prediction-bot at `main` (READ 2026-10-19). The file governs; a value quoted here is "as of 2026-10-19". The framing itself is `blockchain-kit:record-format`; the seal is `blockchain-kit:research-surface`.

**The archive**

| Fact | Where |
|---|---|
| Segments: `/data/raw/<collector>/[<symbol>/]<day>/<HH>.log` while the hour is open, `<HH>.log.zst` once sealed (plain zstd: `zstd -dc`), each beside `<HH>.meta.json` (record counts, the ordering table, writer stamps) | `docs/specs/log-format.md` §2, §4; `ls /data/raw` (trees `bsc`, `binance-spot/BNBUSDT`, `binance-perp/{BNBUSDT,_allmarket}`, `bot/bot`) |
| The decision log: `/data/raw/bot/bot/<day>/00.log`, one daily segment (a restart opens an `<HH>.log` beside it); kind 200 `BotDecision` on `bot.decisions`, a JSON `strategy.DecisionSnapshot` keyed `"Epoch":N` | `internal/event/kind.go:136`; `cmd/etl/decode_bot.go` `botDecisionRow` (`json.Unmarshal` into the snapshot) |
| Control kinds 104 `RecorderStarted` / 105 `RecorderStopped` bracket every restart on the `""` stream; 106 `NodeReorg`; 15 removed frames on `bsc.heads` (ADR 0134) | `internal/event/kind.go:41,59-61`; `docs/specs/event-schema.md` §3, §6 |
| Decision record fields: pools in wei (confirmed, pending, late 5 s), evicted pending count and wei, own bet, the oracle, USDT/USD, perp and spot inputs with their stamps, target slot, margin, basis header, lock second, win probability, payout multiple; the versions and `CodeVersion` in `Provenance` | `internal/strategy/strategy.go` `DecisionSnapshot` (:362-518), `Provenance` (:229); ETL table `bot_decisions` (`cmd/etl/decode.go:117`; sealed days only, and the seal applies) |
| The perp mark differs between live and replay per round by construction: the bot and the collector run independent 30 s REST polls; the bot archives its own perp inputs on each decision | `cmd/bot/main.go:172` (`-premiumindex-interval`), `cmd/collector-binance-perp/main.go:374`; `docs/operations.md` §2.1 (the feed-timing class); prediction-bot#1110 |

**Reading tools**

| Tool | Prints | On a sealed day |
|---|---|---|
| `cmd/segdump -head N -tail 0 <seg>` | text rows: window, ordinal, kind, collector, stream, StreamSeq, LocalWallNs, UTC, body length (`writeRow`, `cmd/segdump/main.go:816`) | allowed: no payload |
| `cmd/segdump -json` | decoded payloads for the bsc and node kinds its `decodePayload` switch names; **no kind 200** (`cmd/segdump/main.go:468-635`; `docs/operations.md` §2.1, the r025-shadow check, step 6) | never |
| The decision-log reader and the round reader (`tools/`, `make decisions`, `make round`) | prediction-bot#1119 items 1-2, lane C of 2026-10-19: not on `main` at this writing; `ls tools/` before citing either | infra fields only, unless the dev snapshot root or an explicit, echoed override |

- Every product binary on the production host (`segdump` and `datatrust` included) runs through `scripts/replay-run.sh [--mem-max NG] [--cpus N] -- <bin> ...`; the kit's `guard-prod-run` hook refuses a bare run.
- A hand JSON walk over raw segment bytes is a known pitfall: an `rfind('{')` stops at a nested brace (the 2026-10-19 `decisions_check.py.txt` walks braces by depth for this reason). Unmarshal into `strategy.DecisionSnapshot` as `cmd/etl` does, or use the reader once it lands.

**The redeploy loop** (bot and collectors are the agent's to release, operator 2026-10-18; node deploys, real money and probe batches stay the operator's)

| Step | What | Where |
|---|---|---|
| 1 | `make binaries` at HEAD, under the cap; `tools/deploy_diff.py` names the class (`decision_basis_touched=yes` is decision-basis) | `docs/operations.md` §2.1 |
| 2 | Before every bot deploy the node's `parlia_getTurnLength` returns 8 | `docs/operations.md` §2.1 (decision-basis paragraph) |
| 3 | `sudo deploy/host/release.sh --units <units> --dry-run`, then the same without `--dry-run` | `deploy/host/release.sh` header; `docs/operations.md` §2.1 (r025-shadow check, steps 3-4) |
| 4 | The release log: one `<unit> stop=… start=… healthy=yes version=<the merge>` line per unit, then `exit 0` | `release.sh:869`; model `docs/reports/2026-10-19-four-unit-redeploy-records/release.log` |
| 5 | The journal since the release start: error count; `NRestarts` stays 0 | `docs/operations.md` §2.1 (r025-shadow check, step 5) |
| 6 | First decision: the first kind-200 record on the new `CodeVersion` carries the new fields and versions | the reader above, or the grep of `docs/operations.md` §2.1 (r025-shadow check, step 6) |
| 7 | `postdeploy_check` every hour (below), `--hours NN` two-digit; a decision-basis restart hour with `--allow-version-seam` | `tools/postdeploy_check.py` docstring |
| 8 | A collector restart is a hole: deprecation records, a `DatasetVersion` bump, the pin-test row. A bot-only restart records no hole | `docs/data-deprecations/README.md` (below) |
| 9 | Evidence in `docs/reports/<date>-<topic>/` with a row in its own `README.md`; every stamp from `date -u` | model `docs/reports/2026-10-19-four-unit-redeploy-records/README.md` |

**The post-deploy bar** (`tools/postdeploy_check.py`; it runs `datatrust` and replay through `scripts/replay-run.sh` itself)

| Line | GREEN |
|---|---|
| each datatrust tree | `gap=PASS`, `completeness=PASS`, `unexplained=0` |
| bot | completeness PASS; integrity `CLOSED` once the day is sealed, `OPEN` with only open-shaped failures expected mid-day |
| crosscheck | `flips=0`, `version_mismatch=0`, `feature_divergent_chain=0`, `config=aligned`, `feature_unclassified=0` |
| informational | `feature_divergent_feed_timing` (feed-timing only when every input its signal's `Reads()` names is a feed input; one chain input makes it chain: `internal/strategy/inputset.go`); `only_live`, the epochs the live bot decided and replay did not (`internal/scoring/crosscheck.go:54`); `beyond_window` (#1082) |
| `--allow-version-seam` | passes only a resolved seam: every mismatched round precedes every matched one, so the latest round runs replay's versions (`version_seam=allowed`); it never waives the flips or the feature bars |

Sources: `tools/postdeploy_check.py:1-200`; `docs/operations.md` §2.1. A RED is the deployer's to explain from the artifact.

**Deprecation records** (`docs/data-deprecations/README.md`)

| Rule | Where |
|---|---|
| One record per collector and incident, window `[RecorderStopped, RecorderStarted)` | §The W2 gap-gate records, "Restart brackets" (:329) |
| bsc: one record. Perp: one per source tree (`BNBUSDT`, `_allmarket`). Spot: five records under prefixes that name no perp stream when perp kept recording inside the spot bracket, else one `binance.` record | the same paragraph (:332); ADR 0135; prefix match `internal/exclusions/exclusions.go:121-122` |
| Adding or editing a record is a `DatasetVersion` bump in the same PR; `TestExclusionRecordsArePinnedToDatasetVersion` (`internal/scoring`) pins the directory digest | §Cache invalidation (:171) |
| A restart hole is expected, never a defect: record it and move on (operator 2026-10-14) | §Adding a record (:648); prediction-bot `CLAUDE.md` §Operator authorizations |

**What only this skill says**
- Measure a bracket from the sealed hour's text rows, never from the release log alone: the release log is REPORTED, the segment is MEASURED.
- Check new data within minutes of a restart, from raw, never at the next nightly.
- A claim from this loop names the commit, the hour window and each verdict line as printed.
