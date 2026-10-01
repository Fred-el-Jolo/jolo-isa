"""End-of-turn check per the ISA method, and #3 (ISA ↔ session ↔ touched projects).
Run: python3 -m unittest tests.test_seamless_projects"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_hooks import E1, HookCase, ISA, ROOT

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import evidence, state  # noqa: E402


def isa_text(marker, ticked=False, closed=False, probe=None):
    box = "x" if ticked or closed else " "
    probe = probe or f"test -f {marker}"
    text = f"""---
task: "Keep the marker file in place"
slug: 20260101-000000_t
effort: E2
phase: {'complete' if closed else 'build'}
progress: {'2/2' if ticked or closed else '0/2'}
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
---

## Problem

The marker must exist.

## Goal

The marker file exists and is not empty.

## Criteria

- [{box}] ISC-1: The marker file exists in the project root folder.
- [{box}] ISC-2: Anti: the marker file is never an empty file here.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  check: marker exists
  threshold: exit 0
  tool: {probe}

- isc: ISC-2
  type: bash
  check: marker not empty
  threshold: exit 0
  tool: test -s {marker}
```
"""
    if closed:
        text += """
## Verification

- ISC-1: `isa verify` PASS — marker present
- ISC-2: `isa verify` PASS — marker not empty
- Goal: yes — the marker exists and is not empty
"""
    return text


class SeamlessCase(HookCase):
    def setUp(self):
        super().setUp()
        self.marker = os.path.join(self.proj, "marker.txt")
        with open(self.marker, "w") as f:
            f.write("here\n")
        os.environ["ISA_HOME"] = self.home

    def tearDown(self):
        os.environ.pop("ISA_HOME", None)
        super().tearDown()

    def verify(self, path):
        return subprocess.run([sys.executable, ISA, "verify", path], cwd=self.proj, env=self.env, text=True,
                              capture_output=True, timeout=60)

    def ready(self, closed=False, probe=None):
        """verify → tick (→ close) → one project change after the verify."""
        path = self.write_isa(isa_text(self.marker, probe=probe))
        self.assertEqual(self.verify(path).returncode, 0)
        self.write_isa(isa_text(self.marker, ticked=True, closed=closed, probe=probe), path)
        self.post_edit_project()
        return path


class TestStopPerMethod(SeamlessCase):
    """The end-of-turn check follows the method: it reads the ISA, the ledger and session state only."""

    def test_stop_runs_no_probe(self):
        ran = os.path.join(self.proj, "probe-ran")
        self.ready(probe=f"test -f {self.marker} && touch {ran}")
        os.remove(ran)
        self.hook("Stop", stop_hook_active=False)
        self.assertFalse(os.path.exists(ran))

    def test_all_ticked_asks_to_close(self):
        path = self.write_isa(isa_text(self.marker))
        self.assertEqual(self.verify(path).returncode, 0)
        self.write_isa(isa_text(self.marker, ticked=True), path)  # every ISC ticked, phase still build
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("close it", err)
        self.assertEqual(self.hook("Stop", stop_hook_active=True)[0], 0)

    def test_mid_work_stale_is_quiet(self):
        text = isa_text(self.marker).replace(
            "- [ ] ISC-2: Anti:", "- [ ] ISC-3: The marker holds exactly one line of text.\n- [ ] ISC-2: Anti:")
        text = text.replace("progress: 0/2", "progress: 0/3").replace(
            "```\n", "\n- isc: ISC-3\n  type: manual\n  check: one line\n  threshold: 1\n  tool: read it\n```\n", 1)
        path = self.write_isa(text)
        self.assertEqual(self.verify(path).returncode, 0)
        ticked = text.replace("- [ ] ISC-1:", "- [x] ISC-1:").replace("- [ ] ISC-2:", "- [x] ISC-2:")
        self.write_isa(ticked.replace("progress: 0/3", "progress: 2/3"), path)
        self.post_edit_project()  # the passes are now older than the last change; ISC-3 still open
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual((code, err), (0, ""))

    def test_stop_never_writes_isa(self):
        path = self.write_isa(isa_text(self.marker))
        self.assertEqual(self.verify(path).returncode, 0)
        self.write_isa(isa_text(self.marker, ticked=True), path)
        with open(path, "rb") as f:
            before = f.read()
        mtime = os.path.getmtime(path)
        self.hook("Stop", stop_hook_active=False)  # blocks: all ticked, not closed
        self.pid = "p2"
        self.post_edit_project()
        self.hook("Stop", stop_hook_active=False)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(os.path.getmtime(path), mtime)


class TestProjects(HookCase):
    def setUp(self):
        super().setUp()
        self.other = tempfile.mkdtemp(prefix="isa-other-", dir=os.path.expanduser("~/.cache"))
        os.makedirs(os.path.join(self.other, ".git"))
        os.environ["ISA_HOME"] = self.home

    def tearDown(self):
        os.environ.pop("ISA_HOME", None)
        shutil.rmtree(self.other, ignore_errors=True)
        super().tearDown()

    def key(self, d):
        return subprocess.run([sys.executable, ISA, "where"], cwd=d, env=self.env, text=True,
                              capture_output=True).stdout.split()[2]

    def change_other(self):
        f = os.path.join(self.other, "b.py")
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": f, "content": "x"}, tool_response={})

    def test_other_repo_change_indexed(self):
        path = self.write_isa(E1)
        self.change_other()
        with open(os.path.join(os.path.dirname(path), ".projects.json")) as f:
            keys = json.load(f)
        self.assertIn(self.key(self.other), keys)

    def test_ls_in_other_project_lists_isa(self):
        self.write_isa(E1)
        self.change_other()
        out = subprocess.run([sys.executable, ISA, "ls"], cwd=self.other, env=self.env, text=True,
                             capture_output=True).stdout
        self.assertIn("20260101-000000_t", out)

    def test_suggestion_follows_target_file(self):
        _, out, _ = self.hook("PreToolUse", tool_name="Write",
                              tool_input={"file_path": os.path.join(self.other, "b.py"), "content": "x"})
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("/" + self.key(self.other) + "/", reason)

    def test_non_git_temp_cwd_ignored(self):
        self.write_isa(E1)
        scratch = tempfile.mkdtemp(prefix="isa-scratch-")
        try:
            cmd = "python3 -c \"open('new.txt','w').write('x')\""
            self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd}, cwd=scratch, tool_use_id="t1")
            subprocess.run(cmd, shell=True, cwd=scratch)
            self.hook("PostToolUse", tool_name="Bash", tool_input={"command": cmd}, cwd=scratch, tool_use_id="t1",
                      tool_response={})
            with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
                self.assertEqual(json.load(f)["mutations"], 0)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_ls_all_shows_home(self):
        p = os.path.join(self.home, "_home", "20260101-000000_h", "ISA.md")
        os.makedirs(os.path.dirname(p))
        with open(p, "w") as f:
            f.write(E1)
        out = subprocess.run([sys.executable, ISA, "ls", "--all"], cwd=self.proj, env=self.env, text=True,
                             capture_output=True).stdout
        self.assertIn("_home/", out)


if __name__ == "__main__":
    unittest.main()
