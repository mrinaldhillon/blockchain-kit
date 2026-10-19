---
name: working-here
description: "How work moves: plan, issues, units, the implement workflow, landing."
---

**When to load:** How work moves in prediction-bot and in the bsc-geth fork from a Claude session: explore and plan in the session, persist open work as issues, cut briefed units, run the implement workflow, adjudicate its result, land (pb: dev-setup/ci/land; bsc-geth: a push to mrinal/dev). Load before a multi-step change, before cutting units, and before landing.

# Working here

The main loop does the thinking: it explores, decides, writes the contract, and judges what
comes back. It does not drive implement → gate → review → fix by hand, and it keeps no
bookkeeping files. The project's `CLAUDE.md` holds the facts and the invariants and wins over
anything here.

## The loop

1. **Explore and plan in the session.** Read the code and the `docs/` that own the topic. The
   plan is the list of units; it lives in the conversation and, when it outlives the session,
   in an issue. No plan, spec, ledger or resume file is tracked in either repository.
2. **Persist open work as issues.** An issue body carries the units still to do, with their
   contracts. A deferral is `gh issue create`, at the moment it is found. Milestone state is
   `docs/project-context.md` (pb) or `docs/PROJECT_CONTEXT.md` (bsc-geth). An issue about
   Claude itself (steering, this kit, a hook, skill, agent or workflow, the harness, model
   cost) is filed in `mrinaldhillon/blockchain-kit`, never in the repository you are in
   (operator, 2026-10-14).
3. **Cut units.** A unit is `{id, brief, packages, skills?}`:
   - The brief is a contract: the files, the interfaces with exact signatures, the test cases
     with their assertions, the invariants, and what is out of scope. Bodies are the
     implementer's. A brief the implementer would have to guess from is not ready.
   - Units are independent: no two share a Go package, and none needs another's result. Work
     that is coupled is one unit.
   - Name the kit skills a unit needs. A subagent gets none by description.
4. **Run `/blockchain-kit:implement`** when the user asks for it: lanes in worktrees beside
   the clone (never inside it), one merged run branch, the gate, one review, one fix round. Its args always carry `project`
   and `module` (the command says how). It runs in the background and returns
   `{merged, conflicted, handbacks, stalled, gate, findings, owed, head}`.
5. **Adjudicate.** Hand-backs are questions for you. A conflicted or stalled lane names what
   it left. Open findings are fixed, deferred to an issue, or accepted, and you say which.
   `owed.parity`: run `make replay-parity` once. `owed.read`: read those diffs yourself.
6. **Land in one call**, and nothing after it. Landing needs no confirmation; a production
   deploy (a geth restart, a host install) is a separate decision and is the operator's.
   - prediction-bot: `git push -q && dev-setup/ci/land <PR>`, foreground Bash, timeout 1800000
     (pb's `BASH_MAX_TIMEOUT_MS`; the longest CI run of the last 60 took 12.1 min, 2026-10-14).
     `land` waits for the pushed head, runs the lanes the diff selects, squash-merges on green
     and leaves a clean `main` at the merge; the kit's `land-shape` hook holds the call to that
     shape. Exit 0 merged, 1 red, 3 merged with a cleanup left, 4 refused, each said in its
     last lines. A red is fixed, committed and sent through the same call.
   - bsc-geth: no CI and no `land`. With the class's gate green, squash the branch to its
     feature commits (an `implement` run leaves lane and merge commits; every commit on the
     stack is upstream-rebase cost), then `git push origin mrinal/dev`, behind
     `.githooks/pre-push`. `mrinal/master` is not touched (operator, 2026-10-14):
     `.githooks/reference-transaction` holds it.

One unit, or a change too small to brief, skips steps 3 to 5: dispatch
`blockchain-kit:golang-implementer` once, or make a prose or tooling edit yourself.

When the operator is offline, run the approved plan to completion and batch what only they
can answer for the end (operator, 2026-09-09).

## What a change owes

The class is read off the diff and decides the ceremony. The last two rows are bsc-geth's.

| Class | The diff | Gate | Review | Record |
|---|---|---|---|---|
| Prose | docs, comments, `CLAUDE.md` | none: `land` posts `ci` with no run | none | none |
| Tooling | `dev-setup/`, `scripts/`, Makefile, CI workflow, `tools/` | the lanes the selector names | none | none |
| Product Go | `cmd/`, `internal/` | the lanes the selector names | one seat at merge: the workflow's, or one `blockchain-kit:code-reviewer` dispatch | none |
| Guarded Go | record spine, hot path, money path | the same, plus `make replay-parity` when owed | the same, and you read the diff | an ADR only when an invariant, a stored-data contract or a boundary changes |
| Fork Go | `*_ext.go`, and upstream files under the wiring rule | package-scoped gates in a capped unit on srv, then `make audit-ext`; `make lint` before a push | one seat, with the `Ext` and landmine angles | an ADR only for a decision about the node |
| Host | `deploy/production/` | `bash deploy/production/host/tests/run.sh`; `check-config-ext.sh` and `host/geth-preflight.sh` before a `config.toml` or `ExecStart` change | none | none; the install itself is the operator's |

- **One branch per change, whatever it touches.** Code, its docs and its tooling land together.
- **A fact has one home, so a change has one edit.** A fact about the code lives in the
  repository's `docs/` and changes in the PR that changes the code. Kit skills route to it.
- **An ADR records a decision about the product**, in `docs/decisions/` (pb) or `docs/adr/`
  (bsc-geth). A prose edit, a tooling change and a change to this kit never get one.
- **Nothing is gated twice.** No local composite before the GitHub run. A known-long command
  runs as foreground Bash at the tool's longest timeout, unless other work runs beside it: past
  that timeout the harness moves it to the background and notifies on exit, and a background
  start costs one more model request. `build/unit_run.py --wait <slug>` on srv is such a call.
  Never wait with `sleep` or a poll loop.
- **One gate command, one line:** `bk-gate <name> -- <command>` prints `gate: <name> rc=<n>
  t=<s>s out=<path>` and, on red, the last ten lines. Never pipe a gate into `tail` or `grep`.

## Tiers and dispatch

- Implementation and review run at opus: `blockchain-kit:golang-implementer`,
  `blockchain-kit:code-reviewer`, the auditors. Git legwork runs at sonnet, a gate run at
  haiku. The workflow fixes these; a hand dispatch states its tier.
- A workflow script written in the session names `model` on every `agent()`: sonnet for
  measurement, git legwork and verification; haiku for a schema or gate check; opus for
  implementation and review. The session's tier is written by name, only for a design or
  review stage where a wrong judgment is expensive, and is never inherited by omission. This
  overrides the harness's `workflow-authoring` text ("Default to omitting it — the agent
  inherits the main-loop model"), which on 2026-10-14 ran four measurement agents and their
  verifies at Fable. The kit's `workflow-tiers` hook refuses a script that leaves one unset.
- Judgment stays in the session: the plan, a contract, an invariant, the reading of a red
  gate, the decision to land.
- A dispatch that edits files gets the tree to itself, or its own worktree. Commit before you
  dispatch.
- A critic is terminal: it returns findings and consults no one. A worker with a question
  hands back.
- On a Fable main loop the advisor is called only to attack an inference you have stated:
  give your read first and stand on it (operator, 2026-09-17).
- The advisor is consulted before a workflow or an execution loop is spawned: the plan it
  would run is the inference it attacks (operator, 2026-10-19).

## The fork

bsc-geth is developed three ways (operator, 2026-10-14; `blockchain-kit:fork-development`):

- **In its own clone**, a session rooted in bsc-geth: node work, landed by step 6's push.
  `implement` runs in place: worktree lanes beside the clone, package-scoped gates, `make
  audit-ext`; the whole-module gates stay out of a lane (the tree is the production host's).
- **From prediction-bot**, in the clone `BSC_FORK_PATH` names: the workflow with `fork` set,
  serial, on a branch cut from `mrinal/dev`, gated by `make audit-ext`.
- **A bot change that needs a fork change** is the second way twice in one pb session: the
  fork run and its push, the pin move, then the bot run. No teammates, no second session.
- **One clone per open session:** a pb session's `BSC_FORK_PATH` never names a clone another
  session has open.

## On srv

- `pkill -f` matches the harness's own command line and kills the session. Kill by PID.
- The `go` on `PATH` is the one `go.mod` names; never put another Go's `bin` first.
- GitHub serves no diff for a PR over 300 files (`gh pr diff`: HTTP 406). Use `git diff`.

## Evidence

Every claim names how it is known: measured (where) or inferred (from what). A node API is
confirmed against the fork with a `file:line` (`bsc-fork show` in prediction-bot, the source
in bsc-geth). "Cannot" is a claim like any other: a failed attempt does not establish it.
A labelled inference does not discharge a recorded field that exists: before a number is
measured from a stand-in (a proxy event, a derived series, a sampled window), say whether the
directly recorded source exists, and read it when it does; a decoder it needs is a defect to
close in the batch, not a cost to avoid. A stand-in that stays names what it misses. The cost
of the direct path, a capped unit on srv included, never picks the evidence path. A subagent's
reading is preliminary until the main loop re-runs one cell of it; an inference a subagent
returns is never forwarded as measured.
