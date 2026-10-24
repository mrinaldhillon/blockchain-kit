"""Tests for hooks/reader-reminder: the reference rule beside each operator message, in
prediction-bot and in the bsc-geth fork, and nowhere else.

The hook is driven as a subprocess with a UserPromptSubmit payload on stdin, in temp trees: a
client (its go.mod replaces go-ethereum), a fork clone, and a Go project that is neither.
Whether the reminder changes what a session writes is a live measurement, not this file.

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

KIT = Path(__file__).resolve().parent.parent
HOOK = KIT / "hooks" / "reader-reminder"
CLIENT_GOMOD = ("module example.com/bot\n\ngo 1.26\n\nrequire github.com/ethereum/go-ethereum v1.16.3\n\nreplace "
                "github.com/ethereum/go-ethereum => github.com/someone/bsc-geth v0.0.0-20260921040038-a539ea2ca63c\n")
NODE_GOMOD = "module github.com/ethereum/go-ethereum\n\ngo 1.24\n"
OTHER_GOMOD = "module example.com/other\n\ngo 1.26\n"


class ReaderReminder(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        for tree, gomod in (("bot", CLIENT_GOMOD), ("fork", NODE_GOMOD), ("other", OTHER_GOMOD)):
            (self.tmp / tree / ".git").mkdir(parents=True)
            (self.tmp / tree / "go.mod").write_text(gomod)
        (self.tmp / "bot/internal/state").mkdir(parents=True)
        (self.tmp / "plain").mkdir()

    def run_hook(self, cwd: Path, project: Path | None = None, stdin: str | None = None, **env: str) -> tuple[int, str]:
        full = {k: v for k, v in os.environ.items() if not k.startswith(("BLOCKCHAIN_KIT_", "CLAUDE_"))}
        if project is not None:
            full["CLAUDE_PROJECT_DIR"] = str(project)
        full.update(env)
        payload = stdin if stdin is not None else json.dumps(
            {"hook_event_name": "UserPromptSubmit", "prompt": "list the items", "cwd": str(cwd)})
        done = subprocess.run([str(HOOK)], input=payload, capture_output=True, text=True, env=full,
                              cwd=self.tmp, timeout=30, check=False)
        self.assertEqual(done.stderr, "")
        return done.returncode, done.stdout

    def context(self, out: str) -> str:
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "UserPromptSubmit")
        return decision["additionalContext"]

    def test_it_reminds_in_the_bot_and_in_the_fork(self):
        for what, cwd, project in [
            ("the bot's root", self.tmp / "bot", None),
            ("a package inside the bot", self.tmp / "bot/internal/state", None),
            ("the fork", self.tmp / "fork", None),
            ("CLAUDE_PROJECT_DIR wins over cwd", self.tmp / "plain", self.tmp / "fork"),
        ]:
            with self.subTest(case=what):
                rc, out = self.run_hook(cwd, project)
                self.assertEqual(rc, 0)
                text = self.context(out)
                self.assertIn("path:line", text)
                self.assertIn("No bare §4.4", text)
                self.assertIn("a label you coined is defined in the same message", text)

    def test_it_is_silent_anywhere_else(self):
        for what, cwd, stdin, env in [
            ("a Go project that is neither", self.tmp / "other", None, {}),
            ("no go.mod at all", self.tmp / "plain", None, {}),
            ("the kill switch, in the bot", self.tmp / "bot", None, {"BLOCKCHAIN_KIT_READER_REMINDER": "0"}),
            ("an unreadable payload, in the bot", self.tmp / "bot", "not json", {}),
            ("a payload that is not an object", self.tmp / "bot", "[1]", {}),
        ]:
            with self.subTest(case=what):
                self.assertEqual(self.run_hook(cwd, stdin=stdin, **env), (0, ""))


if __name__ == "__main__":
    unittest.main()
