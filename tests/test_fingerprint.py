"""SPEC-v2 M3: the probe root, the tree fingerprint, and freshness as the close's job.

Run: python3 -m unittest tests.test_fingerprint
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.test_commands import CommandCase
from tests.test_evidence import read
from tests.test_hooks import ROOT
from tests.test_shell_changes import git

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import evidence, fingerprint, lint  # noqa: E402


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="isa-fp-test-")
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        git(self.repo, "init", "-q")
        self.write("a.txt", "one\n")
        self.write(".gitignore", "build/\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "init")
        self.env = mock.patch.dict(os.environ, {"ISA_HOME": os.path.join(self.tmp, "isa-home")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text, mode="w"):
        p = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, mode) as f:
            f.write(text)

    def fp(self):
        return fingerprint.of(self.repo)


class TestGitContent(RepoCase):
    def test_any_change_any_tool(self):
        base = self.fp()
        self.assertTrue(base.startswith("git:"))
        self.write("a.txt", "two\n")  # an Edit
        edited = self.fp()
        self.assertNotEqual(edited, base)
        subprocess.run("python3 - <<'EOF'\nopen('new.py', 'w').write('x = 1\\n')\nEOF", shell=True,
                       cwd=self.repo, check=True, executable="/bin/bash")  # a heredoc script, untracked file
        scripted = self.fp()
        self.assertNotEqual(scripted, edited)
        subprocess.run([sys.executable, "-c", "import pathlib; p = pathlib.Path('new.py'); "
                        "p.write_text(p.read_text().replace('x = 1', 'x  =  1'))"], cwd=self.repo, check=True)
        self.assertNotEqual(self.fp(), scripted)  # a formatter-style rewrite
        self.assertEqual(sorted(fingerprint.changed_paths(self.repo, base, self.fp())), ["a.txt", "new.py"])


class TestGitStable(RepoCase):
    def test_commit_and_ignored(self):
        self.write("a.txt", "two\n")
        before = self.fp()
        git(self.repo, "commit", "-qam", "content unchanged by the commit itself")
        self.assertEqual(self.fp(), before)
        self.write("build/out.bin", "generated")
        self.assertEqual(self.fp(), before)

    def test_same_tree_twice(self):
        self.assertEqual(self.fp(), self.fp())


class TestIndexUntouched(RepoCase):
    def test_real_index_bytes(self):
        self.write("a.txt", "two\n")
        self.write("untracked.txt", "u")
        idx = os.path.join(self.repo, ".git", "index")
        with open(idx, "rb") as f:
            before = f.read()
        self.fp()
        with open(idx, "rb") as f:
            self.assertEqual(f.read(), before)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True,
                                text=True).stdout
        self.assertIn("?? untracked.txt", status)  # still untracked: nothing was staged for real


class TestIsaHomePlacement(RepoCase):
    def test_inside_is_excluded(self):
        inside = os.path.join(self.repo, ".isa-home")
        with mock.patch.dict(os.environ, {"ISA_HOME": inside}):
            base = self.fp()
            self.write(".isa-home/k/20260101-000000_t/ISA.md", "x")
            self.assertEqual(self.fp(), base)
            self.write("a.txt", "two\n")
            self.assertNotEqual(self.fp(), base)

    def test_outside_works(self):
        base = self.fp()
        os.makedirs(os.path.join(self.tmp, "isa-home", "k"), exist_ok=True)
        self.assertEqual(self.fp(), base)
        self.write("a.txt", "two\n")
        self.assertNotEqual(self.fp(), base)

    def test_subdirectory_root(self):
        self.write("sub/x.txt", "x")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "sub")
        sub = os.path.join(self.repo, "sub")
        base = fingerprint.of(sub)
        self.write("a.txt", "changed outside sub\n")
        self.assertEqual(fingerprint.of(sub), base)
        self.write("sub/x.txt", "y")
        self.assertNotEqual(fingerprint.of(sub), base)


class TestNonGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="isa-fp-plain-", dir=os.path.expanduser("~/.cache"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_touch_and_cap(self):
        with open(os.path.join(self.tmp, "a.txt"), "w") as f:
            f.write("a")
        base = fingerprint.of(self.tmp)
        self.assertTrue(base.startswith("walk:"))
        st = os.stat(os.path.join(self.tmp, "a.txt"))
        os.utime(os.path.join(self.tmp, "a.txt"), ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))  # a touch
        self.assertNotEqual(fingerprint.of(self.tmp), base)
        with mock.patch.object(fingerprint, "WALK_CAP", 3):
            for n in range(5):
                open(os.path.join(self.tmp, f"f{n}"), "w").close()
            self.assertEqual(fingerprint.of(self.tmp), fingerprint.UNCOMPUTABLE)

    def test_home_is_never_walked(self):
        self.assertEqual(fingerprint.of(os.path.expanduser("~")), fingerprint.UNCOMPUTABLE)


class GitCommandCase(CommandCase):
    """CommandCase with a real git project."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(os.path.join(self.proj, ".git"))
        git(self.proj, "init", "-q")
        with open(os.path.join(self.proj, "a.txt"), "w") as f:
            f.write("one\n")
        git(self.proj, "add", "-A")
        git(self.proj, "commit", "-qm", "init")


class TestRowsCarryFingerprint(GitCommandCase):
    def test_rows(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        [row] = [r for r in evidence.rows(path) if r.get("kind") == "verify"]
        self.assertEqual(row["fingerprint"], fingerprint.of(self.proj))
        self.assertEqual(row["root"], ".")  # a repo ISA's ledger stores paths repo-relative (§ 13.3)
        v1 = {"t": 1.0, "isc": "ISC-1", "tool_sha": "x", "ok": True}  # a v1 row: no `v`, no fingerprint
        self.assertIsNone(evidence.row_fingerprint(v1))
        self.assertEqual(evidence.row_fingerprint(row), row["fingerprint"])


class TestProbeChangesTree(GitCommandCase):
    def test_reported_recorded_and_blocks_close(self):
        text = self.text.replace(f"tool: test -f {self.d}/ok2", "tool: echo x >> probe-output.txt")
        path = self.write_isa(text)
        self.flag("ok1")
        rc, out = self.verify(path)
        self.assertIn("probe changed the tree", out)
        self.assertIn("probe-output.txt", out)
        [ch] = [r for r in evidence.rows(path) if r.get("kind") == "changed"]
        self.assertEqual(ch["paths"], ["probe-output.txt"])
        self.isa("verify", path, "ISC-3", "--attest", "fine")
        self.write_isa(read(path).rstrip("\n") + "\n- Goal: yes — done\n", path)
        before = read(path)
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 1, out)
        self.assertIn("a probe changed the tree", out)
        self.assertEqual(read(path), before)


class TestMultiRoot(GitCommandCase):
    def test_entry_root(self):
        other = tempfile.mkdtemp(prefix="isa-other-", dir=os.path.expanduser("~/.cache"))
        self.addCleanup(shutil.rmtree, other, True)
        git(other, "init", "-q")
        with open(os.path.join(other, "marker.txt"), "w") as f:
            f.write("here")
        rel = os.path.relpath(other, os.path.expanduser("~"))
        text = self.text.replace(f"  tool: test -f {self.d}/ok2", f"  root: {rel}\n  tool: test -f marker.txt")
        path = self.write_isa(text)
        rc, out = self.verify(path, "ISC-2")
        self.assertEqual(rc, 0, out)
        [row] = [r for r in evidence.rows(path) if r.get("kind") == "verify"]
        self.assertEqual((row["root"], row["cwd"]), (os.path.realpath(other), os.path.realpath(other)))
        self.assertEqual(row["fingerprint"], fingerprint.of(other))


class TestCompleteNeedsClose(GitCommandCase):
    def test_hand_set_complete(self):
        v2 = self.text.replace("started: 2026-01-01T00:00:00Z", "started: 2026-10-02T09:00:00Z")
        self.flag("ok1")
        self.flag("ok2")
        path = self.write_isa(v2)
        self.verify(path)
        self.isa("verify", path, "ISC-3", "--attest", "fine")
        closed = read(path).replace("phase: build", "phase: complete").rstrip("\n") + "\n- Goal: yes — done\n"
        self.write_isa(closed, path)  # written behind the hooks' back: only `isa close` writes complete
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("`phase: complete` was not written by `isa close`", err)


class TestNoTimestampFreshness(GitCommandCase):
    def test_closed_isa_not_refused_over_timestamps(self):
        self.flag("ok1")
        self.flag("ok2")
        path = self.write_isa(self.text)
        self.verify(path)
        self.isa("verify", path, "ISC-3", "--attest", "fine")
        self.write_isa(read(path).rstrip("\n") + "\n- Goal: yes — done\n", path)
        self.assertEqual(self.isa("close", path)[0], 0)
        self.post_edit_project()  # a change after the close: refused live by the finished-ISA gate
        self.pid = "p2"
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertNotIn("older than the last project change", err)
        self.assertEqual(code, 0, err)


class TestAbsoluteCdWarning(unittest.TestCase):
    def test_warning(self):
        from tests.test_evidence import FIXTURE
        text = FIXTURE.replace("{d}", "/x").replace("tool: test -f /x/ok2", "tool: cd /home/u/p && test -f ok2")
        r = lint.lint("ISA.md", "articulation", text=text)
        self.assertEqual(r.errors, 0)
        self.assertTrue(any(lvl == "WARN" and "starts with `cd /…`" in m for lvl, m in r.items))
        clean = lint.lint("ISA.md", "articulation", text=FIXTURE.replace("{d}", "/x"))
        self.assertFalse(any("cd /" in m for _, m in clean.items))


if __name__ == "__main__":
    unittest.main()
