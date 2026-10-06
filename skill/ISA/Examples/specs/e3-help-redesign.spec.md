---
status: "acked 2026-04-11 #38ae5805"
effort: E3
---

<!-- Fictitious example ("duck" is a teaching placeholder), the spec behind Examples/e3-help-redesign.md. -->

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

## Out of scope

New flags or behaviour, the man page, an interactive `duck help`, colour changes.

## Constraints

- At most 100 lines, every line at most 80 columns, plain text.
- Every flag of the current help appears, and `duck --help | rg <flag>` still finds each.

## Approaches

1. Summary and examples first, then the flags grouped by category, then a footer (chosen): the first screen shows what a new user needs, and the full reference stays on the same page.
2. A short help plus `duck --help --all`: it splits the reference and breaks scripts that grep `--help`. Rejected.

## S1 — Summary and examples

The top of the screen: one sentence on what duck does, then the two most common invocations.
Accepted when:
- the first non-blank line is one sentence of at most 80 characters
- the examples block holds exactly 2 invocations, each runs and exits 0 against the fixtures

## S2 — Flag reference

Every flag, grouped by category; each entry is the signature, then a 4-space-indented description.
Accepted when:
- at most 4 category headers, flags in alphabetical order within each
- every flag of the old 187-line help appears, and `test/help-grep.sh` passes

## S3 — Whole screen

The output as a new user sees it.
Accepted when:
- the output is at most 100 lines, none over 80 columns
- in a five-user test, the median time from `--help` to a first real command is 30 s or less

## Decisions

- 2026-04-11: the split help rejected (see Approaches).

## Open questions
