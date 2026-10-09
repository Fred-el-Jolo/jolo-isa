---
task: "duck --help redesign"
slug: 20260411-191500_duck-help
effort: E3
phase: build
progress: 3/9
started: 2026-04-11T19:15:00
updated: 2026-04-13T16:00:00
root: /home/me/dev/duck
spec: specs/e3-help-redesign.spec.md
spec_hash: 38ae5805
acked: "2026-04-11 #ea4a6b4a"
reviewed: 70bef67d
---

<!-- Fictitious example ("duck" is a teaching placeholder). E3: three levels of criteria, common ground (ISC-0), a context leaf, a manual leaf, Decisions, the review, mid-build. -->

## Problem

`duck --help` prints 187 lines in declaration order; new users give up on it (median 95 s to a first real command).

## Vision

A first-time user reads the top of the screen, types one of the two examples within 15 seconds, and it works.

## Out of Scope

New flags or behaviour, the man page, an interactive `duck help`, colour changes.

## Principles

- The first screen is the whole experience for most new users; the reference comes after it.
- Examples teach faster than prose.

## Constraints

- At most 100 lines, every line at most 80 columns, plain text.
- Every flag of the current help appears, and `duck --help | rg <flag>` still finds each.

## Goal

`duck --help` fits 100 lines at 80 columns, opens with a one-sentence summary and the two most common invocations, and keeps every flag findable with `grep`.

## Criteria

- [x] ISC-0: Common ground: one source for every flag.
  - [x] ISC-0.1: The help screen is rendered from the single flag table in `src/flags.ts`.
- [x] ISC-1: The top of the screen teaches duck.
  - [x] ISC-1.1: The first non-blank line is one sentence of 80 characters or less.
  - [x] ISC-1.2: The examples block runs.
    - [x] ISC-1.2.1: The examples block holds exactly two invocations.
- [0/3] ISC-2: The flag reference is complete and ordered.
  - [ ] ISC-2.1: At most four category headers, flags alphabetical within each.
  - [ ] ISC-2.2: Every old flag appears, and `test/help-grep.sh` passes.
  - [ ] ISC-2.3: Each flag's short form (`-q`, `-v`) sits next to its long form.
- [0/3] ISC-3: The whole screen works for a new user.
  - [ ] ISC-3.1: The output is at most 100 lines, none over 80 columns.
  - [ ] ISC-3.2: In a five-user test the median time to a first command is 30 s or less.
  - [ ] ISC-3.3: Anti: `duck --help`, `duck -h` and `duck help` print different output.

## Test Strategy

```yaml
- isc: ISC-0.1
  serves: S1+S2
  kind: regression
  tool: python3 -m unittest tests.test_help.SingleSource
  fails-when: "a part of the help text is written by hand instead of rendered from the flag table"
  why: the examples (S1) and the reference (S2) both print flags; two sources would drift apart
- isc: ISC-1.1
  anchors_to: S1
  kind: behaviour
  tool: test "$(./duck --help | grep -m1 . | wc -c)" -le 81
- isc: ISC-1.2.1
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_help.Examples
- isc: ISC-2.1
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_help.Categories
- isc: ISC-2.2
  anchors_to: S2
  kind: regression
  tool: ./test/help-grep.sh
  fails-when: "a flag of the old help is missing from the new output"
- isc: ISC-2.3
  anchors_to: S2
  kind: behaviour
  tool: ./test/help-short-forms.sh
  source: context
  why: support tickets quote the short forms; the spec only lists the flag names
- isc: ISC-3.1
  anchors_to: S3
  kind: behaviour
  tool: 'test "$(./duck --help | wc -l)" -le 100 && ! ./duck --help | grep -q ".\{81\}"'
- isc: ISC-3.2
  anchors_to: S3
  kind: manual
- isc: ISC-3.3
  anchors_to: S3
  kind: regression
  tool: 'test "$(./duck --help)" = "$(./duck -h)" && test "$(./duck --help)" = "$(./duck help)"'
  fails-when: "one of the three entry points prints something else"
```

## Decisions

- 2026-04-11 19:40: the two examples are the top two invocations of 30 days of telemetry, not a guess.
- 2026-04-12 10:05: dead end — a two-column flag layout broke the 80-column limit for 6 flags; back to one column.

## Review

Reviewed 2026-04-11 19:50 · criteria #70bef67d · Jev: 1 request, 12 questions
- shared: the examples (S1) and the reference (S2) both print flags from somewhere — ISC-0.1, one flag table, built first
- prerequisites: none beyond ISC-0
- contradictions: none
- drift: none
- gaps: a short form could vanish while every long flag stays findable with grep — ISC-2.3
- context: ISC-2.3 (support tickets quote the short forms)

Flags (each needs an answer before the ISA ack):
- R1: serves ISC-3.2 — no 0.74 ≥ 0.70 — Does criterion ISC-3.2 ("In a five-user test the median time to a first command is 30 s or less.", see `criteria`) help solve the spec's stated Problem and reach its Goal, and deliver what section S3 ("Whole screen") asks for? Answer yes when the Problem needs what it claims; no when it is unrelated to the Problem and the Goal, or only restates a detail no part of the spec asks for. — answer: rebuttal: the Problem is new users giving up (median 95 s); only a user test shows the time to a first command fell

## Verification

- ISC-0.1: red 2026-04-12 08:40 exit 1 — `python3 -m unittest tests.test_help.SingleSource`
- ISC-0.1: verified 2026-04-12 08:55 exit 0 — `python3 -m unittest tests.test_help.SingleSource`
- ISC-1.1: red 2026-04-12 09:00 exit 1 — `test "$(./duck --help | grep -m1 . | wc -c)" -le 81`
- ISC-1.1: verified 2026-04-12 11:30 exit 0 — `test "$(./duck --help | grep -m1 . | wc -c)" -le 81`
- ISC-1.2.1: red 2026-04-12 09:00 exit 1 — `python3 -m unittest tests.test_help.Examples`
- ISC-1.2.1: verified 2026-04-12 11:31 exit 0 — `python3 -m unittest tests.test_help.Examples`
