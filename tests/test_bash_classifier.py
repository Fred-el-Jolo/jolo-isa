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
    "echo x > /dev/null 2>&1", "cat f 2>/dev/null", "ls > /tmp/listing.txt", "date +%F",
    "cd src && ls", "FOO=1 printenv FOO", "timeout 5 cat f", "tree -L 2", "wc -l < f", "stat f",
    "git branch", "git branch -a", "git remote -v", "git config --get user.name", "git stash list",
    "diff <(ls a) <(ls b)", "cp -r /tmp/a /tmp/b", "mkdir -p /tmp/x/y", "rm -rf /tmp/scratch",
    "cat f | tee /tmp/copy", "touch /tmp/stamp", "cat <<'EOF'\nrm -rf /\nEOF", "sort f | uniq -c | sort -rn | head",
    "cat ~/.isa/dev-x/1_a/ISA.md", "grep -n ISC ~/.isa/dev-x/1_a/ISA.md",
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
    "echo `rm x`", "echo \"$(rm x)\"", "grep 'a' `cat list`", "ls \"`pwd`\"",
]
GUARDED = [
    "cat > ~/.isa/dev-x/1_a/ISA.md <<'EOF'\nx\nEOF", "mkdir -p ~/.isa/dev-x/1_a", "rm -rf ~/.isa/_state",
    "sed -i s/a/b/ docs/2026-10-07-x-01-spec.md", "echo x >> docs/2026-10-07-x-02-plan.md",
    "python3 -c \"open('/home/u/.isa/x/ISA.md', 'w')\"".replace("/home/u", os.path.expanduser("~")),
    "python3 - <<'EOF'\nopen('docs/2026-10-07-x-01-spec.md', 'w').write('x')\nEOF",
    "cd ~/.isa/dev-x && ./fix.sh", "node -e \"require('fs').writeFileSync('docs/2026-10-07-x-02-plan.md', '')\"",
]
MENTIONS = [  # naming an ISA entity in a known command's text is no write onto it
    ("git commit -F - <<'EOF'\nMove ~/.isa aside; see docs/2026-10-07-x-01-spec.md\nEOF", "write"),
    ("git commit -m 'the writers of ~/.isa'", "write"),
    ("git add docs/2026-10-07-x-01-spec.md", "write"),
    ("echo 'see ~/.isa/dev-x/1_a/ISA.md'", "read"),
    ("grep -c ISC ~/.isa/dev-x/1_a/ISA.md | sort", "read"),
]
ISA_CMDS = ["isa ls", "isa write ~/.isa/dev-x/1_a/ISA.md Goal <<'EOF'\nThe goal.\nEOF", "isa verify ~/.isa/x/ISA.md"]


class TestTable(unittest.TestCase):
    def check(self, cmds, want):
        for c in cmds:
            self.assertEqual(classify.bash(c, CWD), want, c)

    def test_read(self):
        self.check(READ, "read")

    def test_write(self):
        self.check(WRITE, "write")

    def test_unknown(self):
        self.check(UNKNOWN, "unknown")

    def test_guarded(self):
        self.check(GUARDED, "guarded")

    def test_isa_cmds(self):
        self.check(ISA_CMDS, "isa-cmd")

    def test_mentions_are_not_writes(self):
        for c, want in MENTIONS:
            self.assertEqual(classify.bash(c, CWD), want, c)

    def test_quoted_substitution_is_text(self):
        self.check(["grep -n 'no `root`' SPEC.md", "rg -n 'uses `isa verify`' docs/", "grep -c '$(' f",
                    "grep 'a `b`' f && grep -n 'x' g", "echo 'it''s `fine`'"], "read")

    def test_tools(self):
        c = lambda t, ti=None: classify.classify(t, ti or {}, CWD)  # noqa: E731
        self.assertEqual(c("Write", {"file_path": "x.py"}), "write")
        self.assertEqual(c("Write", {"file_path": "/tmp/x.py"}), "read")
        self.assertEqual(c("edit", {"path": "src/a.ts"}), "write")
        self.assertEqual(c("Read", {"file_path": "x"}), "read")
        self.assertEqual(c("Write", {"file_path": "~/.isa/dev-x/1_a/ISA.md"}), "guarded")
        self.assertEqual(c("Edit", {"file_path": "docs/2026-10-07-x-01-spec.md"}), "guarded")
        self.assertEqual(c("Write", {"file_path": "docs/spec/x.md"}), "write")
        self.assertEqual(c("mcp__claude_ai_Gmail__send_message"), "unknown")
        self.assertEqual(c("mcp__claude_ai_Claude_Docs__read"), "read")
        self.assertEqual(c("SomeFutureTool"), "unknown")


class TestCompositions(unittest.TestCase):
    """∀ composition: the result is the worst part (write > unknown > read)."""

    def test_random(self):
        rnd = random.Random(1234)
        order = {"read": 0, "unknown": 1, "write": 2}
        pools = [(c, "read") for c in READ if "\n" not in c and "<(" not in c and ".isa" not in c] + \
                [(c, "write") for c in WRITE if "\n" not in c] + \
                [(c, "unknown") for c in UNKNOWN if "$(" not in c]
        for _ in range(500):
            parts = rnd.sample(pools, rnd.randint(1, 4))
            joined = parts[0][0]
            for c, _k in parts[1:]:
                joined += rnd.choice([" ; ", " && ", " || ", " | "]) + c
            want = max((k for _, k in parts), key=order.get)
            self.assertEqual(classify.bash(joined, CWD), want, joined)


class TestReviewFixes(unittest.TestCase):
    """docs/2026-10-08-review-fixes-01-spec.md S1 and S8."""

    def check(self, cmds, want):
        for c in cmds:
            self.assertEqual(classify.bash(c, CWD), want, c)

    def test_home_paths(self):
        self.check(["echo x > $HOME/.isa/p/x/ISA.md", "echo x > ${HOME}/.isa/p/x/ISA.md",
                    "cp /tmp/a $HOME/.isa/p/x/ISA.md", "rm -rf $HOME/.isa", "sed -i s/a/b/ $HOME/.isa/p/x/ISA.md",
                    "echo x | tee $HOME/.isa/p/x/ISA.md", 'cp /tmp/a "$HOME/.isa/p/x/ISA.md"'], "guarded")

    def test_cd_targets(self):
        self.check(["cd ~/.isa/p/x && rm ISA.md", "cd ~/.isa/p/x && echo hi > ISA.md",
                    "cd docs && cp /tmp/a 2026-10-06-x-01-spec.md", "cd $HOME/.isa/p ; mv a b"], "guarded")

    def test_git_dir(self):
        self.check(["git -C ~/.isa commit -am x", "cd ~/.isa && git add -A", "git --git-dir=$HOME/.isa/.git add x"],
                   "guarded")
        self.assertEqual(classify.bash("git -C ~/.isa log", CWD), "read")
        self.assertEqual(classify.bash("git -C src commit -m x", CWD), "write")

    def test_code_home_lookup(self):
        self.check(["python3 -c \"import os; open(os.environ['HOME']+'/.isa/x','w')\"",
                    "python3 -c \"import os; os.remove(os.path.join(os.environ['HOME'], '.isa', 'x'))\""], "guarded")

    def test_cd_elsewhere(self):
        self.assertEqual(classify.bash("cd src && rm x", CWD), "write")
        self.assertEqual(classify.bash("cd /tmp && rm x", CWD), "read")

    def test_isa_substitution(self):
        self.check(['isa show "$(isa ls | head -1)"', 'isa new x --tier E1 && isa show "$(isa where | tail -1)"',
                    'isa show "$(ls -d ~/.isa/dev-x/* | tail -1)/ISA.md"'], "isa-cmd")

    def test_other_substitution(self):
        self.assertEqual(classify.bash("rg foo $(cat list)", CWD), "unknown")
        self.assertNotEqual(classify.bash('isa show "$(rm x)"', CWD), "isa-cmd")
        self.assertNotEqual(classify.bash('isa show "$(python3 x.py)"', CWD), "isa-cmd")
        self.assertNotEqual(classify.bash('isa show "$(echo $(rm x))"', CWD), "isa-cmd")


if __name__ == "__main__":
    unittest.main()
