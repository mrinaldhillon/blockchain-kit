---
name: hot-path-determinism
description: "Determinism rules for the record spine and the derive and decide packages."
---

**When to load:** Use before editing or reviewing a record-spine or derive/decide package — internal/event, eventlog, trigger, strategy, state, replay, executor — and for any diff that reads a clock, draws a random number, ranges a map into output, blocks on the hot path, or publishes through an atomic pointer.

# Hot path + determinism — the parity footguns

Companion to `docs/discipline.md` (the home of the numbered rules) and CLAUDE.md
§Non-negotiable invariants, for the record-spine and derive/decide packages:
`internal/event`, `internal/eventlog`, `internal/trigger`, `internal/strategy`,
`internal/state`, `internal/replay`, `internal/executor`. This file points;
discipline.md states.

The footguns that break replay parity or corrupt the log are `docs/discipline.md`
rules **6, 12, 14, 15, 16, 17, 40** — read them there.

Working discipline on any diff here:

- Run the **`blockchain-kit:determinism-auditor`** agent early (fast advisory
  pre-scan of exactly these footguns). It never substitutes for the gate: the
  pre-merge review re-checks and subsumes its findings, and
  `make replay-parity` (rule 32) is the authority.
- `OrderingVersion` and the stored-data contract (rule 42): `docs/specs/log-format.md`
  (the `OrderingVersion` pin) and `docs/discipline.md` rule 42; a dataset is deprecated only
  via `docs/data-deprecations/`.
