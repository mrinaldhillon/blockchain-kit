---
name: fork-lookup
description: >-
  Use to look up a BSC fork symbol (signature, file:line, verified flag) from the
  committed machine index instead of re-parsing the fork, and to check whether the
  fork-knowledge artifacts are stale. Trigger before reading the fork tree for any
  node-API symbol, and before adding or regenerating an index entry.
---

# Fork symbol lookup (parse-once, rule 43)

**Load when**
- You need a fork symbol's signature, `file:line` or `verified` flag, or the concept around it.
- The pin moved, `bsc-fork check` says stale, or a symbol is absent from the index.
- You are adding an entry to the index or regenerating it.

**Where the facts live** (pb repo paths)

| Topic | Doc |
|---|---|
| Parse once; when to re-parse | `docs/discipline.md` §43; `docs/fork-knowledge/README.md` §Why this exists |
| Index schema; regeneration; drift gate; generated `ForkPin` | `docs/fork-knowledge/README.md` §`symbols.json` schema, §Bootstrap and maintenance |
| AST vs pinned entries (`probe`), curated `verified`, runs on the module cache, reading anchors in the pinned tree, what the drift check proves | `docs/fork-knowledge/README.md` §Bootstrap and maintenance |
| Concepts | `docs/fork-knowledge/{node-api,block-time,txpool-internals,peer-management,build-flags,data-shapes}.md` |
| The bindings pb ships against | `docs/specs/nodeapi.md` §4; `docs/fork-knowledge/node-api.md` §Feed contract v1 |

**Commands that answer questions**

| Question | Command (defined in) |
|---|---|
| A symbol's rows: signature, `file:line`, `verified`, note | `bsc-fork show <Symbol>...` (kit `bin/bsc-fork`) |
| Rows that mention a term; the inventory | `bsc-fork search <term>...`; `bsc-fork list [--kind K] [--unverified]` |
| The pin, its tree, the checkout against it | `bsc-fork pin` |
| Is the index built at the pin | `bsc-fork check`; the gate is `make fork-knowledge-check` (Makefile) |
| Absolute path of a fork `file:line` in the pinned tree | `bsc-fork path --pinned <file>[:line]` (with no flag it prints the tree the client compiles, which is the checkout when `go.work` is active) |
| Regenerate the index and `internal/nodeapi/forkpin_gen.go` | `make fork-index` (Makefile) |

**What only this skill says**
- Ask `bsc-fork`; never `Read` `docs/fork-knowledge/symbols.json` to find a row. Exit 1: no such row or stale; 2: no pin or no index; `--json` for a script.
- Read a fork `file:line` anchor at the path `bsc-fork path --pinned` prints: the pin's read-only tree in the module cache, never a checkout whose HEAD sits past the pin.
- For a fork package pb imports, the gopls MCP tools answer at the pin: `go_package_api` (`packagePaths`) for its exported API, `go_symbol_references` (a bare `X` or `T.M`, never `pkg.X`) for pb's call sites. They are absent in CI. Grep the fork tree last, and for non-Go text.
- Cite the fork `file:line` when you assert an API; a `verified:false` row is not evidence until you have confirmed it there.
- Re-parse only on drift or an absent symbol. Regenerating is the `blockchain-kit:fork-indexer` agent's.
