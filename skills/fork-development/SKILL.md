---
name: fork-development
description: "Changing bsc-geth itself: the two roots, the pin, the checkout, go.work, the edit-to-pin loop."
---

**When to load:** Use when changing the bsc-geth fork itself — most often in a session rooted in a bsc-geth clone, or from a prediction-bot session through BSC_FORK_PATH when a bot change needs a fork change — editing, building, testing, committing or pushing fork code, moving the go.mod fork pin (only for a change to what pb consumes, pb ADR 0127), or deciding whether a change belongs in the fork or in the bot. Covers the two roots, the three trees (pin, checkout, go.work), the edit-to-pin loop, where a change belongs, the rules for heavy work and formatting, and where the fork's own facts live (its docs, not this skill).

# Developing the fork

bsc-geth is developed three ways (operator, 2026-10-14). Most fork work is node-internal and
runs in a session rooted in a bsc-geth clone; it ends at the push to `mrinal/dev`, and
prediction-bot stays on its pin (pb ADR 0127: the pin is informational, and pb re-pins only
when a change alters what it consumes). Fork work can also run from a prediction-bot session,
in the clone `BSC_FORK_PATH` names; and a bot change that needs a fork change is that, twice in
one pb session: the fork first, then the pin move, then the bot. One clone per open session: a
pb session's `BSC_FORK_PATH` never names a clone another session has open.

The fork's docs are the home of the fork's facts; their index is `docs/fork/README.md`. What
the fork is, its upstream line and branches, its commands and CI gate, its architecture, commit
conventions and tools are the fork's development document, which the index lists: read them
there, in the tree you are changing, never from memory or from the kit. A bsc-rooted session
also loads the fork's `CLAUDE.md` (its identity, its own rules and pointers); a pb session does
not, and reads the index in the checkout. Claude steering for the fork is the kit's: anything
else tracked under its `.claude/` is stray (the session-start line names it) and is not the
rule. The fork's steering is this skill and these:

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
5. **Commit and push the fork** (the fork's commit conventions, in its development
   document): with its gate green,
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

## Commands

The fork's targets, what each runs, the CI gate and the toolchain are the fork's development
document (its §Commands). The kit's rules on top of them:

- Prefer the fork's Makefile targets over a raw `go build`; a single package or a single test
  needs only the standard toolchain.
- **Never run `make fmt` on the fork tree.** It is upstream's `gofmt -s -w` over every file:
  upstream's files are gofmt-clean but not simplify-clean, and `-s` rewrites upstream lines
  that then conflict at the next rebase. The kit's edit hook formats the one file just
  written, without `-s`.
- **Heavy work runs capped.** The full suite, lint, the production build, or `go test` over
  the whole module, *however it is launched* (`make`, `ci.go`, `golangci-lint`, a script,
  `bash -c`, `xargs`, a `$(go list ./...)` package list), runs under the fork's own runner,
  started in the fork tree (`build/unit_run.py`, the wrapper the kit's `guard-prod-run` hook
  accepts; its flags and the cloud-session fallback are the development document's), and its
  wait runs as foreground Bash at timeout 1800000. The hook refuses an uncapped run on the prod
  host; decide by what runs, not by whether the hook would deny it, since it cannot see inside
  a script file.
- Validate with default toolchain behaviour and set no `GOEXPERIMENT` unless the user asks.

## Commits

The fork's commit conventions are its development document's. The kit's rule across the two
repos: a fork commit and the bot commit that pins it are two commits in two repos, and the
bot's message names the fork SHA it moves the pin to.

## Map of the fork's docs

The fork keeps its own map: `docs/fork/README.md`, one line per document under `docs/fork/`
(rules and state, contracts, decisions, history) and the documents elsewhere in its tree
(`deploy/production/`, each `cmd/<tool>/README.md`). Read it there; the kit names a fork
document by what it is and carries this one path. Three to read before acting: the
development document before building, gating or landing a change; the project context
(milestone state, settled rulings, facts expensive to re-derive) before re-opening a design
question or re-running an investigation; and the feature inventory before changing a feature.
