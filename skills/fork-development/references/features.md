# Fork-local features (the actual product)

What the fork adds to bnb-chain/bsc, as of fork commit `a84a2279`. Paths are in the fork
checkout. A feature added after that commit is not here: the fork's `docs/specs/` and the
`*_ext.go` files are the current answer, and this file is updated in the blockchain-kit repo.

All under `eth/*_ext.go`, wired into upstream with minimal hooks. Toggled by CLI flags
(`cmd/utils/flags.go`), TOML keys, and live `admin_`/`eth_` RPCs. Enabled state on the prod node
lives in the fork-owned `config.toml` under `deploy/production/host/srv/`
(`blockchain-kit:fork-deploy`).

- **Tunables registry** (`internal/tunablesext`) — the one home for fork package-level knobs: each
  registers with a range, a `runtime`/`restart` scope, a subsystem and an operator-readable
  description. Startup values come from the TOML tables `[Eth.TunablesIntExt]` /
  `[Eth.TunablesBoolExt]` (absent = every knob at its default); `eth_tunablesExt` reads them,
  `admin_setTunableExt` sets one, `adminpeers tunables {show|get|set|reset|diff}` drives both, and
  every accepted change bumps `eth/settings/changes`. **A new package-level knob registers here —
  no new bespoke `admin_set*Ext` setter**, which is also how an experiment gets its sweep surface
  for free (`docs/FORK_NAMING_CONVENTION.md` §Capability completeness).
- **Fast local-tx submit** (`api_backend_fast_tx_ext.go`, `local_tx_fast_broadcast_ext.go`) —
  a locally-signed tx is fanned out to peers *before* txpool insertion, no dedup/knownTxs
  bookkeeping; the pool insert then goes to one bounded inserter goroutine
  (`local_tx_inserter_ext.go`, exists only while the fast path is on) whose overflow returns
  `errLocalTxInsertQueueFullExt` to the submitter instead of a hash and bumps the guard metric
  `eth/localtx/fast/insertdropped` (must read **0**; non-zero means pool insert is not keeping up
  with the bots). The two inserter rejections are `rpc.Error` values with JSON-RPC codes
  **-39001** (queue full) and **-39002** (inserter stopped) so the bot switches on a code, not
  the message; `rpc` matches the code by a plain type assertion, so never re-wrap them on the
  `SendTx` path. Flags `txpool.localfastpropagationext`,
  `txpool.localonlypropagationext`; RPC `admin_setLocalTxOnlyPropagationExt`;
  `eth_featureStatusExt` reports `localTxInserterActiveExt`.
  Blob txs and txs over the tunable `localtx_fast_max_broadcast_size` (default **4096**; upstream's
  `txMaxBroadcastSize` constant still governs `BroadcastTransactions`) can't go out as full bodies, so they
  insert synchronously on the submit goroutine, return the pool's permanent rejection to the
  submitter (stock-geth shape), and are announced by hash *after* the insert — ordering is
  load-bearing, since the announce loop resolves hashes via `TxPool.GetMetadata` and silently
  drops announcements the pool can't back. `eth/localtx/fast/skipped` counts those; it reads
  **0** in production and is the guard on the assumption that the bots only send small calls.
- **Peer budget / dial controls** (`p2p/server_ext.go`, `p2p/dial_ext.go`, `node/api_ext.go`) —
  runtime max-peers and dial-ratio, tracked static/trusted peer sets, one-shot dials.
  Flag `dialratioext` writes into upstream's own `DialRatio` config field
  (`cfg.DialRatio = ctx.Int(DialRatioFlagExt.Name)` in `cmd/utils/flags.go`), but the fork
  re-semanticizes what that field means: `p2p/server_ext.go`'s `maxDialedConnsExt` targets a
  dialed:inbound *mix* of `ratio:1` (`maxPeers*ratio/(ratio+1)`) instead of upstream's
  `MaxPeers/ratio` reservation — see `blockchain-kit:upstream-rebase`, `references/landmines.md`.
  A negative ratio is dial-only (the whole peer budget is dialable), which is what the deploy
  `config.toml` carries: `DialRatio = -1`.
  RPCs `admin_setMaxPeersExt`, `admin_setDialRatioExt`, `admin_peerBudgetExt`, `admin_dialPeersExt`.
- **Peer curation** (`peer_curation_ext.go`, `_config_ext.go`) — background rank-based peer
  eviction: hard disqualifiers `missingBsc2`, `ethProtocol!=68`, `lagging` and local fast-relay
  failure, plus the latency limit; ranked eviction candidates are only tx-silent peers with zero
  block-first wins; ranking protection exempts a peer from every eviction class except a hard
  disqualifier (the random dropper skips protected peers too); over-cap admission runs only with
  curation on and evicts, and over-cap and probe victims get the curator cooldown;
  `txBroadcastDisabled` is a tag, not a disqualifier. A curator eviction carries a class on
  the lifecycle record — `curator/hard:<disqualifier>`, `curator/latency`, `curator/ranked`;
  `admin_probePeersExt` never evicts, only resolves IDs off the dial loop and reports
  `unresolved`. A peer's `protected()` check (`Static || Trusted || Proxyed`) means the curator
  never evicts static/trusted peers itself. Its cooldown is also enforced pre-dial: `p2p/dial.go`
  `checkDial` calls `p2p/dial_ext.go`'s `curatorCooldownBlockedExt` and rejects with
  `errCuratorCooldownExt` while a recently-evicted node is on cooldown. Static and trusted adds
  bypass the cooldown: `curatorCooldownBlockedExt` skips nodes in the dial scheduler's static set
  and `postHandshakeChecks` skips trusted/static connections, so an operator's explicit add always
  dials (pinned by `TestDialSchedStaticAddUnderCooldownExt` and the `p2p/server_ext_test.go`
  exemption tests). Flag `peercurationext`; RPC `eth_peerCurationStatusExt`,
  `eth_peerCurationConfigExt`, `admin_setPeerCurationConfigExt`, `admin_curatorDisconnectPeerExt`
  (an operator drop that carries the curator cooldown and leaves the tracked static set alone).
  The ranked-eviction gate has three modes — `off`, `shadow`, `armed` — and comes up **`shadow`**
  after every restart, so arming is an explicit post-restart RPC. Armed, it needs
  `ReadyMinPeersExt`+20 connected (and `ReadyMinDialedPeersExt`+20 dialed for a dialed victim),
  evicts at most one peer per tick and `PeerCurationRankedGateHourlyCapExt` (default 12, 0 = evict
  nobody) per direction per sliding hour, below the decayed block-first floor
  `PeerCurationRankedGateFloorExt` (a TOML **float** literal — `1.0`, never `1`); every decision
  publishes `rankedCandidate` and a `eth/peercuration/rankedgate/` counter.
  The curator publishes no
  latency series of its own: peer latency is the gauges `eth/peers/latency/{p50,p95,max}`,
  published from the *rank* tick, which runs whether or not curation is on (#101).
  Beside it the rank tick publishes a **shadow** keep line and the bad-peer classes
  (`eth/peer_quality_shadow_ext.go`, knobs under `internal/tunablesext` subsystem
  `peerquality`, gauges `eth/peerquality/shadow/`, the verdict on every
  `eth_peerRankingExt` row as `qualityShadow`, read with `adminpeers quality show`) —
  nothing evicts, protects or dials on any of it.
- **Peer ranking and admission** — `eth/peer_rank*_ext.go`, `p2p/admission_ext.go`; RPCs
  `eth_peerRankingExt`, `eth_registeredSentriesExt`, `admin_probePeersExt`; persisted to
  `<datadir>/geth/peerrank_ext.json`. Detail: `cmd/adminpeers/README.md` §Peer ranking.
- **Pinned peers** (`eth/peer_pinned_ext.go`, `eth/peer_redial_ext.go`) — an auto-pinned
  blocks-first top tier, persisted in `peerrank_ext.json`. Two separate invariants: the rank
  store's cap (`makeRoomLocked`) never evicts a pinned record, and `PinnedDialReserveExt`
  (default 16, TOML only) holds that many *dialed slots* back from discovery for pinned
  identities that are not connected — a pinned dial may exceed the dialed cap by at most that
  reserve. A pinned identity that drops reconnects through the redial controller on the manual
  dial queue, with backoff, never through eviction; every persisted pinned identity is
  re-enqueued at startup. The demote clock measures *contiguous* time connected and outside the
  band and resets to zero on band re-entry, so a pinned peer that dips out and returns never
  demotes (#107). RPCs `eth_pinnedPeersExt`,
  `admin_setPinnedReserveExt`, `admin_setMaxActiveDialsExt` (`MaxActiveDialsExt` TOML,
  0 = coupled to `MaxPendingPeers`); `adminpeers pinned {show|reserve}`.
- **Serving policy** (`protocols/eth/serving_policy_ext.go`, `protocols/bsc/serving_policy_ext.go`)
  — refuse serving bodies/receipts/pooled-tx to peers (headers always served), and gates bsc/2
  `GetBlocksByRange` the same way (`servePeerRequestsExt` in `protocols/bsc/handler.go`
  `handleGetBlocksByRange`). Flag `disablepeerservingext`; `admin_setPeerServingExt`.
- **Block relay toggle** (`eth/handler.go` `blockRelayEnabledExt`, `eth/handler_toggles_ext.go`) —
  suppresses the pre-import full-body block push to peers while keeping post-import hash
  announcements; independent of the peer-serving policy above. Flag `disableblockrelayext` /
  TOML `DisableBlockRelayExt`; RPCs `admin_setBlockRelayExt`, `eth_blockRelayEnabledExt`.
  The RPC toggle is runtime-only: a restart takes the state from the flag/TOML key, so re-apply
  it with `adminpeers features block-relay {show|set}` after every restart.
- **Subscription drop accounting** (`rpc/subscription_ext.go`) — when a `ClientSubscription`
  ends by connection drop or by a notification that fails to decode while notifications are
  still buffered client-side, `Err()` yields a `SubscriptionAbandonedErrorExt` (abandoned count
  + `Unwrap` to the cause) instead of the bare error; the count excludes the notification that
  failed to decode, which was never buffered. `Client.Close` still reports nil. The
  wrapped value's `Error()` text gains a suffix and is no longer `==` the cause, so read it with
  `errors.As`/`errors.Is`, never a string or identity match.
- **Destination-filtered pending-tx feeds** (`filters/pending_tx_by_tos_ext.go`) — lets the bot
  subscribe to pending txs by `to` address: `eth_newPendingTransactionsByToExt` / `...ByTosExt`
  (+ filter variants). Delivery is destination-filtered on the shared `EventSystem` event loop,
  so an unmatched batch costs one map lookup per tx and no allocation. The *watched* set that the
  intake table records against is the union of those open subscriptions and a node-owned
  configured set, TOML `WatchedDestinationsExt` (≤ 4 addresses, startup-only — there is deliberately
  no runtime setter, so a bot cannot change what the node measures); the two gauges
  `filters/intake/watched/{configured,subscriptions}` say which source supplies coverage, and
  `eth_featureStatusExt.watchedDestinationsExt` reports the configured set — JSON `null`, not `[]`,
  when unset. `[[Eth.InclusionMarkersExt]]` (≤ 4 `To`/`Selector`/`Sender` triples; `Selector` is a
  quoted 4-byte hex string) stamps an inclusion mark per matching mined transaction.
- **Bot-facing feed/send/readiness contract**: `docs/specs/bot-feed-contract-v1.md` — wire
  shapes, error codes, depths, which surfaces this build actually serves, the Go bindings
  (`ethclient/gethclient/feed_ext.go`) and the golden fixtures
  (`eth/filters/testdata/INDEX.md`). Types and builders live in
  `eth/filters/block_frame_ext.go`, the method set in `eth/filters/api_surface_ext.go`. Do not
  restate any of it here: this file points at documents, it does not carry them.
  **Hot-path rule:** fork code on the import goroutine is a few marked `// Ext:` hooks under
  the wiring rule (`blockchain-kit:fork-ext-convention`), each with a row in
  `docs/specs/bot-feed-contract-v1.md` §Hot path. A hook is bounded and non-blocking — no I/O,
  no channel send that can wait, no lock a slower goroutine holds — and anything that can run
  elsewhere runs on a goroutine reading what the hook wrote. The rule covers that goroutine
  only: per-peer readers, feed writers and RPC handlers get ordinary judgment about lock hold
  times, not this rule.
- **Tx announce wait** (`eth/fetcher/tx_fetcher_ext.go`, `eth/tx_announce_wait_ext.go`) — the
  fetcher's per-announcement wait before it requests a body, upstream's `txArriveTimeout`
  constant made runtime. TOML `TxAnnounceWaitExt` (nanoseconds, optional: absent means unset
  and the fetcher stays byte-for-byte upstream at 200 ms, an explicit 0 fetches at once,
  outside [0, 5s] refuses to start), `admin_setTxAnnounceWaitExt(millis)` (0–5000,
  runtime-only), `eth_featureStatusExt.txAnnounceWaitMillisExt`, `adminpeers features
  announce-wait {show|set}`. `txGatherSlack` is untouched, so any setting under 50 ms is
  immediate. Intake counters under `eth/txintake/` (`eth/tx_intake_metrics_ext.go`) read its effect.
- **Intake and block-vs-tx measurement** (`eth/tx_intake_*_ext.go`, `eth/tx_vs_block_ext.go`,
  `eth/api_tx_intake_ext.go`, `eth/api_tx_vs_block_ext.go`) — receive-path evidence, diagnostic only,
  outside the frozen bot-feed contract. Spec: `docs/superpowers/specs/2026-09-17-instrumentation-batch-design.md`.
  `eth_txIntakeRecordsExt` pages the per-hash records by a millisecond cursor; `eth_txVsBlockExt`
  classifies a retained block's transactions by when this node first held them — five classes
  (`before`, `inWindow`, `afterImport`, `refused`, `never`) whose shares are of the *classified*
  transactions, with `unstamped` reported beside them as a count and `neverZeroPrice`/`arrivedLate`
  as refinements of `never`, never as classes.
  The same shape covers four more operator-only rings, each paged by a millisecond cursor and each
  reporting a **lifetime** `overwritten` (`pushed − capacity`), so gap detection is a `pushed` delta
  between two drains, not the field: `eth_blockArrivalsExt` (`eth/blockarrivals/`),
  `eth_inclusionMarksExt` (`filters/inclusion/`), `eth_watchedTripsExt` (`filters/trips/`),
  `eth_localTxWritesExt` (`eth/localtx/fast/writerecords/`). `eth/blockarrivals/noimport`,
  `filters/trips/dropped` and `eth/localtx/fast/writerecords/dropped` must read **0**.
  Other series: `eth/txintake/`, `eth/txvsblock/`, `eth/blocks/arrivallag/window/`,
  `eth/txpool/publish/` (the *promoted* set of a reorg cycle, not the published set),
  `eth/txpool/reset/`, `eth/txpool/basics/`, `eth/peers/role/`, `eth/peerrank/shadow/`,
  `eth/peerrank/turnover/`, `eth/peercuration/shadow/`, `eth/peerquality/shadow/`,
  `eth/txintake/margin/{unclaimed,early,earlydup}`, `eth/peercuration/{reason,held}/`,
  `eth/serve/refused/`, `bsc/serve/refused/`, `eth/pinned/{promoted,demoted}`,
  `eth/localtx/fast/insertqueue/highwater`, `p2p/refuse/{cooldown,distinctids}/`,
  `p2p/drop/remote/`, `filters/intake/watched/`, `system/cpu/schedlatency/window`,
  `system/clock/wallstepms`.
  Consumers: `adminpeers {intake records|txvsblock show|arrivals|marks|trips}`, and metricsnap,
  which drains each record family on its own cadence behind a persisted cursor.
- **Fast-finality vote toggles** — `disablepeervotebroadcastext`, `disablevoteprocessingext`,
  `disablerandomdropperext`; `admin_setPeerVoteBroadcastExt` / `...VoteProcessingExt` / `...RandomDropperExt`.
- **Feature status** — `eth_featureStatusExt` (`feature_status_ext.go`) reports all toggle states,
  plus `buildExt` (`build_info_ext.go`): the fork commit from Go's embedded `-buildvcs` info.
  The p2p node name and `geth version` are stamped with the *upstream tag* commit on purpose,
  so `web3_clientVersion` cannot detect a fork-version drift; pin checks use `buildExt.commit`.
- **Readiness** (`ready_ext.go`, `core/insert_stats_ext.go`) — `eth_readyExt` is the one
  debounced boolean a local client waits on after (re)connecting to the IPC. Gates, in the
  order they matter to the bot: `handler.synced` (until the first downloader cycle sets it the
  fetcher *discards* propagated blocks, so a node cannot follow the head — `acceptTxs` is
  weaker and wrong here), head age ≤ `ReadyMaxHeadAgeExt` (3 s; entering ready needs half),
  ≥ `ReadyMinPeersExt` (50) connected and ≥ `ReadyMinDialedPeersExt` (30) dialed, rolling import
  lag ≤ `ReadyMaxImportLagExt` (400 ms — the upper median, i.e. 4th-highest, of `imported − mined`
  over the last 8 canonical blocks; mandatory, no off switch, and fewer than 8 samples reads
  not-ready), ≥ `ReadyWarmupBlocksExt` (128) blocks executed since start (the deterministic
  warm-cache dwell), the fast-path inserter running when configured, and no operator override.
  Hysteresis lives in the monitor: ready after every gate passes for `ReadyStableForExt` (2 s),
  not ready after 2 consecutive failing ticks (500 ms grid).
  Optional floors, off at 0: `ReadyMinMgaspsExt` (rolling gas-weighted import Mgas/s) and
  `ReadyMaxArrivalLagExt` (rolling mean of block received − mined, the fork's only per-block
  arrival-lag measure); the status always reports both so a floor can be read off a warm node.
  `reasons` are stable strings. `eth_subscribe("readyChangesExt")` pushes the verdict on
  subscribe and on every flip (latest-wins, a wedged client cannot stall the monitor);
  `admin_setReadyOverrideExt("unready"|"auto")` forces not-ready (drain before a restart;
  not persisted). **EOF is the not-ready signal**: RPC servers close before `Ethereum.Stop`,
  so nothing can be published at shutdown. `eth_readyFlipsExt` returns the last 256 flips with
  their reasons, for a client that reconnected after one. Metrics `eth/ready/readyext` (0/1),
  `eth/ready/flipsext`, `eth/ready/notready/<reason>`. The evidence ring is fed by one of the import-goroutine hooks
  (`docs/specs/bot-feed-contract-v1.md` §Hot path). `adminpeers ready {show|wait|override}`.
- `common/bidutil/` — BSC MEV bid-submission deadline math (`BidBetterBefore`/`BidMustBefore`).

Fork-only ops tools (each has a `README.md` unless noted): `cmd/adminpeers` (CLI over the peer
RPCs), `cmd/feedsoak` (post-deploy soak over the bot feed contract), `cmd/pgocapture` (merged
CPU-profile capture for `make geth-prod`), `cmd/metricsnap` (the minute-metrics JSONL
history plus six daily record families — intake, arrivals, marks, trips, writes, ready flips — each
drained behind its own cursor, and the hourly pprof snapshots the `bsc-metricsnap`/`bsc-pprofsnap`
timers run, with a bounded contention window armed by `--contention-seconds`; its read resets the
`rpc/duration/*` samples),
`cmd/verifyconstrained` (runs the local gate in a
constrained transient systemd unit; no README — `-h` and the package doc are the reference),
`cmd/keeper` (stateless block re-execution as a zkVM guest), `cmd/maliciousvote-submit`
(finality-violation evidence submission), `cmd/extradump` (decode Parlia `Header.Extra`; no
README — `-h` is the reference), `cmd/pyutils/reorg_analyzer.py` (a single script, no README).
`cmd/crawler` also exists but is **unsupported** (no
planned use — see `docs/PROJECT_CONTEXT.md` rulings); don't spend effort on it.

