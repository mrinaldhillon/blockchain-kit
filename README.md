# blockchain-kit

The Claude Code steering for **prediction-bot** and the **bsc-geth fork** it consumes, developed
together from one session rooted in prediction-bot. A Claude Code plugin plus terminal
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
4. The session adjudicates what came back and lands with prediction-bot's `dev-setup/ci/land`.

What a change owes is read off its diff: prose owes no gate and no review; product Go owes the
selected lanes and one review seat; the record spine, the hot path and the money path add a
read by the main loop and `make replay-parity` when owed.

## Layout

| Path | What |
|---|---|
| `skills/working-here` | the process and the change classes |
| `skills/using-blockchain-kit` | the routing table, given at session start |
| `skills/` (bot) | `go`, `fork-lookup`, `fork-node-api`, `contract-abi`, `binance-streams`, `record-format`, `replay-parity`, `hot-path-determinism`, `environment-detection` |
| `skills/` (fork) | `fork-development`, `fork-ext-convention`, `fork-deploy`, `upstream-rebase` |
| `agents/` | `golang-implementer`, `code-reviewer`, `determinism-auditor`, `parity-auditor`, `fork-indexer`, `fixture-capturer`, `infra-profiler`. None runs above opus |
| `workflows/implement.js` | `blockchain-kit:implement`: Lane → Integrate → Gate → Review → Fix → Re-gate. Its header is the contract of its `args` and its return |
| `commands/implement.md` | `/blockchain-kit:implement`, the user's entry to the workflow |
| `commands/init.md` | `/blockchain-kit:init`, once per project; reports, changes nothing |
| `output-styles/` | `distinguished-engineer`, forced for the plugin: the project sets no `outputStyle` |
| `bin/bsc-fork` | `pin`, `show`, `search`, `list`, `check`, `path` |
| `bin/bk-gate` | `bk-gate [-C DIR] <name> -- <command>`: one verdict line, the last ten lines on red, the command's exit code |
| `bin/bk-mainloop-share` | what main-loop turns were spent on, by category: the kit's one metric |
| `bin/blockchain-kit-context` | the session-start hook: routing table, pin and checkout lines, the kit's SHA, the host, and what is out of place (git guard unarmed, steering files outside the kit) |
| `bin/blockchain-kit-setup`, `-update` | install and update, `--scope user\|project` |
| `hooks/guard-secrets` | denies the file tools node identity and account material and the generic secret patterns; fails closed |
| `hooks/guard-prod-run` | on the production host, denies a bare `replay`, `bot` or collector run that bypasses `scripts/replay-run.sh`; fails closed |
| `hooks/gofmt-on-edit` | formats a Go file Claude writes, in the project or the fork checkout |
| `lib/` | `forkpin.py` (the pin, the module cache, the checkout, `go.work`, the index), `bkhost.py` (the production-host test), `blockchain-kit-homes.sh` (the config home) |
| `share/mcp-gopls.json` | the `gopls` entry for a repo's `.mcp.json` |
| `tests/run` | the hermetic suite: `bin/`, `lib/`, the hooks, and the workflow script against scripted agents |
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
| off | the skill deleted |

Every skill is name-only except `upstream-rebase`, which is user-invocable-only. A mode holds for
every repository: each project's install of one kit commit shares one cache directory.

## Enabling it in a project

prediction-bot commits the enablement in `.claude/settings.json`: `extraKnownMarketplaces` names
this repository, `enabledPlugins` turns the kit on, and `worktree.baseRef` is `"head"` so an
`implement` lane starts at the run branch and not at `origin/main`. Then, once per clone:

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
`BLOCKCHAIN_KIT_GUARD_SECRETS=0`, `BLOCKCHAIN_KIT_GUARD_PROD_RUN=0`.

**The gopls MCP server is the repo's**, in its `.mcp.json`, never the plugin's: a server a
plugin ships is named for the plugin, and the agents are granted `mcp__gopls__<tool>`. The key
must be exactly `gopls`. gopls answers for the fork checkout only while `go.work` is active.

## Three trees

| Tree | Where | What it is |
|---|---|---|
| the pin | the module cache | read-only. What `go.mod` names, what CI compiles, what the index describes |
| the checkout | `$BSC_FORK_PATH` | a clone of bsc-geth. The only tree that is edited |
| what the build compiles | | the pin, unless prediction-bot's `go.work` is active: then the checkout |

An edit in the checkout proves nothing in the bot until `go.work` is on or the pin moves, and
the index answers for the pin, never for a checkout past it. A session that edits the fork
needs two things from the shell it starts in:

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
