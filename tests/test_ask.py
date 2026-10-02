"""SPEC-v2 § 11.2: before an unsure prompt goes on without an ISA, the user is asked —
"ISA is not enabled for this prompt (<reason>). Continue?" — Continue without ISA (default) / Enable ISA.
Claude Code: the model asks with AskUserQuestion and the hooks read the answer. pi: the adapter asks
(tested in adapters/pi/test). On by default; `{"ask_without_isa": false}` in ~/.isa/config.json turns it off.

Run: python3 -m unittest tests.test_ask
"""
import json
import os

from tests.test_hooks import HookCase

QUESTION = "what does cmd_list in todo.py print?"
ASKED = "ISA is not enabled for this prompt (a question about the code). Continue?"


class AskCase(HookCase):
    def transcript(self, text):
        tr = os.path.join(self.tmp, f"tr-{len(os.listdir(self.tmp))}.jsonl")
        with open(tr, "w") as f:
            f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": text}]}}) + "\n")
        return tr

    def ask(self, answer, *, failed=False, via="input"):
        ti = {"questions": [{"question": ASKED, "header": "ISA", "multiSelect": False, "options": [
            {"label": "Continue without ISA (Recommended)", "description": "answer without an ISA"},
            {"label": "Enable ISA", "description": "write an ISA first"}]}]}
        if failed:
            return self.hook("PostToolUseFailure", tool_name="AskUserQuestion", tool_input=ti, error="not available")
        if via == "input":
            ti["answers"] = {ASKED: answer}
            return self.hook("PostToolUse", tool_name="AskUserQuestion", tool_input=ti, tool_response={})
        return self.hook("PostToolUse", tool_name="AskUserQuestion", tool_input=ti,
                         tool_response=f'User has answered your questions: "{ASKED}"="{answer}".')

    def stop(self, text):
        return self.hook("Stop", stop_hook_active=False, transcript_path=self.transcript(text))

    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)


DECLARED = "ISA: not needed — a question about the code.\n\nIt prints `1 [ ] buy milk`."


class TestAskInstruction(AskCase):
    def test_unsure_prompt_says_to_ask(self):
        _, out, _ = self.hook("UserPromptSubmit", prompt=QUESTION)
        ctx = self.ctx(out)
        self.assertIn("ask the user with AskUserQuestion", ctx)
        self.assertIn('"ISA is not enabled for this prompt (<your one-line reason>). Continue?"', ctx)
        self.assertIn('"Continue without ISA (Recommended)" and "Enable ISA"', ctx)
        self.assertEqual(self.session()["ask_mode"], "model")

    def test_clear_prompts_never_ask(self):
        for p in ("thanks!", "Fix the bug in dates.py so the tests pass"):
            _, out, _ = self.hook("UserPromptSubmit", prompt=p)
            self.assertNotIn("AskUserQuestion", self.ctx(out))


class TestAskRequired(AskCase):
    def test_declaration_without_asking_blocks_once(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        code, _, err = self.stop(DECLARED)
        self.assertEqual(code, 2)
        self.assertIn("the user was not asked", err)
        code, out, err = self.stop(DECLARED)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("did not ask you", out.get("systemMessage", ""))

    def test_continue_lets_it_end(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        self.ask("Continue without ISA (Recommended)")
        self.assertEqual(self.stop(DECLARED)[:3:2], (0, ""))

    def test_continue_counts_even_without_the_line(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        self.ask("Continue without ISA (Recommended)", via="output")
        self.assertEqual(self.stop("It prints `1 [ ] buy milk`.")[:3:2], (0, ""))


class TestEnableChoice(AskCase):
    def test_enable_switches_on_and_requires_an_isa(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        code, out, _ = self.ask("Enable ISA")
        self.assertEqual(self.session()["mode"], "on")
        self.assertIn("[ISA: ON", self.ctx(out))
        self.assertTrue(out["systemMessage"].startswith("ISA: ON"))
        code, _, err = self.stop(DECLARED)  # the line no longer counts: the user chose an ISA
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)

    def test_enable_read_from_the_text_answer(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        self.ask("Enable ISA", via="output")
        self.assertEqual(self.session()["mode"], "on")


class TestNoOneToAsk(AskCase):
    def test_headless_claude(self):
        self.env.update(CLAUDE_CODE_SESSION_ATTENDED="0", CLAUDE_CODE_ENTRYPOINT="sdk-cli")
        _, out, _ = self.hook("UserPromptSubmit", prompt=QUESTION)
        self.assertNotIn("AskUserQuestion", self.ctx(out))
        self.assertEqual(self.stop(DECLARED)[:3:2], (0, ""))
        self.assertEqual(self.log_rows("prompt")[-1]["ask"], "no-ui")

    def test_question_tool_failed(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        self.ask(None, failed=True)
        self.assertEqual(self.stop(DECLARED)[:3:2], (0, ""))
        self.assertEqual(self.log_rows("stop")[-1]["choice"], "unavailable")


class TestAskConfig(AskCase):
    def test_off(self):
        self.config(ask_without_isa=False)
        _, out, _ = self.hook("UserPromptSubmit", prompt=QUESTION)
        self.assertNotIn("AskUserQuestion", self.ctx(out))
        self.assertIn("ISA: not needed", self.ctx(out))
        self.assertEqual(self.stop(DECLARED)[:3:2], (0, ""))
        self.assertEqual(self.log_rows("prompt")[-1]["ask"], "config")

    def test_missing_and_broken_keep_it_on(self):
        _, out, _ = self.hook("UserPromptSubmit", prompt=QUESTION)  # no config.json
        self.assertIn("AskUserQuestion", self.ctx(out))
        with open(os.path.join(self.home, "config.json"), "w") as f:
            f.write("{not json")
        _, out, _ = self.hook("UserPromptSubmit", prompt=QUESTION)
        self.assertIn("AskUserQuestion", self.ctx(out))
        self.assertIn("config.json", self.log_rows("prompt")[-1]["config_error"])


class TestAskLog(AskCase):
    def test_stop_row(self):
        self.hook("UserPromptSubmit", prompt=QUESTION)
        self.ask("Continue without ISA (Recommended)")
        self.stop(DECLARED)
        row = self.log_rows("stop")[-1]
        self.assertEqual((row["declared"], row["asked"], row["choice"], row["ask"]), (True, True, "continue", "model"))
        self.assertEqual(row["reason"], "a question about the code.")
        post = [r for r in self.log_rows("post_tool") if r.get("tool") == "AskUserQuestion"][-1]
        self.assertEqual(post["choice"], "continue")


if __name__ == "__main__":
    import unittest
    unittest.main()
