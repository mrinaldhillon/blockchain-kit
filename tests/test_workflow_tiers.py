"""Tests for hooks/workflow-tiers: the PreToolUse deny of a workflow script whose agent()
calls leave `model` unset.

The hook is driven as a subprocess with a hook payload on stdin. Whether Claude Code
honours the deny is a live probe, not run here.

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
HOOK = KIT / "hooks" / "workflow-tiers"
META = "export const meta = { name: 'probe', description: 'a probe' }\n"


def payload(tool: str = "Workflow", **tool_input: object) -> str:
    return json.dumps({"tool_name": tool, "tool_input": tool_input})


class WorkflowTiersTest(unittest.TestCase):
    def run_hook(self, stdin: str, **env: str) -> tuple[int, str, str]:
        got = subprocess.run([str(HOOK)], input=stdin, capture_output=True, text=True, timeout=30,
                             env={**os.environ, **env}, check=False)
        return got.returncode, got.stdout, got.stderr

    def denied(self, script: str) -> str:
        """The deny reason for `script` sent inline."""
        rc, out, err = self.run_hook(payload(script=META + script))
        self.assertEqual(rc, 0, err)
        self.assertTrue(out, f"allowed: {script!r}")
        body = json.loads(out)["hookSpecificOutput"]
        self.assertEqual((body["hookEventName"], body["permissionDecision"]), ("PreToolUse", "deny"))
        return body["permissionDecisionReason"]

    def allowed(self, script: str) -> None:
        rc, out, err = self.run_hook(payload(script=META + script))
        self.assertEqual((rc, out), (0, ""), f"{err}\ndenied: {script!r}")

    def test_a_call_with_no_options_is_denied(self):
        reason = self.denied("const last = await agent('build segdump and dump the last record')\nreturn last")
        self.assertIn("1 agent() call leaves `model` unset", reason)
        self.assertIn("line 2: agent('build segdump and dump the last record')", reason)

    def test_options_without_model_are_denied_and_every_call_is_listed(self):
        reason = self.denied(
            "const S = { type: 'object', properties: {} }\n"
            "const out = await pipeline(ITEMS,\n"
            "  (it) => agent(`measure ${it}`, { label: `measure:${it}`, phase: 'Measure', schema: S, effort: 'low' }),\n"
            "  (r, it) => agent('verify ' + it, { label: 'verify', schema: S }).then((v) => ({ ...r, v })))\n"
            "return out")
        self.assertIn("2 agent() calls leave `model` unset", reason)
        self.assertIn("line 4: agent(`measure ${it}`, { label: `measure:${it}`, phase...)", reason)
        self.assertIn("line 5: agent('verify ' + it, { label: 'verify', schema: S })", reason)

    def test_the_reason_states_the_rule_and_the_switch(self):
        reason = self.denied("await agent('x')")
        for text in ("working-here, Tiers and dispatch", "sonnet for measurement, git legwork and verification",
                     "haiku for a schema or gate check", "opus for implementation and review",
                     "never inherited by omission", "BLOCKCHAIN_KIT_WORKFLOW_TIERS=0"):
            self.assertIn(text, reason)

    def test_a_named_model_in_any_spelling_passes(self):
        for opts in ("{ model: 'sonnet' }", '{ label: "m", model: "haiku", effort: "low" }', "{ model: TIER }",
                     "{ model: tierOf('verify') }", "{ 'model': 'sonnet' }", '{ "model": "opus" }',
                     "{ model }", "{ schema: S, model: 'sonnet', }",
                     "{\n    label: 'm',\n    model: 'sonnet',\n  }"):
            with self.subTest(opts=opts):
                self.allowed(f"const model = 'sonnet', TIER = 'sonnet', S = {{}}\nawait agent('x', {opts})")

    def test_options_the_text_cannot_judge_are_allowed(self):
        for opts in ("{ label: 'm', ...TIER }", "{ ...base(it), label: 'm' }", "opts(it)", "cond ? A : B",
                     "Object.assign({ label: 'm' }, tier)"):
            with self.subTest(opts=opts):
                self.allowed(f"await agent('x', {opts})")

    def test_an_options_identifier_is_resolved_to_its_literal(self):
        self.assertIn("1 agent() call", self.denied("const OPTS = { label: 'm', schema: S }\nawait agent('x', OPTS)"))
        self.allowed("const OPTS = { label: 'm', model: 'sonnet' }\nawait agent('x', OPTS)")
        self.allowed("let OPTS = { label: 'm', ...tier }\nawait agent('x', OPTS)")
        self.allowed("const OPTS = mk('sonnet')\nawait agent('x', OPTS)")

    def test_strings_comments_and_other_names_do_not_count(self):
        self.assertIn("line 2", self.denied("await agent('say model: sonnet and agent(x) back', { label: 'm' })"))
        self.assertIn("line 3", self.denied("// agent('old', { model: 'sonnet' })\nawait agent('x', { label: 'm' /* model: 'sonnet' */ })"))
        self.allowed("const subagent = (p) => p\nsubagent('x')\nconst o = { agent(p) { return p } }\no.agent('x')")
        self.allowed("await agent(`a ${b ? `c \"${d}\"` : '`'} e`, { model: 'sonnet' })  // nested templates")
        self.allowed("const re = /[\"'`]\\//g, half = n / 2 / m\nawait agent('x', { model: re.test(s) ? 'opus' : 'sonnet' })")

    def test_the_implement_workflow_passes(self):
        rc, out, err = self.run_hook(payload(script=(KIT / "workflows" / "implement.js").read_text(encoding="utf-8")))
        self.assertEqual((rc, out), (0, ""), err)

    def test_a_script_path_is_read_and_takes_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.js"
            path.write_text(META + "await agent('from the file')\n", encoding="utf-8")
            rc, out, _ = self.run_hook(payload(scriptPath=str(path), script="await agent('x', { model: 'sonnet' })"))
            self.assertIn("agent('from the file')", json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"])
            path.write_text(META + "await agent('x', { model: 'sonnet' })\n", encoding="utf-8")
            self.assertEqual(self.run_hook(payload(scriptPath=str(path), script="await agent('x')"))[1], "")
            rc, out, _ = self.run_hook(payload(scriptPath=str(Path(tmp) / "missing.js")))
            self.assertEqual((rc, out), (0, ""))  # unreadable: fails open

    def test_named_workflows_other_tools_bad_payloads_and_the_switch_print_nothing(self):
        for stdin in (payload(name="blockchain-kit:implement", args={"units": []}),
                      payload(resumeFromRunId="wf_abcdef"),
                      payload(tool="Agent", prompt="await agent('x')"),
                      payload(tool="Bash", command="echo agent('x')"),
                      "not json", "[]", json.dumps({"tool_name": "Workflow", "tool_input": "x"}),
                      payload(script=META + "await agent('unterminated)"),
                      payload(script=META + "await agent('x', { label: 'm' }")):
            with self.subTest(stdin=stdin[:60]):
                rc, out, _ = self.run_hook(stdin)
                self.assertEqual((rc, out), (0, ""))
        rc, out, _ = self.run_hook(payload(script=META + "await agent('x')"), BLOCKCHAIN_KIT_WORKFLOW_TIERS="0")
        self.assertEqual((rc, out), (0, ""))

    def test_the_hook_is_registered_for_workflow_and_executable(self):
        self.assertTrue(os.access(HOOK, os.X_OK))
        hooks = json.loads((HOOK.parent / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
        cmds = [h["command"] for group in hooks if group.get("matcher") == "Workflow" for h in group["hooks"]]
        self.assertEqual(cmds, ['"${CLAUDE_PLUGIN_ROOT}/hooks/workflow-tiers"'])


if __name__ == "__main__":
    unittest.main()
