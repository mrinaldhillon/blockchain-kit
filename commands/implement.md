---
description: Run briefed Go units through the blockchain-kit implement workflow — parallel worktree lanes, one merged run branch, the gate, one review, one fix round.
argument-hint: "[what to implement, or nothing when the units are already in the conversation]"
disable-model-invocation: true
---

# Run `blockchain-kit:implement`

Arguments: `$ARGUMENTS`

This command is the user's request to run the workflow. The contract of its input and output
is the header of `workflows/implement.js`; the process around it is `blockchain-kit:working-here`.

1. **The units.** Each is `{id, brief, packages, skills?}`. The brief is the contract: the
   files, the interfaces with exact signatures, the test cases with their assertions, the
   invariants. If the conversation does not already hold units in that shape, write them now
   and show them before launching. Two units never share a package: split differently, or run
   them as two runs.
2. **Preconditions**, one Bash call each; stop and say which failed:
   - `git branch --show-current` is the run branch, and it is not `main`.
   - `git status --porcelain --untracked-files=no` prints nothing.
   - `.claude/settings.json` sets `worktree.baseRef` to `"head"` (Read it). Without it a lane
     starts at `origin/main` and the workflow drops it.
   - `git rev-parse HEAD` is the `head` you pass.
3. **The gate** is the offline check scoped to the units' packages, for example
   `make test-offline PKG='./internal/feeds/... ./internal/state/...'`. Never
   `make replay-parity`: the run reports when it is owed.
4. **Launch** the Workflow tool with `name: "blockchain-kit:implement"` and `args` as a JSON
   object `{units, branch, head, gate, project, module}` — plus `fork: "<absolute checkout
   path>"` when the units are fork work from prediction-bot, where `branch` is the branch
   checked out in the fork checkout, cut from `mrinal/dev`. `project` and `module` go on every
   run: `project` is the absolute project root (`git rev-parse --show-toplevel`), `module` the
   `module` line of the project's `go.mod` (Read it). The script cannot read the filesystem;
   from these it refuses a run rooted in the fork itself (`module` is
   `github.com/ethereum/go-ethereum` and `fork` is unset or equals `project`) until the kit's
   in-place fork mode lands. In a bsc-geth session, dispatch `blockchain-kit:golang-implementer`
   per unit instead. The run is in the background: do not poll it.
5. **When it returns**, adjudicate; nothing is pushed and no PR exists yet.
   - `handbacks`: answer the question, then re-run that unit alone.
   - `conflicted` and `stalled`: each names the branch or worktree it left. Decide whether to
     re-run the unit on the new head or drop it; remove what is abandoned
     (`git worktree remove`, `git branch -D`).
   - `gate` not green: read the tail; the fix is a new unit or yours.
   - `findings.open`: fix, defer to an issue, or accept, and say which.
   - `owed.parity`: run `make replay-parity` once. `owed.read`: read those units' diffs
     yourself before landing.
