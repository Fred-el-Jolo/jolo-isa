"""SPEC-v2 M9, live: each ISA preset through the real `jev` (jev-kit, consumer `isa`), within its deadline.
Opt-in and paid (a handful of Jev calls, a fraction of a cent):

    ISA_FLOW_LIVE=1 python3 -m unittest tests.flow.test_jev_live

The answers are printed for the record; whether they are *right* is reviewed in the logs (M10), not here.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "runtime"))
LIVE = os.environ.get("ISA_FLOW_LIVE") == "1"

EVIDENCE = """- [x] ISC-1: `done <id>` marks a task completed.
- [x] ISC-2: Anti: `done 99` for an unknown id exits 0.

- ISC-1: verified — exit 0 — `python3 -m unittest tests.test_todo.TestDone`
- ISC-2: verified — exit 0 — `! python3 todo.py done 99`"""

CASES = [
    ("isa-gate", {"prompt": "can you look into why the nightly export is sometimes empty?", "context": "", "skill": ""}, 1.5),
    ("isa-gate", {"prompt": "what does cmd_list in todo.py print?", "context": "", "skill": ""}, 1.5),
    ("isa-continuation", {"isa": "task: Add a done command to todo.py\nGoal: `done <id>` marks a task completed.",
                          "prompt": "now write the release notes for 2.0", "context": ""}, 1.5),
    ("isa-probe", {"isc": "ISC-2", "claim": "Anti: `done 99` for an unknown id exits 0.",
                   "probe": "! python3 todo.py done 99", "why_exempt": "Anti",
                   "fails_when": "`done 99` exits 0"}, 3.0),
    ("isa-probe", {"isc": "ISC-3", "claim": "The README documents the --pending flag.", "probe": "true",
                   "why_exempt": "kind doc", "fails_when": "(not written)"}, 3.0),
    ("isa-goal", {"stated_goal": "Add a `done <id>` command to todo.py", "goal": "todo.py has a done command.",
                  "evidence": EVIDENCE}, 3.0),
    ("isa-claim", {"isc": "ISC-3", "claim": "The README documents the --pending flag.", "threshold": "present",
                   "how": "manual", "evidence": "looks right"}, 3.0),
    ("isa-ask", {"ask": "a `done <id>` command that marks a task as completed",
                 "line": "met — ISC-1", "evidence": EVIDENCE}, 3.0),
]


@unittest.skipUnless(LIVE, "live Jev calls: set ISA_FLOW_LIVE=1")
class TestJevLive(unittest.TestCase):
    def test_each_preset_served_in_time(self):
        os.environ["ISA_HOME"] = tempfile.mkdtemp(prefix="isa-jev-live-")
        os.environ.pop("ISA_JEV_BIN", None)
        from isa import jev
        self.assertTrue(jev.enabled(), "no `jev` on PATH")
        bad = []
        for preset, payload, deadline in CASES:
            r = jev.ask(preset, payload, deadline)
            print(f"{preset:10} served={r['served']} answer={r['answer']} {r['ms']} ms "
                  f"{'' if r['served'] else r['reason'] + ': ' + r['detail'][:120]}", file=sys.stderr)
            if not r["served"]:
                bad.append(f"{preset}: not served ({r['reason']}: {r['detail'][:200]})"
                           + (f" — {jev.message(r)}" if jev.message(r) else ""))
            elif r["ms"] > deadline * 1000:
                bad.append(f"{preset}: {r['ms']} ms over {deadline} s")
        self.assertFalse(bad, "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
