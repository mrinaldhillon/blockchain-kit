# Landmines for the next upstream rebase

This file is a pointer; the facts live in bsc-geth, which supersedes the copy this file held.

- **The landmines** for the next target are bsc-geth's rebase-landmines document, which its
  docs index (`docs/fork/README.md`) lists, with the target it was read against:
  removed config keys fatal at startup, removed mechanisms that take fork hooks with them, and
  the re-semanticized surfaces that keep the fork's version in every conflict.
- **The full inventory** behind it is in the fork's review history, which its docs index names.

Each rebase consumes that doc and refills it for the next target, in bsc-geth.
