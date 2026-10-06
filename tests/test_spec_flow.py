"""Plan P7 (spec 2026-10-06 § B.4, § B.7, § 5.6, § 8 items 8 and 15): a written spec or plan binds to the
session, the ack question is refused until the document lints clean at "ack", only an answer of exactly
`Acknowledge` is recorded, and no `status: acked … #h` line is written without a matching record.

Real git repos, a fake `jev`. Run: python3 -m unittest tests.test_spec_flow
"""
import json
import os
import re
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
from isa import specdoc, state  # noqa: E402

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

    def pi(self, event, pid="p1", **kw):
        d = {"event": event, "session": self.sid, "cwd": self.proj, "prompt_id": pid}
        d.update(kw)
        p = subprocess.run([sys.executable, ISA, "hook", "pi"], input=json.dumps(d), text=True,
                           capture_output=True, env=self.env, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout or "{}")

    def pi_write(self, rel, text, pid="p1"):
        p = self.doc(rel, text)
        self.pi("post_tool", pid, tool="write", tool_input={"path": p, "content": text}, tool_output="")
        return os.path.realpath(p)

    def pi_session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"pi-{self.sid}.json")) as f:
            return json.load(f)

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

    def quiet(self, pid="p1", has_ui=True):
        res = self.pi("prompt", pid, prompt="draft the spec for the help screen", has_ui=has_ui)
        self.assertNotIn("ask", res)
        return res

    def stop(self, pid="p1", has_ui=True, **kw):
        return self.pi("stop", pid, has_ui=has_ui, **kw)

    def ack(self, path, choice="Acknowledge", pid="p1"):
        return self.pi("ask_answer", pid, choice=choice, ask_kind="ack", ask_path=path)

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


def acked(text):
    return text.replace("status: draft", f"status: acked 2026-10-06 #{specdoc.ack_hash(text)}")


TRIAGE = "write the E1 ISA, or the spec, first"
NOT_ACKED = "spec not acknowledged yet"
PLAN_NOT_ACKED = "plan not acknowledged yet"
PRE_ACK = "project files changed before the spec was acknowledged — revert them or ask the user"


class StageRules(SpecCase):
    """Plan P9 (spec § 5, § 5.2, § 8 item 6): the stage of a session and what each stage enforces."""

    def on(self):
        setup_fake(self, isa_gate=0.93)  # Jev yes: ON, nothing bound
        rc, out, err = self.hook("UserPromptSubmit", prompt="redesign the help screen of the tool")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.st().get("mode"), "on")

    def stage(self):
        code = ("import sys; sys.path.insert(0, sys.argv[1]); from isa import engine, state; "
                "print(engine._stage(state.read_session('claude', sys.argv[2]), sys.argv[3]))")
        p = subprocess.run([sys.executable, "-c", code, os.path.join(ROOT, "runtime"), self.sid, self.proj],
                           text=True, capture_output=True, env=self.env, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def pre(self, path, content="x"):
        return self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": path, "content": content})[1]

    def bash(self, cmd):
        return self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd})[1]

    def stop(self):
        return self.hook("Stop", last_assistant_message="Here is the spec draft.")

    def assert_denied(self, out, text):
        self.assertEqual(self.decision(out), "deny", out)
        self.assertIn(text, self.reason(out))

    def test_stage_values(self):
        self.assertEqual(self.stage(), "off")
        self.on()
        self.assertEqual(self.stage(), "triage")
        self.write_doc(SPEC, E3)
        self.assertEqual(self.stage(), "spec_draft")
        self.answer(SPEC, "Acknowledge")
        self.assertEqual(self.stage(), "spec_acked")
        self.doc(E4_SPEC, acked(E4))
        self.write_doc(PLAN_DOC, PLAN)
        self.assertEqual(self.stage(), "plan_draft")
        self.answer(PLAN_DOC, "Acknowledge", header="Plan ack")
        self.assertEqual(self.stage(), "plan_acked")
        self.task()
        self.assertEqual(self.stage(), "build")

    def test_triage_spec_write_passes(self):
        self.on()
        out = self.pre(os.path.join(self.proj, SPEC), E3)
        self.assertNotEqual(self.decision(out), "deny", out)

    def test_triage_refuses_change(self):
        self.on()
        self.assert_denied(self.edit_project()[1], TRIAGE)

    def test_near_miss_names_path(self):
        self.on()
        for rel in ("docs/specs/2026-10-06-help.md", "SPEC.md", "docs/spec/2026-10-06-help.txt"):
            out = self.pre(os.path.join(self.proj, rel), E3)
            self.assert_denied(out, "docs/spec/YYYY-MM-DD-<slug>.md")
            self.assertIn(rel, self.reason(out))

    def test_spec_draft_refuses_change(self):
        self.on()
        self.write_doc(SPEC, E3)
        self.assert_denied(self.edit_project()[1], NOT_ACKED)

    def test_spec_draft_refuses_isa_new(self):
        self.on()
        self.write_doc(SPEC, E3)
        for cmd in ("isa new help", "isa new help --tier E3", "isa new help --goal 'redesign the help screen of it'"):
            self.assert_denied(self.bash(cmd), NOT_ACKED)
        for cmd in ("isa new help --tier E1", "isa new help --tier=e1"):
            self.assertNotEqual(self.decision(self.bash(cmd)), "deny", cmd)

    def test_spec_draft_refuses_isa_write(self):
        self.on()
        self.write_doc(SPEC, E3)
        path = self.isa_path("20261006-000000_help")
        self.assert_denied(self.pre(path, "---\ntask: help\neffort: E3\n---\n"), NOT_ACKED)
        self.assertNotEqual(self.decision(self.pre(path, "---\ntask: help\neffort: E1\n---\n")), "deny")

    def test_plan_draft_refuses(self):
        self.on()
        self.doc(E4_SPEC, acked(E4))
        self.write_doc(PLAN_DOC, PLAN)
        self.assert_denied(self.edit_project()[1], PLAN_NOT_ACKED)
        self.assert_denied(self.bash("isa new api-step"), PLAN_NOT_ACKED)

    def test_e4_spec_acked_needs_plan(self):
        self.on()
        self.write_doc(E4_SPEC, acked(E4))
        self.assertEqual(self.stage(), "spec_acked")
        out = self.edit_project()[1]
        self.assert_denied(out, PLAN_NOT_ACKED)
        self.assertIn("docs/plan/2026-10-06-api-migration.md", self.reason(out))

    def test_stop_ack_question(self):
        self.on()
        self.write_doc(SPEC, E3)
        self.answer(SPEC, "Request changes")
        rc, _, err = self.stop()
        self.assertEqual(rc, 0, err)

    def test_stop_open_questions(self):
        self.on()
        self.write_doc(SPEC, E3 + "- Should `-h` print the short form or the full reference?\n")
        rc, _, err = self.stop()
        self.assertEqual(rc, 0, err)

    def test_stop_refuses_once(self):
        self.on()
        self.write_doc(SPEC, E3)
        rc, _, err = self.stop()
        self.assertEqual(rc, 2, err)
        self.assertIn("Spec ack", err)
        rc, _, err = self.stop()
        self.assertEqual(rc, 0, err)

    def change_before_ack(self):
        self.on()
        self.write_doc(SPEC, E3)
        cmd = "python3 -c \"open('gen.txt', 'w').write('x')\""
        self.assertNotEqual(self.decision(self.bash(cmd)), "deny")
        subprocess.run(cmd, shell=True, cwd=self.proj, check=True)
        return self.hook("PostToolUse", tool_name="Bash", tool_input={"command": cmd},
                         tool_response={"stdout": "", "stderr": ""})[1]

    def test_pre_ack_change_reported(self):
        self.assertIn("before the spec was acknowledged", self.ctx(self.change_before_ack()))

    def test_pre_ack_change_stop(self):
        self.change_before_ack()
        rc, _, err = self.stop()
        self.assertEqual(rc, 2, err)
        self.assertIn(PRE_ACK, err)
        rc, _, err = self.stop()
        self.assertEqual(rc, 0, err)

    def test_after_ack_needs_isa(self):
        self.on()
        self.write_doc(SPEC, E3)
        self.answer(SPEC, "Acknowledge")
        self.write_doc(SPEC, acked(E3))
        self.assertEqual(self.stage(), "spec_acked")
        rc, _, err = self.stop()
        self.assertEqual(rc, 2, err)
        self.assertIn("No ISA yet", err)

    def test_pi_on_session_asks_ack(self):
        setup_fake(self, isa_gate=0.93)
        self.assertNotIn("ask", self.pi("prompt", prompt="redesign the help screen of the tool", has_ui=True))
        p = self.pi_write(SPEC, E3)
        self.assertEqual(self.pi_session().get("mode"), "on")
        res = self.pi("stop", has_ui=True, context="Here is the spec draft.")
        self.assertNotIn("block", res)
        self.assertEqual((res.get("ask_kind"), res.get("ask_path")), ("ack", p), res)

    def test_q2_new_task_triage(self):
        self.on()
        self.write_doc(SPEC, E3)
        self.pid = "p2"
        setup_fake(self, isa_continuation=0.91)
        self.hook("UserPromptSubmit", prompt="now add a man page generator to the release script")
        self.assertEqual(self.st()["q2"]["outcome"], "new")
        self.assertEqual(self.stage(), "triage")
        self.assert_denied(self.edit_project()[1], TRIAGE)

    def test_other_project_doc(self):
        other = tempfile.mkdtemp(prefix="isa-p9-other-", dir=os.path.expanduser("~/.cache"))
        self.addCleanup(shutil.rmtree, other, True)
        self.on()
        self.write_doc(SPEC, E3, root=other)
        self.assertEqual(self.st()["doc"]["path"], os.path.realpath(os.path.join(other, SPEC)))
        self.assertEqual(self.stage(), "triage")
        self.assert_denied(self.edit_project()[1], TRIAGE)

    def test_pass_unaffected(self):
        setup_fake(self, isa_gate=0.1)  # below jev_quiet: the Continue pass
        self.hook("UserPromptSubmit", prompt="redesign the help screen of the tool")
        self.write_doc(SPEC, E3)
        self.assertNotEqual(self.decision(self.edit_project()[1]), "deny")

    def test_no_spec_passes_gate(self):
        self.on()
        self.write_doc(SPEC, E3)
        self.assertNotEqual(self.decision(self.bash("isa new tweak --no-spec --tier E2")), "deny")

    def test_build_unaffected(self):
        self.task()
        self.write_doc(SPEC, E3)
        self.assertEqual(self.stage(), "build")
        self.assertNotEqual(self.decision(self.edit_project()[1]), "deny")


GOAL_LINE = "`tool --help` fits one screen and leads with the common tasks."


def fm_block(text):
    return text.split("\n---\n", 1)[0] + "\n---\n"


class SpecLinks(unittest.TestCase):
    """Plan P10: `specdoc.resolve` and `specdoc.seed` (spec § B.5, § 5.4, § 5.5)."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="isa-p10-links-", dir=os.path.expanduser("~/.cache"))
        self.addCleanup(shutil.rmtree, self.base, True)
        for rel, text in ((SPEC, E3), (E4_SPEC, E4), (PLAN_DOC, PLAN)):
            p = os.path.join(self.base, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(text)

    def resolve(self, link):
        return specdoc.resolve(link, root=self.base)

    def test_resolve_spec(self):
        self.assertEqual(self.resolve(f"{SPEC}#S1"), [("S1", "A1"), ("S1", "A2")])
        self.assertEqual(self.resolve(f"{SPEC}#S2:A1"), [("S2", "A1")])
        self.assertEqual(self.resolve(f"{SPEC}#S1,S2"), [("S1", "A1"), ("S1", "A2"), ("S2", "A1")])
        self.assertEqual(self.resolve(SPEC), [("S1", "A1"), ("S1", "A2"), ("S2", "A1")])
        self.assertEqual(specdoc.resolve(os.path.join(self.base, SPEC) + "#S2"), [("S2", "A1")])

    def test_resolve_plan(self):
        self.assertEqual(self.resolve(f"{PLAN_DOC}#P2"), [("S2", "A1"), ("S2", "A2"), ("S2", "A3")])
        self.assertEqual(self.resolve(f"{PLAN_DOC}#P1"), [("S1", "A1"), ("S1", "A2")])

    def test_resolve_errors(self):
        for link, part in (("docs/spec/2026-10-06-none.md#S1", "2026-10-06-none.md"), (f"{SPEC}#S9", "S9"),
                           (f"{SPEC}#S1:A9", "S1:A9"), (f"{PLAN_DOC}#P9", "P9")):
            with self.assertRaisesRegex(ValueError, re.escape(part)):
                self.resolve(link)

    def test_seed_spec(self):
        s = specdoc.seed(f"{SPEC}#S1", root=self.base)
        self.assertEqual(s["goal"], GOAL_LINE)
        self.assertEqual(s["criteria"], [("S1:A1", "`tool --help | wc -l` prints 24 or less"),
                                         ("S1:A2", "the first task listed is `tool sync`")])
        self.assertEqual((s["tier"], s["constraints"], s["review_focus"]),
                         ("E3", ["At most 24 lines at 80 columns."], []))

    def test_seed_plan(self):
        s = specdoc.seed(f"{PLAN_DOC}#P3", root=self.base)
        self.assertEqual((s["goal"], s["tier"]), ("The REST adapter", "E3"))
        self.assertEqual(s["criteria"], [("S3:A1", "the REST contract tests pass unchanged"),
                                         ("P3", "the REST contract tests pass unchanged.")])
        self.assertEqual(s["review_focus"], ["a client sending both REST and GraphQL headers"])
        self.assertEqual(s["constraints"], ["REST responses stay byte-identical until 2027-04-06."])


class NewLinked(SpecCase):
    """Plan P10: `isa new --spec / --plan / --no-spec` (spec § 5.4 step 5, § 5.5 step 5, § 8 items 7, 17)."""

    def isa_dirs(self):
        folder = os.path.dirname(os.path.dirname(self.isa_path()))
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def new(self, *args):
        rc, out = self.isa("new", "help", *args)
        return rc, out

    def new_spec(self, link=f"{SPEC}#S1", *extra, text=None):
        self.doc(SPEC, text or acked(E3))
        rc, out = self.new("--spec", link, *extra)
        self.assertEqual(rc, 0, out)
        path = out.strip().splitlines()[-1]
        with open(path) as f:
            return path, f.read(), out

    def plan_ready(self, plan=None):
        self.doc(E4_SPEC, acked(E4))
        self.doc(PLAN_DOC, acked(plan or PLAN.replace("- [ ] P1 — The schema", "- [x] P1 — The schema")))

    def test_spec_not_acked(self):
        self.doc(SPEC, E3)
        before = self.isa_dirs()
        rc, out = self.new("--spec", f"{SPEC}#S1")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("not acknowledged", out)
        self.assertEqual(self.isa_dirs(), before)

    def test_spec_changed_since_ack(self):
        self.doc(SPEC, acked(E3).replace("24 or less", "30 or less"))
        rc, out = self.new("--spec", f"{SPEC}#S1")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("changed since its ack", out)

    def test_marks_keep_ack(self):
        text = acked(E3).replace("- [ ] A1: `tool --help", "- [x] A1: `tool --help").replace(
            "## S2 — Full reference\n", "## S2 — Full reference\nDone: 2026-10-09 — 1/1 accepted (ISAs x)\n")
        path, _, _ = self.new_spec(text=text)
        self.assertEqual(state.frontmatter(path).get("spec"), f"{SPEC}#S1")

    def test_plan_after_open(self):
        self.plan_ready(PLAN)
        rc, out = self.new("--plan", f"{PLAN_DOC}#P3")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("P1", out)
        rc, out = self.new("--plan", f"{PLAN_DOC}#P1")
        self.assertEqual(rc, 0, out)

    def test_plan_not_acked(self):
        self.doc(E4_SPEC, acked(E4))
        self.doc(PLAN_DOC, PLAN)
        rc, out = self.new("--plan", f"{PLAN_DOC}#P1")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("not acknowledged", out)
        self.doc(E4_SPEC, E4)
        self.doc(PLAN_DOC, acked(PLAN))
        rc, out = self.new("--plan", f"{PLAN_DOC}#P1")
        self.assertNotEqual(rc, 0, out)
        self.assertIn(E4_SPEC, out)

    def test_seed_goal(self):
        path, text, _ = self.new_spec()
        fm = state.frontmatter(path)
        self.assertEqual((fm.get("spec"), fm.get("stated_goal"), fm.get("stated_goal_source")),
                         (f"{SPEC}#S1", GOAL_LINE, "spec"))
        self.assertIn(f"## Goal\n\n{GOAL_LINE}\n", text)

    def test_seed_criteria(self):
        _, text, _ = self.new_spec(f"{SPEC}#S1,S2")
        for line in ("- [ ] ISC-1: `tool --help | wc -l` prints 24 or less",
                     "- [ ] ISC-2: the first task listed is `tool sync`",
                     "- [ ] ISC-3: every flag of the old help appears in `tool help --all`"):
            self.assertIn(line + "\n", text)
        self.assertEqual(re.findall(r'- isc: (ISC-\d+)\n  anchors_to: "([^"]+)"', text),
                         [("ISC-1", "S1:A1"), ("ISC-2", "S1:A2"), ("ISC-3", "S2:A1")])

    def test_seed_tier(self):
        e2 = E3.replace("effort: E3", "effort: E2")
        path, _, _ = self.new_spec(text=acked(e2))
        self.assertEqual(state.frontmatter(path)["effort"], "E2")
        path, _, _ = self.new_spec(f"{SPEC}#S1", "--tier", "E4", text=acked(e2))
        self.assertEqual(state.frontmatter(path)["effort"], "E4")

    def test_pointer_lines(self):
        _, text, _ = self.new_spec()
        for sec in ("Problem", "Vision", "Out of Scope", "Constraints"):
            self.assertIn(f"## {sec}\n\nSee {SPEC}#S1\n", text)

    def test_constraints_printed(self):
        path, _, out = self.new_spec()
        self.assertIn("At most 24 lines at 80 columns.", out)
        self.assertTrue(path.endswith("/ISA.md"), out)

    def test_plan_seed(self):
        self.plan_ready()
        rc, out = self.new("--plan", f"{PLAN_DOC}#P3")
        self.assertEqual(rc, 0, out)
        fm = state.frontmatter(out.strip().splitlines()[-1])
        self.assertEqual((fm.get("plan"), fm.get("stated_goal"), fm.get("stated_goal_source"), fm.get("effort")),
                         (f"{PLAN_DOC}#P3", "The REST adapter", "spec", "E3"))

    def test_plan_review_focus(self):
        self.plan_ready()
        rc, out = self.new("--plan", f"{PLAN_DOC}#P3")
        self.assertEqual(rc, 0, out)
        with open(out.strip().splitlines()[-1]) as f:
            text = f.read()
        self.assertRegex(text, r"- \[ \] ISC-\d+: a client sending both REST and GraphQL headers\n")
        self.assertNotIn("a list query issuing one SQL query per item", text)

    def test_no_spec(self):
        rc, out = self.isa("new", "tweak", "--no-spec", "--tier", "E2")
        self.assertEqual(rc, 0, out)
        with open(out.strip().splitlines()[-1]) as f:
            self.assertRegex(f.read(), r"## Decisions\n\n- \d{4}-\d\d-\d\d \d\d:\d\d: no-spec: the user's call\n")
        self.doc(SPEC, acked(E3))
        self.doc(E4_SPEC, acked(E4))
        self.doc(PLAN_DOC, acked(PLAN))
        for extra in (("--plan", f"{PLAN_DOC}#P1"), ("--no-spec",)):
            rc, out = self.new("--spec", f"{SPEC}#S1", *extra)
            self.assertNotEqual(rc, 0, out)


FILLED_E2 = """## Problem

See {spec}#S1

## Goal

{goal}

## Criteria

- [ ] ISC-1: `tool --help` prints at most 24 lines.
- [ ] ISC-2: `tool sync` is the first task `tool --help` lists.
- [ ] ISC-3: Anti: `tool --help` prints an ANSI escape code.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "S1:A1"
  type: bash
  kind: behaviour
  check: line count
  threshold: exit 0
  tool: test "$(python3 tool.py --help | wc -l)" -le 24
- isc: ISC-2
  anchors_to: "{a2}"
  type: bash
  kind: behaviour
  check: first task
  threshold: exit 0
  tool: python3 tool.py --help | grep -m1 -q 'tool sync'
- isc: ISC-3
  anchors_to: "Goal"
  type: bash
  kind: regression
  check: no escape code
  threshold: exit 0
  tool: "! python3 tool.py --help | grep -q $'\\\\x1b'"
  fails-when: "an escape code appears in the help output"
```
"""

FILLED_E3_EXTRA = """
## Features

```yaml
- name: summary
  description: the short help screen
  satisfies: [ISC-1, ISC-2, ISC-3]
  depends_on: []
  parallelizable: false
```
"""


class LinkLint(NewLinked):
    """Plan P10: lint of a linked ISA (spec § B.5 "What lint changes in a linked ISA", § B.6)."""

    def filled(self, tier="E2", a2="S1:A2", goal=GOAL_LINE):
        path, text, _ = self.new_spec(f"{SPEC}#S1", "--tier", tier)
        self.assertIn(f"spec: {SPEC}#S1", text)  # the scaffold came out linked
        fm = fm_block(text).replace("asks: []", "asks: []\ncontext_sufficient: true").replace(
            f"stated_goal: \"{GOAL_LINE}\"", f"stated_goal: \"{goal}\"").replace("progress: 0/2", "progress: 0/3")
        body = FILLED_E2.format(spec=SPEC, goal=GOAL_LINE, a2=a2)
        if tier == "E3":
            pointers = "".join(f"## {s}\n\nSee {SPEC}#S1\n\n" for s in ("Vision", "Out of Scope", "Constraints"))
            body = body.replace("## Goal", pointers + "## Goal") + FILLED_E3_EXTRA
        with open(path, "w") as f:
            f.write(fm + "\n" + body)
        return path

    def lint_isa(self, path):
        return self.isa("lint", path)

    def test_unanchored_bullet(self):
        rc, out = self.lint_isa(self.filled())
        self.assertEqual(rc, 0, out)
        rc, out = self.lint_isa(self.filled(a2="Goal"))
        self.assertNotEqual(rc, 0, out)
        self.assertIn("S1:A2", out)

    def test_pointer_sections_pass(self):
        rc, out = self.lint_isa(self.filled("E3"))
        self.assertEqual(rc, 0, out)

    def test_spec_goal_source(self):
        rc, out = self.lint_isa(self.filled())  # no logged prompt holds the goal: the spec does
        self.assertEqual(rc, 0, out)
        rc, out = self.lint_isa(self.filled(goal="`tool --help` fits two screens and leads with the common tasks."))
        self.assertNotEqual(rc, 0, out)
        self.assertIn("stated_goal", out)


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


# ------------------------------------------------------------------ plan P11: the done marks (spec § B.6)

D1, D2 = "2026-10-08", "2026-10-09"
SA, SB = "20261008-101500_first", "20261009-091200_second"
# this repo's shape: a spec without `S<n>` sections, a plan whose steps cover `§8.N` items
REPO_SPEC = """---
status: draft
effort: E4
plan: docs/plan/2026-10-06-repo.md
---

# Repo spec

## 8. Acceptance

1. One holds.
2. Two holds.
"""
REPO_PLAN = """---
status: draft
spec: docs/spec/2026-10-06-repo.md
---

# Plan — Repo

Goal: both items hold.

- [x] P1 — First · E3 · covers §8.1 · Done: 2026-10-06
  Files: `a.txt`
  Done when:
  - one holds.
- [ ] P2 — Second · E3 · covers §8.2 · after P1
  Files: `a.txt`
  Done when:
  - two holds.
- [ ] P3 — Third · E2 · covers §8.2 · after P2
  Files: `a.txt`
  Done when:
  - three holds.
"""


def section(text, sid):
    """The lines of `## <sid>` up to the next `## ` heading."""
    out, inside = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            inside = line.startswith(f"## {sid} ")
            continue
        if inside:
            out.append(line)
    return out


def done_lines(text, sid):
    return [ln for ln in section(text, sid) if ln.startswith("Done:")]


def status_of(text):
    return specdoc.status_line(text)


class MarkDone(unittest.TestCase):
    """Plan P11: `specdoc.mark_done(path, bullets, slug, date)` (spec § B.6)."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="isa-p11-marks-", dir=os.path.expanduser("~/.cache"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.spec = self.put(SPEC, acked(E3))

    def put(self, rel, text):
        p = os.path.join(self.base, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        return p

    def read(self, p):
        with open(p) as f:
            return f.read()

    def plan(self, text=PLAN):
        self.put(E4_SPEC, acked(E4))
        return self.put(PLAN_DOC, acked(text))

    def test_ticks_bullets(self):
        specdoc.mark_done(self.spec, [("S1", "A1")], SA, D1)
        t = self.read(self.spec)
        self.assertIn(f"- [x] A1: `tool --help | wc -l` prints 24 or less  ({D1}, ISA {SA})\n", t)
        self.assertIn("- [ ] A2: the first task listed is `tool sync`\n", t)
        self.assertIn("- [ ] A1: every flag of the old help appears in `tool help --all`\n", t)

    def test_done_line(self):
        specdoc.mark_done(self.spec, [("S1", "A1")], SA, D1)
        self.assertEqual(done_lines(self.read(self.spec), "S1"), [])
        specdoc.mark_done(self.spec, [("S1", "A2")], SA, D1)
        t = self.read(self.spec)
        self.assertIn(f"## S1 — Summary screen\nDone: {D1} — 2/2 accepted (ISAs {SA})\nThe default", t)
        self.assertEqual(done_lines(t, "S2"), [])

    def test_done_line_replaced(self):
        specdoc.mark_done(self.spec, [("S1", "A1"), ("S1", "A2")], SA, D1)
        specdoc.mark_done(self.spec, [("S1", "A1"), ("S1", "A2")], SB, D2)
        t = self.read(self.spec)
        self.assertEqual(done_lines(t, "S1"), [f"Done: {D2} — 2/2 accepted (ISAs {SA})"])
        self.assertEqual(len(re.findall(r"^Done:", t, re.M)), 1)

    def test_done_names_earlier_isas(self):
        spec = self.put(E4_SPEC, acked(E4))
        specdoc.mark_done(spec, [("S2", "A1"), ("S2", "A2")], SA, D1)
        self.assertEqual(done_lines(self.read(spec), "S2"), [])
        specdoc.mark_done(spec, [("S2", "A3")], SB, D2)
        self.assertEqual(done_lines(self.read(spec), "S2"), [f"Done: {D2} — 3/3 accepted (ISAs {SA}, {SB})"])

    def test_ticks_step(self):
        plan = self.plan()
        specdoc.mark_done(plan, ["P1"], SA, D1)
        t = self.read(plan)
        self.assertIn(f"\n- [x] P1 — The schema · E2 · covers S1:A1,A2 · Done: {D1}\n", t)
        self.assertIn("\n- [ ] P3 — The REST adapter · E3 · covers S3 · after P1, P2\n", t)

    def test_spec_done(self):
        h = specdoc.ack_hash(E3)
        lines = specdoc.mark_done(self.spec, [("S1", "A1"), ("S1", "A2"), ("S2", "A1")], SA, D1)
        t = self.read(self.spec)
        self.assertEqual(status_of(t), f"status: done {D1} #{h}")
        self.assertIn(f"status: done {D1} #{h}", lines)
        # a dropped section doesn't hold the spec open
        spec = self.put("docs/spec/2026-10-06-drop.md", acked(E3.replace(
            "- [ ] A1: every flag of the old help appears in `tool help --all`", "- [ ] A1: [DROPPED — moved out]")))
        specdoc.mark_done(spec, [("S1", "A1"), ("S1", "A2")], SA, D1)
        self.assertTrue(status_of(self.read(spec)).startswith(f"status: done {D1} #"))

    def test_plan_done(self):
        plan = self.plan()
        specdoc.mark_done(plan, ["P1"], SA, D1)
        self.assertTrue(status_of(self.read(plan)).startswith("status: acked "))
        specdoc.mark_done(plan, ["P3"], SB, D2)
        self.assertEqual(status_of(self.read(plan)), f"status: done {D2} #{specdoc.ack_hash(PLAN)}")

    def test_never_done_from_empty(self):
        bare = self.put("docs/spec/2026-10-06-repo.md", acked(REPO_SPEC))
        before = self.read(bare)
        self.assertEqual(specdoc.mark_done(bare, [], SA, D1), [])
        self.assertEqual(self.read(bare), before)
        dropped = E3
        for b in ("A1: `tool --help | wc -l` prints 24 or less", "A2: the first task listed is `tool sync`",
                  "A1: every flag of the old help appears in `tool help --all`"):
            dropped = dropped.replace(f"- [ ] {b}", f"- [ ] {b[:2]}: [DROPPED — not needed]")
        spec = self.put("docs/spec/2026-10-06-dropped.md", acked(dropped))
        specdoc.mark_done(spec, [], SA, D1)
        self.assertTrue(status_of(self.read(spec)).startswith("status: acked "))

    def test_open_keeps_status(self):
        acked_line = status_of(self.read(self.spec))
        specdoc.mark_done(self.spec, [("S1", "A1"), ("S1", "A2")], SA, D1)
        self.assertEqual(status_of(self.read(self.spec)), acked_line)
        plan = self.plan()
        plan_line = status_of(self.read(plan))
        specdoc.mark_done(plan, ["P1"], SA, D1)
        self.assertEqual(status_of(self.read(plan)), plan_line)

    def test_returns_changed_lines(self):
        lines = specdoc.mark_done(self.spec, [("S1", "A1")], SA, D1)
        self.assertEqual(lines, [f"- [x] A1: `tool --help | wc -l` prints 24 or less  ({D1}, ISA {SA})"])
        os.utime(self.spec, ns=(1_000_000_000, 1_000_000_000))
        self.assertEqual(specdoc.mark_done(self.spec, [("S1", "A1")], SA, D1), [])
        self.assertEqual(os.stat(self.spec).st_mtime_ns, 1_000_000_000)

    def test_keeps_hash_and_format(self):
        text = acked(E3)
        with open(self.spec, "wb") as f:
            f.write(text.replace("\n", "\r\n").encode())
        os.chmod(self.spec, 0o640)
        specdoc.mark_done(self.spec, [("S1", "A1"), ("S1", "A2")], SA, D1)
        with open(self.spec, "rb") as f:
            raw = f.read()
        self.assertIn(b"Done: ", raw)
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        self.assertEqual(os.stat(self.spec).st_mode & 0o777, 0o640)
        self.assertEqual(specdoc.ack_hash(raw.decode()), specdoc.ack_hash(text))
        self.assertTrue(specdoc.acked(self.spec))

    def test_waits_for_lock(self):
        code = ("import sys; sys.path.insert(0, sys.argv[1]); from isa import specdoc; "
                "specdoc.mark_done(sys.argv[2], [('S1', 'A2')], sys.argv[3], sys.argv[4])")
        with specdoc.doc_lock(self.spec):
            p = subprocess.Popen([sys.executable, "-c", code, os.path.join(ROOT, "runtime"), self.spec, SB, D2])
            time.sleep(0.6)
            self.assertIsNone(p.poll(), "mark_done ran while another process held the lock")
            self.assertEqual(self.read(self.spec), acked(E3))
            # what the first close writes while it holds the lock
            with open(self.spec, "w") as f:
                f.write(acked(E3).replace("- [ ] A1: `tool --help | wc -l` prints 24 or less",
                                          f"- [x] A1: `tool --help | wc -l` prints 24 or less  ({D1}, ISA {SA})"))
        self.assertEqual(p.wait(timeout=20), 0)
        t = self.read(self.spec)
        self.assertIn(f"({D1}, ISA {SA})", t)
        self.assertIn(f"({D2}, ISA {SB})", t)
        self.assertEqual(done_lines(t, "S1"), [f"Done: {D2} — 2/2 accepted (ISAs {SA}, {SB})"])
        self.assertFalse(os.path.exists(self.spec + ".lock"))

    def test_refuses_changed(self):
        self.put(SPEC, acked(E3).replace("24 or less", "30 or less"))
        before = self.read(self.spec)
        with self.assertRaisesRegex(ValueError, "spec changed since its ack — ask the user to acknowledge it again"):
            specdoc.mark_done(self.spec, [("S1", "A1")], SA, D1)
        self.assertEqual(self.read(self.spec), before)

    def test_done_status_holds(self):
        h = specdoc.ack_hash(E3)
        done = E3.replace("status: draft", f"status: done {D1} #{h}")
        self.put(SPEC, done)
        self.assertEqual([m for m in specdoc.lint(self.spec, "ack") if "status" in m], [])
        self.assertTrue(specdoc.ack_holds(done))
        self.assertTrue(specdoc.ack_holds(acked(E3)))
        self.assertFalse(specdoc.acked(self.spec))
        self.assertFalse(specdoc.ack_holds(done.replace("24 or less", "30 or less")))
        self.assertFalse(specdoc.ack_holds(E3))


LINKED = """---
task: "Prove the linked bullets"
slug: {slug}
effort: E2
phase: build
progress: 0/{n}
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
root: {root}
{key}: {link}
asks: []
context_sufficient: true
---

## Problem

See {link}

## Goal

The linked bullets hold.

## Criteria

{criteria}
## Test Strategy

```yaml
{entries}```
"""


def flag(tag):
    return "ok-" + tag.replace(":", "-")


class CloseMarks(SpecCase):
    """Plan P11: `isa close` writes the done marks of a linked ISA (spec § B.6, § 8 items 9–11)."""

    def linked(self, key, link, tags, slug):
        crit, entries = [], []
        for i, tag in enumerate(tags + ["anti"], 1):
            anti = tag == "anti"
            crit.append(f"- [ ] ISC-{i}: " + ("Anti: the file `bad` exists." if anti else f"bullet {tag} holds."))
            entries.append(f"- isc: ISC-{i}\n  anchors_to: \"{'Goal' if anti else tag}\"\n  type: bash\n"
                           f"  kind: {'regression' if anti else 'file'}\n  check: flag file\n  threshold: exit 0\n"
                           f"  tool: {'test ! -e bad' if anti else 'test -f ' + flag(tag)}\n"
                           f"  fails-when: \"the flag file says otherwise\"\n")
        text = LINKED.format(slug=slug, n=len(tags) + 1, root=os.path.realpath(self.proj), key=key, link=link,
                             criteria="\n".join(crit) + "\n", entries="".join(entries))
        path = self.write_isa(text, self.isa_path(slug))
        for tag in tags:
            self.put(flag(tag), "")
        rc, out = self.isa("verify", path)
        self.assertEqual(rc, 0, out)
        with open(path) as f:
            self.write_isa(f.read().rstrip("\n") + "\n- Goal: yes — every flag file is there\n", path)
        return path

    def close(self, path):
        return self.isa("close", path)

    def closed(self, key, link, tags, slug):
        path = self.linked(key, link, tags, slug)
        rc, out = self.close(path)
        self.assertEqual(rc, 0, out)
        return path

    def doc_text(self, rel):
        with open(os.path.join(self.proj, rel)) as f:
            return f.read()

    def test_close_ticks_section(self):
        self.doc(SPEC, acked(E3))
        self.closed("spec", f"{SPEC}#S1", ["S1:A1", "S1:A2"], SA)
        t = self.doc_text(SPEC)
        self.assertIn(f"- [x] A1: `tool --help | wc -l` prints 24 or less  ({today()}, ISA {SA})\n", t)
        self.assertIn(f"- [x] A2: the first task listed is `tool sync`  ({today()}, ISA {SA})\n", t)
        self.assertIn("- [ ] A1: every flag of the old help appears in `tool help --all`\n", t)

    def test_close_one_done_line(self):
        self.doc(SPEC, acked(E3))
        self.closed("spec", f"{SPEC}#S1", ["S1:A1", "S1:A2"], SA)
        t = self.doc_text(SPEC)
        self.assertEqual(done_lines(t, "S1"), [f"Done: {today()} — 2/2 accepted (ISAs {SA})"])
        self.assertTrue(status_of(t).startswith("status: acked "))

    def test_second_close_replaces(self):
        self.doc(SPEC, acked(E3))
        self.closed("spec", f"{SPEC}#S1", ["S1:A1", "S1:A2"], SA)
        self.closed("spec", f"{SPEC}#S1", ["S1:A1", "S1:A2"], SB)
        t = self.doc_text(SPEC)
        self.assertEqual(done_lines(t, "S1"), [f"Done: {today()} — 2/2 accepted (ISAs {SA})"])
        self.assertEqual(len(re.findall(r"^Done:", t, re.M)), 1)

    def test_shared_section_first(self):
        self.doc(E4_SPEC, acked(E4))
        self.closed("spec", f"{E4_SPEC}#S2:A1,A2", ["S2:A1", "S2:A2"], SA)
        t = self.doc_text(E4_SPEC)
        self.assertRegex(t, r"- \[x\] A1: each query returns the same data as its REST endpoint  \(")
        self.assertRegex(t, r"- \[x\] A2: the N\+1 query count stays at 1 per list  \(")
        self.assertIn("- [ ] A3: p95 latency under 200 ms\n", t)
        self.assertEqual(done_lines(t, "S2"), [])

    def test_shared_section_second(self):
        self.doc(E4_SPEC, acked(E4))
        self.closed("spec", f"{E4_SPEC}#S2:A1,A2", ["S2:A1", "S2:A2"], SA)
        self.closed("spec", f"{E4_SPEC}#S2:A3", ["S2:A3"], SB)
        t = self.doc_text(E4_SPEC)
        self.assertEqual(done_lines(t, "S2"), [f"Done: {today()} — 3/3 accepted (ISAs {SA}, {SB})"])
        self.assertEqual(specdoc.ack_hash(t), specdoc.ack_hash(E4))
        self.assertTrue(specdoc.acked(os.path.join(self.proj, E4_SPEC)))

    def test_plan_step(self):
        self.doc(E4_SPEC, acked(E4))
        self.doc(PLAN_DOC, acked(PLAN))
        self.closed("plan", f"{PLAN_DOC}#P1", ["S1:A1", "S1:A2"], SA)
        spec, plan = self.doc_text(E4_SPEC), self.doc_text(PLAN_DOC)
        self.assertRegex(spec, r"- \[x\] A1: every REST resource has a GraphQL type  \(")
        self.assertRegex(spec, r"- \[x\] A2: the schema passes `graphql-schema-linter`  \(")
        self.assertEqual(done_lines(spec, "S1"), [f"Done: {today()} — 2/2 accepted (ISAs {SA})"])
        self.assertIn(f"\n- [x] P1 — The schema · E2 · covers S1:A1,A2 · Done: {today()}\n", plan)
        self.assertTrue(status_of(spec).startswith("status: acked "))
        self.assertTrue(status_of(plan).startswith("status: acked "))

    def test_step_without_bullets(self):
        spec_rel, plan_rel = "docs/spec/2026-10-06-repo.md", "docs/plan/2026-10-06-repo.md"
        spec_before = acked(REPO_SPEC)
        self.doc(spec_rel, spec_before)
        self.doc(plan_rel, acked(REPO_PLAN))
        plan_before = self.doc_text(plan_rel)
        self.closed("plan", f"{plan_rel}#P2", ["P2"], SA)
        self.assertEqual(self.doc_text(spec_rel), spec_before)
        old = "- [ ] P2 — Second · E3 · covers §8.2 · after P1"
        self.assertEqual(self.doc_text(plan_rel),
                         plan_before.replace(old, f"- [x] P2 — Second · E3 · covers §8.2 · after P1 · Done: {today()}"))
        self.assertTrue(specdoc.acked(os.path.join(self.proj, spec_rel)))
        self.assertTrue(specdoc.acked(os.path.join(self.proj, plan_rel)))

    def test_failed_close_writes_nothing(self):
        self.doc(SPEC, acked(E3))
        path = self.linked("spec", f"{SPEC}#S1", ["S1:A1", "S1:A2"], SA)
        before = self.doc_text(SPEC)
        os.remove(os.path.join(self.proj, flag("S1:A2")))
        rc, out = self.close(path)
        self.assertNotEqual(rc, 0, out)
        self.assertEqual(self.doc_text(SPEC), before)

    def test_refuses_changed_spec(self):
        self.doc(SPEC, acked(E3))
        path = self.linked("spec", f"{SPEC}#S1", ["S1:A1", "S1:A2"], SA)
        changed = acked(E3).replace("24 or less", "30 or less")
        self.doc(SPEC, changed)
        rc, out = self.close(path)
        self.assertNotEqual(rc, 0, out)
        self.assertIn("spec changed since its ack — ask the user to acknowledge it again", out)
        self.assertEqual(self.doc_text(SPEC), changed)
        self.assertNotEqual(state.frontmatter(path).get("phase"), "complete")

    def test_two_processes_no_lost_tick(self):
        self.doc(SPEC, acked(E3))
        a = self.linked("spec", f"{SPEC}#S1:A1", ["S1:A1"], SA)
        b = self.linked("spec", f"{SPEC}#S1:A2", ["S1:A2"], SB)
        procs = [subprocess.Popen([sys.executable, ISA, "close", p], cwd=self.proj, env=self.env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT) for p in (a, b)]
        outs = [p.communicate(timeout=60)[0] for p in procs]
        self.assertEqual([p.returncode for p in procs], [0, 0], outs)
        t = self.doc_text(SPEC)
        self.assertIn(f"prints 24 or less  ({today()}, ISA {SA})\n", t)
        self.assertIn(f"`tool sync`  ({today()}, ISA {SB})\n", t)
        self.assertEqual(done_lines(t, "S1"), [f"Done: {today()} — 2/2 accepted (ISAs {SA}, {SB})"])
        self.assertFalse(os.path.exists(os.path.join(self.proj, SPEC + ".lock")))


if __name__ == "__main__":
    unittest.main()
