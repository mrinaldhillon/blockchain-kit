# blockchain-kit

Claude Code steering for **prediction-bot** and the **bsc-geth fork** it consumes, developed
together from one session rooted in prediction-bot. A Claude Code plugin plus terminal
commands.

bsc-geth carries no Claude steering of its own. The fork exists for this one client, so
its conventions ship here and a session in the client gets both.

- **`bsc-fork`** — answers a question about the fork without reading the 44 KB index:
  one symbol's signature, `file:line` and `verified` flag; which commit `go.mod` pins;
  where the checkout is and where it stands against the pin; which of the two the build
  compiles; whether the index was built at the pin.
- **A session-start hook** — in the fork's client, the routing table (what to load, and
  when) and two lines: the pin and the index state, the checkout and what the build
  compiles. Anywhere else, nothing.
- **gofmt on edit** — a Go file Claude writes in the project or in the fork checkout is
  formatted in place, never with `-s`. A formatter that fails says so once; it never blocks.
- **A node-secrets guard** — the file tools are denied `nodekey`, `jwtsecret`, `*.jwt` and
  keystore `UTC--*` files, anywhere but `testdata/` and `tests/`. It fails closed.
- **Skills, the bot** — `go` (what a green build, a cached test and a clean `-race` do and
  do not prove; symbol lookup through gopls), `fork-lookup`, `fork-node-api`,
  `contract-abi`, `binance-streams`, `record-format`, `replay-parity`,
  `hot-path-determinism`, `environment-detection`.
- **Skills, the fork** — `fork-development` (the three trees, the edit-to-pin loop, the
  fork's commands, branches and architecture), `fork-ext-convention` (the `Ext` marker,
  `*_ext.go`, the wiring rule, `make audit-ext`), `fork-deploy` (the production bundle),
  `upstream-rebase` (adopting a new upstream tag).
- **Agents** — `golang-implementer` (opus) and `golang-implementer-lite` (sonnet), for a
  slice in either tree; `determinism-auditor`, `parity-auditor`, `fork-indexer`,
  `fixture-capturer`, `infra-profiler`. None runs above opus.

## Three trees

| Tree | Where | What it is |
|---|---|---|
| the pin | the module cache | read-only. What `go.mod` names, what CI compiles, what the index describes |
| the checkout | `$BSC_FORK_PATH` | a clone of bsc-geth. The only tree that is edited |
| what the build compiles | | the pin, unless prediction-bot's `go.work` is active: then the checkout |

Everything checkout-aware in the kit exists because these are easy to confuse: an edit in
the checkout proves nothing in the bot until `go.work` is on or the pin moves, and the
index answers for the pin, never for a checkout past it.

A session that edits the fork needs two things from the shell it starts in:

```sh
export BSC_FORK_PATH=~/Developer/bsc-geth        # the hooks and bsc-fork read it
claude --add-dir "$BSC_FORK_PATH"                # or /add-dir in the session
```

## Layout

| Path | What |
|---|---|
| `bin/bsc-fork` | `pin`, `show`, `search`, `list`, `check`, `path` |
| `bin/blockchain-kit-context` | the session-start hook: routing table, pin line, checkout line |
| `bin/blockchain-kit-setup` | once per machine: the plugin, the stable link, a report on `go`, `gopls`, `GOPRIVATE`, `BSC_FORK_PATH` |
| `bin/blockchain-kit-update` | update the plugin, read the version back, re-point the link |
| `hooks/hooks.json` | `blockchain-kit-context` at session start, `guard-node-secrets` before `Read`/`Edit`/`Write`/`MultiEdit`, `gofmt-on-edit` after an edit |
| `hooks/gofmt-on-edit` | the formatter hook |
| `hooks/guard-node-secrets` | the deny hook for geth node identity and account material |
| `lib/forkpin.py` | the `go.mod` pin, the module cache, the checkout, `go.work`, the index: shared by `bsc-fork` and both hooks |
| `lib/blockchain-kit-homes.sh` | the config home, shared by setup and update |
| `skills/` | the thirteen skills above, and `using-blockchain-kit` (the routing table) |
| `skills/fork-development/references/features.md` | what the fork adds to upstream, feature by feature |
| `skills/upstream-rebase/references/landmines.md` | what is known to break at the next upstream tag |
| `agents/` | the seven agents above |
| `commands/init.md` | `/blockchain-kit:init` — once per project; reports, changes nothing |
| `workflows/implement.js` | `blockchain-kit:implement` — implement → gate → review → verify → fix → re-gate |
| `share/mcp-gopls.json` | the `gopls` entry for a repo's `.mcp.json` |
| `tests/run` | the hermetic suite for `bsc-fork` and both hooks |
| `.claude-plugin/` | plugin + single-plugin marketplace manifests |

## Install

Once per machine, from a clone:

```sh
git clone https://github.com/mrinaldhillon/blockchain-kit.git ~/Developer/blockchain-kit  # private
~/Developer/blockchain-kit/bin/blockchain-kit-setup
export PATH="$HOME/.local/share/blockchain-kit/kit/bin:$PATH"   # in your shell profile, for terminal use
```

`blockchain-kit-setup` is idempotent and reports one row per step: the plugin
(`blockchain-kit@blockchain-kit`, user scope), the stable link, and the toolchain — `go`,
where `gopls` is and whether the claude process can start it, whether `GOPRIVATE` covers
the fork's module path, and whether `BSC_FORK_PATH` names a bsc-geth tree. It installs the
plugin and nothing else. After a kit release: `blockchain-kit-update`.
`claude --plugin-dir ~/Developer/blockchain-kit` loads a working tree for one session
without installing.

**What it costs**, measured (haiku, Claude Code 2.1.283, 2026-09-27): about **3,400
tokens a session in the fork's client**, of which about 1,100 is the session-start table;
about **2,300 in every other repo**, because a user-scope plugin lists its skills and
agents everywhere. `BLOCKCHAIN_KIT_CONTEXT=0` turns the table off; `BLOCKCHAIN_KIT_GOFMT=0`
the formatter; `BLOCKCHAIN_KIT_NODE_SECRETS=0` the guard.

## Per project

`/blockchain-kit:init` (you run it; the model never does) reports the pin and the index
state, the checkout and where it stands against the pin, whether `.mcp.json` has a `gopls`
server under that exact key, the toolchain against the `go` directive, and which of the
repo's own `.claude/` files the kit now duplicates. It changes nothing.

**The gopls MCP server is the repo's**, in its `.mcp.json`, never the plugin's: a server a
plugin ships is named for the plugin, and the agents are granted `mcp__gopls__<tool>`.
The key must be exactly `gopls`. A misspelled grant is silent. gopls answers for the fork
checkout only while `go.work` is active; without it, the fork packages it resolves are the
pin's.

## bsc-fork

```sh
bsc-fork pin                              # module, version, SHA, the pinned tree, the checkout, what compiles, index state
bsc-fork show MilliTimestamp              # signature, file:line, verified, note
bsc-fork show GetHeaderByHash             # a name can have several rows; file:line tells them apart
bsc-fork search pending tos               # rows where every term appears; name matches first
bsc-fork list --kind flag                 # also: --unverified
bsc-fork check                            # exit 1 when the index was not built at the pin
bsc-fork path core/types/block.go:167     # the absolute path, in the tree the build compiles
bsc-fork path --checkout eth/handler.go   # in the checkout: the file to edit
bsc-fork path --pinned eth/handler.go     # in the pin: what CI compiles
```

`-C DIR` works from another directory; `--json` for a script; `--index` or
`$BSC_FORK_INDEX` when the index is not `docs/fork-knowledge/symbols.json`. The checkout is
the one `go.work` uses, else `$BSC_FORK_PATH`, else a local `replace`. Exit codes: 0
answered, 1 nothing matched or stale or absent, 2 usage, no fork pin, or no index. A row
from a stale index prints with a warning on stderr: it is a claim about another commit. So
does a path in a checkout that is not at the pin: the line number may have moved.

It reads; it never generates and never moves the pin. The index is the repo's
(`make fork-index`, the `fork-indexer` agent), and `make fork-knowledge-check` stays the
gate.

## The `blockchain-kit:implement` workflow

For several independent, already-briefed units of Go work. Ask for it by name; the Workflow
tool runs only on an explicit request.

| Stage | Tier | |
|---|---|---|
| Implement | opus | `blockchain-kit:golang-implementer`; loads `go` and the unit's `skills`; returns the paths it changed |
| Gate | haiku | the project's check command; one at a time; a red caused only by another unit's paths is inconclusive |
| Review | opus | the unit's own paths only, against `base` |
| Verify | sonnet | one refuter per finding; a refuter that dies refutes nothing |
| Fix | opus | confirmed findings, in the unit's paths only |
| Re-gate | haiku | the check again after a fix |

```json
{ "units": [
    { "id": "feed-dedup", "brief": "…the contract…" },
    { "id": "reorg-proof", "brief": "…", "skills": ["fork-node-api", "record-format"] } ],
  "gate": "make test-offline", "base": "origin/main" }
```

Units must touch disjoint files. Nothing is committed. A tier above opus is refused.
`make replay-parity` is never a per-unit gate: the result names the units that touched
`internal/{replay,trigger,strategy,state}` under `parityOwed`, and the caller runs it once.

One run is one tree. For fork work, `"fork": "<the checkout>"` puts every stage in that
tree: paths are relative to it, `gate` runs in it (`make audit-ext`), `base` is one of its
refs (`mrinal/master`), `fork-ext-convention` is loaded beside `go`, and the implementer
is told never to build, vet or test the whole fork. A change that spans both repos is two
runs, the fork's first.

## Probed

Claims about Claude Code's behaviour, settled by running it (2.1.283, 2026-09-27, in a
throwaway fork-client repo, `--plugin-dir`):

| Claim | Result |
|---|---|
| The session-start context reaches the model | yes: it quoted the pin line and the checkout line verbatim |
| The hook sees `BSC_FORK_PATH` from the shell `claude` started in | yes: the checkout line named the directory and its branch |
| The plugin's `bin/` is on the Bash tool's `PATH` | yes: `bsc-fork check` ran by bare name |
| `gofmt-on-edit` formats a written file | yes: misformatted content in, formatted file on disk, nothing said |
| A write into the checkout, with `--add-dir`, is formatted too | yes: `PostToolUse` fired, and the file on disk was formatted |
| The four fork skills are listed to the session | yes: all four named, with `fork-lookup` and `fork-node-api` |
| `guard-node-secrets` denies a `Read` of a `nodekey` | yes: the tool call returned the deny reason; the same name under `testdata/` was read |
| An agent's `skills:` with bare names preloads the plugin's skills | yes: the agent quoted `go` and `fork-lookup` |
| An agent's `model:` is honoured | yes: `golang-implementer-lite` ran on sonnet under a haiku session |
| `paths:` on a plugin skill scopes it | **no**: listed before any file was read, and nothing loaded on a matching `Read`. The key is not used; routing is the table plus each description |

One claim about Go, settled the same way (go 1.27.1): a commit SHA written by
`go mod edit -replace=…@<sha>` is rewritten as a pseudo-version by `go mod tidy`. That is
the pin move in `fork-development`; prediction-bot's `make update-fork` is a stub.

Not probed: the workflow inside the Workflow tool (its logic was run against a stubbed
runtime), `blockchain-kit-setup` and `-update` against a published marketplace, any agent
against a live `gopls` server, a project- or local-scope install, and the loop against the
real pair (it needs the private fork's remote and a prediction-bot working tree).

## Sources

Copied, then edited, from pinned read-only clones. prediction-bot is the reference where
the two repos overlap: bsc-geth's steering was seeded from it.

| Source | Commit | What |
|---|---|---|
| prediction-bot | `01f5af59` (fork pin `a539ea2ca63c`) | seven skills, five agents, the determinism rule, the gofmt hook |
| bsc-geth | `a84a2279` | `CLAUDE.md` §What this repo is, §Commands, §Fork-local convention, §Fork-local features, §Architecture, §Commit conventions, §Production deployment, §Known landmines, §Map of docs; the rules `fork-ext-convention` and `prod-deploy`; the skill `upstream-rebase` |
| claude-kit `plugins/lang-go` | `29efe52` | the `go` rule, both implementer agents, the gopls template |
| ios-kit | 0.11.0 | the plugin's form: setup, update, the context hook, the workflow |

Also from bsc-geth: the node-material half of `guard-secrets.sh`, as
`hooks/guard-node-secrets`. Not taken: its process skills, its other hooks and guards,
`unit_run.py` (the bot's runner serves both), and `CLAUDE.md` §Working context and §Claude steering layer,
which are about how a session works and are prediction-bot's to state once.

Changes from the sources that are corrections, not retargeting: `go_package_api` takes
`packagePaths` (the agents said `importPaths`); `go_symbol_references` takes a bare name or
`T.M`, and `pkg.X` errors; the Python rows were dropped from the symbol block; the hooks use
`except (A, B):`, which parses before Python 3.14; `golang-implementer-lite` is pinned to
sonnet, which its own text already claimed.

## Adopting it

Not done, and not this repo's to do.

**In prediction-bot**: the skills, agents, rule and hook that `/blockchain-kit:init` step 7
lists exist in both places, under different names, and both are paid for. prediction-bot
keeps what the kit does not ship: its `CLAUDE.md`, `docs/discipline.md`, its process skills
and commands, its guards, `.claude/tools/`, and `delegation.json`. Its `CLAUDE.md` is where
"the fork is developed from here" is said, in a line.

**In bsc-geth**: `CLAUDE.md` and `.claude/` go. What they said about the fork is in the
four fork skills; `docs/`, `build/auditext`, `make audit-ext` and `deploy/` stay, because
they are the fork's product and its gates, not steering. Two things to decide there, which
the kit assumes nothing about:

- `.githooks/` (`reference-transaction`, `pre-push`) are git's, not Claude's, and with no
  CI on the working branch pair they are the only enforcement on a push. `upstream-rebase`
  names `BSC_REFS_GUARD_DISABLE` only "where the checkout's git hooks are armed".
- bsc-geth's Claude hooks denied git writes while `master` or `mrinal/master` was checked
  out. A session rooted in prediction-bot runs prediction-bot's `main_guard`, which
  protects a branch named `main` (read at `01f5af59`). **Nothing in this kit denies a
  commit on the fork's trunk branches**; with `.githooks/` armed, `reference-transaction`
  still does, at the ref.
- bsc-geth's secrets guard also named the node's own material. That part is
  `guard-node-secrets` here; the generic patterns (`.env`, `*.key`, `*.pem`, `secrets/`)
  are prediction-bot's `guard_secrets`, which matches any path.

Two costs of moving a skill out of the repo it describes. A skill here cannot be updated in
the same commit as the code it describes: `features.md` and `landmines.md` are true at
`a84a2279` and say so. And a `file:line@sha` anchor inside a skill is true at the commit it
names; `bsc-fork show` is the current answer.

## Requirements

Python 3.9+ on `PATH` as `python3` (standard library only). `go`, `gofmt` and `git` on
`PATH`. `claude` for setup and update. macOS or Linux.
