"""ISA friction (docs/2026-10-13-isa-friction-01-spec.md): one class per spec section, one test per criterion of
its ISA. Same harness as test_foundations: real hooks, real `isa` commands, real git, a fake Jev.

Run: python3 -m unittest tests.test_friction
"""
import os
import re
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
from tests.test_derivation import Base  # noqa: E402
from tests.test_foundations import Case, ROOT  # noqa: E402

UNKNOWN = ['python3 -c "print(1)"', "node --test x.test.ts", "python3 -m unittest tests.x",
           'for f in a b; do grep -n x "$f"; done']
WRITES = ["rm a.txt", "mv a b", "echo x > a.txt", "sed -i s/a/b/ a.txt"]
HOOK_FORMS = ["echo '{}' | isa hook claude", "isa hook pi < e.json", "ISA_HOME=/tmp/x ~/.local/bin/isa hook claude < e.json",
              "python3 -m isa.cli hook claude < e.json", "true && isa hook claude"]


class Friction(Case):
    def bash(self, cmd, cwd=None):
        """PreToolUse of a Bash call → the refusal text, or None."""
        return self.deny(self.hook("PreToolUse", cwd=cwd, tool_name="Bash", tool_input={"command": cmd})[1])

    def edit(self, rel="a.txt"):
        return self.deny(self.hook("PreToolUse", tool_name="Edit", tool_input={
            "file_path": os.path.join(self.proj, rel), "old_string": "one", "new_string": "two"})[1])

    def stage(self):
        rc, out = self.isa("status", "--session", self.sid)
        return out

    def e1_with(self, *criteria):
        """ON, an E1 ISA with these criteria: (id, claim, probe, kind, fails-when or None)."""
        self.on()
        isa = self.path_of(self.ok("new", "demo", "--tier", "E1"), "ISA")
        self.ok("write", isa, "Problem", stdin="p\n")
        self.ok("write", isa, "Goal", stdin="g\n")
        for i, claim, probe, kind, fails in criteria:
            args = ["write", isa, i, claim] + (["--probe", probe] if probe else []) + ["--kind", kind]
            self.ok(*args + (["--fails-when", fails] if fails else []))
        return isa


# ------------------------------------------------------------------ S1

class S1(Friction):
    def stages_e1_e2(self, check):
        """`check(stage)` in TRIAGE, SPEC DRAFT and ISA DRAFT of an E2 session, and TRIAGE and ISA DRAFT of an E1."""
        self.on()
        check("TRIAGE")
        spec = self.spec()
        check("SPEC DRAFT")
        self.ack_spec(spec)
        self.isa_from(spec)
        check("ISA DRAFT")
        self.sid = "e1"
        self.on()
        check("TRIAGE")
        self.ok("new", "demo", "--tier", "E1")  # E1 is in ISA DRAFT until it lints
        check("ISA DRAFT")

    def test_unknown_runs_before_build(self):
        def check(stage):
            for cmd in UNKNOWN:
                self.assertIsNone(self.bash(cmd), f"{stage}: {cmd}")
        self.stages_e1_e2(check)

    def test_recognised_writes_refused(self):
        def check(stage):
            for r in [self.change(), self.edit()] + [self.bash(c) for c in WRITES]:
                self.assertIsNotNone(r, stage)
                self.assertIn(stage, r)
                self.assertIn("`isa ", r)
        self.stages_e1_e2(check)

    def test_guarded_refused_everywhere(self):
        isa_path = os.path.join(self.home, "x", "1_a", "ISA.md")

        def check(stage):
            for cmd in (f"echo x > {isa_path}", f"python3 -c \"open('{isa_path}', 'w')\""):
                r = self.bash(cmd)
                self.assertIsNotNone(r, f"{stage}: {cmd}")
                self.assertIn("written only by `isa` commands", r)
        self.stages_e1_e2(check)
        self.sid = "build"
        self.on()
        spec = self.spec(slug="built")
        self.ack_spec(spec)
        self.ack_isa(self.isa_from(spec))
        check("BUILD")


# ------------------------------------------------------------------ S2

class S2(Friction):
    def ack(self, spec):
        self.click("Spec ack", f"Acknowledge {os.path.relpath(spec, self.proj)}?")
        return self.run_isa("ack", spec)

    def test_non_spec_change_refuses_ack(self):
        self.on()
        spec = self.spec()
        self.put("src/a.py", "x = 1\n")
        head = self.git("rev-parse", "HEAD").stdout
        rc, out = self.ack(spec)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("src/a.py", out)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, head)
        self.assertIn("status: draft", self.read(spec))
        os.remove(os.path.join(self.proj, "src", "a.py"))
        self.ok("ack", spec)  # the same click
        self.assertRegex(self.read(spec), r"(?m)^status: \"?acked ")

    def test_baseline_files_not_listed(self):
        self.put("pre.txt", "mine\n")
        self.put("a.txt", "user edit\n")
        self.on()
        spec = self.spec()
        self.put("pre.txt", "mine, again\n")
        rc, out = self.ack(spec)
        self.assertEqual(rc, 0, out)

    def test_spec_related_paths(self):
        self.on()
        spec = self.spec()
        prefix = os.path.basename(spec)[:-len("-01-spec.md")]
        related = [f"docs/{prefix}-diagram.svg", f"docs/{prefix}/flow.png", f"docs/assets/{prefix}/x.png"]
        for rel in related + ["docs/other.md", "src/a.py"]:
            self.put(rel, "x\n")
        rc, out = self.ack(spec)
        self.assertNotEqual(rc, 0, out)
        listed = re.findall(r"(?m)^  - (\S+)$", out)
        self.assertEqual(sorted(listed), ["docs/other.md", "src/a.py"])
        for rel in ("docs/other.md", "src/a.py"):
            os.remove(os.path.join(self.proj, rel))
        self.ok("ack", spec)

    def test_no_git_in_hooks(self):
        log = os.path.join(self.tmp, "git.log")
        real = next(os.path.join(d, "git") for d in os.environ["PATH"].split(os.pathsep)
                    if os.access(os.path.join(d, "git"), os.X_OK))
        fake = self.put("git", f"#!/bin/sh\necho \"$@\" >> {log}\nexec {real} \"$@\"\n", base=os.path.join(self.tmp, "gb"))
        os.chmod(fake, 0o755)
        self.on()
        spec = self.spec()
        self.env["PATH"] = os.path.dirname(fake) + os.pathsep + self.env["PATH"]
        self.prompt("go on with the demo", "p2")
        self.bash("ls")
        self.change()
        self.hook("PostToolUse", tool_name="Bash", tool_input={"command": f"isa show {spec}"},
                  tool_response={"stdout": ""})
        self.hook("Stop")
        self.assertFalse(os.path.exists(log), self.read(log) if os.path.exists(log) else "")


# ------------------------------------------------------------------ S3

class S3(Friction):
    def words(self, prompt):
        self.env["CLAUDE_CODE_SESSION_ID"] = self.sid
        self.env["ISA_MODE"] = "on"
        self.prompt(prompt, "p1")

    def test_goal_pieces(self):
        self.words("I want you to update the status line ISA handler: make it short")
        for goal in ("update the status line ISA handler", "update the status line … handler",
                     "update  the status\nline ISA handler"):
            self.ok("new", "demo", "--tier", "E1", "--goal", goal)
        rc, out = self.run_isa("new", "demo", "--tier", "E1", "--goal", "update the ISA status line")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("update the status line ISA handler", out)
        self.assertIn("…", out)

    def test_ask_from_answer(self):
        self.words("plan the release")
        self.click("Deadline", "When should it ship?", answer="Ship it on Friday")
        self.ok("new", "demo", "--tier", "E1", "--ask", "Ship it on Friday")
        rc, out = self.run_isa("new", "demo", "--tier", "E1", "--ask", "Ship it on Monday")
        self.assertNotEqual(rc, 0, out)

    def test_per_criterion_only(self):
        self.on()
        isa = self.e1()
        self.assertEqual(self.isa("lint", isa)[0], 0, self.isa("lint", isa)[1])
        for section in ("Criteria", "Test Strategy"):
            rc, out = self.run_isa("write", isa, section, stdin="- [ ] ISC-9: x\n")
            self.assertNotEqual(rc, 0, out)
            self.assertIn("isa write <ISA> ISC-N", out)

    def test_anti_at_first_command(self):
        self.on()
        isa = self.e1()
        rc, out = self.run_isa("write", isa, "ISC-3", "Anti: x", "--probe", "true")
        self.assertNotEqual(rc, 0, out)
        self.assertIn('--fails-when "<what it would see>"', out)
        self.assertIn("isa write", out)
        self.assertNotIn("ISC-3", self.read(isa))
        self.ok("write", isa, "ISC-3", "Anti: x", "--probe", "true", "--fails-when", "x shows up")
        from isa import isafile
        self.assertEqual(isafile.entry(isafile.parse(self.read(isa)), "3")["kind"], "regression")

    def test_manual_kind(self):
        self.on()
        isa = self.e1()
        self.ok("write", isa, "ISC-3", "The output reads well.", "--kind", "manual")
        self.assertEqual(self.isa("lint", isa)[0], 0, self.isa("lint", isa)[1])
        self.assertNotIn("ISC-3", self.ok("verify", isa, "--red").split("progress")[0])
        self.put("ok", "")
        self.assertNotIn("ISC-3 ", self.ok("verify", isa))
        self.ok("answer", isa, "goal", "yes — ok")
        rc, out = self.run_isa("close", isa)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("ISC-3", out)
        self.ok("attest", isa, "ISC-3", "read it at 60 columns")
        self.ok("close", isa)

    def test_spec_sections_by_number(self):
        self.on()
        spec = self.spec()
        self.ok("write", spec, "S1 — The renamed part", stdin="New.\nAccepted when:\n- `ok` exists\n")
        text = self.read(spec)
        self.assertEqual(len(re.findall(r"(?m)^## S1 — ", text)), 1)
        self.assertIn("## S1 — The renamed part", text)
        self.ok("write", spec, "S2 — Two", stdin="Two.\nAccepted when:\n- two\n")
        self.ok("drop", spec, "S2", "not needed")
        self.assertNotIn("## S2", self.read(spec))
        self.ack_spec(spec)
        for args in (("write", spec, "S1 — Again"), ("drop", spec, "S1", "x")):
            rc, out = self.run_isa(*args, stdin="x\n" if args[0] == "write" else None)
            self.assertNotEqual(rc, 0, out)
            self.assertIn("isa reopen", out)

    def test_classifier_quotes_and_loops(self):
        from isa import classify
        self.assertEqual(classify.bash('isa new x --goal "a \\`b\\` c"', self.proj), "isa-cmd")
        self.assertEqual(classify.bash("for n in 1 2; do isa write F ISC-$n --probe x; done", self.proj), "isa-cmd")
        self.assertEqual(classify.bash('for f in a b; do grep x "$f"; done', self.proj), "read")
        self.assertEqual(classify.bash("for f in a b; do rm $f; done", self.proj), "write")

    def test_leaf_to_parent_no_probe(self):
        self.on()
        spec = self.spec()
        self.ack_spec(spec)
        isa = self.isa_from(spec)
        self.ok("write", isa, "ISC-2", "Anti: the file bad exists.", "--probe", "test ! -e bad", "--fails-when", "bad",
                "--anchors", "Goal")
        rc, out = self.run_isa("write", isa, "ISC-2.1", "bad is never written")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("ISC-2 --no-probe", out)
        self.ok("write", isa, "ISC-2", "--no-probe")
        from isa import isafile
        self.assertIsNone(isafile.entry(isafile.parse(self.read(isa)), "2"))
        self.ok("write", isa, "ISC-2.1", "Anti: bad is never written", "--probe", "test ! -e bad", "--fails-when",
                "bad", "--anchors", "Goal")
        self.assertNotIn("is a parent", self.isa("lint", isa)[1])


# ------------------------------------------------------------------ S4

class S4(Friction):
    def setUp(self):
        super().setUp()
        self.log = os.path.join(self.tmp, "runs.log")
        self.isa_path = self.e1_with(*[(f"ISC-{n}", f"f{n} exists", self.probe(n), "behaviour", None) for n in (1, 2, 3)],
                                     ("ISC-4", "Anti: bad exists", f"echo 4 >> {self.log}; test ! -e bad",
                                      "regression", "bad exists"))

    def probe(self, n):
        return f"echo {n} >> {self.log}; test -f f{n}"

    def ran(self):
        runs = self.read(self.log).split() if os.path.exists(self.log) else []
        if os.path.exists(self.log):
            os.remove(self.log)
        return sorted(runs)

    def green(self):
        self.run_isa("verify", self.isa_path, "--red")
        for n in (1, 2, 3):
            self.put(f"f{n}", "")
        self.ok("verify", self.isa_path)
        self.ran()

    def test_red_runs_behaviour_only(self):
        self.run_isa("verify", self.isa_path, "--red")
        self.assertEqual(self.ran(), ["1", "2", "3"])

    def test_verify_skips_green(self):
        self.run_isa("verify", self.isa_path, "--red")
        self.ran()
        for n in (1, 2, 3):
            self.put(f"f{n}", "")
        self.ok("verify", self.isa_path)
        self.assertEqual(self.ran(), ["1", "2", "3", "4"])
        out = self.ok("verify", self.isa_path)
        self.assertEqual(self.ran(), [])
        self.assertIn("nothing to run", out)

    def test_verify_changed_and_named(self):
        self.green()
        self.ok("write", self.isa_path, "ISC-2", "--probe", self.probe(2) + " && true")
        self.ok("verify", self.isa_path)
        self.assertEqual(self.ran(), ["2"])
        self.ok("verify", self.isa_path, "ISC-1")
        self.assertEqual(self.ran(), ["1"])

    def test_close_runs_each_once(self):
        self.green()
        self.ok("answer", self.isa_path, "goal", "yes — all four")
        self.ok("close", self.isa_path)
        self.assertEqual(self.ran(), ["1", "2", "3", "4"])


# ------------------------------------------------------------------ S5

NOISY = "sh -c 'test -f ok && exit 0; echo first; seq 1 100; echo boom >&2; exit 3'"


class S5(Friction):
    def noisy(self):
        return self.e1_with(("ISC-1", "ok exists", NOISY, "behaviour", None),
                            ("ISC-2", "Anti: bad exists", "test ! -e bad", "regression", "bad exists"))

    def shown(self, out):
        return [ln[6:] for ln in out.splitlines() if ln.startswith("    | ")]

    def test_failure_output_verify(self):
        isa = self.noisy()
        rc, out = self.run_isa("verify", isa)
        self.assertEqual(rc, 1, out)
        shown = self.shown(out)
        self.assertIn("boom", shown)
        self.assertIn("100", shown)
        self.assertNotIn("first", shown)
        self.assertEqual(len(shown), 40)
        log = self.read(os.path.join(os.path.dirname(isa), "runs", "ISC-1.log"))
        self.assertEqual(len(log.splitlines()), 102)

    def test_failure_output_close(self):
        isa = self.noisy()
        self.put("ok", "")
        self.ok("verify", isa)
        self.ok("answer", isa, "goal", "yes — ok")
        os.remove(os.path.join(self.proj, "ok"))
        rc, out = self.run_isa("close", isa)
        self.assertNotEqual(rc, 0, out)
        shown = self.shown(out)
        self.assertIn("boom", shown)
        self.assertIn("100", shown)
        self.assertNotIn("first", shown)

    def test_red_pass_flagged(self):
        isa = self.e1_with(("ISC-1", "true holds", "true", "behaviour", None),
                           ("ISC-2", "Anti: bad exists", "test ! -e bad", "regression", "bad exists"))
        rc, out = self.run_isa("verify", isa, "--red")
        self.assertEqual(rc, 0, out)
        self.assertIn("⚠", out)
        self.assertIn("ISC-1 passed before the build: this probe proves nothing yet", out)
        red = next(ln for ln in self.read(isa).splitlines() if ln.startswith("- ISC-1: red "))
        self.assertIn("red PASS ⚠ not seen failing", red)

    def test_close_lists_never_seen_failing(self):
        spec, isa = self.build()
        self.put("ok", "")
        self.ok("verify", isa, "--red")
        self.finish(isa)
        out = self.ok("close", isa)
        self.assertRegex(out, r"Never seen failing.*ISC-1\.1")
        self.assertIn("Never seen failing: ISC-1.1", self.read(spec.replace("-01-spec.md", "-02-plan.md")))

    def test_open_writable(self):
        self.on()
        isa = self.e1()
        for name in ("nvim", "vim", "vi"):
            exe = self.put(name, f"#!/bin/sh\necho \"$@\" > {self.tmp}/args\n", base=os.path.join(self.tmp, "bin"))
            os.chmod(exe, 0o755)
            self.env["ISA_EDITOR"] = exe
            rc, out = self.isa("open", "--session", self.sid)
            self.assertEqual(rc, 0, out)
            self.assertEqual(self.read(os.path.join(self.tmp, "args")).strip(), isa)


# ------------------------------------------------------------------ S6

class S6(Friction):
    def stages(self, check):
        """`check(stage)` with the session OFF, in TRIAGE, SPEC DRAFT and BUILD."""
        check("OFF")
        self.sid = "on"
        self.on()
        check("TRIAGE")
        self.spec(slug="other")
        check("SPEC DRAFT")
        self.sid = "build"
        self.build()
        check("BUILD")

    def test_hook_from_tool_call_refused(self):
        spec = os.path.join(self.proj, "docs", time.strftime("%Y-%m-%d") + "-demo-01-spec.md")

        def check(stage):
            for cmd in HOOK_FORMS:
                r = self.bash(cmd)
                self.assertIsNotNone(r, f"{stage}: {cmd}")
                self.assertIn("only the harness runs `isa hook`", r)
            for cmd in ("isa status", f"isa ack {spec}", f"isa lint {spec}",
                        f"grep -n hook {os.path.join(ROOT, 'runtime', 'isa', 'cli.py')}"):
                self.assertIsNone(self.bash(cmd), f"{stage}: {cmd}")
        self.stages(check)

    def test_open_from_tool_call_refused(self):
        def check(stage):
            for cmd in ("isa open", "isa open spec", "ISA_EDITOR=sed isa open isa", "isa serve", "isa serve --port 9000"):
                r = self.bash(cmd)
                self.assertIsNotNone(r, f"{stage}: {cmd}")
                self.assertIn("`isa open` and `isa serve` are for the user's own terminal", r)
            self.assertIsNone(self.bash("isa open --print"), stage)
        self.stages(check)


# ------------------------------------------------------------------ S7

class S7(Base):
    def flagged(self, about="ISC-"):
        """An E2 ISA reviewed with every question flagged → (ISA, the first flag about `about…`, what it is about)."""
        self.fake(0.1)
        _, isa = self.ready()
        self.review(isa)
        rows = re.findall(r"(?m)^- (R\d+): \w+ (\S+) — ", self.read(isa))
        f, what = next((f, a) for f, a in rows if a.startswith(about))
        return isa, f, what

    def answer(self, isa, f, text):
        return self.run_isa("review", isa, "--answer", f, text)

    def test_rebuttal_removed(self):
        isa, f, _ = self.flagged()
        rc, out = self.answer(isa, f, "rebuttal: x")
        self.assertNotEqual(rc, 0, out)
        for a in ("keep:", "drop:", "fix:", "reopen:"):
            self.assertIn(a, out)

    def test_keep_needs_a_real_reason(self):
        isa, f, _ = self.flagged()
        for bad in ("keep: S3 asks for it", "keep: the spec's Accepted when names it"):
            rc, out = self.answer(isa, f, bad)
            self.assertNotEqual(rc, 0, out)
        rc, out = self.answer(isa, f, "keep: without it a broken parser would pass unnoticed")
        self.assertEqual(rc, 0, out)

    def test_drop_needs_the_drop(self):
        isa, f, what = self.flagged()
        rc, out = self.answer(isa, f, "drop: duplicate of ISC-7")
        self.assertNotEqual(rc, 0, out)
        self.assertIn(f"isa drop", out)
        self.ok("drop", isa, what, "duplicate")
        rc, out = self.answer(isa, f, "drop: duplicate of ISC-7")
        self.assertEqual(rc, 0, out)

    def test_fix_needs_a_change(self):
        isa, f, what = self.flagged()
        rc, out = self.answer(isa, f, "fix: the claim was vague")
        self.assertNotEqual(rc, 0, out)
        self.ok("write", isa, what, "A sharper claim about the ok file.")
        rc, out = self.answer(isa, f, "fix: the claim was vague; sharpened")
        self.assertEqual(rc, 0, out)

    def test_checklist_needs_redundant(self):
        _, isa = self.ready()
        rc, out = self.review(isa, "shared: none\nprerequisites: none\ncontradictions: none\ndrift: none\ngaps: none\n"
                                   "context: none\n")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("redundant:", out)


if __name__ == "__main__":
    unittest.main()
