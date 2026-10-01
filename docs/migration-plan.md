# Migration plan — steering moves to blockchain-kit

Date 2026-10-01. Implements `docs/design.md` (cited as D§n). Bases: prediction-bot (pb)
`01f5af59`, blockchain-kit `6796a58`, bsc-geth `mrinal/dev`.

**Style:** contract-first. Each task states what must be true when it is done and how that is
observed. Bodies are written at execution.

**Shape:** 7 phases, 4 PRs (kit, pb consolidation, pb cut, bsc-geth), no review seat on prose
or tooling. Shared homes with exactly one writer each: pb `CLAUDE.md` and
`.claude/settings.json` (phase 3), kit `workflows/implement.js` and
`agents/golang-implementer.md` (phase 2), pb `docs/project-context.md` (phase 1).

**Proof:** the kit's hermetic suite (`tests/run`) covers `bin/`, `lib/` and hook logic. Prose,
agents, skills and the workflow are proven by one live run each, recorded in the PR body.

## Global constraints

- pb's recorder and the prod host are not touched by any phase. No phase restarts a service.
- No history rewrite and no force-push without the operator's explicit instruction (phase 5
  step 3 only).
- GitHub writes that are not PRs — issue transfer, issue close, branch-protection edit — happen
  only in the phase that names them, after that phase's dry-run list has been shown.
- The pb tag `steering-final` is created on the commit before the cut and is never moved.
- A harness fact from D§9 is a hypothesis until its probe in phase 0 passes.

## Phase 0 — probes (no tracked edits)

Method: a scratch clone of pb with `.claude/` reduced to a trial `settings.json`, run with
`claude --plugin-dir ../blockchain-kit` unless the probe says otherwise. Each result is written
into the kit PR body as the observed string or number.

| # | Question | Observation that settles it | Decides |
|---|---|---|---|
| P1 | What `subagent_type` and hook `agent_type` does a plugin agent present? | A PreToolUse(Agent) and a SubagentStop payload for `blockchain-kit:parity-auditor`, logged by a throwaway hook | hook matchers in D§5.3 |
| P2 | Does a plugin hook run for an agent spawned by the Workflow tool, and for one in a worktree? | The same throwaway hook fires, or does not, during a two-unit workflow run | whether `guard-secrets` and `guard-prod-run` cover lanes |
| P3 | Where does an `isolation: 'worktree'` agent start, and how does its work come back? | In a two-unit run: each lane reports `git rev-parse HEAD`, its branch name and its worktree path; after it commits, the branch is visible from the session's tree | the Lane and Integrate contracts in D§7 |
| P4 | Does `agentType: 'blockchain-kit:golang-implementer'` resolve inside a workflow, with `model` and `skills:` honoured? | The lane names its model and quotes a line of `go` | D§7 stage 1 |
| P5 | Does a committed `extraKnownMarketplaces` + `enabledPlugins` load the kit on a fresh clone with no install step? Under `claude -p`? | `claude plugin list --json` and a session-start line in a fresh clone, interactive then headless | phase 4's per-clone step |
| P6 | Does dropping `version` make a new kit commit reach an installed copy? | Commit a marker line to the routing table; update; the next session quotes it | D§5.5 |
| P7 | Does `force-for-plugin: true` apply the kit's output style with no `outputStyle` in the project? | The session reports its output style | pb `settings.json` content |
| P8 | Do `CLAUDE_PROJECT_DIR` and `CLAUDE_PLUGIN_DATA` reach a plugin hook? | The throwaway hook prints both | D§5.3 state rule |
| P9 | What does a one-line change to `docs/*.md` select in pb today? | `make ci-select` on that diff: the lane list | D§8.1 selector rule, phase 3 task C6 |
| P10 | Is the bare local `make ci` denial in the Makefile or only in `composite_gate_guard.py`? | Read the `ci` target; run it bare with the hook disabled | D§6 hook disposition |

Also in this phase: `make tools` in the scratch clone (gopls and pyright MCP servers, the git
hook path). A probe that fails does not stop the plan; it changes the row it decides, and the
change is written into `design.md` in the same kit PR.

## Phase 1 — consolidate open plans and milestones (pb, one PR, prose class)

The precondition for deleting `.claude/superpowers/`. Inventory at `01f5af59` (measured, by a
heading-and-ledger count that is a first sort, not a verdict): 42 plans, 11 specs, 30 ledgers,
16 briefs. Plans whose ledgers show unfinished tasks: `2026-09-09-feedv2-consumption`,
`2026-09-06-m8-t457-closeout`, `2026-09-10-611-follow-up-run`,
`2026-09-17-778-node-path-replayability` (T7, T8 blocked on a fork SHA),
`2026-09-17-769-send-cutoff-measurement` (PR #775 in flight), `2026-09-17-840-instrumentation`,
`2026-09-09-subagent-isolation`, `2026-09-11-harness-selection`,
`2026-09-02-tooling-steering-closeout`. Plans with no ledger: twelve, among them
`2026-09-10-gap-evidence-records`, `2026-09-11-inserter-nonce-anchors`,
`2026-09-15-fork-pin-go1271`.

Tasks:

- **A1 Classify every plan and spec**: product or steering; then done, open, or abandoned.
  Read the ledger's last rows and the PR or issue it names, not the task count. Output: one
  table, plan → class → state → the issue that owns what remains.
- **A2 Open product work becomes issues.** For each open product plan: the remaining tasks,
  with their contracts, go into the body of the issue that already tracks it, or a new one.
  A blocked task names what blocks it. Nothing open exists only in a plan file afterwards.
- **A3 Durable design content moves to `docs/`.** A spec section that states an invariant, a
  contract or a measurement still true of the code goes to the matching file under pb
  `docs/`. Everything else in a spec is history.
- **A4 Milestone state**: `docs/project-context.md` §Current state and §In progress are brought
  up to date from the ledgers, and lose every reference to a plan path.
- **A5 Open steering plans are closed, not carried.** A steering plan's remaining tasks are
  listed for phase 6 as candidates, with the default "obsolete".

Done: the A1 table is in the PR body with no row in state "unknown"; `git grep -n
'superpowers/' -- docs CLAUDE.md` returns only SHA-pinned historical citations; the operator
has seen the list of issues created or amended.

## Phase 2 — the kit absorbs (kit, one PR from `steering-home`)

- **K1 Agents.** `golang-implementer`: no `LSP` in `tools:`; a section stating the lane
  contract of D§7 stage 1 (start at `head`, package-scoped gates through `bk-gate`, commit on
  the lane branch, the return shape, hand back rather than guess). Delete
  `golang-implementer-lite`. Add `ToolSearch` to both auditors. New `code-reviewer`: Read and
  Bash only; closed coverage over every changed path; the four reserved angles, each naming
  the pb doc that owns its invariant; findings as `{title, file, line, severity, why}`; never
  edits, never consults.
- **K2 `workflows/implement.js`** to D§7. Interfaces: the `args` table and the output object
  as written there. Cases the script must handle, each observable in its return value: two
  units sharing a package are rejected before any agent runs; a lane that returns `handback`
  is not merged; a conflicting lane is reported and the others still merge; a red gate skips
  review; a dead stage appears under `stalled` with the branch it left; a fork run is serial;
  a tier above opus is refused. `commands/implement.md` invokes it and is
  `disable-model-invocation: true`.
- **K3 `bin/bk-gate`** (Python: it times, captures and tails). Contract: D§5.4. Tests: exit
  code passthrough; exactly one verdict line; a red run prints at most ten tail lines; the
  full output is at the path the line names.
- **K4 `bin/bk-mainloop-share`** (Python). Contract: D§5.4; categories and precedence as in
  the 2026-10-01 measurement; one row per category with turns, output-token share and
  context share. Tests: a fixture transcript with one turn per category classifies as
  labelled; sidechain entries are ignored; a `git grep` call counts as a read.
- **K5 Hooks.** `guard-node-secrets` becomes `guard-secrets` with pb's generic patterns
  added. New `guard-prod-run` from pb `run_guard.py`, keyed on the same host test the context
  hook uses. `blockchain-kit-context` gains the environment line, the `core.hooksPath` line
  and the stray-file line of D§5.3. Tests: each new pattern denied and its `testdata/`
  counterpart allowed; a bare prod run denied on a host marked prod and allowed on dev; the
  three context lines present and absent as their conditions change; every hook exits 0 on
  an unparseable payload except the two guards, which deny.
- **K6 Skills.** New `working-here` (D§5.1, D§8, D§8.1; at most 120 lines; names
  `dev-setup/ci/land` and the change classes). `using-blockchain-kit`: rows for
  `working-here`, `code-reviewer` and `/blockchain-kit:implement`; the lite row removed.
  `fork-development`: the "no steering of its own" sentence stated as the target, not as
  present fact, until phase 5 lands. Domain skills are thinned in phase 3, when their facts
  have a home in pb.
- **K7 Setup and versioning.** `installed_field` takes a scope and matches a project install
  by `projectPath`; `blockchain-kit-setup` and `-update` accept `--scope user|project`;
  `plugin.json` loses `version` (subject to P6). Tests for both scopes.
- **K8 Output style**: `output-styles/distinguished-engineer.md` from pb, with
  `force-for-plugin: true` (subject to P7).
- **K9 Kit CI and README.** A pull-request workflow running `tests/run`, `claude plugin
  validate .`, shellcheck and ruff. README: the layout, the working model, project-scope
  enablement; the "Adopting it" section replaced by a pointer to `docs/`.

Done: `tests/run` and `claude plugin validate .` green; one live `/blockchain-kit:implement`
run of two real units in the phase-0 scratch clone, its return object pasted into the PR
body; P1–P8 recorded.

## Phase 3 — the pb cut (pb, one PR)

Order inside the PR: knowledge first, deletion last, so every intermediate commit still has
its steering.

- **C1 Facts to `docs/`.** For each of the seven domain skills and the three fact-bearing
  rules (`docs-code-boundary`, `host-deploy`, `python`): any statement about the code that
  has no home under `docs/` gets one, in the file that already owns the topic. The kit's
  copies are thinned to routers in a kit commit that lands first; the pb PR follows it.
- **C2 Tag** `steering-final` on the PR's base commit.
- **C3 `dev-setup/ci/land`** (language by the plan-authoring rule: it parses `gh` JSON, so
  Python). Contract: given a PR, it finds the head SHA; when the selector classes the diff
  `none`, it posts `ci` success on that SHA; otherwise it dispatches `ci` on the branch,
  waits for the run pinned to that SHA, and stops on red with the failing tail; on green it
  squash-merges and deletes the branch; it prints one verdict line. It refuses a PR whose
  head moved after the run started. No ledger, slice or steering-status logic.
- **C4 Delete** everything under `.claude/` except `settings.json`; delete
  `.github/workflows/steering.yml`; remove the overlay's rows from `dev-setup/layout-map.tsv`
  and `dev-setup/dev-setup.md`.
- **C5 `.claude/settings.json`** to D§4.1. **`CLAUDE.md`** to D§4.1: at most 150 lines, no
  reference to a deleted path.
- **C6 Selector**: a prose-only diff selects no lane (subject to P9; a lane that P9 shows
  selected is either given the inputs it really reads or left, with the reason in the PR).
- **C7 The engineering ADR** in `docs/decisions/`: no steering layer in this repo; home is
  blockchain-kit; supersedes 0032.
- **C8 Branch protection**: required contexts become `ci` alone. This is the PR's last step
  before merge and is the operator-visible GitHub write of this phase.

Done: `git ls-files .claude` prints one path; `git grep -n -F '.claude/' -- ':!docs/decisions'
':!docs/reports' ':!research'` prints nothing outside SHA-pinned citations; a fresh session
in a fresh clone shows the kit's routing table and no stray-file line; a one-line `docs/`
change lands through `dev-setup/ci/land` with zero Actions minutes; one real product unit
lands through `/blockchain-kit:implement` and `land`.

## Phase 4 — clones, the prod host, the driver loops

- Each clone (`prediction-bot`, `pb-steer`, `bot`, `botbase`, `bot-chores`, `bot-layout`,
  `wip-branch`) pulls the cut. Whatever P5 showed is needed per clone is done once per clone.
  `prediction-bot` is mid-flight on `chore/send-lead-cut`; it rebases after the cut.
- The prod host: the kit reachable with the host's git credentials; folder trust accepted;
  `BSC_FORK_PATH` set where fork work happens.
- `milestone_run.py` and the conductor are gone with the layer. Unattended work, if wanted
  again, is a workflow run started from a session; it is not rebuilt here.

Done: in every clone a fresh session quotes the kit's pin line.

## Phase 5 — bsc-geth

1. Facts to `docs/`: what the kit's `features.md` and `landmines.md` say that the fork's
   `docs/` does not; the kit's copies become pointers.
2. One commit on `mrinal/dev` deleting `CLAUDE.md`, `.claude/` and, if present, `.mcp.json`.
   `.githooks/` stays.
3. Only on the operator's instruction, at the next upstream rebase: commits whose every path
   is steering are dropped from the stack. The path set is decided then, commit by commit;
   `.githooks/` and `docs/` commits are not steering.

Done: `git -C "$BSC_FORK_PATH" ls-files .claude CLAUDE.md .mcp.json` prints nothing; a pb
session with `BSC_FORK_PATH` set completes one fork edit, `make audit-ext` and a pin move
under the kit's fork skills.

## Phase 6 — issues

- **I1 Classify** pb's open issues carrying `steering` or `tooling` (124 at 2026-10-01) and
  bsc-geth's open issues (53, almost all unlabelled), one row each: *product* (stays),
  *kit* (still true of the kit's design), *obsolete* (about a retired mechanism). A read-only
  fan-out; the table is shown to the operator before any write.
- **I2 Transfer** the *kit* rows to blockchain-kit with `gh issue transfer`. **Close** the
  *obsolete* rows with one comment naming the tag and this plan. Labels `steering` and
  `deferred`-as-steering are retired in pb once empty.

Done: pb's open issues carry no `steering` label; every transferred issue resolves in the
kit; the counts moved, closed and kept are reported.

## Phase 7 — measure

After ten pb sessions under the kit: `bk-mainloop-share` against the baseline in D§10, and
the token cost of a session start with the kit against the old layer's. Both numbers go into
`design.md`. A subtotal above 15% of turns names the category that did not fall, and that
category is the next change to the kit.

## Rollback

- Phases 0–2 change only the kit and scratch state: drop the branch.
- Phase 1 is prose in pb: revert the PR; the issues it created stay and are harmless.
- Phase 3: revert the PR and restore `steering` in branch protection. The tag holds the
  layer regardless.
- Phase 5 step 2: revert the commit. Step 3 has no rollback but the pre-rebase ref, which is
  kept until the operator releases it.
- Phase 6: a transferred issue can be transferred back; a closed one reopened.

## API-risk register

| Surface | Why it is a risk | Falsified by |
|---|---|---|
| Workflow `isolation: 'worktree'` branch point and hand-back | Undocumented; pb's own notes say a worktree branches from the default branch | P3 shows a lane cannot reach `head` or its commit is not visible to Integrate |
| Plugin hooks inside workflow agents | Undocumented | P2 shows no fire: lanes then run without the secrets and prod-run guards, and D§7 must say so or the lane prompt must carry the rule |
| Project-scope load without install | Docs only; the other session's review read the opposite | P5 shows the "enabled but not installed" notice |
| Commit-SHA versioning | Docs only | P6 shows a stale copy after update |
| `gh workflow run` then finding the run for a SHA | Dispatch returns no run id; the run must be matched by head SHA | `land` merges on a run for another SHA in a test with two quick pushes |
| Posting `ci` from `land` on a `none` diff | Needs a token with status scope; branch protection is strict | The status is rejected, or the merge is refused as out of date |
| `gh issue transfer` between private repos of one owner | Labels and milestones without a namesake are dropped | A dry run on one issue loses data the kit needs |
