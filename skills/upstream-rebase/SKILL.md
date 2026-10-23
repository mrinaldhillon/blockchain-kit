---
name: upstream-rebase
description: Use when adopting a new upstream bnb-chain/bsc release tag as the bsc-geth fork's base — moving mrinal/master to the tag and rebuilding mrinal/dev's feature-level history on top of it. Covers the pre-rebase survey, the oracle-then-replay method, the differential proof, the rebase-specific gates, the guarded ref moves, and the bot's pin move afterwards. Not for ordinary fork feature work, and not for the production cutover.
disable-model-invocation: true
---

# Upstream rebase — adopting a new base tag

The fork's base moves only to upstream's newest **stable** tag — never to
`upstream/master` or an alpha/RC. The branch model this operates on
(`master` mirrors upstream; `mrinal/master` is the fork's master; `mrinal/dev`
carries the feature-level history) is `blockchain-kit:fork-development`
§What the fork is.

`mrinal/master` is not touched (operator, 2026-10-14): everything lands on
`mrinal/dev`. The steps below that move `mrinal/master` are the documented
procedure and run only on the operator's explicit instruction.

Everything here runs in the fork tree. In a session rooted in a bsc-geth clone the
commands are plain (`git …`, `make …`); from a prediction-bot session they name the
checkout (`git -C "$BSC_FORK_PATH" …`, `make -C "$BSC_FORK_PATH" …`). The commands
below are written in the plain form. From prediction-bot, the bot's `go.work` is
**off** for the whole rebase (`make go.work-off`): the bot keeps compiling the old pin
until the last step.

## The survey — before any branch moves

1. Fetch the target:
   `git fetch https://github.com/bnb-chain/bsc.git tag vNEW --no-tags`
   (and refresh `origin/master`, which tracks upstream).
2. **Consume the fork's rebase landmines** (its docs index, `docs/fork/README.md`, lists the
   document; the full inventory is `2026-10-04-rebase-v180-inventory.md` in the review history
   the index names; `references/landmines.md` points there) — it is written for exactly
   this moment: removed config keys
   that are fatal at startup, removed mechanisms that take fork hooks with them,
   and the deliberately re-semanticized surfaces that must keep the fork's
   version in every conflict, not upstream's.
3. `make audit-ext` must exit 0 on the pre-rebase tree — start from a clean
   Ext-surface inventory; the same sweep re-runs as a closing gate and rides
   `make lint`. Its allowlist (`build/audit-ext-allow.txt`) is kind-keyed and
   base-anchored: a symbol finding's row is `CHECK<TAB>path:Symbol@kind`, where
   `kind` names what the finding is (the file's header lists them). Re-baseline
   it after the rebase, and delete whatever the run then reports as ALLOW-STALE.
4. Forecast the conflicts: for each file the fork touches
   (`git diff --name-only $(git merge-base HEAD origin/master) HEAD`),
   inspect upstream's movement with `git log --oneline vOLD..vNEW -- <path>`.
   A fork hook whose upstream anchor was deleted is a design question for the
   session, not a merge-time improvisation.
5. Forecast the bot: every row of the fork index is a surface the bot depends on
   (`bsc-fork list`). One that upstream renamed, moved or removed is a bot change
   that rides with the pin move.

## The method — oracle first, history second

- **Safety net before anything moves:** tag the old tip —
  `git tag -a archive/mrinal-dev-<old-base>-base <old dev tip>`. It is the
  only recovery point for the eventual force-push; do not skip it.
- **Oracle:** bring the complete fork delta onto the new tag on a scratch
  branch and make that one tree fully green (build, vet, lint, tests) before
  shaping any history. The oracle is the byte-exact target state; everything
  after it is history construction, not new porting work.
- **Feature-level replay:** rebuild the history as one commit per feature so
  the base stays cheap to re-rebase. When transcribing wiring hunks forward
  is risky, use the reverse-strip method: strip one feature at a time from
  the oracle, letting the compiler name every wiring line that belongs to it,
  then replay the recorded trees forward as the commits.
- **The differential proof:** the new tip's tree is byte-identical to the
  oracle (`git diff --exit-code <oracle> <new-dev>` is empty) and the new
  range contains zero merge commits. With reverse-strip, both hold by
  construction; assert them anyway.

## Rebase-specific gates

On top of the fork's standard gates (`make geth`, `make test`, `make lint`;
`blockchain-kit:fork-development` §Commands, heavy work as a capped unit), a
rebase adds:

- **Vet baseline:** run `go vet ./...` on the pristine new tag first and
  record its accepted findings; on the fork tree, any *additional* line is a
  real regression — upstream's own findings are the baseline, not noise.
- **Generated TOML codec:** regenerate `eth/ethconfig/gen_config.go` with
  `go generate ./eth/ethconfig/` — never hand-edit it — then assert every
  fork `*Ext` key from `eth/ethconfig/config.go` still appears in the
  generated file. Regenerating from an upstream-only struct silently drops
  the fork keys and still builds; the failure would otherwise surface only at
  node start.
- **Deploy contract:** `deploy/production/check-config-ext.sh` against the
  deploy pairing, plus a `dumpconfig` decode of the production `config.toml`
  with the freshly built binary and a re-validation of every `ExecStart`
  flag — read stderr, not just exit codes. Removed-upstream keys must stay
  removed (the landmines document names the fatal ones).
- **Ext surface:** `make audit-ext` exits 0 on the rebased tree. The
  rename direction matters most here — conflict resolution is where an
  upstream symbol accidentally picks up a fork marker.
- **Identity:** `./build/bin/geth version` reports the new base version, and
  `make geth-prod` still builds.
- **Host discipline:** when the session runs on the host that runs the
  production node, pin every build, test, and lint to the housekeeping cores
  from `/etc/pinnedCPU` (`taskset -c 0-3,16-19`), and touch nothing about the
  live service.

## Moving refs — the guarded steps

- `mrinal/master` → the new tag. Where the fork tree's git hooks are armed
  (`git config --get core.hooksPath` prints `.githooks`; `make dev-setup` arms
  them), `reference-transaction` holds `master` and `mrinal/master` to commits their origin counterpart already
  has; `BSC_REFS_GUARD_DISABLE=1` is the human escape, and this is its one
  sanctioned use. Every other ref move stays guarded.
- `mrinal/dev` is force-moved only after the differential proof and the full
  gate roster pass. The push commands — archive tag, upstream-mirror refs,
  `--force-with-lease` on `mrinal/dev` — are printed for the maintainer to
  run, never run by an agent.
- One PR to `mrinal/master`, only when the operator says so (see above).
- The oracle and scratch branches survive locally until the maintainer
  confirms the push landed.

## Afterwards

- **Move the bot's pin** to the rebased `mrinal/dev` tip and re-index, in a
  prediction-bot session: `blockchain-kit:fork-development` §The loop, steps 6
  to 8. The old pin's commit is no longer on `mrinal/dev` after the force-push;
  until the pin moves, `make fork-pin-check` is red.
- **Rewrite the fork's landmines document for the next
  target** — each rebase consumes it and refills it for the following one, in
  a bsc-geth commit. The kit's `references/landmines.md` stays a pointer.
- The production cutover, soak, and PGO recapture are out of scope:
  `deploy/production/CUTOVER_RUNBOOK.md` owns them.
- Open work from the run is issues; a durable inventory goes in the fork's
  review history (as `2026-10-04-rebase-v180-inventory.md` did). No plan or
  ledger is tracked. Worked example of this whole method (the v1.7.8
  adoption, a record of the past): `2026-08-16-fork-rebase-v1.7.8.md` in the plan history
  and `2026-08-16-fork-rebase-v1.7.8-design.md` in the spec history. The fork's docs index,
  `docs/fork/README.md`, names all three history directories.
