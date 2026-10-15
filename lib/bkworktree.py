"""Where the kit keeps a harness worktree: beside the clone, never inside it.

Claude Code makes every worktree it isolates work in (a workflow lane, an agent with
isolation "worktree", `claude -w`, EnterWorktree) at <clone>/.claude/worktrees/<name>. A
session rooted at the clone then has full checkouts of its repository inside its own tree:
every tree walker that does not honour .gitignore sees each copy, bsc's `make fmt` runs
gofmt over `find . -name "*.go"`, and a lane in the fork is ~13,500 files inside the
production host's tree, two or three times over (operator, 2026-10-15: move them out).

The hooks worktree-create and worktree-remove put them at

    <parent of the main clone>/.<main clone's directory name>.worktrees/<name>

keyed on the MAIN clone (git's common dir), so a lane spawned from a `-w` session lands
beside the clone too and not inside another worktree; a dot prefix keeps the directory
out of a listing of the parent; the clone's directory name, not the repository's, keeps
two clones of one repository in one parent apart (bsc and bsc-chores). The parent must not
be inside any git repository: Claude Code refuses a worktree whose directory git resolves
to another checkout, and ~/Developer is not one.

Pure path logic plus a few read-only git queries; nothing here creates or removes.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

NAME_OK = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
BRANCH_PREFIX = "worktree-"  # the harness's own naming, which the implement workflow keys on
DEFAULT_REL = Path(".claude/worktrees")  # the harness's own location: the kill switch's


class WorktreeError(Exception):
    """A reason the hook refuses; printed on stderr."""


def git(tree: Path, *args: str, timeout: float = 60) -> str:
    done = subprocess.run(["git", "-C", str(tree), *args], capture_output=True, text=True, timeout=timeout, check=False)
    if done.returncode != 0:
        first = next((ln for ln in done.stderr.splitlines() if ln.strip()), f"exit {done.returncode}")
        raise WorktreeError(f"git {' '.join(args)}: {first.strip()}")
    return done.stdout.strip()


def real(path: os.PathLike[str] | str) -> Path:
    return Path(os.path.realpath(path))


def session_tree(cwd: Path) -> Path:
    """The top level of the checkout `cwd` is in: the tree whose HEAD a new worktree branches from."""
    return real(git(cwd, "rev-parse", "--show-toplevel"))


def main_clone(tree: Path) -> Path:
    """The main clone behind `tree`, which may itself be a linked worktree."""
    common = git(tree, "rev-parse", "--git-common-dir")
    common_path = Path(common) if os.path.isabs(common) else tree / common
    common_path = real(common_path)
    if common_path.name != ".git":
        raise WorktreeError(f"{tree} is not a working tree of an ordinary clone (git dir {common_path})")
    return common_path.parent


def inside_repository(path: Path) -> bool:
    """Whether some git repository contains `path` (an existing directory)."""
    done = subprocess.run(["git", "-C", str(path), "rev-parse", "--git-dir"], capture_output=True, text=True,
                          timeout=10, check=False)
    return done.returncode == 0


def lane_dir(main: Path) -> Path:
    return main.parent / f".{main.name}.worktrees"


def listed(main: Path) -> dict[Path, str]:
    """{realpath of each worktree of `main`: its branch ('' when detached)}, the main one included."""
    out: dict[Path, str] = {}
    path: Path | None = None
    for line in git(main, "worktree", "list", "--porcelain").splitlines() + [""]:
        if line.startswith("worktree "):
            path = real(line[len("worktree "):])
            out[path] = ""
        elif line.startswith("branch ") and path is not None:
            out[path] = line[len("branch "):].removeprefix("refs/heads/")
        elif not line:
            path = None
    return out


def check_name(name: object) -> str:
    if not isinstance(name, str) or not NAME_OK.fullmatch(name):
        raise WorktreeError(f"worktree name {name!r} is not a plain slug")
    return name


def place(main: Path, name: str, default_location: bool = False) -> Path:
    """The directory a new worktree `name` of `main` goes to, every refusal raised."""
    if default_location:
        return main / DEFAULT_REL / name
    parent = lane_dir(main)
    if not parent.parent.is_dir():
        raise WorktreeError(f"{parent.parent} is not a directory")
    if inside_repository(parent.parent):
        raise WorktreeError(f"{parent.parent} is inside a git repository: a worktree there would resolve to that "
                            f"checkout and Claude Code refuses it. Clone {main.name} under a directory that is not "
                            f"in a repository, or set BLOCKCHAIN_KIT_WORKTREES=0 for the harness's location")
    target = parent / name
    if target.exists() or target.is_symlink():
        raise WorktreeError(f"{target} already exists")
    if parent.exists():
        if not parent.is_dir() or parent.is_symlink():
            raise WorktreeError(f"{parent} exists and is not a plain directory")
        ours = listed(main)
        for entry in parent.iterdir():
            if real(entry) not in ours:
                raise WorktreeError(f"{entry} is not a worktree of {main}: remove it yourself, then retry")
    return target


def owned(main: Path, path: Path) -> str:
    """`path` is a linked worktree of `main` in one of the two places the kit puts them: returns its branch."""
    worktrees = listed(main)
    if path == main or path not in worktrees:
        raise WorktreeError(f"{path} is not a linked worktree of {main}")
    if path.parent not in (lane_dir(main), real(main / DEFAULT_REL)):
        raise WorktreeError(f"{path} is a worktree of {main} outside the kit's directories: remove it yourself")
    return worktrees[path]
