---
status: acked 2026-04-11 #21f7ab60
effort: E3
---

<!-- Fictitious example, the spec behind Examples/e3-help-redesign.md ("duck" is a teaching placeholder). Its project path would be docs/spec/2026-04-11-duck-help.md. -->

# duck --help redesign

## Problem
`duck --help` prints 187 lines, one block per flag in declaration order, with the first example at line 142. New users give up on it: the median time from `--help` to a first real command is 95 s.

## Goal
`duck --help` fits 100 lines at 80 columns, opens with a one-sentence summary and the two most common invocations, and keeps every flag findable with `grep`.
Said:
- make `duck --help` usable for someone who has never run duck
Assumed:
- "usable" means a new user's median time from `--help` to a first real command drops from 95 s to 30 s or less.
- the reference content stays as it is; only layout, order and density change.
- the two examples are the top two invocations in 30 days of telemetry.

## Out of scope
New flags or behaviour, the man page (`man duck` stays the deep reference), an interactive `duck help`, colour changes, localisation.

## Constraints
- At most 100 lines, every line at most 80 columns, plain text: no terminal escapes for the layout.
- Every flag of the current help appears in the new one, and `duck --help | rg <flag>` still finds each.
- `duck --help` is rendered at build time from the one template `templates/help.txt`.

## Approaches
1. Summary and examples first, then the flags grouped by category, then a footer (chosen): the first 30 seconds show what a new user needs, and the full reference stays on the same screen.
2. A short help plus `duck --help --all`: shorter, but it splits the reference and breaks scripts that grep `--help`. Rejected.
3. A pager with sections: needs a pager everywhere, and the help stops being pipeable. Rejected.

## S1 — Summary and examples
The top of the screen: one sentence on what duck does, then the two most common invocations.
Accepted when:
- [ ] A1: the first non-blank line is one sentence of at most 80 characters
- [ ] A2: the examples block holds exactly 2 invocations, each with a one-line gloss
- [ ] A3: each example runs and exits 0 against the test fixtures

## S2 — Flag reference
Every flag, grouped by category; each entry is two lines, the signature, then a 4-space-indented description.
Accepted when:
- [ ] A1: at most 4 category headers, with the flags in alphabetical order within each
- [ ] A2: every flag of the old 187-line help appears, and `test/help-grep.sh` passes
- [ ] A3: no flag description is over 80 characters or wraps onto a second line

## S3 — Footer
Where to go next, after the reference.
Accepted when:
- [ ] A1: exactly three items: the man page, the docs URL, the version with its short sha
- [ ] A2: the version and the sha come from build-time placeholders, never typed by hand

## S4 — Rollout
The new template ships behind a build flag for one release, then becomes the default.
Accepted when:
- [ ] A1: `duck --help`, `duck -h` and `duck help` print the same output and exit 0
- [ ] A2: the whole output is at most 100 lines, none over 80 columns
- [ ] A3: in a five-user test, the median time from `--help` to a first real command is 30 s or less

## Decisions
- 2026-04-11: the split help and the pager rejected (see Approaches).

## Open questions
