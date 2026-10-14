"""Tests for hooks/implement-args: the implement workflow told what the project is, and
refused in the bsc-geth fork itself.

The hook is driven as a subprocess with a PreToolUse payload on stdin, in temp trees: a
client (its go.mod replaces go-ethereum) and two fork clones. Whether Claude Code applies
updatedInput to a Workflow call, and honours the deny, is a live probe, not run here.

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
HOOK = KIT / "hooks" / "implement-args"
UPSTREAM = "github.com/ethereum/go-ethereum"
REASON = ("This project is the bsc-geth fork; in-place fork runs are not supported yet (kit #16). Dispatch "
          "blockchain-kit:golang-implementer by hand, package-scoped, or run implement from the prediction-bot "
          "clone with `fork` set.")
CLIENT_GOMOD = ("module example.com/bot\n\ngo 1.26\n\nrequire github.com/ethereum/go-ethereum v1.16.3\n\nreplace "
                "github.com/ethereum/go-ethereum => github.com/someone/bsc-geth v0.0.0-20260921040038-a539ea2ca63c\n")
NODE_GOMOD = f"module {UPSTREAM}\n\ngo 1.24\n"
ARGS = {"units": [{"id": "a", "brief": "the contract", "packages": ["eth"]}], "branch": "feat/x", "head": "a" * 40}


class ImplementArgs(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        for tree, gomod in (("bot", CLIENT_GOMOD), ("fork", NODE_GOMOD), ("other", NODE_GOMOD)):
            (self.tmp / tree / ".git").mkdir(parents=True)
            (self.tmp / tree / "go.mod").write_text(gomod)
        (self.tmp / "bot/internal").mkdir()
        (self.tmp / "fork/eth").mkdir()
        (self.tmp / "fork-link").symlink_to(self.tmp / "fork")
        self.bot, self.fork, self.other = (str(self.tmp / t) for t in ("bot", "fork", "other"))

    def env(self, project: str | None = None, **more: str) -> dict[str, str]:
        full = {k: v for k, v in os.environ.items() if not k.startswith(("BLOCKCHAIN_KIT_", "CLAUDE_"))}
        if project is not None:
            full["CLAUDE_PROJECT_DIR"] = project
        full.update(more)
        return full

    def run_hook(self, stdin: str, env: dict[str, str], cwd: str | None = None) -> tuple[int, str, str]:
        done = subprocess.run([str(HOOK)], input=stdin, capture_output=True, text=True, env=env,
                              cwd=cwd or self.tmp, timeout=30, check=False)
        return done.returncode, done.stdout, done.stderr

    def call(self, args: object = None, name: str = "blockchain-kit:implement", cwd: str = "/nowhere",
             tool: str = "Workflow", **more: object) -> str:
        tool_input: dict[str, object] = {"name": name, **more}
        if args is not None:
            tool_input["args"] = args
        return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "cwd": cwd})

    def rewritten(self, result: tuple[int, str, str]) -> dict:
        rc, out, err = result
        self.assertEqual((rc, err), (0, ""))
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(set(decision), {"hookEventName", "updatedInput"})
        return decision["updatedInput"]

    def assertDenied(self, result: tuple[int, str, str], what: str) -> None:
        rc, out, err = result
        self.assertEqual((rc, err), (0, ""), what)
        self.assertTrue(out, f"not denied: {what}")
        self.assertEqual(json.loads(out), {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": REASON}}, what)

    def test_a_client_root_gets_project_and_module_filled_in(self):
        new = self.rewritten(self.run_hook(self.call(ARGS, description="run"), self.env(self.bot)))
        self.assertEqual(new, {"name": "blockchain-kit:implement", "description": "run",
                               "args": {**ARGS, "project": self.bot, "module": "example.com/bot"}})
        # without CLAUDE_PROJECT_DIR: the git top level above the payload cwd
        new = self.rewritten(self.run_hook(self.call(ARGS, name="implement", cwd=f"{self.bot}/internal"), self.env()))
        self.assertEqual((new["args"]["project"], new["args"]["module"]), (self.bot, "example.com/bot"))
        # a field the caller set is kept; with both set nothing is printed
        new = self.rewritten(self.run_hook(self.call({**ARGS, "project": "/given"}), self.env(self.bot)))
        self.assertEqual((new["args"]["project"], new["args"]["module"]), ("/given", "example.com/bot"))
        both = {**ARGS, "project": "/given", "module": "example.com/given"}
        self.assertEqual(self.run_hook(self.call(both), self.env(self.bot)), (0, "", ""))

    def test_a_fork_root_without_another_fork_is_denied(self):
        cases = [
            ("no fork", self.call(ARGS), self.env(self.fork)),
            ("the bare name", self.call(ARGS, name="implement"), self.env(self.fork)),
            ("fork names the root", self.call({**ARGS, "fork": self.fork}), self.env(self.fork)),
            ("fork, trailing slash", self.call({**ARGS, "fork": self.fork + "/"}), self.env(self.fork)),
            ("fork through a symlink", self.call({**ARGS, "fork": str(self.tmp / "fork-link")}), self.env(self.fork)),
            ("from a subdirectory cwd", self.call(ARGS, cwd=f"{self.fork}/eth"), self.env()),
            ("args as a JSON string", self.call(json.dumps(ARGS)), self.env(self.fork)),
            ("a caller's wrong module", self.call({**ARGS, "module": "example.com/bot"}), self.env(self.fork)),
            ("no args at all", self.call(), self.env(self.fork)),
        ]
        for what, stdin, env in cases:
            with self.subTest(case=what):
                self.assertDenied(self.run_hook(stdin, env), what)

    def test_a_fork_root_with_fork_naming_another_tree_runs(self):
        new = self.rewritten(self.run_hook(self.call({**ARGS, "fork": self.other}), self.env(self.fork)))
        self.assertEqual(new["args"], {**ARGS, "fork": self.other, "project": self.fork, "module": UPSTREAM})

    def test_any_other_call_is_untouched(self):
        cases = [
            ("another workflow", self.call(ARGS, name="blockchain-kit:other"), self.env(self.fork)),
            ("a script", json.dumps({"tool_name": "Workflow", "tool_input": {"script": "x"}}), self.env(self.fork)),
            ("another tool", self.call(ARGS, tool="Bash"), self.env(self.fork)),
            ("the kill switch", self.call(ARGS), self.env(self.fork, BLOCKCHAIN_KIT_IMPLEMENT_ARGS="0")),
            ("a project with no go.mod, args set", self.call({**ARGS, "project": "/p"}), self.env(str(self.tmp))),
        ]
        for what, stdin, env in cases:
            with self.subTest(case=what):
                self.assertEqual(self.run_hook(stdin, env), (0, "", ""), what)

    def test_it_fails_closed_only_in_the_fork(self):
        for stdin in ("not json", "[1, 2]"):
            rc, out, err = self.run_hook(stdin, self.env(self.fork))
            self.assertEqual((rc, out), (2, ""), stdin)
            self.assertIn("failing closed in the bsc-geth fork", err)
            self.assertIn(REASON, err)
            self.assertEqual(self.run_hook(stdin, self.env(), cwd=f"{self.fork}/eth")[0], 2, stdin)  # the hook's cwd
            self.assertEqual(self.run_hook(stdin, self.env(self.bot)), (0, "", ""), stdin)


if __name__ == "__main__":
    unittest.main()
