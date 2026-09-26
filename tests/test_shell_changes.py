"""Project changes made by `unknown` shell commands (heredoc scripts, `node -e`, builds).

Run: python3 -m unittest tests.test_shell_changes
"""
import json
import os
import shutil
import subprocess
import unittest

from tests.test_hooks import E1, HookCase


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                            GIT_COMMITTER_EMAIL="t@t"))


class ScriptCase(HookCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(os.path.join(self.proj, ".git"))
        git(self.proj, "init", "-q")
        with open(os.path.join(self.proj, "a.txt"), "w") as f:
            f.write("one\n")
        git(self.proj, "add", "a.txt")
        git(self.proj, "commit", "-qm", "init")
        self.n = 0

    def script(self, code):
        """Pre hook → run a Python heredoc in the project → Post hook, like a real Bash call."""
        self.n += 1
        cmd = f"python3 - <<'EOF'\n{code}\nEOF"
        tid = f"toolu_{self.n}"
        pre = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_use_id=tid)[1]
        subprocess.run(cmd, shell=True, cwd=self.proj, check=True, executable="/bin/bash")
        self.hook("PostToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_use_id=tid, tool_response={})
        return pre

    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)


class TestTrackedEdit(ScriptCase):
    def test_heredoc_edit_of_tracked_file_counts(self):
        self.write_isa(E1)
        self.script("open('a.txt', 'w').write('two\\n')")
        st = self.session()
        self.assertEqual(st["mutations"], 1)
        self.assertGreater(st["last_mutation"], 0)



class TestCreateDelete(ScriptCase):
    def test_new_untracked_file_counts(self):
        self.write_isa(E1)
        self.script("open('new.txt', 'w').write('x')")
        self.assertEqual(self.session()["mutations"], 1)

    def test_deleted_tracked_file_counts(self):
        self.write_isa(E1)
        self.script("import os; os.remove('a.txt')")
        self.assertEqual(self.session()["mutations"], 1)



class TestDirtyAgain(ScriptCase):
    def test_second_edit_of_dirty_file_counts(self):
        self.write_isa(E1)
        with open(os.path.join(self.proj, "a.txt"), "w") as f:
            f.write("dirty before\n")
        self.script("open('a.txt', 'w').write('dirty again\\n')")
        self.assertEqual(self.session()["mutations"], 1)

    def test_edit_inside_untracked_directory_counts(self):
        self.write_isa(E1)
        os.makedirs(os.path.join(self.proj, "newdir"))
        with open(os.path.join(self.proj, "newdir", "f.txt"), "w") as f:
            f.write("x")
        self.script("open('newdir/f.txt', 'w').write('y')")
        self.assertEqual(self.session()["mutations"], 1)



class TestNoChange(ScriptCase):
    def test_command_that_writes_nothing_does_not_count(self):
        self.write_isa(E1)
        with open(os.path.join(self.proj, "a.txt"), "w") as f:
            f.write("dirty before\n")  # a dirty file that the command only reads
        self.script("print(open('a.txt').read())")
        self.assertEqual(self.session()["mutations"], 0)

    def test_ignored_output_does_not_count(self):
        with open(os.path.join(self.proj, ".gitignore"), "w") as f:
            f.write("build/\n")
        git(self.proj, "add", ".gitignore")
        git(self.proj, "commit", "-qm", "ignore")
        self.write_isa(E1)
        self.script("import os; os.makedirs('build', exist_ok=True); open('build/out', 'w').write('x')")
        self.assertEqual(self.session()["mutations"], 0)



class TestNonGit(ScriptCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(os.path.join(self.proj, ".git"))  # a plain directory project

    def test_edit_in_plain_directory_counts(self):
        self.write_isa(E1)
        self.script("open('a.txt', 'w').write('changed\\n')")
        self.assertEqual(self.session()["mutations"], 1)

    def test_new_file_and_no_op_in_plain_directory(self):
        self.write_isa(E1)
        self.script("print('nothing')")
        self.assertEqual(self.session()["mutations"], 0)
        self.script("open('b.txt', 'w').write('x')")
        self.assertEqual(self.session()["mutations"], 1)



class TestFreshnessSeesScripts(ScriptCase):
    def test_script_edit_after_a_tick_makes_its_pass_stale(self):
        import sys
        from tests.test_evidence import FIXTURE, tick
        from tests.test_hooks import ISA
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
        from isa import evidence, lint
        flags = os.path.join(self.tmp, "flags")
        os.makedirs(flags)
        open(os.path.join(flags, "ok2"), "w").close()
        text = FIXTURE.replace("{d}", flags)
        path = self.write_isa(text)
        subprocess.run([sys.executable, ISA, "verify", path, "ISC-2"], cwd=self.proj, env=self.env,
                       check=True, capture_output=True)
        self.write_isa(tick(text, "ISC-2"), path)
        old = os.environ.get("ISA_HOME")
        os.environ["ISA_HOME"] = self.home
        try:
            parsed = lint.parse(tick(text, "ISC-2"), path)
            self.assertEqual(evidence.status(path, parsed, "ISC-2", since=self.session()["last_mutation"]), "proven")
            self.script("open('a.txt', 'w').write('edited by a script\\n')")
            self.assertEqual(evidence.status(path, parsed, "ISC-2", since=self.session()["last_mutation"]), "stale")
        finally:
            if old is None:
                os.environ.pop("ISA_HOME", None)
            else:
                os.environ["ISA_HOME"] = old
        # and closing on that stale pass is refused
        closed = tick(text, "ISC-2").replace("phase: build", "phase: complete")
        self.write_isa(closed, path)
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("ISC-2: its pass is older than the last project change", err)


class TestBudget(ScriptCase):
    def test_hook_pair_under_300ms_in_2000_file_repo(self):
        import time
        for n in range(2000):
            sub = os.path.join(self.proj, f"d{n % 40}")
            os.makedirs(sub, exist_ok=True)
            with open(os.path.join(sub, f"f{n}.txt"), "w") as f:
                f.write(str(n))
        git(self.proj, "add", "-A")
        git(self.proj, "commit", "-qm", "many")
        for n in range(20):  # some dirty state, as in real work
            with open(os.path.join(self.proj, f"d{n}", f"f{n}.txt"), "a") as f:
                f.write("x")
        self.write_isa(E1)
        cmd = "python3 - <<'EOF'\nprint(1)\nEOF"
        worst = 0.0
        for i in range(5):
            t = time.perf_counter()
            self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_use_id=f"b{i}")
            self.hook("PostToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_use_id=f"b{i}",
                      tool_response={})
            worst = max(worst, (time.perf_counter() - t) * 1000)
        print(f"\nworst pre+post pair: {worst:.0f} ms")
        self.assertLess(worst, 300)


if __name__ == "__main__":
    unittest.main()
