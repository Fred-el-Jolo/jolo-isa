"""Plan P3 (docs/plan/2026-10-06-local-isas-spec-driven.md, spec § A.1, § A.4): task ISAs always live in
ISA_HOME, also inside a git repo; the repo keeps only its project ISA (`<repo>/ISA.md`, `kind: project`),
re-proved by `isa verify ISA.md` and found through a task ISA's `root:` for `promote: true`.

Real git repos. No network.
Run: python3 -m unittest tests.test_project_isa
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from tests.test_commands import CommandCase
from tests.test_evidence import read
from tests.test_hooks import ISA, ROOT

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import changes, evidence, state  # noqa: E402

GOAL = "Add a --shout flag to greet.py that prints the greeting in uppercase, with a test."
PROMPT = "please " + GOAL + " Thanks!"

TASK = """---
task: "Add a shout flag"
slug: {slug}
effort: E2
phase: build
progress: 0/2
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
root: {root}
stated_goal: "{goal}"
asks: ["Add a --shout flag to greet.py", "with a test"]
context_sufficient: true
---

## Problem

greet.py can't shout.

## Goal

"{goal}" The flag uppercases the whole greeting.

## Criteria

- [ ] ISC-1: `--shout` prints the greeting in uppercase.
- [ ] ISC-2: Anti: the default output is unchanged.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "Add a --shout flag to greet.py"
  type: bash
  kind: file
  check: flag
  threshold: exit 0
  tool: test -f ok1
  fails-when: "ok1 missing"
- isc: ISC-2
  anchors_to: "with a test"
  type: bash
  kind: file
  check: flag
  threshold: exit 0
  tool: test -f ok2
  fails-when: "ok2 missing"
```
"""


class GitCase(CommandCase):
    """A real git repo as the project."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(os.path.join(self.proj, ".git"))
        self.git("init", "-q")
        self.put("a.txt", "one\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")

    def git(self, *args, check=True):
        env = dict(self.env, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t")
        return subprocess.run(["git", "-C", self.proj, *args], capture_output=True, text=True, env=env, check=check)

    def put(self, rel, text):
        p = os.path.join(self.proj, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        return p

    def new_isa(self, slug="shout"):
        self.hook("UserPromptSubmit", prompt=PROMPT)
        rc, out = self.isa("new", slug)
        self.assertEqual(rc, 0, out)
        return out.strip().splitlines()[-1]

    def task(self, text=None):
        path = self.new_isa()
        text = (text or TASK).format(slug=os.path.basename(os.path.dirname(path)),
                                     root=os.path.realpath(self.proj), goal=GOAL)
        return self.write_isa(text, path)

    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)


class TestLocation(GitCase):
    def test_new_goes_home_without_key(self):
        path = self.new_isa()
        self.assertTrue(path.startswith(os.path.join(self.home, state.project_key(self.proj)) + os.sep), path)
        self.assertTrue(os.path.isfile(path))

    def test_new_writes_nothing_in_repo(self):
        self.new_isa()
        self.assertFalse(os.path.exists(os.path.join(self.proj, ".isa")))
        self.assertFalse(os.path.exists(os.path.join(self.proj, ".gitattributes")))
        self.assertEqual(self.git("config", "--local", "--get-regexp", r"^filter\.isa", check=False).stdout, "")

    def test_root_is_absolute(self):
        path = self.new_isa()
        self.assertEqual(state.frontmatter(path)["root"], os.path.realpath(self.proj))

    def test_project_dir_and_removed_helpers(self):
        self.assertEqual(state.project_dir(self.proj), os.path.join(self.home, state.project_key(self.proj)))
        self.assertFalse(hasattr(state, "repo_isa_dir"))
        self.assertFalse(hasattr(state, "isa_repo"))

    def test_non_repo_uses_isa_home(self):
        d = tempfile.mkdtemp(prefix="isa-norepo-", dir=os.path.expanduser("~/.cache"))
        try:
            rc, out = self.isa("new", "x", cwd=d)
            self.assertEqual(rc, 0, out)
            self.assertTrue(out.strip().splitlines()[-1].startswith(os.path.realpath(self.home)))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_existing_non_project_isa_md_untouched(self):
        self.put("ISA.md", "# International Standard Atmosphere\n")
        self.hook("UserPromptSubmit", prompt=PROMPT)
        rc, out = self.isa("new", "x")
        self.assertEqual(rc, 0, out)
        self.assertEqual(read(os.path.join(self.proj, "ISA.md")), "# International Standard Atmosphere\n")
        self.assertIn("left untouched", out)

    def test_home_repo_is_no_repo(self):
        fake = tempfile.mkdtemp(prefix="isa-homerepo-")
        try:
            os.makedirs(os.path.join(fake, ".git"))
            env = dict(self.env, HOME=fake, ISA_HOME=os.path.join(fake, ".isa"))
            r = subprocess.run([sys.executable, ISA, "where"], cwd=fake, env=env, text=True, capture_output=True)
            self.assertIn(os.path.join(fake, ".isa", "_home"), r.stdout)
        finally:
            shutil.rmtree(fake, ignore_errors=True)


class TestLedgerPaths(GitCase):
    def test_ledger_only_under_state_evidence(self):
        old = os.path.join(self.proj, ".isa", "20260101-000000_x", "ISA.md")
        self.put(".isa/20260101-000000_x/ISA.md", "---\nroot: .\n---\n")
        led = evidence.ledger_path(old)
        self.assertTrue(led.startswith(os.path.join(self.home, "_state", "evidence") + os.sep), led)
        self.assertFalse(evidence.is_ledger_path(os.path.join(os.path.dirname(old), "evidence.jsonl")))
        self.assertTrue(evidence.is_ledger_path(led))


class TestChanges(GitCase):
    def test_dot_isa_counts_isa_md_does_not(self):
        self.assertEqual(changes.ISA_FILES, (":(top,exclude)ISA.md",))
        before = changes.snapshot(self.proj)
        self.put("ISA.md", "---\nkind: project\n---\n")
        self.assertFalse(changes.changed(before, self.proj))
        self.put(".isa/notes.md", "x\n")
        self.assertTrue(changes.changed(before, self.proj))


class TestProjectIsa(GitCase):
    def test_standing_claims_and_never_bound(self):
        self.task()
        proj = os.path.join(self.proj, "ISA.md")
        with open(proj, "a") as f:
            f.write("\n## Criteria\n\n- ISC-P1: a.txt exists (from x ISC-1)\n\n## Test Strategy\n\n```yaml\n"
                    "- isc: ISC-P1\n  type: bash\n  check: file\n  threshold: exit 0\n  tool: test -f a.txt\n```\n")
        rc, out = self.isa("verify", proj)
        self.assertEqual(rc, 0, out)
        self.assertIn("1/1 standing claim(s) hold", out)
        bound = self.session()["bound"]
        self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": proj}, tool_response={})
        self.assertEqual(self.session()["bound"], bound)
        rc, out = self.isa("close", proj)
        self.assertEqual(rc, 2)

    def test_promote_needs_project_line(self):
        path = self.task(TASK.replace("  tool: test -f ok2\n", "  tool: test -f ok2\n  promote: true\n"))
        self.put("ok1", "")
        self.put("ok2", "")
        self.verify(path)
        self.write_isa(read(path).rstrip("\n") + "\n- Ask 1: met — ISC-1\n- Ask 2: met — ISC-2\n- Goal: yes — done\n", path)
        rc, out = self.isa("close", path)
        self.assertNotEqual(rc, 0)
        self.assertIn("promote: true", out)
        slug = os.path.basename(os.path.dirname(path))
        with open(os.path.join(self.proj, "ISA.md"), "a") as f:
            f.write(f"\n## Criteria\n\n- ISC-P1: default output unchanged (from {slug} ISC-2)\n")
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 0, out)

    def test_user_quotes_allowed(self):
        """Q9: whether the project ISA quotes the user is the user's call, not the tool's."""
        self.task()
        proj = os.path.join(self.proj, "ISA.md")
        with open(proj, "a") as f:
            f.write('\n## Decisions\n\n- 2026-01-01 00:00: user: "keep the default output as is" — no flag changes.\n')
        rc, out = self.isa("lint", proj)
        self.assertEqual(rc, 0, out)
        _, hook_out, _ = self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": proj}, tool_response={})
        self.assertIn("edited (not bound to this session)", self.ctx(hook_out))
        self.assertNotIn("never holds the user's words", json.dumps(hook_out))

    def test_project_isa_of(self):
        repo = os.path.realpath(self.proj)
        self.put("sub/x.txt", "x\n")
        for root, want in ((repo, os.path.join(repo, "ISA.md")), (os.path.join(repo, "sub"), os.path.join(repo, "ISA.md")),
                           (self.tmp, None), (None, None)):
            p = os.path.join(self.home, "k", "20260101-000000_r", "ISA.md")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write("---\n" + (f"root: {root}\n" if root else "") + "---\n")
            self.assertEqual(state.project_isa_of(p), want, root)


class TestMissingBound(GitCase):
    def test_stale_binding_reads_as_none(self):
        gone = os.path.join(os.path.realpath(self.proj), ".isa", "20260101-000000_gone", "ISA.md")
        with state.session("claude", self.sid) as st:
            st["bound"], st["mode"] = gone, "on"
        rc, out, err = self.hook("UserPromptSubmit", prompt=PROMPT)
        self.assertEqual(rc, 0, err)
        self.assertNotIn("not on this branch", json.dumps(out))
        self.assertIn("no ISA bound yet", json.dumps(out))
        rc, _, err = self.hook("Stop", stop_hook_active=False, last_assistant_message="done")
        self.assertEqual(rc, 2, "Stop must ask for an ISA: nothing is bound")
        rc, out, err = self.hook("PreToolUse", tool_name="Read", tool_input={"file_path": os.path.join(self.proj, "a.txt")})
        self.assertEqual(rc, 0, err)
        self.assertNotEqual((out.get("hookSpecificOutput") or {}).get("permissionDecision"), "deny", out)
        rc, out, err = self.hook("PreToolUse", tool_name="Write",
                                 tool_input={"file_path": os.path.join(self.proj, "b.txt"), "content": "x"})
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny", out)
        self.assertIn("no ISA is bound to this session", self.reason(out))
        self.assertNotIn("not on this branch", json.dumps(out))
        rc, out = self.isa("status", "--session", self.sid)
        self.assertIn("no ISA bound", out)
        self.assertFalse(os.path.exists(os.path.join(self.home, "_state", "errors.log")))


if __name__ == "__main__":
    import unittest
    unittest.main()
