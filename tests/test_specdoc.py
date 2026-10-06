"""Plan P5 (spec 2026-10-06 § B.3, § B.4, § B.6, § 8 item 16): parse, lint and hash specs and plans.

Run: python3 -m unittest tests.test_specdoc
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_hooks import ROOT

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import specdoc  # noqa: E402

E2 = """---
status: draft
effort: E2
---

# Backup verify mode

## Problem
`backup --verify` only checks that each file exists in the archive, so a corrupted copy passes.

## Goal
`backup --verify` compares SHA-256 digests and fails on the first mismatch.
Said:
- make --verify actually check the contents
Assumed:
- SHA-256 is enough; no signature check.

## S1 — Digest check
`--verify` hashes each archived file and compares it with the manifest digest.
Accepted when:
- [ ] A1: a flipped byte in one archived file makes `backup --verify` exit 3 and name the file
- [ ] A2: an intact archive of 1000 files verifies in under 5 s

## Open questions
"""

E3 = """---
status: draft
effort: E3
---

# Help screen redesign

## Problem
`tool --help` prints 140 lines in declaration order; users miss the two flags they need.

## Goal
`tool --help` fits one screen and leads with the common tasks.
Said:
- the help is a wall of text, make it usable
Assumed:
- 24 lines is "one screen".
- the full list stays reachable as `tool help --all`.

## Out of scope
Man pages and shell completion.

## Constraints
- At most 24 lines at 80 columns.

## Approaches
1. Task-first summary plus `help --all` (chosen): short, keeps everything reachable.
2. Paged output: needs a pager on every platform. Rejected.

## S1 — Summary screen
The default `--help`: usage line, five common tasks, a pointer to `help --all`.
Accepted when:
- [ ] A1: `tool --help | wc -l` prints 24 or less
- [ ] A2: the first task listed is `tool sync`

## S2 — Full reference
`tool help --all` keeps the full flag list, grouped by command.
Accepted when:
- [ ] A1: every flag of the old help appears in `tool help --all`

## Decisions
- 2026-10-06: paging rejected (see Approaches).

## Open questions
"""

E4 = """---
status: draft
effort: E4
plan: docs/plan/2026-10-06-api-migration.md
---

# REST to GraphQL migration

## Problem
Clients make 6 REST calls per screen; the mobile team wants one query.

## Goal
Every REST endpoint has a GraphQL equivalent, and REST keeps working for six months.
Said:
- move the API to GraphQL without breaking existing clients
Assumed:
- six months of REST support is enough.

## Out of scope
Subscriptions.

## Constraints
- REST responses stay byte-identical until 2027-04-06.

## Approaches
1. Schema-first, REST as a thin adapter over resolvers (chosen).
2. Two parallel stacks: double the maintenance. Rejected.

## S1 — Schema
The GraphQL schema covering every REST resource.
Accepted when:
- [ ] A1: every REST resource has a GraphQL type
- [ ] A2: the schema passes `graphql-schema-linter`

## S2 — Resolvers
Resolvers backed by the existing services.
Accepted when:
- [ ] A1: each query returns the same data as its REST endpoint
- [ ] A2: the N+1 query count stays at 1 per list
- [ ] A3: p95 latency under 200 ms

## S3 — REST adapter
REST endpoints served by the resolvers.
Accepted when:
- [ ] A1: the REST contract tests pass unchanged

## Decisions
- 2026-10-06: two parallel stacks rejected (see Approaches).
- second-look: a reviewer read the spec before the ack; findings folded into S2.

## Open questions
"""

PLAN = """---
status: draft
spec: docs/spec/2026-10-06-api-migration.md
---

# Plan — REST to GraphQL migration

Goal: GraphQL for every resource, with REST served through it.
Approach: Schema first, then resolvers, then the REST adapter over them.
Files:
- `api/schema.graphql` — the schema
- `api/resolvers.py` — the resolvers
Review focus:
- a client sending both REST and GraphQL headers → P3
- a list query issuing one SQL query per item → P2

- [ ] P1 — The schema · E2 · covers S1:A1,A2
  Files: `api/schema.graphql` (create)
  Done when: every REST resource has a type, and the linter passes.
- [x] P2 — The resolvers · E3 · covers S2 · after P1
  Files: `api/resolvers.py` (create)
  Interfaces: produces `resolve(query: str) -> dict`
  Done when:
  - each query matches its REST endpoint;
  - p95 under 200 ms.
- [ ] P3 — The REST adapter · E3 · covers S3 · after P1, P2
  Files: `api/rest.py` (change)
  Done when: the REST contract tests pass unchanged.
"""

SPEC_NAME = "2026-10-06-api-migration.md"


class DocCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="isa-specdoc-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, text, kind="spec", name=SPEC_NAME):
        d = os.path.join(self.tmp, "docs", kind)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return p

    def lint(self, text, kind="spec", moment="draft", spec=E4):
        if kind == "plan":
            self.write(spec)
        return specdoc.lint(self.write(text, kind), moment)

    def errors(self, items):
        return [m for m in items if not m.startswith("warn:")]

    def warns(self, items):
        return [m for m in items if m.startswith("warn:")]

    def assertError(self, items, *needles):
        errs = self.errors(items)
        self.assertTrue(errs, f"expected an error, got {items}")
        for n in needles:
            self.assertTrue(any(n in e for e in errs), f"no error mentions {n!r}: {errs}")

    def assertClean(self, items):
        self.assertEqual(self.errors(items), [], items)


class Parse(DocCase):
    def test_kind(self):
        self.assertEqual(specdoc.parse(E3)["kind"], "spec")
        self.assertEqual(specdoc.parse(PLAN)["kind"], "plan")
        # the shape decides: a Plan title without `spec:`, or `spec:` without the title, is a spec
        self.assertEqual(specdoc.parse(PLAN.replace("spec: docs/spec/2026-10-06-api-migration.md\n", ""))["kind"],
                         "spec")
        self.assertEqual(specdoc.parse(PLAN.replace("# Plan — ", "# "))["kind"], "spec")
        self.assertEqual(specdoc.parse(PLAN)["fm"]["spec"], "docs/spec/2026-10-06-api-migration.md")

    def test_sections(self):
        d = specdoc.parse(E3)
        self.assertEqual(sorted(d["sections"]), ["S1", "S2"])
        s1 = d["sections"]["S1"]
        self.assertEqual(s1["title"], "Summary screen")
        lines = E3.splitlines()
        self.assertEqual(lines[s1["line"] - 1], "## S1 — Summary screen")
        self.assertEqual(sorted(s1["bullets"]), ["A1", "A2"])
        a2 = s1["bullets"]["A2"]
        self.assertEqual(a2["text"], "the first task listed is `tool sync`")
        self.assertFalse(a2["ticked"])
        self.assertEqual(lines[a2["line"] - 1], "- [ ] A2: the first task listed is `tool sync`")
        ticked = specdoc.parse(E3.replace("- [ ] A1: every flag", "- [X] A1: every flag"))
        self.assertTrue(ticked["sections"]["S2"]["bullets"]["A1"]["ticked"])

    def test_steps(self):
        d = specdoc.parse(PLAN)
        self.assertEqual(sorted(d["steps"]), ["P1", "P2", "P3"])
        p1, p2, p3 = d["steps"]["P1"], d["steps"]["P2"], d["steps"]["P3"]
        self.assertEqual(p1["goal"], "The schema")
        self.assertEqual(p1["tier"], "E2")
        self.assertEqual(p1["covers"], [("S1", "A1"), ("S1", "A2")])
        self.assertEqual(p1["after"], [])
        self.assertFalse(p1["ticked"])
        self.assertEqual(PLAN.splitlines()[p1["line"] - 1], "- [ ] P1 — The schema · E2 · covers S1:A1,A2")
        self.assertEqual(p2["covers"], [("S2", None)])
        self.assertEqual(p2["after"], ["P1"])
        self.assertTrue(p2["ticked"])
        self.assertEqual(p2["files"], ["api/resolvers.py"])
        self.assertEqual(p2["done_when"], ["each query matches its REST endpoint;", "p95 under 200 ms."])
        self.assertEqual(p3["after"], ["P1", "P2"])
        self.assertEqual(p3["done_when"], ["the REST contract tests pass unchanged."])
        done = specdoc.parse(PLAN.replace("covers S1:A1,A2\n", "covers S1:A1,A2 · Done: 2026-10-08\n"))
        self.assertEqual(done["steps"]["P1"]["covers"], [("S1", "A1"), ("S1", "A2")])

    def test_review_focus(self):
        self.assertEqual(specdoc.parse(PLAN)["review_focus"], [
            ("a client sending both REST and GraphQL headers", "P3"),
            ("a list query issuing one SQL query per item", "P2"),
        ])
        self.assertEqual(specdoc.parse(E3)["review_focus"], [])


class AckHash(unittest.TestCase):
    def test_crlf(self):
        self.assertEqual(specdoc.ack_hash(E4), specdoc.ack_hash(E4.replace("\n", "\r\n")))
        self.assertEqual(specdoc.ack_hash(PLAN), specdoc.ack_hash(PLAN.replace("\n", "\r\n")))

    def test_final_newline(self):
        base = E4.rstrip("\n")
        self.assertEqual(len({specdoc.ack_hash(base), specdoc.ack_hash(base + "\n"),
                              specdoc.ack_hash(base + "\n\n")}), 1)

    def test_ticks(self):
        hashes = {specdoc.ack_hash(E4.replace("- [ ] A", f"- [{t}] A")) for t in (" ", "x", "X")}
        self.assertEqual(len(hashes), 1)
        hashes = {specdoc.ack_hash(PLAN.replace("- [ ] P", f"- [{t}] P").replace("- [x] P2", f"- [{t}] P2"))
                  for t in (" ", "x", "X")}
        self.assertEqual(len(hashes), 1)

    def test_status_done_lines(self):
        acked = E4.replace("status: draft", "status: acked 2026-10-06 #a1b2c3d4")
        done = acked.replace("## S1 — Schema\n",
                             "## S1 — Schema\nDone: 2026-10-09 — 2/2 accepted (ISAs 20261008-101500_schema)\n")
        self.assertEqual(len({specdoc.ack_hash(E4), specdoc.ack_hash(acked), specdoc.ack_hash(done),
                              specdoc.ack_hash(done.replace("status: acked 2026-10-06 #a1b2c3d4",
                                                            "status: done 2026-10-09"))}), 1)

    def test_isa_suffix(self):
        marked = E4.replace("- [ ] A1: every REST resource has a GraphQL type",
                            "- [x] A1: every REST resource has a GraphQL type  (2026-10-08, ISA 20261008-101500_schema)")
        self.assertEqual(specdoc.ack_hash(E4), specdoc.ack_hash(marked))

    def test_step_done_suffix(self):
        marked = PLAN.replace("- [ ] P1 — The schema · E2 · covers S1:A1,A2",
                              "- [x] P1 — The schema · E2 · covers S1:A1,A2 · Done: 2026-10-08")
        self.assertEqual(specdoc.ack_hash(PLAN), specdoc.ack_hash(marked))

    def test_content_change(self):
        h = specdoc.ack_hash(E4)
        self.assertRegex(h, r"^[0-9a-f]{8}$")
        self.assertNotEqual(h, specdoc.ack_hash(E4.replace("p95 latency under 200 ms", "p95 latency under 300 ms")))
        self.assertNotEqual(specdoc.ack_hash(PLAN), specdoc.ack_hash(PLAN.replace("· after P1\n", "\n", 1)))


class SpecLint(DocCase):
    def test_fixtures_clean(self):
        for text in (E2, E3, E4):
            self.assertEqual(self.lint(text, moment="ack"), [], text.splitlines()[5])
        self.assertEqual(self.lint(PLAN, "plan", moment="ack"), [])

    def test_frontmatter(self):
        self.assertError(self.lint(E3.replace("status: draft\n", "")), "status")
        self.assertError(self.lint(E3.replace("effort: E3\n", "")), "effort")

    def test_said_assumed(self):
        self.assertError(self.lint(E3.replace("Said:\n- the help is a wall of text, make it usable\n", "")), "Said")
        self.assertError(self.lint(E3.replace("Assumed:\n", "Guessed:\n")), "Assumed")

    def test_s_sections(self):
        no_s = re.sub(r"## S\d — .*?(?=## Decisions)", "", E3, flags=re.S)
        self.assertNotIn("## S1", no_s)
        self.assertError(self.lint(no_s), "S<n>")
        self.assertError(self.lint(E3.replace("- [ ] A1: every flag", "- A1: every flag")), "S2")
        self.assertError(self.lint(E3.replace("Accepted when:\n- [ ] A1: every flag of the old help appears in "
                                              "`tool help --all`\n", "")), "S2")

    def test_bullet_ids_unique(self):
        dup = E3.replace("- [ ] A2: the first task", "- [ ] A1: the first task")
        self.assertError(self.lint(dup), "S1", "A1")
        self.assertClean(self.lint(E3))  # A1 in S1 and in S2 is fine

    def test_placeholders(self):
        for bad in ("TBD", "TODO", "…", "<one or two sentences>"):
            text = E3.replace("Man pages and shell completion.", f"Man pages and {bad} completion.")
            self.assertError(self.lint(text), bad)
        self.assertError(self.lint(E3.replace("## S2 — Full reference", "## S2 — <…>")), "<…>")

    def test_placeholder_quoted(self):
        quoted = E3.replace("Man pages and shell completion.",
                            "Man pages, a `TODO` list, `TBD` markers, `…` and `<one or two sentences>` slots.\n\n"
                            "```\nTODO: TBD …\n<one or two sentences>\n```")
        self.assertClean(self.lint(quoted))
        self.assertClean(self.lint(E3.replace("Man pages and shell completion.", "Man pages, and so on…")))

    def test_empty_section(self):
        self.assertError(self.lint(E3.replace("Man pages and shell completion.\n", "")), "Out of scope")

    def test_open_questions(self):
        asked = E3.rstrip("\n") + "\n- Is 24 lines right for Windows terminals?\n"
        self.assertClean(self.lint(asked, moment="draft"))
        self.assertError(self.lint(asked, moment="ack"), "Open questions")
        self.assertClean(self.lint(E3, moment="ack"))

    def test_approaches(self):
        cut = re.sub(r"## Approaches\n.*?(?=## S1)", "", E3, flags=re.S)
        self.assertError(self.lint(cut), "Approaches")
        self.assertClean(self.lint(E2))  # E2 has no Approaches and needs none

    def test_plan_field(self):
        self.assertError(self.lint(E4.replace("plan: docs/plan/2026-10-06-api-migration.md\n", "")), "plan:")
        self.assertClean(self.lint(E3))

    def test_second_look(self):
        cut = E4.replace("- second-look: a reviewer read the spec before the ack; findings folded into S2.\n", "")
        self.assertError(self.lint(cut), "second-look:")
        # a second-look line outside Decisions does not count
        moved = cut.replace("## Out of scope\nSubscriptions.", "## Out of scope\nSubscriptions. second-look: none.")
        self.assertError(self.lint(moved), "second-look:")

    def test_interview(self):
        e5 = E4.replace("effort: E4", "effort: E5")
        self.assertError(self.lint(e5), "interview:")
        self.assertClean(self.lint(e5.replace("effort: E5\n", "effort: E5\ninterview: 2026-10-06\n")))
        self.assertClean(self.lint(E4))


class PlanLint(DocCase):
    def test_coverage(self):
        narrowed = PLAN.replace("covers S2 · after P1", "covers S2:A1,A3 · after P1")
        self.assertError(self.lint(narrowed, "plan"), "S2:A2")
        self.assertClean(self.lint(PLAN, "plan"))  # `covers S2` covers A1–A3
        self.assertError(self.lint(PLAN.replace("covers S3 ·", "covers S9 ·"), "plan"), "S9")

    def test_after(self):
        self.assertError(self.lint(PLAN.replace("after P1, P2", "after P1, P9"), "plan"), "P9")

    def test_review_focus_target(self):
        self.assertError(self.lint(PLAN.replace("headers → P3", "headers → P9"), "plan"), "P9")
        self.assertError(self.lint(PLAN.replace("headers → P3", "headers"), "plan"), "Review focus")

    def test_step_files(self):
        self.assertError(self.lint(PLAN.replace("  Files: `api/resolvers.py` (create)\n", ""), "plan"),
                         "P2", "Files")

    def test_step_done_when(self):
        cut = PLAN.replace("  Done when: every REST resource has a type, and the linter passes.\n", "")
        self.assertError(self.lint(cut, "plan"), "P1", "Done when")

    def test_plan_placeholder(self):
        self.assertError(self.lint(PLAN.replace("p95 under 200 ms.", "p95 TODO."), "plan"), "TODO")

    def test_size_warning(self):
        padded = PLAN + "\nNotes:\n" + ("- a note that only pads the plan out.\n" * (3 * len(E4) // 30))
        self.assertGreater(len(padded.encode()), 3 * len(E4.encode()))
        out = self.lint(padded, "plan")
        self.assertClean(out)
        self.assertEqual(len([w for w in self.warns(out) if "3×" in w]), 1, out)
        self.assertEqual(self.warns(self.lint(PLAN, "plan")), [])

    def test_code_warning(self):
        code = PLAN + "\n```python\n" + ("x = resolve('query { a }')\n" * 60) + "```\n"
        out = self.lint(code, "plan")
        self.assertClean(out)
        self.assertTrue(any("code" in w for w in self.warns(out)), out)

    def test_missing_spec(self):
        p = self.write(PLAN.replace("2026-10-06-api-migration.md\n---", "2026-10-06-gone.md\n---"), "plan")
        out = specdoc.lint(p)
        self.assertError(out, "2026-10-06-gone.md")


class Cli(DocCase):
    def setUp(self):
        super().setUp()
        # a /tmp folder is no doc root (plan P6): specs of a scratch project live under ISA_HOME/<key>/docs/
        self.docs = os.path.join(self.tmp, "home", "_scratch")

    def write(self, text, kind="spec", name=SPEC_NAME):
        d = os.path.join(self.docs, "docs", kind)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return p

    def isa(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("ISA_")}
        env["ISA_HOME"] = os.path.join(self.tmp, "home")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "runtime", "bin", "isa"), *args],
                           capture_output=True, text=True, env=env, cwd=self.tmp)
        return r.returncode, r.stdout

    def test_lint_routes_spec(self):
        good = self.write(E3)
        rc, out = self.isa("lint", good)
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.strip(), f"{good}: ok (spec)")
        bad = self.write(E3.replace("Said:\n", ""), name="2026-10-06-bad.md")
        rc, out = self.isa("lint", bad)
        self.assertEqual(rc, 1, out)
        self.assertTrue(out.startswith(f"{bad}: 1 error(s) (spec)\n  ERROR: "), out)
        self.write(E4)
        plan = self.write(PLAN.replace("headers → P3", "headers"), "plan")
        rc, out = self.isa("lint", plan)
        self.assertEqual(rc, 1, out)
        self.assertIn("(plan)", out.splitlines()[0])
        rc, out = self.isa("lint", "--moment", "ack", self.write(E3.rstrip("\n") + "\n- open?\n", name="q.md"))
        self.assertEqual(rc, 1, out)
        self.assertIn("Open questions", out)

    def test_lint_other_files(self):
        near = os.path.join(self.tmp, "docs", "specs")
        os.makedirs(near)
        p = os.path.join(near, SPEC_NAME)
        with open(p, "w") as f:
            f.write(E3)
        rc, out = self.isa("lint", p)
        self.assertEqual(rc, 1, out)
        self.assertNotIn("(spec)", out)
        self.assertIn("missing `## Criteria`", out)  # the ISA gate read it
        example = os.path.join(ROOT, "skill", "ISA", "Examples", "e1-minimal.md")
        rc, out = self.isa("lint", example)
        self.assertEqual((rc, out.splitlines()[0]), (0, f"{example}: ok"))

    def test_lint_routes_by_doc_root(self):
        spec = self.write(E3)  # ISA_HOME/<key>/docs/spec/: a spec path
        rc, out = self.isa("lint", spec)
        self.assertEqual((rc, out.strip()), (0, f"{spec}: ok (spec)"))
        loose = os.path.join(self.tmp, "docs", "spec", SPEC_NAME)  # a /tmp folder is no doc root
        os.makedirs(os.path.dirname(loose))
        with open(loose, "w") as f:
            f.write(E3)
        rc, out = self.isa("lint", loose)
        self.assertEqual(rc, 1, out)
        self.assertNotIn("(spec)", out)
        self.assertIn("missing `## Criteria`", out)


if __name__ == "__main__":
    unittest.main()
