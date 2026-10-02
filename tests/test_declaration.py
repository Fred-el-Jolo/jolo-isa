"""SPEC-v2 § 12.5: when Jev is unavailable, the running model judges Q1 itself — its answer carries
`ISA judge (model): yes|no|unsure — <reason>`, which Stop reads as a string — or it writes an ISA.
The hooks never call a model CLI (tripwires on PATH).

Run: python3 -m unittest tests.test_declaration
"""
import json
import os

from tests.test_hooks import CLOSED, HookCase, fake_cli

QUESTION = "what does cmd_list in todo.py print?"
TRIPWIRE = """
with open(os.environ["TRIP_LOG"], "a") as f:
    f.write("called\\n")
sys.exit(3)
"""


class DeclCase(HookCase):
    def setUp(self):
        super().setUp()
        bin_ = os.path.join(self.tmp, "fakebin")
        for name in ("claude", "pi", "jev"):  # no model may be called on the hook path
            fake_cli(bin_, name, TRIPWIRE)
        self.trip = os.path.join(self.tmp, "trip.log")
        self.env.update(PATH=bin_ + os.pathsep + self.env["PATH"], TRIP_LOG=self.trip)
        self.config(ask_without_isa=False)  # the line alone; asking the user is in tests/test_ask.py

    def tearDown(self):
        self.assertFalse(os.path.exists(self.trip), "a model CLI was called from a hook")
        super().tearDown()

    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)

    def transcript(self, text):
        tr = os.path.join(self.tmp, f"tr-{len(os.listdir(self.tmp))}.jsonl")
        with open(tr, "w") as f:
            f.write(json.dumps({"type": "user", "message": {"role": "user", "content": QUESTION}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": text}]}}) + "\n")
        return tr

    def stop(self, **kw):
        return self.hook("Stop", stop_hook_active=False, **kw)


class TestModelJudges(DeclCase):
    def test_instruction_and_still_off(self):
        code, out, _ = self.hook("UserPromptSubmit", prompt=QUESTION)
        self.assertEqual(code, 0)
        ctx = self.ctx(out)
        self.assertIn("[ISA gate — Jev unavailable (off): you judge this prompt]", ctx)
        self.assertIn("`ISA judge (model): yes|no|unsure — <one-line reason>`", ctx)
        self.assertIn("SKILL.md", ctx)
        self.assertNotIn("[ISA: ON", ctx)
        st = self.session()
        self.assertEqual((st.get("mode", "off"), st["gate"]["judge"]), ("off", "model"))


class TestJudgeLineStop(DeclCase):
    def test_line_lets_the_turn_end(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        tr = self.transcript("ISA judge (model): no — a question about existing code.\n\nIt prints `1 [ ] buy milk`.")
        self.assertEqual(self.stop(transcript_path=tr)[:3:2], (0, ""))
        self.assertEqual(self.log_rows("stop")[-1]["model_verdict"], "no")

    def test_line_anywhere_and_last_assistant_message_field(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        code, _, err = self.stop(last_assistant_message="It prints the tasks.\nISA judge (model): unsure - just a question")
        self.assertEqual((code, err), (0, ""))

    def test_missing_line_blocks_once(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        tr = self.transcript("It prints each task as `1 [ ] buy milk`.")
        code, _, err = self.stop(transcript_path=tr)
        self.assertEqual(code, 2)
        self.assertIn("ISA judge (model): yes|no|unsure — <one-line reason>", err)
        code, out, err = self.stop(transcript_path=tr)  # the second time the turn ends, with a warning
        self.assertEqual((code, err), (0, ""))
        self.assertIn("neither judged this prompt nor wrote an ISA", out.get("systemMessage", ""))

    def test_old_declaration_is_not_the_line(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        tr = self.transcript("ISA: not needed — a question\n\nIt prints the tasks.")
        self.assertEqual(self.stop(transcript_path=tr)[0], 2)

    def test_an_isa_takes_the_on_path(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        path = self.isa_path()
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write(CLOSED.replace("phase: complete", "phase: observe"))  # an open ISA written this prompt
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": path}, tool_response={})
        code, _, err = self.stop(transcript_path=self.transcript("Working on it."))
        self.assertNotIn("ISA judge (model)", err)  # ON rules apply now, not the line

    def test_a_change_takes_the_on_path(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        _, out, _ = self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": f"{self.proj}/x.py", "content": "x"})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        code, _, err = self.stop(transcript_path=self.transcript("ISA judge (model): no — tiny change"))
        self.assertEqual(code, 2)  # a write turned the session ON: an ISA is required, the line is not enough
        self.assertIn("No ISA yet", err)


class TestAfterComplete(DeclCase):
    def bind_closed(self):
        path = self.isa_path()
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write(CLOSED)
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": path}, tool_response={})
        return path

    def test_model_judges_again_after_complete(self):
        self.bind_closed()
        self.pid = "p2"
        _, out, _ = self.hook("UserPromptSubmit", prompt=QUESTION)
        ctx = self.ctx(out)
        self.assertIn("ISA bound:", ctx)
        self.assertIn("ISA judge (model)", ctx)
        self.assertEqual(self.stop(transcript_path=self.transcript("It prints the tasks."))[0], 2)
        self.pid = "p3"
        self.hook("UserPromptSubmit", prompt=QUESTION)
        self.assertEqual(self.stop(transcript_path=self.transcript("ISA judge (model): no — a question"))[:3:2], (0, ""))
        self.pid = "p4"
        self.hook("UserPromptSubmit", prompt="Add a --shout flag to greet.py")
        code, _, err = self.stop(transcript_path=self.transcript("ISA judge (model): yes — a change"))
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)  # yes after a finished ISA: a new ISA (or a reopen) is required


if __name__ == "__main__":
    import unittest
    unittest.main()
