"""Tests for bin/blockchain-kit-context, the SessionStart hook, bin/bsc-fork,
hooks/gofmt-on-edit and hooks/guard-node-secrets. What Claude Code does with a hook's
answer is a live probe.

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
HOOK = KIT / "bin" / "blockchain-kit-context"
FORK = KIT / "bin" / "bsc-fork"
GOFMT = KIT / "hooks" / "gofmt-on-edit"
GUARD = KIT / "hooks" / "guard-node-secrets"

PIN = "a539ea2ca63c"
SHA = PIN + "0" * 28


def client(pin: str) -> str:
    return f"""module example.com/bot

go 1.26

require github.com/ethereum/go-ethereum v1.16.3

replace (
\tgithub.com/ethereum/go-ethereum => github.com/someone/bsc-geth v0.0.0-20260921040038-{pin} // the fork
\tgithub.com/other/dep => github.com/other/fork v1.2.3
)
"""


NODE = "module github.com/ethereum/go-ethereum\n\ngo 1.27\n"
ROWS = [
    {"symbol": "MilliTimestamp", "kind": "method", "signature": "func (h *Header) MilliTimestamp() uint64",
     "file": "core/types/block.go", "line": 167, "verified": True, "note": "BEP-520."},
    {"symbol": "GetHeaderByHash", "kind": "method", "signature": "func (a) GetHeaderByHash()",
     "file": "internal/ethapi/api.go", "line": 503, "verified": True, "note": "the RPC"},
    {"symbol": "GetHeaderByHash", "kind": "method", "signature": "func (b) GetHeaderByHash()",
     "file": "core/headerchain.go", "line": 502, "verified": False, "note": "the chain"},
]


class Kit(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        for d in ("bot/.git", "bot/internal/replay", "geth/consensus/parlia", "notes/.git", "cache"):
            (self.tmp / d).mkdir(parents=True)
        (self.tmp / "bot/go.mod").write_text(client(PIN))
        (self.tmp / "geth/go.mod").write_text(NODE)
        (self.tmp / "notes/go.mod").write_text("module example.com/notes\n")
        self.index(SHA)

    def index(self, sha: str) -> None:
        at = self.tmp / "bot/docs/fork-knowledge"
        at.mkdir(parents=True, exist_ok=True)
        (at / "symbols.json").write_text(json.dumps({"fork_sha": sha, "symbols": ROWS}))

    def env(self, **more: str) -> dict[str, str]:
        drop = ("BLOCKCHAIN_KIT_", "BSC_FORK_", "GOPATH", "GOFLAGS", "GOWORK", "GIT_")
        full = {k: v for k, v in os.environ.items() if not k.startswith(drop)}
        full["GOMODCACHE"] = str(self.tmp / "cache")
        full.update(more)
        return full

    def commit(self, subject: str) -> str:
        """A commit in the fork checkout; the bot's go.mod is NOT moved to it. Returns its SHA."""
        geth = self.tmp / "geth"
        who = ("-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false")
        for args in (("init", "--quiet", "--initial-branch=mrinal/dev"), ("add", "--all"),
                     (*who, "commit", "--quiet", "--allow-empty", "--message", subject)):
            if args[0] == "init" and (geth / ".git").exists():
                continue
            subprocess.run(["git", "-C", str(geth), *args], check=True, capture_output=True, env=self.env())
        done = subprocess.run(["git", "-C", str(geth), "rev-parse", "HEAD"], check=True, capture_output=True,
                              text=True, env=self.env())
        return done.stdout.strip()

    def given(self, cwd: str, stdin: str | None = None, **env: str) -> str | None:
        call = json.dumps({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(self.tmp / cwd)})
        done = subprocess.run([str(HOOK)], input=call if stdin is None else stdin, capture_output=True,
                              text=True, env=self.env(**env), cwd=self.tmp, timeout=30, check=False)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"] if done.stdout else None

    def fork(self, *args: str, cwd: str = "bot", **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(FORK), "-C", str(self.tmp / cwd), *args], capture_output=True, text=True,
                              env=self.env(**env), cwd=self.tmp, timeout=30, check=False)

    # the session-start hook

    def test_a_fork_client_is_given_the_table_and_the_pin(self):
        text = self.given("bot/internal/replay")
        assert text is not None
        self.assertTrue(text.startswith("# Using blockchain-kit"))
        self.assertIn("`blockchain-kit:fork-node-api`", text)
        self.assertIn("`blockchain-kit:fork-development`", text)
        self.assertIn(f"at {PIN}. Fork index: current (3 symbols).\nFork checkout: none named.", text)
        self.assertLess(len(text), 10_000)  # above it Claude Code spills the context to a file

    def test_a_stale_index_is_said_at_session_start(self):
        self.index("5bed3824ce90" + "0" * 28)
        text = self.given("bot")
        assert text is not None
        self.assertIn("Fork index: STALE, built at 5bed3824ce90", text)

    def test_anything_else_is_given_nothing(self):
        self.assertIsNone(self.given("notes"))
        self.assertIsNone(self.given("geth"))  # the fork is developed from its client
        self.assertIsNone(self.given("bot", BLOCKCHAIN_KIT_CONTEXT="0"))
        self.assertIsNone(self.given("bot", stdin="not json"))

    # the checkout against the pin

    def test_the_checkout_is_placed_against_the_pin(self):
        geth = str(self.tmp / "geth")
        pinned = self.commit("feat(eth): the pinned commit")
        (self.tmp / "bot/go.mod").write_text(client(pinned[:12]))
        text = self.given("bot", BSC_FORK_PATH=geth)
        assert text is not None
        self.assertIn(f"Fork checkout: {geth} (mrinal/dev @ {pinned[:12]}, at the pin). "
                      "This build compiles the pin, not the checkout.", text)

        ahead = self.commit("feat(eth): past the pin")
        text = self.given("bot", BSC_FORK_PATH=geth)
        assert text is not None
        self.assertIn(f"(mrinal/dev @ {ahead[:12]}, 1 commit past the pin)", text)
        state = json.loads(self.fork("--json", "pin", BSC_FORK_PATH=geth).stdout)
        self.assertEqual((state["checkout"], state["compiles"]), (geth, "the pin (module cache)"))
        self.assertEqual((state["checkout_state"]["ahead"], state["checkout_state"]["dirty"]), (1, False))

    def test_go_work_makes_the_checkout_what_the_build_compiles(self):
        geth = self.tmp / "geth"
        (self.tmp / "bot/go.work").write_text("go 1.26\n\nuse (\n\t.\n\t../geth // the fork\n)\n")
        text = self.given("bot")  # no BSC_FORK_PATH: go.work names the checkout
        assert text is not None
        self.assertIn(f"Fork checkout: {geth} (not a git checkout). go.work is active: "
                      "this build compiles the CHECKOUT, not the pin.", text)
        done = self.fork("path", "go.mod")
        self.assertEqual((done.returncode, done.stdout.strip()), (0, f"{geth}/go.mod"))
        self.assertIn("a line number from the index may have moved", done.stderr)
        off = json.loads(self.fork("--json", "pin", GOWORK="off").stdout)
        self.assertEqual((off["checkout"], off["compiles"]), ("", "the pin (module cache)"))

    # bsc-fork

    def test_show_prints_every_row_of_a_name(self):
        done = self.fork("show", "GetHeaderByHash")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("internal/ethapi/api.go:503", done.stdout)
        self.assertIn("core/headerchain.go:502", done.stdout)
        self.assertIn("UNVERIFIED", done.stdout)

    def test_a_name_not_in_the_index_is_exit_1_with_the_nearest(self):
        done = self.fork("show", "MilliTimestam")
        self.assertEqual((done.returncode, done.stdout), (1, ""))
        self.assertIn("Nearest: MilliTimestamp", done.stderr)

    def test_check_is_exit_1_when_the_index_is_stale(self):
        self.assertEqual(self.fork("check").returncode, 0)
        self.index("5bed3824ce90" + "0" * 28)
        done = self.fork("--json", "check")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(json.loads(done.stdout)["state"], "stale")
        self.assertIn("unconfirmed at the pin", self.fork("show", "MilliTimestamp").stderr)

    def test_path_resolves_in_the_pinned_tree_and_nowhere_else(self):
        tree = self.tmp / "cache" / f"github.com/someone/bsc-geth@v0.0.0-20260921040038-{PIN}"
        (tree / "core/types").mkdir(parents=True)
        (tree / "core/types/block.go").write_text("package types\n")
        geth = str(self.tmp / "geth")
        for which in ((), ("--pinned",)):  # a checkout that is named is not what the build compiles
            done = self.fork("path", *which, "core/types/block.go:167", BSC_FORK_PATH=geth)
            self.assertEqual((done.returncode, done.stdout.strip()), (0, f"{tree}/core/types/block.go:167"))
        self.assertEqual(self.fork("path", "core/absent.go").returncode, 1)
        self.assertEqual(self.fork("path", "../../../etc/passwd").returncode, 2)
        done = self.fork("path", "--checkout", "go.mod", BSC_FORK_PATH=geth)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, f"{geth}/go.mod"))
        self.assertEqual(self.fork("path", "--checkout", "go.mod").returncode, 1)  # none named

    def test_outside_a_fork_client_is_exit_2(self):
        for cwd in ("geth", "notes"):
            done = self.fork("pin", cwd=cwd)
            self.assertEqual(done.returncode, 2)
            self.assertIn("not a fork client", done.stderr)

    # gofmt-on-edit

    def edit(self, path: Path, **env: str) -> subprocess.CompletedProcess[str]:
        call = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Edit",
                           "tool_input": {"file_path": str(path)}})
        return subprocess.run([str(GOFMT)], input=call, capture_output=True, text=True, timeout=30, check=False,
                              env=self.env(CLAUDE_PROJECT_DIR=str(self.tmp / "bot"), **env))

    def test_gofmt_formats_a_go_file_in_the_project_and_says_nothing(self):
        recorder = self.tmp / "fmt"
        recorder.write_text('#!/bin/sh\necho "$@" >>"$0.calls"\n')
        recorder.chmod(0o755)
        inside, outside = self.tmp / "bot/internal/replay/a.go", self.tmp / "notes/a.go"
        for path in (inside, outside, self.tmp / "bot/README.md"):
            done = self.edit(path, BLOCKCHAIN_KIT_GOFMT_BIN=str(recorder))
            self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertEqual(Path(f"{recorder}.calls").read_text(), f"-l -w {inside}\n")

    def test_gofmt_formats_a_go_file_in_the_fork_checkout_the_project_names(self):
        recorder = self.tmp / "fmt"
        recorder.write_text('#!/bin/sh\necho "$@" >>"$0.calls"\n')
        recorder.chmod(0o755)
        fork, other = self.tmp / "geth/consensus/parlia/a_ext.go", self.tmp / "notes/a.go"
        for path in (fork, other):
            done = self.edit(path, BLOCKCHAIN_KIT_GOFMT_BIN=str(recorder), BSC_FORK_PATH=str(self.tmp / "geth"))
            self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertEqual(Path(f"{recorder}.calls").read_text(), f"-l -w {fork}\n")
        # a directory that is named and is not the fork is not formatted
        done = self.edit(other, BLOCKCHAIN_KIT_GOFMT_BIN=str(recorder), BSC_FORK_PATH=str(self.tmp / "notes"))
        self.assertEqual(Path(f"{recorder}.calls").read_text(), f"-l -w {fork}\n")

    # guard-node-secrets

    def read(self, path: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        call = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": path}})
        return subprocess.run([str(GUARD)], input=call if stdin is None else stdin, capture_output=True, text=True,
                              timeout=30, check=False, env=self.env())

    def test_node_identity_and_account_material_is_denied(self):
        for path in ("/data/geth/nodekey", "/data/geth/JWTSecret", "/data/engine.jwt",
                     "/data/keystore/UTC--2026-01-01T00-00-00.000000000Z--00aa"):
            done = self.read(path)
            self.assertEqual(done.returncode, 0, done.stderr)
            out = json.loads(done.stdout)["hookSpecificOutput"]
            self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"), path)
        for path in ("/fork/accounts/keystore/keystore.go", "/fork/p2p/testdata/nodekey",
                     "/fork/cmd/utils/nodekey_ext.go", "/bot/internal/state/a.go"):
            done = self.read(path)
            self.assertEqual((done.returncode, done.stdout), (0, ""), path)

    def test_the_guard_fails_closed(self):
        done = self.read("", stdin="not json")
        self.assertEqual((done.returncode, done.stdout), (2, ""))
        self.assertIn("failing closed", done.stderr)

    def test_a_formatter_that_fails_is_said_once(self):
        done = self.edit(self.tmp / "bot/a.go", BLOCKCHAIN_KIT_GOFMT_BIN=str(self.tmp / "absent"))
        self.assertEqual(done.returncode, 0)
        out = json.loads(done.stdout)["hookSpecificOutput"]
        self.assertEqual(out, {"hookEventName": "PostToolUse", "additionalContext": "gofmt: not found"})


if __name__ == "__main__":
    unittest.main()
