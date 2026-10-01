"""Tests for bin/bk-gate: the verdict line, the tail on red, the out file, the exit code.

Run: tests/run   (or: python3 -m unittest discover -s tests)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

KIT = Path(__file__).resolve().parent.parent
GATE = KIT / "bin" / "bk-gate"
VERDICT = re.compile(r"gate: (?P<name>\S+) rc=(?P<rc>\d+) t=\d+\.\ds out=(?P<out>\S+)")
PY = sys.executable


class Gate(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))

    def env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("BLOCKCHAIN_KIT_")}
        env["TMPDIR"] = str(self.tmp)
        return env

    def gate(self, *argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(GATE), *argv], capture_output=True, text=True, env=self.env(), cwd=self.tmp,
                              timeout=30, check=False)

    def verdict(self, done: subprocess.CompletedProcess[str], name: str, rc: int) -> list[str]:
        """Asserts the first stdout line is the verdict; returns the lines after it."""
        lines = done.stdout.splitlines()
        self.assertTrue(lines, done.stderr)
        m = VERDICT.fullmatch(lines[0])
        assert m is not None, lines[0]
        self.assertEqual((m["name"], int(m["rc"]), done.returncode), (name, rc, rc))
        out = Path(m["out"])
        self.assertEqual(out.parent, self.tmp)
        self.assertRegex(out.name, rf"^bk-gate-{re.escape(name)}-\d{{8}}T\d{{6}}-\d+\.out$")
        self.out = out
        return lines[1:]

    def test_green_is_one_line_and_the_out_file_holds_the_output(self):
        done = self.gate("unit tests/x", "--", PY, "-c", "print('all fine'); import sys; print('warn', file=sys.stderr)")
        self.assertEqual(self.verdict(done, "unit_tests_x", 0), [])
        self.assertEqual(done.stderr, "")
        self.assertEqual(sorted(self.out.read_text().splitlines()), ["all fine", "warn"])

    def test_red_prints_the_last_ten_lines_and_passes_the_rc(self):
        program = "for i in range(25): print(f'line {i}')\nraise SystemExit(3)"
        done = self.gate("lint", "--", PY, "-c", program)
        self.assertEqual(self.verdict(done, "lint", 3), [f"line {i}" for i in range(15, 25)])
        self.assertEqual(self.out.read_text().splitlines(), [f"line {i}" for i in range(25)])

    def test_a_signal_is_128_plus_n(self):
        done = self.gate("killed", "--", PY, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)")
        self.assertEqual(self.verdict(done, "killed", 143), [])

    def test_a_command_that_cannot_be_spawned_is_127(self):
        done = self.gate("absent", "--", str(self.tmp / "no-such-command"))
        self.assertEqual(done.returncode, 127)
        self.assertRegex(done.stdout, r"^gate: absent rc=127 t=\d+\.\ds out=-\n$")
        self.assertEqual(len(done.stderr.splitlines()), 1, done.stderr)
        self.assertIn("no-such-command", done.stderr)

    def test_dash_c_runs_the_command_in_that_directory(self):
        there = self.tmp / "lane"
        there.mkdir()
        done = self.gate("-C", str(there), "pwd", "--", PY, "-c", "import os; print(os.getcwd())")
        self.verdict(done, "pwd", 0)
        self.assertEqual(self.out.read_text().strip(), str(there))

    def test_a_usage_error_is_2_with_no_verdict_line(self):
        argvs = ((), ("name",), ("name", "--"), ("name", "true"), ("--", "true"), ("--bogus", "n", "--", "true"),
                 ("-C",))
        procs = [subprocess.Popen([str(GATE), *argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  env=self.env(), cwd=self.tmp) for argv in argvs]  # independent: run together
        for argv, proc in zip(argvs, procs):
            out, err = proc.communicate(timeout=30)
            with self.subTest(argv=argv):
                self.assertEqual((proc.returncode, out), (2, ""))
                self.assertRegex(err, r"^bk-gate: [^\n]+\n$")

    def test_help_prints_the_contract(self):
        done = self.gate("--help")
        self.assertEqual(done.returncode, 0)
        self.assertIn("gate: <name> rc=<n> t=<S>s out=<path>", done.stdout)


if __name__ == "__main__":
    unittest.main()
