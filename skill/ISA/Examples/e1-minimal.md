---
task: "Add a --no-color flag to the dump CLI"
slug: 20260428-141500_no-color-flag
effort: E1
phase: draft
progress: 0/4
started: 2026-04-28T14:15:00
updated: 2026-04-28T14:20:00
root: /home/me/dev/dump
asks: ["add a --no-color flag"]
---

<!-- Fictitious example ("dump" is a teaching name). E1: one level of criteria, no spec, no Vision / Out of Scope / Constraints. -->

## Problem

`dump.ts` always prints ANSI colour codes, so its output piped into a file or another tool carries escape sequences.

## Goal

`dump.ts --no-color`, or `NO_COLOR=1`, prints plain text; the default output on a terminal keeps its colours.

## Criteria

- [ ] ISC-1: `dump.ts --no-color` prints no ANSI escape sequence.
- [ ] ISC-2: `NO_COLOR=1 dump.ts` prints no ANSI escape sequence.
- [ ] ISC-3: Plain `dump.ts` on a terminal still prints colours.
- [ ] ISC-4: Anti: `dump.ts --no-color` writes anything to stderr.

## Test Strategy

```yaml
- isc: ISC-1
  kind: behaviour
  tool: '! ./dump.ts --no-color fixtures/a.json | grep -qP "\x1b\["'
- isc: ISC-2
  kind: behaviour
  tool: '! NO_COLOR=1 ./dump.ts fixtures/a.json | grep -qP "\x1b\["'
- isc: ISC-3
  kind: regression
  tool: 'script -qc "./dump.ts fixtures/a.json" /dev/null | grep -qP "\x1b\["'
  fails-when: "the terminal output has lost its colour codes"
- isc: ISC-4
  kind: regression
  tool: 'test -z "$(./dump.ts --no-color fixtures/a.json 2>&1 >/dev/null)"'
  fails-when: "--no-color prints a notice or a warning on stderr"
```
