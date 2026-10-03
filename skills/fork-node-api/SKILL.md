---
name: fork-node-api
description: >-
  Use for any BSC node interaction — RPC calls, subscriptions, head/block/log/pending
  streams and feeds, broadcast, block-time, reorg detection, `internal/nodeapi`. The
  node is a PRIVATE FORK: trigger before citing any go-ethereum/geth/ethclient API
  or assuming a method exists, and for MilliTimestamp, MixDigest, NodeReorg,
  SendResultExt.
---

# Node API resolves against the fork, never upstream

**Load when**
- Writing or reviewing code that talks to the node, or `internal/nodeapi` itself.
- About to name a go-ethereum, geth or ethclient method, field, flag or RPC.

**Where the facts live** (pb repo paths)

| Topic | Doc |
|---|---|
| The rule: the fork, never upstream | `docs/discipline.md` §38; `docs/decisions/0003-node-api-against-fork.md` |
| Import wiring; pinned module by default, `go.work` opt-in | `docs/design-notes.md` §3.12; `docs/architecture.md` §8.1; `docs/decisions/0002-fork-import-require-replace.md`, `docs/decisions/0015-fork-default-pinned-module-go-work-opt-in.md` |
| `Node` interface, `Subscription[T]`, explicit address sets, `ErrEmptyFrameFilter` | `docs/specs/nodeapi.md` §2; `docs/design-notes.md` §3.11 |
| Event shapes, raw contract, receive-stamp regimes, feed-contract types | `docs/specs/nodeapi.md` §3 |
| What pb subscribes and calls today | `docs/fork-knowledge/node-api.md` §Feed contract v1; `docs/specs/nodeapi.md` §2 |
| Header-by-hash, broadcast, feature status, inclusion ring, block frame | `docs/specs/nodeapi.md` §4; `docs/fork-knowledge/node-api.md` §Header-by-hash, §Broadcast, §Local-tx inclusion ring |
| Transport (IPC prod, WS dev) | `docs/specs/nodeapi.md` §5 |
| Reconnect, drops, drain, cut-off | `docs/specs/nodeapi.md` §6; `docs/fork-knowledge/node-api.md` §Subscription delivery is out-of-band from its error |
| Invariants | `docs/specs/nodeapi.md` §7 |
| Millisecond block time (BEP-520) | `docs/fork-knowledge/block-time.md` |
| Reorg vs gap, ancestry proof; removed-log frames refused, no `Removed` field | `docs/specs/event-schema.md` §6; `docs/design-notes.md` §4.5 |
| Whether an index row holds at this pin | `docs/fork-knowledge/README.md` §Bootstrap and maintenance |
| A doc that disagrees with code or the fork source | `docs/discipline.md` §43 |

**Commands that answer questions**
- `bsc-fork show <Symbol>` and `bsc-fork path --pinned <file>[:line]` (kit `bin/bsc-fork`): a fork binding's row, and its source in the pinned tree pb ships against.
- `bsc-fork check`; the gate is `make fork-knowledge-check` (Makefile).

**What only this skill says**
- Never answer a node or RPC question from upstream go-ethereum or bnb-chain/bsc documentation or memory. An API without a fork `file:line` does not exist here; cite the anchor when you assert one.
- Trust a custom binding only while its row is `verified: true` in an index built at the current pin (`blockchain-kit:fork-lookup`).
- With `go.work` active, prefer the gopls MCP tools (`go_search`, `go_symbol_references`, `go_package_api`) to grep: they return the fork `file:line` at the checkout's HEAD, which may sit past the pin (`bsc-fork pin` says where).
- A doc that disagrees with the fork source or with `internal/nodeapi/live.go` is adjudicated, never auto-resolved (`docs/discipline.md` §43). A reading of the fork source at the pin is an observation: the doc is fixed in the same PR or superseded by an ADR. Against pb's own code neither side is presumed right: either the code broke a decided invariant (a code bug; restore the decided behavior) or the decision changed (fix the doc in the same PR, or append a superseding ADR).
- The import wiring is decided (ADR 0002); do not reopen it.
- Before writing node code, check it against `docs/specs/nodeapi.md` §2 and §7 and `docs/design-notes.md` §4.5.
