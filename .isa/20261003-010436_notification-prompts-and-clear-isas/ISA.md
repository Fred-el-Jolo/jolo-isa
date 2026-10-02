---
task: "Skip notification prompts; clear the old ISAs"
slug: 20261003-010436_notification-prompts-and-clear-isas
effort: E2
phase: complete
progress: 7/7
started: 2026-10-03T01:04:36
updated: 2026-10-03T01:18:30
root: .
stated_goal: null
asks: ["enc:v1:0ddf368a:KKiaSDWyLBYYlL83dZqD41IfLfniYuNbziCfK4uUEbnpymeSJyuWaTHBxRfu9cvV72mQNTIZjeNkkw", "enc:v1:0ddf368a:8KFIxixWtdh_tSsLXVD9iBV1LztHFAc8gnrNe2DKBqvVDf6jtVXoz6Wt0mygVQwodOOprNT_JcGjYPTr"]
context_sufficient: true
---

## Problem

A background task's completion reaches the prompt hook as a prompt made only of `<task-notification>` blocks. The engine judges it like a user prompt: it clears the user's Continue pass and asks the user again (seen during the M12 live test). Separately, the user wants the pre-M12 ISAs under `~/.isa` gone.

## Goal

A prompt made only of system notification blocks is not judged and changes nothing the user's last answer set (the pass, the gate record, the turn start); it is logged as a notification. And the 46 pre-M12 task ISA folders under `~/.isa` are deleted with their ledgers, leaving the key, config and machine state.

## Criteria

- [x] ISC-1: A notification-only prompt calls no judge and injects nothing.
- [x] ISC-2: A notification-only prompt keeps the Continue pass: a write after it is allowed.
- [x] ISC-3: A notification-only prompt is logged with `notification: true`.
- [x] ISC-4: Anti: a user prompt that merely contains a notification block is skipped.
- [x] ISC-5: No task ISA folder remains directly under `~/.isa` (outside `_state`).
- [x] ISC-6: No ledger file of the old ISAs remains in `~/.isa/_state/evidence`.
- [x] ISC-7: Anti: the key, `config.json`, sessions, prompts or debug logs are deleted.

## Test Strategy

```yaml
- isc: ISC-1
  type: unit-test
  kind: behaviour
  check: fake jev; notification prompt; no jev call, empty output
  threshold: exit 0
  tool: python3 -m unittest tests.test_m12.TestNotification.test_no_judge

- isc: ISC-2
  type: unit-test
  kind: behaviour
  check: Continue, notification, Write allowed
  threshold: exit 0
  tool: python3 -m unittest tests.test_m12.TestNotification.test_pass_kept

- isc: ISC-3
  type: unit-test
  kind: behaviour
  check: prompt row field
  threshold: exit 0
  tool: python3 -m unittest tests.test_m12.TestNotification.test_logged

- isc: ISC-4
  type: unit-test
  kind: behaviour
  check: text before the block is judged
  threshold: exit 0
  tool: python3 -m unittest tests.test_m12.TestNotification.test_mixed_is_judged
  fails-when: "a user prompt with a notification block inside is skipped (no judge call)"

- isc: ISC-5
  type: bash
  kind: file
  check: folders under ~/.isa other than _state
  threshold: exit 0
  tool: test -z "$(find ~/.isa -name ISA.md -not -path '*/_state/*')"
  fails-when: "an ISA.md is still found under ~/.isa outside _state"

- isc: ISC-6
  type: bash
  kind: file
  check: evidence folder empty
  threshold: exit 0
  tool: test -z "$(ls -A ~/.isa/_state/evidence 2>/dev/null)"
  fails-when: "an old ledger file is still there"

- isc: ISC-7
  type: bash
  kind: file
  check: kept files
  threshold: exit 0
  tool: test -f ~/.isa/key && test -d ~/.isa/_state/sessions && test -d ~/.isa/_state/prompts && test -d ~/.isa/_state/logs
  fails-when: "the key or the machine state was deleted"
```

## Decisions

- 2026-10-03 01:05: "the bug you found out" = a `<task-notification>` prompt is judged like a user prompt and clears the Continue pass (M12 live test).
- 2026-10-03 01:05: a notification is recognised only when the whole prompt is notification blocks (`<task-notification>…</task-notification>`, whitespace between): anything the user typed makes it a user prompt.
- 2026-10-03 01:05: "the existing ISAs" = the 46 task ISA folders under `~/.isa` from before M12 (dev-jolo-isa 44, dev-jev-kit 1, dev-jolo-isa-tests-evals-results 1) and their 53-ish ledgers in `_state/evidence`; the M12 ISAs in the repo (this one, the new project ISA) stay. Sessions, prompt logs, debug logs, the key and the config stay: they are machine state, not ISAs. `config.json` absent today is fine (ISC-7 doesn't require it).

## Verification

- ISC-1: verified 2026-10-03T01:18:30 — exit 0 in 0.14s — `python3 -m unittest tests.test_m12.TestNotification.test_no_judge` (ledger: 1daf10c252)
- ISC-2: verified 2026-10-03T01:18:30 — exit 0 in 0.46s — `python3 -m unittest tests.test_m12.TestNotification.test_pass_kept` (ledger: 388e5e48e8)
- ISC-3: verified 2026-10-03T01:18:30 — exit 0 in 0.13s — `python3 -m unittest tests.test_m12.TestNotification.test_logged` (ledger: ae54df7ceb)
- ISC-4: verified 2026-10-03T01:18:30 — exit 0 in 0.16s — `python3 -m unittest tests.test_m12.TestNotification.test_mixed_is_judged` (ledger: e52b7c9477)
- ISC-5: verified 2026-10-03T01:18:30 — exit 0 in 0.0s — `test -z "$(find ~/.isa -name ISA.md -not -path '*/_state/*')"` (ledger: 92237bc636)
- ISC-7: verified 2026-10-03T01:18:30 — exit 0 in 0.0s — `test -f ~/.isa/key && test -d ~/.isa/_state/sessions && test -d ~/.isa/_state/prompts && test -d ~/.isa/_state/logs` (ledger: fcb415bda9)
- ISC-6: verified 2026-10-03T01:18:30 — exit 0 in 0.0s — `test -z "$(ls -A ~/.isa/_state/evidence 2>/dev/null)"` (ledger: 9a698038f9)
- Ask 1: met — 46 pre-M12 ISA folders deleted (ISC-5), their ledgers deleted by the user (the ledger guard refuses the model, ISC-6), plus a dangling `~/.isa/.isa` link folder left by the old cross-project indexing; key and machine state kept (ISC-7)
- Ask 2: met — notification-only prompts are skipped: no judge, the Continue pass kept, logged (ISC-1..4)
- Goal: yes — the bug is fixed and covered by tests (357 pass), and `~/.isa` now holds only the key and `_state`
