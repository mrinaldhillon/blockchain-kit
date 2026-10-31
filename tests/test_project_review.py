"""Tests for workflows/project-review.js: what the script refuses, which tier each seat runs at,
that every seat is pointed at the repository's guide, and what it keeps, with its agents answered
from a scenario (tests/implement_harness.mjs). What a real seat does with a prompt is a live run.

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
SEAT = "blockchain-kit:review-seat"
GUIDE = "docs/project-review.md"
FINDERS = {"find:conformance": "fable", "find:domain": "fable", "find:numbers": "fable", "find:linesA": "opus",
           "find:linesB": "opus", "find:tracer": "opus", "find:tests": "opus", "find:quality": "sonnet"}


def args(**over: object) -> dict:
    base = {"project": "/srv/repo", "head": "b" * 40, "guide": GUIDE, "module": "example.com/bot"}
    base.update(over)
    return base


def intent(**over: object) -> dict:
    out = {"sources": ["docs/a.md"], "contract": [{"id": "C1", "behaviour": "a gap fails loud", "source": "docs/a.md:1"}],
           "numbers": [{"quantity": "stake", "documented": "1", "where": "docs/a.md:2", "status": "measured"}],
           "sanity": [], "areas": [{"name": "one", "paths": ["pkg/one"], "items": ["C1"]},
                                   {"name": "two", "paths": ["pkg/two"], "items": ["C1"]}],
           "skills": ["blockchain-kit:record-format"]}
    out.update(over)
    return out


def candidate(title: str, line: int, severity: str = "major", file: str = "pkg/one/a.go") -> dict:
    return {"title": title, "file": file, "line": line, "severity": severity, "item": "C1", "why": "w", "scenario": "s"}


def finder(*cands: dict) -> dict:
    return {"candidates": list(cands), "covered": "pkg/one: read whole"}


def verdict(cid: str, word: str, **over: object) -> dict:
    return {"id": cid, "verdict": word, "reason": "pkg/one/a.go:9 says so", **over}


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class ProjectReview(unittest.TestCase):
    def run_script(self, arguments: dict, given: dict) -> dict:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as scenario:
            json.dump({"workflow": "project-review", "args": arguments, "answers": given}, scenario)
            scenario.flush()
            done = subprocess.run(["node", str(HARNESS), scenario.name], capture_output=True, text=True,
                                  timeout=30, check=False)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        return json.loads(done.stdout)

    def test_it_refuses_before_any_seat(self):
        for what, arguments, error in [
            ("no head", args(head=None), "project, head and guide are required"),
            ("no guide", args(guide=""), "project, head and guide are required"),
            ("the session tier", args(tiers={"lines": "session"}), "tier not allowed"),
            ("mythos", args(tiers={"intent": "mythos"}), "tier not allowed"),
            ("an unknown tier", args(tiers={"check": "gpt"}), "tier not allowed"),
            ("an unknown seat", args(tiers={"checker": "sonnet"}), "tier not allowed"),
        ]:
            with self.subTest(case=what):
                ran = self.run_script(arguments, {})
                self.assertEqual((ran["result"]["error"], ran["calls"]), (error, []))

    def test_each_seat_runs_at_its_tier_and_is_pointed_at_the_guide(self):
        given = {"intent": intent(), "find:linesA": finder(candidate("x", 5)),
                 "check:pkg/one/a.go": {"verdicts": [verdict("K1", "CONFIRMED")]}}
        ran = self.run_script(args(), given)
        models = {c["label"]: c["model"] for c in ran["calls"]}
        self.assertEqual(models, {"intent": "fable", **FINDERS, "check:pkg/one/a.go": "fable"})
        self.assertEqual({c["agentType"] for c in ran["calls"]}, {SEAT})
        for call in ran["calls"]:
            with self.subTest(seat=call["label"]):
                self.assertIn(f"/srv/repo/{GUIDE}", call["prompt"])
        self.assertEqual(ran["result"]["seats"], {"intent": 1, "find": 8, "check": 1})

    def test_the_script_holds_the_method_and_no_repository_fact(self):
        # A repository's paths and rule numbers go stale here unseen: they live in its guide
        body = (KIT / "workflows" / "project-review.js").read_text().split("const SEAT", 1)[1]
        for fact in ("prediction-bot", "internal/", "docs/", "rule 47", "msg.value"):
            with self.subTest(fact=fact):
                self.assertNotIn(fact, body)

    def test_a_contract_or_areas_missing_stops_before_the_finders(self):
        for what, answer, error in [
            ("a dead seat", None, "the intent seat returned nothing"),
            ("an unreadable guide", intent(contract=[], degraded="no guide"), "the intent seat found no contract in the docs"),
            ("no areas", intent(areas=[]), "the intent seat named no areas to review"),
        ]:
            with self.subTest(case=what):
                ran = self.run_script(args(), {"intent": answer})
                self.assertEqual(ran["result"]["error"], error)
                self.assertEqual([c["label"] for c in ran["calls"]], ["intent"])

    def test_verdicts_sort_the_candidates(self):
        given = {
            "intent": intent(sanity=[candidate("unsound", 0, "blocker", file="")]),
            "find:conformance": finder(candidate("real", 7), candidate("same as real", 9), candidate("wrong", 11)),
            "find:numbers": finder(candidate("no checker", 3, file="pkg/two/b.go")),
            "check:contract": {"verdicts": [verdict("K1", "PLAUSIBLE")]},
            "check:pkg/one/a.go": {"verdicts": [verdict("K2", "CONFIRMED"), verdict("K3", "CONFIRMED", duplicateOf="K2"),
                                                verdict("K4", "REFUTED"), verdict("K5", "CONFIRMED")]},
        }
        out = self.run_script(args(), given)["result"]
        # K5 was another file's: a checker's verdict counts only for what it was given
        self.assertEqual([f["title"] for f in out["findings"]], ["unsound", "real"])  # a blocker outranks a major
        self.assertEqual([f["n"] for f in out["findings"]], [1, 2])
        self.assertEqual([r["title"] for r in out["refuted"]], ["wrong"])
        self.assertEqual(out["merged"], [{"id": "K3", "title": "same as real", "into": "K2", "angle": "conformance"}])
        self.assertEqual([u["title"] for u in out["unchecked"]], ["no checker"])

    def test_a_duplicate_merges_only_into_a_finding_that_stands(self):
        given = {"intent": intent(), "find:conformance": finder(candidate("a", 1), candidate("b", 2), candidate("c", 3), candidate("d", 4)),
                 "check:pkg/one/a.go": {"verdicts": [verdict("K1", "CONFIRMED", duplicateOf="K2"), verdict("K2", "CONFIRMED", duplicateOf="K1"),
                                                     verdict("K3", "REFUTED"), verdict("K4", "CONFIRMED", duplicateOf="K3")]}}
        out = self.run_script(args(), given)["result"]
        self.assertEqual([f["title"] for f in out["findings"]], ["a", "b", "d"])  # no mutual pair or refuted target loses one
        self.assertEqual(out["merged"], [])

    def test_the_cap_and_a_dead_finder_are_reported(self):
        given = {"intent": intent(), "find:conformance": finder(*(candidate(f"c{n}", n) for n in range(1, 11)))}
        out = self.run_script(args(maxChecks=3), given)["result"]
        self.assertEqual([u["title"] for u in out["unchecked"] if u["reason"] == "over maxChecks"],
                         [f"c{n}" for n in range(4, 11)])
        dead = next(c for c in out["coverage"] if c["angle"] == "tracer")
        self.assertIn("not covered", dead["degraded"])
        self.assertIn("not covered", " ".join(out["degraded"]))


if __name__ == "__main__":
    unittest.main()
