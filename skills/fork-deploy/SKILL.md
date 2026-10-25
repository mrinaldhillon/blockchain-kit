---
name: fork-deploy
description: "The production host bundle, in the infra repo: the node's config.toml, the geth and bot units, the one MANIFEST, the runbooks."
---

**When to load:** Use before changing anything in the infra repo (`mrinaldhillon/infra`), or anything that affects the node's `config.toml`, a geth unit's `ExecStart`, a unit or row installed on the production host, or a fork TOML key or flag. Covers the rules for the offline gate, the two config checkers, the one MANIFEST, the paired fork and infra change, and the never-set list; the facts behind each are the infra repo's docs.

# The production host bundle

**The infra repo owns the production host.** Every installed row on it (geth's unit and
`config.toml`, the slices, sysctl, NIC steering, and prediction-bot's bot, collector and ETL
units) is one `host/MANIFEST`, with one installer and a read-only verifier. It builds nothing:
the node binary and the fork's tools are built in bsc-geth, the bot and collectors in
prediction-bot. Its `README.md` is the reasoning behind every installed number and the keys and
flags never to set; `host/README.md` is the bundle (manifest, installer, verifier, offline
tests); `runbooks/` holds the rebuild, the redeploy and the post-deploy health check. The fork's
docs index and prediction-bot's operations document point there, and the latter names the
clone's default path. Read the facts there: this skill holds only the rules.

## Before changing anything there

Paths are in the infra clone. From a bsc-geth or prediction-bot session every command names
that tree (`bash <infra>/host/tests/run.sh`, `git -C <infra> …`), never a `cd`; a read or edit
there that is refused is added by the user (`/add-dir`).

- **Run the offline gate**, `host/tests/run.sh`, which runs the tools' suites too. No CI runs
  in the infra repo; this is the only evidence.
- **Keep both config checkers passing.** Anything affecting `config.toml` semantics or a geth
  unit's `ExecStart` keeps both green: `tools/check-config-ext.sh` (the pairing is correct for
  this fork version) and `host/geth-preflight.sh` (geth loads it and accepts every flag).
  Neither implies the other. Update a checker's rules in the same change as what they gate.
- **One MANIFEST.** A path on the host is installed only by its row there, and nothing under
  `host/srv/` is unmanaged; the offline install test and the verifier assert it. A change to
  what is installed is one change in the infra repo.
- **A fork TOML key or flag is a paired change**: the surface in bsc-geth
  (`blockchain-kit:fork-ext-convention`), and in the infra repo the `config.toml` or `ExecStart`
  that sets it and its row in the correctness checker. Two repositories, two commits, the
  fork's first; the infra commit names the fork commit.
- **The never list.** The infra README names the keys and flags never to set or re-add on this
  node, and the irreversible one; read it before any `config.toml` or `ExecStart` change, and
  the fork's rebase landmines before re-adding anything upstream removed.

## Runbooks

Rebuilding a wiped host and redeploying onto the running host, with prediction-bot's side
sequenced in, are the infra repo's runbooks, with the post-deploy health check beside them.
Both are numbered steps with a pass condition each: run in order, stop on a failed check.
Running either against the live host is the user's: an agent prepares and verifies offline,
and never touches the live service.
