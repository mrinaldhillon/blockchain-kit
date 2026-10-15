"""Tests for workflows/implement.js: what the script refuses, merges, skips and reports,
with its agents answered from a scenario (tests/implement_harness.mjs). What a real agent
does with a prompt, and whether a worktree lane starts at head, is a live run.

Needs `node` on PATH; skipped without it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

KIT = Path(__file__).resolve().parent.parent
HARNESS = KIT / "tests" / "implement_harness.mjs"

HEAD = "86c3c7df66be7d76cbff7301f436652ee29957ea"
GREEN = "gate: run rc=0 t=1.2s out=/tmp/bk-gate-run.out"
RED = "gate: run rc=1 t=1.2s out=/tmp/bk-gate-run.out"


def unit(name: str, package: str) -> dict:
    return {"id": name, "brief": f"the contract of {name}", "packages": [package]}


def lane(n: int, package: str, **over: object) -> dict:
    out = {"branch": f"worktree-wf_run-{n}", "start": HEAD, "sha": f"{n}" * 40, "paths": [f"{package}/a.go"],
           "gates": [{"name": "test", "rc": 0, "line": "gate: test rc=0 t=0.1s out=/tmp/x"}], "summary": "a.go"}
    out.update(over)
    return out


def args(**over: object) -> dict:
    base = {"units": [unit("a", "internal/feeds"), unit("b", "internal/state")], "branch": "run", "head": HEAD,
            "gate": "make test-offline PKG=./internal/..."}
    base.update(over)
    return base


def answers(**over: object) -> dict:
    base = {
        "lane:a": lane(1, "internal/feeds"),
        "lane:b": lane(2, "internal/state"),
        "integrate": {"merged": ["a", "b"], "conflicted": [], "head": "f" * 40},
        "gate": {"line": GREEN, "rc": 0},
        "review": {"findings": [], "enumerated": "internal/feeds/a.go, internal/state/a.go"},
    }
    base.update(over)
    return base


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class Implement(unittest.TestCase):
    def run_script(self, arguments: dict, given: dict) -> dict:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as scenario:
            json.dump({"args": arguments, "answers": given}, scenario)
            scenario.flush()
            done = subprocess.run(["node", str(HARNESS), scenario.name], capture_output=True, text=True,
                                  timeout=30, check=False)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        return json.loads(done.stdout)

    def labels(self, ran: dict) -> list[str]:
        return [c["label"] for c in ran["calls"]]

    def assertNoWholeModule(self, prompt: str) -> None:
        """No gate in `prompt` covers the whole module: the fork's tree is the production host's."""
        for whole in ("go build ./...", "go vet ./...", "go test -count=1 <", "go test ./...", "make test", "make lint"):
            self.assertNotIn(f"-- {whole}", prompt, whole)
        self.assertIn("Never build, vet or test the whole fork", prompt)

    def test_a_clean_run_merges_gates_and_reviews(self):
        ran = self.run_script(args(), answers())
        out = ran["result"]
        self.assertEqual(self.labels(ran), ["lane:a", "lane:b", "integrate", "gate", "review"])
        self.assertEqual((out["merged"], out["conflicted"], out["handbacks"], out["stalled"]), (["a", "b"], [], [], []))
        self.assertEqual((out["gate"]["rc"], out["head"]), (0, "f" * 40))
        self.assertEqual(out["owed"], {"parity": ["b"], "read": ["a", "b"]})
        by = {c["label"]: c for c in ran["calls"]}
        self.assertEqual((by["lane:a"]["model"], by["lane:a"]["isolation"], by["lane:a"]["agentType"]),
                         ("opus", "worktree", "blockchain-kit:golang-implementer"))
        self.assertEqual((by["integrate"]["model"], by["gate"]["model"]), ("sonnet", "haiku"))
        self.assertEqual((by["review"]["model"], by["review"]["agentType"]), ("opus", "blockchain-kit:code-reviewer"))
        # the hot-path skill rides with the unit whose packages reach the hot-path set
        self.assertIn("blockchain-kit:hot-path-determinism", by["lane:b"]["prompt"])
        self.assertNotIn("blockchain-kit:hot-path-determinism", by["lane:a"]["prompt"])
        self.assertIn(f"must print {HEAD}", by["lane:a"]["prompt"])

    def test_units_sharing_a_package_are_refused_before_any_agent(self):
        shared = [unit("a", "./internal/state/..."), unit("b", "internal/state")]
        ran = self.run_script(args(units=shared), answers())
        self.assertEqual(ran["calls"], [])
        self.assertEqual(ran["result"]["error"], "units share a package")
        self.assertEqual(ran["result"]["shared"], [{"package": "internal/state", "units": ["a", "b"]}])

    def test_a_tier_above_opus_is_refused(self):
        for tiers in ({"lane": "fable"}, {"review": "claude-mythos-5"}, {"fix": "session"}):
            ran = self.run_script(args(tiers=tiers), answers())
            self.assertEqual((ran["calls"], ran["result"]["error"]), ([], "tier above opus"), tiers)
        ran = self.run_script(args(tiers={"review": "session"}), answers())
        review = next(c for c in ran["calls"] if c["label"] == "review")
        self.assertIsNone(review["model"])  # the session's tier: no override

    def test_a_lane_that_hands_back_is_not_merged(self):
        back = lane(2, "internal/state", handback="which ordering key?")
        ran = self.run_script(args(), answers(**{"lane:b": back, "integrate": {"merged": ["a"], "conflicted": [], "head": "f" * 40}}))
        out = ran["result"]
        self.assertEqual(out["merged"], ["a"])
        self.assertEqual([(h["unit"], h["branch"], h["handback"]) for h in out["handbacks"]],
                         [("b", "worktree-wf_run-2", "which ordering key?")])
        integrate = next(c for c in ran["calls"] if c["label"] == "integrate")
        self.assertIn("unit a — branch worktree-wf_run-1", integrate["prompt"])
        self.assertNotIn("unit b —", integrate["prompt"])

    def test_a_lane_that_did_not_start_at_head_is_dropped(self):
        ran = self.run_script(args(), answers(**{"lane:b": lane(2, "internal/state", start="01f5af59" + "0" * 32)}))
        dropped = [s for s in ran["result"]["stalled"] if s["unit"] == "b"]
        self.assertEqual(len(dropped), 1)
        self.assertIn("not " + HEAD, dropped[0]["reason"])
        self.assertEqual(dropped[0]["branch"], "worktree-wf_run-2")

    def test_a_conflicting_lane_is_reported_and_the_others_merge(self):
        integrated = {"merged": ["a"], "head": "f" * 40,
                      "conflicted": [{"unit": "b", "branch": "worktree-wf_run-2", "files": ["internal/x/y.go"]}]}
        ran = self.run_script(args(), answers(integrate=integrated))
        out = ran["result"]
        self.assertEqual(out["merged"], ["a"])
        self.assertEqual(out["conflicted"], [{"unit": "b", "branch": "worktree-wf_run-2", "files": ["internal/x/y.go"]}])
        self.assertIn("review", self.labels(ran))

    def test_a_red_gate_skips_review(self):
        # rc is parsed from the verdict line, never taken from the agent's own field
        ran = self.run_script(args(), answers(gate={"line": RED, "rc": 0}))
        self.assertNotIn("review", self.labels(ran))
        self.assertEqual((ran["result"]["gate"]["rc"], ran["result"]["gate"]["green"]), (1, False))
        self.assertEqual(ran["result"]["merged"], ["a", "b"])

    def test_a_dead_stage_is_stalled_with_what_it_left(self):
        ran = self.run_script(args(), answers(**{"lane:b": None}))
        dead = next(s for s in ran["result"]["stalled"] if s["unit"] == "b")
        self.assertEqual((dead["stage"], dead["reason"]), ("Lane", "the lane died"))

        ran = self.run_script(args(), answers(integrate=None))
        dead = next(s for s in ran["result"]["stalled"] if s["stage"] == "Integrate")
        self.assertEqual(dead["left"], ["a: worktree-wf_run-1 @ " + "1" * 40, "b: worktree-wf_run-2 @ " + "2" * 40])
        self.assertEqual(ran["result"]["merged"], [])

        ran = self.run_script(args(), answers(review={"__throw": "terminal API error"}))
        dead = next(s for s in ran["result"]["stalled"] if s["stage"] == "Review")
        self.assertIn("unreviewed", dead["left"])

        orphan = {"merged": ["a", "b"], "conflicted": [], "head": "f" * 40,
                  "unclaimed": [{"worktree": "/p/.claude/worktrees/wf_run-3", "branch": "worktree-wf_run-3"}]}
        ran = self.run_script(args(), answers(integrate=orphan))
        left = next(s for s in ran["result"]["stalled"] if s["reason"] == "worktrees no returned lane claims")
        self.assertEqual(left["left"][0]["branch"], "worktree-wf_run-3")

    def test_blocker_and_major_findings_get_one_fix_and_a_regate(self):
        found = [{"title": "clock read", "file": "internal/state/a.go", "line": 9, "severity": "blocker", "why": "rule 12"},
                 {"title": "test cannot fail", "file": "internal/state/a_test.go", "severity": "major", "why": "asserts nothing"},
                 {"title": "name", "file": "internal/feeds/a.go", "severity": "minor", "why": "stutter"}]
        fix = {"sha": "e" * 40, "paths": ["internal/state/a.go"], "fixed": [1]}
        ran = self.run_script(args(), answers(review={"findings": found, "enumerated": "all"}, fix=fix,
                                              **{"re-gate": {"line": GREEN, "rc": 0}}))
        out = ran["result"]
        self.assertEqual(self.labels(ran)[-2:], ["fix", "re-gate"])
        self.assertEqual([f["title"] for f in out["findings"]["fixed"]], ["clock read"])
        self.assertEqual([f["title"] for f in out["findings"]["open"]], ["test cannot fail", "name"])
        self.assertEqual((out["head"], out["gate"]["rc"], out["merged"]), ("e" * 40, 0, ["a", "b"]))
        fixer = next(c for c in ran["calls"] if c["label"] == "fix")
        self.assertIsNone(fixer["isolation"])  # the fix is on the run branch, in the session's tree
        self.assertNotIn("stutter", fixer["prompt"])

    def test_a_run_rooted_in_the_fork_runs_in_place(self):
        root = "/src/bsc-geth"
        node = "github.com/ethereum/go-ethereum"
        units = [unit("a", "eth"), unit("b", "./p2p/...")]
        given = answers(**{"lane:a": lane(1, "eth"), "lane:b": lane(2, "p2p")})
        for over in ({}, {"fork": root}, {"fork": root + "/"}):
            ran = self.run_script(args(units=units, project=root, module=node, gate=None, **over), given)
            out = ran["result"]
            # parallel worktree lanes and Integrate, as in the client
            self.assertEqual(self.labels(ran), ["lane:a", "lane:b", "integrate", "gate", "review"], over)
            by = {c["label"]: c for c in ran["calls"]}
            self.assertEqual((by["lane:a"]["isolation"], by["lane:a"]["agentType"]), ("worktree", "blockchain-kit:golang-implementer"))
            self.assertIn("You are in your own git worktree", by["lane:a"]["prompt"])
            self.assertEqual((out["merged"], out["owed"]), (["a", "b"], {"parity": [], "read": []}))
            # the fork's skills and gates: package-scoped, never the whole module
            for name in ("lane:a", "lane:b"):
                self.assertIn("blockchain-kit:fork-ext-convention", by[name]["prompt"])
                self.assertNotIn("hot-path-determinism", by[name]["prompt"])
                self.assertNoWholeModule(by[name]["prompt"])
                self.assertNotIn("-C ", by[name]["prompt"])
            self.assertIn("bk-gate test -- go test -count=1 ./eth,", by["lane:a"]["prompt"])
            self.assertIn("bk-gate build -- go build ./p2p,", by["lane:b"]["prompt"])  # exact, not ./p2p/...
            self.assertIn("then bk-gate audit -- make audit-ext", by["lane:b"]["prompt"])
            self.assertIn("no make test, no make lint", by["lane:b"]["prompt"])
            # the gate defaults to make audit-ext, run in the project's tree; the review rule is the Ext convention
            self.assertIn("  bk-gate run -- make audit-ext\n", by["gate"]["prompt"])
            self.assertIn("the Ext convention and the rebase landmines", by["review"]["prompt"])
            self.assertNotIn("bsc-fork show", by["review"]["prompt"])
            self.assertIn("git merge --no-edit", by["integrate"]["prompt"])
        self.assertIn("2 unit(s) · fork in place · tree=/src/bsc-geth", "\n".join(ran["logs"]))
        # the fix stage in place: the fork's gates over the merged units' packages, never ./...
        found = [{"title": "x", "file": "eth/a.go", "severity": "blocker", "why": "y"}]
        fix = {"sha": "e" * 40, "paths": ["eth/a.go"], "fixed": [1]}
        ran = self.run_script(args(units=units, project=root, module=node),
                              answers(**{"lane:a": lane(1, "eth"), "lane:b": lane(2, "p2p"),
                                         "review": {"findings": found, "enumerated": "all"}, "fix": fix,
                                         "re-gate": {"line": GREEN, "rc": 0}}))
        fixer = next(c for c in ran["calls"] if c["label"] == "fix")
        self.assertIn("bk-gate test -- go test -count=1 ./eth ./p2p,", fixer["prompt"])
        self.assertNoWholeModule(fixer["prompt"])
        self.assertIn("blockchain-kit:fork-ext-convention", fixer["prompt"])
        self.assertNotIn("git -C", fixer["prompt"])
        self.assertEqual(ran["result"]["head"], "e" * 40)
        # a caller's gate wins over the default
        ran = self.run_script(args(units=units, project=root, module=node, gate="go test -count=1 ./eth/..."), given)
        self.assertIn("bk-gate run -- go test -count=1 ./eth/...", next(c for c in ran["calls"] if c["label"] == "gate")["prompt"])

    def test_a_fork_root_naming_another_checkout_is_a_remote_run(self):
        # the client, naming a fork checkout elsewhere, runs serially there; so does a fork root naming another tree
        root = "/src/bsc-geth"
        for project, module in (("/src/prediction-bot", "example.com/bot"), ("/src/bsc-other", "github.com/ethereum/go-ethereum")):
            ran = self.run_script(args(project=project, module=module, fork=root, gate="x"),
                                  answers(**{"lane:a": lane(1, "internal/feeds", branch="run"),
                                             "lane:b": lane(2, "internal/state", branch="run", start="1" * 40)}))
            self.assertEqual(self.labels(ran)[:2], ["lane:a", "lane:b"], project)
            by = {c["label"]: c for c in ran["calls"]}
            self.assertIsNone(by["lane:a"]["isolation"])
            self.assertIn(f'go -C "{root}"', by["lane:a"]["prompt"])
            self.assertNotIn("integrate", self.labels(ran))
        # a run that does not say its module is a client run, and logs so
        ran = self.run_script(args(), answers())
        self.assertIn("lane:a", self.labels(ran))
        self.assertIn("no module given — whether this project is the bsc-geth fork is unchecked; the run is a client run", ran["logs"])
        self.assertIn("2 unit(s) · client ·", "\n".join(ran["logs"]))

    def test_a_fork_run_is_serial_and_stops_at_a_hand_back(self):
        fork = "/src/bsc-geth"
        three = [unit("a", "eth"), unit("b", "core"), unit("c", "miner")]
        given = answers(**{"lane:a": lane(1, "eth", branch="feat/x"),
                           "lane:b": lane(2, "core", branch="feat/x", start="1" * 40, sha="1" * 40, handback="?")})
        ran = self.run_script(args(units=three, fork=fork, gate=None, branch="feat/x"), given)
        out = ran["result"]
        self.assertEqual(self.labels(ran), ["lane:a", "lane:b", "gate", "review"])  # no lane:c, no integrate
        by = {c["label"]: c for c in ran["calls"]}
        self.assertIsNone(by["lane:a"]["isolation"])
        self.assertIn(f"must print {'1' * 40}", by["lane:b"]["prompt"])  # b starts where a ended
        self.assertIn(f'bk-gate -C "{fork}" run -- make audit-ext', by["gate"]["prompt"])
        self.assertEqual((out["merged"], [h["unit"] for h in out["handbacks"]]), (["a"], ["b"]))
        self.assertEqual([(s["unit"], s["reason"]) for s in out["stalled"]], [("c", "not started: lane b handed back")])
        self.assertEqual(out["owed"], {"parity": [], "read": []})


if __name__ == "__main__":
    unittest.main()
