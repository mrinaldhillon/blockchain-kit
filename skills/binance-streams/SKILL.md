---
name: binance-streams
description: >-
  Use when capturing, framing, or decoding Binance market data — SBE @depth20 /
  raw @trade, JSON @aggTrade, REST depth snapshots, the SBE schema, the Ed25519
  key, the 24h connection limit / overlap-reconnect, or the dev SOCKS5 proxy.
  Trigger for internal/binance, collector-binance-spot, and the binance parsers.
---

# Binance streams (M1 BNBUSDT spot)

Spec: `docs/specs/recorder-binance.md` (and `docs/specs/binance.md`). M1 captures
RAW and round-trips it; all decoding is deferred (read-time pure functions).

## Endpoints
- **SBE market data** `wss://stream-sbe.binance.com`: `@depth20` (50ms,
  self-contained top-20 snapshots — a dropped frame self-heals on the next, no
  resync machinery) and raw `@trade` (archival, recorder-only). Microsecond
  timestamps. **Ed25519 key required in the `X-MBX-APIKEY` connect header**
  (public market data needs no signature). SBE can multiplex ≤1024 streams on one
  connection, but **M1 uses one path-based connection per stream**
  (`/ws/<symbol>@depth20`, `@trade`): raw SBE frames aren't self-identifying
  before decode, so stream identity must come from the connection, not the bytes
  (`internal/binance`; observed @depth20≈682 B, @trade≈115 B — data-shapes.md).
- **JSON** `wss://data-stream.binance.vision`: `@aggTrade` (SBE has no aggregated
  trade). The legacy `stream.binance.com/public` path was decommissioned upstream. M1 connects to the single-stream path `/ws/<symbol>@aggTrade`, which
  yields the **bare** event `{e:"aggTrade",E,s,a,p,q,f,l,T,m,M}` (NOT the combined
  `{"stream":…,"data":…}` wrapper — that's only on `/stream?streams=`).
- **REST** `https://api.binance.com`: periodic full-depth snapshots (deep-book
  optionality), IP-weight-limited → low cadence with headroom.

## Connection lifecycle
A single SBE connection is valid for **24h**; a `serverShutdown` event is sent
**~10 minutes before** disconnect. M1 uses a **deterministic timer** at
`ConnTTL - OverlapLead` (default 23h50m) — the timer fires before the server's
notice so there is no gap without parsing `serverShutdown`. Handling
`serverShutdown` as an early-trigger is deferred until its SBE frame shape is
captured (data-shapes.md "to fill"). **overlap-reconnect** — open the new
connection before the old drops — is the mechanism regardless (operations.md §8).
Server pings ~every 20s; pong within 60s.

## Schema versioning
SBE schemas are XML; the deployed BNBUSDT spot schema is **`spot_1_0.xml`**
(schemaId=1, version=0 — confirmed live — data-shapes.md ## Binance). The
8-byte LE frame header carries `[blockLength][templateId][schemaId][version]`
(@depth20 templateId=10002, @trade=10000). Store the **exact schema XML in
`testdata/fixtures/binance/sbe/schema/`**. On a schema-id/version change, emit a
versioned record/log line and alert; Binance retires deprecated schemas on a
~6-month cycle.

## Dev vs prod
Dev egresses via SOCKS5, prod direct; the proxy literal, its precedence, and the
Binance-only rule are `environment-detection` §Resolution order (highest wins) and
§Rules. The bot consumes `@depth20` + `@aggTrade`; raw `@trade` and REST snapshots are
recorder-only. No `bookTicker` (price derives from the depth20 top level).

## Perp / USD-M futures (M4 activation, M5a decode)
`collector-binance-perp` is active from M4 (kinds 8/9/10; `EventKind`
`BinancePerpDepth20`/`Trade`/`PremiumIndex`). Unlike spot, futures market data is
**bare JSON, not SBE** — `fstream.binance.com` `/ws/<symbol>@depth20@100ms` and
`/ws/<symbol>@trade` (single-path connections, same convention as spot
`@aggTrade`: no `{stream,data}` wrapper); `premiumIndex` (mark price + funding)
is REST-only at `fapi.binance.com` `/fapi/v1/premiumIndex` — an
outcome-acceptable archival source for mark+funding, kept. Perp WS streams are
**routed** (ADR 0027): `@depth20`/`@trade`/`bookTicker` on `/public`,
`forceOrder`/`markPrice`/`aggTrade` on `/market`; the legacy unrouted
`/ws` serves `/public` only. `forceOrder`
(liquidations) is recovered via `/market/ws/!forceOrder@arr` (kind 11,
record-only) and, being symbol-independent, records under its OWN source
`binance-perp/_allmarket` (`feedid.CollectorBinancePerpAllMarket`) via a second
in-process recorder that opts out of the all-feeds-down backstop — one owner
instance per host (`-allmarket-forceorder`, default true; ADR 0073, #87);
`markPrice` info is archived via `premiumIndex` REST; futures
`aggTrade` is neither collected nor derived (data-shapes.md perp-routing note). Read-time decoders (`internal/parsers/binance/perp*.go`:
`ParsePerpDepth20`/`ParsePerpTrade`/`ParsePerpPremiumIndex`) were built at M5a
(ADR 0021) — pure JSON→E8 decode, fixture-round-tripped; `cmd/etl`'s Parquet
writer does not yet have structured tables for these kinds (still the generic
`events.parquet` fallback — a separate, unstarted ETL workstream).
