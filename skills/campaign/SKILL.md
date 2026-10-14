---
name: campaign
description: "The fork's measurement campaign: cmd/campaign, its locks and holds, bsc-campaign.timer."
---

**When to load:** Use before running, reading or changing the bsc-geth measurement campaign — the `campaign` command (`next`, `read`, `run`, `run --all`, `ack`, `hold`/`release`, `judge`, `restamp`, `report`, `--recover`), its arm locks and ledger, the A/B items and their verdicts, the on-host command line, or the `bsc-campaign.timer` unit.

# The measurement campaign

A router: the facts live in the fork, and this skill names where. Paths are in the fork tree.

| Question | Home |
|---|---|
| The commands, the arm locks, a hold (at most 24 h), `ack`, `run <item> --recover`, exit codes, the files under `--dir` | `cmd/campaign/README.md` |
| The on-host command line (`--dir`, `--history`, `--plan` as installed) | `cmd/campaign/README.md` |
| What the timer runs, where the ledger and the plan live, and that A/B items run only by hand (`campaign run <item>`), never from the timer | `deploy/production/README.md` §Campaign |
| The units | `deploy/production/host/srv/etc/systemd/system/bsc-campaign.{timer,service}` (`blockchain-kit:fork-deploy`) |

An A/B writes to the live node: what it may write, and how it rolls back, is
`cmd/campaign/README.md` §What it writes to the node. Read it before starting one.
