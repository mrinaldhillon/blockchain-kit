---
name: research-surface
description: "prediction-bot's research/ tree: the seal, the Parquet roots, openings, pool rules, the registry, its gates and evidence."
---

**When to load:** any work under `research/` (a query, an entry, a screen, a holdout read, the seal, the registry, the nightly).

# The research surface

**Load when**
- Writing or running a `research/queries/*.py` script, a `research/pb_research` module, a rule or a feature module.
- Opening, screening, amending or superseding a registry entry; choosing or reading a holdout date D.
- Touching the seal, a Parquet root, the derived tables, a pool rule, or the nightly unit.

Facts below are pointers into prediction-bot at `main` (READ 2026-10-19). The file governs; a value quoted here is "as of 2026-10-19" and is re-read before it is used.

**The seal and the roots**

| Fact | Where |
|---|---|
| `HOLDOUT_SEAL_START` (2026-10-16 as of 2026-10-19): no exploration, fit or feature search reads a round's price, pool, bet or outcome on or after it | `research/pb_research/seal.py:94`; declared again in `docs/project-context.md`, held equal by `research/test_seal.py` `test_seal_matches_project_context` |
| The guard: `refuse_sealed(days, what, table)` before the first read, `refuse_sealed_result(text, what)` for a committed result's `- windows:` line, `partition_days(dir)` (days from `date=` names, nothing opened), `SealRefused` (a `SystemExit`, exit 1) | `research/pb_research/seal.py:378-428` |
| Every `research/queries/*.py` imports `pb_research.seal` and calls the guard, or carries exactly `# infra read: no price, pool, bet or outcome field; no seal guard needed` | `research/test_seal.py:27` (the string), `:73` `test_every_query_script_reads_through_the_seal_or_says_infra`; registry README §10 |
| A stream first recorded on or after the seal gets its own forward seal (day 0, window 0..20, seal from day 21) | ADR 0146; `seal.py` `STREAM_SEALS`, `forward_seal`, `seal_for`; registry README §7 |
| `PB_PARQUET_ROOT` picks the Parquet root; default `/data/parquet`, the live ETL tree (`etl.timer`, 02:00 UTC plus a randomized delay; sealed UTC days only) | `research/pb_research/parquet.py:23-29`; `deploy/host/srv/etc/systemd/system/etl.timer` |
| `/data/parquet-dev`: reflink copies of the pre-seal partitions only, readable without restriction; days are added when the seal moves after an opening | `scripts/dev-snapshot.sh` (prediction-bot#1129, on `main` since 2026-10-19) and its `research/README.md` paragraph; `docs/reports/2026-10-19-hardening/dev_snapshot.txt` |
| Derived tables: `/var/lib/pb-research/tables` (the nightly's unsealed root) and `/var/lib/pb-research/tables-sealed` (the openings' root) | registry README §7 (the research-path read); `seal.tables_sealed_root()` |

**Openings and the calendar rule**

| Fact | Where |
|---|---|
| The holdout opens once per promotion decision, only from `screened`; the opened entry is frozen at the bytes the read hashed; the result is a hand-written superseding entry (`promoted` or `rejected`) | registry README §7; ADR 0132 Decision 3; ADR 0140 (the research-path read) |
| One primary entry per opening; other entries read in the same opening are diagnostics; afterwards the seal moves to the opening date by a dated entry | registry README §7; prediction-bot#1118 §Research calendar |
| D = seal start + ⌈400 / expected bets per sealed day⌉, the rate measured on unsealed days only, written as the bullet `- **D = YYYY-MM-DD.**` in `## Test` | `research/registry/r025-tape-thin-side.md` `## Test` (:183-192, the worked case); `seal.READ_DATE_RE` |
| A D amendment dated before any opening is legitimate; after one it is not | prediction-bot#1118 §Research calendar |
| The read is one command (`python3 -m pb_research.screen --holdout-read rNNN --date <D>` with both tables roots) after the nightly's slot on D, with pre-read checks on partitions, builder blobs and the pool rule | registry README §7 (the command and the checklist); `screen.run_holdout`; `seal.holdout_read` |
| The calendar (ADR 0151, prediction-bot#1118 §Research calendar): opening 1 on 2026-10-31 is the research close (span 10-16..10-30; the primary is declared on 2026-10-29 by `research/registry/primary_for_opening.py <D>`, the best W2 lower 95 % bound of per-bet profit among screened entries on the trading process's pool rule; an entry opts out with the `- **Primary-eligible:** no` bullet in `## Holdout`); opening 2 on 2026-11-14 is the production gate (the promoted entry's shadow profit on 10-31..11-13 above zero) and the second wave's read (r026/r027/r028), fallback primary declared 11-12; production switch by about 2026-11-18. As of 2026-10-19 `primary_for_opening.py 2026-10-31` prints none eligible (r029, r030, r032 rejected; r031 screened but opens no holdout: the cut is a production fact, not a research parameter) | `docs/decisions/0151-*.md`; `research/registry/primary_for_opening.txt`; registry README §7 |

**The cut** (operator ruling 2026-10-19: a production fact, never a research parameter)

| Fact | Where |
|---|---|
| The decision cut is 150 ms before the header timestamp of the last canonical block whose timestamp precedes the round's lock (L); its lead over the lock varies per round, p10/p50/p90 200/450/600 ms | ADR 0120; `research/queries/grid_cut.txt` §1 |
| The research default from 2026-10-19 is that cut, `CUT_RULE_GRID = "grid_L_minus_150ms"`, built as the root `/var/lib/pb-research/tables-grid` (114 pre-seal days, rounds/bets/wallets linked to the nightly root); lock − 400 ms (`DEFAULT_CUT_LEAD_MS`) is the legacy stand-in kept only for r023's and r025's registered reads | `research/pb_research/tables/common.py`; `research/queries/grid_cut.py` (`cuts`, `report`, `sealed-grid` stages) |
| Every result produced on the stand-in or on `POOLCUT_KEEP_RECEIVED` is `skewed`: 24 of 24 tested results as of 2026-10-19; no strategy is built on one | `research/queries/inherited_inputs_audit.txt`; `research/notes/2026-10-19-inherited-inputs-audit.md`; registry README §9 |
| No cut comparison of any kind is in scope | the ruling; r031's `## Holdout` |

**Pool rules** (`research/pb_research/features/_poolcut.py:301-320`)

| Name | Meaning |
|---|---|
| `POOLCUT_KEEP_RECEIVED` | the pending leg without the bot's evictions; every result through 2026-10-17; r025 and r023 pin it |
| `POOLCUT_EXPIRE_RECEIVED` | the bot's `ExpireReceived` over the pending leg |
| `POOLCUT_EXPIRE_REVERTED_BY_CUT` | that plus the drop of entries reverted in a block imported by the cut: a diagnostic (#1052) |
| `POOLCUT_EVICT_INCLUDED` | the bot's block-fold eviction (`internal/state/pool.go` `ExpireReceived`, `EvictIncluded`; derivation/v9; ADR 0150); `DEFAULT_POOL_RULE` since 2026-10-19; r029 and r030 name it |

- An entry registers its rule as `POOL_RULE` in its rule module, else the module default (`pb_research.screen.entry_pool_rule`, `screen.py:1313`). A holdout read scores the registered rule first; `--pool-rule NAME` (repeatable, `--holdout-read` only) scores another inside the same opening as a diagnostic file `<id>-holdout-<arm>-<rule>-<date>.txt` (`screen.py:2819-2829`; registry README §7).
- A new entry screens on the bot's pool; a frozen read never relies on the default: it names its rule.

**The registry** (`research/registry/`)

| Fact | Where |
|---|---|
| Files and ids; the entry format; `TEMPLATE.md` | README §1, §2 |
| Verdict ladder (`untested`, `screened`, `promoted`, `rejected`) | README §3 |
| The standard Stage-2 screen; the dependency list (rule 49) | README §4, §5 |
| Windows: the archive, the contaminated weeks, the clean stretches | README §6 |
| The seal, the hash binding, openings, the holdout command | README §7 |
| Evidence classes; the per-entry test minimum (rule 47) | README §9, §10 |
| An entry names its rule module `research/pb_research/rules/rNNN.py` and its feature module `research/pb_research/features/rNNN.py`; results go under `research/registry/results/` | README §1, §2; `ls` the two packages |
| `check_registry.py` validates every entry and regenerates `STATUS.txt`; 0 defects is the bar, exit 1 on any | `research/registry/check_registry.py` docstring |
| A "Paths considered" block in every measurement and entry | `docs/discipline.md` §51 |

**Gates** (a research PR has no review seat; the research pytest suite never joins CI, operator 2026-10-19)

```sh
# from research/, with its venv
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy                      # NO path: the [tool.mypy] files scope; `mypy .` sweeps one-off scripts
# from the repo root
dev-setup/ci/unit_run.py --name <slug> --mem 16G -- research/.venv/bin/pytest research/tests research/test_seal.py
dev-setup/ci/unit_run.py --wait <slug>          # foreground Bash, timeout 1800000
python3 dev-setup/layering_lint.py --check-citations && make citation-lint
research/.venv/bin/python3 -I research/registry/check_registry.py > research/registry/STATUS.txt   # registry edits
```

Sources: `research/README.md` §Linting / type-checking; `research/pyproject.toml` `[tool.mypy]`, `[tool.pytest.ini_options]`; `dev-setup/ci/unit_run.py` docstring (`--same-dir`); `docs/operations.md` §11.

**Evidence**

| Rule | Where |
|---|---|
| Every reported number comes from a committed script and its output: `research/queries/<x>.py` beside `<x>.txt`, or `docs/reports/<date>-<topic>/` with a row in that directory's own `README.md` table | `docs/discipline.md` §49, §50; model: `docs/reports/2026-10-19-four-unit-redeploy-records/README.md` |
| Each claim says MEASURED (where) or INFERRED (from what) in its own sentence | prediction-bot `CLAUDE.md` §Standard of evidence |
| A direct recorded field beats a stand-in; a stand-in says what it misses | `docs/discipline.md` §51; `blockchain-kit:working-here` §Evidence |
| Undecoded recorded fields are a listed gap, never an unknown | `research/queries/decode_inventory.py` and `.txt` |

**What only this skill says**
- The nightly (`research/nightly.py`, `pb-research-nightly.timer` 03:00 UTC) runs from the main checkout: keep it clean on `main`, do all branch work in a worktree the harness makes (`claude -w`, EnterWorktree, an agent with isolation `worktree`), which the kit places beside the clone; never a hand `git worktree add` under `.claude/worktrees/`, never `cd` into the main checkout from a worktree, never a bare `git stash`.
- Python that reads data runs with `-I`. From a worktree, `python3 -I -m pb_research…` imports the MAIN checkout's package through the shared venv's editable finder (`PYTHONPATH` is ignored under `-I`), so a table root built that way is stamped with main's builder blobs: run the worktree's module path explicitly and check the blobs in `_meta.json` (lane G, 2026-10-19). Long runs go through `dev-setup/ci/unit_run.py` or `scripts/replay-run.sh`; never wait with `sleep`.
- An infra read on a sealed day (kinds, stream names, StreamSeq, wall times, record counts, column names) is allowed and says so with the exact comment; anything else on a sealed day goes through the registered holdout path or not at all.
- A segment, a decision or a redeploy: `blockchain-kit:round-forensics`.
