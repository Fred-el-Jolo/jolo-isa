---
task: "Commit, fill the project ISA, fix the examples"
slug: 20261003-012153_commit-project-isa-examples
effort: E2
phase: build
progress: 0/9
started: 2026-10-03T01:21:53
updated: 2026-10-03T01:21:53
root: .
stated_goal: null
asks: ["enc:v1:0ddf368a:1J0lQWwzBW_h1OzM8lqHdg0QPgxJxjEbEBFbnEhK8_0FAW-vDBdBOJMeUnksNWuNTwIumGdJw9YaqeA", "enc:v1:0ddf368a:A72Vpyyt1iYKEKvr9BbYBcuV35Z7x9YbqOFmEceuDvnxcy80hw-I2k4gboZyuj0N4gnhLKT-cqF7SnCLv0sSQl4DVQcY7P53eHcSpFE"]
context_sufficient: true
---

## Problem

The notification fix and this repo's first ISA files are uncommitted, so the encryption has never met a real push. The project ISA is an empty skeleton although AGENTS.md lists this repo's standing rules. Ten examples still miss `fails-when:`, which likely hides probes that can't fail.

## Goal

Everything is committed and pushed to `main`, and what git stored is checked: every quote of the user in `.isa/` encrypted, the root `ISA.md` plain. The project ISA holds AGENTS.md's working rules as standing claims that `isa verify ISA.md` re-proves. Every example's red-exempt entry has a `fails-when:`, and the probes that couldn't fail are tightened.

## Criteria

- [ ] ISC-1: HEAD is on `origin/main` and the working tree is clean.
- [ ] ISC-2: At HEAD, no quoting form in a committed `.isa/` file is plain text.
- [ ] ISC-3: At HEAD, the committed root `ISA.md` holds no ciphertext.
- [ ] ISC-4: The project ISA lints clean and states every AGENTS.md working rule as a standing claim.
- [ ] ISC-5: `isa verify ISA.md` re-proves every standing claim.
- [ ] ISC-6: No example has a red-exempt entry without `fails-when:`.
- [ ] ISC-7: Every example still lints ok.
- [ ] ISC-8: Anti: the full unit suite or the pi tests fail.
- [ ] ISC-9: Anti: a git or encryption error is left unreported to the user.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  kind: config
  check: fetch, ancestry, clean tree
  threshold: exit 0
  tool: git fetch -q origin && git merge-base --is-ancestor HEAD origin/main && test -z "$(git status --porcelain)"
  fails-when: "HEAD is not on origin/main, or something is uncommitted"

- isc: ISC-2
  type: bash
  kind: behaviour
  check: committed blobs read back
  threshold: exit 0
  tool: python3 tools/check_committed_isas.py HEAD
  red: exempt — the first commit with ISA files is part of this task; before it there is no blob to check
  fails-when: "a committed quote of the user reads back in plain text"

- isc: ISC-3
  type: bash
  kind: behaviour
  check: same tool, root ISA.md branch
  threshold: exit 0
  tool: python3 tools/check_committed_isas.py HEAD && git show HEAD:ISA.md | grep -q "kind. project"
  red: exempt — same reason as ISC-2
  fails-when: "the committed root ISA.md holds an enc:v1: value, or is missing"

- isc: ISC-4
  type: bash
  kind: doc
  check: lint + one claim per working rule
  threshold: exit 0
  tool: isa lint ISA.md && test "$(grep -c '^- ISC-P' ISA.md)" -ge 5
  fails-when: "the project ISA fails lint or holds fewer than the five working rules"

- isc: ISC-5
  type: bash
  kind: behaviour
  check: re-prove
  threshold: exit 0
  tool: isa verify ISA.md
  red: exempt — the claims hold already; this proves the project ISA can re-prove them
  fails-when: "a standing claim's probe exits non-zero"

- isc: ISC-6
  type: bash
  kind: doc
  check: the linter's fails-when warning count
  threshold: exit 0
  tool: "! python3 tools/lint_isa.py skill/ISA/Examples/*.md | grep -q \"can't get a red baseline\""
  fails-when: "an example still warns about a missing fails-when"

- isc: ISC-7
  type: bash
  kind: regression
  check: linter on all examples
  threshold: exit 0
  tool: test "$(python3 tools/lint_isa.py skill/ISA/Examples/*.md | grep -c '.md. ok$')" = 12
  fails-when: "an example stops linting ok"

- isc: ISC-8
  type: unit-test
  kind: regression
  check: suite + pi
  threshold: exit 0
  tool: python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install tests.test_status tests.test_evidence tests.test_shell_changes tests.test_feature_order tests.test_home_and_complete tests.test_seamless_projects tests.test_gate tests.test_commands tests.test_fingerprint tests.test_blocked tests.test_red tests.test_lint_v2 tests.test_purge tests.test_declaration tests.test_logs tests.test_ask tests.test_jev tests.test_m11 tests.test_m12 && node --test adapters/pi/test/extension.test.ts
  fails-when: "any test fails"

- isc: ISC-9
  type: manual
  kind: decision
  check: every git command's output read; errors relayed in the reply as they happen
  threshold: none unreported
  tool: read the git outputs of this run
```

## Decisions

- 2026-10-03 01:22: stated_goal null: the prompt is a short list of items; the asks hold its spans.
- 2026-10-03 01:22: ISC-2/3 are checked on what git stored (`git show HEAD:path`), not the working tree, which is always plain by design.
