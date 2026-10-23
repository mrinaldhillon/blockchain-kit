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
A = "internal/recorder/a.go"
B = "internal/recorder/b.go"
CONF = "find:conformance"
THREE = [CONF, "find:lines+tracer", "find:domain+tests+quality"]


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


def candidate(title: str, line: int, severity: str = "major", file: str = A) -> dict:
    return {"title": title, "file": file, "line": line, "severity": severity, "item": "C1", "why": "w", "scenario": "s"}


def finder(*cands: dict) -> dict:
    return {"candidates": list(cands), "covered": "internal/recorder/a.go: read whole"}


def verdict(cid: str, word: str, severity: str | None = None, **over: object) -> dict:
    out = {"id": cid, "verdict": word, "reason": "internal/recorder/a.go:9 says so"}
    if severity:
        out["severity"] = severity
    out.update(over)
    return out


def verdicts(*items: dict) -> dict:
    return {"verdicts": list(items)}


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
            ("fable for a pattern finder", args(tiers={"find": "fable"}), "tier above opus"),
            ("fable for a checker", args(tiers={"check": "fable"}), "tier above opus"),
            ("the session tier", args(tiers={"intent": "session"}), "tier above opus"),
            ("mythos, even for intent", args(tiers={"intent": "mythos"}), "tier above opus"),
        ]:
            with self.subTest(case=what):
                ran = self.run_script(arguments, {})
                self.assertEqual(ran["result"]["error"], error)
                self.assertEqual(ran["calls"], [])

    def test_a_dead_intent_seat_ends_the_run(self):
        ran = self.run_script(args(), {"intent": None})
        self.assertEqual(ran["result"]["error"], "the intent seat returned nothing")
        self.assertEqual(self.labels(ran), ["intent"])

    def test_a_contract_in_doubt_pauses_after_intent(self):
        blocker = {"title": "no restart path", "severity": "blocker", "why": "w", "scenario": "s"}
        for what, seat, why in [
            ("derived", intent(derived=True), ["no source stated the contract: it was worked out from the diff"]),
            ("empty", intent(contract=[]), ["no source stated the contract: it was worked out from the diff"]),
            ("a blocker in its logic", intent(sanity=[blocker]), ["the logic itself: no restart path"]),
        ]:
            with self.subTest(case=what):
                ran = self.run_script(args(), {"intent": seat})
                out = ran["result"]
                self.assertEqual(self.labels(ran), ["intent"])
                self.assertEqual((out["paused"], out["why"]), (True, why))
                self.assertEqual(out["sanity"], seat["sanity"])
                self.assertIn("proceed: true", out["next"])
                gone_on = self.run_script(args(proceed=True), {"intent": seat})
                self.assertEqual(self.labels(gone_on)[:4], ["intent", *THREE])  # then the sanity findings' checker
        major = {**blocker, "severity": "major"}
        self.assertEqual(self.labels(self.run_script(args(), {"intent": intent(sanity=[major])}))[:2], ["intent", CONF])

    def test_the_finder_count_follows_the_diff_size(self):
        for lines, finders in [
            (40, THREE),
            (300, THREE),
            (400, [CONF, "find:lines+tracer", "find:domain", "find:tests+quality"]),
            (600, [CONF, "find:lines", "find:tracer", "find:domain", "find:tests+quality"]),
            (2000, [CONF, "find:lines", "find:tracer", "find:domain", "find:tests", "find:quality"]),
        ]:
            with self.subTest(lines=lines):
                ran = self.run_script(args(), {"intent": intent(lines)})
                self.assertEqual(self.labels(ran), ["intent", *finders])
                self.assertEqual(ran["result"]["seats"], {"intent": 1, "find": len(finders), "check": 0})

    def test_fable_reads_the_intent_and_the_conformance_opus_the_rest(self):
        given = {"intent": intent(), CONF: finder(candidate("x", 5)), "check:" + A: verdicts(verdict("K1", "CONFIRMED"))}
        ran = self.run_script(args(), given)
        self.assertEqual({c["agentType"] for c in ran["calls"]}, {SEAT})
        self.assertEqual([(c["label"], c["model"]) for c in ran["calls"]],
                         [("intent", "fable"), (CONF, "fable"), (THREE[1], "opus"), (THREE[2], "opus"),
                          ("check:" + A, "opus")])
        self.assertEqual(ran["phases"], ["Intent", "Find", "Check"])
        cheap = self.run_script(args(tiers={"intent": "opus", "conformance": "opus", "check": "sonnet"}), given)
        self.assertEqual([c["model"] for c in cheap["calls"]], ["opus", "opus", "opus", "opus", "sonnet"])

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
        prompt = self.prompt(self.run_script(args(), given), CONF)
        self.assertIn("Contract against code, both ways", prompt)
        self.assertIn("C1. a gap fails loud", prompt)
        self.assertIn("do not raise them again:\n- no reorg handling", prompt)
        self.assertIn("before judging: blockchain-kit:go, blockchain-kit:record-format.", prompt)
        self.assertNotIn("a hypothesis, not a spec", prompt)
        derived = self.prompt(self.run_script(args(proceed=True), {"intent": intent(derived=True)}), THREE[1])
        self.assertIn("a hypothesis, not a spec", derived)

    def test_the_mode_picks_the_domain_angle(self):
        client = self.prompt(self.run_script(args(), {"intent": intent()}), THREE[2])
        self.assertIn("docs/discipline.md` rules 6, 12, 14, 15", client)
        self.assertIn("rule 47", client)
        self.assertNotIn("Ext convention", client)
        fork = self.prompt(self.run_script(args(module="github.com/ethereum/go-ethereum", project="/srv/bsc-geth/"),
                                           {"intent": intent()}), THREE[2])
        self.assertIn("The Ext convention", fork)
        self.assertIn("blockchain-kit:go, blockchain-kit:fork-ext-convention, blockchain-kit:record-format.", fork)
        self.assertIn("/srv/bsc-geth/docs/fork/README.md", fork)
        self.assertNotIn("rule 47", fork)
        self.assertNotIn("discipline.md", fork)

    def test_one_checker_per_file_decides_what_stands(self):
        given = {
            "intent": intent(sanity=[{"title": "no restart path", "severity": "blocker", "why": "w", "scenario": "s"}]),
            CONF: finder(candidate("minor one", 30, "minor"), candidate("plausible", 20), candidate("refuted", 10)),
            THREE[1]: finder(candidate("confirmed", 40), candidate("dead checker", 50, "minor", file=B)),
        }
        # ids run most severe first: K1 the sanity blocker; K2..K4 the majors in finder order; K5, K6 the minors
        given.update({
            "check:contract": verdicts(verdict("K1", "CONFIRMED")),
            "check:" + A: verdicts(verdict("K2", "PLAUSIBLE"), verdict("K3", "REFUTED"), verdict("K4", "CONFIRMED"),
                                   verdict("K5", "confirmed", "major"), verdict("K6", "CONFIRMED")),
            "check:" + B: None,
        })
        ran = self.run_script(args(proceed=True), given)
        self.assertEqual([lbl for lbl in self.labels(ran) if lbl.startswith("check")],
                         ["check:contract", "check:" + A, "check:" + B])
        a_prompt = self.prompt(ran, "check:" + A)
        self.assertLess(a_prompt.index("K3. refuted"), a_prompt.index("K2. plausible"))  # by line within the file
        self.assertIn("before judging: blockchain-kit:go, blockchain-kit:record-format.", a_prompt)
        out = ran["result"]
        self.assertEqual([(f["n"], f["title"], f["severity"], f["verdict"]) for f in out["findings"]], [
            (1, "no restart path", "blocker", "CONFIRMED"),
            (2, "confirmed", "major", "CONFIRMED"),
            (3, "minor one", "major", "CONFIRMED"),
            (4, "plausible", "major", "PLAUSIBLE"),
        ])
        self.assertEqual([r["title"] for r in out["refuted"]], ["refuted"])
        # K6's verdict came from the wrong file's checker and is ignored; b.go's checker died
        self.assertEqual([u["title"] for u in out["unchecked"]], ["dead checker"])
        self.assertEqual(out["seats"], {"intent": 1, "find": 3, "check": 3})
        self.assertEqual(out["contract"], {"sources": ["PR #1022"], "items": intent()["contract"], "derived": False})

    def test_the_checker_marks_duplicates_not_the_line(self):
        given = {"intent": intent(), CONF: finder(candidate("off by one", 7), candidate("same off by one", 9)),
                 THREE[2]: finder(candidate("needless copy", 7, "minor")),
                 "check:" + A: verdicts(verdict("K1", "CONFIRMED"), verdict("K2", "CONFIRMED", duplicateOf="K1"),
                                        verdict("K3", "CONFIRMED"))}
        out = self.run_script(args(), given)["result"]
        self.assertEqual([(f["title"], f["angles"]) for f in out["findings"]],
                         [("off by one", ["conformance"]), ("needless copy", ["domain+tests+quality"])])
        self.assertEqual(out["merged"], [{"id": "K2", "title": "same off by one", "into": "K1", "angle": "conformance"}])

    def test_a_file_with_many_candidates_is_split_and_the_total_capped(self):
        many = {"intent": intent(), CONF: finder(*(candidate(f"c{n}", n) for n in range(1, 11)))}
        ran = self.run_script(args(), many)
        self.assertEqual([lbl for lbl in self.labels(ran) if lbl.startswith("check")],
                         ["check:" + A + "#1", "check:" + A + "#2"])
        self.assertIn("K8. c8", self.prompt(ran, "check:" + A + "#1"))
        self.assertIn("K9. c9", self.prompt(ran, "check:" + A + "#2"))
        capped = self.run_script(args(maxChecks=3), many)["result"]
        self.assertEqual(capped["seats"]["check"], 1)
        self.assertEqual([u["title"] for u in capped["unchecked"] if u["reason"] == "over maxChecks"],
                         [f"c{n}" for n in range(4, 11)])

    def test_a_dead_finder_is_a_coverage_hole(self):
        out = self.run_script(args(), {"intent": intent(), CONF: finder(), THREE[1]: finder()})["result"]
        self.assertEqual(out["coverage"][2]["angles"], ["domain", "tests", "quality"])
        self.assertIn("were not covered", out["coverage"][2]["degraded"])
        self.assertIn("were not covered", " ".join(out["degraded"]))

if __name__ == "__main__":
    unittest.main()
