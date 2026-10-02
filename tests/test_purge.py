"""`isa purge-logs`: deletes debug log day files older than N days (default 7), and nothing else.

Run: python3 -m unittest tests.test_purge
"""
import datetime
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISA = os.path.join(ROOT, "runtime", "bin", "isa")


class TestPurge(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="isa-purge-")
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.logs = os.path.join(self.home, "_state", "logs")
        os.makedirs(self.logs)
        today = datetime.date.today()
        self.day = lambda n: (today - datetime.timedelta(days=n)).isoformat() + ".jsonl"
        for n in (0, 1, 7, 8, 30):
            self.touch(self.logs, self.day(n))
        self.touch(self.logs, "notes.txt")  # not a day file: never touched
        # state, not logs: never touched whatever its age
        for sub, name in (("evidence", "x-1.jsonl"), ("sessions", "claude-s.json"), ("prompts", "claude-s.jsonl")):
            self.touch(os.path.join(self.home, "_state", sub), name)
        self.touch(os.path.join(self.home, "_state"), "judge.jsonl")
        self.touch(os.path.join(self.home, "_state"), "errors.log")
        self.touch(os.path.join(self.home, "proj", "20200101-000000_old"), "ISA.md")
        old = 0  # 1970: an mtime-based purge would delete everything
        for dirpath, _dirs, files in os.walk(self.home):
            for f in files:
                os.utime(os.path.join(dirpath, f), (old, old))

    def touch(self, d, name):
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "w") as f:
            f.write("{}\n")

    def run_isa(self, *args):
        env = dict(os.environ, ISA_HOME=self.home)
        r = subprocess.run([sys.executable, ISA, "purge-logs", *args], capture_output=True, text=True, env=env)
        return r.returncode, r.stdout + r.stderr

    def files(self):
        return sorted(os.path.relpath(os.path.join(d, f), self.home) for d, _s, fs in os.walk(self.home) for f in fs)

    def test_deletes_only_old_logs(self):
        before = self.files()
        rc, out = self.run_isa()
        self.assertEqual(rc, 0, out)
        gone = sorted(set(before) - set(self.files()))
        self.assertEqual(gone, sorted(os.path.join("_state", "logs", self.day(n)) for n in (8, 30)))
        self.assertIn("deleted 2", out)

    def test_days_option(self):
        rc, out = self.run_isa("--days", "1")
        self.assertEqual(rc, 0, out)
        left = [f for f in os.listdir(self.logs) if f.endswith(".jsonl")]
        self.assertEqual(sorted(left), sorted([self.day(0), self.day(1)]))

    def test_dry_run(self):
        before = self.files()
        rc, out = self.run_isa("--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.files(), before)
        self.assertIn(self.day(8), out)
        self.assertIn(self.day(30), out)
        self.assertNotIn(self.day(7), out)
        self.assertIn("would delete 2", out)

    def test_no_log_dir(self):
        shutil.rmtree(self.logs)
        rc, out = self.run_isa()
        self.assertEqual(rc, 0, out)
        self.assertFalse(os.path.exists(self.logs))  # a purge never creates the folder

    def test_bad_days(self):
        rc, _out = self.run_isa("--days", "zero")
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
