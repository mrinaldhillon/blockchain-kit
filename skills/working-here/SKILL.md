---
name: working-here
description: "How work moves: plan, issues, units, the implement workflow, landing."
---

**When to load:** How work moves in prediction-bot and the bsc-geth fork from a Claude session: explore and plan in the session, persist open work as issues, cut briefed units, run the implement workflow, adjudicate its result, land with dev-setup/ci/land. Load before a multi-step change, before cutting units, and before landing.

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
   `docs/project-context.md`. An issue about Claude itself (steering, this kit, a hook, skill,
   agent or workflow, the harness, model cost) is filed in `mrinaldhillon/blockchain-kit`,
   never in the repository you are working in (operator, 2026-10-14).
3. **Cut units.** A unit is `{id, brief, packages, skills?}`:
   - The brief is a contract: the files, the interfaces with exact signatures, the test cases
     with their assertions, the invariants, and what is out of scope. Bodies are the
     implementer's. A brief the implementer would have to guess from is not ready.
   - Units are independent: no two share a Go package, and none needs another's result. Work
     that is coupled is one unit.
   - Name the kit skills a unit needs. A subagent gets none by description.
4. **Run `/blockchain-kit:implement`** when the user asks for it: lanes in worktrees, one
   merged run branch, the gate, one review, one fix round. It runs in the background and
   returns `{merged, conflicted, handbacks, stalled, gate, findings, owed, head}`.
5. **Adjudicate.** Hand-backs are questions for you. A conflicted or stalled lane names what
   it left. Open findings are fixed, deferred to an issue, or accepted, and you say which.
   `owed.parity`: run `make replay-parity` once. `owed.read`: read those diffs yourself.
6. **Land** with `dev-setup/ci/land <PR>`: it runs the lanes the diff selects on the PR head and
   squash-merges on green. Merging needs no confirmation in prediction-bot; a production deploy
   is a separate decision and is the operator's. `land` runs in the foreground under
   `timeout 590`: on srv the harness kills background tasks under memory pressure. A re-run
   attaches to the live CI run.

One unit, or a change too small to brief, skips steps 3 to 5: dispatch
`blockchain-kit:golang-implementer` once, or make a prose or tooling edit yourself.

When the operator is offline, run the approved plan to completion and batch what only they
can answer for the end (operator, 2026-09-09).

## What a change owes

The class is read off the diff, and the class decides the ceremony.

| Class | The diff | Gate | Review | Record |
|---|---|---|---|---|
| Prose | docs, comments, `CLAUDE.md` | none: `land` posts `ci` with no run | none | none |
| Tooling | `dev-setup/`, `scripts/`, Makefile, CI workflow, `tools/` | the lanes the selector names | none | none |
| Product Go | `cmd/`, `internal/` | the lanes the selector names | one seat at merge: the workflow's, or one `blockchain-kit:code-reviewer` dispatch | none |
| Guarded Go | record spine, hot path, money path | the same, plus `make replay-parity` when owed | the same, and you read the diff | an ADR only when an invariant, a stored-data contract or a boundary changes |

- **One branch per change, whatever it touches.** Code, its docs and its tooling land together.
- **A fact has one home, so a change has one edit.** A fact about the code lives in the
  repository's `docs/` and changes in the PR that changes the code. Kit skills route to it.
- **An ADR records a decision about the product**, in `docs/decisions/`. A prose edit, a tooling
  change and a change to this kit never get one.
- **Nothing is gated twice.** No local composite before the GitHub run. A known-long command
  runs as background Bash from the start.
- **One gate command, one line:** `bk-gate <name> -- <command>` prints
  `gate: <name> rc=<n> t=<s>s out=<path>` and, on red, the last ten lines. Never pipe a gate
  into `tail` or `grep`.

## Tiers and dispatch

- Implementation and review run at opus: `blockchain-kit:golang-implementer`,
  `blockchain-kit:code-reviewer`, the auditors. Git legwork runs at sonnet, a gate run at
  haiku. The workflow fixes these; a hand dispatch states its tier.
- Judgment stays in the session: the plan, a contract, an invariant, the reading of a red
  gate, the decision to land.
- A dispatch that edits files gets the tree to itself, or its own worktree. Commit before you
  dispatch.
- A critic is terminal: it returns findings and consults no one. A worker with a question
  hands back.
- On a Fable main loop the advisor is called only to attack an inference you have stated:
  give your read first and stand on it (operator, 2026-09-17).

## The fork

bsc-geth is developed from a prediction-bot session, in the checkout `BSC_FORK_PATH` names.
Fork units go through the same workflow with `fork` set: serial, on a branch cut from
`mrinal/dev`, gated by `make audit-ext`. A change that spans both repositories is two runs, the
fork's first, then the pin move (`blockchain-kit:fork-development`).

## On srv

- `pkill -f` matches the harness's own command line and kills the session. Kill by PID.
- The `go` on `PATH` is the one `go.mod` names; never put another Go's `bin` first.
- GitHub serves no diff for a PR over 300 files (`gh pr diff`: HTTP 406). Use `git diff`.

## Evidence

Every claim names how it is known: measured (where) or inferred (from what). A node API is
confirmed against the fork with a `file:line` (`bsc-fork show`). "Cannot" is a claim like any
other: a failed attempt does not establish it.
