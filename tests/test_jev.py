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
from tests.test_hooks import ISA, ROOT, HookCase, fake_cli

QUESTION = "what does cmd_list in todo.py print?"
PRESETS = os.path.join(ROOT, "runtime", "isa", "jev")

FAKE_JEV = r'''
argv = sys.argv[1:]
stdin = sys.stdin.read()
with open(os.environ["FAKE_JEV_LOG"], "a") as f:
    f.write(json.dumps({"argv": argv, "presets": os.environ.get("JEV_KIT_PRESETS", ""), "stdin": stdin}) + "\n")
mode = os.environ.get("FAKE_JEV_MODE", "served")
preset = argv[1] if len(argv) > 1 else ""
def unavailable(reason, detail, code):
    print(json.dumps({"ok": False, "consumer": "isa", "unavailable": {"reason": reason, "detail": detail}}))
    sys.exit(code)
if mode == "slow":
    time.sleep(6)
if mode == "credit":
    unavailable("error", "402 Payment Required: insufficient credit balance on this account", 4)
if mode == "tripped":
    unavailable("tripped", "isa: 5 consecutive failures, cooling down 60s", 4)
if mode == "budget":
    unavailable("budget", "isa: tokensPerDay 500000 reached", 5)
if mode == "garbled":
    print("<html>bad gateway</html>")
    sys.exit(0)
d = os.environ["JEV_KIT_PRESETS"].split(":")[0]
with open(os.path.join(d, preset + ".json")) as f:
    qs = json.load(f)["questions"]
p = float(os.environ.get("FAKE_JEV_P_" + preset.replace("-", "_"), os.environ.get("FAKE_JEV_P", "0.93")))
print(json.dumps({"ok": True, "consumer": "isa", "model": "jev-1.13.0",
                  "answers": {q: {"type": "noul", "answer": p} for q in qs}, "usage": {}}))
'''


def setup_fake(case, mode="served", **p):
    bin_ = os.path.join(case.tmp, "fakejev")
    path = fake_cli(bin_, "jev", FAKE_JEV)
    case.jev_log = os.path.join(case.tmp, "jev-calls.jsonl")
    case.env.update(ISA_JEV_BIN=path, FAKE_JEV_LOG=case.jev_log, FAKE_JEV_MODE=mode,
                    **{f"FAKE_JEV_P_{k}": str(v) for k, v in p.items()})


def calls(case, preset=None):
    try:
        with open(case.jev_log) as f:
            rows = [json.loads(line) for line in f]
    except OSError:
        return []
    return [r for r in rows if preset is None or r["argv"][1:2] == [preset]]


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
        self.assertIn("[ISA: unsure", self.ctx(out))
        self.assertEqual(calls(self), [])
        self.assertNotIn("Jev", out.get("systemMessage", ""))  # not installed is not an outage


class TestDefaultCall(JevHookCase):
    def test_gate_call(self):
        setup_fake(self)
        self.prompt()
        c = calls(self)
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]["argv"], ["run", "isa-gate", "--consumer", "isa"])
        self.assertEqual(os.path.realpath(c[0]["presets"].split(":")[0]), os.path.realpath(PRESETS))
        self.assertEqual(json.loads(c[0]["stdin"])["prompt"], QUESTION)

    def test_clear_prompts_skip_jev(self):
        setup_fake(self)
        self.prompt("thanks!")
        self.prompt("Fix the bug in dates.py so the tests pass")
        self.assertEqual(calls(self), [])


class TestDeadline(JevHookCase):
    def test_slow_jev_is_cut(self):
        setup_fake(self, mode="slow")
        t0 = time.time()
        _, out, _ = self.prompt()
        self.assertLess(time.time() - t0, 4.5)
        self.assertIn("[ISA: unsure", self.ctx(out))
        self.assertEqual(self.log_rows("jev")[-1]["reason"], "timeout")


class TestGateYes(JevHookCase):
    def test_confident_yes_switches_on(self):
        setup_fake(self, isa_gate=0.93)
        _, out, _ = self.prompt("can you look into why the export is empty sometimes")
        self.assertIn("[ISA: ON", self.ctx(out))
        self.assertIn("Jev", out["systemMessage"])
        self.assertEqual(self.session()["mode"], "on")


class TestAddOnly(JevHookCase):
    def baseline(self):
        other = JevHookCase("run")
        other.setUp()
        try:
            other.config(jev=False)
            return other.ctx(other.prompt()[1])
        finally:
            other.tearDown()

    def test_low_answer_and_outage_change_nothing(self):
        expected = self.baseline()
        setup_fake(self, isa_gate=0.4)
        self.assertEqual(self.ctx(self.prompt()[1]), expected)
        self.env["FAKE_JEV_MODE"] = "tripped"
        self.pid = "p2"
        self.assertEqual(self.ctx(self.prompt()[1]), expected)
        self.assertNotEqual(self.session().get("mode"), "on")


class TestGarbled(JevHookCase):
    def test_not_served(self):
        setup_fake(self, mode="garbled")
        _, out, _ = self.prompt()
        self.assertIn("[ISA: unsure", self.ctx(out))
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
