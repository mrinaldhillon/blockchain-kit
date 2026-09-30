---
name: fork-lookup
description: >-
  Use to look up a BSC fork symbol (signature, file:line, verified flag) from the
  committed machine index instead of re-parsing the fork, and to check whether the
  fork-knowledge artifacts are stale. Trigger before reading the fork tree for any
  node-API symbol.
---

# Fork symbol lookup (parse-once, rule 43)

The fork is distilled once into `docs/fork-knowledge/` — prose plus the machine
index `docs/fork-knowledge/symbols.json`. **Consult these before opening the fork
tree.** Regenerating them is the `blockchain-kit:fork-indexer` agent's.

## Lookup
Ask `bsc-fork` (on `PATH` while the plugin is enabled); never `Read`
`symbols.json` to find a row — the file is the whole index, the command prints
the row:

| Question | Command |
|---|---|
| A symbol's signature, `file:line`, `verified` flag and note | `bsc-fork show <Symbol>...` |
| Which rows mention a concept | `bsc-fork search <term>...` |
| The inventory, by kind or unconfirmed only | `bsc-fork list [--kind K] [--unverified]` |
| Which commit `go.mod` pins, and where its tree is | `bsc-fork pin` |
| Whether the index was built at the pin | `bsc-fork check` |
| The absolute path of a fork `file:line` | `bsc-fork path <file>[:line]` |

A name can have several rows (`GetHeaderByHash` has three); `file:line` tells
them apart. Exit 1 is "no such row" or "stale", 2 is "no pin or no index";
`--json` for a script. A row schema is `symbol`, `kind`, `signature`, `file`,
`line`, `verified`, `note` under a header `fork_sha`. Use the prose files
(`node-api.md`, `block-time.md`, `txpool-internals.md`, `peer-management.md`,
`build-flags.md`) for the surrounding concept. Cite the `file:line` anchor when
you assert an API.

The **gopls MCP** tools resolve every fork package pb imports, at the `go.mod`
pin, from the module cache with no `go.work`: `go_package_api` (parameter
`packagePaths`) reads a fork package's exported API with its doc comments, and
`go_symbol_references` (a bare `X` or `T.M`, never `pkg.X`) finds pb's call
sites of a fork symbol (ADR 0067). For a fork `file:line` anchor, Read the path
`bsc-fork path` prints — the pin's own read-only tree, never a checkout whose
HEAD sits past the pin.
`symbols.json` stays the source of truth for the custom surface the project
consumes and for fork packages pb does not import, since gopls indexes only the
import graph; fork-dev mode (`go.work` active) additionally indexes the whole
fork tree. gopls is a dev-loop tool: it needs `make tools` and is absent in CI
(`.mcp.json`). Grepping the fork tree is the last resort, and the route for
non-Go text.

## Adding a pinned entry
Most entries are AST-resolved (`file` empty) and their `file:line` track the fork
automatically. Pin a **statement** instead when the fact is where a line sits or
what it says — statement order inside a body, a delegation target — which AST
resolution cannot express. A pinned entry sets `file`, `line`, and a `probe`
substring that must appear on that line (`checkAnchors` fails `make fork-index`
otherwise), plus a `note` saying what it pins; model it on the `*-order` rpc
entries in `cmd/fork-index/main.go`. `make fork-index` runs against the read-only
module cache: the Makefile passes `-sha`/`-commit-time` from
`scripts/fork-pin.sh`, the single parser of the go.mod pin, whenever the fork dir
has no `.git`, and git stays authoritative when it does (#399).

## Verified flag
`verified:true` means confirmed against the fork at the recorded SHA. A row whose
`verified` is `false` is a name the index has not confirmed against source at
this pin — read the row's `note`, then confirm with `file:line` before relying on
it, and flip the flag by regenerating the index in the same PR. The money-path
custom names: `blockchain-kit:fork-node-api` §Verified fork bindings.

## Drift / missing symbol
`bsc-fork check` is the fast answer, and the session-start line already gave
it. The gate is `make fork-knowledge-check`: it compares `symbols.json`
`fork_sha` to the SHA resolved from the go.mod `replace` pseudo-version, and
diffs the generated pin as well. **Only** re-parse the fork tree
when this reports drift or the symbol you need is absent. After a re-read,
regenerate via `make fork-index` (do not hand-edit `line` fields) and re-verify
the affected prose, updating the SHA tags. `make fork-index` also writes the
generated build-time pin `internal/nodeapi/forkpin_gen.go`, which the drift check
diffs as well — outputs and gate: `docs/fork-knowledge/README.md` §Bootstrap and
maintenance.
