# blockchain-kit as the steering home — design

Date 2026-10-01. Sources read: prediction-bot (pb) `01f5af59`, blockchain-kit `6796a58`,
bsc-geth `mrinal/dev` in `../bsc`. Evidence class is named per claim: **measured** (a command
run on those trees), **docs** (Claude Code docs, read 2026-10-01, not yet observed live) or
**decided** (the operator's ruling in the 2026-10-01 session, or a later ruling where its date
is given).

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
- **Fork changes are mostly bot changes, and the fork is developed three ways** (decided,
  2026-10-14). bsc-geth is pinned by pb as its go-ethereum; most fork work needs bot work.
  (S1) A session rooted in a bsc-geth clone does node-only work and lands by a push to
  `mrinal/dev`, with no CI and no `land`. (S2) A pb session edits the clone `BSC_FORK_PATH`
  names. (S3) A pb change that needs a fork change is S2 twice in one pb session: the fork
  run and its push, the pin move, then the pb run; not a third mechanism, and no second
  session. One clone per open session: a pb session's `BSC_FORK_PATH` never names a clone
  another session has open. `mrinal/master` is not touched: everything lands on `mrinal/dev`,
  which pb pins (decided, 2026-10-14). This replaces the 2026-10-01 "one session rooted in
  pb develops both".
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
  `references/features.md` and `upstream-rebase`'s `references/landmines.md` were copies; they
  are pointers to bsc-geth's feature inventory and rebase landmines since 2026-10-14. The kit
  carries one fork docs path, the fork's index `docs/fork/README.md` (kit #31). The pb domain skills keep only what is not already in pb `docs/`.
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
| `CLAUDE.md` | Project facts only: what the project is, the commands table, architecture at a glance, the non-negotiable invariants, the environment rule, the standard of evidence, the operator authorizations (merge without asking, privileged prod commands, where to ask), the map of docs. No line cap (operator, 2026-10-03): a passage stays if a session needs it on every turn, and goes if it is redundant, verbose commentary, history, or belongs elsewhere. No routing, tiers, hooks, rotation or pipeline text. One line names blockchain-kit as the steering home. |
| `.claude/settings.json` | `extraKnownMarketplaces` (the kit's git repo, as `{"source":"github","repo":"mrinaldhillon/blockchain-kit"}`), `enabledPlugins` (the kit on; nothing else listed), `worktree.baseRef: "head"` (kept for a session without the kit: the default `fresh` starts a lane at `origin/main`, measured; with the kit, `worktree-create` branches from HEAD itself), `env` (`GOPRIVATE`, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, and `BASH_MAX_TIMEOUT_MS=1800000`, so one foreground `land` call outlasts the longest CI run), `enabledMcpjsonServers`, and a `permissions.allow` list trimmed to what remains. No `hooks`, `statusLine`, `outputStyle` or `skillOverrides`. Keys in the order the plugin CLI writes them — `$schema`, `env`, `enabledMcpjsonServers`, `worktree`, `enabledPlugins`, `extraKnownMarketplaces` as observed, with the plugin keys last — so a per-clone install leaves no diff (measured: `plugin install --scope project` rewrites the file). |
| `.mcp.json` | The pyright server loses its `-p .claude/pyrightconfig.json` argument: with the overlay gone the server exits on it (measured). Otherwise unchanged. The `gopls` and `pyright` servers start the repo's pinned binaries under `dev-setup/`, and the key `gopls` keeps the tool names `mcp__gopls__*` that the kit's agents are granted. |
| `.gitignore` | Gains `.claude/worktrees/`: the harness's own location for a lane worktree, and the rule that ignored it before the cut was `.claude/.gitignore`, which the cut deletes (measured). Since kit #21 the kit's `worktree-create` hook puts every worktree beside the clone instead; the rule stays for a session without the kit. |
| `docs/decisions/` | One new engineering ADR: this repo carries no steering layer; its home is blockchain-kit. |
| `dev-setup/` | Gains the land script (§4.3). |

Everything else under `.claude/` is deleted, with `.github/workflows/steering.yml`.

### 4.2 bsc-geth

bsc-geth keeps pb's shape (decided, 2026-10-09; confirmed 2026-10-14). This supersedes the
2026-10-01 ruling that bsc-geth keeps nothing: a session may be rooted in a bsc-geth clone
(§2), and it gets the same kit steering as pb.

| File | Content |
|---|---|
| `CLAUDE.md` | Project facts only, cut by kind as pb's was. The fork's feature inventory and the next rebase's landmines move to their own documents under `docs/fork/` (its index, `docs/fork/README.md`, lists them), and the on-host `cmd/campaign` command line to `cmd/campaign/README.md`. |
| `.claude/settings.json` | The kit enabled at project scope, as pb's, with `worktree.baseRef: "head"`. Nothing else is tracked under `.claude/`. |
| `.mcp.json` | Kept; names `gopls`. |

`.githooks/` (armed by `make dev-setup`; `reference-transaction` holds `master` and
`mrinal/master`), `deploy/`, `build/auditext`, `make audit-ext` and `docs/` stay; they are
the fork's product and its gates. `unit_run.py`, the capped-unit runner for heavy work on the
prod host, moves to `build/`. The steering-only commits are dropped from the patch stack at
the next upstream rebase. That is a rewrite of a pushed branch and runs only on the
operator's explicit instruction.

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
| `working-here` (new) | The process, in about 120 lines for both repositories: explore, plan, cut units, run `implement`, adjudicate, land. Replaces `orchestration`, `git-workflow`, `milestone-workflow`, `dev-workflow`, `plan-authoring` and the superpowers pipeline. |
| `go` | Go authoring bindings. Unchanged. |
| `fork-lookup`, `fork-node-api`, `contract-abi`, `binance-streams`, `record-format`, `replay-parity`, `environment-detection`, `hot-path-determinism` | Routers to pb `docs/`. |
| `fork-development`, `fork-ext-convention`, `fork-deploy`, `upstream-rebase` | Routers to bsc-geth `docs/`, for both roots (§2), plus pb's pin-and-checkout loop. |
| `campaign` (new, 2026-10-14) | Router to the fork's measurement campaign: `cmd/campaign/README.md`, `deploy/production/README.md` §Campaign, `bsc-campaign.timer`. |

### 5.2 Agents

| Agent | Tier | Change from `6796a58` |
|---|---|---|
| `golang-implementer` | opus | Drops `LSP` from `tools:` (it is never in the live roster — measured). Its "never `git commit`; a brief cannot lift that" rule is replaced by the lane contract (§7): at `6796a58` both probe lanes refused to commit against the brief (measured). Absorbs `golang-implementer-lite`, which is deleted: implementation runs at opus (decided). |
| `code-reviewer` (new) | opus | One seat over the merged diff of a run. Carries pb's reserved angles: determinism and parity, the record spine, import boundaries, hot-path blocking. Read, Bash and the read-only gopls tools (callers and implementations; pb's reviewer had them before the cut). A dispatch outside a run is briefed with the PR body and the issue, ADR or plan it names. |
| `review-seat` (new) | opus; fable for the review workflow's intent and conformance seats | One read-only seat of the `review` workflow: the intent seat, a finder or a checker, as the script's brief says. Read, Bash, Skill and the read-only gopls tools. |
| `determinism-auditor`, `parity-auditor`, `fork-indexer`, `fixture-capturer`, `infra-profiler` | opus | Unchanged. An agent without `ToolSearch` gets its granted `mcp__gopls__*` tools undeferred and callable (measured on `parity-auditor`), so the auditors need no new grant. |

pb's other eleven agents are not carried (§6).

### 5.3 Hooks

| Hook | Event | Contract |
|---|---|---|
| `blockchain-kit-context` | SessionStart | Routing table; pin and checkout lines; the kit's own installed SHA (a clone left behind runs an old kit silently — §5.5); one environment line (prod host or dev, from pb's `env_banner`); one line when `core.hooksPath` is unset or its `reference-transaction` hook is missing or not executable; one line, with a count and the first three paths, when the project tracks anything under `.claude/` other than `settings.json` (one line per file would be 407 lines in pb before the cut, and the hook's context spills to a file above 10,000 characters). Prints in a fork client and in the fork itself (a `go.mod` whose module is `github.com/ethereum/go-ethereum`); there it prints the routing table, the host, git-guard (fix: `make dev-setup`), stray and kit lines, and no pin line. Prints nothing elsewhere. Never fails a session. |
| `guard-secrets` | PreToolUse, file tools | The node material it guards today, plus pb `guard_secrets.py`'s generic patterns (dotenv family, `*.pem`, `*.key`, `*.p12`, `secrets/`). One hook. Fails closed. |
| `guard-prod-run` | PreToolUse, Bash | The binary class of pb `run_guard.py`: on the prod host, deny a bare replay, bot or collector run that bypasses `scripts/replay-run.sh`. Fails closed. Protects the recorder log. The command is classified with `shlex` at command position, not with pb's 787-line `cmdclass`; the residuals are in the hook's header. `run_guard.py`'s second class (heavy local work through `unit_run.py`) is not carried for pb: it is a rule about pb's own runner, and if it is wanted it belongs in the `make` targets it names. For the fork tree it is carried (decided, 2026-10-14), since a bsc-rooted session now runs heavy work beside the production geth: on the prod host, deny an uncapped `make test\|lint\|geth-prod`, a whole-module `go test ./...`, `golangci-lint`, or `go run build/ci.go test\|lint` unless wrapped by `build/unit_run.py`, `systemd-run` or `verifyconstrained`, keyed on the targeted tree (the cwd, or `-C`). |
| `land-shape` | PreToolUse, Bash | A call that runs pb's `dev-setup/ci/land` runs the one cheap way: a `timeout` wrapper in front of it is removed, it runs in the foreground, and its tool timeout is 1800000 ms (working-here step 6). Rewrites through `updatedInput` and sets no permission decision. Fails open. |
| `reader-reminder` | UserPromptSubmit | In a fork client and in the fork itself, adds three lines beside each operator message: the output style's two additions to Claude Code's own writing rules, which already ban made-up names and cap file names per paragraph: a repo identifier (a decision record, a rule, an issue, a section) said in words, never as a bare number; the places to read more listed at the end of the reply as full `path:line`s. The rule alone sat at the top of every request of a pb session that still wrote 327 bare labels in 68 replies (2026-10-23). Prints nothing elsewhere; fails open. |
| `workflow-tiers` | PreToolUse, Workflow | A workflow script written in the session (`script`, or the file at `scriptPath`; a saved workflow called by `name` carries its own tiers and is not inspected) is denied when an `agent()` call leaves `model` unset, naming the line and the call, so no stage inherits the session's tier by omission (working-here, Tiers and dispatch). The script is scanned as text with its literals and comments blanked, not parsed; an options object the text cannot judge (a spread, a call, an expression) is allowed. Fails open: it guards spend, not data. |
| `implement-args` | PreToolUse, Workflow | A call of the `blockchain-kit:implement` workflow gets `args.project` (the project root) and `args.module` (its `go.mod` module) filled in through `updatedInput` when the caller left them out, and a `fork` that names the project by another spelling rewritten to the project path, so the script's mode (§7) follows the tree (Claude Code applies `updatedInput` to a Workflow call: measured 2026-10-15). Reads the tree, never the session. Fails closed only in a fork root, where a run the script could not place would brief bot-shaped lanes on the production host. |
| `worktree-create` | WorktreeCreate | Replaces the harness's `git worktree add` for every worktree it isolates work in (a workflow lane, an agent with `isolation: "worktree"`, `claude -w`, EnterWorktree, a background session): the worktree goes to `<parent of the main clone>/.<clone dir>.worktrees/<name>` on branch `worktree-<name>`, cut from the HEAD of the tree the session is in, and the hook prints the path. Keyed on the main clone (git's common dir), so a lane spawned from a `-w` session lands beside the clone too. Why (operator, 2026-10-15): the harness's `<clone>/.claude/worktrees/` puts full checkouts inside the session's own tree, where every walker that ignores `.gitignore` (bsc's `make fmt` runs gofmt over `find .`), gopls and the ignore rules of both repos have to allow for them, and a bsc lane is 13,500 files inside the production host's tree. The harness's `worktree.baseRef` and `.worktreeinclude` do not apply to a hook-made worktree; neither repo uses the latter, and a bot lane compiling the pin, not `go.work`, is by design. Refuses (exit 2, the harness then fails the creation): a name that is not a slug, a target that exists, a parent inside a git repository (Claude Code refuses such a worktree itself), a `.<clone>.worktrees/` holding anything that is not a worktree of the clone. `BLOCKCHAIN_KIT_WORKTREES=0` uses the harness's location with the same branch and HEAD rules. The CLI has no setting for this: `worktree.location` is read by the desktop app for SSH sessions only, and the path is a hardcoded join in the binary (2.1.300). |
| `worktree-remove` | WorktreeRemove | Removes a worktree `worktree-create` made when the harness retires it (`claude -w` exit, EnterWorktree's exit, a deleted background session; the harness does not call it for a workflow lane or an isolated agent, which it keeps, so §7's Integrate removes the merged lanes itself). `git worktree remove` without `--force`, so uncommitted work is refused and kept (the harness's own check sees none in a hook-made worktree), then `git branch -d`; an unmerged branch is kept and named on stderr. Refuses anything that is not a linked worktree of the clone in one of the kit's two locations. |
| `gofmt-on-edit` | PostToolUse | Scope gains a linked worktree of the project (a lane beside the clone shares its git common dir). Otherwise unchanged. |

Each hook has a kill switch in the `BLOCKCHAIN_KIT_*` family and reads project state through
`CLAUDE_PROJECT_DIR`; anything it persists goes under `CLAUDE_PLUGIN_DATA` (docs).

### 5.4 Commands on `PATH`

| Command | Contract |
|---|---|
| `bsc-fork` | Unchanged. |
| `bk-gate [-C DIR] <name> -- <command>` | Run one command, in the caller's directory or in `DIR`; print exactly one line `gate: <name> rc=<n> t=<s>s out=<path>` and, on red, the last ten lines of its output. Exit with the command's code. On the production host, run it inside its repository's cap: pb `dev-setup/ci/ci-cap.sh`, bsc-geth `cmd/verifyconstrained` (kit #7). From pb `gate.py`. |
| `bk-mainloop-share <transcript-dir> <days>` | The classifier behind §2's table. The kit's one metric (§10). |
| `blockchain-kit-setup`, `-update` | Accept `--scope user|project`; `installed_field` matches a project-scope install by `projectPath`. |

### 5.5 Other components

- `workflows/implement.js`, rewritten to §7; `commands/implement.md` is the user-invoked
  entry, because the Workflow tool runs only on an explicit request.
- `commands/init.md`: gains the check that the project's `.claude/` holds only `settings.json`,
  and, in a bsc-geth root, the git-guard check (`core.hooksPath`, `make dev-setup`) in place
  of the pin and checkout steps.
- `output-styles/distinguished-engineer.md` with `force-for-plugin: true` (docs), so the
  project sets no `outputStyle`.
- `plugin.json` drops `version`, so the commit SHA is the version (measured: the install's
  version is the 12-character SHA). A kit commit does not reach an installed copy on its own:
  neither a new session nor `"autoUpdate": true` on the marketplace entry moved it within the
  windows measured. `blockchain-kit-update` runs `claude plugin marketplace update` then
  `claude plugin update blockchain-kit@blockchain-kit --scope project`, and the next session
  has the commit (measured). The marketplace entry keeps the relative source `./`.
- No kit CI and no required check: a change to steering carries no gate (operator,
  2026-10-09). `tests/run`, `claude plugin validate .`, shellcheck and ruff are local tools,
  run by hand when a change touches what they cover.

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
except the output style (§5.5). The statusline is the user's setting, which points at the
kit's `bin/bk-statusline` (README §Status line), since a plugin cannot set `statusLine`.

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
| `fork` | Optional absolute path of the bsc-geth checkout when the units are fork work from pb (S2): the remote mode below. `branch` is then the branch checked out there. |
| `project`, `module` | The absolute project root and the `module` line of its `go.mod`, passed on every run (`implement-args` fills them): the script cannot read the filesystem. With `module` `github.com/ethereum/go-ethereum` and `fork` unset or equal to `project`, the run is rooted in the fork itself (S1): the in-place mode below. |
| `tiers` | Optional per-stage model override (`lane`, `integrate`, `gate`, `review`, `fix`). A tier above opus, by name, is refused. `review: "session"` runs the review seat at the session's tier, and is the only stage that accepts it. |

**Stages:**

1. **Lane**, one per unit, concurrent, each in its own worktree, `golang-implementer` at
   opus. The kit's `worktree-create` hook (§5.3) makes the worktree at
   `<parent>/.<clone>.worktrees/wf_<run>-<n>` on the branch `worktree-wf_<run>-<n>`, cut from
   the session tree's HEAD (before kit #21 the harness made it at `<project>/.claude/worktrees/`
   under `worktree.baseRef: "head"`, measured). The lane reports its start SHA, implements the brief, runs
   package-scoped gates there through `bk-gate`, and commits on that branch. It returns
   `{branch, start, sha, paths, gates:[{name, rc, line}], summary, handback?}`. The script
   drops a lane whose `start` is not `head` and reports it under `stalled`. A lane that hits
   a question the brief does not answer stops at green and returns `handback`; a lane that
   returns a red gate is treated as a hand-back. Neither is merged.
2. **Integrate**, one agent, sonnet. Merges each lane branch into `branch` in unit order
   (the lane branches are visible from the session's tree — measured). A lane that conflicts
   is not resolved: it is left out and reported. It then removes the worktree and deletes the
   branch of every merged lane; the harness keeps a hook-made worktree when its agent ends,
   and before the hook it kept a changed one (measured). Returns `{merged[], conflicted[],
   head, unclaimed[]}`; `unclaimed` is every worktree on a `worktree-wf_*` branch that no
   returned lane names, wherever it is on disk, which is what a lane that died left behind.
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
- Fork work, in either fork mode: `fork-ext-convention` rides on every lane, the gate
  defaults to `make audit-ext`, stage 4's API rule becomes the `Ext` convention and the
  rebase landmines, and nothing is owed (`parity` and `read` are pb's).
- **In place** (S1: `module` is the fork's and `fork` is unset or the project): stages 1 to 5
  as in pb, the worktrees beside the fork clone (`worktree-create`). The lane gates are
  the unit's exact packages, written out (`go build|vet|test -count=1 ./<pkg>`, then
  `make audit-ext`), never `./...`, `make test` or `make lint`: the tree is the production
  host's, and `guard-prod-run` refuses the whole-module forms. The run branch is squashed to
  its feature commits before the push to `mrinal/dev` (the fork's commit convention); the
  Integrate merges are not pushed as they stand.
- **Remote** (S2: `fork` names another tree): lanes run one at a time in the fork checkout,
  each committing on `branch`, which the caller cut from `mrinal/dev`: harness worktrees
  belong to the session's repository, not the fork. Each lane starts where the last one
  ended, there is no Integrate stage, and the run stops at the first lane that dies or hands
  back, because what it left is the next lane's tree.
- The script's own decisions are tested without a session: `tests/test_implement.py` answers
  its agents from a scenario. What an agent does with a prompt is the live run.
- A stage that dies is reported with what it left behind (`stalled`), never as a clean result.

### 7.1 The `review` workflow

`/blockchain-kit:review [<pr#>|<base>]` reviews one diff against what it was written to do
(operator, 2026-10-23: a reviewer that works out intent from the code it reads checks the
code against itself; pb #570 found most of M8's defects broke no rule the single seat
checked). It runs only when the user types it, is read-only, and is separate from the
`implement` workflow's Review stage until its recall is measured against `/code-review
ultra` and the single seat on the same pull requests (kit #7).

| Stage | Seats | Does |
|---|---|---|
| Intent | one `review-seat`, fable | The contract as numbered items from the PR body, the issues and ADRs it names, or the brief; a source's "verified" is a claim. Then whether that logic is sound for the domain, through the kit's skills. Then the diff size |
| Find | the conformance finder at fable, and `ceil(lines / 150)` more kept within 2..5 at opus | Conformance both ways (each item to code, each changed path to an item) is always its own seat. Five more angles, merged when there are fewer finders: line by line and what was removed, callers through gopls and Go's pitfalls, the domain (pb's four reserved angles or the fork's Ext convention and landmines), tests by reading, quality |
| Check | one per changed file with candidates, eight candidates at most each, `maxChecks` (40) candidates in all, opus | A seat that raised none of them reads the file once and decides each candidate: CONFIRMED, PLAUSIBLE or REFUTED, refuted only when the code shows it. It marks a true duplicate; two defects on one line stay two |

The run pauses after Intent when the contract is in doubt: no source stated it, or the
intent seat found a blocker in its logic (operator, 2026-10-23). It returns the contract and
why, and no finder has spent anything; the user goes on (`proceed: true`, resumed from the
paused run so the intent seat comes from cache) or corrects the contract and runs again.

Fable runs where a wrong judgment misdirects everything after it (operator, 2026-10-23): the
contract and its soundness, and the mapping of code to intent; working-here's rule allows a
tier above opus by name for such a stage. The pattern angles and the checks run at opus; a
checker at opus because a refutal drops the finding. `tiers` lowers any of them for one run.

The return carries the contract, the findings that stand with their verdicts, the refuted,
the duplicates the checkers merged, the unchecked, the coverage per angle and the seat
count. Nothing is built, run or posted.
Its decisions are tested in `tests/test_review.py`; its token cost is unmeasured until the
first live run.

## 8. The working model

The main loop does the intelligent work and nothing repetitive:

1. **Explore and plan** in the session, at the session tier. The plan is the unit list.
2. **Persist work as issues.** An issue body, in the repo the work is in, carries the units
   still to do. No plan file, spec file, ledger or resume file is tracked in either repo.
   Milestone state stays where each repo already keeps it: pb `docs/project-context.md`,
   bsc-geth's project context (listed in its docs index, `docs/fork/README.md`).
3. **Run `/blockchain-kit:implement`** with the units. The run is in the background. In a
   bsc-geth root it runs in place (§7).
4. **Adjudicate the result**: hand-backs, conflicts, open findings, the owed reads and the
   parity gate.
5. **Land**: in pb with `dev-setup/ci/land`; in bsc-geth, the gate green, by
   `git push origin mrinal/dev` behind `.githooks/pre-push`, with no CI and no confirmation.
   `mrinal/master` is not touched (decided, 2026-10-14).

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

bsc-geth adds two classes (decided, 2026-10-14; `working-here` carries them): **Fork Go**
(`*_ext.go` and upstream files under the wiring rule; package-scoped gates in a capped unit on
the prod host, then `make audit-ext`, and `make lint` before a push; one review seat with the
`Ext` and landmine angles) and **Host** (`deploy/production/`; `bash
deploy/production/host/tests/run.sh`, plus `check-config-ext.sh` and `host/geth-preflight.sh`
before a `config.toml` or `ExecStart` change; the install itself is the operator's).

Rules that follow:

- **One branch per change, whatever it touches.** Code, its docs and its tooling land
  together. No branch is cut per file category.
- **An ADR records a decision about the product**, in pb `docs/decisions/` or the ADR
  directory bsc-geth's docs index (`docs/fork/README.md`) names. A prose edit, a
  tooling change and any change to the kit never get one.
- **A fact has one home, so a change has one edit.** The mirrors go with the layer: roster
  tables, index files, the skill manifest, tracking rows, the lockstep files and the lints
  that held them in agreement.
- **The selector is the only judge of what CI runs.** A prose-only PR gets no CI run
  (operator, 2026-10-04): the selector gives `docs/**/*.md` and root `*.md` no lane, the
  classifier calls such a diff `none`, and `land` posts `ci` without a run, as it does for
  the record roots (`docs/decisions/`, `docs/reports/`, `docs/reviews/`, `docs/design/`,
  `dev-setup/decisions/`). Three doc paths are lane inputs, not prose, and keep their
  lanes: `docs/fork-knowledge/` and `docs/data-deprecations/` (Go tests read them) and
  `docs/architecture.md` (`boundary-lint` reads its package table). The cost is accepted:
  `citation-lint` and `layering-lint` do read prose, so a hit a prose-only PR introduces
  shows at the next non-prose PR or the weekly all-lanes run, not at its own merge.
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
- That interactive reconcile writes `known_marketplaces.json` but no `installed_plugins.json`
  row: `claude plugin list` shows nothing until the per-clone install runs.
- `advisor` is in every kit agent's and workflow lane's tool roster, though no frontmatter
  grants it.
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
  `origin/<default-branch>`, `head` is the session's HEAD. Not with a WorktreeCreate hook,
  which does the `git worktree add` itself (docs; the kit's branches from HEAD).
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
  (worktrees, the script's fixed tiers) or not at all. §6's return rule applies. The four
  that matter most:
  - Lanes commit, and `agent_write_guard` is gone. Only the lane's instructions stop it from
    a `git push` or a `reset --hard`. Branch protection still holds `main`.
  - `dispatch_guard`'s typed-dispatch allowlist is gone. A dispatch's tier is what the
    workflow script and the agent file say; a hand dispatch from the main loop is unchecked.
  - Nothing denies a commit on the fork's trunk branches, from a pb session or a bsc-geth
    session, except the fork's own `.githooks/`, where they are armed (`make dev-setup`; the
    session-start hook reports an unarmed clone). A bsc-geth push lands with no CI and no
    branch protection: the class's local gate and `.githooks/pre-push` are all that hold it.
  - `dirty_tree_guard` and `dispatch_guard`'s tree lease are gone. A workflow lane gets its
    own worktree and the Integrate stage refuses a dirty tree, but a hand dispatch into the
    session's tree is held only by `working-here`'s "commit before you dispatch": nothing
    stops one from sweeping uncommitted edits into its commit, or two from editing one tree
    at once. Whether pb's guards ever caught a real collision was not measured before the
    cut (their deny logs are in the clone's `.claude/state/`); the lease misfired once
    (pb #932, a phantom lease after a denied dispatch).

## 12. Defaults taken, the operator's to reverse

| Choice | Default |
|---|---|
| Hooks, tools, agents and commands outside §5 | retired, not moved: 26 of 31 hooks, 11 of 18 agents, all but one of the tools, all nine commands. Reversed per item by naming it. |
| Reviewer tier | opus; `tiers.review` can name the session tier for one run |
| `golang-implementer-lite` | deleted |
| The steering ADR corpus | left at the pb tag, not copied here |
| `lockstep_check.py`, `adr.py`, `sweep.py` | retired, not moved to `dev-setup/` |
| Install scope | project, through the committed `settings.json` of pb and of bsc-geth, plus one `claude plugin install … --scope project` per clone so headless runs load it |
