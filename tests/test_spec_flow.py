"""Plan P7 (spec 2026-10-06 § B.4, § B.7, § 5.6, § 8 items 8 and 15): a written spec or plan binds to the
session, the ack question is refused until the document lints clean at "ack", only an answer of exactly
`Acknowledge` is recorded, and no `status: acked … #h` line is written without a matching record.

Real git repos, a fake `jev`. Run: python3 -m unittest tests.test_spec_flow
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from tests.test_hooks import ISA, ROOT, calls, setup_fake
from tests.test_project_isa import GitCase
from tests.test_specdoc import E3, E4, PLAN

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import specdoc  # noqa: E402

SPEC = "docs/spec/2026-10-06-help.md"
E4_SPEC = "docs/spec/2026-10-06-api-migration.md"
PLAN_DOC = "docs/plan/2026-10-06-api-migration.md"
OPTIONS = [{"label": "Acknowledge", "description": "the spec says what I want"},
           {"label": "Request changes", "description": "not yet"}]


def today():
    return time.strftime("%Y-%m-%d")


class SpecCase(GitCase):
    def doc(self, rel, text, root=None):
        p = os.path.join(root or self.proj, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        return p

    def write_doc(self, rel, text, root=None):
        p = self.doc(rel, text, root)
        self.hook("PostToolUse", cwd=root or self.proj, tool_name="Write", tool_input={"file_path": p, "content": text},
                  tool_response={"type": "create"})
        return p

    def st(self):
        return self.session()

    def question(self, rel, header="Spec ack", options=None, **extra):
        q = {"question": f"Acknowledge {rel}?", "header": header, "multiSelect": False,
             "options": OPTIONS if options is None else options}
        q.update(extra)
        return {"questions": [q]}

    def pre_ask(self, ti, cwd=None):
        return self.hook("PreToolUse", cwd=cwd or self.proj, tool_name="AskUserQuestion", tool_input=ti)[1]

    def answer(self, rel, answer, header="Spec ack", cwd=None, via="input"):
        ti = self.question(rel, header)
        if via == "input":
            ti["answers"] = {f"Acknowledge {rel}?": answer}
            resp = {}
        else:
            resp = f'User has answered your questions: "Acknowledge {rel}?"="{answer}". You can now continue.'
        return self.hook("PostToolUse", cwd=cwd or self.proj, tool_name="AskUserQuestion", tool_input=ti,
                         tool_response=resp)[1]

    def acks(self):
        try:
            with open(os.path.join(self.home, "_state", "acks.jsonl")) as f:
                return [json.loads(line) for line in f if line.strip()]
        except OSError:
            return []


class Binding(SpecCase):
    def test_spec_write_binds(self):
        p = self.write_doc(SPEC, E3)
        self.assertEqual(self.st().get("doc"), {"path": os.path.realpath(p), "kind": "spec", "pid": self.pid})

    def test_plan_binds_and_rebinds(self):
        self.doc(E4_SPEC, E4)
        plan = self.write_doc(PLAN_DOC, PLAN)
        self.assertEqual(self.st().get("doc"), {"path": os.path.realpath(plan), "kind": "plan", "pid": self.pid})
        spec = self.write_doc(SPEC, E3)
        self.assertEqual(self.st().get("doc"), {"path": os.path.realpath(spec), "kind": "spec", "pid": self.pid})

    def test_isa_binding_kept(self):
        isa = self.task()
        before = self.st()["bound"]
        self.assertEqual(before, os.path.realpath(isa))
        self.write_doc(SPEC, E3)
        st = self.st()
        self.assertEqual(st["bound"], before)
        self.assertEqual(st["doc"]["kind"], "spec")

    def test_q2_against_doc(self):
        setup_fake(self, isa_continuation=0.91)
        p = self.write_doc(SPEC, E3)  # a project write: the session is ON, nothing bound but the spec
        self.assertEqual(self.st().get("mode"), "on")
        rc, out, err = self.hook("UserPromptSubmit", prompt="now add a man page generator to the release script")
        self.assertEqual(rc, 0, err)
        rows = calls(self, "isa-continuation")
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("Help screen redesign", rows[0]["stdin"])
        q2 = self.st()["q2"]
        self.assertEqual((q2["doc"], q2["outcome"]), (os.path.realpath(p), "new"))
        self.assertNotIn("old", q2)
        self.assertIn("new task", json.dumps(out))


class AckQuestion(SpecCase):
    def test_spec_lint_refuses(self):
        self.doc(SPEC, E3.replace("Said:\n", ""))
        out = self.pre_ask(self.question(SPEC))
        self.assertEqual(self.decision(out), "deny", out)
        self.assertIn("Said", self.reason(out))

    def test_plan_lint_refuses(self):
        self.doc(E4_SPEC, E4)
        self.doc(PLAN_DOC, PLAN.replace("headers → P3", "headers"))
        out = self.pre_ask(self.question(PLAN_DOC, "Plan ack"))
        self.assertEqual(self.decision(out), "deny", out)
        self.assertIn("Review focus", self.reason(out))

    def test_shape_refused(self):
        self.doc(SPEC, E3)
        self.doc(E4_SPEC, E4)
        self.doc(PLAN_DOC, PLAN)
        bad = [
            self.question(SPEC, options=[{"label": "Yes", "description": ""}, {"label": "No", "description": ""}]),
            self.question(SPEC, options=OPTIONS + [{"label": "Later", "description": ""}]),
            self.question(SPEC, multiSelect=True),
            dict(self.question(SPEC), answers={f"Acknowledge {SPEC}?": "Acknowledge"}),
            self.question(PLAN_DOC, "Spec ack"),  # header and document kind disagree
            self.question("docs/spec/2026-10-06-missing.md"),
        ]
        for ti in bad:
            out = self.pre_ask(ti)
            self.assertEqual(self.decision(out), "deny", ti)

    def test_clean_passes(self):
        self.doc(SPEC, E3)
        out = self.pre_ask(self.question(SPEC))
        self.assertNotEqual(self.decision(out), "deny", out)
        self.doc(E4_SPEC, E4)
        self.doc(PLAN_DOC, PLAN)
        out = self.pre_ask(self.question(PLAN_DOC, "Plan ack"))
        self.assertNotEqual(self.decision(out), "deny", out)


class AckRecord(SpecCase):
    def test_acknowledge_records(self):
        p = self.doc(SPEC, E3)
        self.answer(SPEC, "Acknowledge")
        rows = self.acks()
        self.assertEqual(len(rows), 1, rows)
        r = rows[0]
        self.assertEqual((r["path"], r["hash"], r["harness"], r["session"]),
                         (os.path.realpath(p), specdoc.ack_hash(E3), "claude", self.sid))
        self.assertIsInstance(r["t"], (int, float))
        self.answer(SPEC, "Acknowledge", via="output")  # the answer as Claude Code prints it
        self.assertEqual(len(self.acks()), 2)

    def test_only_exact_label(self):
        self.doc(SPEC, E3)
        for a in ("Request changes", "ack", "Acknowledge (Recommended)", "acknowledge", "Acknowledge, but fix S2"):
            self.answer(SPEC, a)
            self.answer(SPEC, a, via="output")
        self.assertEqual(self.acks(), [])

    def test_spec_ack_instructions(self):
        self.doc(SPEC, E3)
        ctx = self.ctx(self.answer(SPEC, "Acknowledge"))
        h = specdoc.ack_hash(E3)
        self.assertIn(f"status: acked {today()} #{h}", ctx)
        self.assertIn(f"add -- {SPEC}", ctx)
        self.assertIn(f'commit -m "Spec: Help screen redesign (acked)" -- {SPEC}', ctx)

    def test_plan_ack_instructions(self):
        self.doc(E4_SPEC, E4)
        self.doc(PLAN_DOC, PLAN)
        ctx = self.ctx(self.answer(PLAN_DOC, "Acknowledge", header="Plan ack"))
        self.assertIn(f"status: acked {today()} #{specdoc.ack_hash(PLAN)}", ctx)
        self.assertIn(f'commit -m "Plan: REST to GraphQL migration (acked)" -- {PLAN_DOC}', ctx)

    def test_no_commit_outside_git(self):
        plain = tempfile.mkdtemp(prefix="isa-p7-plain-", dir=os.path.expanduser("~/.cache"))
        self.addCleanup(shutil.rmtree, plain, True)
        self.doc(SPEC, E3, root=plain)
        ctx = self.ctx(self.answer(SPEC, "Acknowledge", cwd=plain))
        self.assertIn(f"status: acked {today()} #{specdoc.ack_hash(E3)}", ctx)
        self.assertNotIn("git ", ctx)
        self.assertEqual(len(self.acks()), 1)


class StatusLine(SpecCase):
    def setUp(self):
        super().setUp()
        self.task()  # a bound ISA that passes articulation: spec writes are otherwise allowed
        self.path = self.doc(SPEC, E3)
        self.line = f"status: acked {today()} #{specdoc.ack_hash(E3)}"

    def edit(self):
        return self.hook("PreToolUse", tool_name="Edit", tool_input={
            "file_path": self.path, "old_string": "status: draft", "new_string": self.line})[1]

    def test_unrecorded_refused(self):
        out = self.edit()
        self.assertEqual(self.decision(out), "deny", out)
        self.assertIn("Acknowledge", self.reason(out))

    def test_recorded_passes(self):
        self.answer(SPEC, "Acknowledge")
        out = self.edit()
        self.assertNotEqual(self.decision(out), "deny", out)

    def test_smuggled_edit_refused(self):
        self.answer(SPEC, "Acknowledge")
        text = E3.replace("status: draft", self.line).replace("24 or less", "30 or less")
        out = self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": self.path, "content": text})[1]
        self.assertEqual(self.decision(out), "deny", out)
        self.assertIn("match", self.reason(out))

    def test_shell_status_refused(self):
        self.answer(SPEC, "Acknowledge")  # even with a record: the status line is written with Edit
        for cmd in (f"sed -i 's/status: draft/{self.line}/' {SPEC}",
                    f"cat > {SPEC} <<'EOF'\n---\n{self.line}\neffort: E3\n---\nEOF"):
            out = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd})[1]
            self.assertEqual(self.decision(out), "deny", cmd)
            self.assertIn("status: acked", self.reason(out))

    def test_shell_status_text_without_write_passes(self):
        # found live: a commit message naming the status line next to a read of the spec is no status write
        for cmd in (f"git commit -qm 'record {self.line} after the click' && isa lint {SPEC}",
                    f"grep -n '{self.line}' {SPEC}",
                    f"git log -1 --format=%B | grep -q 'status: acked' && cat {SPEC}"):
            out = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd})[1]
            self.assertNotIn("status: acked", self.reason(out), cmd)
        for cmd in (f"perl -pi -e 's/status: draft/{self.line}/' {SPEC}",
                    f"python3 - <<'EOF'\nopen('{SPEC}', 'w').write('{self.line}')\nEOF"):
            out = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd})[1]
            self.assertEqual(self.decision(out), "deny", cmd)

    def test_acks_file_protected(self):
        acks = os.path.join(self.home, "_state", "acks.jsonl")
        out = self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": acks, "content": "{}\n"})[1]
        self.assertEqual(self.decision(out), "deny", out)
        self.assertIn("acks.jsonl", self.reason(out))
        out = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": f"echo '{{}}' >> {acks}"})[1]
        self.assertEqual(self.decision(out), "deny", out)
        self.assertIn("acks.jsonl", self.reason(out))


class PiAck(SpecCase):
    """Plan P8 (spec § 5.6 questions 3–5, pi column; § 8 item 12): pi asks the ack at `agent_before_settle`."""

    def setUp(self):
        super().setUp()
        setup_fake(self, isa_gate=0.1)  # below jev_quiet: no gate question, the prompt has the Continue pass

    def pi(self, event, pid="p1", **kw):
        d = {"event": event, "session": self.sid, "cwd": self.proj, "prompt_id": pid}
        d.update(kw)
        p = subprocess.run([sys.executable, ISA, "hook", "pi"], input=json.dumps(d), text=True,
                           capture_output=True, env=self.env, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout or "{}")

    def quiet(self, pid="p1", has_ui=True):
        res = self.pi("prompt", pid, prompt="draft the spec for the help screen", has_ui=has_ui)
        self.assertNotIn("ask", res)
        return res

    def pi_write(self, rel, text, pid="p1"):
        p = self.doc(rel, text)
        self.pi("post_tool", pid, tool="write", tool_input={"path": p, "content": text}, tool_output="")
        return os.path.realpath(p)

    def stop(self, pid="p1", has_ui=True, **kw):
        return self.pi("stop", pid, has_ui=has_ui, **kw)

    def ack(self, path, choice="Acknowledge", pid="p1"):
        return self.pi("ask_answer", pid, choice=choice, ask_kind="ack", ask_path=path)

    def pi_session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"pi-{self.sid}.json")) as f:
            return json.load(f)

    def assert_ack_ask(self, res, path, rel):
        self.assertEqual((res.get("ask_kind"), res.get("ask_path")), ("ack", path), res)
        self.assertEqual(res.get("options"), ["Acknowledge", "Request changes"])
        self.assertTrue(res["ask"].startswith("Acknowledge ") and res["ask"].endswith(f"{rel}?"), res["ask"])

    def test_settle_asks_spec(self):
        self.quiet()
        p = self.pi_write(SPEC, E3)
        self.assertEqual(self.pi_session()["doc"]["pid"], "p1")
        self.assert_ack_ask(self.stop(), p, SPEC)

    def test_settle_asks_plan(self):
        self.quiet()
        self.doc(E4_SPEC, E4)
        p = self.pi_write(PLAN_DOC, PLAN)
        self.assert_ack_ask(self.stop(), p, PLAN_DOC)

    def test_lint_fails_no_ask(self):
        self.quiet()
        self.pi_write(SPEC, E3.replace("Said:\n", ""))
        self.assertNotIn("ask", self.stop())
        p = self.pi_write(SPEC, E3)
        self.assert_ack_ask(self.stop(), p, SPEC)

    def test_unchanged_not_asked(self):
        self.quiet()
        p = self.pi_write(SPEC, E3)
        self.assert_ack_ask(self.stop(), p, SPEC)
        self.quiet("p2")
        self.assertNotIn("ask", self.stop("p2"))

    def test_acked_not_asked_again(self):
        self.quiet()
        p = self.pi_write(SPEC, E3)
        self.assert_ack_ask(self.stop(), p, SPEC)
        self.assertIn("block", self.ack(p))
        self.assertNotIn("ask", self.stop())  # recorded, status line not written yet
        line = f"status: acked {today()} #{specdoc.ack_hash(E3)}"
        edits = [{"oldText": "status: draft", "newText": line}]
        self.assertNotIn("deny", self.pi("pre_tool", tool="edit", tool_input={"path": p, "edits": edits}))
        self.doc(SPEC, E3.replace("status: draft", line))
        self.pi("post_tool", tool="edit", tool_input={"path": p, "edits": edits}, tool_output="")
        self.assertTrue(specdoc.acked(p))
        self.assertEqual(self.pi_session()["doc"]["pid"], "p1")  # written this prompt, yet acked: not asked
        self.assertNotIn("ask", self.stop())

    def test_acknowledge_records(self):
        self.quiet()
        p = self.pi_write(SPEC, E3)
        res = self.ack(self.stop()["ask_path"])
        rows = self.acks()
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual((rows[0]["path"], rows[0]["hash"], rows[0]["harness"], rows[0]["session"]),
                         (p, specdoc.ack_hash(E3), "pi", self.sid))
        self.assertIn(f"status: acked {today()} #{specdoc.ack_hash(E3)}", res.get("block", ""))
        self.assertIn(f'commit -m "Spec: Help screen redesign (acked)" -- {SPEC}', res["block"])

    def test_only_exact_label(self):
        self.quiet()
        p = self.pi_write(SPEC, E3)
        self.assert_ack_ask(self.stop(), p, SPEC)
        for a in ("Request changes", "ack", "Acknowledge (Recommended)", "acknowledge", "Acknowledge, but fix S2", ""):
            self.assertNotIn("block", self.ack(p, a), a)
        self.assertEqual(self.acks(), [])

    def test_answer_rechecks_lint(self):
        self.quiet()
        p = self.pi_write(SPEC, E3)
        self.assert_ack_ask(self.stop(), p, SPEC)
        self.doc(SPEC, E3.replace("Said:\n", ""))  # broken on disk before the click lands
        self.assertNotIn("block", self.ack(p))
        self.assertEqual(self.acks(), [])

    def test_answer_other_path(self):
        self.quiet()
        p = self.pi_write(SPEC, E3)
        other = os.path.realpath(self.doc("docs/spec/2026-10-06-other.md", E3))
        self.assertNotIn("block", self.ack(other))
        self.assertEqual(self.acks(), [])
        self.assertIn("block", self.ack(p))
        self.assertEqual([r["path"] for r in self.acks()], [p])

    def test_no_ui(self):
        self.quiet(has_ui=False)
        self.pi_write(SPEC, E3)
        self.assertNotIn("ask", self.stop(has_ui=False))
        self.assertEqual(self.acks(), [])

    def test_gate_first(self):
        self.env["ISA_JEV_BIN"] = os.path.join(self.tmp, "no-jev-here")  # Jev unavailable: the model judges
        self.assertNotIn("ask", self.pi("prompt", prompt="what does the help screen show?", has_ui=True))
        p = os.path.realpath(self.doc(SPEC, E3))
        # the doc bound this prompt without switching the session ON (a write would turn it ON and drop the gate)
        sess = os.path.join(self.home, "_state", "sessions", f"pi-{self.sid}.json")
        st = self.pi_session()
        st["doc"] = {"path": p, "kind": "spec", "pid": "p1"}
        with open(sess, "w") as f:
            json.dump(st, f)
        res = self.stop(context="ISA judge (model): no — a question about the help screen.")
        self.assertTrue(res.get("ask", "").startswith("ISA is not enabled for this prompt"), res)
        self.assertNotIn("ask_kind", res)
        self.assertNotIn("block", self.pi("ask_answer", choice="Continue without ISA"))
        setup_fake(self, isa_gate=0.1)
        self.quiet("p2")
        self.assert_ack_ask(self.stop("p2"), p, SPEC)  # the next completed run asks the ack
        self.assertNotIn("ask", self.stop("p2"))  # asked once: not again for an unchanged doc

    def test_pi_edit_status_guard(self):
        self.quiet()  # the Continue pass: only the status-line guard can refuse the edit
        p = self.pi_write(SPEC, E3)
        line = f"status: acked {today()} #{specdoc.ack_hash(E3)}"
        ti = {"path": p, "edits": [{"oldText": "status: draft", "newText": line}]}
        res = self.pi("pre_tool", tool="edit", tool_input=ti)
        self.assertIn("Acknowledge", res.get("deny", ""), res)
        self.assertIn("block", self.ack(self.stop()["ask_path"]))
        self.assertNotIn("deny", self.pi("pre_tool", tool="edit", tool_input=ti))

    def test_claude_stop_unchanged(self):
        self.write_doc(SPEC, E3)  # Claude Code: the model asks with AskUserQuestion, never the Stop hook
        code = ("import json, sys; sys.path.insert(0, sys.argv[1]); from isa import engine; "
                "print(json.dumps(engine.handle(json.load(sys.stdin))))")
        ev = {"event": "stop", "harness": "claude", "session": self.sid, "cwd": self.proj, "prompt_id": self.pid,
              "has_ui": True, "transcript_path": "/dev/null"}
        p = subprocess.run([sys.executable, "-c", code, os.path.join(ROOT, "runtime")], input=json.dumps(ev),
                           text=True, capture_output=True, env=self.env, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("ask", json.loads(p.stdout))


class SpecdocAcks(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="isa-p7-acks-", dir=os.path.expanduser("~/.cache"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.old = os.environ.get("ISA_HOME")
        os.environ["ISA_HOME"] = os.path.join(self.base, "home")
        self.addCleanup(lambda: os.environ.pop("ISA_HOME") if self.old is None
                        else os.environ.__setitem__("ISA_HOME", self.old))
        self.path = os.path.join(self.base, "docs", "spec", "2026-10-06-help.md")
        os.makedirs(os.path.dirname(self.path))

    def put(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def test_record_and_find(self):
        self.put(E3)
        h = specdoc.record_ack(self.path, "claude", "s1")
        self.assertEqual(h, specdoc.ack_hash(E3))
        with open(os.path.join(self.base, "home", "_state", "acks.jsonl")) as f:
            row = json.loads(f.readline())
        self.assertEqual({k: row[k] for k in ("path", "hash", "harness", "session")},
                         {"path": os.path.realpath(self.path), "hash": h, "harness": "claude", "session": "s1"})
        self.assertTrue(specdoc.ack_recorded(self.path, h))
        self.assertFalse(specdoc.ack_recorded(self.path, "00000000"))
        self.assertFalse(specdoc.ack_recorded(os.path.join(self.base, "docs", "spec", "other.md"), h))

    def test_acked(self):
        h = specdoc.ack_hash(E3)
        acked = E3.replace("status: draft", f"status: acked 2026-10-06 #{h}")
        self.put(acked)
        self.assertTrue(specdoc.acked(self.path))
        self.put(acked.replace("- [ ] A1: `tool --help", "- [x] A1: `tool --help").replace(
            "## S2 — Full reference\n", "## S2 — Full reference\nDone: 2026-10-09 — 1/1 accepted (ISAs x)\n"))
        self.assertTrue(specdoc.acked(self.path))
        self.put(acked.replace("24 or less", "30 or less"))
        self.assertFalse(specdoc.acked(self.path))
        self.put(E3)
        self.assertFalse(specdoc.acked(self.path))
        os.remove(self.path)
        self.assertFalse(specdoc.acked(self.path))


if __name__ == "__main__":
    unittest.main()
