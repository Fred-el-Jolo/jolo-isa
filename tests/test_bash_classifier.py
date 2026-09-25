"""Classifier table + randomized compositions. Run: python3 -m unittest tests.test_bash_classifier"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
from isa import classify  # noqa: E402

CWD = os.path.expanduser("~/dev/some-project")
READ = [
    "ls -la", "cat README.md", "git status", "git log --oneline -5", "git diff HEAD~1", "rg -n foo src/",
    "grep -rn TODO . | wc -l", "find . -name '*.py' -type f", "head -20 x | tail -5", "jq .version package.json",
    "echo hello", "pwd", "which python3", "sed -n 1,20p file", "awk '{print $1}' f", "diff a b",
    "git show HEAD:README.md", "gh pr view 12", "gh api repos/o/r/pulls", "python3 --version",
    "echo x > /dev/null 2>&1", "cat f 2>/dev/null", "ls > /tmp/listing.txt", "date +%F", "isa ls",
    "cd src && ls", "FOO=1 printenv FOO", "timeout 5 cat f", "tree -L 2", "wc -l < f", "stat f",
    "git branch", "git branch -a", "git remote -v", "git config --get user.name", "git stash list",
    "diff <(ls a) <(ls b)", "cp -r /tmp/a /tmp/b", "mkdir -p /tmp/x/y", "rm -rf /tmp/scratch",
    "mkdir -p ~/.isa/dev-x/1_a", "cat f | tee /tmp/copy", "touch /tmp/stamp", "cat <<'EOF'\nrm -rf /\nEOF", "sort f | uniq -c | sort -rn | head",
]
WRITE = [
    "rm -rf build", "mv a b", "cp a b", "mkdir -p x", "touch f", "echo x > out.txt", "echo x >> log.md",
    "sed -i s/a/b/ f", "git commit -m msg", "git push", "git add -A", "git checkout -b feat", "npm install",
    "pip install requests", "find . -name '*.pyc' -delete", "tee out.txt", "chmod +x run.sh",
    "cat <<EOF > notes.md\nhello\nEOF", "curl -o x.tgz https://e.x/x.tgz", "sudo apt install jq",
    "git reset --hard", "make", "ls && rm x", "cat f | tee copy.txt", "xargs rm < list",
    "git branch -D old", "cp /tmp/a src/a", "mv src/a /tmp/a", "mktemp -p .", "git tag v1", "git stash", "tar -xzf a.tgz", "ln -s a b",
]
UNKNOWN = [
    "python3 script.py", "node build.js", "./run.sh", "bash deploy.sh", "rg foo $(cat list)",
    "gh pr create --fill", "curl -X POST https://api.x/y", "gh api -X DELETE repos/o/r", "pytest",
    "some-new-tool --flag", "awk '{print > \"out\"}' f", "git fetch", "cat x | python3 -c 'print(1)'",
]


class TestTable(unittest.TestCase):
    def check(self, cmds, want):
        for c in cmds:
            got, _ = classify.bash(c, CWD)
            self.assertEqual(got, want, c)

    def test_read(self):
        self.check(READ, "read")

    def test_write(self):
        self.check(WRITE, "write")

    def test_unknown(self):
        self.check(UNKNOWN, "unknown")

    def test_isa_redirect(self):
        k, isa = classify.bash("cat > ~/.isa/dev-x/1_a/ISA.md <<'EOF'\nx\nEOF", CWD)
        self.assertEqual((k, len(isa)), ("read", 1))

    def test_tools(self):
        c = lambda t, ti=None: classify.classify(t, ti or {}, CWD)[0]
        self.assertEqual(c("Write", {"file_path": "x.py"}), "write")
        self.assertEqual(c("Write", {"file_path": "/tmp/x.py"}), "read")
        self.assertEqual(c("edit", {"path": "src/a.ts"}), "write")
        self.assertEqual(c("Read", {"file_path": "x"}), "read")
        self.assertEqual(c("mcp__claude_ai_Gmail__send_message"), "unknown")
        self.assertEqual(c("mcp__claude_ai_Claude_Docs__read"), "read")
        self.assertEqual(c("SomeFutureTool"), "unknown")


class TestCompositions(unittest.TestCase):
    """∀ composition: the result is the worst part (write > unknown > read)."""

    def test_random(self):
        rnd = random.Random(1234)
        order = {"read": 0, "unknown": 1, "write": 2}
        pools = [(c, "read") for c in READ if "\n" not in c and "<(" not in c] + \
                [(c, "write") for c in WRITE if "\n" not in c] + \
                [(c, "unknown") for c in UNKNOWN if "$(" not in c]
        for _ in range(500):
            parts = rnd.sample(pools, rnd.randint(1, 4))
            joined = parts[0][0]
            for c, _k in parts[1:]:
                joined += rnd.choice([" ; ", " && ", " || ", " | "]) + c
            want = max((k for _, k in parts), key=order.get)
            got, _ = classify.bash(joined, CWD)
            self.assertEqual(got, want, joined)


if __name__ == "__main__":
    unittest.main()
