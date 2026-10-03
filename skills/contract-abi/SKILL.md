---
name: contract-abi
description: >-
  Use when decoding or encoding on-chain data for the PancakeSwap Prediction V2
  contract, the Chainlink BNB/USD and USDT/USD aggregators, or PancakeSwap
  router calldata — event logs, calldata, packing a bet, the embedded ABI in
  `internal/parsers` and the pack ABI in `internal/executor` — or converting a
  numeric on-chain value for state or strategy. Trigger before abigen, a bound
  contract, or any `getLogs`/`FilterLogs` call.
---

# Contract ABI

**Load when**
- Writing or reviewing a decoder in `internal/parsers` or a pack in `internal/executor`.
- Touching a contract address, an embedded ABI, or an on-chain amount or price.
- About to reach for abigen, `bind`, or `getLogs`.

**Where the facts live** (pb repo paths)

| Topic | Doc |
|---|---|
| Parser purity; `accounts/abi` over `go:embed` ABIs; what is forbidden | `docs/specs/event-schema.md` §7 |
| Decoder per kind and stream; router selector dispatch | `docs/specs/event-schema.md` §7 (table) |
| Unmodeled router selectors | `docs/specs/state.md` §5b |
| `Raw` of a log and of a pending tx | `docs/specs/nodeapi.md` §3 |
| Prediction V2 address, events, admin-derived params | `docs/architecture.md` §8.3; `docs/discipline.md` rule 25 |
| Chainlink BNB/USD and USDT/USD: proxy, aggregator rotation, deferred OCR events | `docs/architecture.md` §8.4 |
| Topic0s, live-verified vs pinned events, resolved addresses | `docs/fork-knowledge/data-shapes.md` (header; §Chainlink BNB/USD, its USDT/USD regime gate) |
| Bet amount and the confirmed log's authority | `docs/decisions/0007-bet-amount-is-msg-value.md`; `docs/specs/state.md` §3 |
| Fixed-point E8, integer-wei folds | `docs/specs/event-schema.md` §7; `docs/specs/state.md` §2; `docs/discipline.md` rule 15 |
| Executor's pack-only ABI; signing; nonce | `docs/decisions/0019-m3-executor-leaf-and-live-execution.md`; `docs/architecture.md` §6; `docs/discipline.md` rules 21, 24 |
| Who may import whom | `docs/architecture.md` §3 (Package Boundaries) |

**Commands that answer questions**
- `make test-offline` (Makefile) — decoders against frozen fixtures.
- `make boundary-lint` (Makefile) — the §3 table and the depguard rules agree; `make lint` enforces depguard.
- `go test -tags parsers_live ./internal/parsers` (`internal/parsers/parsers_live_test.go`) — NETWORK, read-only: the embedded ABIs against a running node.
- gopls MCP `go_package_api` on `github.com/ethereum/go-ethereum/accounts/abi` (`.mcp.json`) — the `accounts/abi` API at the pin.

**What only this skill says**
- Cite an `accounts/abi` call at the pin (`blockchain-kit:fork-lookup`), never from upstream docs or memory.
- Node reads, and why there is no `getLogs`: `blockchain-kit:fork-node-api`.
- Before landing a decode or pack diff, check it against event-schema §7 and the §3 boundary table; a parser change reaches replay (`blockchain-kit:replay-parity`).
