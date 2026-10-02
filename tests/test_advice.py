"""SPEC-v2 M7: the advisory judge — `probe_adequacy` at `isa lint`, `goal_met` / `asks_met` at `isa close`.
Never blocking, never an error. A fake `claude` answers by template; no model is called.

Run: python3 -m unittest tests.test_advice
"""
import json
import os
import sys
import unittest

from tests.test_commands import CommandCase
from tests.test_evidence import read
from tests.test_gate import fake_cli
from tests.test_hooks import ROOT

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import evidence  # noqa: E402

JUDGE = r"""
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"prompt": prompt}) + "\n")
if os.environ.get("FAKE_FAIL"):
    sys.exit(3)
if "Items (ISC: criterion | probe)" in prompt:
    out = []
    for line in prompt.splitlines():
        if line.startswith("- ISC-") and " | probe: " in line:
            isc = line[2:].split(":", 1)[0]
            tool = line.split(" | probe: ", 1)[1].strip()
            bad = tool == "true"
            out.append({"isc": isc, "verdict": "no" if bad else "yes",
                        "reason": "it can't fail" if bad else "fails when false"})
    answer = {"verdicts": out}
elif "Stated goal:" in prompt:
    answer = {"verdict": "yes", "reason": "fake goal ok"}
elif "The asks (verbatim spans" in prompt:
    answer = {"verdict": "no", "reason": "Ask 1 has no evidence"}
else:
    answer = {"verdict": "yes", "reason": "?"}
print(json.dumps({"type": "result", "result": "", "structured_output": answer}))
"""


class AdviceCase(CommandCase):
    def setUp(self):
        super().setUp()
        bin_ = os.path.join(self.tmp, "fakebin")
        fake_cli(bin_, "claude", JUDGE)
        self.log = os.path.join(self.tmp, "judge-calls.jsonl")
        self.env.update(ISA_JUDGE="claude", PATH=bin_ + os.pathsep + self.env["PATH"], FAKE_LOG=self.log)
        self.weak = self.text.replace(f"tool: test -f {self.d}/ok2", 'tool: "true"')

    def calls(self):
        try:
            with open(self.log) as f:
                return [json.loads(line)["prompt"] for line in f]
        except OSError:
            return []

    def closable(self, text):
        path = self.write_isa(text)
        self.flag("ok1")
        self.flag("ok2")
        self.verify(path)
        self.isa("verify", path, "ISC-3", "--attest", "looked at it")
        ask = "- Ask 1: met — the flags are checked\n" if "asks:" in text else ""
        self.write_isa(read(path).rstrip("\n") + "\n" + ask + "- Goal: yes — done\n", path)
        return path


class TestProbeAdequacy(AdviceCase):
    def test_warning_and_cache(self):
        path = self.write_isa(self.weak)
        rc, out = self.isa("lint", path)
        self.assertEqual(rc, 0, out)
        self.assertIn("WARN: ISC-2: the judge doubts this probe would fail if the ISC were false — it can't fail", out)
        self.assertNotIn("WARN: ISC-1", out)
        rc, out = self.isa("lint", path)
        self.assertIn("ISC-2: the judge doubts", out)  # still shown, from the cache
        self.assertEqual(len(self.calls()), 1)  # judged once per (ISC, probe)
        rows = [r for r in evidence.rows(path) if r.get("question") == "probe_adequacy"]
        self.assertEqual(sorted(r["isc"] for r in rows), ["ISC-1", "ISC-2", "ISC-4"])


class TestBatched(AdviceCase):
    def test_one_call_then_only_the_changed_probe(self):
        path = self.write_isa(self.weak)
        self.isa("lint", path)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.calls()[0].count("| probe: "), 3)
        self.write_isa(read(path).replace(f"tool: echo run >> {self.d}/runs && test -f {self.d}/ok1\n- isc: ISC-2",
                                          f"tool: test -f {self.d}/ok1\n- isc: ISC-2"), path)
        self.isa("lint", path)
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(self.calls()[1].count("| probe: "), 1)
        self.assertIn("- ISC-1:", self.calls()[1])


class TestJudgeFailureIsQuiet(AdviceCase):
    def test_lint_and_close(self):
        self.env["FAKE_FAIL"] = "1"
        path = self.write_isa(self.text)
        rc, out = self.isa("lint", path)
        self.assertEqual(rc, 0, out)
        self.assertIn("probe adequacy not judged this time", out)
        path = self.closable(self.text.replace("updated: 2026-01-01T00:00:00Z",
                                               'updated: 2026-01-01T00:00:00Z\nasks: ["check the flags"]'))
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 0, out)
        self.assertIn("goal_met: not judged (the judge failed)", out)


class TestCloseAdvice(AdviceCase):
    def test_recorded_and_shown(self):
        path = self.closable(self.text.replace("updated: 2026-01-01T00:00:00Z",
                                               'updated: 2026-01-01T00:00:00Z\nasks: ["check the flags"]'))
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 0, out)  # an advisory "no" never blocks
        self.assertIn("goal_met: yes — fake goal ok", out)
        self.assertIn("asks_met: no — Ask 1 has no evidence", out)
        qs = {r["question"]: r["verdict"] for r in evidence.rows(path) if r.get("kind") == "advice"
              and r.get("question") in ("goal_met", "asks_met")}
        self.assertEqual(qs, {"goal_met": "yes", "asks_met": "no"})

    def test_no_asks_no_asks_question(self):
        path = self.closable(self.text)
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 0, out)
        self.assertIn("goal_met: yes", out)
        self.assertNotIn("asks_met", out)


class TestAdviceOff(AdviceCase):
    def test_switch_and_heuristic(self):
        self.env["ISA_ADVICE"] = "off"
        path = self.write_isa(self.weak)
        rc, out = self.isa("lint", path)
        self.assertNotIn("judge doubts", out)
        self.assertEqual(self.calls(), [])
        self.env.pop("ISA_ADVICE")
        self.env["ISA_JUDGE"] = "heuristic"
        rc, out = self.isa("lint", path)
        self.assertNotIn("judge", out)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
