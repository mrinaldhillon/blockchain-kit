"""Tests for hooks/worktree-create and hooks/worktree-remove: harness worktrees beside the clone.

Real git repositories in a temp directory: a clone, a second clone of the same name in
another parent, a clone inside a repository. The hooks are driven as subprocesses with a
WorktreeCreate or WorktreeRemove payload on stdin. That Claude Code calls them for a
workflow lane, and enters the path they print, is a live run (kit #21).

Run: tests/run   (or: python3 -m unittest discover -s tests)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "lib"))
import bkworktree  # noqa: E402

CREATE = KIT / "hooks" / "worktree-create"
REMOVE = KIT / "hooks" / "worktree-remove"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def git(tree: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(tree), *args], capture_output=True, text=True, check=True,
                          env={**os.environ, **GIT_ENV}).stdout.strip()


class Worktrees(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        self.clone = self.repo(self.tmp / "work/bot")

    def repo(self, path: Path) -> Path:
        path.mkdir(parents=True)
        git(path, "init", "-q", "-b", "main")
        (path / "a.txt").write_text("a\n")
        git(path, "add", "a.txt")
        git(path, "commit", "-q", "-m", "one")
        return path

    def env(self, **more: str) -> dict[str, str]:
        full = {k: v for k, v in os.environ.items() if not k.startswith(("BLOCKCHAIN_KIT_", "CLAUDE_"))}
        full.update(GIT_ENV)
        full.update(more)
        return full

    def run_hook(self, hook: Path, body: object, cwd: Path | None = None, **env: str) -> tuple[int, str, str]:
        stdin = body if isinstance(body, str) else json.dumps(body)
        done = subprocess.run([str(hook)], input=stdin, capture_output=True, text=True, env=self.env(**env),
                              cwd=cwd or self.tmp, timeout=60, check=False)
        return done.returncode, done.stdout, done.stderr

    def create(self, name: str, cwd: Path | None = None, **env: str) -> tuple[int, str, str]:
        payload = {"hook_event_name": "WorktreeCreate", "name": name, "cwd": str(cwd or self.clone), "session_id": "s"}
        return self.run_hook(CREATE, payload, **env)

    def remove(self, path: Path | str) -> tuple[int, str, str]:
        return self.run_hook(REMOVE, {"hook_event_name": "WorktreeRemove", "worktree_path": str(path)})

    def worktrees(self, clone: Path) -> dict[str, str]:
        out, path = {}, None
        for line in git(clone, "worktree", "list", "--porcelain").splitlines():
            if line.startswith("worktree "):
                path = line.split(" ", 1)[1]
                out[path] = ""
            elif line.startswith("branch ") and path:
                out[path] = line.split(" ", 1)[1].removeprefix("refs/heads/")
        return out

    # create

    def test_a_lane_is_made_beside_the_clone_on_its_own_branch_at_head(self):
        git(self.clone, "checkout", "-q", "-b", "feat/x")
        (self.clone / "b.txt").write_text("b\n")
        git(self.clone, "add", "b.txt")
        git(self.clone, "commit", "-q", "-m", "two")  # not on main: the lane must start here, not at main
        head = git(self.clone, "rev-parse", "HEAD")
        rc, out, err = self.create("wf_run-1")
        self.assertEqual(rc, 0, err)
        target = self.tmp / "work/.bot.worktrees/wf_run-1"
        self.assertEqual(out, f"{target}\n")  # the path is the whole of stdout
        self.assertEqual(self.worktrees(self.clone)[str(target)], "worktree-wf_run-1")
        self.assertEqual(git(target, "rev-parse", "HEAD"), head)
        self.assertEqual(git(target, "branch", "--show-current"), "worktree-wf_run-1")
        self.assertTrue((target / "b.txt").is_file())
        self.assertFalse((self.clone / ".claude").exists())  # nothing inside the clone
        # a second lane sits beside the first; from a subdirectory cwd too
        rc, out, _ = self.create("wf_run-2", cwd=self.clone)
        self.assertEqual((rc, out), (0, f"{self.tmp}/work/.bot.worktrees/wf_run-2\n"))
        self.assertEqual(sorted(p.name for p in (self.tmp / "work/.bot.worktrees").iterdir()), ["wf_run-1", "wf_run-2"])

    def test_a_lane_spawned_from_a_worktree_lands_beside_the_main_clone(self):
        rc, out, err = self.create("bold-oak-a3f2")  # a `claude -w` session's worktree
        self.assertEqual(rc, 0, err)
        session = Path(out.strip())
        (session / "c.txt").write_text("c\n")
        git(session, "add", "c.txt")
        git(session, "commit", "-q", "-m", "in the -w session")
        rc, out, err = self.create("wf_run-1", cwd=session)  # cwd is the -w worktree
        self.assertEqual(rc, 0, err)
        lane = Path(out.strip())
        self.assertEqual(lane, self.tmp / "work/.bot.worktrees/wf_run-1")  # not nested in the -w worktree
        self.assertEqual(git(lane, "rev-parse", "HEAD"), git(session, "rev-parse", "HEAD"))  # that tree's HEAD

    def test_two_clones_of_one_repository_in_one_parent_stay_apart(self):
        other = self.repo(self.tmp / "work/bot-chores")
        self.assertEqual(self.create("wf_run-1")[1], f"{self.tmp}/work/.bot.worktrees/wf_run-1\n")
        self.assertEqual(self.create("wf_run-1", cwd=other)[1], f"{self.tmp}/work/.bot-chores.worktrees/wf_run-1\n")

    def test_the_kill_switch_uses_the_harness_location(self):
        rc, out, err = self.create("wf_run-1", BLOCKCHAIN_KIT_WORKTREES="0")
        self.assertEqual((rc, out), (0, f"{self.clone}/.claude/worktrees/wf_run-1\n"), err)
        self.assertEqual(self.worktrees(self.clone)[f"{self.clone}/.claude/worktrees/wf_run-1"], "worktree-wf_run-1")

    def test_it_refuses_with_a_reason_and_no_path(self):
        cases = {
            "a name with a slash": self.create("../x"),
            "an empty name": self.create(""),
            "not a checkout": self.create("wf_run-1", cwd=self.tmp),
            "not json": self.run_hook(CREATE, "not json"),
            "not an object": self.run_hook(CREATE, "[1]"),
        }
        inner = self.repo(self.tmp / "outer")  # a clone whose parent is inside a repository
        nested = self.repo(inner / "nested")
        cases["a parent inside a repository"] = self.create("wf_run-1", cwd=nested)
        (self.tmp / "work/.bot.worktrees").mkdir()
        (self.tmp / "work/.bot.worktrees/stray").mkdir()
        cases["a stray entry in the worktrees directory"] = self.create("wf_run-1")
        (self.tmp / "work/.bot.worktrees/stray").rmdir()
        (self.tmp / "work/.bot.worktrees/wf_run-1").mkdir()
        cases["a target that exists"] = self.create("wf_run-1")
        for what, (rc, out, err) in cases.items():
            with self.subTest(case=what):
                self.assertEqual((rc, out), (2, ""), what)
                self.assertIn("worktree-create: refused: ", err, what)
        self.assertIn("inside a git repository", cases["a parent inside a repository"][2])
        self.assertIn("is not a worktree of", cases["a stray entry in the worktrees directory"][2])
        self.assertIn("already exists", cases["a target that exists"][2])
        self.assertEqual(len(self.worktrees(self.clone)), 1)  # nothing was added
        self.assertEqual(len(self.worktrees(nested)), 1)

    # remove

    def test_a_sibling_lane_mid_creation_is_not_a_stray(self):
        # git worktree add makes the directory before it is listed: the re-list after the pause must take it
        sibling = self.tmp / "work/.bot.worktrees/wf_run-1"
        sibling.mkdir(parents=True)
        real_listed, lists = bkworktree.listed, []

        def listed(main: Path) -> dict:
            lists.append(main)
            if len(lists) == 2:
                git(self.clone, "worktree", "add", "-q", "-b", "worktree-wf_run-1", str(sibling))
            return real_listed(main)

        with mock.patch.object(bkworktree, "listed", listed):
            target = bkworktree.place(self.clone, "wf_run-2")
        self.assertEqual(len(lists), 2)
        self.assertEqual(target, sibling.parent / "wf_run-2")

    def test_remove_takes_a_lane_and_its_merged_branch(self):
        lane = Path(self.create("wf_run-1")[1].strip())
        rc, out, err = self.remove(lane)
        self.assertEqual((rc, out), (0, ""), err)
        self.assertFalse(lane.exists())
        self.assertEqual(list(self.worktrees(self.clone)), [str(self.clone)])
        self.assertNotIn("worktree-wf_run-1", git(self.clone, "branch", "--list", "worktree-*"))
        # the kill switch's location is accepted too
        lane = Path(self.create("wf_run-2", BLOCKCHAIN_KIT_WORKTREES="0")[1].strip())
        self.assertEqual(self.remove(lane)[0], 0)
        self.assertFalse(lane.exists())

    def test_remove_keeps_an_unmerged_branch_and_says_so(self):
        lane = Path(self.create("wf_run-1")[1].strip())
        (lane / "d.txt").write_text("d\n")
        git(lane, "add", "d.txt")
        git(lane, "commit", "-q", "-m", "lane work")
        rc, out, err = self.remove(lane)
        self.assertEqual((rc, out), (0, ""))
        self.assertFalse(lane.exists())
        self.assertIn("branch worktree-wf_run-1 kept", err)
        self.assertIn("worktree-wf_run-1", git(self.clone, "branch", "--list", "worktree-*"))

    def test_remove_refuses_uncommitted_work_and_anything_not_ours(self):
        lane = Path(self.create("wf_run-1")[1].strip())
        (lane / "a.txt").write_text("changed\n")
        rc, out, err = self.remove(lane)
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("refused", err)
        self.assertTrue(lane.is_dir())  # kept
        # a worktree the kit did not place
        elsewhere = self.tmp / "elsewhere"
        git(self.clone, "worktree", "add", "-q", "-b", "hand", str(elsewhere))
        rc, _, err = self.remove(elsewhere)
        self.assertEqual(rc, 2)
        self.assertIn("outside the kit's directories", err)
        self.assertTrue(elsewhere.is_dir())
        # the main clone, a plain directory, a missing path, a bad payload
        for what, body in (("the main clone", self.clone), ("a plain directory", self.tmp / "work"),
                           ("a missing path", self.tmp / "nowhere")):
            with self.subTest(case=what):
                rc, out, err = self.remove(body)
                self.assertEqual((rc, out), (2, ""), what)
                self.assertIn("refused", err)
        self.assertEqual(self.run_hook(REMOVE, "not json")[0], 2)
        self.assertEqual(self.run_hook(REMOVE, {"hook_event_name": "WorktreeRemove"})[0], 2)
        self.assertTrue((self.clone / "a.txt").is_file())


if __name__ == "__main__":
    unittest.main()
