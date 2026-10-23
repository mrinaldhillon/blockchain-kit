---
name: fork-development
description: "Changing bsc-geth itself: the two roots, the pin, the checkout, go.work, the edit-to-pin loop."
---

**When to load:** Use when changing the bsc-geth fork itself — most often in a session rooted in a bsc-geth clone, or from a prediction-bot session through BSC_FORK_PATH when a bot change needs a fork change — editing, building, testing, committing or pushing fork code, moving the go.mod fork pin (only for a change to what pb consumes, pb ADR 0127), or deciding whether a change belongs in the fork or in the bot. Covers the two roots, the three trees (pin, checkout, go.work), the edit-to-pin loop, the fork's commands, branches, architecture and commit conventions.

# Developing the fork

bsc-geth is developed three ways (operator, 2026-10-14). Most fork work is node-internal and
runs in a session rooted in a bsc-geth clone; it ends at the push to `mrinal/dev`, and
prediction-bot stays on its pin (pb ADR 0127: the pin is informational, and pb re-pins only
when a change alters what it consumes). Fork work can also run from a prediction-bot session,
in the clone `BSC_FORK_PATH` names; and a bot change that needs a fork change is that, twice in
one pb session: the fork first, then the pin move, then the bot. One clone per open session: a
pb session's `BSC_FORK_PATH` never names a clone another session has open.

The fork's `CLAUDE.md` holds its facts: a bsc-rooted session loads it, a pb session does not.
Its steering is the kit's. Anything else tracked under its `.claude/` is stray (the
session-start line names it) and is not the rule. The fork's steering is this skill and these:

| Load | When |
|---|---|
| `blockchain-kit:fork-ext-convention` | before editing any Go file in the fork |
| `blockchain-kit:fork-deploy` | anything under `deploy/production/**` |
| `blockchain-kit:campaign` | the measurement campaign (`cmd/campaign`, `bsc-campaign.timer`) |
| `blockchain-kit:upstream-rebase` | moving the fork to a new upstream tag |
| the fork's feature inventory (its docs index, `docs/fork/README.md`, lists it) | what the fork adds, feature by feature, before changing one (`references/features.md` points there) |

## The two roots

| Root | Commands | Reads and edits |
|---|---|---|
| a bsc-geth clone | plain `git`, `make`, `go`, run in the tree | the session's own tree; gopls answers natively; `bsc-fork` exits 2 (no pin, no index): the source is the reference |
| prediction-bot | `git -C "$BSC_FORK_PATH" …`, `make -C "$BSC_FORK_PATH" …`, `go -C "$BSC_FORK_PATH" …`, never a `cd` | the checkout is outside the project: if a read or an edit there is refused, the user adds it (`claude --add-dir "$BSC_FORK_PATH"`, or `/add-dir`). Do not work around a refusal with Bash |

Commands below are written for a bsc root; from prediction-bot, add the `-C` form.

## In prediction-bot: three trees

| Tree | Where | What it is |
|---|---|---|
| the pin | the module cache; `bsc-fork path --pinned` | read-only. What `go.mod` names, what CI compiles, what the fork index describes |
| the checkout | `$BSC_FORK_PATH`; `bsc-fork path --checkout` | a git clone of bsc-geth. The only tree that is edited |
| what the build compiles | `bsc-fork pin`, row `compiles` | the pin, unless `go.work` is active: then the checkout |

`bsc-fork pin` prints all three and where the checkout stands against the pin. Read it
before the first fork edit, and again before claiming a bot test proved a fork change.

- A fork edit is invisible to the bot's build until `go.work` is active or the pin moves.
- The index (`bsc-fork show`) answers for the pin. For a checkout past the pin, a
  `file:line` may have moved and a new symbol is not in it: use gopls or read the file.

## The loop

Steps marked **pb** run in a prediction-bot session only. From a bsc-geth session the loop
is steps 1, 3 and 5, and it ends at the push. pb re-pins only for a change to what it consumes:
a method pb calls, a field it decodes, a `-1039xxx` code it switches on, a feature-status key it
reads. bsc's announcement for the build names any such change, from its diff over the fork
files pb's code cites (pb ADR 0127 decision 4). Only then do steps 6 to 8 run, in a
prediction-bot session, once the node that serves the change is live: the pin never passes the
deployed node (decision 3).

1. **Branch.** The fork tree is on `mrinal/dev` (or a branch cut from it), never `master`
   or `mrinal/master`. In pb, `bsc-fork pin` shows the branch.
2. **pb: workspace on.** `make go.work` (needs `BSC_FORK_PATH`). The bot now compiles the
   checkout, and gopls sees both modules. `go.work` is gitignored and never committed.
3. **Edit the fork** under `blockchain-kit:fork-ext-convention`. Gate it package-scoped:
   `go vet ./<pkg>/…`, the package's tests, then `make audit-ext`; `make lint` before a push.
4. **pb: edit the bot** against the changed fork. Its gates run as usual; with `go.work`
   active they prove the pair, not what CI will build.
5. **Commit and push the fork** (conventions below): with its gate green,
   `git push origin mrinal/dev`, behind `.githooks/pre-push`. No CI runs and no confirmation
   is needed (operator, 2026-10-14); a production deploy is the operator's.
6. **pb: move the pin**, for a consumed-API change only (above), with the pushed commit's
   full SHA:
   `go mod edit -replace=github.com/ethereum/go-ethereum=github.com/mrinaldhillon/bsc-geth@<sha>`
   then `go mod tidy`, which rewrites the SHA as a pseudo-version (checked, go 1.27.1).
   The pin must be on `mrinal/dev`: `make fork-pin-check`.
7. **pb: workspace off, then re-index.** `make go.work-off`, `make fork-index`,
   `make fork-knowledge-check`. `make fork-index` refuses a checkout whose HEAD is not the
   pin, so the checkout is at the pinned commit or `BSC_FORK_PATH` is unset for this step.
8. **pb: prove what CI builds.** Run the bot's gates again with no `go.work`. This is the
   run that counts.

The pin and the index move in the same commit of the bot. A bot commit that needs a fork
change not yet pinned does not build in CI.

## Where a change belongs

The fork is a node: it serves data and accepts transactions. The bot decides. A change
goes in the fork when it needs the node's internals (the txpool, the p2p layer, the
block import path, a new RPC or feed field). Everything that is policy, strategy,
sizing or parsing of a served value goes in the bot. A new fork surface is a contract:
it is named under the `Ext` convention, specified among the fork's shipped contracts, and the
bot reads it through `internal/nodeapi` (`blockchain-kit:fork-node-api`).

## What the fork is

A **fork of `bnb-chain/bsc`** (itself a go-ethereum fork). The Go module path is still
`github.com/ethereum/go-ethereum`, base version **BSC v1.7.8** (`version/version.go`), Go **1.27.1**.
The base is exactly upstream's `v1.7.8` tag, the newest *stable* upstream release; upstream master
has since moved on to `v1.8.0-alpha`, which this fork deliberately does not track yet.

The fork's purpose is a **latency-critical BSC "fast node" that feeds co-located trading bots**.
Almost all local value-add is low-latency transaction submission/propagation, peer curation, and
the OS/systemd tuning to run it. Upstream geth/BSC subsystems are otherwise intact.

Submitters are **always local and trusted** — the IPC unix socket or loopback websocket, possibly
several bots. There is no untrusted RPC path and none is planned. Several design decisions rest on
this (e.g. the fast path broadcasts before signature recovery); revisit them if it ever changes.

**Branches.** `origin/master` tracks upstream bnb-chain/bsc and carries no fork work.
`mrinal/master` is the fork's master, always rebased from it. **`mrinal/dev` is the working
branch** and the GitHub default; everything lands on it by a push, and prediction-bot pins it.
`mrinal/master` is not touched (operator, 2026-10-14: `mrinal/dev` needs much work before a
merge there); `.githooks/reference-transaction` holds it, and the upstream-rebase steps that
move it run only on the operator's explicit instruction. History is kept linear and
feature-level (one commit per feature) so the base stays cheap to re-rebase onto new upstream
tags: every commit riding on the fork stack is upstream-rebase cost. CI workflows trigger only
on `master`/`develop`, so **no CI runs on the `mrinal/dev` → `mrinal/master` pair** — the local
gate is the only evidence.

## Commands

Build/test go through `build/ci.go` (a Go wrapper that sets build tags and flags) — prefer the
Makefile targets over raw `go build`:

- `make geth` — build → `build/bin/geth`
- `make geth-prod` — production build: `GOAMD64=v3`, `-march=znver3`, `-z noexecstack`, PGO
  auto-applied iff `cmd/geth/default.pgo` exists (it currently does **not** — capture one first;
  see `deploy/production/README.md`). Host-specific (Zen 3); build on the CPU class you deploy on.
- `make tools-prod` — stages the fork tools (`adminpeers`, `feedsoak`, `pgocapture`, `metricsnap`)
  into `FORK_TOOLS_DIR` (`host.env`; the timer units' `ExecStart` resolve there); refuses a dirty tree.
- `make test` — full suite (`go run build/ci.go test -timeout 1h`)
- `make lint` — golangci-lint via `build/ci.go` (config: `.golangci.yml`, v2, `default: none` +
  an explicit allowlist), **then `make audit-ext` and `make modzip-check`**. Needs
  `CGO_CFLAGS="-O -D__BLST_PORTABLE__"` + `CGO_CFLAGS_ALLOW` on hosts where blst won't build
  natively (CI sets this).
- `make audit-ext` (fork-local) — `go run ./build/auditext`: the Ext naming/placement/wiring sweep
  of the **working tree** against the upstream merge-base (uncommitted work included); exit 1 on any
  fail-severity finding, 2 if the base won't resolve. `make audit-ext-test` runs its own tests.
- `make fmt` — `gofmt -s -w`. **Never run it on the fork tree**: upstream's files are
  gofmt-clean but not simplify-clean, and `-s` rewrites upstream lines that then conflict
  at the next rebase. The kit's edit hook formats the one file just written, without `-s`.
- **Heavy local work on srv** — the full suite, lint, `geth-prod`, or `go test` over the whole
  module, *however it is launched* (`make`, `ci.go`, `golangci-lint`, a script, `bash -c`,
  `xargs`, a `$(go list ./...)` package list) — runs as a capped systemd unit, outside the
  Claude process tree, with the fork's own runner, started in the fork tree:
  `python3 build/unit_run.py --name <slug> --mem 16G -- <cmd>`, then
  `python3 build/unit_run.py --wait <slug>` as foreground Bash at timeout 1800000 (verdict +
  log tail; re-run it if killed). Or `cmd/verifyconstrained`. Linux with a systemd user
  manager only. The kit's `guard-prod-run` hook refuses an uncapped run on the prod host.

Single package / single test (standard toolchain is fine — no ci.go needed):
- `go test ./eth/...` · `go test ./eth -run TestPeerCuration -v`
- `go vet ./eth/...`

**CI gate** (upstream's, on `master`/`develop` only): `build-test` runs `go run build/ci.go
check_generate` (go generate + `go mod tidy` produce no diff) and `check_baddeps`, then
`make geth`; `unit-test` runs `make test`; `lint` runs `go mod tidy` + `make lint`.

**Toolchain policy**: validate with default toolchain behavior and set no
`GOEXPERIMENT` unless the user explicitly asks; a non-default experiment run is a labeled
diagnostic.

## Architecture (big picture)

Standard geth layout — only the non-obvious wiring matters here:

- `cmd/geth` — entrypoint; flags registered in `cmd/utils/flags.go`.
- `eth/` — the full node backend (`backend.go`), the p2p protocol handler (`handler.go`), and the
  JSON-RPC surface (`api.go`, `api_admin.go`). **This is where nearly all fork wiring lives** — the
  `_ext.go` files hang off these. `eth/ethconfig/config.go` (+ generated `gen_config.go`) defines
  the config struct that TOML binds to, including the `*Ext` keys.
- `consensus/` — **Parlia** is BSC's PoSA engine (21 validators, fast-finality votes); this and the
  system contracts are the main divergence from vanilla geth. See `docs/parlia/`.
- `core/` — blockchain, EVM, `core/txpool/legacypool` (fork edits present here too — check for `Ext`).
- `ethdb` / `triedb` / `trie` — pebble-backed state; large trie/snapshot caches are **off the Go
  heap** (fastcache anon mmap / pebble block cache), which drives the memory sizing in the deploy docs.
- `p2p` — **not stock**: peer budget, curator cooldown, tracked peer sets and one-shot dialing live
  in `p2p/server_ext.go`, `p2p/peer_ext.go`, `p2p/dial_ext.go`. `node/api_ext.go`,
  `internal/debug/api_ext.go` and `log/handler_glog_ext.go` also carry fork code.
- `miner`, `rpc` — standard geth.

## Commit conventions

- Fork-local commits on `mrinal/dev` use **conventional commits**: `type(scope): subject`
  (e.g. `deploy(prod): …`, `docs(deploy): …`, `fix(deploy): …`, `build: …`).
- The upstream `commit-lint` CI (`docs/lint/commit.md`: `scope: subject`, ≤72-char head, no
  `R4R`/`WIP`) only runs on `master`/`develop`, so it does not gate this branch — but keep new
  scopes short and lowercase.
- A fork commit and the bot commit that pins it are two commits in two repos. The bot's
  message names the fork SHA it moves the pin to.

## Map of the fork's docs

The fork keeps its own map: `docs/fork/README.md`, one line per document under `docs/fork/`
(rules and state, contracts, decisions, history) and the documents elsewhere in its tree
(`deploy/production/`, each `cmd/<tool>/README.md`). Read it there; the kit names a fork
document by what it is and carries this one path. Two to read before acting: the project
context (milestone state, settled rulings, facts expensive to re-derive) before re-opening a
design question or re-running an investigation, and the feature inventory before changing a
feature.
