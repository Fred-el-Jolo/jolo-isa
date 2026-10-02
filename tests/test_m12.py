"""SPEC-v2 § 13, M12: a repo's ISAs live at its root, committed with it; only the user's verbatim words
are encrypted, by a required git clean/smudge filter; the key never reaches an agent.

Real git repos (and one bare remote for two clones); the filter runs this repo's runtime. No network.
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
from tests.test_hooks import E1, ISA, ROOT, TEST_KEY

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
    def test_new_isa_in_repo(self):
        path = self.new_isa()
        self.assertTrue(path.startswith(os.path.join(os.path.realpath(self.proj), ".isa") + os.sep), path)
        self.assertEqual(state.frontmatter(os.path.join(self.proj, "ISA.md")).get("kind"), "project")
        with open(os.path.join(self.proj, ".gitattributes")) as f:
            attrs = f.read()
        self.assertIn(".isa/**/*.md filter=isa", attrs)
        self.assertIn(".isa/**/evidence.jsonl merge=union", attrs)
        self.assertEqual(self.git("config", "--local", "filter.isa.required").stdout.strip(), "true")
        self.assertTrue(self.git("config", "--local", "filter.isa.clean").stdout.strip().startswith("/"))

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
    def test_commit_encrypts_exactly_the_quotes(self):
        path = self.task()
        rel = os.path.relpath(path, os.path.realpath(self.proj))
        self.assertEqual(self.commit_all().returncode, 0)
        stored = self.blob(rel)
        for words in (GOAL, "Add a --shout flag to greet.py", "with a test", 'keep the default \\"as is\\"'):
            self.assertNotIn(words, stored)
        self.assertEqual(stored.count("enc:v1:"), 7)  # goal, 2 asks, Goal quote, 2 anchors_to, user quote
        for plain in ("ISC-1: `--shout` prints the greeting in uppercase.", "The flag uppercases the whole greeting.",
                      "greet.py can't shout.", 'task: "Add a shout flag"'):
            self.assertIn(plain, stored)
        self.assertEqual(read(path), TASK.replace("20260101-000000_t", os.path.basename(os.path.dirname(path))))
        self.assertEqual(self.git("status", "--porcelain").stdout.strip(), "")

    def test_checkout_restores_and_is_deterministic(self):
        path = self.task()
        rel = os.path.relpath(path, os.path.realpath(self.proj))
        self.commit_all()
        first = self.blob(rel)
        plain = read(path)
        os.remove(path)
        self.git("checkout", "--", rel)
        self.assertEqual(read(path), plain)
        with open(path, "a") as f:
            f.write("\n- 2026-01-01 00:01: a note.\n")
        self.commit_all("note")
        second = self.blob(rel)
        self.assertEqual([x for x in first.splitlines() if "enc:v1:" in x],
                         [x for x in second.splitlines() if "enc:v1:" in x])

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

    def test_ephemeral_slice_encrypted(self):
        path = self.task()
        sl = self.put(os.path.join(os.path.dirname(path), "_ephemeral", "f.md"),
                      f'## Goal\n\nuser: "{GOAL}"\n', base="/")
        self.commit_all()
        rel = os.path.relpath(sl, os.path.realpath(self.proj))
        self.assertNotIn(GOAL, self.blob(rel))
        self.assertIn("enc:v1:", self.blob(rel))

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


class TestNoKey(RepoCase):
    def test_commit_refused_without_key(self):
        self.task()
        self.env.pop("ISA_KEY")
        r = self.commit_all()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no key", r.stderr)

    def test_hard_stop(self):
        self.env.pop("ISA_KEY")
        self.hook("UserPromptSubmit", prompt=PROMPT)
        rc, out = self.isa("new", "x")
        self.assertEqual(rc, 2)
        self.assertIn("isa key import FILE", out)
        p = self.isa_path("20260101-000000_x")
        _, hout, _ = self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": p, "content": E1})
        self.assertEqual(self.decision(hout), "deny")

    def test_wrong_key_values_stay_and_verify_refuses(self):
        path = self.task()
        rel = os.path.relpath(path, os.path.realpath(self.proj))
        self.commit_all()
        self.env["ISA_KEY"] = OTHER_KEY
        os.remove(path)
        self.git("checkout", "--", rel)
        self.assertIn("enc:v1:", read(path))
        rc, out = self.isa("verify", path)
        self.assertEqual(rc, 2)
        self.assertIn("not your key", out)


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
    def test_beside_relative_and_no_words(self):
        path = self.task()
        self.put("ok1", "")
        self.put("ok2", "")
        self.verify(path)
        led = os.path.join(os.path.dirname(path), "evidence.jsonl")
        self.assertTrue(os.path.isfile(led))
        rows = [json.loads(x) for x in read(led).splitlines()]
        self.assertTrue(all("id" in r and "machine" in r for r in rows))
        self.assertTrue(all(r.get("root") in (None, ".") for r in rows))
        self.assertNotIn("shout flag", read(led))
        snap = next(r for r in rows if r.get("kind") == "asks")
        self.assertTrue(all(a.startswith("hmac:v1:") for a in snap["asks"]))

    def test_probe_output_redacted(self):
        text = TASK.replace("tool: test -f ok1", f'tool: grep -c "{GOAL[:20]}" ISA.md >/dev/null; echo "{GOAL}"')
        path = self.task(text)
        self.verify(path, "ISC-1")
        self.assertNotIn(GOAL, read(os.path.join(os.path.dirname(path), "evidence.jsonl")))
        self.assertIn("[user words]", read(os.path.join(os.path.dirname(path), "evidence.jsonl")))

    def test_fingerprint_ignores_isa_files_and_close_succeeds(self):
        path = self.task()
        self.put("ok1", "")
        self.put("ok2", "")
        self.git("add", "-A")
        self.git("commit", "-qm", "flags")
        self.verify(path)
        self.write_isa(read(path).rstrip("\n") + "\n- Ask 1: met — ISC-1\n- Ask 2: met — ISC-2\n"
                       "- Goal: yes — the flag works\n", path)
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("changed the tree", out)

    def test_ids_survive_shifted_lines(self):
        path = self.task()
        self.put("ok2", "")
        self.verify(path, "ISC-2")
        led = os.path.join(os.path.dirname(path), "evidence.jsonl")
        rows = read(led)
        early = json.dumps({"v": 2, "t": 1.0, "kind": "note", "id": "0000000000"}) + "\n"
        with open(led, "w") as f:
            f.write(early * 3 + rows)  # a union merge put three rows first
        line = [x for x in read(path).splitlines() if x.startswith("- ISC-2: verified")][0]
        rid = line.rsplit("(ledger: ", 1)[1].rstrip(")")
        self.assertEqual(evidence.find(path, rid)["isc"], "ISC-2")

    def test_rows_sorted_by_time(self):
        path = self.task()
        evidence.record(path, [{"v": 2, "t": 50.0, "isc": "ISC-2", "kind": "verify", "ok": True, "tool_sha": "a"}])
        evidence.record(path, [{"v": 2, "t": 10.0, "isc": "ISC-2", "kind": "verify", "ok": False, "tool_sha": "b"}])
        self.assertEqual(evidence.latest(path)["ISC-2"]["tool_sha"], "a")


class TestTwoMachines(RepoCase):
    def test_continue_elsewhere(self):
        path = self.task()
        self.put("ok1", "")
        self.put("ok2", "")
        self.verify(path, "ISC-2")
        self.commit_all()
        bare = os.path.join(self.tmp, "remote.git")
        self.git("init", "-q", "--bare", bare, cwd=self.tmp)
        self.git("remote", "add", "origin", bare)
        self.git("push", "-q", "origin", "HEAD:main")
        b_home = os.path.join(self.tmp, "home-b")
        clone = tempfile.mkdtemp(prefix="isa-clone-", dir=os.path.expanduser("~/.cache"))
        try:
            env_b = dict(self.env, ISA_HOME=b_home)
            subprocess.run(["git", "clone", "-q", "-b", "main", bare, clone], env=env_b, check=True, capture_output=True)
            b_isa = os.path.join(clone, os.path.relpath(path, os.path.realpath(self.proj)))
            self.assertIn("enc:v1:", read(b_isa))  # filter not registered yet in this clone
            r = subprocess.run([sys.executable, ISA, "lint", b_isa], cwd=clone, env=env_b, text=True, capture_output=True)
            subprocess.run([sys.executable, ISA, "verify", b_isa, "ISC-1"], cwd=clone, env=env_b, text=True,
                           capture_output=True)
            r = subprocess.run(["git", "-C", clone, "config", "--local", "filter.isa.clean"], env=env_b, text=True,
                               capture_output=True)
            self.assertTrue(r.stdout.strip())  # the first command in the clone registered the filter
            self.assertIn(GOAL, read(b_isa))  # …and re-checked out the ISA plain
            self.write_isa(read(b_isa).rstrip("\n") + "\n- Ask 1: met — ISC-1\n- Ask 2: met — ISC-2\n"
                           "- Goal: yes — done\n", b_isa)
            for f in ("ok1", "ok2"):
                open(os.path.join(clone, f), "w").close()
            r = subprocess.run([sys.executable, ISA, "close", b_isa], cwd=clone, env=env_b, text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        finally:
            shutil.rmtree(clone, ignore_errors=True)

    def test_quote_verified_on_machine_without_prompt(self):
        path = self.task()
        rc, out = self.isa("lint", path)
        self.assertEqual(rc, 0, out)  # verified here, against this machine's prompt log
        shutil.rmtree(os.path.join(self.home, "_state", "prompts"))
        rc, out = self.isa("lint", path)
        self.assertNotIn("not a verbatim span", out)


class TestProjectIsa(RepoCase):
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
        text = TASK.replace("  tool: test -f ok2\n", "  tool: test -f ok2\n  promote: true\n")
        path = self.task(text)
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

    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)


class TestBranches(RepoCase):
    def test_bound_isa_missing_on_another_branch(self):
        path = self.task()
        self.commit_all()
        self.git("checkout", "-q", "-b", "other", "HEAD~1")
        self.assertFalse(os.path.exists(path))
        self.pid = "p2"
        from tests.test_hooks import setup_fake
        setup_fake(self, isa_gate=0.31)
        _, out, _ = self.hook("UserPromptSubmit", prompt="what does greet.py print?")
        self.assertIn("is not on this branch (other)", out.get("systemMessage", ""))
        self.hook("PostToolUse", tool_name="AskUserQuestion", tool_input={"questions": [{"question":
                  "ISA is not enabled for this prompt (Jev: 0.31). Continue?"}], "answers": {
                  "ISA is not enabled for this prompt (Jev: 0.31). Continue?": "Continue without ISA"}},
                  tool_response={})
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertNotIn("No ISA yet", err)
        self.git("checkout", "-q", "-")
        self.assertTrue(os.path.exists(path))
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            self.assertEqual(json.load(f)["bound"], os.path.realpath(path))


class TestMigrate(RepoCase):
    def test_moves_into_repo(self):
        key = state.project_key(self.proj)
        old = os.path.join(self.home, key, "20250101-000000_old", "ISA.md")
        os.makedirs(os.path.dirname(old))
        with open(old, "w") as f:
            f.write(TASK.replace("root: .", f"root: {os.path.realpath(self.proj)}")
                    .replace("20260101-000000_t", "20250101-000000_old")
                    + "\n## Verification\n\n- ISC-2: verified 2026-01-01T00:00:00 — exit 0 — `test -f ok2` "
                      "(ledger: 20250101-000000_old-abc#L1)\n")
        led_old = evidence.ledger_path(old)
        os.makedirs(os.path.dirname(led_old), exist_ok=True)
        with open(led_old, "w") as f:
            f.write(json.dumps({"v": 2, "t": 1.0, "isc": "ISC-2", "kind": "verify", "ok": True, "tool_sha": "x",
                                "root": os.path.realpath(self.proj), "tail": GOAL}) + "\n")
            f.write(json.dumps({"v": 2, "t": 2.0, "kind": "asks", "asks": ["with a test"]}) + "\n")
        self.hook("UserPromptSubmit", prompt=PROMPT)
        rc, out = self.isa("migrate")
        self.assertEqual(rc, 0, out)
        self.assertIn("1 ISA(s) moved", out)
        new = os.path.join(os.path.realpath(self.proj), ".isa", "20250101-000000_old", "ISA.md")
        self.assertTrue(os.path.isfile(new))
        self.assertFalse(os.path.exists(old))
        self.assertEqual(state.frontmatter(new)["root"], ".")
        led = read(os.path.join(os.path.dirname(new), "evidence.jsonl"))
        self.assertNotIn(GOAL, led)
        self.assertNotIn('"with a test"', led)
        rows = [json.loads(x) for x in led.splitlines()]
        line = [x for x in read(new).splitlines() if x.startswith("- ISC-2: verified")][0]
        self.assertIn(f"(ledger: {rows[0]['id']})", line)
        self.assertTrue(os.path.isfile(os.path.join(self.proj, "ISA.md")))


class TestExtras(RepoCase):
    def test_no_key_warning_when_on(self):
        from tests.test_hooks import setup_fake
        setup_fake(self, isa_gate=0.93)
        self.env.pop("ISA_KEY")
        _, out, _ = self.hook("UserPromptSubmit", prompt=PROMPT)
        self.assertIn("no key for this repo's ISA prompts", out.get("systemMessage", ""))

    def test_loose_quote_warned(self):
        path = self.task()
        with open(path, "a") as f:
            f.write(f"- 2026-01-01 00:01: the user wants to {GOAL[:60]} soon.\n")
        rc, out = self.isa("lint", path)
        self.assertIn("quotes the user's prompt outside the quoting forms", out)

    def test_ls_marks_missing_bound(self):
        path = self.task()
        self.commit_all()
        self.git("checkout", "-q", "-b", "other", "HEAD~1")
        r = subprocess.run([sys.executable, ISA, "ls"], cwd=self.proj, env=dict(self.env, CLAUDE_CODE_SESSION_ID=self.sid),
                           text=True, capture_output=True)
        self.assertIn("(not on this branch)", r.stdout)
        self.assertIn(os.path.basename(os.path.dirname(path)), r.stdout)


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
