---
name: record-format
description: >-
  Use when writing, reading, framing, or testing the append-only event log —
  the record codec, CRC, envelope, EventKind values, NodeReorg/infra payloads,
  or fixture round-trip. Trigger for any work in internal/event, internal/eventlog,
  or codec/fuzz tests so framing is never guessed.
---

# Record format (authoritative quick reference)

Specs: `docs/specs/event-schema.md`, `docs/specs/log-format.md`. This skill is
the fast reference; those specs govern.

## Framing
```
record = sync(4) | len(4) | crc(4) | body
body   = fmt(1) | ver(1) | env_len(2) | envelope(env_len) | payload(rest)
```
- `sync`: constant magic; resynchronization anchor.
- `len`: uint32 LE byte length of `body`.
- `crc`: **CRC32C (Castagnoli) over `len_bytes || body`** — covers `fmt`, `ver`,
  `env_len`, envelope, payload. Only `sync` and `crc` itself are outside it.
- `fmt`: container-layout version; `ver`: envelope codec version. Both
  version-gated; readers keep all historical decoders forever.
- `envelope`: protobuf receive metadata. `payload`: raw wire bytes, eternal.

## Read & resync
Verify `sync`; read `len`/`crc`/`body`; recompute CRC32C. On mismatch emit a
`CorruptRecord` diagnostic (file, offset) — a hook both exported
`eventlog.Reader` constructors register by default, incrementing the unlabeled
in-process counter `telemetry.ReplayCorruptRecords`
(`replay_corrupt_records_total`) before forwarding to a caller's own hook, which
`SetOnCorrupt` adds rather than replaces; the counter takes damage only — an
`ErrResyncRefused` callback (intact bytes — routed to its own counter
`telemetry.ReplayResyncRefusals`, `replay_resync_refusals_total`, and
still visible per-Reader via `ResyncRefusals()`), an `ErrUnknownCodec`
callback (routed to `replay_unknown_codec_records_total`), and an
`ErrUnresolvedTail` callback (a length shortfall whose resync framed at least one
candidate — cleared `sync`/`len`/an accepted `fmt`/`ver` and a body wholly present —
then rejected it at CRC or the §4.2 ordering guard; routed to
`replay_unresolved_tails_total`, still visible per-Reader via
`UnresolvedTails()`) each route to their own counter instead — and **scan forward
to the next `sync`** — never abort the
file, never *silently* drop the remainder (a non-EOF stream-read error, e.g. a
damaged `.zst`, does end the read early, but counted, not silent). A candidate
`sync` is accepted only when a full record parses, CRC passes, and StreamSeq
continues the epoch (rejects a `sync` pattern inside payload). A short read at
EOF is decided by evidence: a corrupt in-range `len` (or false `sync`
candidate) with a valid record behind it is counted and recovered; a shortfall whose
resync framed a candidate it could not accept is counted too, as `UnresolvedTails()`,
never folded into a clean EOF; only a genuinely torn tail — including a torn record
*header*, or a tail whose every record has a damaged header (event-schema
invariant 13) — is a clean, uncounted EOF. **Report all four
counters, never sum them:** `UnresolvedTails()` counts BREAKS, not records, and fires
*alongside* `ResyncRefusals()` on a refused tail. The write side has an instance
too: `internal/recorder`'s startup tail scan logs one Warn line per lossy segment
carrying all four. The replay loaders surface a fifth count beside them,
`OverlapDuplicatesDropped` (hot-restart copies dropped by `eventlog.DedupOverlap`,
ADR 0075): not a loss class, never summed with the four. The read buffer is
capped at one maximum record.

## Envelope (no GlobalSeq, no LocalMonoNs, no Removed)
`StreamSeq` (per-stream, gap detection only), `Collector`, `Stream`,
`LocalWallNs` (clamped non-decreasing — the ordering key), `SourceNs`, chain
fields (`BlockNumber`, `BlockHash`, `TxHash`, `TxIndex`, `LogIndex`; zero-cost
when absent), `Kind`, `Raw`. Additive-only protobuf; never renumber/remove a tag.

## EventKind ranges
Data `1 ≤ k < 100`; infra `100 ≤ k < 200`; bot `k ≥ 200`. Infra includes
`FeedDown`/`FeedUp`/`SequenceGap`/`Resync`/`RecorderStarted`/`RecorderStopped`/
`NodeReorg`(**106**)/`ClockCorrection`. Infra payloads are `encoding/json`,
fixed field order. **`NodeReorg` payload:**
`{"orphaned":[{"block_number","block_hash"}],"canonical":[...]}`. Field 12 is
reserved/unused — no `Removed` field anywhere (`fork-node-api`); reorg is
head-`ParentHash`-derived.

### The `""` recorder-control stream (read before writing any log consumer)
Infra kinds are **not** interchangeable in where they live. `FeedDown`/`FeedUp`/
`SequenceGap`/`Resync`/`NodeReorg` always carry a **real stream** and are ordinary
merge-ordered records. `RecorderStarted`(104)/`RecorderStopped`(105), and a
collector-wide `ClockCorrection`(107), ride **`Stream == ""`** — process/epoch
provenance, not a feed. `""` **is a registered entry
in `feedid.StreamPriority()`, at priority -1** — below every feed stream, so a
bracket sorts BEFORE the data it stamps on a clamped `LocalWallNs` tie (the entry is
what `OrderingVersion` v6→v7 covers).

Consequences, in order of how easily they bite (spec: `docs/specs/log-format.md` §4):
- A merging consumer **does not drop control records** — they resolve through the
  table and merge like any record (no-ops for derivation; in replay their recorded
  wall stamps feed the ADR 0044 recorded-stall backstop). Never drop `""` records
  before the ordering lookup, and never fail loud on one.
- **Classification is `event.IsRecorderControlEvent(ev)`** — never a hand-copied
  kind list, and never the kind half alone. `EventKind.IsRecorderControl()` is
  **kind-only**, and `ClockCorrection` is written BOTH ways:
  `recorder.streamState.clampStep` mints one on every backward wall step of a DATA
  stream and `send` stamps it with that stream, so a stream-scoped 107 is the
  ordinary case and the collector-wide one the rare case. The bot's action
  streams mint the same 107 (`bot.clockCorrection`) off the shared
  `eventlog.StreamClamp`, so `bot.decisions` is not an exception. A kind-blind
  `if ev.Kind.IsRecorderControl() { continue }` discards those — and because a 107
  occupies a `StreamSeq` slot, dropping it also **fabricates a gap** in the §6.2
  datatrust scan. `internal/datatrust`'s census/gap scans still turn on this
  predicate (stream-continuity semantics, unchanged by the ordering entry).
- The set stays **exact**. Never "any infra kind on `""`": `""` carries ONLY the
  control kinds — an unregistered kind on `""` and a **data** kind on `""`
  (corruption) must both fail loud (discipline 5: replay's kind/stream consistency
  guard), and the refusal should name which case it is. `internal/replay` and
  `internal/datatrust` both refuse with which-case-and-remedy messages (the exact
  wording differs: replay says "record-spine control stream", datatrust
  "recorder-control stream").
- A **new** control kind is registered in `EventKind.IsRecorderControl` in the same
  change that adds the constant and the writer; consumers then need no edit.

## StreamSeq epochs (ADR 0005)
Resets to 0 per process; `RecorderStarted` carries the prior high-water
(tail-scan recovery, no sidecar) and brackets the epoch; gap detection is
within-epoch. zstd-on-close is transparent (reader handles `.zst`); never modify
written bytes.

## Tests
Round-trip every kind from `testdata/fixtures/`; **fuzz the reader** against
corruption, torn final record, and sync-inside-payload (synthetic generator,
`docs/specs/fixtures.md`); assert chain-field zero-elision and `EventKind` pinning.
