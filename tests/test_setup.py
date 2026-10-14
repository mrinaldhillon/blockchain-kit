"""Tests for bin/blockchain-kit-setup and bin/blockchain-kit-update, both scopes.

A fake `claude` on PATH records its argv and cwd and edits installed_plugins.json in a
temp CLAUDE_CONFIG_DIR the way the real CLI records an install; a fake `go` keeps the
toolchain rows from failing. Whether the real CLI writes what the fake writes is a live
probe (docs/migration-plan.md, phase 0, P5 and P6).

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
SETUP = KIT / "bin" / "blockchain-kit-setup"
UPDATE = KIT / "bin" / "blockchain-kit-update"
PLUGIN = "blockchain-kit@blockchain-kit"

FAKE_CLAUDE = """#!{python}
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as log:
    log.write(json.dumps({{"argv": args, "cwd": os.getcwd()}}) + "\\n")
home = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "plugins"
home.mkdir(parents=True, exist_ok=True)
record = home / "installed_plugins.json"
d = json.loads(record.read_text()) if record.exists() else {{"version": 2, "plugins": {{}}}}
scope = args[args.index("--scope") + 1] if "--scope" in args else "user"

def at(version):
    path = home / "cache" / "blockchain-kit" / "blockchain-kit" / version
    path.mkdir(parents=True, exist_ok=True)
    return str(path)

if args[:3] == ["plugin", "marketplace", "add"]:
    (home / "known_marketplaces.json").write_text(json.dumps({{"blockchain-kit": {{"source": args[3]}}}}))
elif args[:2] == ["plugin", "install"]:
    version = os.environ["FAKE_VERSION"]
    entry = {{"version": version, "scope": scope, "installPath": at(version)}}
    if scope == "project":
        entry["projectPath"] = os.environ.get("FAKE_PROJECT_PATH") or os.getcwd()
        if os.environ.get("FAKE_TOUCH_SETTINGS"):
            Path(".claude/settings.json").write_text('{{"enabledPlugins": {{"{plugin}": true}}}}\\n')
    d["plugins"].setdefault(args[2], []).append(entry)
elif args[:2] == ["plugin", "update"] and os.environ.get("FAKE_NEXT_VERSION"):
    for e in d["plugins"].get(args[2], []):
        if e["scope"] == scope and (scope != "project"
                                    or os.path.realpath(e["projectPath"]) == os.path.realpath(os.getcwd())):
            e["version"] = os.environ["FAKE_NEXT_VERSION"]
            e["installPath"] = at(e["version"])
record.write_text(json.dumps(d))
"""

FAKE_GO = """#!/bin/sh
case "$1 $2" in
"version "*) echo "go version go1.26.0 linux/amd64" ;;
"env GOPRIVATE") echo "github.com/mrinaldhillon/*" ;;
"env "*) echo "" ;;
esac
"""


class Setup(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        self.bin, self.config, self.proj = self.tmp / "bin", self.tmp / "config", self.tmp / "proj"
        for d in (self.bin, self.tmp / "home", self.tmp / "data", self.proj / ".claude", self.proj / "sub",
                  self.tmp / "elsewhere"):
            d.mkdir(parents=True)
        (self.proj / ".claude/settings.json").write_text('{"env": {}}\n')
        (self.tmp / "proj-link").symlink_to(self.proj)  # the CLI may record a path the kit must realpath
        for name, body in (("claude", FAKE_CLAUDE.format(python=sys.executable, plugin=PLUGIN)), ("go", FAKE_GO)):
            (self.bin / name).write_text(body)
            (self.bin / name).chmod(0o755)
        self.log = self.tmp / "claude.log"

    def env(self, **more: str) -> dict[str, str]:
        drop = ("BLOCKCHAIN_KIT_", "CLAUDE_", "BSC_FORK_", "GIT_", "XDG_", "GO")
        full = {k: v for k, v in os.environ.items() if not k.startswith(drop)}
        full.update(PATH=f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", HOME=str(self.tmp / "home"),
                    CLAUDE_CONFIG_DIR=str(self.config), XDG_DATA_HOME=str(self.tmp / "data"), TMPDIR=str(self.tmp),
                    FAKE_CLAUDE_LOG=str(self.log), FAKE_VERSION="aaaaaaaaaaaa",
                    GIT_CEILING_DIRECTORIES=str(self.tmp), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        full.update(more)
        return full

    def run_tool(self, tool: Path, *args: str, cwd: Path | None = None, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(tool), *args], capture_output=True, text=True, env=self.env(**env),
                              cwd=cwd or self.tmp / "elsewhere", timeout=60, check=False)

    def calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def seed(self, *entries: dict) -> None:
        plugins = self.config / "plugins"
        plugins.mkdir(parents=True, exist_ok=True)
        for e in entries:
            Path(e["installPath"]).mkdir(parents=True, exist_ok=True)
        (plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {PLUGIN: list(entries)}}))
        (plugins / "known_marketplaces.json").write_text(json.dumps({"blockchain-kit": {}}))

    def entry(self, version: str, scope: str, project: Path | None = None) -> dict:
        e = {"version": version, "scope": scope, "installPath": str(self.tmp / "cache" / version)}
        if project is not None:
            e["projectPath"] = str(project)
        return e

    def link(self) -> str:
        return os.readlink(self.tmp / "data/blockchain-kit/kit")

    # setup

    def test_setup_user_scope_installs_for_the_home(self):
        done = self.run_tool(SETUP)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        argvs = [c["argv"] for c in self.calls()]
        self.assertEqual(argvs[0][:3], ["plugin", "marketplace", "add"])
        self.assertEqual(argvs[1:], [["plugin", "install", PLUGIN, "--scope", "user"]])
        self.assertIn(f"  ok     plugin                 {PLUGIN} aaaaaaaaaaaa ({self.config}, user-scope)", done.stdout)
        self.assertNotIn("settings.json", done.stdout)
        self.assertEqual(self.link(), str(self.config / "plugins/cache/blockchain-kit/blockchain-kit/aaaaaaaaaaaa"))

    def test_setup_project_scope_installs_from_the_clone_and_matches_by_projectpath(self):
        # another clone's install and a user install are not this clone's
        self.seed(self.entry("dddddddddddd", "project", self.tmp / "elsewhere"), self.entry("uuuuuuuuuuuu", "user"))
        done = self.run_tool(SETUP, "--scope", "project", "--project", str(self.proj),
                             FAKE_PROJECT_PATH=str(self.tmp / "proj-link"))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual([(c["argv"], c["cwd"]) for c in self.calls()],
                         [(["plugin", "install", PLUGIN, "--scope", "project"], str(self.proj))])
        # the version is read back through the symlinked projectPath the fake recorded
        self.assertIn(f"{PLUGIN} aaaaaaaaaaaa ({self.config}, project-scope ({self.proj}))", done.stdout)
        self.assertIn("  ok     settings.json          unchanged by the install\n", done.stdout)
        self.assertTrue(self.link().endswith("/aaaaaaaaaaaa"), self.link())

    def test_setup_project_scope_defaults_to_the_git_top_level_and_says_when_settings_changed(self):
        subprocess.run(["git", "init", "--quiet", str(self.proj)], check=True, env=self.env())
        done = self.run_tool(SETUP, "--scope", "project", cwd=self.proj / "sub", FAKE_TOUCH_SETTINGS="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual([c["cwd"] for c in self.calls() if c["argv"][:2] == ["plugin", "install"]], [str(self.proj)])
        self.assertIn(f"  warn   settings.json          changed by the install — read it with: "
                      f"git -C {self.proj} diff -- .claude/settings.json", done.stdout)
        self.assertNotIn("FAIL", done.stdout)

    def test_setup_refuses_a_directory_where_the_link_goes(self):
        kit = self.tmp / "data/blockchain-kit/kit"
        kit.mkdir(parents=True)  # a kit cloned there to bootstrap setup
        done = self.run_tool(SETUP)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn(f"{kit} is a directory, not a link: move it aside", done.stdout)
        self.assertEqual(list(kit.iterdir()), [])
        self.assertFalse(kit.is_symlink())

    def test_scope_usage_errors_are_2_and_run_nothing(self):
        cases = ((SETUP, "--scope", "project"),  # no --project, and the cwd is no git work tree
                 (UPDATE, "--scope", "project"),
                 (SETUP, "--scope", "global"),
                 (UPDATE, "--project", str(self.proj)),
                 (SETUP, "--scope", "project", "--project", str(self.tmp / "absent")))
        for tool, *args in cases:
            with self.subTest(args=[tool.name, *args]):
                done = self.run_tool(tool, *args)
                self.assertEqual((done.returncode, done.stdout), (2, ""))
                self.assertTrue(done.stderr.startswith(f"{tool.name}: "), done.stderr)
        self.assertEqual(self.calls(), [])

    # update

    def test_update_project_scope_updates_this_clones_install(self):
        self.seed(self.entry("aaaaaaaaaaaa", "project", self.tmp / "proj-link"), self.entry("uuuuuuuuuuuu", "user"),
                  self.entry("dddddddddddd", "project", self.tmp / "elsewhere"))
        done = self.run_tool(UPDATE, "--scope", "project", "--project", str(self.proj),
                             FAKE_NEXT_VERSION="bbbbbbbbbbbb")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        calls = self.calls()
        self.assertEqual([c["argv"] for c in calls], [["plugin", "marketplace", "update", "blockchain-kit"],
                                                       ["plugin", "update", PLUGIN, "--scope", "project"]])
        self.assertEqual(calls[1]["cwd"], str(self.proj))
        self.assertIn(f"  ok     plugin                 {PLUGIN} aaaaaaaaaaaa -> bbbbbbbbbbbb\n", done.stdout)
        self.assertTrue(self.link().endswith("/bbbbbbbbbbbb"), self.link())

    def test_update_user_scope_says_already_current(self):
        self.seed(self.entry("uuuuuuuuuuuu", "user"), self.entry("aaaaaaaaaaaa", "project", self.proj))
        done = self.run_tool(UPDATE)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.calls()[-1]["argv"], ["plugin", "update", PLUGIN, "--scope", "user"])
        self.assertIn(f"{PLUGIN} uuuuuuuuuuuu (already current)", done.stdout)
        self.assertEqual(self.link(), str(self.tmp / "cache/uuuuuuuuuuuu"))

    def test_update_without_an_install_of_the_scope_fails_naming_the_scope(self):
        self.seed(self.entry("uuuuuuuuuuuu", "user"))
        done = self.run_tool(UPDATE, "--scope", "project", "--project", str(self.proj))
        self.assertEqual(done.returncode, 1)
        self.assertIn(f"has no project-scope ({self.proj}) install of {PLUGIN}", done.stdout)
        self.assertNotIn("user-scope", done.stdout)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
