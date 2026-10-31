# blockchain-kit

The Claude Code steering for **prediction-bot** and the **bsc-geth fork** it consumes; a
session is rooted in either. The fork is developed in its own clone, from a prediction-bot
session through `BSC_FORK_PATH`, or, for a bot change that needs a fork change, both ways in
order within one prediction-bot session (fork, pin, bot). A Claude Code plugin plus terminal
commands. It has no other consumer, and it names their paths, make targets and branches freely.

Both repositories keep project facts (`CLAUDE.md`, `docs/`) and the minimum the harness needs
(`.claude/settings.json`). How a session routes, dispatches, tiers, guards and reports lives
here and nowhere else. The decision and its reasons: [`docs/design.md`](docs/design.md). The
move, phase by phase, with what was measured: [`docs/migration-plan.md`](docs/migration-plan.md).

## The working model

The main loop explores, plans and judges; it does not drive implement → gate → review → fix by
hand. `skills/working-here` is the whole process:

1. Plan in the session. The plan is a list of units, each a contract with its Go packages.
2. Open work persists as issues, never as plan, ledger or resume files.
3. `/blockchain-kit:implement` runs the units: one opus lane per unit in its own worktree, the
   lane branches merged into the run branch, the gate, one review seat, one fix round.
4. The session adjudicates what came back and lands with prediction-bot's `dev-setup/ci/land`
   or, in bsc-geth, pushes `mrinal/dev` (`mrinal/master` is not touched).

What a change owes is read off its diff: prose owes no gate and no review; product Go owes the
selected lanes and one review seat; the record spine, the hot path and the money path add a
read by the main loop and `make replay-parity` when owed.

## Layout

| Path | What |
|---|---|
| `skills/working-here` | the process and the change classes |
| `skills/using-blockchain-kit` | the routing table, given at session start |
| `skills/` (bot) | `go`, `fork-lookup`, `fork-node-api`, `contract-abi`, `binance-streams`, `record-format`, `replay-parity`, `hot-path-determinism`, `environment-detection`, `round-forensics` |
| `skills/` (fork) | `fork-development`, `fork-ext-convention`, `fork-deploy`, `campaign`, `upstream-rebase` |
| `agents/` | `golang-implementer`, `code-reviewer`, `review-seat`, `determinism-auditor`, `parity-auditor`, `fork-indexer`, `fixture-capturer`, `infra-profiler`. None runs above opus, except the review workflow's intent and conformance seats (fable, operator 2026-10-23) |
| `workflows/implement.js` | `blockchain-kit:implement`: Lane → Integrate → Gate → Review → Fix → Re-gate. Its header is the contract of its `args` and its return |
| `commands/implement.md` | `/blockchain-kit:implement`, the entry to the workflow: the user's command, or the session's on the user's approval of a plan's units |
| `workflows/review.js` | `blockchain-kit:review`: Intent → Find → Check. The contract and its soundness first (fable), then a conformance finder (fable) and two to five more by angle (opus), then one checker per changed file with a verdict per candidate (opus); pauses after Intent when the contract is in doubt; read-only. Its header is the contract of its `args` and its return |
| `commands/review.md` | `/blockchain-kit:review [<pr#>\|<base>]`, the user's entry to the review workflow |
| `commands/init.md` | `/blockchain-kit:init`, once per project; reports, changes nothing |
| `output-styles/` | `distinguished-engineer`, forced for the plugin: the project sets no `outputStyle` |
| `bin/bsc-fork` | `pin`, `show`, `search`, `list`, `check`, `path` |
| `bin/bk-gate` | `bk-gate [-C DIR] <name> -- <command>`: one verdict line, the last ten lines on red, the command's exit code. On the production host the command runs inside its repository's cap (pb `dev-setup/ci/ci-cap.sh`, bsc-geth `cmd/verifyconstrained`) |
| `bin/bk-mainloop-share` | what main-loop turns were spent on, by category: the kit's one metric |
| `bin/bk-statusline` | the status line: the session (model, context, rate limits, cache, cost) and the place (branch, PR, PROD, the fork pin and checkout, the kit's SHA) |
| `bin/blockchain-kit-context` | the session-start hook, in prediction-bot, in a bsc-geth clone and in a lead directory: routing table, pin and checkout lines (prediction-bot only), one line per tree (the lead directory only), the kit's SHA, the host, and what is out of place (git guard unarmed, steering files outside the kit) |
| `bin/blockchain-kit-setup`, `-update` | install and update, `--scope user\|project` |
| `bin/bk-team` | `init DIR CLONE...`, `start`, `status`, `stop`: a lead session over one worker session per clone; §Lead and workers |
| `hooks/guard-secrets` | denies the file tools node identity and account material and the generic secret patterns; fails closed |
| `hooks/guard-prod-run` | on the production host, denies a bare `replay`, `bot` or collector run that bypasses `scripts/replay-run.sh`, and, in the fork tree, heavy work (`make test\|lint\|geth-prod`, `go test ./...`, `golangci-lint`, `ci.go test\|lint`) not wrapped by `build/unit_run.py`, `systemd-run` or `verifyconstrained`; fails closed |
| `hooks/land-shape` | runs a `dev-setup/ci/land` call in the foreground at a 30-minute timeout, with no `timeout` wrapper; fails open |
| `hooks/reader-reminder` | in prediction-bot and the bsc-geth fork, adds the output style's two additions to Claude Code's writing rules (repo identifiers said in words; the `path:line`s listed at the end) beside each message the operator sends; fails open |
| `hooks/workflow-tiers` | refuses a workflow script written in the session whose `agent()` calls leave `model` unset, so no stage inherits the session's tier by omission; fails open |
| `hooks/implement-args` | fills `project` and `module` into an implement or review run's args from the tree, so the workflow picks its mode (the bot, the fork in place, a fork checkout) whatever the caller passed |
| `hooks/worktree-create` | makes every harness worktree (a workflow lane, `claude -w`, EnterWorktree) beside the clone at `<parent>/.<clone>.worktrees/<name>`, never inside it, on `worktree-<name>` from the session's HEAD; refuses a parent inside a repository or a target that exists |
| `hooks/worktree-remove` | removes a worktree the kit made when the harness retires it, uncommitted work refused and kept, then deletes its branch when merged |
| `hooks/gofmt-on-edit` | formats a Go file Claude writes, in the project, a worktree of it, or the fork checkout |
| `lib/` | `forkpin.py` (the pin, the module cache, the checkout, `go.work`, the index), `bkhost.py` (the production-host test), `blockchain-kit-homes.sh` (the config home) |
| `share/mcp-gopls.json` | the `gopls` entry for a repo's `.mcp.json` |
| `share/cloud-setup-bsc-geth.sh` | the setup script of the `bsc-geth` cloud environment at claude.ai/code, versioned; §Cloud sessions |
| `tests/run` | the hermetic suite: `bin/`, `lib/`, the hooks, and the workflow scripts against scripted agents |
| `.claude-plugin/` | plugin and single-plugin marketplace manifests. No `version`: the commit SHA is the version |

## Skill modes

Claude Code's `skillOverrides` setting does not reach plugin skills ("Plugin skills are not
affected by `skillOverrides`", Claude Code docs, Skills), so a `blockchain-kit:*` key there does
nothing. A kit skill's mode is its own frontmatter, changed in a kit commit and delivered by
`blockchain-kit-update`:

| Mode | Frontmatter |
|---|---|
| on | `description:` the full when-to-load text |
| name-only | `description:` one line naming what the skill covers. The routing table the session-start hook injects says when to load it; the full text is the body's **When to load** line |
| user-invocable-only | `disable-model-invocation: true`: hidden from the model, `/blockchain-kit:<name>` still runs. Never on a skill an agent preloads (`skills:` in `agents/`) or a workflow unit names: the flag blocks both |
| model-only | name-only plus `user-invocable: false`: off the `/` menu; the model and a subagent still load it by name |
| off | the skill deleted |

Every skill is name-only except `upstream-rebase`, which is user-invocable-only, and
`using-blockchain-kit`, which is model-only: the session-start hook already puts its body in the
session, so a `/` entry would only load it twice. A mode holds for every repository: each
project's install of one kit commit shares one cache directory.

## Enabling it in a project

prediction-bot and bsc-geth (from migration Phase 5 step 3) commit the enablement in
`.claude/settings.json`: `extraKnownMarketplaces` names this repository, `enabledPlugins` turns
the kit on, and `worktree.baseRef` is `"head"` (the kit's `worktree-create` hook branches a lane
from HEAD itself; the setting covers a session without the kit). Then, once per clone of either:

```sh
claude                                     # one interactive start: accept folder trust; the marketplace registers
~/.claude/plugins/marketplaces/blockchain-kit/bin/blockchain-kit-setup --scope project
                                           # records the install, so headless runs load the kit too
```

The first setup runs from the marketplace copy the interactive start registered (under
`$CLAUDE_CONFIG_DIR` when that is set). After it, `~/.local/share/blockchain-kit/kit` links
to the installed kit. Do not clone the kit there to bootstrap: setup refuses a directory
where its link goes.

- A headless run (`claude -p`) in a clone that skipped the second step loads no kit and says
  nothing. The session-start line `blockchain-kit: installed at <sha>` is the signal.
- A kit commit reaches a clone only through `blockchain-kit-update --scope project`, then a
  new session. Nothing propagates on its own.
- Never run `claude plugin uninstall` or `claude plugin marketplace remove` inside a clone:
  both empty the two plugin keys of its tracked `settings.json`.
- `claude --plugin-dir <a kit checkout>` loads a working tree for one session without
  installing.

For terminal use of the commands: `export PATH="$HOME/.local/share/blockchain-kit/kit/bin:$PATH"`.
Kill switches: `BLOCKCHAIN_KIT_CONTEXT=0`, `BLOCKCHAIN_KIT_GOFMT=0`,
`BLOCKCHAIN_KIT_GUARD_SECRETS=0`, `BLOCKCHAIN_KIT_GUARD_PROD_RUN=0`, `BLOCKCHAIN_KIT_LAND_SHAPE=0`,
`BLOCKCHAIN_KIT_WORKFLOW_TIERS=0`.

**The gopls MCP server is the repo's**, in its `.mcp.json`, never the plugin's: a server a
plugin ships is named for the plugin, and the agents are granted `mcp__gopls__<tool>`. The key
must be exactly `gopls`. In a bsc-geth root gopls answers for the fork natively; from
prediction-bot it answers for the fork checkout only while `go.work` is active.

## Lead and workers

One session to plan with, which executes nothing, and one working session per clone, briefed
over cross-session messages. The lead's directory is a plain directory, never a repository
(the `worktree-create` hook refuses a clone whose parent is inside one), holding a link to
each clone, a CLAUDE.md that states the lead's role and `.claude/settings.json` enabling the
kit; `bk-team init` writes all three, so this kit is their versioned home.

```sh
bk-team init ~/Developer/team ~/Developer/prediction-bot ~/Developer/bsc-geth
bk-team start ~/Developer/team       # a tmux window per clone: prediction-bot-worker, bsc-geth-worker; then the lead
```

- The session-start hook in the lead directory prints the routing table and one `Tree:` line
  per clone (the client's pin, the fork's branch), so the lead holds the kit's skills and both
  trees' state without executing anything.
- Workers are ordinary interactive sessions (`claude -n <clone>-worker --model opus
  --permission-mode bypassPermissions`, Remote Control off so each lists once). Not
  `claude --bg`: a background session refuses writes into its checkout until it enters a
  worktree, and its supervisor stops it after about an hour idle.
- The lead briefs a worker by SendMessage to its name and waits for the report; a brief asks
  for the report after the result lands, never alongside the action. The receiving session is
  told the message comes from another session working on the operator's behalf and acts on it
  within its own permissions.
- Needs, once: each clone trusted and the kit installed for it (above), and the user's
  `crossSessionInbound` set to `accept`. With `refuse` a brief is dropped silently; with no
  value it is held for approval when the two sessions' permission modes differ.
- In-process agent teams are not this: a teammate has no Workflow tool and gets no
  session-start context, so it cannot run the kit's workflows.

## Status line

A plugin cannot set `statusLine`: its `settings.json` honours only `agent` and
`subagentStatusLine`. So the user's settings point at the kit's script through the stable
link, and it moves with each `blockchain-kit-setup` or `-update`:

```json
"statusLine": {
  "type": "command",
  "command": "~/.local/share/blockchain-kit/kit/bin/bk-statusline",
  "refreshInterval": 10
}
```

It prints two lines:

```text
Opus 5.5·xhigh │ ctx ▓▓▓░░░░░░░ 34% │ 5h 74% ↻04:13 7d 41% │ 340k/1.0M │ cache 93% cold in 4m │ $12.35 │ 1h30m │ bkworking
prediction-bot main +1 ~2 │ PROD │ PR #903 approved │ pin 485bcb1c2c70 │ fork mrinal/dev +42 │ kit cef76f3
```

- **The session line:** the model and effort; the context fill, yellow from 50% and red from
  80%; the 5h and 7d rate-limit windows, with the reset time once a window passes 70%; tokens;
  the prompt cache, which turns yellow within ten minutes of going cold (a pause then
  re-caches); cost, duration and the session name.
- **The place line:** the repo (a link) and branch, with staged `+`, changed `~` and conflicted
  `!` counts, `↑`/`↓` against the upstream, and a rebase or merge in progress; then the
  worktree and the PR.
- **`PROD`:** shown when the geth IPC path is a socket. It is probed on every run, so it
  never goes stale the way the session-start Host line can.
- **In prediction-bot:** the pin, with `index STALE` when the index was built elsewhere; the
  fork checkout against the pin (`+N` past it, `~` when dirty); and `go.work: builds the
  CHECKOUT`. In a bsc-geth root there is no pin: the repo name and branch are the place.
- **`kit <sha>`:** the kit installed for this project, with `→<sha>` when the marketplace
  has moved past it, which means `blockchain-kit-update` has work to do.

When the terminal is narrow, the line drops duration and cost first, then tokens and the
cache, and keeps the model to the end. `refreshInterval` keeps the git and host segments current while the session is
idle. A run takes about 50 ms.

## Three trees

A session rooted in a bsc-geth clone has one tree, its own: no pin, no index (`bsc-fork`
exits 2), and nothing to export. It needs only that clone's git guard armed (`make
dev-setup`), and no other open session using the same clone. The rest of this section is
prediction-bot's.

| Tree | Where | What it is |
|---|---|---|
| the pin | the module cache | read-only. What `go.mod` names, what CI compiles, what the index describes |
| the checkout | `$BSC_FORK_PATH` | a clone of bsc-geth. The only tree that is edited |
| what the build compiles | | the pin, unless prediction-bot's `go.work` is active: then the checkout |

An edit in the checkout proves nothing in the bot until `go.work` is on or the pin moves, and
the index answers for the pin, never for a checkout past it. A prediction-bot session that
edits the fork needs two things from the shell it starts in, and a clone no other open
session has:

```sh
export BSC_FORK_PATH=~/Developer/bsc-geth        # the hooks and bsc-fork read it
claude --add-dir "$BSC_FORK_PATH"                # or /add-dir in the session
```

## bsc-fork

```sh
bsc-fork pin                              # module, version, SHA, the pinned tree, the checkout, what compiles, index state
bsc-fork show MilliTimestamp              # signature, file:line, verified, note
bsc-fork search pending tos               # rows where every term appears; name matches first
bsc-fork list --kind flag                 # also: --unverified
bsc-fork check                            # exit 1 when the index was not built at the pin
bsc-fork path core/types/block.go:167     # the absolute path, in the tree the build compiles
bsc-fork path --checkout eth/handler.go   # in the checkout: the file to edit
```

`-C DIR` works from another directory; `--json` for a script. Exit codes: 0 answered, 1 nothing
matched or stale or absent, 2 usage, no fork pin, or no index. It reads; it never generates
and never moves the pin. The index is the repo's (`make fork-index`, the `fork-indexer` agent).

## Cloud sessions

A session of Claude Code on the web (claude.ai/code, the Desktop app's Cloud mode, `claude
--cloud`) runs on a fresh Anthropic-hosted VM, Ubuntu 24.04 on x86_64, documented at 4 vCPUs
and 16 GB, with a fresh clone of one repository. For bsc-geth that session is set up in two
places, and the kit reaches it through the first.

**The environment, at claude.ai/code.** Environments are created and edited only in the
environment selector on the new-session screen (the first control under the message box →
**New environment**); the CLI cannot create one. `/web-setup` sends the local `gh` token to
the claude.ai account, which is what lets a cloud session clone the private fork, and makes a
bare **Default** environment when none exists; `/remote-env` picks, among the existing ones,
the default for `claude --cloud` and writes `remote.defaultEnvironmentId` to the user
settings. The bsc-geth environment is:

| Field | Value |
|---|---|
| Name | `bsc-geth` |
| Network access | **Trusted**: the default allowlist carries `proxy.golang.org`, `sum.golang.org`, `github.com` and the release hosts `objects.githubusercontent.com`, `release-assets.githubusercontent.com` |
| Environment variables | none |
| Setup script | `share/cloud-setup-bsc-geth.sh`, pasted whole |

The script runs as root before Claude Code launches, once per environment cache (about
seven days, or until the script or the allowed hosts change), and must exit 0 inside about
five minutes or nothing is cached. It warms Go 1.27.1 through `proxy.golang.org`, builds
gopls into `/usr/local/bin` (bsc-geth's `.mcp.json` names a bare `gopls`), fetches the
golangci-lint archive `build/ci.go` would download into `/root/.cache/bsc-geth` (a `go
install` of the same version when the release host is refused), and downloads the modules
when it finds the clone. Every step is `|| true`. A change to it is a kit commit, then a
paste into the dialog: nothing propagates on its own.

**The clone, in bsc-geth.** `.claude/settings.json` runs `build/cloud-session-start.sh` as a
SessionStart hook (`startup|resume`). Outside a cloud session it exits at once. In one,
each start: `make dev-setup`, so the reference-transaction guard holds `master` and
`mrinal/master` there as on a dev box and the pre-push ratchet is live; the fetched linter
archive verified against `build/checksums.txt` and unpacked into `build/cache/`, where the
ratchet and `make lint` look; then one `Cloud session:` line with what it measured: Go,
CPUs, memory, whether a systemd user manager answers, the guard and the linter. The fork's
development document (its docs index lists it) carries the clause the line points at: no
systemd user manager, so `build/unit_run.py` cannot run and heavy work goes in the foreground.

**The kit reaches the VM through the setup script, and only that way.** A cloud session
installs no plugin from a repository's `enabledPlugins` or `extraKnownMarketplaces` (Claude
Code docs, Cloud environments, "What carries over"), and a private repository is out of a
VM's reach: the setup script runs before the session's GitHub proxy attaches, and that proxy
serves only the repositories attached to the session. So this repository is public
(operator, 2026-10-16), and the setup script clones it to `/opt/blockchain-kit` and installs
the plugin at user scope on the VM by both routes it has: `claude plugin marketplace add` and
`claude plugin install --scope user` when the `claude` CLI is on the setup script's PATH, and,
always, a `directory` marketplace entry plus `enabledPlugins` merged into
`/root/.claude/settings.json`. Whether either loads is not documented, and three things could
stop it: the GitHub proxy may refuse a clone of a repository not attached to the session,
public or not (the docs say so for archives; the setup script may run before that proxy
applies); bsc-geth's own `.claude/settings.json` names the same marketplace from a `github`
source, and two layers naming one marketplace from two sources is undocumented; and a
plugin with a `bin/` directory is one claude.ai and Cowork do not install (Claude Code docs,
Plugins reference), which may or may not reach the cloud CLI. The measurement is the
session-start context: a `blockchain-kit: running from the checkout /opt/blockchain-kit at
<sha>` line means the kit loaded; without it the session has bsc-geth's `CLAUDE.md`,
`.mcp.json` (gopls) and the git guards, nothing of the kit, and its result is read by a local
session with the kit. Public means public: the code, the issues (#7 holds the Claude-issue
triage), the pull requests and this README are readable by anyone. Nothing in them is a
credential or an address: the tree, the history, the issues, the PR bodies and the comments
were scanned on 2026-10-16 before the change, and a kit change is reviewed as public text
from now on.

**Starting one.** From claude.ai/code, pick the repository, the branch (`mrinal/dev`) and the
`bsc-geth` environment. From a terminal, `claude --cloud "<task>"` in a bsc-geth clone uses
the `/remote-env` pick, but it clones from GitHub only when the Claude GitHub App is
installed on the repository; without it, `/web-setup` connection or not, it uploads a bundle
of the local clone, and bsc-geth is well past the 100 MB bundle limit (Claude Code docs,
Cloud sessions, "Send local repositories without GitHub"). `gh pr` and `gh issue` fail in a
cloud session (GraphQL is refused); `gh api repos/...` works.

**What the setup script places beyond Go.** gopls, the golangci-lint archive for `make lint`,
the module cache, `shellcheck` (for the fork's shell scripts) and `benchstat` (pinned to an x/perf version in the script; the before/after perf gate of the fork's hygiene
refactor, `2026-10-16-fork-hygiene-refactor.md` in bsc-geth's plan history). Each step
is tolerated absent, capped so the five-minute cache window holds, and named in the setup
output, which ends with whether shellcheck and benchstat landed; `go generate` needs nothing extra, since
bsc-geth pins gencodec with a go.mod `tool` directive and `go mod download` warms it.

**The first session is the measurement.** Ask it to show its session-start context (the
`Cloud session:` line and whether a `blockchain-kit:` line is there), then to run
`check-tools`, `go version`, `make geth`, `make lint`, `git config --get core.hooksPath`,
`ls build/cache`, `ls /opt/blockchain-kit`, `cat /root/.claude/settings.json` and `git
ls-remote https://github.com/mrinaldhillon/blockchain-kit`. That settles what the docs leave
open: the base image's Go, whether the toolchain download, the gopls build and the linter
archive got through the proxies inside the five-minute cache window, whether `make lint` has
its binary, and, for the kit, which of three cases holds: the clone failed during setup
(`/opt/blockchain-kit` absent), the clone fails in-session too (`ls-remote` refused), or the
clone worked and the plugin did not load (the directory there, no `blockchain-kit:` line).
Until then, every claim in this section about what works in the VM is read from the docs,
not measured.

## Checks

`tests/run` is the hermetic suite: no network, no Go toolchain, no `claude`; `node` for the
workflow tests, which are skipped without it. The kit has no CI and no required check: a
change to steering carries no gate (operator, 2026-10-09). Run `tests/run`, `claude plugin
validate .`, shellcheck and ruff by hand when a change touches what they cover. What Claude
Code does with a hook's answer, whether a skill or an agent loads, and what an agent does
with a prompt are live runs; the ones made are in `docs/migration-plan.md` §Phase 0 results.

## Sources

Copied, then edited, from prediction-bot `01f5af59`, bsc-geth `a84a2279`, claude-kit
`plugins/lang-go` `29efe52` and ios-kit 0.11.0. prediction-bot's steering layer as it stands
before the move is tagged `steering-final` when the cut lands (migration plan, C2).

## Requirements

Python 3.9+ on `PATH` as `python3` (standard library only). `go`, `gofmt` and `git` on `PATH`.
`claude` for setup and update. Linux or macOS.
