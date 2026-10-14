---
name: using-blockchain-kit
description: "The routing table: which kit skill, agent or command to load, and when. A subagent that writes Go loads it."
---

# Using blockchain-kit

Load at the moment named, not after the first failure. A subagent gets no skill by
description: name the skills to load in its brief. The project's own instructions win over
anything here.

| When | Use |
|---|---|
| **Changing the fork itself**: any edit, build, test or commit in bsc-geth; moving the pin | `blockchain-kit:fork-development` |
| Before editing any Go file in the fork | `blockchain-kit:fork-ext-convention` |
| Anything under the fork's `deploy/production/`, its `config.toml` or `ExecStart` | `blockchain-kit:fork-deploy` |
| The measurement campaign: `cmd/campaign`, `bsc-campaign.timer`, an A/B, a hold | `blockchain-kit:campaign` |
| Moving the fork to a new upstream tag | the user's `/blockchain-kit:upstream-rebase`: not model-invocable |
| Before a Go edit, deleting code as unused, or a rename | `blockchain-kit:go` |
| Any node interaction; before citing a go-ethereum, geth or ethclient API | `blockchain-kit:fork-node-api` |
| One fork symbol: signature, `file:line`, `verified` flag | `bsc-fork show <Symbol>`; the rules are `blockchain-kit:fork-lookup` |
| Decoding or packing Prediction V2 or Chainlink data; any on-chain number | `blockchain-kit:contract-abi` |
| Binance market data: SBE, aggTrade, depth snapshots, reconnect, the proxy | `blockchain-kit:binance-streams` |
| The event log: framing, CRC, envelope, `EventKind`, the control stream | `blockchain-kit:record-format` |
| Replay, the parity gate, a golden that moved | `blockchain-kit:replay-parity` |
| A diff in `internal/{event,eventlog,trigger,strategy,state,replay,executor}` | `blockchain-kit:hot-path-determinism`, then the `blockchain-kit:determinism-auditor` agent |
| Endpoints, IPC or WebSocket, `PB_ENV`, a test that must run offline | `blockchain-kit:environment-detection` |
| A multi-step change, cutting units, landing; what a change owes by class | `blockchain-kit:working-here` |
| An issue about Claude itself: steering, this kit, a hook, skill, agent or workflow, the harness, model cost | `gh issue create -R mrinaldhillon/blockchain-kit`, never the repository you are in |
| A Go slice whose contract is written, in the bot or in the fork | the `blockchain-kit:golang-implementer` agent |
| A product-Go diff about to land that no workflow run reviewed | the `blockchain-kit:code-reviewer` agent, once |
| Before claiming a gate that depends on parity | the `blockchain-kit:parity-auditor` agent, in a snapshot the brief names |
| The fork pin moved, or a needed symbol is not in the index | the `blockchain-kit:fork-indexer` agent |
| The one-time live capture of test fixtures | the `blockchain-kit:fixture-capturer` agent |
| Right-sizing or tuning the running node | the `blockchain-kit:infra-profiler` agent |
| Several independent units of one change, each with its own brief and packages | `/blockchain-kit:implement`: the user's command, which runs the `blockchain-kit:implement` workflow |
| A workflow script written in the session (the `Workflow` tool) | every `agent()` names `model`: `blockchain-kit:working-here`, Tiers and dispatch. The `workflow-tiers` hook refuses one that leaves it unset |

## In prediction-bot

- **The node is a private fork.** `github.com/ethereum/go-ethereum` resolves to bsc-geth at
  the commit `go.mod` pins. Upstream documentation and memory do not answer a question about
  it: an API without a fork `file:line` does not exist here.
- **The pin is not the checkout.** The build compiles the pin unless `go.work` is active.
  The two lines below this table say which commit is pinned, where the checkout is, where
  it stands against the pin, and which one this build compiles. An edit in the checkout
  proves nothing in the bot until one of them changes.
- **`bsc-fork` is on `PATH`.** `pin`, `show`, `search`, `list`, `check`, `path`; never
  `Read` `symbols.json` to find one row. The index answers for the pin. If the line below
  says STALE, no `verified` flag holds until the index is regenerated.

## In bsc-geth

- **This tree is the fork** (`module github.com/ethereum/go-ethereum`). No pin and no index:
  `bsc-fork` exits 2, gopls answers natively, and this source is the reference.
- **Landing:** the class's gate green (`make audit-ext`; `make lint` before a push; `bash
  deploy/production/host/tests/run.sh` for `deploy/`), then `git push origin mrinal/dev`. No
  CI, no `land`, no confirmation. `mrinal/master` is not touched (operator, 2026-10-14). A
  production deploy is the operator's.
- **Heavy work on srv** (the full suite, lint, `geth-prod`, `go test ./...`) runs capped:
  `python3 build/unit_run.py --name <slug> --mem 16G -- <cmd>`, then `python3
  build/unit_run.py --wait <slug>` as foreground Bash at timeout 1800000; or
  `cmd/verifyconstrained`.

**Setup is the user's:** `/blockchain-kit:init`, `blockchain-kit-setup`,
`blockchain-kit-update`. A blockchain-kit command or skill that does not resolve: say so and
stop.
