---
name: fork-deploy
description: Use before changing anything under deploy/production/ in the bsc-geth fork checkout, or anything that affects the node's config.toml, its systemd unit's ExecStart, the host bundle's MANIFEST, or which repo installs a path on the production host. Covers the offline gate, the two config checkers, one-writer-per-path across the fork's and the bot's manifests, and the keys and flags never to set.
---

# The fork's production deploy bundle

**The fork owns the production host.** The installed OS+geth bundle for the Ryzen 9 5950X
latency host — systemd units, slices and cpuset drop-ins, `config.toml`, sysctl, limits, NIC IRQ
steering, CPU/cache pinning — lives in the checkout at `deploy/production/host/` (`MANIFEST`
declares every installed row, `install.sh` is the only writer, `verify.sh` is the read-only
drift checker). prediction-bot keeps only bot-specific infra in its own manifest; **one
writer per path** across the two manifests, the bot's rows installed first, then the fork's, then
exactly one `daemon-reload`.

The rest of `deploy/production/` is the fork-side contract and tooling: `check-config-ext.sh`
(is a `config.toml`/`geth.service` pairing correct for this fork version?),
`host/geth-preflight.sh` (does it load?), the snapshot tooling (`snapshot/`), the peer tooling
(`peers/`; seeding is deliberately not part of bring-up), PGO capture (`cmd/pgocapture`), and
the redeploy diagnostics.

Every number and its derivation (cache split, `GOMEMLIMIT`, history flags, CPU partition, the
things never to do on this node) is in `deploy/production/README.md`; do not restate them.

## Before changing anything there

Paths are in the checkout; run with `bash "$BSC_FORK_PATH"/deploy/production/…`.

- **The offline gate is `bash deploy/production/host/tests/run.sh`** — shellcheck,
  fixture-sync, run.sh (banners), the both-manifests lint, verify.sh, install.sh,
  fixture-sync (--check/--apply), geth-preflight.sh, nic-{tune,steer}-lt.sh,
  check-config-ext.sh. No CI runs on the working branch pair; this is
  the only evidence. After editing anything under `host/srv/`, run
  `host/tests/fixture-sync.sh --apply` first.
- Anything affecting `config.toml` semantics or the unit's `ExecStart` must keep
  **both** `deploy/production/check-config-ext.sh` (is it correct?) and
  `deploy/production/host/geth-preflight.sh` (does it load?) passing; neither implies
  the other. Update the checker's rules in the same PR as the change they gate.
- **One writer per path.** No installed path may appear in both the fork's
  `host/MANIFEST` and the bot's. `host/tests/manifests_test.sh` asserts the
  fork's half offline against `pb-manifest-paths.txt` (no dependency on the bot's repo). The
  bot's half has no commit-time check; a live two-writer violation reddens `verify.sh`
  assertion 13 (sha256) host-side. Changing the split is a paired change: the fork's
  manifest, the bot's manifest and `pb-manifest-paths.txt`, in one loop
  (`blockchain-kit:fork-development`).
- **Caches are CLI-authoritative**: the four cache keys are absent from
  `config.toml` and `--cache`/`--cache.*` on `ExecStart` are the authority
  (`SetEthConfig` overwrites the TOML values when the flags are set). Never
  re-add the keys. `GOMEMLIMIT` is derived from the split — change one,
  re-derive the other (README §memory).
- Never re-add TOML keys upstream removed without deprecation
  (`EnableOpcodeOptimizing` hard-fails geth startup). Never set `--pruneancient`.
  `--history.blocks` is irreversible.
- A new `*Ext` TOML key or flag is a fork surface (`blockchain-kit:fork-ext-convention`)
  and a row in `check-config-ext.sh`, in the same change.

## Runbooks

Rebuilding a wiped host is `deploy/production/CUTOVER_RUNBOOK.md`; redeploying a new
binary and pairing onto the running host, with prediction-bot's side sequenced in, is
`deploy/production/REDEPLOY_RUNBOOK.md`. Both are numbered steps with a pass condition each:
run in order, stop on a failed check. Running either against the live host is the
user's: an agent prepares and verifies offline, and never touches the live service.
