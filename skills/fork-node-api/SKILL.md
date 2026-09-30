---
name: fork-node-api
description: >-
  Use for any BSC node interaction — RPC calls, subscriptions,
  head/log/pending streams, broadcast, block-time, reorg detection,
  `internal/nodeapi`. The node is a PRIVATE FORK: trigger before citing any
  go-ethereum/geth/ethclient API or assuming a method exists, and for
  MilliTimestamp, MixDigest, NodeReorg.
---

# Node API resolves against the fork, never upstream

The BSC node is a private fork: **`github.com/mrinaldhillon/bsc-geth`**, branch
`mrinal/dev` (a local checkout is opt-in via `BSC_FORK_PATH` — ADR 0015; default builds
use the pinned module). Discipline rule 38. The custom subscriptions, the millisecond
block time, and the fast-path broadcast exist **only** in this fork.

**Rule:** never answer a node/RPC question from upstream `go-ethereum` or
`bnb-chain/bsc` documentation or memory. If an API is not confirmed in the fork
source, treat it as not existing for this project. When you assert an API,
cite `file:line` in the fork.

> **Import is settled (ADR 0002).** Consume the fork via `require` the upstream
> path + `replace` to a fork pseudo-version + repeat the fork's transitive
> replaces + `GOPRIVATE` + `BSC_FORK_TOKEN`. This is decided; do not relitigate
> the build wiring. Consult `docs/fork-knowledge/` (prose + `symbols.json`)
> before reading the fork tree, and only re-parse on drift
> (`bsc-fork check`, `make fork-knowledge-check`) or a missing symbol (the
> `blockchain-kit:fork-lookup` skill; one row is `bsc-fork show <Symbol>`).
> For a live read, prefer the gopls MCP tools (`go_search`,
> `go_symbol_references`, `go_package_api`) over grep when the fork is in your
> workspace (`go.work` active) — they return `file:line` directly.

## Verified fork bindings (from `docs/specs/nodeapi.md §4`)

Confirmed against the fork at the SHA recorded in `symbols.json` (`fork_sha`).
These are the only node entry points M1 uses.

- **Heads** — standard `ethclient.SubscribeNewHead` (`eth_subscribe("newHeads")`).
  `BlockTimeMs` is the node's **`MilliTimestamp`**: `header.MilliTimestamp()` =
  `Time*1000 + ms` with ms in the last two bytes of `MixDigest` per BEP-520
  (Lorentz), consensus-derived
  and regenerable from the persisted RLP header. It survives WebSocket because
  `RPCMarshalHeader` emits `mixHash` (whole-second boundary ⇒ `MixDigest == 0` ⇒
  `ms == 0`). No custom head RPC.
- **Logs** — standard `ethclient.SubscribeFilterLogs`, one subscription per
  contract: Prediction V2 (`0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA`) and the
  Chainlink BNB/USD aggregator. **Subscriptions only — `getLogs`/historical
  `FilterLogs` is never called.**
- **Pending (relevant)** — the **CUSTOM fork subscription**
  `gethclient.SubscribeFullPendingTransactionsByTosExt(ctx, tos, ch)` →
  `eth_subscribe("newPendingTransactionsByTosExt", tos, true)`
  Server-side filtered by `tos`; the `true` flag returns full transactions so raw
  calldata is captured. **M1 `tos` = Prediction + Chainlink only**; the isolated
  second subscription for PCS routers (`bsc.pending.swaps`) is M4/WS4 (ADR 0020),
  decoded at read time (`bsc.ParsePendingSwap`) at M5a (ADR 0021). NOTE: the
  parse-once bootstrap confirmed the custom names against the fork source —
  `symbols.json` carries `verified: true` for
  `SubscribeFullPendingTransactionsByTosExt`, `sendTxFastExt`,
  `SendRawTransactionExt` and `--txpool.localfastpropagationext`. A name is
  trusted only while that flag holds at the current pin; a pin move invalidates
  every `verified` flag until `make fork-index` regenerates the index
  (`make fork-knowledge-check` only proves the index is for the current pin, not
  that a name survived).
- **Broadcast** — the CUSTOM `eth_sendRawTransactionExt` via
  `gethclient.SendRawTransactionExt`
  (`ethclient/gethclient/feed_ext.go:126@a0af46223e21`): the same envelope as
  `eth_sendRawTransaction`, returning
  `SendResultExt{hash, sentMillis, fanout?, skipped}`. The three skip strings
  pass through byte-exact; the inserter rejections -39001/-39002 arrive
  unwrapped as `rpc.Error` and are read by CODE via `errors.As`, never by
  message; a stock node answers -32601, so this build cannot send on one.
  Whether the fast fan-out runs is the node-side
  `--txpool.localfastpropagationext` flag
  (`cmd/utils/flags.go:539@a0af46223e21`), never a call argument. The start-up
  probe is `eth_featureStatusExt` (`Commit` = `buildExt.commit`,
  `InserterActive` = `localTxInserterActiveExt`, `Raw` verbatim = the kind-110
  payload). The rest: `docs/specs/nodeapi.md` §4 Broadcast / Feature status and
  `docs/fork-knowledge/node-api.md` §Broadcast.

## Reorg detection is head-derived

The collector keeps the last head's hash and emits **`NodeReorg`** when a new
head's `ParentHash` does not match (event-schema §6; the `HeadEvent` struct
carries `ParentHash`). An unseen-parent head jump ≥2 is recorded as
`SequenceGap` immediately and proven or disproven off the hot path:
`chaintrack.Prove` walks the observed head's parents via `Node.HeaderByHash`,
which calls `eth_getHeaderByHash` directly over `rpc.Client`
(`internal/ethapi/api.go:503` — the header alone, never
`ethclient.HeaderByHash`, which pulls a whole block). Orphaned branches are
servable because the backend resolves by hash through the block index
(`eth/api_backend.go:126` → `core/headerchain.go:502`). A proven divergence
emits a second block-keyed `NodeReorg`; a jump past the prover's depth cap is
refused unwalked and counted. Still subscriptions plus bounded header
reads: `getLogs` is never called and the fork does not stream removed logs, so **there is no
`Removed` field anywhere** — not in the proto envelope, not in
`PredictionEvent`, not in any native struct. `NodeReorg` is emitted from **M1**
because an archive gap is permanent (rule 39, design-notes §4.5).

## Interface shape

`internal/nodeapi` exposes a narrow `Node` interface whose subscription methods
return **`Subscription[T]`** (a typed channel plus `Err()` and `Unsubscribe()`),
**not** a bare `<-chan T` (nodeapi §2, §3). A subscription's address set is
fixed **server-side at subscribe time** (fork-knowledge/node-api.md) — following
a rotating address means a second subscription, which is what
`SubscribeLogsFor`/`SubscribePendingFor` (explicit address set) exist
for; the Config-driven subscribe methods delegate to them, and an empty set
yields a silent subscription, never match-everything — except `SubscribeBlocks`,
which refuses an empty set (`ErrEmptyFrameFilter`; nodeapi §2). Transport is a single `endpoint`
string through `rpc.Dial`: an IPC path in production (`/run/geth/geth.ipc`), a
`ws://` URL in dev (`ws://10.99.0.1:8546`, `dev-setup/dev-setup.md`). The custom
subscriptions are identical across transports.

## Checklist before writing node code

- [ ] Is every RPC/subscription confirmed in the fork source (cite `file:line`)?
- [ ] Heads use `MilliTimestamp` for block time; the RLP header is preserved.
- [ ] Logs are subscriptions only; no `getLogs`.
- [ ] Pending uses the custom `...ByTosExt` subscription, `tos` = Prediction +
      Chainlink for M1.
- [ ] Reorg = `ParentHash` mismatch → `NodeReorg`; an unseen-parent jump ≥2 =
      `SequenceGap` + off-path ancestry proof (may add a `NodeReorg`); no
      `Removed` field.
- [ ] Subscriptions return `Subscription[T]`, not bare channels.
- [ ] Custom symbols (`...ByTosExt`, `sendTxFastExt`, `SendRawTransactionExt`,
      the fast-propagation flag) are `verified:true` in `symbols.json` at the
      current pin (`make fork-knowledge-check` green AND the row's
      `verified: true` read from the regenerated index).
