"""Tests for workflows/review.js: what the script refuses, how many finders it seats, which
angles it briefs, and what it keeps, with its agents answered from a scenario
(tests/implement_harness.mjs). What a real seat does with a prompt is a live run.

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
TWO = ["find:conformance+lines+tracer", "find:domain+tests+quality"]


def args(**over: object) -> dict:
    base = {"base": "a" * 40, "head": "b" * 40, "pr": 1022, "project": "/srv/bot", "module": "example.com/bot"}
    base.update(over)
    return base


def intent(lines: int = 100, **over: object) -> dict:
    out = {"sources": ["PR #1022"], "contract": [{"id": "C1", "behaviour": "a gap fails loud", "source": "PR #1022"}],
           "derived": False, "sanity": [], "skills": ["blockchain-kit:record-format"], "files": 3, "lines": lines,
           "paths": ["internal/recorder/a.go"]}
    out.update(over)
    return out


def candidate(title: str, line: int, severity: str = "major", file: str = "internal/recorder/a.go") -> dict:
    return {"title": title, "file": file, "line": line, "severity": severity, "item": "C1", "why": "w", "scenario": "s"}


def finder(*cands: dict) -> dict:
    return {"candidates": list(cands), "covered": "internal/recorder/a.go: read whole"}


def verdict(word: str, severity: str | None = None) -> dict:
    out = {"verdict": word, "reason": "internal/recorder/a.go:9 says so"}
    if severity:
        out["severity"] = severity
    return out


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class Review(unittest.TestCase):
    def run_script(self, arguments: dict, given: dict) -> dict:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as scenario:
            json.dump({"workflow": "review", "args": arguments, "answers": given}, scenario)
            scenario.flush()
            done = subprocess.run(["node", str(HARNESS), scenario.name], capture_output=True, text=True,
                                  timeout=30, check=False)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        return json.loads(done.stdout)

    def labels(self, ran: dict) -> list[str]:
        return [c["label"] for c in ran["calls"]]

    def prompt(self, ran: dict, label: str) -> str:
        return next(c["prompt"] for c in ran["calls"] if c["label"] == label)

    def test_it_refuses_before_any_seat(self):
        for what, arguments, error in [
            ("no head", args(head=None), "base and head are required"),
            ("no base", args(base=""), "base and head are required"),
            ("fable by name", args(tiers={"find": "fable"}), "tier above opus"),
            ("the session tier", args(tiers={"check": "session"}), "tier above opus"),
        ]:
            with self.subTest(case=what):
                ran = self.run_script(arguments, {})
                self.assertEqual(ran["result"]["error"], error)
                self.assertEqual(ran["calls"], [])

    def test_a_dead_intent_seat_ends_the_run(self):
        ran = self.run_script(args(), {"intent": None})
        self.assertEqual(ran["result"]["error"], "the intent seat returned nothing")
        self.assertEqual(self.labels(ran), ["intent"])

    def test_the_finder_count_follows_the_diff_size(self):
        for lines, finders in [
            (40, TWO),
            (100, TWO),
            (400, ["find:conformance+lines", "find:tracer+domain", "find:tests+quality"]),
            (600, ["find:conformance", "find:lines+tracer", "find:domain", "find:tests+quality"]),
            (2000, ["find:conformance", "find:lines", "find:tracer", "find:domain", "find:tests", "find:quality"]),
        ]:
            with self.subTest(lines=lines):
                ran = self.run_script(args(), {"intent": intent(lines)})
                self.assertEqual(self.labels(ran), ["intent", *finders])
                self.assertEqual(ran["result"]["seats"], {"intent": 1, "find": len(finders), "check": 0})

    def test_every_seat_is_the_read_only_agent_at_a_named_tier(self):
        given = {"intent": intent(), TWO[0]: finder(candidate("x", 5)), TWO[1]: finder(), "check:1": verdict("CONFIRMED")}
        ran = self.run_script(args(), given)
        self.assertEqual({c["agentType"] for c in ran["calls"]}, {SEAT})
        self.assertEqual([(c["label"], c["model"]) for c in ran["calls"]],
                         [("intent", "opus"), (TWO[0], "opus"), (TWO[1], "opus"), ("check:1", "opus")])
        self.assertEqual(ran["phases"], ["Intent", "Find", "Check"])
        tiered = self.run_script(args(tiers={"check": "sonnet"}), given)
        self.assertEqual(tiered["calls"][-1]["model"], "sonnet")

    def test_the_intent_seat_reads_the_sources_before_the_code(self):
        ran = self.run_script(args(), {"intent": None})
        prompt = self.prompt(ran, "intent")
        self.assertIn("gh pr view 1022 --json title,body,closingIssuesReferences", prompt)
        self.assertIn("is its author's belief", prompt)
        self.assertIn("Is that logic sound?", prompt)
        brief = self.run_script(args(pr=None, contract="the lane must X"), {"intent": None})
        self.assertIn("## The brief\n\nthe lane must X", self.prompt(brief, "intent"))
        self.assertNotIn("gh pr view", self.prompt(brief, "intent"))

    def test_the_finders_work_against_the_contract(self):
        given = {"intent": intent(sanity=[{"title": "no reorg handling", "severity": "major", "why": "w", "scenario": "s"}])}
        prompt = self.prompt(self.run_script(args(), given), TWO[0])
        self.assertIn("C1. a gap fails loud", prompt)
        self.assertIn("do not raise them again:\n- no reorg handling", prompt)
        self.assertIn("before judging: blockchain-kit:go, blockchain-kit:record-format.", prompt)
        self.assertNotIn("a hypothesis, not a spec", prompt)
        derived = self.prompt(self.run_script(args(), {"intent": intent(derived=True)}), TWO[0])
        self.assertIn("a hypothesis, not a spec", derived)

    def test_the_mode_picks_the_domain_angle(self):
        client = self.prompt(self.run_script(args(), {"intent": intent()}), TWO[1])
        self.assertIn("docs/discipline.md` rules 6, 12, 14, 15", client)
        self.assertIn("rule 47", client)
        self.assertNotIn("Ext convention", client)
        fork = self.prompt(self.run_script(args(module="github.com/ethereum/go-ethereum", project="/srv/bsc-geth/"),
                                           {"intent": intent()}), TWO[1])
        self.assertIn("The Ext convention", fork)
        self.assertIn("blockchain-kit:go, blockchain-kit:fork-ext-convention, blockchain-kit:record-format.", fork)
        self.assertIn("/srv/bsc-geth/docs/fork/README.md", fork)
        self.assertNotIn("rule 47", fork)
        self.assertNotIn("discipline.md", fork)

    def test_a_checker_decides_what_stands(self):
        given = {
            "intent": intent(sanity=[{"title": "no restart path", "severity": "blocker", "why": "w", "scenario": "s"}]),
            TWO[0]: finder(candidate("minor one", 30, "minor"), candidate("plausible", 20), candidate("refuted", 10)),
            TWO[1]: finder(candidate("confirmed", 40), candidate("dead checker", 50, "minor")),
        }
        # checks run most severe first: the sanity blocker, then the majors in finder order, then the minors
        given.update({"check:1": verdict("CONFIRMED"), "check:2": verdict("PLAUSIBLE"), "check:3": verdict("REFUTED"),
                      "check:4": verdict("CONFIRMED"), "check:5": verdict("confirmed", "major"), "check:6": None})
        out = self.run_script(args(), given)["result"]
        self.assertEqual([(f["n"], f["title"], f["severity"], f["verdict"]) for f in out["findings"]], [
            (1, "no restart path", "blocker", "CONFIRMED"),
            (2, "confirmed", "major", "CONFIRMED"),
            (3, "minor one", "major", "CONFIRMED"),
            (4, "plausible", "major", "PLAUSIBLE"),
        ])
        self.assertEqual([r["title"] for r in out["refuted"]], ["refuted"])
        self.assertEqual([u["title"] for u in out["unchecked"]], ["dead checker"])
        self.assertEqual(out["contract"], {"sources": ["PR #1022"], "items": intent()["contract"], "derived": False})

    def test_one_line_is_checked_once(self):
        given = {"intent": intent(), TWO[0]: finder(candidate("off by one", 7)),
                 TWO[1]: finder(candidate("needless copy", 7, "minor"), candidate("elsewhere", 7, file="b.go")),
                 "check:1": verdict("CONFIRMED"), "check:2": verdict("CONFIRMED")}
        ran = self.run_script(args(), given)
        self.assertEqual([lbl for lbl in self.labels(ran) if lbl.startswith("check")], ["check:1", "check:2"])
        self.assertIn("Also raised at that line: needless copy", self.prompt(ran, "check:1"))
        self.assertIn("before judging: blockchain-kit:go, blockchain-kit:record-format.", self.prompt(ran, "check:1"))
        self.assertEqual(ran["result"]["findings"][0]["angles"], ["conformance+lines+tracer", "domain+tests+quality"])

    def test_checks_stop_at_max_checks(self):
        given = {"intent": intent(), TWO[0]: finder(*(candidate(f"c{n}", n) for n in range(1, 6))), TWO[1]: finder(),
                 **{f"check:{n}": verdict("CONFIRMED") for n in range(1, 4)}}
        out = self.run_script(args(maxChecks=3), given)
        self.assertEqual(out["result"]["seats"]["check"], 3)
        self.assertEqual([u["title"] for u in out["result"]["unchecked"]], ["c4", "c5"])

    def test_a_dead_finder_is_a_coverage_hole(self):
        out = self.run_script(args(), {"intent": intent(), TWO[0]: finder()})["result"]
        self.assertEqual(out["coverage"][1]["angles"], ["domain", "tests", "quality"])
        self.assertIn("were not covered", out["coverage"][1]["degraded"])
        self.assertIn("were not covered", " ".join(out["degraded"]))


if __name__ == "__main__":
    unittest.main()
