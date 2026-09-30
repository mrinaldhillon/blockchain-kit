---
name: go
description: >-
  Use before writing, editing, reviewing or deleting Go: symbol lookup through
  gopls instead of grep, what a green build, vet, cached test or clean -race run
  does and does not prove, map order, injected clocks, atomic publish, error
  wrapping, and the language-version rule. Trigger on any .go file, go.mod, or a
  rename or unused-code removal in Go.
---

# Go authoring — conditional bindings

Load it before the first Go edit; nothing loads it for you when a Go file enters
context. Each rule lives here whole — cite it by name, never by number. These are the Go facts that bite in an agent context;
the repo's own gate commands are not this skill's to state.

- **The symbol-tool rule.** Go symbols go to a semantic tool, never grep. A
  `gopls` MCP server where the repo binds one; `LSP` where it is live. Grep
  silently misses a method that satisfies an interface implicitly (Go has no
  `implements` keyword, so the only textual link between a type and the
  interface it satisfies is the method name), a symbol reached through an
  import alias or a re-export, and anything in a file the current build
  constraints exclude. A grep result presented as a symbol answer is the
  failure the split exists to prevent: say "degraded" when you take it.
- **The reference-count rule.** A `go_symbol_references` result that reads low
  is as wrong as an empty one and looks far more credible. Measured on gopls
  v0.23.0: a query on a fresh workspace returned the declaration alone and
  missed a cross-package call site, repeatedly inside that server session, and
  the same recipe then produced the correct answer three times in a row — so the
  under-report is real and its trigger is not established. Never delete
  "unused" code, and never call a rename complete, on one reference query. The
  authoritative check for call-site completeness is a green `go build ./...`
  plus `go vet ./...`: the compiler sees every call site the build constraints
  include, and a reference query is a convenience beside it.
- **The build-constraint rule.** `go build ./...` type-checks only the files
  whose `//go:build` constraints match the current `GOOS`, `GOARCH`, and tag
  set. Code behind `//go:build linux` is not compiled by a green build on a
  Mac, and code behind a tag no gate sets is compiled by nothing at all. A
  green build is evidence about one platform; name which one when you report
  it, and cross-compile (`GOOS=… go build ./...`) when the diff touches a
  constrained file.
- **The vet rule.** `go build ./...` does not compile `_test.go` files, so a
  build that passes proves nothing about the test tree; `go vet ./...` type-
  checks tests as well as non-test code. That — not the style checks — is why
  `vet` belongs in the gate beside `build` rather than in a lint pass.
- **The test-cache rule.** `go test` caches a passing result keyed on the test
  binary, the command line, and the files and environment the run observed. A
  re-run that prints `(cached)` executed nothing. Anything the cache key does
  not cover — a fixture reached by an absolute path, a changed environment
  variable the test never read through `os.Getenv`, wall-clock behaviour —
  makes a stale pass look identical to a fresh one. `-count=1` is the only
  reliable defeat; use it on every verification run, not just near flaky code.
- **The race-detector rule.** `go test -race` observes the interleavings that
  actually happened in that run. A clean `-race` run is evidence, never proof
  of absence: an unsynchronized access on a path the run did not exercise, or
  one the scheduler happened to serialize, reports nothing. Any diff that adds
  a goroutine, a channel, or a shared field runs `-race`; a clean result is
  reported as "no race observed", never as "race-free".
- **The map-order rule.** Go's runtime randomizes map iteration order on
  purpose, per run. Any output derived from ranging a map — a serialized
  record, a log line, a hash input, an accumulation order — is
  nondeterministic unless the keys are collected and sorted first. A test that
  passes ten times and fails on the eleventh is usually this.
- **The injected-clock rule.** `time.Now()` and the `math/rand` global source
  read state no caller controls, so code that calls either cannot be replayed
  or reproduced. Where a repo has a determinism or replay requirement, the
  clock and the RNG are injected dependencies (a `Clock` interface, a
  `*rand.Rand` built from a recorded seed), including for timers, deadlines,
  and expirations — a `time.After` inside a strategy is the same defect as a
  bare `time.Now()`.
- **The immutable-publish rule.** After `atomic.Pointer[T].Store`, the pointee
  is shared with every reader that already loaded it. Mutating it afterwards is
  a data race that `-race` will only catch if a reader happens to be running.
  Allocate a fresh value and swap; never edit a published one.
- **The language-version rule.** Go's per-file language semantics follow the
  `go` directive in `go.mod`, not the toolchain that compiles it. The
  loop-variable change (each iteration gets a fresh variable, from Go 1.22) is
  the one that bites: the same source compiles under both semantics and
  behaves differently, so a goroutine or a closure capturing a range variable
  is correct or broken depending on a line in a file the diff does not touch.
  Read the `go` directive before reasoning about capture.
- **The gofmt-is-not-goimports rule.** `gofmt` rewrites layout and never adds,
  removes, or regroups an import. A format-on-save hook running `gofmt` leaves
  an unused import as a build error and a missing one as a build error; only
  `goimports` (or the editor's organize-imports) fixes either. Do not read a
  clean format run as a clean import block.
- **Errors carry a chain, not a string.** Wrap with `%w` — once per error, so
  the chain stays walkable — and match with `errors.Is` / `errors.As`, never by
  comparing message text. A wrap adds what the caller could not know (which
  file, which key, which attempt); a wrap that only restates the callee's own
  message is noise in a stack trace made of prose.
- **`context.Context` is the first parameter and is never stored in a struct.**
  It carries cancellation and deadline for one call tree; a context on a struct
  field outlives the call it was made for and silently detaches cancellation.
- **A behaviour change carries its test in the SAME commit.** A commit that changes
  non-test Go in a package and changes no `_test.go` in that same package
  directory is a commit whose behaviour nothing asserted at the moment it
  changed; a later "add the tests" commit is a weaker claim, because the test
  was then written against code that already existed. Four changes assert
  nothing new and are exempt: generated code (`*.pb.go`), a
  deletion-only directory, a comment-only change, and one the commit itself
  names a reason for.
- **`internal/` is compiler-enforced, not a convention.** A package under
  `internal/` is importable only from within the subtree rooted at its parent.
  An import boundary expressed any other way (a naming convention, a lint rule)
  is advisory by comparison — prefer the one the compiler checks.

## Review pitfalls

The classes a review pass flags in Go — nil-map write; a
`sync.Mutex`/`RWMutex` copied by value, or a lock scope that shrank; a slice or
map aliased into a struct the caller keeps mutating; `append` on a shared backing
array; an error wrapped so an `errors.Is`/`errors.As` target no longer matches,
or wrapped twice into a message that reads as two errors; a goroutine that
outlives its context or leaks on a shutdown path; a `time.Timer`/`Ticker` never
stopped; an `atomic.Value` stored with a second concrete type; float equality and
map-iteration-order arithmetic.

**Range-variable capture is not a finding** when the `go` directive is 1.22 or
later: per-iteration loop variables are the language semantics there, so
flagging one is a false positive. Read the directive first.

## What is the repo's, not this skill's

A repo's own gate commands — what its build, vet, test, lint, and vulnerability
passes actually run, and which packages are hot enough to need `-race` on every
diff — live in the repo's own `CLAUDE.md`.

The symbol-tool rule names a `gopls` MCP server; registering one is the repo's
(`.mcp.json`), not the kit's, because a server a plugin ships is named for the
plugin and the agents' grants are `mcp__gopls__<tool>`. The kit ships
`share/mcp-gopls.json` for the default shape (gopls on `PATH`, stdio,
`GOFLAGS=-mod=readonly`); a repo that pins its own gopls binary points `command`
at it. The server key must stay `gopls`. `/blockchain-kit:init` checks it.

In a BSC fork client the go-ethereum import path resolves to the **fork**, at
the commit `go.mod` pins: `blockchain-kit:fork-lookup` before citing any
go-ethereum API.
