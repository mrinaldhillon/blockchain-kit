"""Tests for bin/bk-team: init (links, CLAUDE.md, settings, the project install through
blockchain-kit-setup) and start (one tmux window per clone, then the lead).

A fake `claude` records its argv (test_setup's), a fake `tmux` records its argv, a fake `go`
keeps setup's toolchain rows quiet. What a real tmux or a real session does is a live probe.

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

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_setup import FAKE_CLAUDE, FAKE_GO, PLUGIN  # noqa: E402

KIT = Path(__file__).resolve().parent.parent
TEAM = KIT / "bin" / "bk-team"
WHO = ("-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false")

FAKE_TMUX = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_TMUX_LOG"
"""


class Team(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        self.bin = self.tmp / "bin"
        for d in (self.bin, self.tmp / "home", self.tmp / "data", self.tmp / "config", self.tmp / "clones"):
            d.mkdir(parents=True)
        for name, body in (("claude", FAKE_CLAUDE.format(python=sys.executable, plugin=PLUGIN)), ("go", FAKE_GO),
                           ("tmux", FAKE_TMUX)):
            (self.bin / name).write_text(body)
            (self.bin / name).chmod(0o755)
        self.claude_log, self.tmux_log = self.tmp / "claude.log", self.tmp / "tmux.log"
        for clone in ("prediction-bot", "bsc-geth"):
            path = self.tmp / "clones" / clone
            path.mkdir()
            subprocess.run(["git", "-C", str(path), *WHO, "init", "--quiet"], check=True, env=self.env())

    def env(self, **more: str) -> dict[str, str]:
        drop = ("BLOCKCHAIN_KIT_", "CLAUDE_", "BSC_FORK_", "GIT_", "XDG_", "GO", "BK_TEAM_")
        full = {k: v for k, v in os.environ.items() if not k.startswith(drop)}
        full.update(PATH=f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", HOME=str(self.tmp / "home"),
                    CLAUDE_CONFIG_DIR=str(self.tmp / "config"), XDG_DATA_HOME=str(self.tmp / "data"),
                    TMPDIR=str(self.tmp), FAKE_CLAUDE_LOG=str(self.claude_log), FAKE_TMUX_LOG=str(self.tmux_log),
                    FAKE_VERSION="aaaaaaaaaaaa", GIT_CEILING_DIRECTORIES=str(self.tmp), GIT_CONFIG_GLOBAL=os.devnull,
                    GIT_CONFIG_NOSYSTEM="1")
        full.update(more)
        return full

    def team(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(TEAM), *args], capture_output=True, text=True, env=self.env(),
                              cwd=cwd or self.tmp, timeout=60, check=False)

    def claude_calls(self) -> list[dict]:
        return [json.loads(line) for line in self.claude_log.read_text().splitlines()] if self.claude_log.exists() else []

    def test_init_links_the_clones_and_writes_the_leads_files_and_install(self):
        lead = self.tmp / "team"
        done = self.team("init", str(lead), str(self.tmp / "clones/prediction-bot"), str(self.tmp / "clones/bsc-geth"))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(os.readlink(lead / "prediction-bot"), str(self.tmp / "clones/prediction-bot"))
        self.assertEqual(os.readlink(lead / "bsc-geth"), str(self.tmp / "clones/bsc-geth"))
        text = (lead / "CLAUDE.md").read_text()
        self.assertIn("# team: the lead's directory", text)
        self.assertIn("`prediction-bot` (worker session `prediction-bot-worker`)", text)
        self.assertIn("`bsc-geth` (worker session `bsc-geth-worker`)", text)
        self.assertIn("executes nothing", text)
        self.assertIn("`## Units` and `## Not implement` sections", text)
        settings = json.loads((lead / ".claude/settings.json").read_text())
        self.assertEqual(settings["enabledPlugins"], {PLUGIN: True})
        installs = [c for c in self.claude_calls() if c["argv"][:2] == ["plugin", "install"]]
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0]["argv"][2:], [PLUGIN, "--scope", "project"])
        self.assertEqual(os.path.realpath(installs[0]["cwd"]), str(lead))
        # idempotent
        again = self.team("init", str(lead), str(self.tmp / "clones/prediction-bot"))
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)

    def test_init_takes_a_clone_checked_out_under_the_directory_as_it_is(self):
        lead = self.tmp / "team"
        inside = lead / "bsc-geth"
        inside.mkdir(parents=True)
        subprocess.run(["git", "-C", str(inside), *WHO, "init", "--quiet"], check=True, env=self.env())
        done = self.team("init", str(lead), str(inside), str(self.tmp / "clones/prediction-bot"))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("clone  bsc-geth in place", done.stdout)
        self.assertFalse((lead / "bsc-geth").is_symlink())
        self.assertTrue((lead / "prediction-bot").is_symlink())
        self.assertIn("`bsc-geth` (worker session `bsc-geth-worker`)", (lead / "CLAUDE.md").read_text())

    def test_init_refuses_a_directory_inside_a_repository(self):
        inside = self.tmp / "clones/prediction-bot/team"
        done = self.team("init", str(inside), str(self.tmp / "clones/bsc-geth"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("inside a git repository", done.stderr)
        self.assertFalse((inside / "CLAUDE.md").exists())

    def test_init_refuses_a_clone_that_is_not_one(self):
        done = self.team("init", str(self.tmp / "team"), str(self.tmp / "home"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("is not a git clone", done.stderr)

    def test_start_opens_a_window_per_clone_then_the_lead_with_every_clone_added(self):
        lead = self.tmp / "team"
        self.team("init", str(lead), str(self.tmp / "clones/prediction-bot"), str(self.tmp / "clones/bsc-geth"))
        done = self.team("start", str(lead))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        windows = self.tmux_log.read_text().splitlines()
        self.assertEqual(len(windows), 2)
        self.assertIn(f"new-window -d -c {self.tmp / 'clones/bsc-geth'} -n bsc-geth-worker claude -n bsc-geth-worker "
                      "--model opus --permission-mode bypassPermissions --settings '{\"remoteControlAtStartup\":false}'",
                      windows[0])
        self.assertIn("-n prediction-bot-worker", windows[1])
        lead_call = self.claude_calls()[-1]
        self.assertEqual(lead_call["argv"][:2], ["-n", "lead"])
        self.assertEqual(os.path.realpath(lead_call["cwd"]), str(lead))
        self.assertEqual(lead_call["argv"].count("--add-dir"), 2)
        self.assertIn(str(self.tmp / "clones/prediction-bot"), lead_call["argv"])

    def test_start_without_init_says_so(self):
        done = self.team("start", str(self.tmp / "clones"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("run bk-team init first", done.stderr)


if __name__ == "__main__":
    unittest.main()
