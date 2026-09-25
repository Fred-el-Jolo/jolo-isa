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


if __name__ == "__main__":
    unittest.main()
