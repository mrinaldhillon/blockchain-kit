---
name: contract-abi
description: >-
  Use when decoding or encoding on-chain data for the PancakeSwap Prediction V2
  contract or the Chainlink BNB/USD and USDT/USD aggregators — event logs,
  calldata, packing a bet, the embedded ABI in `internal/parsers` — or
  converting a numeric on-chain value for state or strategy. Trigger before
  abigen or any `getLogs`/`FilterLogs` call.
---

# Decode and pack directly through the fork's `accounts/abi`

Contract interaction in this project goes **straight through the fork's
`accounts/abi`** (`abi.JSON`, `Unpack` / `UnpackIntoInterface`, `Pack`) over an
**embedded ABI JSON** (`go:embed`, compile-time-immutable; event-schema §7,
design-notes §3.12). The ABI is the only package-level data in a parser, which
keeps parsers pure (rule 13).

## Forbidden

- **No abigen-generated wrappers.** Do not run abigen and do not depend on
  generated `*.go` bindings.
- **No backend-bound contract objects.** No `bind.NewBoundContract`, no
  filterer, no transactor. These couple parsing/packing to a live backend and
  hide the wire bytes the recorder must preserve.
- **No `getLogs` / historical `FilterLogs`** (`fork-node-api`). History is
  reconstructed by replaying the recorder stream, never re-fetched.

## Required

- **Pure decode of `Raw`.** `internal/parsers` decodes an event's `Raw` (canonical
  RLP of `types.Log`, or the typed-tx envelope for calldata) into typed values.
  `Parse(ev *event.Event)` is a pure function of `(ev.Raw, envelope chain
  fields)` — no clock, no I/O, no mutable globals (`replay-parity` §The three
  properties, property 1; rules 13, 15).
- **Fixed-point numerics, never `float`.** Decoded amounts and prices are
  fixed-point `int64`/E8. Confirmed pool sums fold integer wei in a deterministic
  order and convert once (state §3.4). A `float` reaching a published value
  breaks parity (rule 15).
- **Addresses as arguments, not globals.** Pass the Prediction and Chainlink
  addresses in. The Chainlink **proxy can rotate to a new aggregator**, so
  hard-coding the aggregator address is wrong (design-notes §8.4).
- **The bet amount is `msg.value`.** A Prediction bet's amount is the
  transaction value, not a calldata argument (state §3, design-notes §6.7).
  Parse direction from calldata, amount from `msg.value`; on any discrepancy with
  the confirmed `BetBull`/`BetBear` log, the log is authoritative.
- **Signing lives in the executor (M3).** Decode/pack code never signs. Nonce
  sequencing and submission are centralized in `internal/executor` (rules 21,
  24); `strategy/` cannot import `executor/`.
- **The executor embeds its own pack-only ABI, separate from `internal/parsers`'
  decode ABI.** Because `strategy ⊥ executor` (rule 21) rules out `executor`
  importing `parsers`, `internal/executor/abis/prediction_bet.abi.json` is a
  deliberate, minimal (`betBull`/`betBear`/`claim`) boundary-driven duplicate of
  three immutable deployed-contract signatures — a pack surface, not a decode
  surface, so it carries no data-consistency coupling to the recorder (ADR
  0019). Same rule applies: straight `accounts/abi.Pack`, no abigen.

## Contracts (architecture §8.3, §8.4)

- **Prediction V2** `0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA`. Events:
  `StartRound`, `LockRound`, `EndRound`, `BetBull`, `BetBear`, `Claim`, `Pause`,
  `Unpause`, `RewardsCalculated`, plus admin parameter events. Treasury fee,
  interval, and minimum bet are derived from admin-event logs (one startup read
  then maintained from logs), never hardcoded and never read via hot-path RPC
  (rule 25).
- **Chainlink BNB/USD** — dynamic (ADR 0008): `Prediction.oracle()` → proxy
  `0x0567F2323251f0Aab15c8dFb1967E4e8A7D42aeE` (`description()=="BNB / USD"`,
  `decimals()==8`); `proxy.aggregator()` → underlying OCR aggregator (rotates —
  never pin). Events embedded (live-verified — `parsers_live_test.go`):
  `AnswerUpdated`, `NewRound` — subscribe on the **aggregator**, not the proxy.
  `NewTransmission` + OCR `transmit()` calldata (pre-aggregation front-run signal)
  are **deferred** to the gated capture (M2/M4); the ABI is intentionally **not
  embedded**. **USDT/USD** aggregator
  `0xB97Ad0E74fa7d920791E90258A6E2085088b4320` (stablecoin-stress regime gating,
  M4/WS3, ADR 0020).
- **PCSRouterV2** — the minimal PancakeSwap V2 router surface (the nine
  `swap*` methods only, no events), embedded at M5a (ADR 0021) to decode WBNB-path
  swap **calldata** off the isolated mempool stream `bsc.pending.swaps` (M4/WS4,
  ADR 0020) at read time (`bsc.ParsePendingSwap`, `internal/parsers/bsc/swap.go`).
  Unlike Prediction/Chainlink, this is a **pack-and-unpack-by-selector** surface
  (`MethodById` + `Inputs.Unpack`), not an event-log ABI — an unrecognized
  selector is not an error (the stream carries non-swap router calls too).

## Checklist

- [ ] ABI is embedded (`go:embed`), decode/pack via `accounts/abi` only.
- [ ] No abigen wrapper, no bound contract, no `getLogs`.
- [ ] Parse is pure over `(Raw, chain fields)`; numerics are `int64`/E8.
- [ ] Addresses passed in, not hard-coded (Chainlink rotation).
- [ ] Bet amount from `msg.value`; confirmed log is authoritative on mismatch.
- [ ] No signing here — that is the executor's job at M3.
