"""The three foundations (docs/spec/2026-10-06-gate-close-issues.md), end to end through the hooks and the
`isa` commands, the way the model drives them: every command runs between its PreToolUse and PostToolUse
hooks, clicks arrive as AskUserQuestion answers, projects are real git repos. No model, no real Jev.

Run: python3 -m unittest tests.test_foundations
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISA = os.path.join(ROOT, "runtime", "bin", "isa")
sys.path.insert(0, os.path.join(ROOT, "runtime"))

GATE_Q = ("Does this message ask for work with several dependent steps, where a mistake in one step could carry "
          "into the final result unnoticed unless each step is checked")

FAKE_JEV = """#!/usr/bin/env python3
import json, os, sys
preset = sys.argv[2]
qs = {"isa-gate": ["work"], "isa-continuation": ["new_task", "resumes"]}.get(preset, ["answer"])
p = float(os.environ.get("FAKE_JEV_P", "0.5"))
print(json.dumps({"ok": True, "answers": {q: {"answer": p} for q in qs}}))
"""

SPEC_BODY = {
    "Title": "Demo tool",
    "Problem": "The demo tool has no ok file.",
    "Goal": "The tool writes an ok file and never a bad one.\nSaid:\n- make the tool write ok\nAssumed:\n- ok is empty.",
    "Out of scope": "Anything but the ok file.",
    "Constraints": "- Plain files only.",
    "Approaches": "1. Touch the file (chosen): simplest.\n2. A daemon: too much. Rejected.",
    "S1 — The ok file": "The tool creates `ok`.\nAccepted when:\n- `ok` exists\n- `bad` never exists",
}

E1_CRITERIA = "- [ ] ISC-1: The file ok exists.\n- [ ] ISC-2: Anti: the file bad exists.\n"
E1_TESTS = ("- isc: ISC-1\n  kind: behaviour\n  tool: test -f ok\n"
            "- isc: ISC-2\n  kind: regression\n  tool: test ! -e bad\n  fails-when: \"bad exists\"\n")
E2_CRITERIA = ("- [ ] ISC-1: The ok file is written.\n  - [ ] ISC-1.1: The file ok exists.\n"
               "  - [ ] ISC-1.2: Anti: the file bad exists.\n")
E2_TESTS = ("- isc: ISC-1.1\n  anchors_to: S1\n  kind: behaviour\n  tool: test -f ok\n"
            "- isc: ISC-1.2\n  anchors_to: S1\n  kind: regression\n  tool: test ! -e bad\n  fails-when: \"bad exists\"\n")


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="isa-f-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        self.proj = os.path.join(self.tmp, "proj")
        os.makedirs(self.proj)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("ISA_") and not k.startswith("CLAUDE_CODE")}
        self.env.update(ISA_HOME=self.home, ISA_JEV_BIN=os.path.join(self.tmp, "no-jev"), GIT_AUTHOR_NAME="t",
                        GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        self.git("init", "-q")
        self.put("a.txt", "one\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")
        self.sid, self.pid = "s1", "p1"

    # -- plumbing
    def git(self, *args, cwd=None):
        return subprocess.run(["git", "-C", cwd or self.proj, *args], capture_output=True, text=True, env=self.env)

    def put(self, rel, text, base=None):
        p = os.path.join(base or self.proj, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        return p

    def read(self, p):
        with open(p) as f:
            return f.read()

    def fake_jev(self, p):
        exe = self.put("fake-jev", FAKE_JEV, base=self.tmp)
        os.chmod(exe, 0o755)
        self.env.update(ISA_JEV_BIN=exe, FAKE_JEV_P=str(p))

    def isa(self, *args, stdin=None, cwd=None):
        p = subprocess.run([sys.executable, ISA, *args], input=stdin or "", cwd=cwd or self.proj, env=self.env, text=True,
                           capture_output=True, timeout=120)
        return p.returncode, p.stdout + p.stderr

    def hook(self, name, cwd=None, **kw):
        d = {"hook_event_name": name, "session_id": self.sid, "cwd": cwd or self.proj, "prompt_id": self.pid,
             "transcript_path": "/dev/null"}
        d.update(kw)
        p = subprocess.run([sys.executable, ISA, "hook", "claude"], input=json.dumps(d), text=True,
                           capture_output=True, env=self.env, timeout=60)
        return p.returncode, (json.loads(p.stdout) if p.stdout.strip() else {}), p.stderr

    def run_isa(self, *args, stdin=None, cwd=None):
        """An `isa` command as the model runs it: PreToolUse, the command, PostToolUse."""
        cmd = "isa " + " ".join(shlex.quote(a) for a in args) + (" <<'EOF'\n" + stdin + "EOF" if stdin else "")
        _, pre, _ = self.hook("PreToolUse", cwd=cwd, tool_name="Bash", tool_input={"command": cmd})
        self.assertIsNone(self.deny(pre), f"PreToolUse refused `{cmd}`")
        rc, out = self.isa(*args, stdin=stdin, cwd=cwd)
        self.hook("PostToolUse", cwd=cwd, tool_name="Bash", tool_input={"command": cmd},
                  tool_response={"stdout": out})
        return rc, out

    def ok(self, *args, stdin=None, cwd=None):
        rc, out = self.run_isa(*args, stdin=stdin, cwd=cwd)
        self.assertEqual(rc, 0, out)
        return out

    @staticmethod
    def deny(out):
        return (out.get("hookSpecificOutput") or {}).get("permissionDecisionReason")

    @staticmethod
    def context(out):
        return (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""

    def prompt(self, text, pid):
        self.pid = pid
        return self.hook("UserPromptSubmit", prompt=text)

    def change(self, rel="b.txt"):
        """PreToolUse of a project change → the refusal text, or None."""
        return self.deny(self.hook("PreToolUse", tool_name="Write",
                                   tool_input={"file_path": os.path.join(self.proj, rel), "content": "x"})[1])

    def click(self, header, question, answer="Acknowledge"):
        """The model asks (no `answers` at PreToolUse); the user's pick arrives at PostToolUse."""
        ti = {"questions": [{"question": question, "header": header, "multiSelect": False,
                             "options": [{"label": "Acknowledge", "description": "a"},
                                         {"label": "Request changes", "description": "b"}]}]}
        _, pre, _ = self.hook("PreToolUse", tool_name="AskUserQuestion", tool_input=ti)
        self.assertIsNone(self.deny(pre), "the ack question was refused")
        return self.hook("PostToolUse", tool_name="AskUserQuestion", tool_input=dict(ti, answers={question: answer}),
                         tool_response={})[1]

    def path_of(self, out, kind):
        line = next(ln for ln in out.splitlines() if ln.startswith(kind + ": "))
        return line.split(": ", 1)[1].strip()

    # -- the lifecycle, step by step
    def on(self):
        self.env["ISA_MODE"] = "on"
        self.prompt("build the demo tool", "p1")

    def spec(self, slug="demo", tier="E2", body=None):
        path = self.path_of(self.ok("spec", "new", slug, "--tier", tier), "Spec")
        for section, text in (body or SPEC_BODY).items():
            if section == "Approaches" and tier == "E2":
                continue
            self.ok("write", path, section, stdin=text + "\n")
        return path

    def ack_spec(self, path):
        self.click("Spec ack", f"Acknowledge {os.path.relpath(path, self.proj)}?")
        return self.ok("ack", path)

    def isa_from(self, spec, criteria=E2_CRITERIA, tests=E2_TESTS):
        path = self.path_of(self.ok("new", "--spec", spec), "ISA")
        for section in ("Vision", "Principles"):
            self.ok("write", path, section, stdin=f"The {section.lower()} of the demo.\n")
        self.ok("write", path, "Criteria", stdin=criteria)
        self.ok("write", path, "Test Strategy", stdin=tests)
        return path

    def ack_isa(self, path):
        self.click("ISA ack", "Acknowledge the ISA of this task?")
        return self.ok("ack", path)

    def e1(self, criteria=E1_CRITERIA, tests=E1_TESTS):
        path = self.path_of(self.ok("new", "demo", "--tier", "E1"), "ISA")
        self.ok("write", path, "Problem", stdin="No ok file.\n")
        self.ok("write", path, "Goal", stdin="The ok file exists.\n")
        self.ok("write", path, "Criteria", stdin=criteria)
        self.ok("write", path, "Test Strategy", stdin=tests)
        return path

    def build(self):
        """An E2 task through SPEC → ISA → both acks: BUILD."""
        self.on()
        spec = self.ack_spec_path = self.spec()
        self.ack_spec(spec)
        isa = self.isa_from(spec)
        self.ack_isa(isa)
        return spec, isa

    def finish(self, isa):
        self.put("ok", "")
        self.ok("verify", isa)
        self.ok("answer", isa, "goal", "yes — the ok file exists")


def _isa_text(effort, criteria, tests, extra=None, spec=None):
    sections = {"Problem": "p", "Goal": "g", "Criteria": criteria, "Test Strategy": "```yaml\n" + tests + "```"}
    if effort != "E1":
        sections = {"Problem": "p", "Vision": "v", "Out of Scope": "o", "Principles": "pr", "Constraints": "c",
                    "Goal": "g", "Criteria": criteria, "Test Strategy": "```yaml\n" + tests + "```"}
    sections.update(extra or {})
    fm = f"---\ntask: \"t\"\nslug: x\neffort: {effort}\nphase: draft\nprogress: 0/0\nroot: /tmp\n"
    fm += f"spec: {spec}\n" if spec else ""
    return fm + "---\n\n" + "".join(f"## {k}\n\n{v}\n\n" for k, v in sections.items() if v is not None)


class Tiers(Case):
    """S2: the tier sets the documents and the depth of the criteria tree."""

    def lint_text(self, text, spec=None):
        p = self.put("x/ISA.md", text, base=self.home)
        return self.isa("lint", p)

    def nested(self, depth):
        lines, tests, ids = [], [], []
        for d in range(1, depth + 1):
            ids.append("1")
            lines.append("  " * (d - 1) + f"- [ ] ISC-{'.'.join(ids)}: level {d}.")
        lines.append("- [ ] ISC-2: Anti: the file bad exists.")
        leaf = "ISC-" + ".".join(ids)
        tests = (f"- isc: {leaf}\n  anchors_to: S1\n  kind: regression\n  tool: \"true\"\n  fails-when: \"x\"\n"
                 "- isc: ISC-2\n  anchors_to: S1\n  kind: regression\n  tool: test ! -e bad\n  fails-when: \"bad\"\n")
        return "\n".join(lines) + "\n", tests

    def spec_file(self):
        from isa import spec as specmod
        text = specmod.template("Demo", "E2")
        for k, v in SPEC_BODY.items():
            if k != "Approaches":
                text = specmod.set_section(text, k, v)
        text = text.replace("status: draft", f"status: acked 2026-10-07 #{specmod.ack_hash(text)}")
        return self.put("docs/2026-10-07-demo-01-spec.md", text)

    def test_depth_limit(self):
        spec = self.spec_file()
        c, t = self.nested(2)
        rc, out = self.lint_text(_isa_text("E1", c, t.replace("  anchors_to: S1\n", "")))
        self.assertNotEqual(rc, 0, out)
        self.assertIn("ISC-1.1", out)
        self.assertIn("E1 allows 1", out)
        for effort, depth, ok in (("E2", 2, True), ("E2", 3, False), ("E3", 3, True), ("E3", 4, False),
                                  ("E4", 6, True)):
            c, t = self.nested(depth)
            rc, out = self.lint_text(_isa_text(effort, c, t, spec=spec))
            self.assertEqual(rc == 0, ok, f"{effort} depth {depth}: {out}")

    def test_probes_on_leaves(self):
        c = "- [ ] ISC-1: parent.\n  - [ ] ISC-1.1: leaf.\n- [ ] ISC-2: Anti: bad.\n"
        t = ("- isc: ISC-1\n  kind: regression\n  tool: \"true\"\n  fails-when: \"x\"\n"
             "- isc: ISC-2\n  kind: regression\n  tool: \"true\"\n  fails-when: \"x\"\n")
        spec = self.spec_file()
        rc, out = self.lint_text(_isa_text("E2", c, t.replace("  kind", "  anchors_to: S1\n  kind"), spec=spec))
        self.assertNotEqual(rc, 0, out)
        self.assertIn("ISC-1 is a parent", out)
        self.assertIn("ISC-1.1 has no Test Strategy entry", out)

    def test_parent_box(self):
        spec, isa = self.build()
        self.put("ok", "")
        self.ok("verify", isa, "ISC-1.1")
        text = self.read(isa)
        self.assertIn("- [1/2] ISC-1: ", text)
        self.assertIn("  - [x] ISC-1.1: ", text)
        self.ok("verify", isa)
        self.assertIn("- [x] ISC-1: ", self.read(isa))

    def test_tier_sections(self):
        spec = self.spec_file()
        rc, out = self.lint_text(_isa_text("E5", E2_CRITERIA, E2_TESTS, spec=spec))
        self.assertIn("effort: E5", out)
        rc, out = self.lint_text(_isa_text("E1", E1_CRITERIA, E1_TESTS, extra={"Vision": "v"}))
        self.assertIn("E1 has no `## Vision`", out)
        rc, out = self.lint_text(_isa_text("E2", E2_CRITERIA, E2_TESTS, extra={"Principles": None}, spec=spec))
        self.assertIn("missing `## Principles`", out)
        rc, out = self.lint_text(_isa_text("E2", E2_CRITERIA, E2_TESTS, extra={"Features": "f"}, spec=spec))
        self.assertIn("`## Features`", out)


class Lifecycle(Case):
    """S3: the gate's question and the fixed lifecycle."""

    def test_gate_question(self):
        with open(os.path.join(ROOT, "runtime", "isa", "jev", "isa-gate.json")) as f:
            self.assertIn(GATE_Q, json.load(f)["questions"]["work"]["instructions"])
        _, out, _ = self.prompt("refactor the parser and its tests", "p1")  # no Jev: the model judges
        self.assertIn(GATE_Q, self.context(out))

    def test_stage_refusals(self):
        self.on()
        self.assertIn("TRIAGE", self.change())
        self.assertIn("isa spec new", self.change())
        spec = self.spec()
        self.assertIn("SPEC DRAFT", self.change())
        self.ack_spec(spec)
        r = self.change()
        self.assertIn("SPEC ACKED", r)
        self.assertIn("isa new --spec", r)
        isa = self.isa_from(spec)
        r = self.change()
        self.assertIn("ISA DRAFT", r)
        self.assertIn("ISA ack", r)
        self.ack_isa(isa)
        self.assertIsNone(self.change())

    def test_question_not_skippable(self):
        self.fake_jev(0.5)
        _, out, _ = self.prompt("rename the module", "p1")
        self.assertIn("AskUserQuestion", self.context(out))
        self.e1()  # an ISA bound in the same turn does not answer the question
        rc, _, err = self.hook("Stop")
        self.assertEqual(rc, 2, err)
        self.assertIn("ISA is not enabled for this prompt", err)

    def test_isa_needs_acks(self):
        self.on()
        spec = self.spec()
        rc, out = self.run_isa("new", "--spec", spec)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("not acked", out)
        self.ack_spec(spec)
        isa = self.isa_from(spec)
        self.assertEqual(self.isa("lint", isa)[0], 0)
        self.assertIn("ISA DRAFT", self.change())
        self.ack_isa(isa)
        self.assertIsNone(self.change())


class Specs(Case):
    """S4: the spec, its reopen and its change summary."""

    def test_spec_new(self):
        self.on()
        out = self.ok("spec", "new", "demo", "--tier", "E3")
        path = self.path_of(out, "Spec")
        self.assertEqual(path, os.path.join(self.proj, "docs", time.strftime("%Y-%m-%d") + "-demo-01-spec.md"))
        text = self.read(path)
        self.assertIn("status: draft\n", text)
        self.assertIn("effort: E3\n", text)
        self.assertIn("SPEC DRAFT", self.change())

    def test_spec_lint(self):
        self.on()
        path = self.spec()
        self.assertEqual(self.isa("lint", path)[0], 0)
        for bad in ("- [ ] `ok` exists", "- A1: `ok` exists", "- `ok` exists  (2026-10-07, ISA x)"):
            self.ok("write", path, "S1 — The ok file", stdin=f"The tool creates `ok`.\nAccepted when:\n{bad}\n")
            rc, out = self.isa("lint", path)
            self.assertNotEqual(rc, 0, bad)
            self.assertIn("Accepted when", out)

    def test_reopen(self):
        self.on()
        path = self.spec()
        self.ack_spec(path)
        rc, out = self.run_isa("write", path, "Problem", stdin="Changed.\n")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("isa reopen", out)
        self.ok("reopen", path)
        self.assertIn("status: draft\n", self.read(path))
        self.ok("write", path, "Problem", stdin="Changed.\n")

    def test_diff(self):
        self.on()
        path = self.spec()
        self.ack_spec(path)
        self.ok("reopen", path)
        self.ok("write", path, "S1 — The ok file", stdin="The tool creates `ok` now.\nAccepted when:\n- `ok` exists\n")
        self.ok("write", path, "S2 — The log", stdin="The tool logs.\nAccepted when:\n- a log line\n")
        out = self.ok("diff", path)
        self.assertEqual(out.strip().splitlines(), ["Demo tool — changed since its ack:", "  ~ S1 — The ok file",
                                                    "  + S2 — The log"])

    def test_reopened_blocks_build(self):
        spec, isa = self.build()
        self.assertIsNone(self.change())
        self.ok("reopen", spec)
        self.assertIn("SPEC DRAFT", self.change())
        self.ok("write", spec, "Problem", stdin="The demo tool has no ok file yet.\n")
        self.ack_spec(spec)
        self.assertIn("isa refine", self.change())
        self.ok("refine", isa)
        self.assertIn("ISA DRAFT", self.change())
        self.ack_isa(isa)
        self.assertIsNone(self.change())

    def test_new_from_spec(self):
        self.on()
        spec = self.spec()
        self.ack_spec(spec)
        first = self.path_of(self.ok("new", "--spec", spec), "ISA")
        again = self.path_of(self.ok("new", "--spec", spec), "ISA")
        self.assertEqual(first, again)
        self.put(os.path.join("docs", os.path.basename(spec).replace("-01-spec.md", "-02-plan.md")), "done\n")
        rc, out = self.run_isa("new", "--spec", spec)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("finished", out)


class Proof(Case):
    """S5: the ISA written through commands, its proof in its own Verification."""

    def test_block_write_once(self):
        self.on()
        isa = self.e1()
        rc, out = self.run_isa("write", isa, "Criteria", stdin=E1_CRITERIA)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("isa write", out)
        self.assertIn("ISC-N", out)

    def test_isc_write_and_drop(self):
        self.on()
        isa = self.e1()
        self.put("ok", "")
        self.ok("verify", isa)
        self.assertIn("- [x] ISC-1: ", self.read(isa))
        self.ok("write", isa, "ISC-2", "Anti: the file bad ever exists.")
        text = self.read(isa)
        self.assertIn("- [x] ISC-1: ", text)
        self.assertIn("- [ ] ISC-2: Anti: the file bad ever exists.", text)
        self.ok("write", isa, "ISC-3", "The file ok is empty.")
        self.ok("write", isa, "ISC-3", "--probe", "test ! -s ok", "--kind", "regression", "--fails-when", "ok has text")
        self.assertEqual(self.isa("lint", isa)[0], 0)
        rc, out = self.run_isa("write", isa, "ISC-3.1", "Too deep for E1.")
        self.assertNotEqual(rc, 0, out)
        self.ok("drop", isa, "ISC-3", "not needed")
        self.assertIn("- [ ] ISC-3: [DROPPED — not needed]", self.read(isa))
        rc, out = self.run_isa("write", isa, "ISC-3", "Reused id.")
        self.assertNotEqual(rc, 0, out)

    def test_isc_change_breaks_ack(self):
        spec, isa = self.build()
        self.assertIsNone(self.change())
        self.ok("write", isa, "ISC-1.1", "The file ok exists in the project.")
        r = self.change()
        self.assertIn("changed since its ack", r)
        self.ack_isa(isa)
        self.assertIsNone(self.change())

    def test_verification_lines(self):
        self.on()
        isa = self.e1()
        self.run_isa("verify", "--red", isa)
        self.put("ok", "")
        self.ok("verify", isa)
        text = self.read(isa)
        self.assertRegex(text, r"\n- ISC-1: red \S+ \S+ exit 1 — `test -f ok`\n")
        self.assertRegex(text, r"\n- ISC-1: verified \S+ \S+ exit 0 — `test -f ok`\n")
        self.assertFalse(os.path.exists(os.path.join(self.home, "_state", "evidence")))

    def test_red_baseline(self):
        self.on()
        isa = self.e1()
        self.put("ok", "")
        self.ok("verify", isa)
        self.assertRegex(self.read(isa), r"- ISC-1: verified .* \(no red baseline\)\n")

    def test_show_to_criteria(self):
        spec, isa = self.build()
        out = self.ok("show", isa, "--to", "Criteria")
        for s in ("## Problem", "## Vision", "## Out of Scope", "## Principles", "## Constraints", "## Goal",
                  "## Criteria", "ISC-1.1"):
            self.assertIn(s, out)
        self.assertNotIn("## Test Strategy", out)


class Close(Case):
    """S6: the close writes the plan and the commits."""

    def plan_path(self, spec):
        return spec.replace("-01-spec.md", "-02-plan.md")

    def test_plan_file(self):
        spec, isa = self.build()
        self.ok("decide", isa, "touch was enough")
        self.finish(isa)
        self.ok("close", isa)
        plan = self.read(self.plan_path(spec))
        heads = [ln[3:] for ln in plan.splitlines() if ln.startswith("## ")]
        self.assertEqual(heads, ["Problem", "Vision", "Out of Scope", "Principles", "Constraints", "Goal", "Criteria",
                                 "Test Strategy", "Decisions", "Verification"])
        self.assertIn("touch was enough", plan)
        self.assertIn("- Goal: yes — the ok file exists", plan)
        self.assertNotRegex(plan, r"ISC-[\d.]+: (verified|red|failed) ")

    def test_commits(self):
        spec, isa = self.build()
        log = self.git("log", "--format=%s", "--name-only").stdout
        self.assertIn("(acked)", log.splitlines()[0])
        self.assertEqual(self.git("show", "--format=", "--name-only", "HEAD").stdout.split(),
                         [os.path.relpath(spec, self.proj)])
        self.put("lib.txt", "work\n")
        self.finish(isa)
        self.ok("close", isa)
        self.assertEqual(self.git("show", "--format=", "--name-only", "HEAD").stdout.split(),
                         [os.path.relpath(self.plan_path(spec), self.proj)])
        self.assertEqual(sorted(self.git("show", "--format=", "--name-only", "HEAD~1").stdout.split()),
                         ["lib.txt", "ok"])

    def test_failed_close_nothing(self):
        spec, isa = self.build()
        self.finish(isa)
        os.remove(os.path.join(self.proj, "ok"))
        head = self.git("rev-parse", "HEAD").stdout
        rc, out = self.run_isa("close", isa)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(os.path.exists(self.plan_path(spec)))
        self.assertNotIn("phase: complete", self.read(isa))
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, head)
        # outside git: the close passes and commits nothing
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        self.env["ISA_MODE"] = "on"
        path = self.path_of(self.ok("new", "demo", "--tier", "E1", cwd=plain), "ISA")
        for s, t in (("Problem", "p\n"), ("Goal", "g\n"), ("Criteria", E1_CRITERIA), ("Test Strategy", E1_TESTS)):
            self.ok("write", path, s, stdin=t, cwd=plain)
        self.put("ok", "", base=plain)
        self.ok("verify", path, cwd=plain)
        self.ok("answer", path, "goal", "yes — ok", cwd=plain)
        self.ok("close", path, cwd=plain)
        self.assertFalse(os.path.exists(os.path.join(plain, ".git")))

    def test_dirty_before_new_left_out(self):
        self.put("a.txt", "user edit\n")
        spec, isa = self.build()
        self.put("lib.txt", "work\n")
        self.finish(isa)
        self.ok("close", isa)
        work = self.git("show", "--format=", "--name-only", "HEAD~1").stdout.split()
        self.assertNotIn("a.txt", work)
        self.assertIn("lib.txt", work)
        self.assertIn("a.txt", self.git("status", "--porcelain").stdout)


class Perimeter(Case):
    """S7: `isa` commands are the only writers."""

    COMMANDS = {"spec", "new", "write", "drop", "decide", "show", "lint", "ack", "reopen", "diff", "refine", "verify",
                "attest", "answer", "close", "ls", "status", "current", "where", "log", "purge-logs", "hook"}

    def test_commands_exist(self):
        from isa import cli
        self.assertEqual(set(cli.COMMANDS), self.COMMANDS)
        import re
        for doc in (os.path.join(ROOT, "runtime", "isa", "protocol.md"), os.path.join(ROOT, "skill", "ISA", "SKILL.md")):
            named = set(re.findall(r"`isa ([a-z][a-z-]*)", self.read(doc)))
            self.assertTrue(named, doc)
            self.assertLessEqual(named, self.COMMANDS, doc)

    def test_refuses_writes(self):
        self.on()
        isa = self.e1()
        spec = os.path.join(self.proj, "docs", "2026-10-07-x-01-spec.md")
        for tool, ti in (("Write", {"file_path": isa, "content": "x"}),
                         ("Edit", {"file_path": spec, "old_string": "a", "new_string": "b"}),
                         ("Bash", {"command": f"echo x > {isa}"}),
                         ("Bash", {"command": f"python3 -c \"open('{isa}', 'w')\""}),
                         ("Bash", {"command": f"sed -i s/a/b/ {spec}"}),
                         ("Bash", {"command": f"rm -rf {self.home}/_state"}),
                         ("Bash", {"command": f"cd {os.path.dirname(isa)} && python3 fix.py"})):
            r = self.deny(self.hook("PreToolUse", tool_name=tool, tool_input=ti)[1])
            self.assertIsNotNone(r, f"{tool} {ti}")
            self.assertIn("`isa ", r)
        for cmd in (f"cat {isa}", f"grep -n ISC {isa}", f"isa show {isa}"):
            self.assertIsNone(self.deny(self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd})[1]), cmd)

    def test_ack_needs_click(self):
        self.on()
        spec = self.spec()
        rc, out = self.run_isa("ack", spec)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("click", out)
        self.click("Spec ack", f"Acknowledge {os.path.relpath(spec, self.proj)}?")
        self.ok("write", spec, "Problem", stdin="Edited after the click.\n")
        rc, out = self.run_isa("ack", spec)
        self.assertNotEqual(rc, 0, out)


class State(Case):
    """S8: minimal state, and DEBUG free when off."""

    def files(self):
        out = []
        for d, _, names in os.walk(self.home):
            out += [os.path.relpath(os.path.join(d, n), self.home) for n in names]
        return sorted(out)

    def test_e2_lifecycle_files(self):
        spec, isa = self.build()
        self.finish(isa)
        self.ok("close", isa)
        key = os.path.basename(os.path.dirname(os.path.dirname(isa)))
        slug = os.path.basename(os.path.dirname(isa))
        self.assertEqual(self.files(), sorted([f"{key}/{slug}/ISA.md", f"{key}/acks.jsonl",
                                               f"_state/sessions/claude-{self.sid}.json"]))

    def test_debug_off(self):
        def run():
            self.prompt("refactor the parser and its tests", "p1")
            outs = [self.prompt("refactor the parser and its tests", "p2")[1],
                    self.hook("PreToolUse", tool_name="Write",
                              tool_input={"file_path": os.path.join(self.proj, "b.txt"), "content": "x"})[1]]
            return outs
        off = run()
        self.assertFalse(os.path.exists(os.path.join(self.home, "_state", "logs")))
        shutil.rmtree(self.home)
        self.env["ISA_DEBUG"] = "1"
        on = run()
        self.assertTrue(os.listdir(os.path.join(self.home, "_state", "logs")))
        self.assertEqual(off, on)


SPY_TESTS = ("- isc: ISC-1.1\n  anchors_to: S1\n  kind: behaviour\n  tool: touch probe-ran; test -f ok\n"
             "- isc: ISC-1.2\n  anchors_to: S1\n  kind: regression\n  tool: test ! -e bad\n  fails-when: \"bad exists\"\n")
CLOSED = "this ISA is closed; new work gets a new ISA"


class ReviewFixes(Case):
    """docs/2026-10-08-review-fixes-01-spec.md, S1–S8, through the hooks and the commands."""

    def failing(self, *args, stdin=None):
        rc, out = self.run_isa(*args, stdin=stdin)
        self.assertNotEqual(rc, 0, out)
        self.assertNotIn("Traceback", out)
        return out

    def session(self, change=None):
        path = os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")
        st = json.loads(self.read(path))
        if change:
            change(st)
            with open(path, "w") as f:
                json.dump(st, f)
        return st

    def closed_e2(self):
        spec, isa = self.build()
        self.finish(isa)
        self.ok("close", isa)
        return spec, isa

    def pre_commit_fails(self):
        hook = self.put(".git/hooks/pre-commit", "#!/bin/sh\necho 'blocked by hook' >&2\nexit 1\n")
        os.chmod(hook, 0o755)

    # S1
    def test_perimeter_home(self):
        self.env["HOME"] = os.path.join(self.tmp, "u")
        self.home = self.env["ISA_HOME"] = os.path.join(self.env["HOME"], ".isa")
        self.on()
        isa = self.e1()
        self.assertIsNone(self.change())  # BUILD
        key = os.path.basename(os.path.dirname(os.path.dirname(isa)))
        r = self.deny(self.hook("PreToolUse", tool_name="Bash", tool_input={"command": f"rm -rf $HOME/.isa/{key}"})[1])
        self.assertIsNotNone(r)
        self.assertIn("`isa ", r)

    # S2
    def test_verify_needs_ack(self):
        self.on()
        spec = self.spec()
        self.ack_spec(spec)
        isa = self.isa_from(spec, tests=SPY_TESTS)
        before = self.read(isa)
        for args in (("verify", "--red", isa), ("verify", isa)):
            out = self.failing(*args)
            self.assertIn("ISA ack", out)
            self.assertIn("--to Criteria", out)
        self.assertEqual(self.read(isa), before)
        self.assertFalse(os.path.exists(os.path.join(self.proj, "probe-ran")))

    def test_verify_spec_reopened(self):
        spec, isa = self.build()
        self.ok("reopen", spec)
        self.assertIn("Spec ack", self.failing("verify", isa))
        self.ok("write", spec, "Problem", stdin="The demo tool has no ok file yet.\n")
        self.ack_spec(spec)
        self.assertIn("isa refine", self.failing("verify", "--red", isa))

    def test_guarded_probe_write(self):
        self.on()
        isa = self.e1()
        before = self.read(isa)
        probe = f"rm -rf {self.home}/x"
        out = self.failing("write", isa, "ISC-1", "--probe", probe)
        self.assertIn(probe, out)
        self.assertEqual(self.read(isa), before)

    def test_guarded_probe_run(self):
        self.on()
        marker = os.path.join(self.home, "marker")
        tests = E1_TESTS.replace("tool: test -f ok", f"tool: echo x > {marker}; test -f ok")
        isa = self.e1(tests=tests)
        self.put("ok", "")
        self.assertIn(f"echo x > {marker}", self.failing("verify", isa))
        self.failing("close", isa)
        self.assertFalse(os.path.exists(marker))

    # S3
    def test_close_unbinds(self):
        self.closed_e2()
        del self.env["ISA_MODE"]
        self.fake_jev(0.95)
        self.prompt("now add a logo to the page", "p9")
        st = self.session()
        self.assertFalse(st.get("bound"))
        self.assertFalse(st.get("doc"))
        self.assertIn("TRIAGE", self.change())

    def test_finished_spec_not_open(self):
        spec, _ = self.closed_e2()
        del self.env["ISA_MODE"]
        self.session(lambda st: st.update(bound=None, doc=spec))
        self.fake_jev(0.95)
        _, out, _ = self.prompt("now add a logo to the page", "p9")
        self.assertIn("→ ON", out.get("systemMessage", ""))
        r = self.change()
        self.assertNotIn("isa new --spec", r or "")
        self.assertIn("TRIAGE", r)

    # S4
    def test_closed_isa_frozen(self):
        _, isa = self.closed_e2()
        before = self.read(isa)
        for args, stdin in ((("write", isa, "ISC-1.1", "changed"), None), (("write", isa, "Problem"), "changed\n"),
                            (("drop", isa, "ISC-1.1", "why"), None), (("decide", isa, "late"), None),
                            (("verify", isa), None), (("attest", isa, "ISC-1.1", "seen"), None),
                            (("answer", isa, "goal", "yes — again"), None), (("ack", isa), None),
                            (("refine", isa), None), (("close", isa), None)):
            self.assertIn(CLOSED, self.failing(*args, stdin=stdin), args)
        self.assertEqual(self.read(isa), before)

    def test_closed_isa_readable(self):
        _, isa = self.closed_e2()
        for args in (("show", isa), ("diff", isa), ("lint", isa)):
            self.ok(*args)

    # S5
    def ask(self, header, question, answers):
        ti = {"questions": [{"question": question, "header": header, "multiSelect": False,
                             "options": [{"label": "Acknowledge", "description": "a"},
                                         {"label": "Request changes", "description": "b"}]}]}
        if answers:
            ti["answers"] = answers
        return self.deny(self.hook("PreToolUse", tool_name="AskUserQuestion", tool_input=ti)[1])

    def test_prefilled_answer_denied(self):
        self.on()
        spec = self.spec()
        q = f"Acknowledge {os.path.relpath(spec, self.proj)}?"
        r = self.ask("Spec ack", q, {q: "Acknowledge"})
        self.assertIsNotNone(r)
        self.assertIn("user", r)
        gate = "ISA is not enabled for this prompt (Jev: 0.50). Continue?"
        self.assertIsNotNone(self.ask("ISA gate", gate, {gate: "Continue without ISA"}))
        self.assertIsNone(self.ask("Spec ack", q, None))
        rc, out = self.run_isa("ack", spec)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("click", out)

    def test_ack_click_at_post(self):
        self.on()
        spec = self.spec()
        self.click("Spec ack", f"Acknowledge {os.path.relpath(spec, self.proj)}?")
        self.ok("ack", spec)

    # S6
    def test_close_commit_failure(self):
        spec, isa = self.build()
        self.pre_commit_fails()
        self.put("lib.txt", "work\n")
        self.finish(isa)
        out = self.ok("close", isa)
        self.assertIn("Not committed: the work — blocked by hook", out)
        self.assertIn("Not committed: the plan — blocked by hook", out)
        self.assertIn("phase: complete", self.read(isa))

    def test_ack_commit_failure(self):
        self.on()
        spec = self.spec()
        self.pre_commit_fails()
        out = self.ack_spec(spec)
        self.assertIn("Not committed: the spec — blocked by hook", out)
        self.assertRegex(self.read(spec), r"(?m)^status: \"?acked ")

    def test_close_nothing_to_commit(self):
        self.on()
        self.put("ok", "")
        self.git("add", "-A")
        self.git("commit", "-qm", "ok")
        isa = self.e1()
        self.ok("verify", isa)
        self.ok("answer", isa, "goal", "yes — ok")
        self.assertNotIn("Not committed", self.ok("close", isa))

    # S7
    def test_rename_committed(self):
        spec, isa = self.build()
        self.git("mv", "a.txt", "b.txt")
        self.finish(isa)
        self.ok("close", isa)
        work = self.git("show", "--format=", "--name-status", "--no-renames", "HEAD~1").stdout
        self.assertRegex(work, r"(?m)^D\ta\.txt$")
        self.assertRegex(work, r"(?m)^A\tb\.txt$")
        self.assertEqual(self.git("status", "--porcelain").stdout, "")

    # S8
    def test_verify_timeout_value(self):
        self.on()
        isa = self.e1()
        out = self.failing("verify", isa, "--timeout", "abc")
        self.assertIn("--timeout takes whole seconds", out)


if __name__ == "__main__":
    unittest.main()
