"""Project keys and ISA paths. Run: python3 -m unittest tests.test_state"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
from isa import state  # noqa: E402

H = os.path.expanduser("~")


class TestKeys(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="isa-key-", dir=os.path.join(H, ".cache"))
        os.makedirs(os.path.join(self.repo, ".git"))
        os.makedirs(os.path.join(self.repo, "src", "deep"))

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_repo_root_and_subdir_share_key(self):
        self.assertEqual(state.project_key(self.repo), state.project_key(os.path.join(self.repo, "src", "deep")))

    def test_key_is_readable_path_slug(self):
        self.assertEqual(state.project_key(self.repo), ".cache-" + os.path.basename(self.repo))

    def test_non_repo_dir_is_its_own_project(self):
        d = tempfile.mkdtemp(prefix="isa-nongit-", dir=os.path.join(H, ".cache"))
        try:
            self.assertEqual(state.project_key(d), ".cache-" + os.path.basename(d))
        finally:
            shutil.rmtree(d)

    def test_home_and_outside_home(self):
        self.assertEqual(state.project_key(H), "_home")
        self.assertTrue(state.project_key("/etc").startswith("root-etc") or state.project_key("/etc") == "root-etc")

    def test_cwd_inside_isa_home_maps_to_its_project(self):
        os.environ["ISA_HOME"] = os.path.join(self.repo, "home")
        try:
            folder = os.path.join(self.repo, "home", "dev-app", "20261001-120000_task")
            os.makedirs(os.path.join(folder, "_ephemeral"))
            self.assertEqual(state.project_key(folder), "dev-app")
            self.assertEqual(state.project_key(os.path.join(folder, "_ephemeral")), "dev-app")
            self.assertEqual(state.project_dir(folder), os.path.join(self.repo, "home", "dev-app"))
        finally:
            del os.environ["ISA_HOME"]

    def test_isa_paths(self):
        os.environ["ISA_HOME"] = os.path.join(self.repo, "home")
        try:
            p = state.new_isa_path(self.repo, "Fix the Login Bug!")
            self.assertRegex(p, r"/\d{8}-\d{6}_fix-the-login-bug/ISA\.md$")
            self.assertTrue(state.is_master_isa(p))
            self.assertTrue(state.is_isa_path(os.path.join(os.path.dirname(p), "_ephemeral", "f.md")))
            self.assertFalse(state.is_isa_path(os.path.join(state.home(), "_state", "x", "y", "ISA.md")))
            self.assertFalse(state.is_isa_path(os.path.join(self.repo, "ISA.md")))
        finally:
            del os.environ["ISA_HOME"]


class TestDocRoot(unittest.TestCase):
    """Plan P6: where specs, plans and the project ISA live (spec 2026-10-06 § B.1, § A.4)."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="isa-docroot-", dir=os.path.join(H, ".cache"))
        self.home = os.path.join(self.base, "home")
        self.old = os.environ.get("ISA_HOME")
        os.environ["ISA_HOME"] = self.home
        self.repo = os.path.join(self.base, "repo")
        os.makedirs(os.path.join(self.repo, ".git"))
        os.makedirs(os.path.join(self.repo, "src", "deep"))
        self.plain = os.path.join(self.base, "plain")
        os.makedirs(os.path.join(self.plain, "sub"))
        self.tmp = tempfile.mkdtemp(prefix="isa-docroot-tmp-", dir="/tmp")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("ISA_HOME", None)
        else:
            os.environ["ISA_HOME"] = self.old
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def keyed(self, d):
        return os.path.join(self.home, state.project_key(d))

    def test_git_root(self):
        self.assertEqual(state.doc_root(os.path.join(self.repo, "src", "deep")), os.path.realpath(self.repo))
        self.assertEqual(state.doc_root(self.repo), os.path.realpath(self.repo))

    def test_non_git(self):
        self.assertEqual(state.doc_root(self.plain), os.path.realpath(self.plain))
        self.assertEqual(state.doc_root(os.path.join(self.plain, "sub")), os.path.realpath(os.path.join(self.plain, "sub")))

    def test_home(self):
        self.assertEqual(state.doc_root(H), os.path.join(self.home, "_home"))

    def test_temp_dir(self):
        self.assertEqual(state.doc_root(self.tmp), self.keyed(self.tmp))
        self.assertTrue(state.doc_root(self.tmp).startswith(self.home + os.sep))

    def test_git_under_tmp(self):
        os.makedirs(os.path.join(self.tmp, ".git"))
        os.makedirs(os.path.join(self.tmp, "a"))
        self.assertEqual(state.doc_root(os.path.join(self.tmp, "a")), os.path.realpath(self.tmp))

    def test_inside_isa_home(self):
        d = os.path.join(self.home, "dev-app", "docs", "spec")
        os.makedirs(d)
        self.assertEqual(state.doc_root(d), os.path.join(self.home, "dev-app"))
        self.assertEqual(state.doc_root(os.path.join(self.home, "dev-app")), os.path.join(self.home, "dev-app"))

    def test_spec_path_true(self):
        for root in (self.repo, self.plain, os.path.join(self.home, "_home"), self.keyed(self.tmp)):
            for kind in ("spec", "plan"):
                p = os.path.join(root, "docs", kind, "2026-10-06-x.md")
                self.assertTrue(state.is_spec_path(p), p)
        self.assertTrue(state.is_spec_path(os.path.join(self.repo, "docs", "spec", "new-not-yet-written.md")))

    def test_spec_path_false(self):
        for p in (os.path.join(self.repo, "docs", "specs", "x.md"), os.path.join(self.repo, "docs", "spec", "x.txt"),
                  os.path.join(self.repo, "docs", "spec", "sub", "x.md"), os.path.join(self.repo, "src", "docs", "spec", "x.md"),
                  os.path.join(self.repo, "doc", "spec", "x.md"), os.path.join(self.tmp, "docs", "spec", "x.md"),
                  os.path.join(H, "docs", "spec", "x.md"), os.path.join(self.repo, "docs", "spec")):
            self.assertFalse(state.is_spec_path(p), p)

    def test_project_isa_everywhere(self):
        for root in (self.repo, self.plain, os.path.join(self.home, "_home"), self.keyed(self.tmp)):
            self.assertTrue(state.is_project_isa(os.path.join(root, "ISA.md")), root)

    def test_task_isa_not_project(self):
        task = os.path.join(self.home, "dev-app", "20261006-120000_t", "ISA.md")
        self.assertFalse(state.is_project_isa(task))
        self.assertFalse(state.is_project_isa(os.path.join(self.repo, "src", "ISA.md")))
        self.assertFalse(state.is_project_isa(os.path.join(self.home, "ISA.md")))
        self.assertFalse(state.is_project_isa(os.path.join(self.home, "_state", "ISA.md")))
        self.assertFalse(state.is_project_isa(os.path.join(self.tmp, "ISA.md")))

    def test_home_project_isa_not_task(self):
        self.assertFalse(state.is_task_isa(os.path.join(self.home, "dev-app", "ISA.md")))
        self.assertTrue(state.is_task_isa(os.path.join(self.home, "dev-app", "20261006-120000_t", "ISA.md")))


if __name__ == "__main__":
    unittest.main()
