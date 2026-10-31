---
description: Review a whole repository at one commit against its own docs — the contract, the measured numbers and their soundness first, then finders by angle, then an independent check of every finding.
disable-model-invocation: true
---

# Run `blockchain-kit:project-review`

This command is the user's request to run the workflow, and no plan or approval comes first. The contract of its input and output
is the header of `workflows/project-review.js`. It reviews the session's own repository: the
seats read only, and the gate below is the one thing that runs.

1. **The tree**, one Bash call each; stop and say which failed:
   - `head` is `git rev-parse HEAD`, and `git status --porcelain --untracked-files=no` prints
     nothing: gopls reads the working tree.
   - The review guide exists: `docs/project-review.md` in prediction-bot,
     `docs/fork/project-review.md` in bsc-geth. Without one, say so and stop: every seat
     works from it. It names **Gate**, the commands that prove the tree and what a seat needs
     installed; **Sources**, the docs to read, in order; **Contract**, what the contract must
     cover; **Domain**, what the logic is judged against; **Areas**, how to choose them;
     **Invariants**, each with its surface and its rule's home; **Numbers**, what to collect
     and which units matter; **Tests**, the test rules; **Report**, where the report goes and
     its example; **Not reviewed**, what this review cannot see.
2. **The gate**, in the background, one Bash call: each of the guide's Gate commands as
   `bk-gate <name> -- <command>`, every one run whatever the one before returned, so that the
   production host's cap applies and each has its own verdict line. Record each rc.
3. **Launch** the Workflow tool with `name: "blockchain-kit:project-review"` and `args` as a
   JSON object `{project, head, guide, module}`: `guide` is the path above, and the kit's
   `implement-args` hook fills `project` and `module` when they are left out. Do not poll it.
4. **When it returns and the gate has exited**, write the report where the guide's Report says, in the shape of its
   example: the target (`head`, the areas and paths reviewed); the method (seats and tiers,
   whether gopls served them, every degraded note); the headline verdict; the gate table; the
   contract as the intent seat read it, every item with its source; the numbers table;
   findings most severe first, each with `file:line`, the contract item, why, the scenario,
   the verdict and the reason that decided it; the refuted with their reasons; merged
   duplicates; every unchecked candidate; coverage per angle; the guide's Not reviewed; seats
   spent. Leave the file uncommitted: the user decides whether it rides a PR.
5. **In chat:** the headline verdict, the gate table, then the findings, blockers and majors
   first, with what you recommend for each (fix now, issue, accept), and what the review could
   not see.
