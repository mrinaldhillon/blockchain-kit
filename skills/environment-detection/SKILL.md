---
name: environment-detection
description: >-
  Use when wiring endpoints, choosing IPC vs WebSocket for geth, configuring the
  Binance SOCKS5 proxy, or writing tests that must run offline. Trigger for
  internal/envdetect, transport selection in nodeapi/binance, and CI/test setup.
---

# Environment detection

Spec: `dev-setup/dev-setup.md`, `docs/operations.md` §7. The same binary runs on prod
and the dev box; the environment is **declared, never detected** (ADR 0031) —
there is no IPC-socket probe and no ambient inference of any kind.

## Resolution order (highest wins)
1. **`PB_ENV` / `--env` — REQUIRED.** Must be exactly `"prod"` or `"dev"`. Missing
   or invalid is a startup fatal: `envdetect.Detect` returns `ErrEnvUnset` /
   `ErrEnvInvalid` and every caller logs at ERROR and exits non-zero — it never
   falls back. Prod pins `Environment=PB_ENV=prod` in the systemd unit; a dev box
   pins `PB_ENV=dev` once via the dotenv (step 3) or exports it.
2. **Explicit endpoint/proxy override** — `--node-endpoint` / `BSC_ENDPOINT`,
   `--binance-proxy` / `BINANCE_PROXY` — wins over the declared environment's
   built-in default, within that environment. The proxy tier is resolved by ONE
   shared function, **`envdetect.ResolveBinanceProxy(flagValue, flagSet) (string,
   bool)`**, called by all three Binance-consuming binaries (`cmd/bot`,
   `cmd/collector-binance-spot`, `cmd/collector-binance-perp`), each spelling the
   flag **`--binance-proxy`** — never open-code the tier in a `main`. Two edge
   rules are **contractual**, not incidental:
   - an **explicitly-passed flag wins even when its value is empty** —
     `--binance-proxy=""` declares DIRECT egress and must outrank an inherited env
     var. Answering "was it passed?" is the second shared helper,
     **`envdetect.BinanceProxyFlagSetIn(fset *flag.FlagSet) bool`**, registered
     against **`envdetect.BinanceProxyFlagName`** so the name the flag is declared
     under and the name the scan looks for cannot drift. Call it once, right after
     `fs.Parse(...)`, and feed its result to `ResolveBinanceProxy` as `flagSet`.
     **Never open-code a `Visit`-by-name loop** — that is how the tier gets
     duplicated, and its failure mode is silent: a
     wrong `false` is indistinguishable from "the operator did not pass the flag",
     so an explicit `--binance-proxy=""` reverts to the dev SOCKS5 default with no
     error. The `*flag.FlagSet` is a **parameter**, not `flag.CommandLine` read
     implicitly, precisely so it also serves a binary with a private FlagSet —
     `cmd/bot` passes its own `fs`; the two collectors pass `flag.CommandLine`;
   - an **empty env var reads as unset** — `BINANCE_PROXY=` in a unit file or a
     sourced dotenv is absence, not a declaration, so the declared environment's
     default applies.

   The two helpers are complements with one job each and there is exactly ONE
   proxy-precedence resolver: `BinanceProxyFlagSetIn` resolves *was the flag
   passed*, `ResolveBinanceProxy` resolves *which tier wins*, and `Detect` applies
   the result within the declared environment. A helper that returned a finished
   `Env` would have to invent the rest of `Flags` and so could not serve `cmd/bot`,
   which also carries a `--endpoint` override.

   ADR 0031 is satisfied: reading an explicitly-set env var is a *declaration*
   (exactly as `$PB_ENV` is), not the ambient inference the ADR forbids. The value
   only ever feeds `Flags.BinanceProxy`, which `Detect` applies WITHIN the declared
   environment; it never re-derives which environment this is.
3. **Per-user dev dotenv** — `envdetect.LoadUserEnv(UserEnvPath())` back-fills
   `PB_ENV` / `BSC_ENDPOINT` / `BINANCE_PROXY` from
   `${XDG_CONFIG_HOME:-~/.config}/prediction-bot/env` for keys not already set (a
   real env var / flag still wins; missing file = no-op). **Endpoints only** —
   the secret `BINANCE_API_KEY` stays in its own `0600` file.
4. **Declared-environment default** — `prod` → IPC for BSC (`/run/geth/geth.ipc`),
   direct Binance egress (no proxy); `dev` → BSC over `ws://10.99.0.1:8546`,
   Binance egress via SOCKS5 `socks5h://10.99.0.1:1080` (`socks5h` resolves DNS at
   the proxy).

## Rules
- SOCKS5 carries **Binance only**, never the node.
- `internal/nodeapi` dials one `endpoint` string via `rpc.Dial`; it dispatches on
  form (IPC path vs `ws://`); custom subscriptions are identical across transports.
- `internal/envdetect.Detect(flags)` takes only `Flags` (no injected stat/probe —
  ADR 0031 removed it); `IsProd` is exactly what `PB_ENV` declared, never
  re-derived from an overridden endpoint's shape (a `dev` declaration with an
  IPC-shaped `--node-endpoint` override is still `IsProd=false`, and
  symmetrically for `prod`). Unit tests exercise `Detect` directly — no stat
  injection needed, since there is nothing left to probe.
- All resolved values, **including `PB_ENV` itself**, are **environment wiring →
  excluded from `ConfigHash`**, so dev and prod hash identically.
- Canonical prod IPC path is `/run/geth/geth.ipc` (not `/var/run/...`).
- **Why declared, not probed:** ADR 0031 — a probe-based resolver can fall back
  to the wrong environment silently; declaring it removes the ambient inference.
