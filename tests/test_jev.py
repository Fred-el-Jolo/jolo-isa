"""SPEC-v2 § 11, M9: the Jev layer — on by default, bounded, add-only, advisory; outages fall back to the
baseline with one clear message. A fake `jev` (ISA_JEV_BIN) plays every case; no test reaches the real one.

Run: python3 -m unittest tests.test_jev
"""
import json
import os
import subprocess
import sys
import time

from tests.test_commands import CommandCase
from tests.test_evidence import read
from tests.test_hooks import ISA, ROOT, HookCase, calls, setup_fake  # noqa: F401 (re-exported)

QUESTION = "what does cmd_list in todo.py print?"
PRESETS = os.path.join(ROOT, "runtime", "isa", "jev")

class JevHookCase(HookCase):
    def prompt(self, text=QUESTION):
        return self.hook("UserPromptSubmit", prompt=text)

    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)


class TestSwitch(JevHookCase):
    def test_config_off(self):
        setup_fake(self)
        self.config(jev=False)
        self.prompt()
        self.assertEqual(calls(self), [])
        self.assertEqual(self.log_rows("jev"), [])

    def test_no_cli(self):
        setup_fake(self)
        self.env["ISA_JEV_BIN"] = os.path.join(self.tmp, "no-such-jev")
        _, out, _ = self.prompt()
        self.assertIn("ISA judge (model)", self.ctx(out))  # the model judges
        self.assertEqual(calls(self), [])
        self.assertNotIn("Jev credit", out.get("systemMessage", ""))  # not installed is not an outage
        self.assertNotIn("Jev unavailable (off:", out.get("systemMessage", ""))


class TestDefaultCall(JevHookCase):
    def test_gate_call(self):
        setup_fake(self)
        self.prompt()
        c = calls(self)
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]["argv"], ["run", "isa-gate", "--consumer", "isa"])
        self.assertEqual(os.path.realpath(c[0]["presets"].split(":")[0]), os.path.realpath(PRESETS))
        self.assertEqual(json.loads(c[0]["stdin"])["prompt"], QUESTION)

    def test_every_prompt_is_judged(self):  # SPEC-v2 § 12: no keyword pre-filter in front of Jev
        setup_fake(self, isa_gate=0.2)
        self.prompt("thanks!")
        self.pid = "p2"
        self.prompt("Fix the bug in dates.py so the tests pass")
        self.assertEqual(len(calls(self, "isa-gate")), 2)


class TestDeadline(JevHookCase):
    def test_slow_jev_is_cut(self):
        setup_fake(self, mode="slow")
        t0 = time.time()
        _, out, _ = self.prompt()
        self.assertLess(time.time() - t0, 4.5)
        self.assertIn("ISA judge (model)", self.ctx(out))  # past the deadline: the model judges
        self.assertEqual(self.log_rows("jev")[-1]["reason"], "timeout")


class TestGateYes(JevHookCase):
    def test_confident_yes_switches_on(self):
        setup_fake(self, isa_gate=0.93)
        _, out, _ = self.prompt("can you look into why the export is empty sometimes")
        self.assertIn("[ISA: ON", self.ctx(out))
        self.assertIn("Jev", out["systemMessage"])
        self.assertEqual(self.session()["mode"], "on")


class TestAddOnly(JevHookCase):
    def test_low_answer_and_outage_never_switch_on(self):  # § 12.1: below the line the user decides
        setup_fake(self, isa_gate=0.4)
        self.assertIn("AskUserQuestion", self.ctx(self.prompt()[1]))
        self.env["FAKE_JEV_MODE"] = "tripped"
        self.pid = "p2"
        self.assertIn("ISA judge (model)", self.ctx(self.prompt()[1]))
        self.assertNotEqual(self.session().get("mode"), "on")


class TestGarbled(JevHookCase):
    def test_not_served(self):
        setup_fake(self, mode="garbled")
        _, out, _ = self.prompt()
        self.assertIn("ISA judge (model)", self.ctx(out))
        self.assertEqual(self.log_rows("jev")[-1]["reason"], "garbled")


class TestCreditMessage(JevHookCase):
    def test_once_per_session(self):
        setup_fake(self, mode="credit")
        _, out, _ = self.prompt()
        msg = out.get("systemMessage", "")
        self.assertIn("Jev credit looks exhausted (402 Payment Required: insufficient credit balance", msg)
        self.assertIn("top up TypeSafe credits, then run `jev reset`", msg)
        self.assertIn("`jev disable`", msg)
        self.assertIn('`"jev": false` in ~/.isa/config.json', msg)
        self.pid = "p2"
        _, out, _ = self.prompt()
        self.assertNotIn("Jev credit", out.get("systemMessage", ""))


class TestOtherMessages(JevHookCase):
    def test_budget(self):
        setup_fake(self, mode="budget")
        _, out, _ = self.prompt()
        self.assertIn('Jev\'s daily budget for consumer "isa" is used up (isa: tokensPerDay 500000 reached)',
                      out.get("systemMessage", ""))

    def test_tripped(self):
        setup_fake(self, mode="tripped")
        _, out, _ = self.prompt()
        self.assertIn("Jev unavailable (tripped: isa: 5 consecutive failures", out.get("systemMessage", ""))
        self.assertIn("`jev status`", out.get("systemMessage", ""))


class TestJevRows(JevHookCase):
    def test_row(self):
        setup_fake(self, isa_gate=0.42)
        self.prompt()
        row = self.log_rows("jev")[-1]
        self.assertEqual((row["preset"], row["served"], row["answer"], row["session"]), ("isa-gate", True, 0.42, self.sid))
        self.assertIsInstance(row["ms"], int)


class TestStatusJev(JevHookCase):
    def status(self):
        p = subprocess.run([sys.executable, ISA, "status", "--session", self.sid, "--json"], env=self.env,
                           text=True, capture_output=True)
        return json.loads(p.stdout)["jev"]

    def test_served_then_credit(self):
        setup_fake(self, isa_gate=0.3)  # low: the session stays OFF, so the next prompt asks Jev again
        self.prompt()
        self.assertEqual(self.status()["served"], True)
        self.env["FAKE_JEV_MODE"] = "credit"
        self.pid = "p2"
        self.prompt()
        st = self.status()
        self.assertEqual((st["served"], st["reason"]), (False, "error"))
        self.assertIn("credit", st["detail"])


class JevCommandCase(CommandCase):
    def closable(self, asks=False):
        text = self.text
        if asks:
            self.hook("UserPromptSubmit", prompt="please check the flag files today")
            text = text.replace("updated: 2026-01-01T00:00:00Z",
                                'updated: 2026-01-01T00:00:00Z\nasks: ["check the flag files"]')
        path = self.write_isa(text)
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": path}, tool_response={})
        self.flag("ok1")
        self.flag("ok2")
        self.verify(path)
        self.isa("verify", path, "ISC-3", "--attest", "looked at it")
        extra = "- Ask 1: met — both flags checked\n" if asks else ""
        self.write_isa(read(path).rstrip("\n") + "\n" + extra + "- Goal: yes — done\n", path)
        return path


class TestProbeAdvice(JevCommandCase):
    def test_once_per_probe_and_warning(self):
        setup_fake(self, isa_probe=0.2)
        path = self.write_isa(self.text)
        self.flag("ok1")
        self.flag("ok2")
        rc, out = self.verify(path)
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(json.loads(c["stdin"])["isc"] for c in calls(self, "isa-probe")),
                         ["ISC-1", "ISC-2", "ISC-4"])  # the red-exempt ones (kind file, Anti)
        self.assertIn("Jev doubts ISC-2's probe would fail if the claim were false (0.2)", out)
        rc, out = self.verify(path)
        self.assertEqual(len(calls(self, "isa-probe")), 3)  # cached per (ISC, probe text)
        self.assertIn("Jev doubts ISC-2's probe", out)


class TestCloseAdvice(JevCommandCase):
    def test_shown_never_blocking(self):
        setup_fake(self, isa_goal=0.91, isa_ask=0.3)
        path = self.closable(asks=True)
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 0, out)
        self.assertIn("Jev (advisory — never blocks the close):", out)
        self.assertIn("goal delivered: 0.91", out)
        self.assertIn('Ask 1 ("check the flag files") met: 0.3 — check it', out)

    def test_outage_does_not_block(self):
        setup_fake(self, mode="tripped")
        path = self.closable()
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 0, out)
        self.assertIn("not judged (Jev unavailable: tripped)", out)


class TestCommandLine(JevCommandCase):
    def test_credit_line_in_close_and_relay_instruction(self):
        setup_fake(self, mode="credit")
        path = self.closable()
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 0, out)
        self.assertTrue(any(line.startswith("Jev: Jev credit looks exhausted") for line in out.splitlines()), out)
        with open(os.path.join(ROOT, "runtime", "isa", "protocol.md")) as f:
            self.assertIn("relay it to the user word for word", f.read())


if __name__ == "__main__":
    import unittest
    unittest.main()
