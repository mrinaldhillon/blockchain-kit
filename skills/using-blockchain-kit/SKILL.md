---
name: using-blockchain-kit
description: "The routing table: which kit skill, agent or command to load, and when. A subagent that writes Go loads it."
---

# Using blockchain-kit

Load at the moment named, not after the first failure. The project's own instructions win
over anything here.

| When | Use |
|---|---|
| Before a Go edit, deleting code as unused, or a rename | `blockchain-kit:go` |
| Any node interaction; before citing a go-ethereum, geth or ethclient API | `blockchain-kit:fork-node-api` |
| One fork symbol: signature, `file:line`, `verified` flag | `bsc-fork show <Symbol>`; the rules are `blockchain-kit:fork-lookup` |
| Decoding or packing Prediction V2 or Chainlink data; any on-chain number | `blockchain-kit:contract-abi` |
| Binance market data: SBE, aggTrade, depth snapshots, reconnect, the proxy | `blockchain-kit:binance-streams` |
| The event log: framing, CRC, envelope, `EventKind`, the control stream | `blockchain-kit:record-format` |
| Replay, the parity gate, a golden that moved | `blockchain-kit:replay-parity` |
| A diff in `internal/{event,eventlog,trigger,strategy,state,replay,executor}` | `blockchain-kit:hot-path-determinism`, then the `blockchain-kit:determinism-auditor` agent |
| Endpoints, IPC or WebSocket, `PB_ENV`, a test that must run offline | `blockchain-kit:environment-detection` |
| **Changing the fork itself**: any edit, build, test or commit in the fork checkout; moving the pin | `blockchain-kit:fork-development` |
| Before editing any Go file in the fork checkout | `blockchain-kit:fork-ext-convention` |
| Anything under the fork's `deploy/production/`, its `config.toml` or `ExecStart` | `blockchain-kit:fork-deploy` |
| Moving the fork to a new upstream tag | the user's `/blockchain-kit:upstream-rebase`: not model-invocable |
| A multi-step change, cutting units, landing; what a change owes by class | `blockchain-kit:working-here` |
| An issue about Claude itself: steering, this kit, a hook, skill, agent or workflow, the harness, model cost | `gh issue create -R mrinaldhillon/blockchain-kit`, never the repository you are in |
| A Go slice whose contract is written, in the bot or in the fork | the `blockchain-kit:golang-implementer` agent |
| A product-Go diff about to land that no workflow run reviewed | the `blockchain-kit:code-reviewer` agent, once |
| Before claiming a gate that depends on parity | the `blockchain-kit:parity-auditor` agent, in a snapshot the brief names |
| The fork pin moved, or a needed symbol is not in the index | the `blockchain-kit:fork-indexer` agent |
| The one-time live capture of test fixtures | the `blockchain-kit:fixture-capturer` agent |
| Right-sizing or tuning the running node | the `blockchain-kit:infra-profiler` agent |
| Several independent units of one change, each with its own brief and packages | `/blockchain-kit:implement`: the user's command, which runs the `blockchain-kit:implement` workflow |

- **The node is a private fork, developed from this repo.** The import path reads
  `github.com/ethereum/go-ethereum` and resolves to bsc-geth at the commit `go.mod` pins.
  Upstream documentation and memory do not answer a question about it: an API without a
  fork `file:line` does not exist here. A session rooted here loads none of the fork's own
  steering; its conventions are the four fork skills above.
- **The pin is not the checkout.** The build compiles the pin unless `go.work` is active.
  The two lines below this table say which commit is pinned, where the checkout is, where
  it stands against the pin, and which one this build compiles. An edit in the checkout
  proves nothing in the bot until one of them changes.
- **`bsc-fork` is on `PATH`.** `pin`, `show`, `search`, `list`, `check`, `path`; never
  `Read` `symbols.json` to find one row. The index answers for the pin. If the line below
  says STALE, no `verified` flag holds until the index is regenerated.
- **A subagent gets no skill by description.** Name the skills to load in its brief.
- **Setup is the user's:** `/blockchain-kit:init`, `blockchain-kit-setup`,
  `blockchain-kit-update`. A blockchain-kit command or skill that does not resolve: say so
  and stop.
