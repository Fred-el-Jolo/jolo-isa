---
spec: 2026-10-08-review-fixes-01-spec.md
isa: 20261008-213626_review-fixes
closed: 2026-10-09
---

# Plan — Review fixes: the perimeter, the stages of `isa verify`, closed work, forged acks, commits

## Problem

The review of 848222f..HEAD (2026-10-08) found eight bugs in the engine built on the three foundations. The two high ones break the foundations themselves:
- FOUNDATION_2: shell commands that reach `~/.isa` or a spec through `$HOME`, or through a `cd` earlier in the same command, are classified as plain project writes and go through in BUILD. Commit 6888294 opened the `cd` case.
- FOUNDATION_1: `isa verify` runs arbitrary probes in any stage, so work can start before the user's ack.
The rest: after an E2+ close the session stays bound to the finished spec, whose next command is refused; a closed ISA can still be changed, and `isa ack` sets it back to BUILD with no new click; an ack question can arrive with its answer pre-filled by the model; a failed commit at close is silent; a staged rename loses its old path in the work commit; and an `isa` command with `$(isa …)` counts as a project change.

## Vision

The three foundations hold in the code as they do in the docs: no shell spelling reaches an ISA entity except an `isa` command, no probe runs before the user's ack, a closed task stays closed, an ack is always the user's own click, and the close never hides what it didn't commit.

## Out of Scope

Sandboxing probes beyond the classifier check (a probe that runs a script can still do what the script does). The `ISA: ` binding of any `isa` command's output. The open items in AGENTS.md § Issues. Parsing nested `$(…)`: a nested substitution stays `unknown`.

## Principles

- Each fix starts as a failing test, in the suite of the part it touches: classifier cases in `tests/test_bash_classifier.py`, everything through the hooks and commands in `tests/test_foundations.py`.
- The smallest change in the module that owns the rule: `classify.py` for the perimeter, `commands.py` for the commands, `engine.py` for the hooks, `gitops.py` for git.
- A test that encodes old, wrong behaviour (the click helper filling in `answers` at PreToolUse) is fixed to the real harness shape, not worked around.

## Constraints

- `runtime/` stays standard-library only; every file stays under 50 KB.
- Every case in `tests/test_bash_classifier.py` keeps its current kind, the `MENTIONS` table included (a commit message naming `~/.isa` stays a `write`).
- The hooks still fail open on a crash.

## Goal

Each of the eight bugs is fixed in `runtime/`, each fix is proven by a test that fails on the current code, and every existing suite still passes.

## Criteria

- [x] ISC-1: The perimeter catches `$HOME`, `cd` and `git -C` spellings.
  - [x] ISC-1.1: The six `$HOME` / `${HOME}` write commands classify as guarded.
  - [x] ISC-1.2: Writes after `cd ~/.isa/…` or `cd docs` classify as guarded.
  - [x] ISC-1.3: `git -C ~/.isa` and `cd ~/.isa && git add` classify as guarded.
  - [x] ISC-1.4: Python code opening `os.environ['HOME']+'/.isa'` classifies as guarded.
  - [x] ISC-1.5: `cd src && rm x` is write and `cd /tmp && rm x` read.
  - [x] ISC-1.6: The Claude hook denies `rm -rf $HOME/.isa/<project>` in BUILD.
  - [x] ISC-1.7: Anti: an existing classifier table or composition case changes its kind.
- [x] ISC-2: `isa verify` runs only in BUILD, never a guarded probe.
  - [x] ISC-2.1: Verify on an unacked E2 ISA refuses, runs nothing, names the ack.
  - [x] ISC-2.2: Verify refuses while the spec is reopened or not refined.
  - [x] ISC-2.3: An E1 ISA that lints still verifies as before.
  - [x] ISC-2.4: `isa write ISC-N --probe` refuses a guarded command, ISA unchanged.
  - [x] ISC-2.5: Verify and close refuse an ISA holding a guarded probe.
- [x] ISC-3: A finished spec no longer stays bound after its close.
  - [x] ISC-3.1: After an E2 close, the next ON prompt unbinds ISA and spec.
  - [x] ISC-3.2: A bound finished spec gets Q1, never `isa new --spec`.
- [x] ISC-4: A closed ISA can't be changed by any command.
  - [x] ISC-4.1: All ten writing commands refuse a closed ISA, leaving it byte-identical.
  - [x] ISC-4.2: `isa show`, `isa diff` and `isa lint` still read a closed ISA.
- [x] ISC-5: An ack or gate answer pre-filled by the model is refused.
  - [x] ISC-5.1: PreToolUse denies an ack or gate question with pre-filled answers.
  - [x] ISC-5.2: An ack answered only at PostToolUse still records the click.
- [x] ISC-6: A failed commit is reported by the close and the ack.
  - [x] ISC-6.1: A close under a failing pre-commit hook prints both `Not committed` lines.
  - [x] ISC-6.2: A spec ack under a failing pre-commit hook prints `Not committed`.
  - [x] ISC-6.3: A close with nothing to commit prints no `Not committed` line.
- [x] ISC-7: A staged rename commits both its paths.
  - [x] ISC-7.1: After `git mv a.txt b.txt`, the work commit deletes a and adds b.
- [x] ISC-8: `isa` commands compose with `$(isa …)`, and options are checked.
  - [x] ISC-8.1: `isa show "$(isa ls | head -1)"` and the `&&` form classify as isa-cmd.
  - [x] ISC-8.2: `rg foo $(cat list)` stays unknown; `isa show "$(rm x)"` isn't isa-cmd.
  - [x] ISC-8.3: `isa verify --timeout abc` exits 1 with a message, no traceback.
- [x] ISC-9: Anti: a pre-install test suite fails after the fixes.
- [x] ISC-10: Anti: `runtime/` imports beyond stdlib, or a file reaches 50 KB.

## Test Strategy

```yaml
- isc: ISC-1.1
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_bash_classifier.TestReviewFixes.test_home_paths
- isc: ISC-1.2
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_bash_classifier.TestReviewFixes.test_cd_targets
- isc: ISC-1.3
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_bash_classifier.TestReviewFixes.test_git_dir
- isc: ISC-1.4
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_bash_classifier.TestReviewFixes.test_code_home_lookup
- isc: ISC-1.5
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_bash_classifier.TestReviewFixes.test_cd_elsewhere
- isc: ISC-1.6
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_perimeter_home
- isc: ISC-1.7
  anchors_to: S1
  kind: regression
  tool: python3 -m unittest tests.test_bash_classifier.TestTable tests.test_bash_classifier.TestCompositions
  fails-when: "a fix changed the kind of a command already in the classifier's table or compositions"
- isc: ISC-2.1
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_verify_needs_ack
- isc: ISC-2.2
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_verify_spec_reopened
- isc: ISC-2.3
  anchors_to: S2
  kind: regression
  tool: python3 -m unittest tests.test_foundations.Proof.test_verification_lines tests.test_foundations.Proof.test_red_baseline
  fails-when: the stage check refuses or changes an E1 verify
- isc: ISC-2.4
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_guarded_probe_write
- isc: ISC-2.5
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_guarded_probe_run
- isc: ISC-3.1
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_close_unbinds
- isc: ISC-3.2
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_finished_spec_not_open
- isc: ISC-4.1
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_closed_isa_frozen
- isc: ISC-4.2
  anchors_to: S4
  kind: regression
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_closed_isa_readable
  fails-when: the closed check also refuses a read command
- isc: ISC-5.1
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_prefilled_answer_denied
- isc: ISC-5.2
  anchors_to: S5
  kind: regression
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_ack_click_at_post
  fails-when: "the PreToolUse check also blocks a real click, so no ack can be recorded"
- isc: ISC-6.1
  anchors_to: S6
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_close_commit_failure
- isc: ISC-6.2
  anchors_to: S6
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_ack_commit_failure
- isc: ISC-6.3
  anchors_to: S6
  kind: regression
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_close_nothing_to_commit
  fails-when: a close with nothing to commit reports it as a failure
- isc: ISC-7.1
  anchors_to: S7
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_rename_committed
- isc: ISC-8.1
  anchors_to: S8
  kind: behaviour
  tool: python3 -m unittest tests.test_bash_classifier.TestReviewFixes.test_isa_substitution
- isc: ISC-8.2
  anchors_to: S8
  kind: regression
  tool: python3 -m unittest tests.test_bash_classifier.TestReviewFixes.test_other_substitution
  fails-when: "the isa-cmd rule also covers a substitution that runs a non-isa, non-read command"
- isc: ISC-8.3
  anchors_to: S8
  kind: behaviour
  tool: python3 -m unittest tests.test_foundations.ReviewFixes.test_verify_timeout_value
- isc: ISC-9
  anchors_to: Goal
  kind: regression
  tool: "python3 -m unittest tests.test_foundations tests.test_install tests.test_bash_classifier && node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts"
  fails-when: "any test of the pre-install suites fails, old or new"
- isc: ISC-10
  anchors_to: Goal
  kind: regression
  tool: "python3 tests/check_stdlib.py runtime/ && test -z \"$(git ls-files runtime tests | xargs stat -c '%s %n' | awk '$1>=51200')\""
  fails-when: a fix imports a non-stdlib module or grows a tracked file to 50 KB
```

## Decisions

- 2026-10-09 15:09: S7: keeping a rename old path was not enough — "git add -A -- <deleted path>" fails the whole add (pathspec did not match), so commit() now adds the paths that exist and "git rm --cached --ignore-unmatch" the gone ones; this also fixes any task that deletes a tracked file.
- 2026-10-09 15:09: S5: the test helper click() sent answers already at PreToolUse — exactly the forged shape S5 refuses; it now asks without answers and delivers the pick at PostToolUse, as the harness does.
- 2026-10-09 15:09: ISC-4.1 "ten writing commands": the nine of S4 with isa write counted twice, as its two forms (an ISC and a section), both tested.
- 2026-10-09 15:09: S2: a guarded probe is a lint error (lint.errors judges every probe with classify.bash), so verify and close refuse it through their lint gate; isa write --probe refuses it outright.
- 2026-10-09 15:09: ISC-1.7 kept as is despite Jev 0.49: the existing classifier table and compositions fail on any kind change, which is the claim.
- 2026-10-09 15:09: Seen, out of scope: an escaped backtick inside double quotes still reads as a substitution, so isa decide with \\` in its text next to an ISA path is refused (hit during this build).

## Verification

- Goal: yes — all 8 review findings fixed in runtime/ (classify, commands, engine, gitops, lint), each by a test seen failing first (21 red), 27/27 probes green, every pre-install suite passes
- Ask 1: met — spec docs/2026-10-08-review-fixes-01-spec.md acked and committed (61e6dd9); S1–S8 each delivered and proven
