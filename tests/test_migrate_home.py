"""Plan P1 (docs/plan/2026-10-06-local-isas-spec-driven.md, spec § A.5): `isa migrate --home` moves a repo's
task ISAs from `<repo>/.isa/` back to `~/.isa/<project-key>/`, with their ledgers, and removes the git filter.

Real git repos; the filter runs this repo's runtime. No network.
Run: python3 -m unittest tests.test_migrate_home
"""
import base64
import hashlib
import json
import os
import re
import shutil
import sys

from tests.test_evidence import read
from tests.test_hooks import ROOT, TEST_KEY
from tests.test_m12 import TASK, RepoCase

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import commands, crypt, evidence, fingerprint, state  # noqa: E402

COMMIT = 'git rm -r --cached .isa && git add .gitattributes && git commit -m "Move task ISAs out of git"'
LEDGER_REF = re.compile(r"\(ledger: ([0-9a-f]{10})\)")


class HomeCase(RepoCase):
    """A repo holding two committed task ISAs in the SPEC-v2 § 13 layout that P2 found in the four repos:
    `shout` (root `.`, verified, with an ephemeral slice) and `sub` (root `sub`)."""

    def setUp(self):
        super().setUp()
        self.put("ok1", "")
        self.put("ok2", "")
        self.put("sub/keep.txt", "x\n")
        home_a = self.task(TASK.replace("root: .", f"root: {os.path.realpath(self.proj)}"))
        rc, out = self.isa("verify", home_a)
        self.assertEqual(rc, 0, out)
        home_b = self.new_isa("sub")
        with open(home_b, "w") as f:
            f.write(TASK.replace("root: .", "root: sub")
                    .replace("slug: 20260101-000000_t", f"slug: {self.slug(home_b)}"))
        self.isa_a, self.isa_b = self.to_repo(home_a), self.to_repo(home_b)
        self.put("_ephemeral/feat.md", "# slice\n", base=os.path.dirname(self.isa_a))
        crypt.setup_repo(self.proj, out=lambda *_: None)
        r = self.commit_all()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.key = state.project_key(self.proj)
        self.dest = os.path.join(self.home, self.key)

    def to_repo(self, path):
        """`isa new` writes to ISA_HOME now (P3): move the ISA into `<repo>/.isa/<slug>/` as § 13 kept it —
        `root: .`, the ledger beside it with repo-relative paths and the asks as keyed HMACs, ids unchanged."""
        repo = os.path.realpath(self.proj)
        dest = os.path.join(repo, ".isa", self.slug(path), "ISA.md")
        rows, led = evidence.rows(path), evidence.ledger_path(path)
        os.makedirs(os.path.dirname(os.path.dirname(dest)), exist_ok=True)
        shutil.move(os.path.dirname(path), os.path.dirname(dest))
        if os.path.exists(led):
            os.remove(led)
        k = base64.b64decode(TEST_KEY)
        with open(os.path.join(os.path.dirname(dest), "evidence.jsonl"), "w") as f:
            for row in rows:
                for kk in ("root", "cwd"):
                    if isinstance(row.get(kk), str) and os.path.isabs(row[kk]):
                        row[kk] = os.path.relpath(row[kk], repo)
                if row.get("kind") == "asks":
                    row["asks"] = [crypt.tag(str(a), k) for a in row["asks"]]
                f.write(json.dumps(row) + "\n")
        with open(dest) as f:
            text = f.read()
        with open(dest, "w") as f:
            f.write(text.replace(f"root: {repo}\n", "root: .\n"))
        commands._rebind({os.path.realpath(path): os.path.realpath(dest)})
        return dest

    def slug(self, path):
        return os.path.basename(os.path.dirname(path))

    def moved(self, path):
        return os.path.join(self.dest, self.slug(path), "ISA.md")

    def migrate(self, *args, env=None):
        saved = self.env
        if env is not None:
            self.env = env
        try:
            return self.isa("migrate", "--home", *args)
        finally:
            self.env = saved

    def listing(self, out):
        return [x for x in out.splitlines() if x.startswith(("move ", "skip "))]


class TestMove(HomeCase):
    def test_every_slug_folder_moves_home(self):
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        for p in (self.isa_a, self.isa_b):
            self.assertTrue(os.path.isfile(self.moved(p)), out)
            self.assertFalse(os.path.exists(os.path.dirname(p)))
        self.assertTrue(os.path.isfile(os.path.join(self.dest, self.slug(self.isa_a), "_ephemeral", "feat.md")))
        self.assertEqual(os.listdir(os.path.join(self.proj, ".isa")) if os.path.isdir(
            os.path.join(self.proj, ".isa")) else [], [])
        self.assertEqual(len(self.listing(out)), 2, out)


class TestLedger(HomeCase):
    def test_ledger_moves_to_home_name_absolute_ids_kept(self):
        old_ledger = os.path.join(os.path.dirname(self.isa_a), "evidence.jsonl")
        old_rows = [json.loads(x) for x in read(old_ledger).splitlines()]
        self.assertTrue(any(r.get("root") == "." for r in old_rows))
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        new = self.moved(self.isa_a)
        real = os.path.realpath(new)
        want = os.path.join(self.home, "_state", "evidence",
                            f"{self.slug(new)}-{hashlib.sha256(real.encode()).hexdigest()[:12]}.jsonl")
        self.assertEqual(evidence.ledger_path(new), want)
        self.assertTrue(os.path.isfile(want), out)
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(new), "evidence.jsonl")))
        rows = [json.loads(x) for x in read(want).splitlines()]
        self.assertEqual([r["id"] for r in rows], [r["id"] for r in old_rows])
        proj = os.path.realpath(self.proj)
        for r in rows:
            for k in ("root", "cwd"):
                if k in r:
                    self.assertEqual(r[k], proj, r)
        refs = LEDGER_REF.findall(read(new))
        self.assertTrue(refs)
        for rid in refs:
            self.assertIsNotNone(evidence.find(new, rid), rid)


class TestRoot(HomeCase):
    def test_relative_root_becomes_absolute_and_lints_clean(self):
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        proj = os.path.realpath(self.proj)
        self.assertEqual(state.frontmatter(self.moved(self.isa_a))["root"], proj)
        self.assertEqual(state.frontmatter(self.moved(self.isa_b))["root"], os.path.join(proj, "sub"))
        for p in (self.isa_a, self.isa_b):
            rc, lout = self.isa("lint", self.moved(p))
            self.assertEqual(rc, 0, lout)


class TestAsksSnapshot(HomeCase):
    def test_hmac_asks_come_back_verbatim(self):
        old = read(os.path.join(os.path.dirname(self.isa_a), "evidence.jsonl"))
        snap = [json.loads(x) for x in old.splitlines() if '"kind": "asks"' in x][0]
        self.assertTrue(all(str(a).startswith("hmac:") for a in snap["asks"]))
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        rows = evidence.rows(self.moved(self.isa_a))
        snap = [r for r in rows if r.get("kind") == "asks"][0]
        self.assertEqual(snap["asks"], ["Add a --shout flag to greet.py", "with a test"])


class TestEncrypted(HomeCase):
    def setUp(self):
        super().setUp()
        self.plain = read(self.isa_a)
        self.secret = crypt.clean(self.plain, base64.b64decode(TEST_KEY))
        self.assertIn("enc:v1:", self.secret)
        with open(self.isa_a, "w") as f:  # a value the smudge filter never opened
            f.write(self.secret)

    def test_decrypted_with_the_key(self):
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        self.assertEqual(read(self.moved(self.isa_a)), self.plain.replace(
            "root: .", f"root: {os.path.realpath(self.proj)}"))

    def test_without_key_blanked_and_reported(self):
        env = {k: v for k, v in self.env.items() if k != "ISA_KEY"}
        self.assertFalse(os.path.exists(crypt.key_path()))
        rc, out = self.migrate(env=env)
        self.assertEqual(rc, 0, out)
        text = read(self.moved(self.isa_a))
        self.assertNotIn("enc:v1:", text)
        self.assertEqual(state.frontmatter(self.moved(self.isa_a))["stated_goal"], "")
        self.assertRegex(out, r"\d+ encrypted value\(s\).*no key")
        self.assertIn(self.slug(self.isa_a), [x for x in out.splitlines() if "encrypted value" in x][0])


class TestRebind(HomeCase):
    def test_sessions_follow_the_move(self):
        d = os.path.join(self.home, "_state", "sessions")
        bound = [n for n in os.listdir(d) if n.endswith(".json")
                 and json.loads(read(os.path.join(d, n))).get("bound") == os.path.realpath(self.isa_a)]
        self.assertTrue(bound)
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        for n in bound:
            with open(os.path.join(d, n)) as f:
                st = json.load(f)
            self.assertEqual(st["bound"], os.path.realpath(self.moved(self.isa_a)))
            self.assertNotIn(os.path.realpath(self.isa_a), st.get("bound_history") or [])


class TestGitCleanup(HomeCase):
    def filter_config(self):
        return self.git("config", "--local", "--get-regexp", r"^filter\.isa", check=False).stdout

    def test_attributes_file_deleted_and_filter_removed(self):
        self.assertEqual(sorted(read(os.path.join(self.proj, ".gitattributes")).split("\n")[:-1]),
                         sorted(crypt.ATTRIBUTES))
        self.assertTrue(self.filter_config())
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        self.assertFalse(os.path.exists(os.path.join(self.proj, ".gitattributes")))
        self.assertEqual(self.filter_config(), "")

    def test_other_attribute_lines_kept(self):
        p = os.path.join(self.proj, ".gitattributes")
        with open(p) as f:
            have = f.read()
        with open(p, "w") as f:
            f.write("*.png binary\n" + have + "*.sh text eol=lf\n")
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        self.assertEqual(read(p), "*.png binary\n*.sh text eol=lf\n")
        self.assertEqual(self.filter_config(), "")


class TestUntouchedAndSkip(HomeCase):
    def test_root_isa_untouched_and_existing_slug_skipped(self):
        root_isa = os.path.join(self.proj, "ISA.md")
        before = read(root_isa)
        clash = os.path.join(self.dest, self.slug(self.isa_b))
        self.put("ISA.md", "already here\n", base=clash)
        rc, out = self.migrate()
        self.assertEqual(read(root_isa), before)
        skips = [x for x in out.splitlines() if x.startswith("skip ")]
        self.assertEqual(len(skips), 1, out)
        self.assertIn(self.slug(self.isa_b), skips[0])
        self.assertTrue(os.path.isfile(self.isa_b))
        self.assertEqual(read(os.path.join(clash, "ISA.md")), "already here\n")
        self.assertTrue(os.path.isfile(self.moved(self.isa_a)))
        self.assertNotEqual(rc, 0, out)  # a skip is a partial result


class TestCommitLine(HomeCase):
    def test_prints_the_commit_and_commits_nothing(self):
        head = self.git("rev-parse", "HEAD").stdout
        count = self.git("rev-list", "--count", "HEAD").stdout
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        self.assertIn(COMMIT, out.splitlines())
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, head)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout, count)
        r = self.git("diff", "--cached", "--quiet", check=False)
        self.assertEqual(r.returncode, 0, "migrate staged something")


class TestDryRun(HomeCase):
    def walk(self, top, skip=()):
        out = {}
        for d, dirs, files in os.walk(top):
            dirs[:] = [x for x in dirs if os.path.join(d, x) not in skip]
            for n in files:
                p = os.path.join(d, n)
                with open(p, "rb") as f:
                    out[os.path.relpath(p, top)] = hashlib.sha256(f.read()).hexdigest()
        return out

    def snapshot(self):
        logs = os.path.join(self.home, "_state", "logs")
        return fingerprint.of(self.proj), self.walk(self.proj), self.walk(self.home, skip=(logs,))

    def test_same_list_and_nothing_changed(self):
        before = self.snapshot()
        rc, dry = self.migrate("--dry-run")
        self.assertEqual(rc, 0, dry)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.listing(dry)), 2, dry)
        rc, out = self.migrate()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.listing(dry), self.listing(out))


if __name__ == "__main__":
    import unittest
    unittest.main()
