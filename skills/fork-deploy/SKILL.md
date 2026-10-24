---
name: fork-deploy
description: "The fork's deploy/production tree: config.toml, the geth unit, the host manifests."
---

**When to load:** Use before changing anything under deploy/production/ in the bsc-geth fork checkout, or anything that affects the node's config.toml, its systemd unit's ExecStart, the host bundle's MANIFEST, or which repo installs a path on the production host. Covers the rules for the offline gate, the two config checkers, one writer per path across the fork's and the bot's manifests, and the never-set list; the facts behind each are the fork's deploy docs.

# The fork's production deploy bundle

**The fork owns the production host.** Its bundle is `deploy/production/` in the fork tree,
documented beside it. The fork's docs index (`docs/fork/README.md`, its "Elsewhere in the tree"
list) names those documents: the reasoning behind every installed number and the things never
to do on the node, the host bundle (manifest, installer, verifier, offline tests), the two
runbooks, and the post-deploy soak with the health gate. Read the facts there: the host, the
files, the checks and their numbers change with the fork, and this skill holds only the rules.
prediction-bot keeps only bot-specific infra, in its own manifest.

## Before changing anything there

Paths are in the fork tree. In a bsc-geth root run them as written; from prediction-bot,
`bash "$BSC_FORK_PATH"/deploy/production/…`.

- **Run the offline gate** the host bundle's README names, with any fixture step it puts
  first. No CI runs on the working branch pair; this is the only evidence.
- **Keep both config checkers passing.** Anything affecting `config.toml` semantics or the
  unit's `ExecStart` must keep both of the fork's checkers green: the one that says the
  pairing is correct for this fork version and the one that says geth loads it. Neither
  implies the other. Update a checker's rules in the same change as what they gate.
- **One writer per path.** No installed path may appear in both the fork's manifest and the
  bot's. Changing the split is a paired change (the fork's manifest, the bot's manifest and
  the fork's contracted list of bot paths) in one loop (`blockchain-kit:fork-development`).
  What asserts it, offline and on the host, and the install order across the two manifests
  are the host bundle's README.
- **The never list.** The deploy README names the keys and flags never to set or re-add on
  this node, and the irreversible one; read it before any `config.toml` or `ExecStart`
  change, and the rebase landmines before re-adding anything upstream removed.
- A new `*Ext` TOML key or flag is a fork surface (`blockchain-kit:fork-ext-convention`)
  and a row in the correctness checker, in the same change.

## Runbooks

Rebuilding a wiped host and redeploying a new binary onto the running host, with
prediction-bot's side sequenced in, are the fork's two runbooks, which the index lists. Both
are numbered steps with a pass condition each: run in order, stop on a failed check. Running
either against the live host is the user's: an agent prepares and verifies offline, and never
touches the live service.
