"""SPEC-v2 M4: problems still open when Stop lets a turn end are recorded as `blocked` (ledger rows keyed
by code; `no-isa` in session state), shown until a command sees them fixed, and block `isa close`.

Run: python3 -m unittest tests.test_blocked
"""
import json
import os
import subprocess
import sys
import unittest

from tests.test_commands import CommandCase
from tests.test_evidence import read, tick
from tests.test_hooks import E1, ISA, ROOT, setup_fake

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import evidence, problems  # noqa: E402

NO_ANTI = E1.replace("ISC-4: Anti:", "ISC-4:")


class BlockedCase(CommandCase):
    def let_through(self):
        """A turn with an open problem: Stop refuses once, then lets it end."""
        first = self.hook("Stop", stop_hook_active=False)
        second = self.hook("Stop", stop_hook_active=True)
        return first, second

    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)

    def blocked_rows(self, path):
        return [r for r in evidence.rows(path) if r.get("kind") == "blocked"]


class TestBlockedRow(BlockedCase):
    def test_second_stop_records(self):
        path = self.write_isa(NO_ANTI)
        self.post_edit_project()
        (c1, _, _), (c2, out, _) = self.let_through()
        self.assertEqual((c1, c2), (2, 0))
        self.assertIn("recorded as blocked", out.get("systemMessage", ""))
        [row] = self.blocked_rows(path)
        self.assertEqual(row["items"], [{"code": "lint-error", "isc": None}])
        self.assertEqual(problems.open_items(path), [("lint-error", None)])

    def test_first_refusal_records_nothing(self):
        path = self.write_isa(NO_ANTI)
        self.post_edit_project()
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[0], 2)
        self.assertEqual(self.blocked_rows(path), [])


class TestNoIsaBlocked(BlockedCase):
    def test_session_state_then_cleared(self):
        setup_fake(self, isa_gate=0.93)
        self.hook("UserPromptSubmit", prompt="Review utils.py for bugs and list each one with its line number.")
        self.let_through()
        self.assertEqual(self.session()["blocked_no_isa"], self.pid)
        _, out, _ = self.hook("SessionStart", source="resume")
        self.assertIn("ended without an ISA", self.ctx(out))
        self.write_isa(E1)
        self.assertNotIn("blocked_no_isa", self.session())


class TestShownOnResume(BlockedCase):
    def test_resume(self):
        self.write_isa(NO_ANTI)
        self.post_edit_project()
        self.let_through()
        _, out, _ = self.hook("SessionStart", source="resume")
        c = self.ctx(out)
        self.assertIn("Still blocked from an earlier turn", c)
        self.assertIn("the ISA fails lint", c)


class TestStatusShowsBlocked(BlockedCase):
    def test_json_and_text(self):
        path = self.write_isa(NO_ANTI)
        self.post_edit_project()
        self.let_through()
        run = lambda *a: subprocess.run([sys.executable, ISA, "status", "--session", self.sid, *a], env=self.env,
                                        text=True, capture_output=True).stdout
        v = json.loads(run("--json"))
        self.assertEqual((v["bound"], v["blocked"], v["mode"]),
                         (os.path.realpath(path), [{"code": "lint-error", "isc": None}], "on"))
        self.assertIn("blocked: lint-error", run())


class TestClearedByCommands(BlockedCase):
    def test_lint_clears(self):
        path = self.write_isa(NO_ANTI)
        self.post_edit_project()
        self.let_through()
        self.write_isa(E1, path)  # fixed
        rc, out = self.isa("lint", path)
        self.assertIn("cleared 1 blocked item", out)
        self.assertEqual(problems.open_items(path), [])
        [row] = [r for r in evidence.rows(path) if r.get("kind") == "unblocked"]
        self.assertEqual(row["items"], [{"code": "lint-error", "isc": None}])

    def test_verify_keeps_what_still_holds(self):
        path = self.write_isa(NO_ANTI)
        self.post_edit_project()
        self.let_through()
        rc, out = self.isa("verify", path)
        self.assertEqual(problems.open_items(path), [("lint-error", None)])


class TestMatchedByCode(BlockedCase):
    def test_reworded_problem_clears(self):
        path = self.write_isa(self.text)
        self.write_isa(tick(self.text, "ISC-2"), path)  # a tick behind the hooks' back: unproven
        self.post_edit_project()
        self.let_through()
        self.assertIn(("tick-unproven", "ISC-2"), problems.open_items(path))
        # an old engine wrote the same key with other words: only the key counts
        evidence.record(path, [{"v": 2, "t": 1.0, "kind": "blocked",
                                "items": [{"code": "tick-unproven", "isc": "ISC-2", "text": "old wording"}]}])
        self.flag("ok2")
        rc, out = self.verify(path, "ISC-2")
        self.assertEqual(rc, 0, out)
        self.assertNotIn(("tick-unproven", "ISC-2"), problems.open_items(path))


class TestCloseRefusesBlocked(BlockedCase):
    def test_close_with_open_item(self):
        v2 = self.text.replace("started: 2026-01-01T00:00:00Z", "started: 2026-10-02T09:00:00Z")
        path = self.write_isa(v2)
        self.flag("ok1")
        self.flag("ok2")
        self.verify(path)
        hand = read(path).replace("- [ ] ISC-3:", "- [x] ISC-3:")  # self-attested, ticked by hand
        self.write_isa(hand, path)
        self.post_edit_project()
        self.let_through()
        self.assertIn(("tick-unattested", "ISC-3"), problems.open_items(path))
        self.write_isa(read(path).rstrip("\n") + "\n- Goal: yes — done\n", path)
        before = read(path)
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 1, out)
        self.assertIn("still blocked from an earlier turn: ISC-3: ticked without `isa verify --attest`", out)
        self.assertEqual(read(path), before)


class TestHookNeverWritesIsa(BlockedCase):
    def test_bytes_and_mtime(self):
        path = self.write_isa(NO_ANTI)
        self.post_edit_project()
        before, mtime = read(path), os.stat(path).st_mtime_ns
        self.let_through()
        self.hook("SessionStart", source="resume")
        self.assertEqual((read(path), os.stat(path).st_mtime_ns), (before, mtime))


if __name__ == "__main__":
    unittest.main()
