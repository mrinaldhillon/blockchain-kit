---
name: replay-parity
description: >-
  Use when implementing or reasoning about replay, the parity test, determinism,
  or the replay-parity gate — internal/replay, the trigger/decision determinism
  checks, or any change that could make replay diverge from live. Trigger before
  claiming a milestone gate is met.
---

# Replay parity (the tested invariant, rule 32)

Spec: `docs/specs/trigger.md` (replay driver), design-notes §3.10. Live and replay
share pure logic (parse, state update, feature construction, decision); they
differ only in drivers (live = per-feed goroutines + atomic pointers; replay =
single serial loop over time-ordered events with the full order-key k-way merge).

## The three properties
1. **Determinism — exact, deploy-gating.** Replaying the same stream twice with
   the same code/config/versions yields **bit-identical** decision output. No
   tolerance. This is what `make replay-parity` asserts (against a checked-in
   golden `Output`). M1 asserts bit-identical **triggers**; M2 adds **decisions**.
2. **Live-faithfulness — no lookahead.** Information visible at a replayed decision
   is exactly what was visible live at that instant (same feed-latency and
   publish-cadence profile). Achieved by construction via the clock-driven cadence;
   spot-checked (every feature reconstructable from data before the trigger).
3. **Equivalence under change — semantic.** A refactor/strategy change flips no
   decision except where intended; edge/size move within bounds; PnL-delta
   reported. Not bit-equality to a prior version.

## What breaks it (forbid)
The determinism footguns are `docs/discipline.md` rules **6, 12, 14, 15** — read
them there (the hot-path latency rules 16, 17, 40 ride the
`blockchain-kit:hot-path-determinism` skill). Decisions are pure functions of
`(snapshot, config, model params, trigger context)`.

## Running it
`make replay-parity` replays a captured fixture and diffs against the golden
output; failure **blocks deploy**. The fixture lives in
`testdata/recorded/`/`internal/replay/testdata/`. Determinism is run-to-run
exact; faithfulness is spot-checked; equivalence reports PnL-delta across a
held-out corpus.

## Runtime knobs are provenance, never key material (rule 35)
`GOGC` / `GOMEMLIMIT` / `GOMAXPROCS` — and `cmd/replay`'s self-defaulted GC
regime — are output-invariant by construction and are stamped into fitwalk
provenance (`gcRegime`) so runs stay diffable. They must **never** enter the
dataset manifest or shard cache key: a key that varies with a runtime knob
silently invalidates the warm prod cache while every test stays green.
Conversely, a cross-binary comparator (invariance gate) scrubs exactly
`{codeVersion, codeVersionIsStamped, gcRegime}` and diffs everything else —
and is itself subject to rule 44 (absent keys fail loud, never pass vacuous).

## Sanctioned regeneration (property 3, M5b/WS1)
A golden that moves is **property 3, not a chore**: regenerating first destroys the
only evidence of what changed. Order is fixed:
1. **Capture the diff WITHOUT regenerating** — run the parity test, save the
   failure output (expected vs got, field by field). This is the artifact.
2. **The `blockchain-kit:parity-auditor` agent adjudicates** the captured field-level movement: is every
   moved field one the change intends to move, and is every unmoved field one it
   must not? Its verdict is the sanction; a self-assessment is not.
3. **Only then regenerate** with `-update`.
4. **Verify the regenerated diff matches the captured one** (`git diff` the golden
   against step 1's record). A field that moved in the regeneration but not in the
   captured failure is an unreviewed change — stop.

## The `-update` hazard
`internal/replay/parity_test.go` declares **one package-level** `updateGolden` flag consumed by
**both** parity tests (`TestReplayParity`, `TestReplayParityDecisions`), and
`-run TestReplayParity` **prefix-matches both**. So the obvious command silently
regenerates the decisions golden too. Always anchor the regex:

```
go test ./internal/replay -run '^TestReplayParityDecisions$' -update -count=1
go test ./internal/replay -run '^TestReplayParity$'          -update -count=1
```

Then `git diff` the golden files and confirm only the intended one moved.
