"""forkpin — which bsc-geth commit a Go module is pinned to, and the index built from it.

Shared by bin/bsc-fork, bin/blockchain-kit-context and hooks/guard-prod-run. Stdlib
only, and no `go` subprocess on the paths the hooks use: each has a five second budget.

A consumer pins the fork with a go.mod replace:

    replace github.com/ethereum/go-ethereum => github.com/<owner>/bsc-geth v0.0.0-<ts>-<sha12>

The pseudo-version carries the commit's first twelve hex digits and its timestamp as
digits. The full hash and the canonical time are in the metadata the Go toolchain
wrote when it downloaded the pin:

    $GOMODCACHE/cache/download/<modpath>/@v/<pseudo>.info

and the pinned source is the read-only tree at $GOMODCACHE/<modpath>@<pseudo>.

The fork is developed in one of two modes. From the client's session, in a checkout
the client names with $BSC_FORK_PATH: that checkout is what gets edited, and what the
client COMPILES is still the pin, unless a go.work at the client's root `use`s the
checkout. Three trees, then, and a file:line is only true of the one it was read from.
Or from a session rooted in the fork itself (is_fork at the module root): one tree, no
pin, and nothing here about a pin applies to it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

UPSTREAM = "github.com/ethereum/go-ethereum"
INDEX_DEFAULT = "docs/fork-knowledge/symbols.json"

# golang.org/x/mod/module/pseudo.go pseudoVersionRE, with the time and the revision captured:
# v0.0.0-<time>-<rev>, vX.Y.Z-pre.0.<time>-<rev>, vX.Y.(Z+1)-0.<time>-<rev>
_PSEUDO = re.compile(r"^v[0-9]+\.(?:0\.0-|\d+\.\d+-(?:[^+]*\.)?0\.)(\d{14})-([0-9a-f]{12})"
                     r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
_REPLACE = re.compile(r"^(?:replace\s+)?(\S+)(?:\s+v\S+)?\s+=>\s+(\S+)(?:\s+(v\S+))?\s*$")


class ForkError(Exception):
    """A state the caller reports and exits 2 on: no go.mod, unreadable index."""


@dataclass(frozen=True)
class Pin:
    """The fork replace in a go.mod."""

    gomod: Path
    modpath: str  # the replace target: github.com/<owner>/bsc-geth, or a local path
    pseudo: str  # "" when the replace names a local directory
    sha12: str  # "" when the replace names a local directory, or a version that is not a pseudo-version

    @property
    def local(self) -> bool:
        return not self.pseudo


def git_root(start: Path) -> Path:
    for d in (start, *start.parents):
        if (d / ".git").exists():
            return d
    return start


def module_root(start: Path) -> Path | None:
    """The nearest directory at or above `start` that holds a go.mod, inside the git root."""
    top = git_root(start)
    for d in (start, *start.parents):
        if (d / "go.mod").is_file():
            return d
        if d == top:
            break
    return None


def _directives(text: str) -> tuple[str, list[str]]:
    """The module path and every replace line of a go.mod, block form unfolded."""
    module, replaces, in_block = "", [], False
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if in_block:
            if line == ")":
                in_block = False
            else:
                replaces.append(line)
        elif line.startswith("module "):
            module = line.split(None, 1)[1].strip().strip('"')
        elif re.match(r"^replace\s*\($", line):
            in_block = True
        elif line.startswith("replace "):
            replaces.append(line)
    return module, replaces


def read_gomod(gomod: Path) -> tuple[str, Pin | None]:
    """(module path, the fork pin or None). Raises ForkError when go.mod is unreadable."""
    try:
        module, replaces = _directives(gomod.read_text(encoding="utf-8"))
    except OSError as err:
        raise ForkError(f"cannot read {gomod}: {err.strerror}") from err
    for line in replaces:
        m = _REPLACE.match(line)
        if not m or m.group(1).strip('"') != UPSTREAM:
            continue
        target, version = m.group(2).strip('"'), m.group(3) or ""
        if not version:  # a local directory: fork co-development
            return module, Pin(gomod, target, "", "")
        p = _PSEUDO.match(version)
        return module, Pin(gomod, target, version, p.group(2) if p else "")
    return module, None


def is_client(root: Path) -> bool:
    """True when the go.mod at `root` replaces go-ethereum with a fork."""
    try:
        return read_gomod(root / "go.mod")[1] is not None
    except ForkError:
        return False


def is_fork(tree: Path) -> bool:
    """True when `tree` holds the fork itself: its module is still named go-ethereum."""
    try:
        return read_gomod(tree / "go.mod")[0] == UPSTREAM
    except ForkError:
        return False


def workspace(root: Path) -> Path | None:
    """The fork checkout a go.work at `root` uses, when workspace mode is on.

    With one, the client compiles the checkout and not the pin. $GOWORK=off turns
    workspace mode off; $GOWORK=<file> names the file.
    """
    named = os.environ.get("GOWORK", "")
    if named == "off":
        return None
    gowork = Path(named) if named else root / "go.work"
    try:
        text = gowork.read_text(encoding="utf-8")
    except OSError:
        return None
    used, in_block = [], False
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if in_block:
            if line == ")":
                in_block = False
            elif line:
                used.append(line)
        elif re.match(r"^use\s*\($", line):
            in_block = True
        elif line.startswith("use "):
            used.append(line.split(None, 1)[1])
    for entry in used:
        member = Path(entry.strip('"'))
        member = member if member.is_absolute() else (gowork.parent / member)
        if is_fork(member):
            return member.resolve()
    return None


def checkout(root: Path, pin: Pin | None = None) -> Path | None:
    """The fork checkout this client edits: go.work's, else $BSC_FORK_PATH, else a local replace."""
    used = workspace(root)
    if used is not None:
        return used
    named = os.environ.get("BSC_FORK_PATH")
    if named:
        return Path(named).expanduser().resolve()
    if pin is not None and pin.local:
        target = Path(pin.modpath)
        return target if target.is_absolute() else (pin.gomod.parent / target).resolve()
    return None


def _git(tree: Path, *args: str, timeout: float = 1.5) -> str | None:
    """A read-only git query's stdout, None when it fails or takes too long."""
    try:
        out = subprocess.run(["git", "-C", str(tree), *args], capture_output=True, text=True, check=False,
                             timeout=timeout, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def checkout_state(tree: Path, pin: Pin | None, dirty: bool = True) -> dict[str, object]:
    """Where a checkout stands against the pin.

    {'head', 'branch', 'at_pin', 'ahead', 'behind', 'dirty'}; 'ahead'/'behind' are None
    when the pinned commit is not in the checkout, 'dirty' is None when not asked for.
    {} when `tree` is not a git checkout.
    """
    seen = _git(tree, "rev-parse", "HEAD", "--abbrev-ref", "HEAD")
    if not seen or len(seen.splitlines()) != 2:
        return {}
    head, branch = seen.splitlines()
    state: dict[str, object] = {"head": head, "branch": branch, "at_pin": False, "ahead": None,
                                "behind": None, "dirty": None}
    if pin is not None and pin.sha12:
        state["at_pin"] = head.startswith(pin.sha12)
        counts = _git(tree, "rev-list", "--left-right", "--count", f"{pin.sha12}...HEAD")
        if counts and len(counts.split()) == 2:
            behind, ahead = counts.split()
            state["behind"], state["ahead"] = int(behind), int(ahead)
    if dirty:
        changed = _git(tree, "status", "--porcelain", "--untracked-files=no", timeout=4)
        state["dirty"] = None if changed is None else bool(changed)
    return state


def describe(state: dict[str, object]) -> str:
    """'mrinal/dev @ 5bed3824ce90, 3 commits past the pin, uncommitted changes'"""
    if not state:
        return "not a git checkout"
    branch = "detached" if state["branch"] == "HEAD" else state["branch"]
    parts = [f"{branch} @ {str(state['head'])[:12]}"]
    ahead, behind = state.get("ahead"), state.get("behind")
    if state.get("at_pin"):
        parts.append("at the pin")
    elif ahead is None:
        parts.append("the pinned commit is not in it (fetch)")
    else:
        if ahead:
            parts.append(f"{ahead} commit{'s' if ahead != 1 else ''} past the pin")
        if behind:
            parts.append(f"{behind} behind the pin")
    if state.get("dirty"):
        parts.append("uncommitted changes")
    return ", ".join(parts)


def _escape(modpath: str) -> str:
    """The module cache's case encoding: an upper-case letter is '!' + its lower case."""
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), modpath)


def modcache(ask_go: bool = True) -> Path | None:
    """$GOMODCACHE, else $GOPATH/pkg/mod, else what `go env` says, else ~/go/pkg/mod."""
    env = os.environ.get("GOMODCACHE")
    if env:
        return Path(env)
    gopath = os.environ.get("GOPATH")
    if gopath:
        return Path(gopath.split(os.pathsep)[0]) / "pkg" / "mod"
    if ask_go:
        try:
            out = subprocess.run(["go", "env", "GOMODCACHE"], capture_output=True, text=True, check=False,
                                 timeout=10, env={**os.environ, "GOFLAGS": ""})
            if out.returncode == 0 and out.stdout.strip():
                return Path(out.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
    default = Path.home() / "go" / "pkg" / "mod"
    return default if default.is_dir() else None


def info(pin: Pin, cache: Path | None) -> dict[str, str]:
    """{'sha': <40 hex>, 'time': <RFC 3339>} from the module cache, {} when it is cold."""
    if pin.local or cache is None:
        return {}
    meta = cache / "cache" / "download" / _escape(pin.modpath) / "@v" / f"{pin.pseudo}.info"
    try:
        d = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sha = str((d.get("Origin") or {}).get("Hash") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not sha.startswith(pin.sha12):
        return {}
    return {"sha": sha, "time": str(d.get("Time") or "")}


def pinned_dir(pin: Pin, cache: Path | None) -> Path | None:
    """The pin's own read-only tree in the module cache. None for a local replace."""
    if pin.local or cache is None:
        return None
    return cache / f"{_escape(pin.modpath)}@{pin.pseudo}"


def compiled_dir(root: Path, pin: Pin, cache: Path | None) -> tuple[Path | None, str]:
    """(the tree the client compiles, why): go.work's checkout, a local replace, else the pin."""
    used = workspace(root)
    if used is not None:
        return used, "the checkout (go.work)"
    if pin.local:
        return checkout(root, pin), "the checkout (a local replace)"
    return pinned_dir(pin, cache), "the pin (module cache)"


def index_path(root: Path, named: str | None = None) -> Path:
    """--index, else $BSC_FORK_INDEX, else docs/fork-knowledge/symbols.json at the root."""
    chosen = named or os.environ.get("BSC_FORK_INDEX")
    if chosen:
        p = Path(chosen).expanduser()
        return p if p.is_absolute() else (Path.cwd() / p)
    return root / INDEX_DEFAULT


def load_index(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except OSError as err:
        raise ForkError(f"no fork index at {path}: {err.strerror}") from err
    except ValueError as err:
        raise ForkError(f"{path} is not JSON: {err}") from err
    if not isinstance(d, dict) or not isinstance(d.get("symbols"), list):
        raise ForkError(f"{path} has no 'symbols' list: not a fork index")
    return d


def drift(pin: Pin | None, index: dict | None) -> str:
    """current | stale | local | tagged | unpinned | unindexed — the index against the pin.

    'tagged': the replace names a version that is not a pseudo-version, so it carries no
    commit to compare and neither verdict can be given.
    """
    if pin is None:
        return "unpinned"
    if pin.local:
        return "local"
    if not pin.sha12:
        return "tagged"
    if index is None:
        return "unindexed"
    recorded = str(index.get("fork_sha") or "")
    return "current" if pin.sha12 and recorded.startswith(pin.sha12) else "stale"


def _checkout_line(root: Path, pin: Pin) -> str:
    tree = checkout(root, pin)
    if tree is None:
        return ("Fork checkout: none named. To edit the fork from this session, set BSC_FORK_PATH "
                "to a bsc-geth checkout.")
    if not is_fork(tree):
        return f"Fork checkout: {tree} is not a bsc-geth tree."
    line = f"Fork checkout: {tree} ({describe(checkout_state(tree, pin, dirty=False))})."
    if workspace(root) is not None:
        return f"{line} go.work is active: this build compiles the CHECKOUT, not the pin."
    return f"{line} This build compiles the pin, not the checkout."


def summary(root: Path) -> str:
    """Two lines for a session's context: the pin and index, the checkout. Never raises,
    never runs `go`; the only subprocesses are two git queries, 1.5 s each at most."""
    try:
        _, pin = read_gomod(root / "go.mod")
    except ForkError:
        return ""
    if pin is None:
        return ""
    if pin.local:
        return (f"Fork pin: a local checkout ({pin.modpath}), so the index may not describe it.\n"
                f"{_checkout_line(root, pin)}")
    try:
        index: dict | None = load_index(index_path(root))
    except ForkError:
        index = None
    state = drift(pin, index)
    line = f"Fork pin: {pin.modpath} at {pin.sha12 or pin.pseudo}."
    if state == "tagged":
        line = f"{line} Fork index: not comparable, the pin is a version and names no commit."
    elif state == "current" and index is not None:
        line = f"{line} Fork index: current ({len(index['symbols'])} symbols)."
    elif state == "stale" and index is not None:
        recorded = str(index.get("fork_sha") or "")[:12] or "no SHA"
        line = (f"{line} Fork index: STALE, built at {recorded}. Every `verified` flag is void "
                f"until the index is regenerated at the pin.")
    else:
        line = f"{line} Fork index: none found."
    return f"{line}\n{_checkout_line(root, pin)}"
