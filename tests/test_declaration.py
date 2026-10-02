"""SPEC-v2 § 11.2: the gate makes no model call. The pre-filter settles clear prompts; an `unsure` one is
decided by the running model itself — it writes an ISA, or its answer carries
`ISA: not needed — <reason>`, which Stop checks as a string.

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
        self.config(ask_without_isa=False)  # the declaration alone; asking the user is in tests/test_ask.py

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


class TestUnsurePrompt(DeclCase):
    def test_declaration_line_and_still_off(self):
        code, out, _ = self.hook("UserPromptSubmit", prompt=QUESTION)
        self.assertEqual(code, 0)
        ctx = self.ctx(out)
        self.assertIn("[ISA: unsure", ctx)
        self.assertIn("`ISA: not needed — <one-line reason>`", ctx)
        self.assertIn("SKILL.md", ctx)
        self.assertNotIn("[ISA: ON", ctx)
        self.assertTrue(out["systemMessage"].startswith("ISA: unsure"))
        st = self.session()
        self.assertEqual((st["mode"] if "mode" in st else "off", st["declare_for"]), ("off", self.pid))
        row = self.log_rows("prompt")[-1]
        self.assertEqual((row["prefilter"], row["declare"]), ("unsure", True))


class TestDeclarationStop(DeclCase):
    def test_line_lets_the_turn_end(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        tr = self.transcript("ISA: not needed — a question about existing code.\n\nIt prints each task as `1 [ ] buy milk`.")
        self.assertEqual(self.stop(transcript_path=tr)[:3:2], (0, ""))
        self.assertTrue(self.log_rows("stop")[-1]["declared"])

    def test_last_assistant_message_field(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        code, _, err = self.stop(last_assistant_message="It prints the tasks.\nISA: not needed - just a question")
        self.assertEqual((code, err), (0, ""))

    def test_missing_line_blocks_once(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        tr = self.transcript("It prints each task as `1 [ ] buy milk`.")
        code, _, err = self.stop(transcript_path=tr)
        self.assertEqual(code, 2)
        self.assertIn("ISA: not needed — <one-line reason>", err)
        code, out, err = self.stop(transcript_path=tr)  # the second time the turn ends, with a warning
        self.assertEqual((code, err), (0, ""))
        self.assertIn("neither wrote an ISA nor said why", out.get("systemMessage", ""))

    def test_line_without_reason_is_not_enough(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        tr = self.transcript("ISA: not needed\n\nIt prints the tasks.")
        self.assertEqual(self.stop(transcript_path=tr)[0], 2)

    def test_an_isa_takes_the_on_path(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        path = self.isa_path()
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write(CLOSED.replace("phase: complete", "phase: observe"))  # an open ISA written this prompt
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": path}, tool_response={})
        code, _, err = self.stop(transcript_path=self.transcript("Working on it."))
        self.assertNotIn("ISA: not needed", err)  # ON rules apply now, not the declaration

    def test_a_change_takes_the_on_path(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        _, out, _ = self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": f"{self.proj}/x.py", "content": "x"})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        code, _, err = self.stop(transcript_path=self.transcript("ISA: not needed — tiny change"))
        self.assertEqual(code, 2)  # a write turned the session ON: an ISA is required, the line is not enough
        self.assertIn("No ISA yet", err)


class TestPrefilterModes(DeclCase):
    def test_yes_on_with_block(self):
        _, out, _ = self.hook("UserPromptSubmit", prompt="Fix the bug in dates.py so the tests pass")
        self.assertIn("[ISA: ON", self.ctx(out))
        self.assertTrue(out["systemMessage"].startswith("ISA: ON"))
        self.assertEqual(self.session()["mode"], "on")

    def test_no_off_and_silent(self):
        _, out, _ = self.hook("UserPromptSubmit", prompt="thanks, looks good")
        self.assertEqual(self.ctx(out), "")
        self.assertTrue(out["systemMessage"].startswith("ISA: OFF"))
        self.assertEqual(self.session()["mode"], "off")
        self.assertEqual(self.stop(transcript_path=self.transcript("You're welcome."))[:3:2], (0, ""))


class TestAfterComplete(DeclCase):
    def bind_closed(self):
        path = self.isa_path()
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write(CLOSED)
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": path}, tool_response={})
        return path

    def test_unsure_needs_isa_reopen_or_line(self):
        self.bind_closed()
        self.pid = "p2"
        _, out, _ = self.hook("UserPromptSubmit", prompt=QUESTION)
        ctx = self.ctx(out)
        self.assertIn("new ISA (or a reopen", ctx)
        self.assertIn("ISA: not needed", ctx)
        self.assertEqual(self.stop(transcript_path=self.transcript("It prints the tasks."))[0], 2)
        self.pid = "p3"
        self.hook("UserPromptSubmit", prompt=QUESTION)
        self.assertEqual(self.stop(transcript_path=self.transcript("ISA: not needed — a question"))[:3:2], (0, ""))


if __name__ == "__main__":
    import unittest
    unittest.main()
