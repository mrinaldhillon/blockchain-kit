---
name: binance-streams
description: "Binance market data in prediction-bot: SBE and JSON streams, depth snapshots, reconnects, the proxy."
---

**When to load:** Use when capturing, framing, or decoding Binance market data — SBE @depth20 / raw @trade, JSON @aggTrade, REST depth snapshots, USD-M perp streams and forceOrder, the SBE schema, the Ed25519 key, the 24h connection limit / overlap-reconnect, or the dev SOCKS5 proxy. Trigger for internal/binance, collector-binance-spot and collector-binance-perp, and the binance parsers (internal/parsers/binance).

# Binance streams

**Load when**
- Editing `internal/binance`, `cmd/collector-binance-spot`, `cmd/collector-binance-perp` or `internal/parsers/binance`.
- Answering what a Binance stream carries, where it connects, or how a connection rotates.
- Adding a symbol, a stream, a poller or a decoder.

**Where the facts live** (pb repo paths)

| Topic | Doc |
|---|---|
| Recording set: streams, kinds, sources | `docs/specs/recorder-binance.md` §2, §2.1, §2.2 |
| Perp hosts and routed bases | `docs/specs/recorder-binance.md` §2.1; `docs/decisions/0027-forceorder-recovery-endpoint-routing-misdiagnosis.md` |
| Spot hosts, one connection per stream, 24h rotation, overlap, timer defaults | `docs/specs/recorder-binance.md` §3 |
| API key, `X-MBX-APIKEY`, ping/pong, proxy scope, symbol case | `docs/specs/recorder-binance.md` §3.1 |
| Envelope mapping, pollers, watchdog, `Poller.Valid` | `docs/specs/recorder-binance.md` §4 |
| Bot-consumed vs recorder-only streams; no `bookTicker` | `docs/specs/recorder-binance.md` §2, §5 |
| SBE `blockLength` validation | `docs/specs/recorder-binance.md` §8 inv. 9 |
| Decode side: schema dispatch, fail-loud, fixed-point | `docs/specs/binance.md` |
| Wire shapes, SBE header, templateIds, body offsets, `serverShutdown` | `docs/fork-knowledge/data-shapes.md` §Binance |
| Decoder per kind | `docs/specs/event-schema.md` §7 (table) |
| Fixture layout, frozen schema XML | `docs/specs/fixtures.md` §Layout |
| Proxy precedence, dev vs prod egress | `docs/operations.md` §7 |
| Overlap-reconnect vs process restart | `docs/operations.md` §8 |
| Parquet output per kind | `docs/architecture.md` §4.4 |
| Claiming a stream is unavailable | `docs/discipline.md` rule 46 |

**Commands that answer questions**
- `make test-offline` (Makefile) — the suite with Binance down, on frozen fixtures.
- `go test -tags binance_live ./internal/binance` (`internal/binance/live_smoke_test.go`) — NETWORK: live raw frames through the configured egress.
- `make fixture-capture` (Makefile) — NETWORK, prod host, operator-approved; the `blockchain-kit:fixture-capturer` agent's job.

**What only this skill says**
- Take a wire shape from `docs/fork-knowledge/data-shapes.md` or a frozen fixture, not from Binance's public docs or memory alone.
- Endpoint and proxy resolution: load `blockchain-kit:environment-detection`.
- Before writing that Binance withholds or lacks a stream, run the rule-46 check (docs and a probe); ADR 0027 records what a one-sided probe cost.
