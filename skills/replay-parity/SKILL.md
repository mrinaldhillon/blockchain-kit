---
name: replay-parity
description: "Replay, the parity test and the replay-parity gate."
---

**When to load:** Use when implementing or reasoning about replay, the parity test, determinism, or the replay-parity gate — internal/replay, the trigger/decision determinism checks, a parity golden that moved, or any change that could make replay diverge from live. Trigger before claiming a milestone gate is met.

# Replay parity (the tested invariant, rule 32)

**Load when**
- A diff touches `internal/replay`, trigger or strategy derivation, or anything replay reads.
- A parity golden moved, or you are about to claim a gate that rests on parity.

**Where the facts live** (pb repo paths)

| Topic | Doc |
|---|---|
| The three properties; shared pure logic vs drivers; purity, float order | `docs/design-notes.md` §3.10; `docs/discipline.md` §32 |
| Replay driver, merge order, the gate, no lookahead | `docs/specs/trigger.md` §5, §6 |
| Determinism footguns | `docs/discipline.md` §6, §12, §14, §15; hot path §16, §17, §40 |
| Where parity fixtures and goldens live | `docs/specs/fixtures.md` §Layout, §Tests, §Open |
| Regenerating a golden; the shared `-update` flag | `docs/specs/trigger.md` §5 (Regenerating a parity golden) |
| Runtime knobs vs shard key and provenance; comparing two builds | `docs/specs/trigger.md` §5 (Runtime knobs are provenance); `docs/decisions/0025-m5b-close-at-dev-gate.md` §Decision, point 6 |
| Version stamps; fail-loud comparators | `docs/discipline.md` §35, §44 |

**Commands that answer questions**
- `make replay-parity` (Makefile): both parity tests, anchored, `-count=1`. Red blocks deploy.
- `go test ./internal/replay -run '^TestReplayParity$' -update -count=1` (trigger goldens) or `-run '^TestReplayParityDecisions$'` (decision goldens): only at step 3 of the order in `docs/specs/trigger.md` §5.

**What only this skill says**
- Never regenerate first. Keep the failing diff, then dispatch the `blockchain-kit:parity-auditor` agent on it; its verdict is the sanction, a self-assessment is not.
- Never run `-update` with an unanchored `-run TestReplayParity`: it prefix-matches both tests and rewrites every parity golden, trigger and decision.
- A gate claim names a green `make replay-parity` at the commit claimed.
- A diff in a hot-path package also loads `blockchain-kit:hot-path-determinism`.
