"""Prompt fit check. Run: python3 -m unittest tests.test_fit"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
from isa import fit  # noqa: E402

STRONG = [
    "Review the whole auth module for security issues and make sure every endpoint checks the session.",
    "Audit our Terraform for public S3 buckets across all environments and list each one with its owner.",
    "Investigate why the nightly export job fails intermittently; find the root cause and propose a fix.",
    "Compare Postgres, SQLite and DuckDB for our analytics workload on cost, latency and ops burden, "
    "then recommend one.",
    "Do a thorough code review of this PR:\n- correctness\n- error handling\n- tests",
    "ok we need to adjust. exempting read only actions might not suffice. For example complex reviews could "
    "benefit from an ISA. On read only actions, check if isa could structure the process. propose me a way "
    "to state what isa process solves, and check the current prompt against this. don't go too far, we "
    "will handle it better with jev",
    "Plan the migration from REST to GraphQL and design the deprecation runway for every partner.",
]
NONE = [
    "what time is it?", "thanks!", "ok", "yes", "What does `git rebase -i` do?", "explain this error",
    "which python version is installed?", "/model", "is the build green?", "hi",
    "How do I list hidden files?", "where is the config file?", "can you review my commit message?",
    "please review",
]


class TestFit(unittest.TestCase):
    def test_shape(self):
        for p in STRONG + NONE + ["maybe review this"]:
            level, reasons = fit.score(p)
            self.assertIn(level, ("strong", "maybe", "none"))
            if level != "none":
                self.assertTrue(reasons, p)

    def test_strong(self):
        for p in STRONG:
            self.assertEqual(fit.score(p)[0], "strong", p)

    def test_none(self):
        for p in NONE:
            self.assertEqual(fit.score(p)[0], "none", p)

    def test_advice(self):
        self.assertEqual(fit.advice("none", []), "")
        self.assertIn("ISA fit: strong", fit.advice(*fit.score(STRONG[0])))


if __name__ == "__main__":
    unittest.main()
