---
description: Review a pull request or branch against what it was written to do — the contract and its soundness first, then finders by angle, then an independent check of every finding.
argument-hint: "[<pr#> | <base ref> | nothing for the current branch]"
disable-model-invocation: true
---

# Run `blockchain-kit:review`

Arguments: `$ARGUMENTS`

This command is the user's request to run the workflow. The contract of its input and output
is the header of `workflows/review.js`. It reviews the session's own repository, read-only:
nothing is edited, built, pushed or posted.

1. **The range**, one Bash call each; stop and say which failed:
   - **A PR number:** `gh pr view <n> --json headRefOid,baseRefName,state`. `head` is
     `headRefOid`. When `git cat-file -e <head>^{commit}` fails (a merged PR's branch is
     gone, and `git fetch origin` does not fetch pull refs), `git fetch origin pull/<n>/head`.
     `base` is `git merge-base origin/<baseRefName> <head>`. A merged PR works the same way.
   - **A base ref:** `head` is `git rev-parse HEAD`; `base` is `git merge-base <ref> HEAD`.
   - **Nothing:** `head` is `git rev-parse HEAD`; `base` is `git merge-base origin/main HEAD`
     in prediction-bot, `git merge-base origin/mrinal/dev HEAD` in bsc-geth. An empty range
     (`git diff --quiet <base> <head>` succeeds): say so and stop.
2. **The tree is at `head`.** `git rev-parse HEAD` equals `head`, and
   `git status --porcelain --untracked-files=no` prints nothing: gopls reads the working tree.
   If the tree is elsewhere, do not move it: tell the user the command that would
   (`git switch --detach <head>`, or `gh pr checkout <n>`) and stop, or, if they say to go on,
   launch anyway and say the seats read through `git show` without gopls.
3. **The contract.** With a PR, its body and the issues and ADRs it names are the contract;
   the intent seat reads them itself. Without one, pass the brief or the plan text the
   change was written against as `contract` when the conversation holds it. With neither,
   the intent seat works the contract out from the diff and the findings say so.
4. **Launch** the Workflow tool with `name: "blockchain-kit:review"` and `args` as a JSON
   object `{base, head, pr?, contract?, project, module}`. `project` is the absolute project
   root (`git rev-parse --show-toplevel`), `module` the `module` line of its `go.mod`; the
   kit's `implement-args` hook fills both when they are left out, and `module` picks the
   angles (the bot's four reserved angles, or the fork's Ext convention and landmines). The
   run is in the background: do not poll it.
5. **When it returns**, show the user, in this order:
   - the contract as the intent seat read it (`contract.items`, and `contract.derived` when
     no source stated one): a misread intent is the first thing to correct;
   - `findings`, most severe first, each with `file:line`, the contract item, the scenario
     and the verdict (`CONFIRMED` or `PLAUSIBLE`) with the reason that decided it;
   - a count of `refuted` (the titles on request), every `unchecked` candidate, every
     `coverage` entry with a `degraded` note, and `seats` (the cost of the run).

   Fix, defer to an issue, or accept each finding, and say which; that is the user's call or
   the session's under `blockchain-kit:working-here`. Nothing here replaces a gate.
