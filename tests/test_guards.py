"""Tests for the PreToolUse guards: hooks/guard-secrets and hooks/guard-prod-run.

Each guard is driven as a subprocess with a hook payload on stdin. The prod host is a
real unix socket made in a temp dir and named by BLOCKCHAIN_KIT_IPC. Whether Claude
Code honours a deny is a live probe, not run here.

Run: tests/run   (or: python3 -m unittest discover -s tests)
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

KIT = Path(__file__).resolve().parent.parent
SECRETS = KIT / "hooks" / "guard-secrets"
PROD_RUN = KIT / "hooks" / "guard-prod-run"

NODE = ("/data/geth/nodekey", "nodekey", "/data/geth/JWTSecret", "jwtsecret", "/data/engine.jwt",
        "/data/keystore/UTC--2026-01-01T00-00-00.000000000Z--00aa")
GENERIC = ("/repo/secrets/token", "secrets/token", "/repo/deploy/prod-secrets.env", "/repo/tls/server.KEY",
           "/repo/tls/server.pem", "/repo/sign/id.p12", "/repo/.envrc", "/repo/config.local", "/repo/.env",
           "/repo/.env.production")
SOURCE = ("/fork/accounts/keystore/keystore.go", "/fork/cmd/utils/nodekey_ext.go", "/bot/internal/state/a.go",
          "/repo/.claude/settings.local.json", "/repo/docs/secrets.md")

DENIED = (
    "./bin/replay -x",
    "sudo ./bin/bot",
    "FOO=1 collector-bsc",
    "cd x && go run ./cmd/bot -env prod",
    "timeout 5 bot",
    'bash -c "bot --env prod"',
    "echo start\nreplay",
    "nohup /srv/pb/bin/collector-binance-perp >log 2>&1 &",
    "sudo -u pb env GOMAXPROCS=4 nice -n 5 ./bin/collector-binance-spot --env prod",
    "go run cmd/replay/main.go -from 1",
    "if ./bin/bot --dry; then echo ok; fi",
    "x=$(bot)",
    # a parse error (the apostrophe) that names a guarded binary as a path-word
    "git commit -F - <<'EOF'\ndocs: don't run ./bin/bot here\nEOF",
    "go run ./cmd/replay it's",
)
ALLOWED = (
    "scripts/replay-run.sh -- ./bin/replay x",
    "scripts/replay-run.sh --mem-max 8G --cpus 4 -- ./bin/bot --env prod",
    "ls bin/bot",
    "git log -- cmd/bot",
    "bot --help",
    "./bin/collector-bsc -version",
    "go run ./cmd/replay --version",
    "command -v bot",
    "go build ./cmd/bot",
    "echo x > bot",
    "grep -n replay internal/replay/*.go",
    'git commit -m "it\'s the bot"',
    # a parse error (the apostrophe) whose only mention of bot is prose: `bot"` is not a path-word
    "git commit -F - <<'EOF'\ndocs: don't call it \"the bot\"\nEOF",
    "bash -c 'ls bin/bot'",
)


def run_all(script: Path, stdins: list[str], env: dict[str, str] | list[dict[str, str]]) -> list[tuple[int, str, str]]:
    """(rc, stdout, stderr) of one run per stdin, started together: the runs are independent.
    `env` is one environment for every run, or one per run."""
    envs = env if isinstance(env, list) else [env] * len(stdins)
    procs = [subprocess.Popen([str(script)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=e) for e in envs]
    results = []
    try:
        for proc, stdin in zip(procs, stdins):
            out, err = proc.communicate(stdin, timeout=30)
            results.append((proc.returncode, out, err))
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    return results


def payload(tool: str, **tool_input: str) -> str:
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
                       "cwd": "/repo"})


class Guards(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        self.ipc = self.tmp / "geth.ipc"
        back = os.getcwd()
        os.chdir(self.tmp)  # bind by a relative name: AF_UNIX paths stop at 108 bytes
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.bind(self.ipc.name)
        finally:
            os.chdir(back)

    def env(self, **more: str) -> dict[str, str]:
        full = {k: v for k, v in os.environ.items() if not k.startswith("BLOCKCHAIN_KIT_")}
        full["BLOCKCHAIN_KIT_IPC"] = str(self.tmp / "absent.ipc")
        full.update(more)
        return full

    def assertDenied(self, result: tuple[int, str, str], what: str) -> dict[str, str]:
        rc, out, err = result
        self.assertEqual((rc, err), (0, ""), what)
        self.assertTrue(out, f"not denied: {what!r}")
        decision = json.loads(out)
        self.assertEqual(list(decision), ["hookSpecificOutput"], what)
        self.assertEqual({k: v for k, v in decision["hookSpecificOutput"].items() if k != "permissionDecisionReason"},
                         {"hookEventName": "PreToolUse", "permissionDecision": "deny"}, what)
        return decision["hookSpecificOutput"]

    def assertAllowed(self, result: tuple[int, str, str], what: str) -> None:
        self.assertEqual(result, (0, "", ""), what)

    def assertFailsClosed(self, result: tuple[int, str, str], what: str) -> None:
        rc, out, err = result
        self.assertEqual((rc, out), (2, ""), what)
        self.assertIn("failing closed", err, what)

    # guard-secrets

    def test_every_node_and_generic_pattern_is_denied(self):
        paths = [*NODE, *GENERIC]
        results = run_all(SECRETS, [payload("Read", file_path=p) for p in paths], self.env())
        for path, result in zip(paths, results):
            with self.subTest(path=path):
                reason = self.assertDenied(result, path)["permissionDecisionReason"]
                self.assertTrue(reason.startswith(f"Blocked: '{path}' "), reason)
                self.assertIn("ask for the fact", reason)
                if path in NODE:
                    self.assertIn("geth node identity or account material", reason)
                else:
                    self.assertIn("is secret material", reason)

    def test_fixtures_and_source_are_allowed(self):
        fixtures = [f"/repo/testdata/{p.lstrip('/')}" for p in (*NODE, *GENERIC)]
        fixtures += ["testdata/nodekey", "tests/.env", "/fork/p2p/tests/server.pem"]
        paths = [*fixtures, *SOURCE]
        results = run_all(SECRETS, [payload("Edit", file_path=p) for p in paths], self.env())
        for path, result in zip(paths, results):
            with self.subTest(path=path):
                self.assertAllowed(result, path)

    def test_secrets_kill_switch_is_the_new_name_only(self):
        call = [payload("Read", file_path="/repo/.env")]
        self.assertAllowed(run_all(SECRETS, call, self.env(BLOCKCHAIN_KIT_GUARD_SECRETS="0"))[0],
                           "BLOCKCHAIN_KIT_GUARD_SECRETS=0")
        self.assertDenied(run_all(SECRETS, call, self.env(BLOCKCHAIN_KIT_NODE_SECRETS="0"))[0],
                          "the old variable is not honoured")

    def test_secrets_fails_closed(self):
        for result in run_all(SECRETS, ["not json", "[1, 2]"], self.env()):
            self.assertFailsClosed(result, "unparseable payload")

    # guard-prod-run

    def test_a_bare_run_on_the_prod_host_is_denied(self):
        results = run_all(PROD_RUN, [payload("Bash", command=c) for c in DENIED], self.env(BLOCKCHAIN_KIT_IPC=str(self.ipc)))
        for command, result in zip(DENIED, results):
            with self.subTest(command=command):
                reason = self.assertDenied(result, command)["permissionDecisionReason"]
                self.assertIn("scripts/replay-run.sh [--mem-max <N>G] [--cpus <N>] -- <binary> [args]", reason)
                self.assertIn("irreplaceable recorder log", reason)
                self.assertIn("BLOCKCHAIN_KIT_GUARD_PROD_RUN=0", reason)

    def test_the_sanctioned_path_and_mentions_are_allowed_on_the_prod_host(self):
        results = run_all(PROD_RUN, [payload("Bash", command=c) for c in ALLOWED], self.env(BLOCKCHAIN_KIT_IPC=str(self.ipc)))
        for command, result in zip(ALLOWED, results):
            with self.subTest(command=command):
                self.assertAllowed(result, command)

    def test_a_dev_host_a_non_bash_tool_an_empty_command_and_the_kill_switch_allow(self):
        plain = self.tmp / "plain.ipc"
        plain.write_text("")
        bare = payload("Bash", command="./bin/bot")
        cases = [
            ("no IPC path", bare, self.env()),
            ("a regular file at the IPC path", bare, self.env(BLOCKCHAIN_KIT_IPC=str(plain))),
            ("a non-Bash tool", payload("Read", file_path="./bin/bot"), self.env(BLOCKCHAIN_KIT_IPC=str(self.ipc))),
            ("an empty command", payload("Bash", command="  "), self.env(BLOCKCHAIN_KIT_IPC=str(self.ipc))),
            ("the kill switch", bare, self.env(BLOCKCHAIN_KIT_IPC=str(self.ipc), BLOCKCHAIN_KIT_GUARD_PROD_RUN="0")),
        ]
        results = run_all(PROD_RUN, [stdin for _, stdin, _ in cases], [env for _, _, env in cases])
        for (what, _, _), result in zip(cases, results):
            with self.subTest(case=what):
                self.assertAllowed(result, what)

    def test_prod_run_fails_closed_on_either_host(self):
        ipcs = [str(self.ipc), str(self.ipc), str(self.tmp / "absent.ipc"), str(self.tmp / "absent.ipc")]
        results = run_all(PROD_RUN, ["not json", "[1, 2]"] * 2, [self.env(BLOCKCHAIN_KIT_IPC=i) for i in ipcs])
        for ipc, result in zip(ipcs, results):
            self.assertFailsClosed(result, f"unparseable payload, IPC {ipc}")


if __name__ == "__main__":
    unittest.main()
