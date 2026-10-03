---
name: record-format
description: >-
  Use when writing, reading, framing, or testing the append-only event log —
  the record codec, CRC, resync and the loss counters, the envelope, EventKind
  values, NodeReorg and the other infra payloads, the "" recorder-control
  stream, StreamSeq epochs, or fixture round-trip. Trigger for any work in
  internal/event, internal/eventlog, a log consumer (replay, datatrust, etl, a
  cmd tool), or codec/fuzz tests, so framing is never guessed.
---

# Record format

**Load when**
- Editing `internal/event`, `internal/eventlog`, or the recorder's write path.
- Writing or changing anything that reads segments.
- Adding an `EventKind`, an envelope tag, an infra payload, or a control kind.

**Where the facts live** (pb repo paths; the specs govern)

| Topic | Doc |
|---|---|
| Envelope, ordering key, priorities | `docs/specs/event-schema.md` §2 |
| `EventKind` values, ranges, classes | `docs/specs/event-schema.md` §3 |
| Framing, CRC, resync, short-read endings | `docs/specs/event-schema.md` §4, §4.2, §8 inv. 13 |
| Codec seam (Go API) | `docs/specs/event-schema.md` §4.1 |
| Protobuf tags, reserved field, compatibility contract | `docs/specs/event-schema.md` §5 |
| Infra payloads, `reason` values, StreamSeq epochs, `NodeReorg` | `docs/specs/event-schema.md` §6 |
| Segment layout, rotation, sealing, zstd | `docs/specs/log-format.md` §2; `docs/specs/storage.md` |
| `meta.json`; the `""` control stream; classifying a control record | `docs/specs/log-format.md` §4 |
| Reader API, the loss counters, the overlap-duplicate count | `docs/specs/log-format.md` §5 |
| Epochs across restarts; hot vs cold restart | `docs/operations.md` §8; `docs/specs/restart.md` |
| Fixtures, reader fuzz, round-trip tests | `docs/specs/fixtures.md`; `docs/specs/event-schema.md` §9 |

**Commands that answer questions**
- `go run ./cmd/segdump [-head N] [-tail N] [-json] <segment>...` (`cmd/segdump`, listed in `docs/architecture.md` §3) — read-only record dump of a `.log` or `.log.zst`.
- `make test-offline` (Makefile) — codec and reader tests on frozen fixtures.
- `go test -run '^$' -fuzz FuzzReaderNeverPanics ./internal/event` (`internal/event/fuzz_test.go`) — fuzz the reader.
- `make generate` / `make generate-check` (Makefile) — protobuf regen; `buf breaking` against `origin/main`.
- `make replay-parity` (Makefile) — after any change a replay reads.

**What only this skill says**
- Read the governing section before writing a consumer; never infer framing or counter meaning from one call site.
- A diff in `internal/{event,eventlog}`: `blockchain-kit:hot-path-determinism`, then the `blockchain-kit:determinism-auditor` agent. A moved golden: `blockchain-kit:replay-parity`.
