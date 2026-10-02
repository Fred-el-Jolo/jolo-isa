"""The gate's judge against a calibration set, live (`ISA_JUDGE=claude`, Haiku: a few cents a run).

    ISA_FLOW_LIVE=1 python3 -m unittest tests.flow.test_gate_calibration

The prompts are worded differently from the examples in gate.md, so a pass means the rule generalises
and isn't just the judge echoing an example back. Only prompts the free pre-filter leaves `unsure`
reach the judge; the others are checked against the pre-filter's answer. Each verdict and its time
are printed.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "runtime"))

LIVE = os.environ.get("ISA_FLOW_LIVE") == "1"

# (prompt, previous assistant message, expected verdict)
CASES = [
    # investigations of the user's own system → yes
    ("why is the build slow?", "", "yes"),
    ("why does the nightly export sometimes produce an empty CSV?", "", "yes"),
    ("any idea why test_parse keeps failing on CI but passes locally?", "", "yes"),
    ("what's causing the memory growth in the worker process?", "", "yes"),
    # other work → yes
    ("can you compare the two retry strategies in net.py and pick one?", "", "yes"),
    ("go", "I can split the parser into three functions and add tests for each. Want me to?", "yes"),
    # explanations, general knowledge, conversation → no
    ("what does cmd_list in todo.py print?", "", "no"),
    ("how do Python generators work?", "", "no"),
    ("why do people prefer composition over inheritance?", "", "no"),
    ("what's the difference between git merge and git rebase?", "", "no"),
    ("sounds good", "Is there anything else you'd like to know about the parser?", "no"),
]


@unittest.skipUnless(LIVE, "live, paid judge calls: set ISA_FLOW_LIVE=1")
class TestGateCalibration(unittest.TestCase):
    def test_cases(self):
        saved = {k: os.environ.get(k) for k in ("ISA_HOME", "ISA_JUDGE")}
        os.environ.update(ISA_HOME=tempfile.mkdtemp(prefix="isa-gate-cal-"), ISA_JUDGE="claude")
        try:
            from isa import judge
            wrong = []
            for prompt, context, want in CASES:
                v = judge.gate(prompt, context=context, harness="claude")
                print(f"{v['verdict']:>3} via {v['source']:<9} {v.get('ms', 0):>5} ms  {prompt!r} — {v['reason']}",
                      file=sys.stderr)
                if v["source"] == "error":
                    self.fail(f"the judge failed on {prompt!r}: {v['reason']}")
                if v["verdict"] != want:
                    wrong.append(f"{prompt!r}: got {v['verdict']} ({v['reason']}), want {want}")
            self.assertFalse(wrong, "\n".join(wrong))
        finally:
            for k, val in saved.items():
                if val is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = val


if __name__ == "__main__":
    unittest.main()
