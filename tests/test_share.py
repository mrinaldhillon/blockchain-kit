"""Tests for bin/bk-mainloop-share, driven as a subprocess over fixture transcripts.

Run: tests/run   (or: python3 -m unittest discover -s tests)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

KIT = Path(__file__).resolve().parent.parent
SHARE = KIT / "bin" / "bk-mainloop-share"
ROW = re.compile(r"(?P<category>\S.*?)\s+(?P<turns>\d+)\s+[\d.]+\s+[\d.]+\s+[\d.]+")

# One main-loop turn per category, in ORDER; each carries one call (or none) that only
# its own category matches.
ONE_PER_CATEGORY = {
    "dispatch": [{"type": "tool_use", "name": "Agent", "input": {"subagent_type": "x"}}],
    "bookkeeping-write": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/r/.claude/context/RESUME.md"}}],
    "git/gh/land legwork": [{"type": "tool_use", "name": "Bash", "input": {"command": "dev-setup/ci/land --merge"}}],
    "gate run": [{"type": "tool_use", "name": "Bash", "input": {"command": "bk-gate unit -- go test ./internal/x"}}],
    "steering edit": [{"type": "tool_use", "name": "Write", "input": {"file_path": "/r/.claude/agents/a.md"}}],
    "plan/spec/ADR/doc write": [{"type": "tool_use", "name": "Write", "input": {"file_path": "/r/docs/design.md"}}],
    "product edit": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/r/internal/state/a.go"}}],
    "read/search": [{"type": "tool_use", "name": "Read", "input": {"file_path": "/r/go.mod"}}],
    "other tool": [{"type": "tool_use", "name": "TodoWrite", "input": {}}],
    "text only": [{"type": "text", "text": "done"}],
}


def entry(mid: str, content: list[dict], sidechain: bool = False) -> str:
    usage = {"output_tokens": 10, "input_tokens": 1, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0}
    return json.dumps({"type": "assistant", "isSidechain": sidechain,
                       "message": {"id": mid, "content": content, "usage": usage}})


class Share(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))

    def transcript(self, name: str, lines: list[str], age_days: float = 0.01) -> None:
        path = self.tmp / name
        path.write_text("\n".join(lines) + "\n")
        when = time.time() - age_days * 86400
        os.utime(path, (when, when))

    def share(self, *argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(SHARE), *argv], capture_output=True, text=True, timeout=30, check=False)

    def rows(self, days: str = "1") -> dict[str, int]:
        done = self.share(str(self.tmp), days)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        rows = {}
        for line in done.stdout.splitlines()[2:]:
            m = ROW.fullmatch(line)
            assert m is not None, line
            rows[m["category"]] = int(m["turns"])
        return rows

    def test_one_turn_per_category_classifies_as_labelled(self):
        lines = [entry(f"m{i}", content) for i, content in enumerate(ONE_PER_CATEGORY.values())]
        # a message split across two entries is one turn
        lines.append(entry("m0", [{"type": "text", "text": "and a word"}]))
        # sidechain entries are a subagent's turns, not the main loop's
        lines += [entry("s1", ONE_PER_CATEGORY["dispatch"], sidechain=True),
                  entry("s2", ONE_PER_CATEGORY["gate run"], sidechain=True)]
        self.transcript("a.jsonl", lines)
        # outside the window: not read
        self.transcript("old.jsonl", [entry("o1", ONE_PER_CATEGORY["dispatch"])], age_days=10)
        rows = self.rows()
        self.assertEqual(rows, {**dict.fromkeys(ONE_PER_CATEGORY, 1), "orchestration subtotal": 4})

    def test_git_grep_is_a_read_whatever_its_pattern_says(self):
        commands = ("git grep -n make -- docs", "git -C ../geth grep -n 'git commit'", "make test")
        self.transcript("a.jsonl", [entry(f"g{i}", [{"type": "tool_use", "name": "Bash", "input": {"command": c}}])
                                    for i, c in enumerate(commands)])
        self.assertEqual(self.rows(), {"gate run": 1, "read/search": 2, "orchestration subtotal": 1})

    def test_usage_errors_are_2(self):
        argvs = ((), (str(self.tmp),), (str(self.tmp / "absent"), "1"), (str(self.tmp), "soon"),
                 (str(self.tmp), "1", "x"))
        procs = [subprocess.Popen([str(SHARE), *argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for argv in argvs]  # independent: run together
        for argv, proc in zip(argvs, procs):
            out, err = proc.communicate(timeout=30)
            with self.subTest(argv=argv):
                self.assertEqual((proc.returncode, out), (2, ""))
                self.assertEqual(len(err.splitlines()), 1, err)
        self.assertIn("orchestration subtotal", self.share("--help").stdout)


if __name__ == "__main__":
    unittest.main()
