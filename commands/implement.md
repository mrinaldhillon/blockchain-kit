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
   files, the interfaces with exact signatures, the invariants each test protects, and the
   Tests line every brief carries (`blockchain-kit:working-here`, step 3). If the conversation does not already hold units in that shape, write them now
   and show them before launching. Two units never share a package: split differently, or run
   them as two runs.
2. **Preconditions**, one Bash call each; stop and say which failed:
   - `git branch --show-current` is the run branch: in prediction-bot not `main`; in bsc-geth
     `mrinal/dev` or a branch cut from it, never `master` or `mrinal/master`.
   - `git status --porcelain --untracked-files=no` prints nothing.
   - `git rev-parse HEAD` is the `head` you pass.
3. **The gate** is the offline check scoped to the units' packages, for example
   `make test-offline PKG='./internal/feeds/... ./internal/state/...'`. Never
   `make replay-parity`: the run reports when it is owed. In bsc-geth it defaults to
   `make audit-ext`, the lanes having gated their own packages; a package-scoped `go test`
   may replace it, never `./...`, `make test` or `make lint` (the tree is the production
   host's).
4. **Launch** the Workflow tool with `name: "blockchain-kit:implement"` and `args` as a JSON
   object `{units, branch, head, gate, project, module}` — plus `fork: "<absolute checkout
   path>"` when the units are fork work from prediction-bot, where `branch` is the branch
   checked out in the fork checkout, cut from `mrinal/dev`. `project` and `module` go on every
   run: `project` is the absolute project root (`git rev-parse --show-toplevel`), `module` the
   `module` line of the project's `go.mod` (Read it). The script cannot read the filesystem;
   from these it picks its mode: the bot; the fork in place (`module` is
   `github.com/ethereum/go-ethereum` and `fork` is unset or equals `project`: worktree lanes in
   this clone, package-scoped gates); or a fork checkout from the bot (`fork` names another
   tree: serial). The kit's `implement-args` hook fills `project` and `module` from the tree
   when they are left out. A lane's worktree is made by the kit's `worktree-create` hook
   beside the clone, `<parent>/.<clone>.worktrees/wf_<run>-<n>`, from the session's HEAD;
   nothing is written under the clone's `.claude/`. The run is in the background: do not
   poll it.
5. **When it returns**, adjudicate; nothing is pushed and no PR exists yet. In bsc-geth the
   landing squashes the run branch to its feature commits before the push (`working-here`).
   - `handbacks`: answer the question, then re-run that unit alone.
   - `conflicted` and `stalled`: each names the branch or worktree it left. Decide whether to
     re-run the unit on the new head or drop it; remove what is abandoned
     (`git worktree remove`, `git branch -D`).
   - `gate` not green: read the tail; the fix is a new unit or yours.
   - `findings.open`: fix, defer to an issue, or accept, and say which.
   - `owed.parity`: run `make replay-parity` once. `owed.read`: read those units' diffs
     yourself before landing.
