---
name: environment-detection
description: "Endpoints, IPC or WebSocket, PB_ENV, the SOCKS5 proxy, tests that run offline."
---

**When to load:** Use when wiring endpoints, choosing IPC vs WebSocket for geth (the node), configuring the Binance SOCKS5 proxy, adding a binary that reads PB_ENV, or writing tests that must run offline. Trigger for internal/envdetect, transport selection in nodeapi/binance, a cmd/* main's endpoint or proxy flags, and CI/test setup.

# Environment detection

**Load when**
- Editing `internal/envdetect`, or a `cmd/*` flag that picks a node endpoint or Binance egress.
- Adding a binary that talks to the node or to Binance.
- A test that might touch the network; a dev-box or CI setup question.

**Where the facts live** (pb repo paths)

| Topic | Doc |
|---|---|
| Declared environment, resolution order, defaults, flag spellings per binary, `ConfigHash` exclusion | `docs/operations.md` §7 |
| Proxy edge rules and flag wiring (`ResolveBinanceProxy`, `BinanceProxyFlagSetIn`) | `docs/operations.md` §7 |
| Prod pre-deploy check: no `BINANCE_PROXY` reachable | `docs/operations.md` §7 |
| Dev box: `PB_ENV`, dotenv, tunnels, proxy | `dev-setup/dev-setup.md` §Environment detection, §BSC node, §Binance |
| Why declared; `IsProd`; how tests exercise `Detect` | `docs/decisions/0031-environment-declared-never-detected.md` |
| Transport dispatch: IPC path vs `ws://` | `docs/specs/nodeapi.md` §5 |
| Binance credential and egress | `docs/specs/recorder-binance.md` §3.1 |
| Secrets | `docs/operations.md` §13 |
| Offline test contract | `docs/specs/fixtures.md` §Invariants |
| `PB_ENV` pins in the bot and collector units | the infra repo's `README.md` §The bot and collector units; its `host/srv/etc/systemd/system/` |

**Commands that answer questions**
- `make test-offline` (Makefile) — the suite must pass with geth and Binance down.
- `go test ./internal/envdetect` — the resolver, against `Flags` directly.

**What only this skill says**
- Set `PB_ENV` explicitly on every binary that declares it when a session runs one; a refusal to start is the design, never a cue to guess or fall back.
- Node work: `blockchain-kit:fork-node-api`. Binance egress: `blockchain-kit:binance-streams`.
