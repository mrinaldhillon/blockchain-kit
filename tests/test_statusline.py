"""Tests for bin/bk-statusline, driven as a subprocess over status JSON and temp checkouts.
How Claude Code draws the two lines is a live look, not tested here.

Run: tests/run   (or: python3 -m unittest discover -s tests)
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

KIT = Path(__file__).resolve().parent.parent
LINE = KIT / "bin" / "bk-statusline"
WHO = ("-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false")
NODE = "module github.com/ethereum/go-ethereum\n\ngo 1.27\n"
LINKS = re.compile(r"\x1b\]8;;[^\x07]*\x07")  # OSC 8 hyperlinks stay under NO_COLOR, which is about colour


def client(pin: str) -> str:
    return ("module example.com/bot\n\ngo 1.26\n\nrequire github.com/ethereum/go-ethereum v1.16.3\n\n"
            f"replace github.com/ethereum/go-ethereum => github.com/someone/bsc-geth "
            f"v0.0.0-20260921040038-{pin}\n")


class StatusLine(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        (self.tmp / "home").mkdir()

    def env(self, **more: str) -> dict[str, str]:
        drop = ("BLOCKCHAIN_KIT_", "BSC_FORK_", "GOWORK", "GIT_", "CLAUDE_CONFIG_DIR", "COLUMNS")
        full = {k: v for k, v in os.environ.items() if not k.startswith(drop)}
        full.update(GIT_CEILING_DIRECTORIES=str(self.tmp), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                    NO_COLOR="1", COLUMNS="400", CLAUDE_CONFIG_DIR=str(self.tmp / "home"),
                    BLOCKCHAIN_KIT_IPC=str(self.tmp / "no-geth.ipc"))
        full.update(more)
        return full

    def git(self, tree: str, *args: str) -> str:
        done = subprocess.run(["git", "-C", str(self.tmp / tree), *WHO, *args], check=True, capture_output=True,
                              text=True, env=self.env())
        return done.stdout.strip()

    def repo(self, tree: str, branch: str = "main") -> str:
        """A checkout with one commit; returns its SHA."""
        (self.tmp / tree).mkdir(parents=True, exist_ok=True)
        self.git(tree, "init", "--quiet", f"--initial-branch={branch}")
        self.git(tree, "commit", "--quiet", "--allow-empty", "--message", "first")
        return self.git(tree, "rev-parse", "HEAD")

    def run_line(self, status: dict | str, **env: str) -> subprocess.CompletedProcess[str]:
        text = status if isinstance(status, str) else json.dumps(status)
        return subprocess.run([str(LINE)], input=text, capture_output=True, text=True, env=self.env(**env),
                              cwd=self.tmp, timeout=30, check=False)

    def lines(self, status: dict, **env: str) -> list[str]:
        done = self.run_line(status, **env)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        out = [LINKS.sub("", line) for line in done.stdout.splitlines()]
        self.assertEqual(len(out), 2, done.stdout)
        return out

    def at(self, tree: str, **more: object) -> dict:
        where = str(self.tmp / tree)
        return {"cwd": where, "workspace": {"current_dir": where, "project_dir": where},
                "model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"}, **more}

    # the session line

    def test_the_session_line_carries_model_effort_context_and_limits(self):
        soon = int(time.time()) + 3600
        session, _ = self.lines(self.at(".", effort={"level": "xhigh"}, session_name="bkworking",
                                        context_window={"used_percentage": 34, "context_window_size": 1_000_000,
                                                        "current_usage": {"input_tokens": 2000,
                                                                          "cache_creation_input_tokens": 5000,
                                                                          "cache_read_input_tokens": 333000}},
                                        rate_limits={"five_hour": {"used_percentage": 74.2, "resets_at": soon},
                                                     "seven_day": {"used_percentage": 41, "resets_at": soon}},
                                        cost={"total_cost_usd": 12.345, "total_duration_ms": 5_400_000}))
        self.assertTrue(session.startswith("Opus 5.5·xhigh │ ctx ▓▓▓░░░░░░░ 34%"), session)
        self.assertIn(f"5h 74% ↻{time.strftime('%H:%M', time.localtime(soon))} 7d 41%", session)
        self.assertNotIn("7d 41% ↻", session)  # a window under 70% gives no reset time
        for part in ("340k/1.0M", "$12.35", "1h30m", "bkworking"):
            self.assertIn(part, session)

    def test_a_spend_limit_and_the_prompt_cache_are_shown(self):
        later = int(time.time()) + 3600
        session, _ = self.lines(self.at(".", rate_limits={"spend_limit": {"used_percentage": 63, "used_usd": 314.12,
                                                                          "limit_usd": 500}},
                                        prompt_cache={"warm": True, "caching_observed": True, "hit_ratio": 0.91,
                                                      "expires_at": later}))
        self.assertIn("spend $314/$500", session)
        self.assertIn("cache 91%", session)
        self.assertNotIn("cold", session)

    def test_a_cache_about_to_go_cold_or_cold_is_said(self):
        soon = int(time.time()) + 240
        session, _ = self.lines(self.at(".", prompt_cache={"warm": True, "caching_observed": True, "hit_ratio": 0.5,
                                                           "expires_at": soon}))
        self.assertIn("cache 50% cold in 4m", session)
        session, _ = self.lines(self.at(".", prompt_cache={"warm": False, "caching_observed": True}))
        self.assertIn("cache cold", session)
        session, _ = self.lines(self.at(".", prompt_cache={"warm": False, "caching_observed": False}))
        self.assertNotIn("cache", session)

    def test_a_segment_that_fails_leaves_the_rest(self):
        session, _ = self.lines(self.at(".", context_window="garbage", cost={"total_cost_usd": 1.5}))
        self.assertIn("Opus 5.5", session)
        self.assertIn("$1.50", session)
        self.assertNotIn("ctx", session)

    # the place line

    def test_the_place_line_carries_the_branch_and_its_state(self):
        self.repo("bot")
        (self.tmp / "bot/a.txt").write_text("a\n")
        (self.tmp / "bot/b.txt").write_text("b\n")
        self.git("bot", "add", "a.txt", "b.txt")
        self.git("bot", "commit", "--quiet", "--message", "two files")
        (self.tmp / "bot/a.txt").write_text("changed\n")
        (self.tmp / "bot/c.txt").write_text("c\n")
        self.git("bot", "add", "c.txt")
        (self.tmp / "bot/sub/dir").mkdir(parents=True)
        status = self.at("bot/sub/dir", pr={"number": 903, "url": "https://example.com/pr/903",
                                            "review_state": "changes_requested"})
        status["workspace"]["repo"] = {"host": "github.com", "owner": "me", "name": "prediction-bot"}
        _, place = self.lines(status)
        self.assertIn("prediction-bot/sub/dir main +1 ~1", place)
        self.assertIn("PR #903 changes requested", place)
        self.assertNotIn("PROD", place)

    def test_ahead_behind_detached_and_a_rebase_are_said(self):
        self.repo("up")
        self.git(".", "clone", "--quiet", str(self.tmp / "up"), str(self.tmp / "bot"))
        self.git("bot", "commit", "--quiet", "--allow-empty", "--message", "mine")
        self.git("up", "commit", "--quiet", "--allow-empty", "--message", "theirs")
        self.git("bot", "fetch", "--quiet")
        _, place = self.lines(self.at("bot"))
        self.assertIn("bot main ↑1 ↓1", place)
        (self.tmp / "bot/.git/rebase-merge").mkdir()
        _, place = self.lines(self.at("bot"))
        self.assertIn("REBASE", place)
        head = self.git("bot", "rev-parse", "HEAD")
        self.git("bot", "checkout", "--quiet", "--detach")
        _, place = self.lines(self.at("bot"))
        self.assertIn(f"bot {head[:8]}", place)

    def test_outside_a_repository_the_place_is_the_directory(self):
        (self.tmp / "plain").mkdir()
        _, place = self.lines(self.at("plain"))
        self.assertEqual(place, str(self.tmp / "plain"))

    def test_prod_is_said_where_the_geth_ipc_is_a_socket(self):
        back = os.getcwd()
        os.chdir(self.tmp)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.bind("geth.ipc")
        finally:
            os.chdir(back)
        (self.tmp / "plain").mkdir()
        _, place = self.lines(self.at("plain"), BLOCKCHAIN_KIT_IPC=str(self.tmp / "geth.ipc"))
        self.assertTrue(place.endswith(" │ PROD"), place)

    # a fork client

    def fork_client(self) -> str:
        """bot/ pins geth/'s first commit; returns that SHA."""
        sha = self.repo("geth", branch="mrinal/dev")
        (self.tmp / "geth/go.mod").write_text(NODE)
        self.repo("bot")
        (self.tmp / "bot/go.mod").write_text(client(sha[:12]))
        index = self.tmp / "bot/docs/fork-knowledge"
        index.mkdir(parents=True)
        (index / "symbols.json").write_text(json.dumps({"fork_sha": sha, "symbols": []}))
        return sha

    def test_a_fork_client_shows_the_pin_and_the_checkout_against_it(self):
        sha = self.fork_client()
        _, place = self.lines(self.at("bot"))
        self.assertIn(f"pin {sha[:12]}", place)
        self.assertNotIn("STALE", place)
        self.assertNotIn("fork ", place)  # no checkout named
        self.git("geth", "add", "go.mod")
        self.git("geth", "commit", "--quiet", "--message", "past the pin")
        _, place = self.lines(self.at("bot"), BSC_FORK_PATH=str(self.tmp / "geth"))
        self.assertIn("fork mrinal/dev +1", place)
        (self.tmp / "bot/go.work").write_text("go 1.26\n\nuse (\n\t.\n\t../geth\n)\n")
        _, place = self.lines(self.at("bot"))
        self.assertIn("go.work: builds the CHECKOUT", place)

    def test_a_stale_index_is_said(self):
        self.fork_client()
        (self.tmp / "bot/docs/fork-knowledge/symbols.json").write_text(json.dumps({"fork_sha": "5bed3824ce90" + "0" * 28,
                                                                                   "symbols": []}))
        _, place = self.lines(self.at("bot"))
        self.assertIn("index STALE", place)

    # the kit

    def install(self, project: str, sha: str, scope: str = "project") -> None:
        entry = {"scope": scope, "version": sha[:12], "gitCommitSha": sha}
        if scope == "project":
            entry["projectPath"] = str(self.tmp / project)
        plugins = self.tmp / "home/plugins"
        plugins.mkdir(parents=True, exist_ok=True)
        (plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
            "blockchain-kit@blockchain-kit": [entry]}}))

    def test_the_kit_installed_for_the_project_and_a_newer_marketplace_are_shown(self):
        self.repo("bot")
        market = self.repo("home/plugins/marketplaces/blockchain-kit")
        self.install("bot", market)
        _, place = self.lines(self.at("bot"))
        self.assertTrue(place.endswith(f" │ kit {market[:7]}"), place)
        self.git("home/plugins/marketplaces/blockchain-kit", "commit", "--quiet", "--allow-empty", "--message", "new")
        moved = self.git("home/plugins/marketplaces/blockchain-kit", "rev-parse", "HEAD")
        _, place = self.lines(self.at("bot"))
        self.assertIn(f"kit {market[:7]}→{moved[:7]}", place)

    def test_another_projects_install_is_not_this_ones(self):
        self.repo("bot")
        self.repo("other")
        self.install("other", "c" * 40)
        _, place = self.lines(self.at("bot"))
        self.assertNotIn("kit ", place)
        self.install("", "d" * 40, scope="user")
        _, place = self.lines(self.at("bot"))
        self.assertIn("kit ddddddd", place)

    # width, colour and bad input

    def test_a_narrow_terminal_drops_the_least_important_segments_first(self):
        status = self.at(".", effort={"level": "high"}, context_window={"used_percentage": 81},
                         rate_limits={"five_hour": {"used_percentage": 20, "resets_at": int(time.time()) + 60}},
                         cost={"total_cost_usd": 3.0, "total_duration_ms": 600_000}, session_name="a-name")
        session, _ = self.lines(status, COLUMNS="60")
        self.assertEqual(session, "Opus 5.5·high │ ctx ▓▓▓▓▓▓▓▓░░ 81% │ 5h 20% │ a-name")  # cost, then duration, go first
        session, _ = self.lines(status, COLUMNS="10")
        self.assertEqual(session, "Opus 5.5·high")  # the first segment always stays

    def test_colour_is_ansi_unless_no_color_is_set(self):
        session, _ = self.lines(self.at(".", context_window={"used_percentage": 85}), NO_COLOR="")
        self.assertIn("\x1b[31mctx ▓▓▓▓▓▓▓▓░░ 85%\x1b[0m", session)

    def test_bad_input_still_prints_a_line_and_exits_zero(self):
        for text in ("not json", "[1, 2]", ""):
            done = self.run_line(text)
            self.assertEqual((done.returncode, done.stderr, done.stdout), (0, "", f"{self.tmp}\n"))

    def test_help_and_usage(self):
        done = subprocess.run([str(LINE), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0)
        self.assertIn("Usage: bk-statusline", done.stdout)
        done = subprocess.run([str(LINE), "extra"], capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 2)


if __name__ == "__main__":
    unittest.main()
