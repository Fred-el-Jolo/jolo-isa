"""Installer against copies (never the real settings). Run: python3 -m unittest tests.test_install"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL = os.path.expanduser("~/.claude/settings.json")


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="isa-inst-")
        self.settings = os.path.join(self.tmp, "settings.json")
        if os.path.isfile(REAL):
            # start from the real file minus any ISA entries a real install already added
            sys.path.insert(0, ROOT)
            import install
            with open(REAL) as f:
                base = install.strip_statusline(install.strip_settings(json.load(f)))
            with open(self.settings, "w") as f:
                json.dump(base, f, indent=2)
        else:
            json.dump({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "x"}]}]}},
                      open(self.settings, "w"))
        os.makedirs(os.path.join(self.tmp, "pi", "extensions"))
        self.args = ["--claude-settings", self.settings, "--prefix", os.path.join(self.tmp, "local"),
                     "--skills-dir", os.path.join(self.tmp, "skills"), "--pi-dir", os.path.join(self.tmp, "pi")]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_install(self, *extra):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "install.py"), *self.args, *extra],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    @staticmethod
    def entries(s):
        return sorted((ev, json.dumps(h, sort_keys=True)) for ev, gs in s.get("hooks", {}).items()
                      for g in gs for h in g.get("hooks", []))

    def test_keeps_existing_entries(self):
        before = json.load(open(self.settings))
        self.run_install()
        after = json.load(open(self.settings))
        missing = set(self.entries(before)) - set(self.entries(after))
        self.assertEqual(missing, set())
        isa = [e for e in self.entries(after) if "isa hook claude" in e[1]]
        self.assertEqual(sorted({ev for ev, _ in isa}),
                         sorted(["PostToolUse", "PostToolUseFailure", "PreToolUse", "SessionStart", "Stop",
                                 "UserPromptSubmit"]))
        for k in before:
            if k not in ("hooks", "permissions"):
                self.assertEqual(before[k], after[k], k)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "pi", "extensions", "isa.ts")))
        self.assertTrue(os.path.islink(os.path.join(self.tmp, "local", "bin", "isa")))

    def test_one_limit_for_every_hook(self):
        """SPEC-v2 § 11: no hook waits for a model, so every ISA hook gets the same 15 s, and an older
        install's 20 s UserPromptSubmit limit is brought back to 15 on the next install."""
        self.run_install()
        s = json.load(open(self.settings))
        for g in s["hooks"]["UserPromptSubmit"]:
            for h in g["hooks"]:
                if "isa hook claude" in h.get("command", ""):
                    h["timeout"] = 20
        with open(self.settings, "w") as f:
            json.dump(s, f)
        self.run_install()
        after = json.load(open(self.settings))
        limits = [h["timeout"] for gs in after["hooks"].values() for g in gs for h in g["hooks"]
                  if "isa hook claude" in h.get("command", "")]
        self.assertEqual(len(limits), 6)
        self.assertEqual(set(limits), {15})

    def test_idempotent(self):
        self.run_install()
        first = open(self.settings, "rb").read()
        out = self.run_install()
        self.assertEqual(open(self.settings, "rb").read(), first)
        self.assertIn("unchanged", out)
        backups = [f for f in os.listdir(self.tmp) if ".isa-backup-" in f]
        self.assertEqual(len(backups), 1)

    def test_uninstall_restores_entries(self):
        before = json.load(open(self.settings))
        self.run_install()
        self.run_install("--uninstall")
        after = json.load(open(self.settings))
        self.assertEqual(self.entries(before), self.entries(after))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "pi", "extensions", "isa.ts")))


class TestStatusline(unittest.TestCase):
    """`--statusline`: the wire-settings mechanism (ex progress-outline) ported into install.py."""

    CC = {"type": "command", "command": "ccstatusline", "padding": 0, "refreshInterval": 10}

    def setUp(self):
        if not shutil.which("node"):
            self.skipTest("node not on PATH")
        self.tmp = tempfile.mkdtemp(prefix="isa-sl-")
        self.settings = os.path.join(self.tmp, "settings.json")
        self.prefix = os.path.join(self.tmp, "local")
        self.sl = os.path.join(self.prefix, "share", "isa", "statusline")
        self.args = ["--claude-settings", self.settings, "--prefix", self.prefix, "--no-skill",
                     "--skills-dir", os.path.join(self.tmp, "skills"), "--pi-dir", os.path.join(self.tmp, "nopi")]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, s):
        with open(self.settings, "w") as f:
            json.dump(s, f, indent=2)

    def load(self):
        with open(self.settings) as f:
            return json.load(f)

    def run_install(self, *extra):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "install.py"), *self.args, *extra],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p.stdout

    def test_composes_existing(self):
        self.write({"statusLine": dict(self.CC)})
        self.run_install("--statusline")
        sl = self.load()["statusLine"]
        self.assertTrue(sl["_isaManaged"])
        self.assertEqual(sl["_isaInnerCommand"], "ccstatusline")
        self.assertEqual((sl["type"], sl["padding"], sl["refreshInterval"]), ("command", 0, 10))
        self.assertIn(os.path.join(self.sl, "scripts", "statusline-wrapper.cjs"), sl["command"])
        self.assertIn(os.path.join(self.sl, "harness.ts"), sl["command"])
        self.assertIn("'ccstatusline'", sl["command"])
        self.assertTrue(os.path.isfile(os.path.join(self.sl, "renderer.ts")))
        self.assertFalse(os.path.exists(os.path.join(self.sl, "test")))

    def test_idempotent_no_nesting(self):
        self.write({"statusLine": dict(self.CC)})
        self.run_install("--statusline")
        first = open(self.settings, "rb").read()
        self.run_install("--statusline")
        self.assertEqual(open(self.settings, "rb").read(), first)
        sl = self.load()["statusLine"]
        self.assertEqual(sl["_isaInnerCommand"], "ccstatusline")
        self.assertEqual(sl["command"].count("statusline-wrapper.cjs"), 1)

    def test_migrates_progress_outline_entry(self):
        old = "'node' '/home/x/dev/progress-outline/scripts/statusline-wrapper.cjs' 'node' " \
              "'/home/x/dev/progress-outline/harness.ts' 'ccstatusline'"
        self.write({"statusLine": {"type": "command", "command": old, "padding": 0,
                                   "_isaManaged": True, "_isaInnerCommand": "ccstatusline"}})
        self.run_install("--statusline")
        sl = self.load()["statusLine"]
        self.assertEqual(sl["_isaInnerCommand"], "ccstatusline")
        self.assertNotIn("progress-outline", sl["command"])
        self.assertIn(self.sl, sl["command"])
        self.run_install("--uninstall")
        self.assertEqual(self.load()["statusLine"], {"type": "command", "command": "ccstatusline", "padding": 0})

    def test_legacy_task_plan(self):
        harness = "/home/x/dev/progress-outline/harness.ts"
        self.write({
            "statusLine": {"type": "command", "command": f"node {harness} render",
                           "_taskPlanManaged": True, "_taskPlanInnerCommand": "ccstatusline"},
            "hooks": {"PostToolUse": [
                {"matcher": "TodoWrite", "hooks": [{"type": "command", "command": f"node {harness} capture"}]},
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "keep-me"}]}]}})
        self.run_install("--statusline")
        s = self.load()
        sl = s["statusLine"]
        self.assertEqual(sl["_isaInnerCommand"], "ccstatusline")
        self.assertFalse({"_taskPlanManaged", "_taskPlanInnerCommand"} & set(sl))
        cmds = [h["command"] for g in s["hooks"]["PostToolUse"] for h in g["hooks"]]
        self.assertIn("keep-me", cmds)
        self.assertFalse(any("capture" in c for c in cmds))

    def test_uninstall_restores(self):
        self.write({"statusLine": dict(self.CC)})
        self.run_install("--statusline")
        self.run_install("--uninstall")
        self.assertEqual(self.load()["statusLine"], self.CC)
        self.assertFalse(os.path.exists(self.sl))

    def test_uninstall_removes_added(self):
        self.write({"theme": "dark"})
        self.run_install("--statusline")
        sl = self.load()["statusLine"]
        self.assertIsNone(sl["_isaInnerCommand"])
        self.assertTrue(sl["command"].endswith("harness.ts' render"))
        self.run_install("--uninstall")
        self.assertNotIn("statusLine", self.load())

    def test_plain_install_refreshes_managed(self):
        self.write({"statusLine": dict(self.CC)})
        self.run_install("--statusline")
        renderer = os.path.join(self.sl, "renderer.ts")
        with open(renderer, "w") as f:
            f.write("stale")
        s = self.load()
        s["statusLine"]["command"] = "stale"
        self.write(s)
        self.run_install()
        self.assertNotEqual(open(renderer).read(), "stale")
        sl = self.load()["statusLine"]
        self.assertIn(self.sl, sl["command"])
        self.assertEqual(sl["_isaInnerCommand"], "ccstatusline")

    def test_plain_install_leaves_unmanaged(self):
        self.write({"statusLine": dict(self.CC)})
        self.run_install()
        self.assertEqual(self.load()["statusLine"], self.CC)
        self.assertFalse(os.path.exists(self.sl))
        self.write({})
        self.run_install()
        self.assertNotIn("statusLine", self.load())

    def test_config_survives_reinstall(self):
        self.run_install("--statusline")
        cfg = os.path.join(self.sl, "config.json")
        with open(cfg, "w") as f:
            f.write('{"mode": "compact"}\n')
        self.run_install("--statusline")
        self.assertEqual(open(cfg).read(), '{"mode": "compact"}\n')

    def test_wrapper_composes_output(self):
        fake = os.path.join(self.tmp, "fake-isa")
        view = {"bound": "/x/ISA.md", "task": "Fake task", "effort": "E2", "phase": "build",
                "progress": "1/2", "iscs": [{"id": "ISC-1", "text": "one", "done": True},
                                            {"id": "ISC-2", "text": "two open", "done": False}]}
        with open(fake, "w") as f:
            f.write(f"#!/bin/sh\ncat <<'EOF'\n{json.dumps(view)}\nEOF\n")
        os.chmod(fake, 0o755)
        self.write({"statusLine": {"type": "command", "command": "echo INNER-LINE"}})
        self.run_install("--statusline")
        cmd = self.load()["statusLine"]["command"]
        env = {**os.environ, "ISA_BIN": fake, "NO_COLOR": "1", "COLUMNS": "120"}
        p = subprocess.run(cmd, shell=True, input=json.dumps({"session_id": "s1"}),
                           capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = p.stdout.splitlines()
        self.assertEqual(lines[0], "INNER-LINE")
        self.assertTrue(any("Fake task" in l for l in lines[1:]), p.stdout)
        self.assertTrue(any("ISC-2" in l for l in lines[1:]), p.stdout)


BLOCK_FILE = os.path.join(ROOT, "skill", "global-rules.md")
SPEC = os.path.join(ROOT, "docs", "spec", "2026-10-06-local-isas-spec-driven.md")
BEGIN, END = "<!-- isa:spec-driven:begin -->", "<!-- isa:spec-driven:end -->"
USER = "# Global Instructions\n\nThese apply to **every** project and session.\n\n- Propose, don't impose.\n"
REAL_FILES = [os.path.expanduser("~/.claude/CLAUDE.md"), os.path.expanduser("~/.pi/agent/AGENTS.md")]


def block():
    with open(BLOCK_FILE) as f:
        return f.read().rstrip("\n")


def snapshot(paths):
    out = {}
    for p in paths:
        try:
            st = os.stat(p)
            with open(p, "rb") as f:
                out[p] = (f.read(), st.st_mtime_ns)
        except FileNotFoundError:
            out[p] = None
    return out


class TestRuleBlock(unittest.TestCase):
    """Plan P13 (spec § B.8, Q4): the spec-driven rule block in ~/.claude/CLAUDE.md and ~/.pi/agent/AGENTS.md."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="isa-p13-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.claude_dir = os.path.join(self.tmp, "claude")
        self.pi = os.path.join(self.tmp, "pi")
        os.makedirs(self.claude_dir)
        self.claude_md = os.path.join(self.claude_dir, "CLAUDE.md")
        self.agents = os.path.join(self.pi, "AGENTS.md")
        self.args = ["--claude-settings", os.path.join(self.claude_dir, "settings.json"),
                     "--prefix", os.path.join(self.tmp, "local"), "--skills-dir", os.path.join(self.tmp, "skills"),
                     "--pi-dir", self.pi]
        sys.path.insert(0, ROOT)
        import install
        self.install = install

    def with_pi(self, text=USER):
        os.makedirs(os.path.join(self.pi, "extensions"), exist_ok=True)
        with open(self.agents, "w") as f:
            f.write(text)

    def put_claude(self, text):
        with open(self.claude_md, "w") as f:
            f.write(text)

    def read(self, p):
        with open(p) as f:
            return f.read()

    def run_install(self, *extra):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "install.py"), *self.args, *extra],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def backups(self, p):
        d, name = os.path.dirname(p), os.path.basename(p)
        return sorted(n for n in os.listdir(d) if n.startswith(name + ".isa-backup-")) if os.path.isdir(d) else []

    def test_merge_appends(self):
        b = block()
        self.assertEqual(self.install.merge_block(USER, b), USER + "\n" + b + "\n")
        self.assertEqual(self.install.merge_block("", b), b + "\n")
        self.assertEqual(self.install.merge_block("no newline", b), "no newline\n\n" + b + "\n")

    def test_merge_replaces(self):
        b = block()
        old = f"top\n\n{BEGIN}\nold rules\n{END}\n\nbottom\n"
        self.assertEqual(self.install.merge_block(old, b), f"top\n\n{b}\n\nbottom\n")
        self.assertEqual(self.install.merge_block(self.install.merge_block(USER, b), b),
                         self.install.merge_block(USER, b))

    def test_strip_only_block(self):
        b = block()
        for text in (USER, "", "x\n\n\ny\n"):
            self.assertEqual(self.install.strip_block(self.install.merge_block(text, b)), text, repr(text))
        self.assertEqual(self.install.strip_block(f"top\n\n{b}\n\nbottom\n"), "top\n\nbottom\n")
        self.assertEqual(self.install.strip_block(USER), USER)

    def test_writes_claude_md(self):
        self.run_install()
        self.assertEqual(self.read(self.claude_md), block() + "\n")

    def test_writes_pi_agents(self):
        self.with_pi()
        self.run_install()
        after = self.read(self.agents)
        self.assertTrue(after.startswith(USER), after)
        self.assertEqual(after, USER + "\n" + block() + "\n")

    def test_no_pi_dir(self):
        self.run_install()
        self.assertFalse(os.path.exists(self.pi))

    def test_backs_up(self):
        self.put_claude("mine\n")
        self.with_pi()
        self.run_install()
        for p, before in ((self.claude_md, "mine\n"), (self.agents, USER)):
            baks = self.backups(p)
            self.assertEqual(len(baks), 1, baks)
            self.assertEqual(self.read(os.path.join(os.path.dirname(p), baks[0])), before)

    def test_rerun_unchanged(self):
        self.with_pi()
        self.run_install()
        self.assertIn(BEGIN, self.read(self.claude_md))
        for p in (self.claude_md, self.agents):
            os.utime(p, ns=(1_000_000_000, 1_000_000_000))
        before = snapshot([self.claude_md, self.agents])
        baks = self.backups(self.agents)
        self.run_install()
        self.assertEqual(snapshot([self.claude_md, self.agents]), before)
        self.assertEqual(self.backups(self.agents), baks)

    def test_uninstall_strips(self):
        self.put_claude("mine\n")
        self.with_pi()
        self.run_install()
        self.assertTrue(BEGIN in self.read(self.claude_md) and BEGIN in self.read(self.agents))
        self.run_install("--uninstall")
        self.assertEqual((self.read(self.claude_md), self.read(self.agents)), ("mine\n", USER))
        os.remove(self.claude_md)
        self.run_install()
        self.assertTrue(os.path.exists(self.claude_md))
        self.run_install("--uninstall")
        self.assertFalse(os.path.exists(self.claude_md))

    def test_dry_run_writes_nothing(self):
        self.with_pi()
        out = self.run_install("--dry-run")
        self.assertIn(f"would update {self.claude_md}", out)
        self.assertFalse(os.path.exists(self.claude_md))
        self.assertEqual((self.read(self.agents), self.backups(self.agents)), (USER, []))
        self.run_install()
        before = snapshot([self.claude_md, self.agents])
        self.run_install("--uninstall", "--dry-run")
        self.assertEqual(snapshot([self.claude_md, self.agents]), before)

    def test_block_is_spec_draft(self):
        with open(SPEC) as f:
            spec = f.read()
        draft = spec[spec.index(BEGIN):spec.index(END) + len(END)]
        self.assertEqual(block(), draft)

    def test_real_files_untouched(self):
        before = snapshot(REAL_FILES)
        self.with_pi()
        self.run_install()
        self.run_install("--uninstall")
        TestInstall.setUp(self)  # the existing installer tests' own redirected paths
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.run_install()
        self.assertEqual(snapshot(REAL_FILES), before)


if __name__ == "__main__":
    unittest.main()
