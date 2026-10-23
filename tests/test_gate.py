"""Tests for bin/bk-gate: the verdict line, the tail on red, the out file, the exit code.

Run: tests/run   (or: python3 -m unittest discover -s tests)
"""

from __future__ import annotations

import fcntl
import os
import re
import socket
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

    def env(self, **more: str) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("BLOCKCHAIN_KIT_")}
        env["TMPDIR"] = str(self.tmp)
        env["BLOCKCHAIN_KIT_IPC"] = str(self.tmp / "absent.ipc")  # a dev host, whatever host runs the suite
        env["BLOCKCHAIN_KIT_GATE_SLOTS_DIR"] = str(self.tmp / "slots")  # never the host's real slots
        env.update(more)
        return env

    def gate(self, *argv: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(GATE), *argv], capture_output=True, text=True, env=env or self.env(),
                              cwd=self.tmp, timeout=30, check=False)

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


    def prod_socket(self) -> Path:
        """A real unix socket at a temp IPC path: lib/bkhost.py then reads this host as production."""
        ipc = self.tmp / "geth.ipc"
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        back = os.getcwd()
        os.chdir(self.tmp)  # bind by a relative name: AF_UNIX paths stop at 108 bytes
        try:
            sock.bind(ipc.name)
        finally:
            os.chdir(back)
        return ipc

    def tree(self, name: str, *, tool: str | None = None, source: bool = False) -> Path:
        """A git repository; `tool` is a fake cap that logs its argv to $CAP_LOG and runs the command."""
        root = self.tmp / name
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "i"], check=True)
        if source:
            (root / "cmd/verifyconstrained").mkdir(parents=True)
            (root / "cmd/verifyconstrained/main.go").write_text("package main\n")
        if tool:
            (root / tool).parent.mkdir(parents=True, exist_ok=True)
            (root / tool).write_text('#!/bin/sh\nprintf "%s\\n" "$0" "$@" > "$CAP_LOG"\n[ "$1" = "--" ] && shift\n'
                                     'exec "$@"\n')
            (root / tool).chmod(0o755)
        return root

    def test_on_the_production_host_a_gate_runs_inside_its_trees_cap(self):
        # The invariant: on the host that runs geth and the collectors, a gate never runs outside the cap its
        # repository ships; on any other host, or with the switch off, bk-gate is what it always was.
        ipc = self.prod_socket()
        tree = self.tree
        pb = tree("pb", tool="dev-setup/ci/ci-cap.sh")
        bsc = tree("bsc", tool="build/bin/verifyconstrained", source=True)
        lane = self.tmp / ".bsc.worktrees/wf_1"  # a lane beside the clone: the source, not the built binary
        subprocess.run(["git", "-C", str(bsc), "worktree", "add", "-q", "--detach", str(lane)], check=True)
        (lane / "cmd/verifyconstrained").mkdir(parents=True)
        (lane / "cmd/verifyconstrained/main.go").write_text("package main\n")
        plain = tree("plain")
        prod = {"BLOCKCHAIN_KIT_IPC": str(ipc)}
        cases = [  # (case, -C tree, env, the tool that ran it or None, what stderr says)
            ("pb on prod", pb, prod, pb / "dev-setup/ci/ci-cap.sh", "capped by dev-setup/ci/ci-cap.sh"),
            ("bsc on prod", bsc, prod, bsc / "build/bin/verifyconstrained", "capped by"),
            ("a bsc lane on prod", lane, prod, bsc / "build/bin/verifyconstrained", "capped by"),
            ("no cap tool on prod", plain, prod, None, "running uncapped"),
            ("pb on a dev host", pb, {}, None, ""),
            ("pb on prod, switched off", pb, {**prod, "BLOCKCHAIN_KIT_GATE_CAP": "0"}, None, ""),
        ]
        for case, root, more, tool, said in cases:
            log = self.tmp / f"cap-{len(case)}-{case[:3]}.argv"
            done = self.gate("-C", str(root), "t", "--", PY, "-c", "print('ran'); raise SystemExit(3)",
                             env=self.env(CAP_LOG=str(log), **more))
            self.assertEqual(self.verdict(done, "t", 3), ["ran"], case)
            self.assertEqual(log.read_text().splitlines()[:2] if log.exists() else None,
                             [str(tool), "--"] if tool else None, case)
            self.assertIn(said, done.stderr, case) if said else self.assertEqual(done.stderr, "", case)


    def test_on_the_production_host_a_third_capped_gate_waits_for_a_slot(self):
        # The invariant: at most two capped gates hold memory on the production host at once (operator, 2026-10-23).
        env = self.env(BLOCKCHAIN_KIT_IPC=str(self.prod_socket()), CAP_LOG=str(self.tmp / "cap.argv"))
        slots = Path(env["BLOCKCHAIN_KIT_GATE_SLOTS_DIR"])
        slots.mkdir()
        held = [open(slots / f"slot-{i}.lock", "a") for i in range(2)]  # two gates already running
        for f in held:
            self.addCleanup(f.close)
            fcntl.flock(f, fcntl.LOCK_EX)
        third = subprocess.Popen([str(GATE), "-C", str(self.tree("pb", tool="dev-setup/ci/ci-cap.sh")), "t", "--",
                                  PY, "-c", "print('ran')"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, env=env, cwd=self.tmp)
        self.addCleanup(third.kill)
        assert third.stderr is not None
        self.assertIn("capped by", third.stderr.readline())
        self.assertIn("waiting for a gate slot", third.stderr.readline())
        self.assertFalse((self.tmp / "cap.argv").exists())  # it waits before the cap tool starts
        held[1].close()  # one gate finishes
        out, err = third.communicate(timeout=30)
        self.assertRegex(out, r"^gate: t rc=0 ")
        self.assertIn("got a gate slot after", err)
        self.assertTrue((self.tmp / "cap.argv").exists())


if __name__ == "__main__":
    unittest.main()
