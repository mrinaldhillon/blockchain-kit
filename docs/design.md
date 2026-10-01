# blockchain-kit as the steering home — design

Date 2026-10-01. Sources read: prediction-bot (pb) `01f5af59`, blockchain-kit `6796a58`,
bsc-geth `mrinal/dev` in `../bsc`. Evidence class is named per claim: **measured** (a command
run on those trees), **docs** (Claude Code docs, read 2026-10-01, not yet observed live) or
**decided** (the operator's ruling in the 2026-10-01 session).

## 1. Decision

Claude steering for prediction-bot and bsc-geth lives in blockchain-kit. Both repos keep only
project-fact documentation and the minimum the harness requires. The kit has one consumer
pair and is free to name their paths, make targets and branches. (decided)

This supersedes pb ADR 0032 (vendor the steering layer) and, with it, the steering ADR corpus
under pb `.claude/decisions/`: those records govern a layer that stops existing. They stay
addressable at the pb tag `steering-final`; they are not copied here. This file is the kit's
one decision record. A change of design is a PR to this file, with no ADR ceremony.

## 2. Why

- **Noise in the engineering repos** (measured). pb: 124 of 203 open issues carry `steering`
  or `tooling`; `.claude/` is 408 of about 1,460 tracked files, 95k lines. bsc-geth: up to 74
  of the 382 non-merge commits on `mrinal/dev` since `v1.7.8` touch only steering paths, and
  every one is replayed at each upstream rebase.
- **The main loop orchestrates instead of thinking** (measured: 28 pb sessions, 2,704
  main-loop turns, 14 days). Dispatching, bookkeeping writes, git/gh legwork and gate runs
  are 40% of turns and 53% of output tokens. Plans, specs, ADRs and docs are 2% of turns.
- **Fork changes are bot changes** (decided). bsc-geth is pinned by pb as its go-ethereum;
  most fork work needs bot work. One session rooted in pb develops both.
- **pb is built to shed the overlay** (measured). `dev-setup/dev-setup.md` §Layout classes
  `.claude/` as an overlay; the root `Makefile`, `dev-setup/ci` and `ci.yml` do not name it.
  The one reverse dependency is the merge step (§4.3).

## 3. The placement rule

Every line of the current layer falls in one of four classes. The class decides the home.

| Class | Test | Home |
|---|---|---|
| Fact about the code | Would a human contributor need it, with no agent involved? Must it change in the PR that changes the code? | the repo's `docs/` |
| Engineering tooling | Does a human run it to build, check or land the product? | the repo's `dev-setup/` |
| Product-invariant enforcement | Would its absence let anyone, human or agent, damage the product? | an agent-independent layer: git hooks, branch protection, CI, the script itself |
| Agent behaviour | Is it about how a Claude session routes, dispatches, tiers, guards or reports? | blockchain-kit |

Consequences:

- A kit skill is a **router**: when to load, which repo doc holds the facts, which command
  answers the question. It does not carry a copy of the facts. `fork-development`'s
  `references/features.md` and `upstream-rebase`'s `references/landmines.md` are copies today
  and go back to bsc-geth `docs/`; the pb domain skills keep only what is not already in pb
  `docs/`.
- A guard that fires only inside Claude Code never protected against a human. The
  main-branch guard is already `dev-setup/githooks/reference-transaction` plus branch
  protection (measured), so pb's `main_guard.py` hook is not carried.
- **One home, no shadow.** The earlier plugin attempt left repo-local copies beside the
  plugin and they diverged. Here the repo has no copy to diverge: the kit's session-start
  hook reports any tracked file under the project's `.claude/` other than `settings.json`.

## 4. What each repo keeps

### 4.1 prediction-bot

| File | Content |
|---|---|
| `CLAUDE.md` | Project facts only: what the project is, the commands table, architecture at a glance, the non-negotiable invariants, the environment rule, the standard of evidence, the operator authorizations (merge without asking, privileged prod commands, where to ask), the map of docs. Target at most 150 lines. No routing, tiers, hooks, rotation or pipeline text. One line names blockchain-kit as the steering home. |
| `.claude/settings.json` | `extraKnownMarketplaces` (the kit's git repo), `enabledPlugins` (the kit on; nothing else listed), `worktree.baseRef: "head"` (§7 depends on it: the default `fresh` starts a lane at `origin/main` — measured), `env` (`GOPRIVATE` and `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`), `enabledMcpjsonServers`, and a `permissions.allow` list trimmed to what remains. No `hooks`, `statusLine`, `outputStyle` or `skillOverrides`. Keys in the order the plugin CLI writes them — `$schema`, `env`, `enabledMcpjsonServers`, `worktree`, `enabledPlugins`, `extraKnownMarketplaces` as observed, with the plugin keys last — so a per-clone install leaves no diff (measured: `plugin install --scope project` rewrites the file). |
| `.mcp.json` | The pyright server loses its `-p .claude/pyrightconfig.json` argument: with the overlay gone the server exits on it (measured). Otherwise unchanged. The `gopls` and `pyright` servers start the repo's pinned binaries under `dev-setup/`, and the key `gopls` keeps the tool names `mcp__gopls__*` that the kit's agents are granted. |
| `.gitignore` | Gains `.claude/worktrees/`: lane worktrees live there and the rule that ignores them today is `.claude/.gitignore`, which the cut deletes (measured). |
| `docs/decisions/` | One new engineering ADR: this repo carries no steering layer; its home is blockchain-kit. |
| `dev-setup/` | Gains the land script (§4.3). |

Everything else under `.claude/` is deleted, with `.github/workflows/steering.yml`.

### 4.2 bsc-geth

Nothing: no `CLAUDE.md`, no `.claude/`, no `.mcp.json`. `docs/`, `build/auditext`,
`make audit-ext`, `deploy/` and `.githooks/` stay; they are the fork's product and its gates.
The steering-only commits are dropped from the patch stack at the next upstream rebase. That
is a rewrite of a pushed branch and runs only on the operator's explicit instruction.

### 4.3 The merge step is engineering

`ci.yml` has no `pull_request` trigger; a run is dispatched per PR and posts the `ci` status,
and branch protection on `main` requires `ci` and `steering`, strict, admins included
(measured). Today `.claude/tools/land.py` (1,826 lines) is what dispatches. After the cut:

- Branch protection requires `ci` only.
- `dev-setup/ci/land` is a small script a human can run: dispatch `ci` on the PR head, wait
  for that run, squash-merge on success, delete the branch; print one verdict line and the
  failing tail on red. It carries none of `land.py`'s slice, ledger or status-posting logic.

## 5. What the kit carries

### 5.1 Skills

| Skill | Role |
|---|---|
| `using-blockchain-kit` | The routing table, injected at session start. |
| `working-here` (new) | The process, in at most 120 lines: explore, plan, cut units, run `implement`, adjudicate, land. Replaces `orchestration`, `git-workflow`, `milestone-workflow`, `dev-workflow`, `plan-authoring` and the superpowers pipeline. |
| `go` | Go authoring bindings. Unchanged. |
| `fork-lookup`, `fork-node-api`, `contract-abi`, `binance-streams`, `record-format`, `replay-parity`, `environment-detection`, `hot-path-determinism` | Routers to pb `docs/`. |
| `fork-development`, `fork-ext-convention`, `fork-deploy`, `upstream-rebase` | Routers to bsc-geth `docs/`, plus the pin-and-checkout loop. |

### 5.2 Agents

| Agent | Tier | Change from `6796a58` |
|---|---|---|
| `golang-implementer` | opus | Drops `LSP` from `tools:` (it is never in the live roster — measured). Its "never `git commit`; a brief cannot lift that" rule is replaced by the lane contract (§7): at `6796a58` both probe lanes refused to commit against the brief (measured). Absorbs `golang-implementer-lite`, which is deleted: implementation runs at opus (decided). |
| `code-reviewer` (new) | opus | One seat over the merged diff of a run. Carries pb's reserved angles: determinism and parity, the record spine, import boundaries, hot-path blocking. Read and Bash only. |
| `determinism-auditor`, `parity-auditor`, `fork-indexer`, `fixture-capturer`, `infra-profiler` | opus | Unchanged. An agent without `ToolSearch` gets its granted `mcp__gopls__*` tools undeferred and callable (measured on `parity-auditor`), so the auditors need no new grant. |

pb's other eleven agents are not carried (§6).

### 5.3 Hooks

| Hook | Event | Contract |
|---|---|---|
| `blockchain-kit-context` | SessionStart | Routing table; pin and checkout lines; the kit's own installed SHA (a clone left behind runs an old kit silently — §5.5); one environment line (prod host or dev, from pb's `env_banner`); one line when `core.hooksPath` is unset or its `reference-transaction` hook is missing or not executable; one line, with a count and the first three paths, when the project tracks anything under `.claude/` other than `settings.json` (one line per file would be 407 lines in pb before the cut, and the hook's context spills to a file above 10,000 characters). Prints nothing outside a fork client. Never fails a session. |
| `guard-secrets` | PreToolUse, file tools | The node material it guards today, plus pb `guard_secrets.py`'s generic patterns (dotenv family, `*.pem`, `*.key`, `*.p12`, `secrets/`). One hook. Fails closed. |
| `guard-prod-run` | PreToolUse, Bash | The binary class of pb `run_guard.py`: on the prod host, deny a bare replay, bot or collector run that bypasses `scripts/replay-run.sh`. Fails closed. Protects the recorder log. The command is classified with `shlex` at command position, not with pb's 787-line `cmdclass`; the residuals are in the hook's header. `run_guard.py`'s second class (heavy local work through `unit_run.py`) is not carried: it is a rule about pb's own runner, and if it is wanted it belongs in the `make` targets it names. |
| `gofmt-on-edit` | PostToolUse | Unchanged. |

Each hook has a kill switch in the `BLOCKCHAIN_KIT_*` family and reads project state through
`CLAUDE_PROJECT_DIR`; anything it persists goes under `CLAUDE_PLUGIN_DATA` (docs).

### 5.4 Commands on `PATH`

| Command | Contract |
|---|---|
| `bsc-fork` | Unchanged. |
| `bk-gate [-C DIR] <name> -- <command>` | Run one command, in the caller's directory or in `DIR`; print exactly one line `gate: <name> rc=<n> t=<s>s out=<path>` and, on red, the last ten lines of its output. Exit with the command's code. From pb `gate.py`. |
| `bk-mainloop-share <transcript-dir> <days>` | The classifier behind §2's table. The kit's one metric (§10). |
| `blockchain-kit-setup`, `-update` | Accept `--scope user|project`; `installed_field` matches a project-scope install by `projectPath`. |

### 5.5 Other components

- `workflows/implement.js`, rewritten to §7; `commands/implement.md` is the user-invoked
  entry, because the Workflow tool runs only on an explicit request.
- `commands/init.md`: gains the check that the project's `.claude/` holds only `settings.json`.
- `output-styles/distinguished-engineer.md` with `force-for-plugin: true` (docs), so the
  project sets no `outputStyle`.
- `plugin.json` drops `version`, so the commit SHA is the version (measured: the install's
  version is the 12-character SHA). A kit commit does not reach an installed copy on its own:
  neither a new session nor `"autoUpdate": true` on the marketplace entry moved it within the
  windows measured. `blockchain-kit-update` runs `claude plugin marketplace update` then
  `claude plugin update blockchain-kit@blockchain-kit --scope project`, and the next session
  has the commit (measured). The marketplace entry keeps the relative source `./`.
- Kit CI: `tests/run`, `claude plugin validate .`, shellcheck and ruff, on pull requests.

## 6. Disposition of pb's current layer

ADOPT: reworked into the kit. REPO: moves to pb as engineering. RETIRE: not carried; available
at the tag. The retire class is mostly machinery that polices or records hand orchestration,
which the workflow replaces (§8). A retired mechanism returns only when its absence costs
something observed.

**Hooks (31).** ADOPT: `guard_secrets`, `run_guard`, `gofmt_on_edit`, `env_banner` and
`git_guard_check` (as context lines). RETIRE: `dispatch_guard`, `dirty_tree_guard`,
`agent_write_guard`, `retry_guard`, `wait_guard`, `delegation_ladder_inject`,
`delegation_nudge`, `main_loop_edit_nudge`, `piped_gate_nudge`, `pr_boundary_nudge`,
`gate_reds`, `rotate_nudge`, `rotate_trigger`, `rotate_actuate`, `precompact_hold`,
`checkpoint`, `resume_inject`, `startup_resume`, `state_sweep`, `subagent_trail`,
`commit_trailers`, `issues_inject`, `validate_config`, `py_diagnostics`, `main_guard`.
`composite_gate_guard`: the denial of a bare local `make ci` exists only in this hook
(measured: `PB_COMPOSITE_OK` appears nowhere in the `Makefile` or `dev-setup/ci`), so it moves
into the Makefile target (REPO).

**Tools (41 scripts and `conductor/`).** ADOPT: `gate.py` as `bk-gate`. REPO: the land step,
rewritten small (§4.3). REPO if the operator wants them as engineering checks, else RETIRE:
`lockstep_check.py`, `adr.py`, `sweep.py`. RETIRE: everything else, including
`steering_lint.py`, `skill.py`, `brief.py`, `land.py`, `ci_watch.py`, the `milestone_*` and
`rotate_*` scripts, `conductor/`, `slice_close.py`, `resume_check.py`, the metrics scripts,
`issues.py` and `defer.py` (an issue is filed with `gh issue create`).

**Agents (18).** ADOPT: the seven the kit has, and `code-reviewer`. RETIRE: `advisor-plus`,
`config-auditor`, `doc-sync`, `docs-implementer`, `tooling-implementer`,
`mechanical-implementer`, `generalist`, `harness-docs`, `intent-reconciler`, `search`,
`golang-implementer-lite`.

**Skills (27).** ADOPT: the seven domain skills. RETIRE: the eleven vendored superpowers
skills, `deep-research-tiered`, `local-code-review`, `skill-maintenance`, and the five
process skills that `working-here` replaces.

**Rules (6).** `hot-path-determinism`: kit skill (a plugin ships no path-scoped rule; docs
and the kit's own probe). `docs-code-boundary`, `host-deploy`, `python`: facts about the
repo, folded into pb `docs/` where not already there. `claude-md-editing`,
`hook-authoring`: RETIRE; what the kit needs of them is §5.3.

**Commands (9), output style, statusline, `delegation.json`, `agent-blocks/`.** RETIRE,
except the output style (§5.5). The statusline is the user's own setting.

**Records.** `.claude/decisions/` (61), `.claude/reports/` (11) and `.claude/superpowers/`
(125 files of plans, specs, ledgers and briefs) are deleted after the consolidation in the
migration plan, and remain at the tag.

## 7. The `implement` workflow contract

One run takes several briefed units to one merged, gated, reviewed branch. Parallel lanes in
worktrees; one review when the lanes merge; no per-lane reviewer and no refuters (decided).

**Input** (`args`):

| Field | Meaning |
|---|---|
| `units[]` | `{id, brief, packages?, skills?}`. `brief` is the contract: files, interfaces, test cases, invariants. `packages` are the Go packages the unit may touch. |
| `branch` | The run branch all lanes merge into. It exists and is checked out in the session's tree. |
| `head` | The commit of `branch` every lane starts from. |
| `gate` | The check command for the merged tree, for example `make test-offline PKG=…`. |
| `fork` | Optional absolute path of the bsc-geth checkout: the units are fork work. `branch` is then the branch checked out there, and `gate` defaults to `make audit-ext`. |
| `tiers` | Optional per-stage model override (`lane`, `integrate`, `gate`, `review`, `fix`). A tier above opus, by name, is refused. `review: "session"` runs the review seat at the session's tier, and is the only stage that accepts it. |

**Stages:**

1. **Lane**, one per unit, concurrent, each in its own worktree, `golang-implementer` at
   opus. The harness creates the worktree at `<project>/.claude/worktrees/wf_<run>-<n>` on a
   branch it names `worktree-wf_<run>-<n>`, cut from the session's HEAD (measured, under
   `worktree.baseRef: "head"`). The lane reports its start SHA, implements the brief, runs
   package-scoped gates there through `bk-gate`, and commits on that branch. It returns
   `{branch, start, sha, paths, gates:[{name, rc, line}], summary, handback?}`. The script
   drops a lane whose `start` is not `head` and reports it under `stalled`. A lane that hits
   a question the brief does not answer stops at green and returns `handback`; a lane that
   returns a red gate is treated as a hand-back. Neither is merged.
2. **Integrate**, one agent, sonnet. Merges each lane branch into `branch` in unit order
   (the lane branches are visible from the session's tree — measured). A lane that conflicts
   is not resolved: it is left out and reported. It then removes the worktree and deletes the
   branch of every merged lane; a changed worktree is never removed by the harness
   (measured). Returns `{merged[], conflicted[], head, unclaimed[]}`; `unclaimed` is every
   worktree under `.claude/worktrees/` that no returned lane names, which is what a lane that
   died left behind.
3. **Gate**, one agent, haiku. Runs `bk-gate run -- <gate>` on the merged tree and returns
   the verdict line verbatim with `rc`. The script decides green from `rc == 0`, never from
   the agent's reading.
4. **Review**, one `code-reviewer` seat, opus. Reads `head..HEAD` whole and returns findings
   with severity. Skipped when the gate is red.
5. **Fix**, one implementer dispatch, opus, for blocker and major findings together; then the
   gate again. One round. What remains is returned, not looped on.

**Output:** `{merged, conflicted, handbacks, stalled, gate, findings:{fixed, open}, owed, head}`.
`owed.parity` lists units that touched `internal/{replay,trigger,strategy,state}`: the caller
runs `make replay-parity` once. `owed.read` lists units that touched the record spine, the
hot path or the money path: the main loop reads those diffs itself before landing.

**Invariants:**

- Nothing is pushed and no PR is opened. Landing is the main loop's decision.
- A unit whose `packages` intersect the hot-path set gets `hot-path-determinism` in its
  load line. `go` is always loaded.
- Two units with a package in common are rejected before any lane starts.
- With `fork`, lanes run one at a time in the fork checkout, each committing on `branch`,
  which the caller cut from `mrinal/dev`: harness worktrees belong to the session's
  repository, not the fork. Each lane starts where the last one ended, there is no Integrate
  stage, and the run stops at the first lane that dies or hands back, because what it left is
  the next lane's tree. Stage 4's API rule becomes the `Ext` convention and the gate is
  `make audit-ext`.
- The script's own decisions are tested without a session: `tests/test_implement.py` answers
  its agents from a scenario. What an agent does with a prompt is the live run.
- A stage that dies is reported with what it left behind (`stalled`), never as a clean result.

## 8. The working model

The main loop does the intelligent work and nothing repetitive:

1. **Explore and plan** in the session, at the session tier. The plan is the unit list.
2. **Persist work as issues.** A pb issue body carries the units still to do. No plan file,
   spec file, ledger or resume file is tracked in either repo. Milestone state stays where pb
   already keeps it, `docs/project-context.md`.
3. **Run `/blockchain-kit:implement`** with the units. The run is in the background.
4. **Adjudicate the result**: hand-backs, conflicts, open findings, the owed reads and the
   parity gate.
5. **Land** with `dev-setup/ci/land`.

Context is the harness's own compaction. There is no rotation, checkpoint or resume protocol;
their purpose was to survive the context that hand orchestration consumed.

### 8.1 Ceremony scales with the diff

A one-line prose change went through a separate docs branch, CI, an ADR question and edits to
several mirrors of the same fact. That stops (decided). What a change owes is read off its
class, and the class is read off the diff:

| Class | The diff | Branch and PR | Gate | Review | Record |
|---|---|---|---|---|---|
| Prose | docs, comments, `CLAUDE.md` only | any branch; rides with the code change it belongs to when there is one | none: the selector classes it `none` and `land` posts `ci` without a run | none | none |
| Tooling | `dev-setup/`, `scripts/`, Makefile, CI workflow, root `tools/` | one branch | the lanes the selector names | none | none |
| Product Go | `cmd/`, `internal/` | one branch | the lanes the selector names | one seat at merge (the workflow's, or one `code-reviewer` dispatch) | none |
| Guarded Go | record spine, hot path, money path | one branch | the same, plus `make replay-parity` when owed | the same, plus the main loop reads the diff | an ADR only when an invariant, a stored-data contract or a boundary changes |

Rules that follow:

- **One branch per change, whatever it touches.** Code, its docs and its tooling land
  together. No branch is cut per file category.
- **An ADR records a decision about the product**, in pb `docs/decisions/`. A prose edit, a
  tooling change and any change to the kit never get one.
- **A fact has one home, so a change has one edit.** The mirrors go with the layer: roster
  tables, index files, the skill manifest, tracking rows, the lockstep files and the lints
  that held them in agreement.
- **The selector is the only judge of what CI runs.** A lane runs when the diff touches a
  file the lane reads. A prose diff selecting any lane is a selector defect to fix in pb.
  The prose row above is the target, not today's behaviour (measured at `01f5af59`): only the
  ceremony-free roots (`docs/decisions/`, `docs/reports/`, `docs/reviews/`, `docs/design/`,
  `dev-setup/decisions/`) select nothing; any other `docs/*.md` selects `python-floor-check
  boundary-lint citation-lint layering-lint shelltest` and four selector harnesses, and
  `CLAUDE.md` or `README.md` the first four lanes. The migration plan's C6 closes the gap.
- **Nothing is gated twice.** There is no local composite before the GitHub run and no
  per-slice gate before the merge gate.

## 9. Harness facts this design leans on

**Measured** on Claude Code 2.1.286 by the phase-0 probes (observed strings: the migration
plan, §Phase 0 results) unless marked **docs**.

- A plugin ships skills, agents, commands, hooks, MCP servers, output styles, workflows and
  `bin/`. It ships no rules. Its `settings.json` honours only `agent` and
  `subagentStatusLine`, so `env` and `permissions` stay in the project's settings. (docs)
- With `extraKnownMarketplaces` and `enabledPlugins` committed, an **interactive** session
  registers the marketplace and caches the plugin after folder trust, with no prompt and no
  install record; it does so in the background, about five seconds in, so that first
  session's SessionStart hook is missed. That a second interactive start with no install then
  has the kit from its first moment is inferred from the cache being in place, not measured. A
  **headless** run loads nothing until `claude plugin install blockchain-kit@blockchain-kit
  --scope project` has run once in that clone.
- `claude plugin uninstall --scope project` and `claude plugin marketplace remove` empty
  `enabledPlugins` and `extraKnownMarketplaces` in the clone's tracked `settings.json`.
- A private marketplace is fetched with the user's git credentials. (docs — the probes used
  a local `file://` git source)
- Plugin agents are named `blockchain-kit:<name>`: that string is the Agent tool's
  `subagent_type` and the hook payload's `agent_type`. A plugin workflow is addressed as
  `blockchain-kit:<name>`; the bare name is not found.
- Plugin hooks run for subagents, for workflow agents and for agents in a worktree; the
  payload `cwd` is the worktree. The default workflow agent's `agent_type` is
  `workflow-subagent`. A plugin hook receives `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT` and
  `CLAUDE_PLUGIN_DATA`.
- `agentType`, `model` and the agent's `skills:` preload are honoured inside a workflow.
- `worktree.baseRef` decides where an isolated agent starts: `fresh` (the default) is
  `origin/<default-branch>`, `head` is the session's HEAD.
- `force-for-plugin: true` applies the kit's output style, headless and interactive, over a
  user-level `outputStyle`.
- Without `version` in `plugin.json`, the commit SHA is the version.

## 10. The metric

`bk-mainloop-share` over pb sessions after the cut. Baseline: orchestration subtotal 40% of
main-loop turns and 53% of output tokens. Target: under 15% of turns. A subtotal that does not
fall says the workflow is not carrying the load, whatever else improved.

## 11. Costs accepted

- A pb commit no longer pins its steering. The kit commit is the version on each machine.
- Each machine needs git access to the private kit repository.
- The hot-path rule no longer loads on a matching file read. It loads by routing and by the
  workflow's `packages` rule, and `owed.read` puts those diffs in front of the main loop.
- Retired guards leave gaps that were closed by mechanism and are now closed by structure
  (worktrees, the script's fixed tiers) or not at all. §6's return rule applies. The three
  that matter most:
  - Lanes commit, and `agent_write_guard` is gone. Only the lane's instructions stop it from
    a `git push` or a `reset --hard`. Branch protection still holds `main`.
  - `dispatch_guard`'s typed-dispatch allowlist is gone. A dispatch's tier is what the
    workflow script and the agent file say; a hand dispatch from the main loop is unchecked.
  - Nothing denies a commit on the fork's trunk branches from a pb session except the
    fork's own `.githooks/`, where they are armed.

## 12. Defaults taken, the operator's to reverse

| Choice | Default |
|---|---|
| Hooks, tools, agents and commands outside §5 | retired, not moved: 26 of 31 hooks, 11 of 18 agents, all but one of the tools, all nine commands. Reversed per item by naming it. |
| Reviewer tier | opus; `tiers.review` can name the session tier for one run |
| `golang-implementer-lite` | deleted |
| The steering ADR corpus | left at the pb tag, not copied here |
| `lockstep_check.py`, `adr.py`, `sweep.py` | retired, not moved to `dev-setup/` |
| Install scope | project, through pb's committed `settings.json`, plus one `claude plugin install … --scope project` per clone so headless runs load it |
