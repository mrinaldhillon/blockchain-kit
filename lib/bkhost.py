"""bkhost — whether this host is the production host: the one a recorder log lives on.

Shared by bin/blockchain-kit-context (the Host line) and hooks/guard-prod-run (which is
inert anywhere else). Stdlib only; no subprocess, no connection.

The test is the geth IPC socket: the production host runs the node, a dev box does not.
The path is $BLOCKCHAIN_KIT_IPC when set and non-empty, else /run/geth/geth.ipc. Only a
socket counts: a regular file, a directory or an absent path is a dev host. The probe is
a stat, never a dial, so a node that is down but left its socket is still the prod host.

    ipc_path()  -> str   the path probed
    prod_host() -> bool  True when that path is a unix socket; False on any OSError
"""

from __future__ import annotations

import os
import stat

DEFAULT_IPC = "/run/geth/geth.ipc"


def ipc_path() -> str:
    """$BLOCKCHAIN_KIT_IPC, else the default geth IPC path."""
    return os.environ.get("BLOCKCHAIN_KIT_IPC") or DEFAULT_IPC


def prod_host() -> bool:
    """True when the geth IPC path is a unix socket."""
    try:
        return stat.S_ISSOCK(os.stat(ipc_path()).st_mode)
    except OSError:
        return False
