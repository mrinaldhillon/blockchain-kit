# Known landmines for the next upstream rebase (v1.8.0)

The target-specific intelligence the `upstream-rebase` skill consumes. Paths are in the
fork checkout. Verified against `upstream/master` at v1.8.0-alpha, ~511 commits past
v1.7.8, with the fork at `a84a2279`:

- **`EnableOpcodeOptimizing` is removed and is *not* deprecated-listed**, so putting it back in
  the deploy `config.toml` (`deploy/production/host/srv/`) would be a hard TOML decode error and **geth refuses to start** —
  the same failure mode `EnableBAL` had. Already defused: both the TOML key and the
  `--vm.opcode.optimize` CLI flag are gone from the deploy bundle, so opcode optimization runs at
  its `false` default (upstream did not just drop the flag, it **reverted the whole feature** in
  `d6f5ff936`). Nothing to do at the rebase — just never re-add the key.
  (Removed-but-deprecated-listed keys, e.g. `OverflowPoolSlots`, only warn.)
- **The local-tx reannounce mechanism is removed entirely** (`ReannounceTime`, `reannoTxFeed`,
  `SubscribeReannoTxsEvent`). The fork's `filterLocalReannounceTransactionsExt`
  (`eth/handler_toggles_ext.go`) hangs off it and must be deleted with it.
- **`p2p/server_ext.go`'s `maxDialedConnsExt` dial-ratio formula is deliberately
  re-semanticized vs. upstream** — keep it, don't take upstream's `MaxDialedConns` resolution.
  Upstream reserves `MaxPeers/DialRatio` slots for dialed peers; this fork targets a dialed:inbound
  *mix* of `ratio:1` (`maxPeers*ratio/(ratio+1)`). Taking upstream's version silently cuts dialed
  peers (200 peers, ratio 3: 150 → 66) — see the comment on `maxDialedConnsExt` itself.
- **`log/handler_glog.go` carries a whole-file fork restructure** (`glogSharedStateExt`, field
  `stateExt`). Resolution at the rebase: take upstream's file wholesale and delete
  `log/handler_glog_ext.go` — upstream's `glogWithAttrs` delegates to the base handler, so the
  fork's runtime vmodule presets keep reaching child loggers. Do not merge the fork's version.
- **`eth/filters/filter_system.go` `SubscribePendingTxs` is a one-call swap** into
  `subscribePendingTxsExt` (`filter_system_ext.go`), which owns the `subscription` literal. If
  upstream adds a field to `subscription`, add it there too — the deleted upstream body will
  conflict rather than silently drop it. The fork's *filtered* pending subscription does not
  go through it (it owns a goroutine and a queue per subscription); the swap stays for
  the poll filter and for upstream's unfiltered `SubscribePendingTxs`, so this note stands.
- Also removed upstream: incremental snapshots, and BSC's p2p ENR node filtering — the latter
  overlaps heavily customised fork territory.
- **An upstream *rename* of a type parameter on a fork-touched generic declaration is a real
  `make audit-ext` finding**: `auditext` renders type-parameter names (`typeParamsText`), and
  compares them — for a type in its own `typeParams` field (`build/auditext/decls.go` `declInfo`,
  compared in `wiring.go` `classifyType`), for a func inside the printed `signature`. So on a
  fork-modified file `[T any]` → `[U any]` is a WIRING **fail**, reading "type parameters of
  upstream type X changed (…)" on a type and "upstream signature of X changed (…)" on a func.
  The remedy is a reviewed row in `build/audit-ext-allow.txt` (the tool prints the exact
  `CHECK<TAB>path:symbol` key to paste), not a change to the rendering — a silent type-parameter
  *permutation* must stay a finding. That row is symbol-keyed, not message-keyed, so it also
  hides every *later* WIRING fail on that declaration, a real body restructure included: drop it
  once the rebase has settled.

