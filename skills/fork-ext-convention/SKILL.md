---
name: fork-ext-convention
description: "The fork's Ext marker, *_ext.go placement and make audit-ext."
---

**When to load:** Use before editing, adding or renaming any Go code in the bsc-geth fork checkout — the Ext marker on fork-added symbols, fields, tags, TOML keys, flags and RPC methods, the *_ext.go placement rule, the wiring rule for edits inside upstream functions, the provenance check against the upstream tag, and make audit-ext.

# The fork's `Ext` convention — read this before editing anything in the checkout

bsc-geth is a fork of bnb-chain/bsc (base tag `v1.7.8`) kept cheap to rebase. This is the
single most important rule in that tree. Full spec, in the checkout:
**`docs/FORK_NAMING_CONVENTION.md`**. It applies to the fork only: prediction-bot's own
code takes no `Ext` suffix.

- **`Ext` is the only fork marker.** Every *durable* fork-local surface added inside a package
  that also exists upstream ends with `Ext`: exported symbols, struct fields (**and their
  `json`/`yaml` tags**), TOML keys, CLI flag names, RPC method names. Not local vars/params.
- **The marker runs in ONE direction.** Never add `Ext` to a symbol that came from upstream — it
  claims fork provenance for upstream code and guarantees a rename conflict. Three had to be
  reverted (`p2p.Server.disconnectEnodeSet`, `p2p.PeerInfo.Latency`, `eth.Ethereum.localTxTracker`).
- **Not every `Ext` is ours.** Upstream uses `Ext` for *extension*: `ethPeer.snapExt`,
  `ethPeer.bscExt`, `trie.newExt`. Leave them alone. So `rg 'Ext\b'` is a starting point, not an
  inventory — audit by diffing against the upstream tag, in both directions (fork-added symbols
  have also been found *missing* the marker). `make audit-ext` is that sweep, mechanized — placement,
  both marker directions (declarations *and* struct fields, tags, interface methods) and the wiring
  rule below; `make lint` runs it, so the convention is gated, not just documented.
- **Fork logic lives in `*_ext.go` files**, never inline in upstream files. `rg '_ext\.go'`.
- **The wiring rule — as few upstream-rebase conflicts as practically possible.** That property
  is the rule. Firm, because these are what conflict: an edit to an upstream function **deletes
  no upstream line** (a one-call swap to an `*Ext` helper excepted) and never restructures the
  body inline; an edit to an upstream struct only adds `*Ext` fields — none removed, retyped,
  retagged or reordered. Soft, because insertions rebase cheaply: **about ten inserted lines per
  function**; past that `make audit-ext` reports a WIRING finding and a reviewed row in
  `build/audit-ext-allow.txt` with the reason is the normal way through. Where a clause would
  make the rebase harder, the property wins and the reason is written down.
  Canonical patterns to copy: `eth/protocols/eth/serving_policy_ext.go`,
  `eth/handler_broadcast_ext.go` (+ the one-line swap in `eth/handler.go` `BroadcastTransactions`),
  `eth/api_backend_fast_tx_ext.go` (+ the guard in `eth/api_backend.go` `SendTx`).
- Brand-new fork-only packages (e.g. `cmd/adminpeers`, `cmd/feedsoak`) may use normal Go
  file/identifier names.

## The provenance check

The one recipe; everything else cites it. In the checkout:

```sh
git -C "$BSC_FORK_PATH" show v1.7.8:path/file.go | grep -n '\bSymbol\b'
```

No output means fork-added. If the `v1.7.8` tag is absent in a clone, resolve the base as
`git merge-base HEAD origin/master` (verified equal to the v1.7.8 commit) or fetch it:
`git fetch https://github.com/bnb-chain/bsc.git tag v1.7.8 --no-tags`. Never infer
provenance from the suffix alone — gopls cannot answer it either; it sees HEAD only.

The whole-tree mechanical sweep is `make -C "$BSC_FORK_PATH" audit-ext`
(`go run ./build/auditext`: placement, both marker directions over declarations *and*
struct fields, tags and interface methods, and the wiring rule, against the merge-base).
Run the tool rather than re-deriving the convention by hand.

## Navigating the checkout

Navigate Go with the `mcp__gopls__*` tools, not text search. gopls answers for the fork
tree only while prediction-bot's `go.work` is active (`make go.work`); without it the
fork package it resolves is the pin's, in the module cache.
`go_search` locates a symbol, `go_symbol_references` is the only proof for "every
caller" / "nothing else writes this" / interface satisfaction, `go_file_context` and
`go_package_api` give signatures and a package's surface before an edit,
`go_diagnostics` gives the compile and vet state of a file you just edited before you
spend a build, `go_rename_symbol` returns every call-site edit — which is how an `Ext`
suffix is applied without missing a caller. `git grep` and `go doc` are the fallback
when a call fails; say so once when you fall back. The two things gopls cannot answer
are upstream provenance (the provenance check above — it sees HEAD only) and anything
in a file that does not compile.

## A renamed or removed `Ext` surface breaks the bot

Every `Ext` RPC method, feed field and TOML key is something prediction-bot may consume.
Before renaming or removing one, find its consumer in the bot (`internal/nodeapi`,
`blockchain-kit:fork-node-api`), and change both sides in the same loop
(`blockchain-kit:fork-development`). The fork index lists what the bot depends on:
`bsc-fork search <name>`.
