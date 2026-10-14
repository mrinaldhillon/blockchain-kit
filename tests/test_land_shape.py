"""Tests for hooks/land-shape: the PreToolUse rewrite of a `dev-setup/ci/land` call.

The hook is driven as a subprocess with a hook payload on stdin. Whether Claude Code
applies an `updatedInput` is a live probe, not run here.

Run: tests/run   (or: python3 -m unittest discover -s tests)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "land-shape"
LONG = 1_800_000


def payload(command: str, tool: str = "Bash", **fields: object) -> str:
    return json.dumps({"tool_name": tool, "tool_input": {"command": command, **fields}})


class LandShapeTest(unittest.TestCase):
    def run_hook(self, stdin: str, **env: str) -> tuple[int, str, str]:
        got = subprocess.run([str(HOOK)], input=stdin, capture_output=True, text=True, timeout=30,
                             env={**os.environ, **env}, check=False)
        return got.returncode, got.stdout, got.stderr

    def shaped(self, command: str, **fields: object) -> dict[str, object]:
        rc, out, err = self.run_hook(payload(command, **fields))
        self.assertEqual(rc, 0, err)
        body = json.loads(out)
        self.assertEqual(body["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertNotIn("permissionDecision", body["hookSpecificOutput"])  # permission rules still judge it
        return body["hookSpecificOutput"]["updatedInput"]

    def untouched(self, stdin: str) -> None:
        rc, out, err = self.run_hook(stdin)
        self.assertEqual((rc, out), (0, ""), err)

    def test_the_969_shape_loses_its_timeout_wrapper_and_runs_in_the_foreground(self):
        command = 'timeout 590 dev-setup/ci/land 969 > /tmp/l.log 2>&1; echo "exit=$?"; tail -4 /tmp/l.log'
        new = self.shaped(command, description="Land PR 969", run_in_background=True, timeout=600000)
        self.assertEqual(new, {
            "command": 'dev-setup/ci/land 969 > /tmp/l.log 2>&1; echo "exit=$?"; tail -4 /tmp/l.log',
            "description": "Land PR 969",
            "run_in_background": False,
            "timeout": LONG,
        })

    def test_every_wrapper_form_in_front_of_land_is_removed(self):
        for command, want in (
            ("git push -q && timeout -k 5 590 ./dev-setup/ci/land 971", "git push -q && ./dev-setup/ci/land 971"),
            ("cd /tmp/pb && timeout --signal=KILL 10m dev-setup/ci/land", "cd /tmp/pb && dev-setup/ci/land"),
            ("PB_LAND_POLL=2 timeout 590 python3 dev-setup/ci/land.py 12",
             "PB_LAND_POLL=2 python3 dev-setup/ci/land.py 12"),
            ("timeout 590 /home/u/pb/dev-setup/ci/land 3 || echo red", "/home/u/pb/dev-setup/ci/land 3 || echo red"),
        ):
            with self.subTest(command=command):
                self.assertEqual(self.shaped(command)["command"], want)

    def test_a_bare_land_gets_the_long_foreground_timeout(self):
        new = self.shaped("git push -q && dev-setup/ci/land 971", timeout=600000)
        self.assertEqual(new, {"command": "git push -q && dev-setup/ci/land 971", "run_in_background": False,
                               "timeout": LONG})

    def test_a_background_start_is_made_foreground(self):
        new = self.shaped("dev-setup/ci/land 971", run_in_background=True, timeout=LONG)
        self.assertIs(new["run_in_background"], False)
        self.assertEqual(new["timeout"], LONG)

    def test_a_call_already_in_the_cheap_shape_is_left_alone(self):
        self.untouched(payload("git push -q && dev-setup/ci/land 971", timeout=LONG))
        self.untouched(payload("dev-setup/ci/land 971", timeout=LONG, run_in_background=False))

    def test_a_heredoc_keeps_its_text_even_when_land_is_found(self):
        command = "git commit -q -F - <<'EOF' && dev-setup/ci/land 9\nwas: timeout 590 dev-setup/ci/land <PR>\nEOF"
        new = self.shaped(command)
        self.assertEqual(new["command"], command)
        self.assertEqual(new["timeout"], LONG)

    def test_land_named_but_not_run_is_left_alone(self):
        for command in ("grep -n settle dev-setup/ci/land.py", "cat dev-setup/ci/land", "echo dev-setup/ci/land",
                        "git log -- dev-setup/ci/land.py", "ls dev-setup/ci", "make land-lint",
                        'git commit -m "timeout 590 dev-setup/ci/land"'):
            with self.subTest(command=command):
                self.untouched(payload(command))

    def test_other_tools_bad_payloads_and_the_switch_print_nothing(self):
        self.untouched(payload("dev-setup/ci/land 1", tool="Read"))
        for stdin in ("not json", "[]", json.dumps({"tool_name": "Bash", "tool_input": "x"}),
                      payload("timeout 590 dev-setup/ci/land 'unterminated")):
            with self.subTest(stdin=stdin):
                rc, out, _ = self.run_hook(stdin)
                self.assertEqual((rc, out), (0, ""))
        rc, out, _ = self.run_hook(payload("timeout 590 dev-setup/ci/land 1"), BLOCKCHAIN_KIT_LAND_SHAPE="0")
        self.assertEqual((rc, out), (0, ""))

    def test_the_hook_is_registered_for_bash_and_executable(self):
        self.assertTrue(os.access(HOOK, os.X_OK))
        hooks = json.loads((HOOK.parent / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
        bash = [h["command"] for group in hooks if group.get("matcher") == "Bash" for h in group["hooks"]]
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/hooks/land-shape"', bash)


if __name__ == "__main__":
    unittest.main()
