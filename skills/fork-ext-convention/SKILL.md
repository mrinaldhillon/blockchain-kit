---
name: fork-ext-convention
description: "The fork's Ext marker, *_ext.go placement and make audit-ext."
---

**When to load:** Use before editing, adding or renaming any Go code in the bsc-geth fork (a bsc-geth session's own tree, or the checkout from prediction-bot) — the Ext marker on fork-added symbols, fields, tags, TOML keys, flags and RPC methods, the *_ext.go placement rule, the wiring rule for edits inside upstream functions, the provenance check against the upstream tag, and make audit-ext.

# The fork's `Ext` convention — read this before editing anything in the fork

bsc-geth is a fork of bnb-chain/bsc kept cheap to rebase. This is the single most important
rule in that tree. Full spec, in the fork tree: its **naming convention**, which the fork's
docs index `docs/fork/README.md` lists; its examples, names, limits and file paths are the
fork's facts and are read there. It applies to the fork only: prediction-bot's own code takes
no `Ext` suffix.

- **`Ext` is the only fork marker.** Every *durable* fork-local surface added inside a package
  that also exists upstream ends with `Ext`: exported symbols, struct fields (**and their
  `json`/`yaml` tags**), TOML keys, CLI flag names, RPC method names. Not local vars/params.
- **The marker runs in ONE direction.** Never add `Ext` to a symbol that came from upstream — it
  claims fork provenance for upstream code and guarantees a rename conflict. It has happened
  and been reverted; the naming convention names the cases.
- **Not every `Ext` is ours.** Upstream uses `Ext` for *extension* too (the naming convention
  lists the known names). Leave them alone. So `rg 'Ext\b'` is a starting point, not an
  inventory — audit by diffing against the upstream base, in both directions (fork-added
  symbols have also been found *missing* the marker). `make audit-ext` is that sweep,
  mechanized; what it checks is the naming convention's. `make lint` runs it, so the convention
  is gated, not just documented.
- **Fork logic lives in `*_ext.go` files**, never inline in upstream files. `rg '_ext\.go'`.
- **The wiring rule — as few upstream-rebase conflicts as practically possible.** That property
  is the rule. Firm, because these are what conflict: an edit to an upstream function **deletes
  no upstream line** (a one-call swap to an `*Ext` helper excepted) and never restructures the
  body inline; an edit to an upstream struct only adds `*Ext` fields — none removed, retyped,
  retagged or reordered. Soft, because insertions rebase cheaply: past the naming convention's
  per-function insertion limit `make audit-ext` reports a WIRING finding, and a reviewed
  allowlist row with the reason is the normal way through. Where a clause would make the
  rebase harder, the property wins and the reason is written down. Copy the reference
  patterns the naming convention names.
- Brand-new fork-only packages may use normal Go file/identifier names.

## The provenance check

The one recipe; everything else cites it. In a bsc-geth root (from prediction-bot, write
`git -C "$BSC_FORK_PATH" show …`):

```sh
git show <base-tag>:path/file.go | grep -n '\bSymbol\b'
```

No output means fork-added. The base tag, and how a clone without it resolves the base, are
the naming convention's, beside the same recipe. Never infer provenance from the suffix
alone — gopls cannot answer it either; it sees HEAD only.

The whole-tree mechanical sweep is `make audit-ext` (from prediction-bot,
`make -C "$BSC_FORK_PATH" audit-ext`), against the upstream merge-base. Run the tool rather
than re-deriving the convention by hand.

## Navigating the fork

Navigate Go with the `mcp__gopls__*` tools, not text search. In a bsc-geth root gopls
answers for the tree natively. From prediction-bot it answers for the checkout only while
pb's `go.work` is active (`make go.work`); without it the fork package it resolves is the
pin's, in the module cache.
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
`bsc-fork search <name>`, from prediction-bot. In a bsc-geth session such a change is a bot
change too: it runs from a prediction-bot session, fork first, then the pin and the bot.
