"""`isa status`: the read-only view status lines consume. Run: python3 -m unittest tests.test_status"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISA = os.path.join(ROOT, "runtime", "bin", "isa")

FIXTURE = """---
task: "Status fixture"
slug: 20260101-000000_status
effort: E1
phase: execute
progress: 1/3
iteration: 2
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
---

## Goal

Exercise every ISC shape the status view has to skip.

## Criteria

- [x] ISC-1: first leaf, done.
- [ ] ISC-2: parent, never listed.
  - [ ] ISC-2.1: nested leaf, open.
- [ ] ISC-3: [DROPPED — see Decisions 2026-01-01]
- [ ] ISC-4: waived leaf.
- [ ] ISC-5: Anti: last leaf, open.

## Decisions

- 2026-01-01 00:00: waived: ISC-4 — user: "not needed"
"""


class StatusCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="isa-status-")
        self.env = dict(os.environ, ISA_HOME=self.home)
        self.isa = os.path.join(self.home, "proj", "20260101-000000_status", "ISA.md")
        os.makedirs(os.path.dirname(self.isa))
        with open(self.isa, "w") as f:
            f.write(FIXTURE)
        os.makedirs(os.path.join(self.home, "_state", "sessions"))
        with open(os.path.join(self.home, "_state", "sessions", "claude-s1.json"), "w") as f:
            json.dump({"bound": self.isa}, f)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def run_isa(self, *args):
        p = subprocess.run([sys.executable, ISA, "status", *args], env=self.env, text=True,
                           capture_output=True, timeout=20)
        return p.returncode, p.stdout, p.stderr

    def test_bound_fields(self):
        rc, out, _ = self.run_isa("--json", "--session", "s1")
        v = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertEqual((v["bound"], v["task"], v["effort"], v["phase"], v["progress"], v["iteration"]),
                         (self.isa, "Status fixture", "E1", "execute", "1/3", 2))

    def test_leaf_iscs_in_file_order_without_parents_dropped_or_waived(self):
        v = json.loads(self.run_isa("--json", "--session", "s1")[1])
        self.assertEqual([(i["id"], i["done"]) for i in v["iscs"]],
                         [("ISC-1", True), ("ISC-2.1", False), ("ISC-5", False)])
        self.assertEqual(v["iscs"][2]["text"], "Anti: last leaf, open.")

    def test_list_matches_progress_denominator(self):
        v = json.loads(self.run_isa("--json", "--session", "s1")[1])
        done = sum(i["done"] for i in v["iscs"])
        self.assertEqual(f"{done}/{len(v['iscs'])}", v["progress"])

    def test_unknown_session_is_null_not_error(self):
        rc, out, _ = self.run_isa("--json", "--session", "nope")
        self.assertEqual((rc, json.loads(out)), (0, {"bound": None}))

    def test_bound_file_deleted_is_null(self):
        os.remove(self.isa)
        self.assertEqual(json.loads(self.run_isa("--json", "--session", "s1")[1]), {"bound": None})

    def test_harness_selects_session_file(self):
        self.assertEqual(json.loads(self.run_isa("--json", "--harness", "pi", "--session", "s1")[1]),
                         {"bound": None})

    def test_text_mode_and_missing_session(self):
        rc, out, _ = self.run_isa("--session", "s1")
        self.assertEqual(rc, 0)
        self.assertIn("E1 execute 1/3 — Status fixture", out)
        self.assertIn("open: ISC-2.1, ISC-5", out)
        self.assertEqual(self.run_isa("--json")[0], 2)

    def test_read_only(self):
        before = sorted(os.walk(self.home))
        self.run_isa("--json", "--session", "s1")
        self.assertEqual(sorted(os.walk(self.home)), before)


if __name__ == "__main__":
    unittest.main()
