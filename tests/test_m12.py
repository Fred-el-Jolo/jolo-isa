"""SPEC-v2 § 13, M12: a repo's ISAs live at its root, committed with it; only the user's verbatim words
are encrypted, by a required git clean/smudge filter; the key never reaches an agent.

Plan P3 (2026-10-06) moved task ISAs back to ISA_HOME: the tests of the repo layout went with it (the project
ISA and `promote:` tests now live in tests/test_project_isa.py); P4 deletes the rest with crypt.py.

Real git repos; the filter runs this repo's runtime. No network.
Run: python3 -m unittest tests.test_m12
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile

from tests.test_commands import CommandCase
from tests.test_evidence import read
from tests.test_hooks import ISA, ROOT, TEST_KEY

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import crypt, evidence, lint, quotes, state  # noqa: E402

GOAL = "Add a --shout flag to greet.py that prints the greeting in uppercase, with a test."
PROMPT = "please " + GOAL + " Thanks!"
OTHER_KEY = base64.b64encode(b"o" * 32).decode()

TASK = f"""---
task: "Add a shout flag"
slug: 20260101-000000_t
effort: E2
phase: build
progress: 0/2
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
root: .
stated_goal: "{GOAL}"
asks: ["Add a --shout flag to greet.py", "with a test"]
context_sufficient: true
---

## Problem

greet.py can't shout.

## Goal

"{GOAL}" The flag uppercases the whole greeting.

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

## Decisions

- 2026-01-01 00:00: user: "keep the default \\"as is\\"" — no other flag changes.
"""


class RepoCase(CommandCase):
    """A real git repo as the project; git runs with this test's ISA_HOME and key."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(os.path.join(self.proj, ".git"))
        self.git("init", "-q")
        self.put("a.txt", "one\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")

    def git(self, *args, cwd=None, check=True):
        env = dict(self.env, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t")
        return subprocess.run(["git", "-C", cwd or self.proj, *args], capture_output=True, text=True, env=env,
                              check=check)

    def put(self, rel, text, base=None):
        p = os.path.join(base or self.proj, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        return p

    def new_isa(self, slug="shout"):
        self.hook("UserPromptSubmit", prompt=PROMPT)
        rc, out = self.isa("new", slug)
        self.assertEqual(rc, 0, out)
        return out.strip().splitlines()[-1]

    def task(self, text=TASK):
        """The fixture task ISA, set up through `isa new` (so the repo gets .gitattributes and the filter)."""
        path = self.new_isa()
        self.hook("UserPromptSubmit", prompt=PROMPT)
        with open(path, "w") as f:
            f.write(text.replace("slug: 20260101-000000_t", f"slug: {os.path.basename(os.path.dirname(path))}"))
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": path}, tool_response={})
        return path

    def blob(self, rel):
        return self.git("show", f"HEAD:{rel}").stdout

    def commit_all(self, msg="isa"):
        """→ the first failing step (`git add` runs the clean filter), or the commit."""
        r = self.git("add", "-A", check=False)
        return r if r.returncode else self.git("commit", "-qm", msg, check=False)


class TestLocation(RepoCase):
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
        rc, out = self.isa("new", "x") if self.hook("UserPromptSubmit", prompt=PROMPT) else (None, None)
        self.assertEqual(rc, 0, out)
        self.assertEqual(read(os.path.join(self.proj, "ISA.md")), "# International Standard Atmosphere\n")
        self.assertIn("left untouched", out)

    def test_home_repo_is_no_repo(self):
        self.assertIsNone(state.repo_root(os.path.expanduser("~")) if os.path.exists(os.path.expanduser("~/.git"))
                          else None)
        fake = tempfile.mkdtemp(prefix="isa-homerepo-")
        try:
            os.makedirs(os.path.join(fake, ".git"))
            env = dict(self.env, HOME=fake, ISA_HOME=os.path.join(fake, ".isa"))
            r = subprocess.run([sys.executable, ISA, "where"], cwd=fake, env=env, text=True, capture_output=True)
            self.assertIn(os.path.join(fake, ".isa", "_home"), r.stdout)
        finally:
            shutil.rmtree(fake, ignore_errors=True)


class TestFilter(RepoCase):
    def test_root_isa_md_never_encrypted(self):
        self.task()
        proj = os.path.join(self.proj, "ISA.md")
        before = read(proj)
        self.commit_all()
        self.assertEqual(self.blob("ISA.md"), before)
        with open(proj, "a") as f:
            f.write('\n## Decisions\n\n- 2026-01-01: user: "a quote"\n')
        rc, out = self.isa("lint", proj)
        self.assertNotEqual(rc, 0)
        self.assertIn("never quotes the user", out)

    def test_tampered_tag_left_encrypted(self):
        k = crypt.key() or base64.b64decode(TEST_KEY)
        tok = crypt.encrypt("Vhello", k)
        bad = tok[:-2] + ("AA" if not tok.endswith("AA") else "BB")
        text = f'---\nstated_goal: "{bad}"\n---\n'
        self.assertEqual(crypt.smudge(text, k), text)
        self.assertIsNone(crypt.decrypt(bad, k))

    def test_round_trip_every_example(self):
        k = base64.b64decode(TEST_KEY)
        for name in sorted(os.listdir(os.path.join(ROOT, "skill/ISA/Examples"))):
            t = read(os.path.join(ROOT, "skill/ISA/Examples", name))
            c = crypt.clean(t, k)
            self.assertEqual(crypt.smudge(c, k), t, name)
            self.assertEqual(crypt.clean(c, k), c, name)

    def test_escaped_quote_round_trips(self):
        k = base64.b64decode(TEST_KEY)
        t = 'x\n- user: "say \\"hi\\" twice"\n'
        c = crypt.clean(t, k)
        self.assertNotIn("twice", c)
        self.assertEqual(crypt.smudge(c, k), t)


class TestKeyCommands(RepoCase):
    def test_export_refuses_stdout_in_agent_session_and_new_never_prints(self):
        env = dict(self.env, CLAUDE_CODE_SESSION_ID="s1")
        env.pop("ISA_KEY")
        r = subprocess.run([sys.executable, ISA, "key", "new"], env=env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        k = read(os.path.join(self.home, "key")).strip()
        self.assertNotIn(k, r.stdout + r.stderr)
        r = subprocess.run([sys.executable, ISA, "key", "export"], env=env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn(k, r.stdout + r.stderr)
        dest = os.path.join(self.tmp, "k.out")
        r = subprocess.run([sys.executable, ISA, "key", "export", dest], env=env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(read(dest).strip(), k)
        self.assertEqual(oct(os.stat(dest).st_mode & 0o777), "0o600")

    def test_model_may_not_run_key_commands(self):
        for cmd, refused in (("isa key export /tmp/k", True), ("isa key new", True), ("isa key import f", True),
                             ("isa key status", False)):
            _, out, _ = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd})
            self.assertEqual(self.decision(out) == "deny", refused, cmd)


class TestLedger(RepoCase):
    def test_rows_sorted_by_time(self):
        path = self.task()
        evidence.record(path, [{"v": 2, "t": 50.0, "isc": "ISC-2", "kind": "verify", "ok": True, "tool_sha": "a"}])
        evidence.record(path, [{"v": 2, "t": 10.0, "isc": "ISC-2", "kind": "verify", "ok": False, "tool_sha": "b"}])
        self.assertEqual(evidence.latest(path)["ISC-2"]["tool_sha"], "a")


NOTIFICATION = ("<task-notification>\n<task-id>b1</task-id>\n<status>completed</status>\n"
                "<summary>Background command finished</summary>\n</task-notification>")


class TestNotification(RepoCase):
    """A background task's completion arrives as a prompt made only of notification blocks: not the user's."""

    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)

    def gate(self, p=0.31):
        from tests.test_hooks import calls, setup_fake
        setup_fake(self, isa_gate=p)
        return calls

    def test_no_judge(self):
        calls = self.gate()
        self.pid = "p2"
        _, out, _ = self.hook("UserPromptSubmit", prompt=NOTIFICATION + "\n" + NOTIFICATION)
        self.assertEqual(calls(self, "isa-gate"), [])
        self.assertEqual(out, {})

    def test_pass_kept(self):
        self.gate()
        path = self.isa_path("20260101-000000_closed")  # a session ON with a closed ISA bound
        os.makedirs(os.path.dirname(path))
        from tests.test_hooks import CLOSED
        with open(path, "w") as f:
            f.write(CLOSED)
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": path}, tool_response={})
        self.assertEqual(self.session()["bound"], os.path.realpath(path))
        self.pid = "p2"
        self.hook("UserPromptSubmit", prompt="commit and push")
        q = "ISA is not enabled for this prompt (Jev: 0.31). Continue?"
        self.hook("PostToolUse", tool_name="AskUserQuestion",
                  tool_input={"questions": [{"question": q}], "answers": {q: "Continue without ISA"}}, tool_response={})
        self.pid = "p3"
        self.hook("UserPromptSubmit", prompt=NOTIFICATION)
        _, out, _ = self.hook("PreToolUse", tool_name="Write",
                              tool_input={"file_path": os.path.join(self.proj, "x.py"), "content": "x"})
        self.assertNotEqual(self.decision(out), "deny")

    def test_logged(self):
        self.gate()
        self.hook("UserPromptSubmit", prompt=NOTIFICATION)
        self.assertTrue(self.log_rows("prompt")[-1].get("notification"))

    def test_mixed_is_judged(self):
        calls = self.gate()
        self.hook("UserPromptSubmit", prompt="ok thanks\n" + NOTIFICATION)
        self.assertEqual(len(calls(self, "isa-gate")), 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
