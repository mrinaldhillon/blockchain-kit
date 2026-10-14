---
description: Check this project for blockchain-kit — in prediction-bot the fork pin and index and the bsc-geth checkout this session edits; in a bsc-geth clone its git guard; in both the gopls MCP server the agents are granted, and that the repo's own .claude/ holds only settings.json.
argument-hint: "[--no-build]"
disable-model-invocation: true
allowed-tools: Bash(bsc-fork*), Bash(blockchain-kit-context*), Bash(git rev-parse*), Bash(git status*), Bash(git ls-files*), Bash(git config --get*), Bash(test -x*), Bash(go version*), Bash(go env*), Bash(go build*), Bash(command -v*), Read
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
   pinned tree is in the module cache.
   - the pinned tree absent: `go mod download` needs `GOPRIVATE` and the fork token;
     `blockchain-kit-setup` reports the first.
   - exit 2 with "not a fork client": Read `go.mod`. A `module github.com/ethereum/go-ethereum`
     line means this is the fork itself, a bsc-geth root: steps 3 and 4 do not apply. Check
     its git guard instead: `git config --get core.hooksPath` prints `.githooks`, and
     `test -x .githooks/reference-transaction` succeeds; either failing is fixed by
     `make dev-setup`. Then go on at step 5. Any other module: blockchain-kit has nothing to
     check here. Say so and stop.
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
     binary builds it with its own target: `make tools` in prediction-bot, `make dev-setup`
     in bsc-geth).
6. **The toolchain.** `go version`, then the `go` directive in `go.mod` (Read it), and the
   checkout's when one is named. A toolchain older than either directive is a failure to
   report. Unless `--no-build`, in prediction-bot: `go build ./...`. Never build the fork
   here, the checkout or a bsc-geth root: its build is heavy work
   (`blockchain-kit:fork-development` §Commands).
7. **The project's `.claude/` holds only `settings.json`.** `git ls-files .claude`. Any other
   tracked path is steering outside its one home: list them (a count and the directories when
   there are many). A repo copy and the plugin's copy both load, under different names
   (`fork-lookup` and `blockchain-kit:fork-lookup`), and both are paid for. Then Read
   `.claude/settings.json`: `enabledPlugins` names `blockchain-kit@blockchain-kit`,
   `extraKnownMarketplaces` names the kit's repository, and `worktree.baseRef` is `"head"`
   (without it an `implement` lane starts at the default branch's origin tip). The same holds
   in both repositories. Report what is missing: list, do not delete or edit.
8. **Hand back.** One line per step: ok, or what it needs and who does it. `git status
   --short` must be unchanged from before step 1.
