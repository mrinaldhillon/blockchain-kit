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

A router: the facts live in prediction-bot, and this skill names where. Paths are in the pb
tree; a value is read there, in the tree you are changing, never from memory or from here.

**Where the facts live**

| Before you | Read |
|---|---|
| Read any round data: the seal start, what it forbids, the guard functions, the forward seal of a stream first recorded after it | `docs/project-context.md` (the `HOLDOUT_SEAL_START` bullet; `research/test_seal.py` holds it equal to the code); `research/pb_research/seal.py` module docstring; registry README §7 |
| Write or run a query script: the seal guard every script calls, or the exact infra-read comment it carries instead | registry README §10; `research/test_seal.py` (the string and the test that enforces it) |
| Pick a Parquet root: the live tree, the development snapshot, how the snapshot gains days | `research/README.md` §Layout |
| Pick a tables root: the nightly's unsealed and sealed roots, the grid root at the production cut | `research/README.md` §`pb_research.tables`; registry README §7 |
| Open a holdout, choose or amend D, declare a primary, read the calendar | registry README §7 (the D formula, the one command, its pre-read checks, the openings); ADR 0151 |
| Name or compare a decision cut: the cut is a production fact, never a research parameter; a result on the stand-in cut or the keep-received pool is `skewed` | ADR 0120; registry README §7 (the entry that varies a production fact) and §9; `docs/project-context.md` §Current state |
| Choose or cite a pool rule: the names, their meanings, the default, how an entry registers one, how a read scores another | `research/pb_research/features/_poolcut.py` (`POOL_RULES` and the comment on each); ADR 0150; registry README §7 (`--pool-rule`) |
| Write or change an entry: files and ids, the format, the verdict ladder, the Stage-2 screen, windows, evidence classes, the per-entry test minimum | registry README §1–§6, §9, §10; `research/registry/check_registry.py` docstring |
| Run the gates: none runs in CI; the by-hand list, the capped pytest run, `check_registry` after a registry edit | `research/README.md` §Linting / type-checking; `docs/operations.md` §11 |
| Report a number: the committed script and its output, MEASURED or INFERRED in the sentence, a stand-in says what it misses, undecoded fields are a listed gap | `docs/discipline.md` rules 49–51; pb `CLAUDE.md` §Standard of evidence; `research/queries/decode_inventory.py` |
| Touch the nightly: what it runs, the seal decision, the unit, its state layout | `research/README.md` §The operator digest and the nightly unit |

**What only this skill says**
- The nightly unit runs the main checkout, so the main checkout stays clean on `main`; branch work is in a worktree the harness makes (`claude -w`, EnterWorktree, an agent with isolation `worktree`), placed beside the clone; never a hand `git worktree add` under `.claude/worktrees/`, never `cd` into the main checkout from a worktree, never a bare `git stash`.
- Python that reads data runs with `-I`. From a worktree, read `research/README.md` §Setup (From a worktree) before the first `python3 -I -m pb_research…`: the import resolves to the main checkout unless you run the module by its path. Long runs go through `dev-setup/ci/unit_run.py` or `scripts/replay-run.sh`; never wait with `sleep`.
- A sealed day is read only through the registered holdout path, or as an infra read with the exact comment registry README §10 names; nothing else.
- A segment, a decision or a redeploy: `blockchain-kit:round-forensics`.
