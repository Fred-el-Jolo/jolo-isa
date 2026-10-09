"""Spec-derived criteria (docs/2026-10-09-spec-derived-criteria-01-spec.md), S1–S5, end to end through the hooks
and the `isa` commands. Jev is always a fake that logs every request; no test calls the real one.

Run: python3 -m unittest tests.test_derivation
"""
import json
import os
import re
import sys
import unittest

from tests.test_foundations import Case, E1_CRITERIA, E1_TESTS, ROOT, SPEC_BODY, _isa_text

sys.path.insert(0, os.path.join(ROOT, "runtime"))

FAKE_JEV = r'''#!/usr/bin/env python3
import json, os, sys
mode = sys.argv[1] if len(sys.argv) > 1 else ""
raw = sys.stdin.read()
data = json.loads(raw or "{}")
qs = (data.get("questions") or {}) if mode == "ask" else {"answer": {}}
state = json.dumps(data.get("state") if mode == "ask" else data)
longest = max([len(json.dumps(q)) for q in qs.values()] or [0])
log = os.environ.get("FAKE_JEV_LOG")
if log:
    with open(log, "a") as f:
        f.write(json.dumps({"mode": mode, "questions": len(qs), "state_chars": len(state),
                            "longest_chars": longest, "all_chars": len(json.dumps(qs)), "ids": sorted(qs)}) + "\n")
p = float(os.environ.get("FAKE_JEV_P", "0.9"))
over = json.loads(os.environ.get("FAKE_JEV_MAP") or "{}")
def ans(q):
    return next((v for k, v in over.items() if q.startswith(k)), p)
print(json.dumps({"ok": True, "answers": {q: {"answer": ans(q)} for q in qs}}))
'''

CHECK = "shared: none\nprerequisites: none\ncontradictions: none\ndrift: none\ngaps: none\ncontext: none\n"
LINES = ["- `ok` exists", "- `ok` is empty", "- `ok` is a plain file"]


def body(sections):
    """SPEC_BODY with its S1 replaced by `sections`: {title: [accepted-when lines]}."""
    out = {k: v for k, v in SPEC_BODY.items() if not k.startswith("S1")}
    for n, (title, lines) in enumerate(sections.items(), 1):
        out[f"S{n} — {title}"] = f"The part {title.lower()}.\nAccepted when:\n" + "\n".join(lines)
    return out


class Base(Case):
    def fake(self, p=0.9, mapping=None):
        exe = self.put("fake-jev", FAKE_JEV, base=self.tmp)
        os.chmod(exe, 0o755)
        self.log = os.path.join(self.tmp, "jev.log")
        self.env.update(ISA_JEV_BIN=exe, FAKE_JEV_P=str(p), FAKE_JEV_MAP=json.dumps(mapping or {}),
                        FAKE_JEV_LOG=self.log)

    def calls(self):
        if not os.path.exists(getattr(self, "log", "")):
            return []
        return [json.loads(ln) for ln in self.read(self.log).splitlines() if ln.strip()]

    def config(self, **kw):
        self.put("config.json", json.dumps(kw), base=self.home)

    def seeded(self, sections=None):
        """ON, a spec (one section by default) acked, its ISA seeded: → (spec, ISA)."""
        self.on()
        spec = self.spec(body=body(sections) if sections else None)
        self.ack_spec(spec)
        isa = self.path_of(self.ok("new", "--spec", spec), "ISA")
        for section in ("Vision", "Principles"):
            self.isa("write", isa, section, stdin=f"The {section.lower()} of the demo.\n")
        return spec, isa

    def leaf(self, isa, isc, text, probe="test -f ok", kind="behaviour", fails=None, *extra):
        args = ["write", isa, isc, text, "--probe", probe, "--kind", kind] + (["--fails-when", fails] if fails else [])
        rc, out = self.isa(*args, *extra)
        self.assertEqual(rc, 0, out)
        return out

    def ready(self):
        """An E2 ISA that lints: S1 seeded, a behaviour leaf and an Anti under it."""
        spec, isa = self.seeded()
        self.leaf(isa, "ISC-1.1", "The file ok exists.")
        self.leaf(isa, "ISC-1.2", "Anti: the file bad exists.", "test ! -e bad", "regression", "bad exists")
        self.assertEqual(self.isa("lint", isa)[0], 0, self.isa("lint", isa)[1])
        return spec, isa

    def review(self, isa, check=CHECK):
        return self.run_isa("review", isa, stdin=check)

    def ack_question(self):
        ti = {"questions": [{"question": "Acknowledge the ISA of this task?", "header": "ISA ack", "multiSelect": False,
                             "options": [{"label": "Acknowledge", "description": "a"},
                                         {"label": "Request changes", "description": "b"}]}]}
        return self.deny(self.hook("PreToolUse", tool_name="AskUserQuestion", tool_input=ti)[1])

    def flags(self, isa):
        return re.findall(r"(?m)^- (R\d+): ", self.read(isa))

    def lint_text(self, text):
        return self.isa("lint", self.put("x/ISA.md", text, base=self.home))

    def spec3(self):
        from isa import spec as specmod
        text = specmod.template("Demo", "E2")
        for k, v in body({"One": LINES[:1], "Two": LINES[1:2], "Three": LINES[2:]}).items():
            if k != "Approaches":
                text = specmod.set_section(text, k, v)
        text = text.replace("status: draft", f"status: acked 2026-10-09 #{specmod.ack_hash(text)}")
        return self.put("docs/2026-10-09-demo-01-spec.md", text)

    def tree(self, extra_c="", extra_t=""):
        """Criteria and Test Strategy covering S1–S3 of spec3, plus `extra_c` / `extra_t`."""
        c = ("- [ ] ISC-1: One.\n  - [ ] ISC-1.1: ok exists.\n- [ ] ISC-2: Two.\n  - [ ] ISC-2.1: ok is empty.\n"
             "- [ ] ISC-3: Three.\n  - [ ] ISC-3.1: Anti: ok is a directory.\n") + extra_c
        t = ("- isc: ISC-1.1\n  anchors_to: S1\n  kind: behaviour\n  tool: test -f ok\n"
             "- isc: ISC-2.1\n  anchors_to: S2\n  kind: behaviour\n  tool: test ! -s ok\n"
             "- isc: ISC-3.1\n  anchors_to: S3\n  kind: regression\n  tool: test ! -d ok\n  fails-when: \"dir\"\n") + extra_t
        return c, t


class Common(Base):
    """ISC-0: the shared states."""

    def test_review_section(self):
        self.fake(0.9)
        _, isa = self.ready()
        self.assertEqual(self.review(isa)[0], 0)
        from isa import isafile
        r = isafile.parse(self.read(isa))["review"]
        self.assertEqual(sorted(r["checklist"]), sorted(["shared", "prerequisites", "contradictions", "drift", "gaps",
                                                         "context"]))
        self.assertRegex(r["hash"], r"^[0-9a-f]{8}$")
        rc, out = self.run_isa("write", isa, "Review", stdin="hand-written\n")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("isa review", out)

    def test_origin_fields_roundtrip(self):
        _, isa = self.seeded({"One": LINES[:1], "Two": LINES[1:2], "Three": LINES[2:]})
        self.ok("write", isa, "ISC-0", "Common ground.", "--before", "ISC-1")
        self.leaf(isa, "ISC-0.1", "The ok helper exists.", "true", "regression", "x", "--serves", "S2+S3",
                  "--why", "both read it")
        self.leaf(isa, "ISC-1.1", "ok exists.", "test -f ok", "behaviour", None, "--source", "context",
                  "--why", "from the codebase")
        self.leaf(isa, "ISC-1.2", "ok is fresh.")
        self.ok("drop", isa, "ISC-1.2", "not needed")
        self.ok("write", isa, "ISC-1.1", "--probe", "test -e ok")
        from isa import isafile
        p = isafile.parse(self.read(isa))
        self.assertEqual(isafile.entry(p, "0.1").get("serves"), "S2+S3")
        self.assertEqual(isafile.entry(p, "0.1").get("why"), "both read it")
        self.assertEqual(isafile.entry(p, "1.1").get("source"), "context")
        self.assertEqual(isafile.entry(p, "1.1").get("why"), "from the codebase")

    def test_jev_adhoc_one_request(self):
        self.fake(0.4)
        keep = {k: os.environ.get(k) for k in ("ISA_HOME", "ISA_JEV_BIN", "FAKE_JEV_P", "FAKE_JEV_LOG", "FAKE_JEV_MAP")}
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in keep.items()])
        for k in keep:
            os.environ[k] = self.env[k] if k != "ISA_HOME" else self.home
        from isa import jev
        qs = {f"q{n}": {"type": "noul", "instructions": f"question {n}?"} for n in range(5)}
        r = jev.ask_adhoc({"spec": "s", "criteria": []}, qs, 3.0)
        self.assertTrue(r["served"], r)
        self.assertEqual(sorted(r["answers"]), sorted(qs))
        self.assertEqual([(c["mode"], c["questions"]) for c in self.calls()], [("ask", 5)])


class Seed(Base):
    """S1: `isa new --spec` writes one parent per section."""

    def test_parents_only(self):
        _, isa = self.seeded({"One": LINES, "Two": LINES[:2]})
        from isa import isafile
        p = isafile.parse(self.read(isa))
        self.assertEqual(p["sections"]["Criteria"].strip(), "- [ ] ISC-1: One\n- [ ] ISC-2: Two")
        self.assertEqual(p["tests"], [])

    def test_empty_parent_listed(self):
        _, isa = self.seeded({"One": LINES, "Two": LINES[:2]})
        out = self.isa("lint", isa)[1]
        self.assertIn("ISC-1 (S1): no criterion yet", out)
        self.assertIn("ISC-2 (S2): no criterion yet", out)

    def test_block_write_refused(self):
        _, isa = self.seeded()
        rc, out = self.run_isa("write", isa, "Criteria", stdin="- [ ] ISC-1: x\n  - [ ] ISC-1.1: y\n")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("written once", out)

    def test_leaf_inherits_anchor(self):
        _, isa = self.seeded()
        self.ok("write", isa, "ISC-1.1", "The file ok exists.")
        from isa import isafile
        e = isafile.entry(isafile.parse(self.read(isa)), "1.1")
        self.assertEqual((e or {}).get("anchors_to"), "S1")
        self.assertFalse((e or {}).get("tool"))
        self.assertIn("ISC-1.1 has no `tool`", self.isa("lint", isa)[1])

    def test_e1_unchanged(self):
        self.on()
        isa = self.path_of(self.ok("new", "demo", "--tier", "E1"), "ISA")
        from isa import doc
        fm, _, rest = doc.split(self.read(isa))
        self.assertEqual(list(fm), ["task", "slug", "effort", "phase", "progress", "started", "updated", "root",
                                    "base_dirty"])
        self.assertEqual(rest, "\n## Problem\n\n## Goal\n\n## Criteria\n\n## Test Strategy\n\n")


class Origins(Base):
    """S2: where a leaf sits says where it came from."""

    def errors(self, extra_c="", extra_t="", swap=None):
        c, t = self.tree(extra_c, extra_t)
        if swap:
            t = t.replace(*swap)
        return self.lint_text(_isa_text("E2", c, t, spec=self.spec3()))[1]

    def test_wrong_section_anchor(self):
        self.assertNotIn("sits under", self.errors())
        self.assertIn("ISC-2.1 sits under ISC-2 (S2)", self.errors(swap=("anchors_to: S2", "anchors_to: S1")))

    def test_common_ground_rules(self):
        c = "- [ ] ISC-0: Common ground.\n  - [ ] ISC-0.1: a.\n  - [ ] ISC-0.2: b.\n  - [ ] ISC-0.3: c.\n"
        t = ("- isc: ISC-0.1\n  kind: regression\n  tool: \"true\"\n  fails-when: x\n  serves: S2\n  why: w\n"
             "- isc: ISC-0.2\n  kind: regression\n  tool: \"true\"\n  fails-when: x\n  serves: S1+S2\n"
             "- isc: ISC-0.3\n  kind: regression\n  tool: \"true\"\n  fails-when: x\n  serves: S1+S3\n  why: w\n")
        out = self.errors(c, t)
        self.assertIn("ISC-0.1: `serves:` names two or more sections", out)
        self.assertIn("ISC-0.2: `serves:` needs a `why:`", out)
        self.assertNotIn("ISC-0.3", out)
        self.assertIn("ISC-0.4: `serves:` names two or more sections", self.errors(
            "- [ ] ISC-0: Common ground.\n  - [ ] ISC-0.4: d.\n",
            "- isc: ISC-0.4\n  anchors_to: S1\n  kind: regression\n  tool: \"true\"\n  fails-when: x\n"))

    def test_top_level_leaf(self):
        c = "- [ ] ISC-4: A plain claim.\n- [ ] ISC-5: Anti: a broken build.\n- [ ] ISC-6: The helper exists.\n"
        t = ("- isc: ISC-4\n  anchors_to: Goal\n  kind: behaviour\n  tool: \"true\"\n"
             "- isc: ISC-5\n  anchors_to: Constraints\n  kind: regression\n  tool: \"true\"\n  fails-when: x\n"
             "- isc: ISC-6\n  anchors_to: Goal\n  kind: behaviour\n  tool: \"true\"\n  source: context\n  why: w\n")
        out = self.errors(c, t)
        self.assertIn("ISC-4 is outside the spec's sections", out)
        self.assertNotIn("ISC-5", out)
        self.assertNotIn("ISC-6", out)

    def test_context_needs_why(self):
        out = self.errors(swap=("  tool: test -f ok\n", "  tool: test -f ok\n  source: context\n"))
        self.assertIn("ISC-1.1: `source: context` needs a `why:`", out)

    def prereqs(self):
        _, isa = self.seeded({"One": LINES[:1], "Two": LINES[1:]})
        self.leaf(isa, "ISC-1.1", "ok exists.")
        self.leaf(isa, "ISC-2.1", "ok is empty.")
        return isa

    def order(self, isa):
        from isa import isafile
        return isafile.parse(self.read(isa))["order"]

    def test_before_first(self):
        isa = self.prereqs()
        self.ok("write", isa, "ISC-2.4", "The fixture exists.", "--before", "ISC-2.1")
        self.assertEqual(self.order(isa), ["1", "1.1", "2", "2.4", "2.1"])

    def test_before_keeps_order(self):
        isa = self.prereqs()
        self.ok("write", isa, "ISC-2.4", "The fixture exists.", "--before", "ISC-2.1")
        self.ok("write", isa, "ISC-2.5", "The fixture is filled.", "--before", "ISC-2.1")
        self.assertEqual(self.order(isa), ["1", "1.1", "2", "2.4", "2.5", "2.1"])

    def test_before_refusals(self):
        isa = self.prereqs()
        before = self.read(isa)
        rc, out = self.run_isa("write", isa, "ISC-2.6", "x.", "--before", "ISC-1.1")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("sibling", out)
        rc, out = self.run_isa("write", isa, "ISC-2.1", "y.", "--before", "ISC-1.1")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("exists", out)
        self.assertEqual(self.read(isa), before)

    def test_e1_lint_unchanged(self):
        ok = _isa_text("E1", E1_CRITERIA, E1_TESTS)
        self.assertEqual(self.lint_text(ok)[0], 0)
        ctx = _isa_text("E1", E1_CRITERIA + "- [ ] ISC-3: Plain.\n", E1_TESTS +
                        "- isc: ISC-3\n  kind: behaviour\n  tool: \"true\"\n  source: context\n")
        self.assertEqual(self.lint_text(ctx)[0], 0, self.lint_text(ctx)[1])
        rc, out = self.lint_text(_isa_text("E1", "- [ ] ISC-1: The file ok exists.\n",
                                           "- isc: ISC-1\n  kind: behaviour\n  tool: test -f ok\n"))
        self.assertEqual([ln.strip() for ln in out.splitlines()[1:]],
                         ["ERROR: no `Anti:` criterion (at least one, at every tier)"])


class Review(Base):
    """S3: `isa review` records the model's whole-file review."""

    def test_checklist_required(self):
        _, isa = self.ready()
        rc, out = self.review(isa, "shared: none\nprerequisites: none\ncontradictions: none\ncontext: none\n")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("drift:", out)
        self.assertIn("gaps:", out)
        self.assertNotIn("## Review", self.read(isa))
        e1 = self.e1()
        rc, out = self.review(e1)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("E1", out)

    def test_contradiction_needs_reopen(self):
        _, isa = self.ready()
        rc, out = self.review(isa, CHECK.replace("contradictions: none", "contradictions: S1 wants ok empty, S2 not"))
        self.assertNotEqual(rc, 0, out)
        self.assertIn("isa reopen", out)

    def test_review_written(self):
        self.fake(0.1)
        _, isa = self.ready()
        self.assertEqual(self.review(isa, CHECK.replace("gaps: none", "gaps: nothing checks the file size"))[0], 0)
        text = self.read(isa)
        self.assertIn("## Review", text)
        self.assertIn("gaps: nothing checks the file size", text)
        self.assertTrue(self.flags(isa))
        self.assertRegex(text, r"(?m)^reviewed: \"?[0-9a-f]{8}\"?$")

    def test_ack_question_needs_review(self):
        _, isa = self.ready()
        r = self.ack_question()
        self.assertIsNotNone(r)
        self.assertIn("isa review", r)
        rc, out = self.run_isa("ack", isa)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("isa review", out)

    def test_ack_needs_answers(self):
        self.fake(0.1)
        _, isa = self.ready()
        self.review(isa)
        flags = self.flags(isa)
        self.assertTrue(flags)
        self.assertIn("isa review", self.ack_question() or "")
        for f in flags:
            self.ok("review", isa, "--answer", f, "rebuttal: the probe proves it")
        self.click("ISA ack", "Acknowledge the ISA of this task?")
        self.ok("ack", isa)

    def test_change_needs_new_review(self):
        self.fake(0.9)
        _, isa = self.ready()
        self.review(isa)
        self.assertIsNone(self.ack_question())
        self.ok("write", isa, "ISC-1.1", "The file ok exists in the project.")
        self.assertIn("changed since its review", self.change())
        self.assertIn("isa review", self.ack_question() or "")

    def test_answer_rules(self):
        self.fake(0.1)
        _, isa = self.ready()
        self.review(isa)
        f = self.flags(isa)[0]
        for bad in ("maybe it is fine", "reopen: the spec is wrong"):
            rc, out = self.run_isa("review", isa, "--answer", f, bad)
            self.assertNotEqual(rc, 0, out)
        self.ok("review", isa, "--answer", f, "rebuttal: the probe runs the real binary")
        self.assertIn("rebuttal: the probe runs the real binary", self.read(isa))

    def test_plan_has_review(self):
        self.fake(0.9)
        spec, isa = self.ready()
        self.ok("decide", isa, "touch was enough")
        self.review(isa)
        self.click("ISA ack", "Acknowledge the ISA of this task?")
        self.ok("ack", isa)
        self.finish(isa)
        self.ok("close", isa)
        plan = self.read(spec.replace("-01-spec.md", "-02-plan.md"))
        heads = [ln[3:] for ln in plan.splitlines() if ln.startswith("## ")]
        self.assertIn("Review", heads)
        self.assertEqual(heads.index("Review"), heads.index("Decisions") + 1)


class JevCheck(Base):
    """S4: Jev's check in one request, with its own thresholds."""

    def wide(self, sizes, line=None):
        """A seeded ISA over len(sizes) sections, sizes[k] leaves under section k+1, one of them an Anti."""
        sections = {f"Part {n}": [line or f"- part {n} works"] for n in range(1, len(sizes) + 1)}
        _, isa = self.seeded(sections)
        for k, n in enumerate(sizes, 1):
            for j in range(1, n + 1):
                if (k, j) == (1, 1):
                    self.leaf(isa, "ISC-1.1", "Anti: the build breaks.", "true", "regression", "it breaks")
                else:
                    self.leaf(isa, f"ISC-{k}.{j}", f"Part {k} check {j} holds.", "true", "regression", "x")
        self.assertEqual(self.isa("lint", isa)[0], 0, self.isa("lint", isa)[1])
        return isa

    def test_one_request(self):
        self.fake(0.9)
        isa = self.wide([4, 4, 4, 3, 3, 3, 3, 3])
        self.assertEqual(self.review(isa)[0], 0)
        self.assertEqual([(c["mode"], c["questions"]) for c in self.calls()], [("ask", 35)])

    def test_defaults(self):
        os.environ["ISA_HOME"] = self.home
        self.addCleanup(os.environ.pop, "ISA_HOME", None)
        from isa import config
        self.assertEqual(config.number("jev_serves"), 0.7)
        self.assertEqual(config.number("jev_covered"), 0.7)
        self.assertEqual((config.number("jev_gate"), config.number("jev_quiet"), config.number("jev_doubt")),
                         (0.8, 0.3, 0.5))

    def test_thresholds_independent(self):
        self.config(jev_serves=0.9)
        self.fake(0.2)
        _, isa = self.ready()
        self.review(isa)
        text = self.read(isa)
        self.assertRegex(text, r"(?m)^- R\d+: covered S1 ")
        self.assertNotRegex(text, r"(?m)^- R\d+: serves ")

    def test_budget_split(self):
        self.fake(0.9)
        isa = self.wide([1, 1, 1, 1, 1, 1], line="- " + "word " * 12000)
        self.assertEqual(self.review(isa)[0], 0)
        calls = self.calls()
        self.assertEqual(len(calls), 3, calls)
        for c in calls:
            self.assertLessEqual(c["state_chars"] + c["longest_chars"], 32000 * 4)
            self.assertLessEqual(c["state_chars"] + c["all_chars"], 64000 * 4)

    def test_flag_fields(self):
        self.fake(0.1)
        _, isa = self.ready()
        self.review(isa)
        line = next(ln for ln in self.read(isa).splitlines() if re.match(r"- R\d+: serves ISC-1\.1 ", ln))
        self.assertIn("no 0.90", line)
        self.assertIn("0.70", line)
        self.assertIn("Problem", line)  # the question itself
        self.assertIn("answer: (open)", line)

    def test_unavailable(self):
        _, isa = self.ready()
        self.assertEqual(self.review(isa)[0], 0)
        self.assertIn("Jev: unavailable — model only", self.read(isa))

    def test_no_jev_in_lint_or_hooks(self):
        self.fake(0.9)
        _, isa = self.ready()
        self.isa("lint", isa)
        self.hook("SessionStart", source="startup")
        self.prompt("go on with the demo", "p2")
        self.change()
        self.ack_question()
        self.hook("PostToolUse", tool_name="Bash", tool_input={"command": "ls"}, tool_response={"stdout": ""})
        self.hook("Stop")
        self.assertEqual(self.calls(), [])


class Trace(Base):
    """S5: the trace at the ISA ack."""

    def traced(self):
        _, isa = self.seeded({"One": LINES[:1], "Two": LINES[1:2], "Three": LINES[2:]})
        self.ok("write", isa, "ISC-0", "Common ground.", "--before", "ISC-1")
        self.leaf(isa, "ISC-0.1", "The ok helper exists.", "test -x helper", "regression", "no helper",
                  "--serves", "S2+S3", "--why", "both read it")
        self.leaf(isa, "ISC-1.1", "ok exists.", "test -f ok")
        self.leaf(isa, "ISC-2.1", "ok is empty.", "test ! -s ok", "behaviour", None, "--source", "context",
                  "--why", "the codebase expects it")
        self.leaf(isa, "ISC-3.1", "ok is a plain file.", "test ! -d ok")
        self.leaf(isa, "ISC-4", "Anti: a bad file exists.", "test ! -e bad", "regression", "bad exists",
                  "--anchors", "Goal")
        self.assertEqual(self.isa("lint", isa)[0], 0, self.isa("lint", isa)[1])
        return isa

    def test_blocks_in_order(self):
        self.fake(0.9)
        isa = self.traced()
        self.review(isa)
        out = self.ok("show", isa, "--trace")
        marks = ["Common ground", "S1 — One", "S2 — Two", "S3 — Three", "Antis and context", "Review", "sections covered"]
        at = [out.find(m) for m in marks]
        self.assertNotIn(-1, at, out)
        self.assertEqual(at, sorted(at), out)
        for probe in ("test -x helper", "test -f ok", "test ! -s ok", "test ! -d ok", "test ! -e bad"):
            self.assertIn(probe, out)
        self.assertIn("serves S2+S3", out)
        self.assertIn("the codebase expects it", out)

    def footer(self, isa):
        return self.ok("show", isa, "--trace").rstrip().splitlines()[-1]

    def test_footer(self):
        isa = self.traced()
        self.assertEqual(self.footer(isa), "3/3 sections covered · 1 common · 1 context · review: missing")
        self.review(isa)
        self.assertEqual(self.footer(isa), "3/3 sections covered · 1 common · 1 context · review: model only")
        self.fake(0.9)
        self.review(isa)
        self.assertEqual(self.footer(isa), "3/3 sections covered · 1 common · 1 context · review ✓ (Jev)")

    def test_ack_names_trace(self):
        self.fake(0.9)
        _, isa = self.ready()
        self.review(isa)
        self.assertIn(f"isa show", self.change())
        self.assertIn("--trace", self.change())
        for doc in (os.path.join(ROOT, "runtime", "isa", "protocol.md"), os.path.join(ROOT, "skill", "ISA", "SKILL.md")):
            self.assertIn("isa show <ISA> --trace", self.read(doc), doc)

    def test_docs_and_help(self):
        refs = os.path.join(ROOT, "skill", "ISA", "References")
        for doc in (os.path.join(refs, "Foundations.md"), os.path.join(refs, "SpecDriven.md"),
                    os.path.join(ROOT, "skill", "ISA", "SKILL.md")):
            text = self.read(doc)
            for word in ("isa review", "--trace", "ISC-0", "source: context"):
                self.assertIn(word, text, f"{doc}: {word}")
        self.assertRegex(self.read(os.path.join(refs, "Foundations.md")), r"(?m)^\|.*`isa review")
        self.assertIn("isa review", self.isa("--help")[1])


if __name__ == "__main__":
    unittest.main()
