# Landmines for the next upstream rebase

This file is a pointer; the facts live in bsc-geth, which supersedes the copy this file held.

- **The landmines** for the v1.8.0 target are bsc-geth `docs/upstream-rebase-landmines.md`:
  removed config keys fatal at startup, removed mechanisms that take fork hooks with them, and
  the re-semanticized surfaces that keep the fork's version in every conflict.
- **The full inventory** behind it is `docs/reviews/2026-10-04-rebase-v180-inventory.md`.

Each rebase consumes that doc and refills it for the next target, in bsc-geth.
