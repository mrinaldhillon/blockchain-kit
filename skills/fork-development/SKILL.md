---
name: fork-development
description: Use when changing the bsc-geth fork itself from a prediction-bot session — editing, building, testing or committing in the fork checkout, moving the go.mod fork pin, or deciding whether a change belongs in the fork or in the bot. Covers the three trees (pin, checkout, go.work), the edit-to-pin loop, the fork's commands, branches, architecture and commit conventions.
---

# Developing the fork from its client

bsc-geth carries no Claude steering of its own: no `CLAUDE.md`, no `.claude/`. It is
developed from a prediction-bot session, for prediction-bot and nothing else. What the
fork's own steering used to say is in this skill and three others:

| Load | When |
|---|---|
| `blockchain-kit:fork-ext-convention` | before editing any Go file in the checkout |
| `blockchain-kit:fork-deploy` | anything under `deploy/production/**` in the checkout |
| `blockchain-kit:upstream-rebase` | moving the fork to a new upstream tag |
| `references/features.md` (this skill) | what the fork adds, feature by feature, before changing one |

## Three trees

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
- The checkout is outside the session's project directory. If a read or an edit there is
  refused, the user adds it: `claude --add-dir "$BSC_FORK_PATH"`, or `/add-dir` in the
  session. Do not work around a refusal with Bash.

## The loop

Commands in the checkout take the tree as an argument, never a `cd`:
`git -C "$BSC_FORK_PATH" …`, `make -C "$BSC_FORK_PATH" …`, `go -C "$BSC_FORK_PATH" test ./eth/…`.

1. **Branch.** The checkout is on `mrinal/dev` (or a branch cut from it), never `master`
   or `mrinal/master`. `bsc-fork pin` shows the branch.
2. **Workspace on.** In prediction-bot: `make go.work` (needs `BSC_FORK_PATH`). The bot
   now compiles the checkout, and gopls sees both modules. `go.work` is gitignored and
   never committed.
3. **Edit the fork** under `blockchain-kit:fork-ext-convention`. Gate it in the checkout:
   `go -C "$BSC_FORK_PATH" vet ./<pkg>/…`, the package's tests, then
   `make -C "$BSC_FORK_PATH" audit-ext`.
4. **Edit the bot** against the changed fork. Its gates run as usual; with `go.work`
   active they prove the pair, not what CI will build.
5. **Commit the fork** in the checkout (conventions below) and push `mrinal/dev`. Pushing
   is the user's call: ask, do not assume.
6. **Move the pin.** In prediction-bot, with the pushed commit's full SHA:
   `go mod edit -replace=github.com/ethereum/go-ethereum=github.com/mrinaldhillon/bsc-geth@<sha>`
   then `go mod tidy`, which rewrites the SHA as a pseudo-version (checked, go 1.27.1).
   The pin must be on `mrinal/dev`: `make fork-pin-check`.
7. **Workspace off, then re-index.** `make go.work-off`, `make fork-index`,
   `make fork-knowledge-check`. `make fork-index` refuses a checkout whose HEAD is not the
   pin, so the checkout is at the pinned commit or `BSC_FORK_PATH` is unset for this step.
8. **Prove what CI builds.** Run the bot's gates again with no `go.work`. This is the run
   that counts.

The pin and the index move in the same commit of the bot. A bot commit that needs a fork
change not yet pinned does not build in CI.

## Where a change belongs

The fork is a node: it serves data and accepts transactions. The bot decides. A change
goes in the fork when it needs the node's internals (the txpool, the p2p layer, the
block import path, a new RPC or feed field). Everything that is policy, strategy,
sizing or parsing of a served value goes in the bot. A new fork surface is a contract:
it is named under the `Ext` convention, specified in the fork's `docs/specs/`, and the
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
`mrinal/master` is the fork's master, always rebased from it. **`mrinal/dev` is the working branch
and merges *into* `mrinal/master`** — so `mrinal/master` is the PR base, not `mrinal/dev`. History
is kept linear and feature-level (one commit per feature) so the base stays cheap to re-rebase onto
new upstream tags: every commit riding on the fork stack is upstream-rebase cost. CI workflows
trigger only on `master`/`develop`, so **no CI runs on the `mrinal/dev` → `mrinal/master` pair** —
the local gate is the only evidence.

## Commands

All from prediction-bot, with `make -C "$BSC_FORK_PATH"` or `go -C "$BSC_FORK_PATH"`.
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
  an explicit allowlist), **then `make audit-ext`** — the fork's Ext-convention sweep is part of
  this target. Needs `CGO_CFLAGS="-O -D__BLST_PORTABLE__"` + `CGO_CFLAGS_ALLOW` on
  hosts where blst won't build natively (CI sets this).
- `make audit-ext` (fork-local) — `go run ./build/auditext`: the Ext naming/placement/wiring sweep
  of the **working tree** against the upstream merge-base (uncommitted work included); exit 1 on any
  fail-severity finding, 2 if the base won't resolve. `make audit-ext-test` runs its own tests.
- `make fmt` — `gofmt -s -w`. **Never run it on the fork tree**: upstream's files are
  gofmt-clean but not simplify-clean, and `-s` rewrites upstream lines that then conflict
  at the next rebase. The kit's edit hook formats the one file just written, without `-s`.
- **Heavy local work** — the full suite, lint, `geth-prod`, or `go test` over the whole
  module, *however it is launched* (`make`, `ci.go`, `golangci-lint`, a script, `bash -c`,
  `xargs`, a `$(go list ./...)` package list) — runs as a capped systemd unit, outside the
  Claude process tree. The runner is prediction-bot's, and the unit runs in the caller's
  directory, so it is started from the checkout:
  `cd "$BSC_FORK_PATH" && python3 <bot>/dev-setup/ci/unit_run.py --name <slug> --mem 16G -- <cmd>`,
  then `python3 <bot>/dev-setup/ci/unit_run.py --wait <slug>` as background Bash (verdict +
  log tail; re-run it if killed). Linux with a systemd user manager only.

Single package / single test (standard toolchain is fine — no ci.go needed):
- `go -C "$BSC_FORK_PATH" test ./eth/...` · `go -C "$BSC_FORK_PATH" test ./eth -run TestPeerCuration -v`
- `go -C "$BSC_FORK_PATH" vet ./eth/...`

**CI gate** (must pass before merge): `build-test` runs `go run build/ci.go check_generate`
(go generate + `go mod tidy` produce no diff) and `check_baddeps`, then `make geth`; `unit-test`
runs `make test`; `lint` runs `go mod tidy` + `make lint`, which also runs `make audit-ext`.

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

Pointers only — each document owns its content. Paths are in the checkout.

- `docs/specs/` — contracts as shipped. `bot-feed-contract-v1.md` is the bot-facing
  feed/send/readiness wire contract.
- `docs/superpowers/specs/` — design records (reasoning, options, rejected alternatives);
  `docs/superpowers/plans/` — the execution plans they feed.
- `docs/PROJECT_CONTEXT.md` — state, settled rulings ("decided — do not reopen"), and the
  verified facts that are expensive to re-derive (what's red on pristine upstream, the
  `bsc/2` capability floor, the measured peer-churn cause). Read it before re-opening a
  design question or re-running an investigation.
- `docs/adr/` — decisions and agreed working guidance from 2026-09-17 on, one numbered file
  each.
- `deploy/production/probes/` — the hand-run live-node probes that seed the health suite.
- `docs/FORK_NAMING_CONVENTION.md` — the `Ext` marker and file-placement rules in full.
- `deploy/production/README.md` — the reasoning behind every installed number;
  `deploy/production/host/README.md` — the host bundle (manifest, installer, verifier, tests);
  `deploy/production/CUTOVER_RUNBOOK.md` — the wiped-host rebuild; `deploy/production/REDEPLOY_RUNBOOK.md`
  — redeploying onto the running host with prediction-bot sequenced in.
- `docs/parlia/`, `docs/audits/`, `docs/postmortems/`, `docs/reviews/` — consensus notes and
  the historical record.
- `docs/go-runtime-diagnostics.md` — sanitizers, race detector, leak/contention profiles,
  execution trace and flight recorder: what each costs and which run on this node.
