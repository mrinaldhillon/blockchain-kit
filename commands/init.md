---
description: Check this project for blockchain-kit — the fork pin and index, the bsc-geth checkout this session edits, the gopls MCP server the agents are granted, and what the repo's own .claude/ now duplicates.
argument-hint: "[--no-build]"
disable-model-invocation: true
allowed-tools: Bash(bsc-fork*), Bash(blockchain-kit-context*), Bash(git rev-parse*), Bash(git status*), Bash(git ls-files*), Bash(go version*), Bash(go env*), Bash(go build*), Bash(command -v*), Read
---

# Initialize blockchain-kit in this project

Arguments: `$ARGUMENTS` — `--no-build` skips the compile check in step 6.

The commands are blockchain-kit's, on the Bash tool's `PATH`; if one does not resolve, call
it as `${CLAUDE_PLUGIN_ROOT}/bin/<command>`. Run the steps in order, one Bash call each.
This command reports and changes nothing: every fix it names is the user's to make or to
ask for. Machine setup is `blockchain-kit-setup`, run once in a terminal; if a step fails
because the machine is not set up, point there.

1. **Where.** `git rev-parse --show-toplevel` — the project root; everything below resolves
   from it. Not a git repository: stop and say so.
2. **The pin.** `bsc-fork pin`. It answers in a fork client (a `go.mod` that replaces
   `github.com/ethereum/go-ethereum`): report the module, the pinned SHA, and whether the
   pinned tree is in the module cache. Exit 2 with "not a fork client": blockchain-kit has
   nothing to check here, the fork itself included (it is developed from its client). Say
   so and stop.
   - the pinned tree absent: `go mod download` needs `GOPRIVATE` and the fork token;
     `blockchain-kit-setup` reports the first.
3. **The fork index.** `bsc-fork check`.
   - `current`, 0 unverified: nothing to do.
   - `stale`: the pin moved after the index was built. Every `verified` flag is void until
     the index is regenerated at the pin: that is the `blockchain-kit:fork-indexer` agent's
     (`make fork-index`). Do not regenerate it here.
   - exit 2, no index: the parse-once bootstrap has not run. Same agent.
4. **The checkout.** From step 2's rows `checkout` and `compiles`.
   - none named: the fork can be read (the pinned tree) and not edited. To develop it from
     this project, `BSC_FORK_PATH` names a bsc-geth clone in the environment `claude` starts
     in. Report and go on.
   - named: report the branch, where it stands against the pin, and uncommitted changes. A
     branch of `master` or `mrinal/master` is a failure to report: fork work is on
     `mrinal/dev`. "The pinned commit is not in it" needs a `git fetch` there.
   - `compiles` says `go.work`: the build is the checkout's, not what CI builds. Report it;
     it is wrong only when the user did not mean it.
   - Read `<checkout>/go.mod`. A refusal or a permission prompt means the checkout is not one
     of the session's directories: `claude --add-dir <checkout>`, or `/add-dir <checkout>`.
   - `git ls-files` cannot see the checkout's steering from here. If `<checkout>/CLAUDE.md`
     or `<checkout>/.claude/` exists (Read), report it: a session rooted in this project
     does not load them, and the kit's fork skills are what it gets.
5. **The gopls MCP server.** Read `.mcp.json` at the root. The agents are granted
   `mcp__gopls__<tool>`, so the server key must be exactly `gopls`.
   - No `.mcp.json`, or no `gopls` key: show `${CLAUDE_PLUGIN_ROOT}/share/mcp-gopls.json` as
     the entry to add. Without it every agent falls back to grep and reports degraded.
   - A `gopls` key whose `command` is a bare name: `command -v gopls` must resolve. A
     `command` that is a path: it must exist and be executable (a repo that pins its own
     binary builds it with its own target, such as `make tools`).
6. **The toolchain.** `go version`, then the `go` directive in `go.mod` (Read it), and the
   checkout's when one is named. A toolchain older than either directive is a failure to
   report. Unless `--no-build`: `go build ./...` in the project. Never build the checkout
   here: its build is heavy work (`blockchain-kit:fork-development` §Commands).
7. **What the repo now duplicates.** `git ls-files .claude/skills .claude/agents .claude/rules
   .claude/hooks`. List the ones blockchain-kit also ships, by name:
   skills `binance-streams`, `contract-abi`, `environment-detection`, `fork-lookup`,
   `fork-node-api`, `record-format`, `replay-parity`; agents `determinism-auditor`,
   `fixture-capturer`, `fork-indexer`, `golang-implementer`, `golang-implementer-lite`,
   `infra-profiler`, `parity-auditor`; rule `hot-path-determinism.md`; hook
   `gofmt_on_edit.py`. A repo copy and the plugin's copy both load, under different names
   (`fork-lookup` and `blockchain-kit:fork-lookup`), and both are paid for. Which one the
   repo keeps is the user's decision: list, do not delete.
8. **Hand back.** One line per step: ok, or what it needs and who does it. `git status
   --short` must be unchanged from before step 1.
