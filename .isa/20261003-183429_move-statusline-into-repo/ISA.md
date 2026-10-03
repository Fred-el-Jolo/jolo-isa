---
task: "Move the ISA statusline into jolo-isa"
slug: 20261003-183429_move-statusline-into-repo
effort: E3
phase: complete
progress: 15/15
started: 2026-10-03T18:34:29
updated: 2026-10-03T18:41:03
root: .
stated_goal: "enc:v1:0ddf368a:UV5iRfvUYU0vMhl_LVttTJ-OP0w9Zsb0SiVPNI8YdFgh8mMyRwK5I1vdc9QOMvyzwVjbknYow9Lh_DKdpYxVU7ZHZRQAFIqqytMvZUXEra98xy8tmn3rFcJ6LeQGKcu_YmBzPxO_10vWBzBrO3aBOw6ICXnqTxkJBFiw-VQDDq8fGKIXaZjRYHTFD1bwHPQOPY9zj7K0SJESqwP5sp5AsiJ03h2sGlCZ_fGVRPy7RrCI9UylvezhkzlPKTT0whlFBpMxrhOgl0HY1U8t_sa8kRFRbh4h_9g4pa9FmWYfYLyAxGKW6EUK7LjAkAnOFz51yulQtK3HZELuSd_9xoyvfINpgBONRApSNsijUw"
stated_goal_source: prompt
asks: ["enc:v1:0ddf368a:_6OcirAS5QkYiDzMDdUyV16B3mVvvwHmt5WUkRj-hyGnxxl7Lq8HgA-GjztTicGW60G1UZBT0r4", "enc:v1:0ddf368a:YqEciyzwoPZDvEHGkWl26aaA7IFOJ6B_MDShWyx9bLeP3SYQGmGo4Bh5MNXi9E_DQrqLMu8BGmCW3Yp1AS1SP2jl8OHcZkoRmo5uz5W_Tg", "enc:v1:0ddf368a:oCPqSR5vKuCZvq77oclcoMWMoBnWRzoRVhhIGSEHjZr9rt7aCGUau52KtUgjjFZI7l6s0YaSdo-5SQ"]
context_sufficient: true
---

## Problem

The Claude Code statusline that renders `isa status --json` lives in a separate repo (`~/dev/progress-outline`, one commit plus an uncommitted rewrite), so a change to the JSON contract needs two repos kept in step, and settings.json has two writers (`install.py` for hooks, `progress-outline/install.sh` → `scripts/wire-settings.cjs` for the statusLine). The mechanism that keeps an existing statusLine (ccstatusline) — `_isaManaged` / `_isaInnerCommand` plus `statusline-wrapper.cjs` — lives only in `wire-settings.cjs`, not in `install.py`.

## Vision

One repo, one installer: `python3 install.py --statusline` puts the ISA rows under whatever statusLine the user already had, re-running it changes nothing, and `--uninstall` gives the old statusLine back byte for byte.

## Out of Scope

Changing how the statusline looks or what `isa status --json` returns. Deleting or editing the progress-outline repo (the user archives it). A pi status display.

## Constraints

`install.py` stays standard-library Python and the single writer of `~/.claude/settings.json`, with its backup-before-write. The composing mechanism keeps the same settings keys (`_isaManaged`, `_isaInnerCommand`, legacy `_taskPlanManaged` / `_taskPlanInnerCommand`) so an existing install migrates in place. The statusline stays opt-in.

## Goal

The statusline lives in `adapters/claude-statusline/` and `install.py --statusline` installs it with the wire-settings mechanism ported: an existing statusLine is kept as the inner command and shown above the ISA rows, re-runs never nest, a progress-outline-era entry migrates, and uninstall restores the previous statusLine.

## Criteria

- [x] ISC-1: The statusline sources and renderer tests live in `adapters/claude-statusline/`.
- [x] ISC-2: The renderer tests pass from the new location.
- [x] ISC-3: `--statusline` keeps an existing statusLine as inner command and its other keys.
- [x] ISC-4: Re-running the statusline install leaves settings.json byte-identical, wrapper not nested.
- [x] ISC-5: A progress-outline-managed statusLine migrates to the installed copy, inner command kept.
- [x] ISC-6: Legacy task-plan keys and the TodoWrite capture hook are removed.
- [x] ISC-7: Uninstall restores the previous statusLine exactly, or removes one it added.
- [x] ISC-8: A plain install refreshes an already-managed statusline's files and command.
- [x] ISC-9: The user's statusline `config.json` survives a reinstall.
- [x] ISC-10: The installed wrapper prints the inner command's output above the ISA rows.
- [x] ISC-11: AGENTS.md documents the adapter, the `--statusline` flag and its tests.
- [x] ISC-12: Anti: a plain install adds or changes an unmanaged statusLine.
- [x] ISC-13: Anti: a `wire-settings.cjs` second settings writer exists in the repo.
- [x] ISC-14: Anti: any existing unit, pi or install test fails.
- [x] ISC-15: Anti: the runtime gains a non-stdlib import.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "enc:v1:0ddf368a:_6OcirAS5QkYiDzMDdUyV16B3mVvvwHmt5WUkRj-hyGnxxl7Lq8HgA-GjztTicGW60G1UZBT0r4"
  type: bash
  kind: file
  check: every source present
  threshold: exit 0
  tool: cd adapters/claude-statusline && test -f harness.ts -a -f isa.ts -a -f renderer.ts -a -f types.ts -a -f config.schema.json -a -f scripts/statusline-wrapper.cjs -a -f test/renderer.test.ts -a -f README.md
  fails-when: "a source file was left behind in progress-outline"

- isc: ISC-2
  anchors_to: "enc:v1:0ddf368a:_6OcirAS5QkYiDzMDdUyV16B3mVvvwHmt5WUkRj-hyGnxxl7Lq8HgA-GjztTicGW60G1UZBT0r4"
  type: unit-test
  kind: behaviour
  check: node renderer tests
  threshold: exit 0
  tool: node --test adapters/claude-statusline/test/renderer.test.ts

- isc: ISC-3
  anchors_to: "enc:v1:0ddf368a:oCPqSR5vKuCZvq77oclcoMWMoBnWRzoRVhhIGSEHjZr9rt7aCGUau52KtUgjjFZI7l6s0YaSdo-5SQ"
  type: unit-test
  kind: behaviour
  check: compose existing statusLine
  threshold: exit 0
  tool: python3 -m unittest tests.test_install.TestStatusline.test_composes_existing

- isc: ISC-4
  anchors_to: "enc:v1:0ddf368a:oCPqSR5vKuCZvq77oclcoMWMoBnWRzoRVhhIGSEHjZr9rt7aCGUau52KtUgjjFZI7l6s0YaSdo-5SQ"
  type: unit-test
  kind: behaviour
  check: idempotent, no nesting
  threshold: exit 0
  tool: python3 -m unittest tests.test_install.TestStatusline.test_idempotent_no_nesting

- isc: ISC-5
  anchors_to: "enc:v1:0ddf368a:oCPqSR5vKuCZvq77oclcoMWMoBnWRzoRVhhIGSEHjZr9rt7aCGUau52KtUgjjFZI7l6s0YaSdo-5SQ"
  type: unit-test
  kind: behaviour
  check: migrate a progress-outline entry
  threshold: exit 0
  tool: python3 -m unittest tests.test_install.TestStatusline.test_migrates_progress_outline_entry

- isc: ISC-6
  anchors_to: "enc:v1:0ddf368a:oCPqSR5vKuCZvq77oclcoMWMoBnWRzoRVhhIGSEHjZr9rt7aCGUau52KtUgjjFZI7l6s0YaSdo-5SQ"
  type: unit-test
  kind: behaviour
  check: legacy keys and hook gone
  threshold: exit 0
  tool: python3 -m unittest tests.test_install.TestStatusline.test_legacy_task_plan

- isc: ISC-7
  anchors_to: "enc:v1:0ddf368a:oCPqSR5vKuCZvq77oclcoMWMoBnWRzoRVhhIGSEHjZr9rt7aCGUau52KtUgjjFZI7l6s0YaSdo-5SQ"
  type: unit-test
  kind: behaviour
  check: uninstall both cases
  threshold: exit 0
  tool: python3 -m unittest tests.test_install.TestStatusline.test_uninstall_restores tests.test_install.TestStatusline.test_uninstall_removes_added

- isc: ISC-8
  anchors_to: "enc:v1:0ddf368a:_6OcirAS5QkYiDzMDdUyV16B3mVvvwHmt5WUkRj-hyGnxxl7Lq8HgA-GjztTicGW60G1UZBT0r4"
  type: unit-test
  kind: behaviour
  check: plain install refreshes managed
  threshold: exit 0
  tool: python3 -m unittest tests.test_install.TestStatusline.test_plain_install_refreshes_managed

- isc: ISC-9
  anchors_to: "enc:v1:0ddf368a:_6OcirAS5QkYiDzMDdUyV16B3mVvvwHmt5WUkRj-hyGnxxl7Lq8HgA-GjztTicGW60G1UZBT0r4"
  type: unit-test
  kind: behaviour
  check: config.json kept
  threshold: exit 0
  tool: python3 -m unittest tests.test_install.TestStatusline.test_config_survives_reinstall

- isc: ISC-10
  anchors_to: "enc:v1:0ddf368a:oCPqSR5vKuCZvq77oclcoMWMoBnWRzoRVhhIGSEHjZr9rt7aCGUau52KtUgjjFZI7l6s0YaSdo-5SQ"
  type: unit-test
  kind: behaviour
  check: wrapper end to end with a fake isa
  threshold: exit 0
  tool: python3 -m unittest tests.test_install.TestStatusline.test_wrapper_composes_output

- isc: ISC-11
  anchors_to: "enc:v1:0ddf368a:_6OcirAS5QkYiDzMDdUyV16B3mVvvwHmt5WUkRj-hyGnxxl7Lq8HgA-GjztTicGW60G1UZBT0r4"
  type: bash
  kind: doc
  check: AGENTS.md mentions adapter, flag, node test; no pointer to progress-outline as the home
  threshold: exit 0
  tool: grep -q 'adapters/claude-statusline/' AGENTS.md && grep -q 'install.py --statusline' AGENTS.md && grep -q 'node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts' AGENTS.md && ! grep -q 'lives in `~/dev/progress-outline`' AGENTS.md && ! grep -q 'in `~/dev/progress-outline`' future/STATUSLINE.md
  fails-when: "AGENTS.md still sends readers to progress-outline or omits the flag or tests"

- isc: ISC-12
  anchors_to: "enc:v1:0ddf368a:oCPqSR5vKuCZvq77oclcoMWMoBnWRzoRVhhIGSEHjZr9rt7aCGUau52KtUgjjFZI7l6s0YaSdo-5SQ"
  type: unit-test
  kind: behaviour
  check: plain install leaves unmanaged statusLine alone
  threshold: exit 0
  tool: python3 -m unittest tests.test_install.TestStatusline.test_plain_install_leaves_unmanaged
  fails-when: "an unmanaged statusLine differs after a plain install"

- isc: ISC-13
  anchors_to: "enc:v1:0ddf368a:YqEciyzwoPZDvEHGkWl26aaA7IFOJ6B_MDShWyx9bLeP3SYQGmGo4Bh5MNXi9E_DQrqLMu8BGmCW3Yp1AS1SP2jl8OHcZkoRmo5uz5W_Tg"
  type: bash
  kind: file
  check: no second writer
  threshold: exit 0
  tool: test -z "$(find adapters install.py -name 'wire-settings*')"
  fails-when: "wire-settings.cjs was copied into the repo"

- isc: ISC-14
  anchors_to: "enc:v1:0ddf368a:_6OcirAS5QkYiDzMDdUyV16B3mVvvwHmt5WUkRj-hyGnxxl7Lq8HgA-GjztTicGW60G1UZBT0r4"
  type: unit-test
  kind: regression
  check: suite + pi + statusline
  threshold: exit 0
  tool: python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install tests.test_status tests.test_evidence tests.test_shell_changes tests.test_feature_order tests.test_home_and_complete tests.test_seamless_projects tests.test_gate tests.test_commands tests.test_fingerprint tests.test_blocked tests.test_red tests.test_lint_v2 tests.test_purge tests.test_declaration tests.test_logs tests.test_ask tests.test_jev tests.test_m11 tests.test_m12 && node --test adapters/pi/test/extension.test.ts
  fails-when: "any test fails"

- isc: ISC-15
  anchors_to: "enc:v1:0ddf368a:_6OcirAS5QkYiDzMDdUyV16B3mVvvwHmt5WUkRj-hyGnxxl7Lq8HgA-GjztTicGW60G1UZBT0r4"
  type: bash
  kind: regression
  check: stdlib checker
  threshold: exit 0
  tool: python3 tests/check_stdlib.py runtime/ && mkdir -p /tmp/isa-stdlib-check && cp install.py /tmp/isa-stdlib-check/ && python3 tests/check_stdlib.py /tmp/isa-stdlib-check
  fails-when: "runtime or install.py imports a third-party module"
```

## Features

```yaml
- name: adapter-copy
  description: copy the statusline sources and tests into adapters/claude-statusline, README adjusted
  satisfies: [ISC-1, ISC-2, ISC-13]
  depends_on: []
  parallelizable: true
- name: installer-statusline
  description: port wire-settings into install.py behind --statusline, with tests
  satisfies: [ISC-3, ISC-4, ISC-5, ISC-6, ISC-7, ISC-8, ISC-9, ISC-10, ISC-12, ISC-15]
  depends_on: [adapter-copy]
  parallelizable: false
- name: docs
  description: AGENTS.md layout, install, Future B, test list; future/STATUSLINE.md
  satisfies: [ISC-11, ISC-14]
  depends_on: [installer-statusline]
  parallelizable: false
```

## Decisions

- 2026-10-03 18:40: Port `wire-settings.cjs` into `install.py` rather than call it, so settings.json keeps one writer with one backup; `statusline-wrapper.cjs` stays (it runs at render time, not install time).
- 2026-10-03 18:40: The statusline is installed as a copy in `<prefix>/share/isa/statusline`, next to the runtime, so settings.json never points into a checkout; `--uninstall` removes it with the runtime.
- 2026-10-03 18:45: refined: ISC-15 probe — `check_stdlib.py` reads only its first argument, so `install.py` was never checked; it now checks a copy of install.py in its own folder.
- 2026-10-03 18:55: refined: ISC-11 probe — AGENTS.md lists the renderer test in the same `node --test` call as the pi test, so the grep now matches that whole call; the claim was right, the probe too literal.
- 2026-10-03 18:40: Copied from progress-outline's working tree, which holds an uncommitted rewrite; its single commit is the old task-plan version.

## Verification

- ISC-1: verified 2026-10-03T18:41:03 — exit 0 in 0.0s — `cd adapters/claude-statusline && test -f harness.ts -a -f isa.ts -a -f renderer.ts -a -f types.ts -a -f config.schema.json -a -f scripts/statusline-wrapper.cjs -a -f test/renderer.test.ts -a -f README.md` (ledger: 55bdc6c4e9)
- ISC-2: verified 2026-10-03T18:41:03 — exit 0 in 0.17s — `node --test adapters/claude-statusline/test/renderer.test.ts` (ledger: 04bf7d489f)
- ISC-13: verified 2026-10-03T18:41:03 — exit 0 in 0.0s — `test -z "$(find adapters install.py -name 'wire-settings*')"` (ledger: 6350b2f905)
- ISC-15: verified 2026-10-03T18:41:03 — exit 0 in 0.18s — `python3 tests/check_stdlib.py runtime/ && mkdir -p /tmp/isa-stdlib-check && cp install.py /tmp/isa-stdlib-check/ && python3 tests/check_stdlib.py /tmp/isa-stdlib-check` (ledger: 76bec430a6)
- ISC-3: verified 2026-10-03T18:41:03 — exit 0 in 0.11s — `python3 -m unittest tests.test_install.TestStatusline.test_composes_existing` (ledger: 34d4d1d1ca)
- ISC-4: verified 2026-10-03T18:41:03 — exit 0 in 0.17s — `python3 -m unittest tests.test_install.TestStatusline.test_idempotent_no_nesting` (ledger: 81a4657046)
- ISC-5: verified 2026-10-03T18:41:03 — exit 0 in 0.15s — `python3 -m unittest tests.test_install.TestStatusline.test_migrates_progress_outline_entry` (ledger: bd88b0737e)
- ISC-6: verified 2026-10-03T18:41:03 — exit 0 in 0.11s — `python3 -m unittest tests.test_install.TestStatusline.test_legacy_task_plan` (ledger: 330898619d)
- ISC-7: verified 2026-10-03T18:41:03 — exit 0 in 0.23s — `python3 -m unittest tests.test_install.TestStatusline.test_uninstall_restores tests.test_install.TestStatusline.test_uninstall_removes_added` (ledger: 88f4cedd82)
- ISC-8: verified 2026-10-03T18:41:03 — exit 0 in 0.17s — `python3 -m unittest tests.test_install.TestStatusline.test_plain_install_refreshes_managed` (ledger: a4d0e31b9b)
- ISC-9: verified 2026-10-03T18:41:03 — exit 0 in 0.16s — `python3 -m unittest tests.test_install.TestStatusline.test_config_survives_reinstall` (ledger: f00cdb1bbb)
- ISC-10: verified 2026-10-03T18:41:03 — exit 0 in 0.24s — `python3 -m unittest tests.test_install.TestStatusline.test_wrapper_composes_output` (ledger: 119b767bce)
- ISC-12: verified 2026-10-03T18:41:03 — exit 0 in 0.14s — `python3 -m unittest tests.test_install.TestStatusline.test_plain_install_leaves_unmanaged` (ledger: c809ee44d2)
- ISC-14: verified 2026-10-03T18:41:03 — exit 0 in 84.43s — `python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install tests.test_status tests.test_evidence tests.test_shell_changes tests.test_feature_order tests.test_home_and_complete tests.test_seamless_projects tests.test_gate tests.test_commands tests.test_fingerprint tests.test_blocked tests.test_red tests.test_lint_v2 tests.test_purge tests.test_declaration tests.test_logs tests.test_ask tests.test_jev tests.test_m11 tests.test_m12 && node --test adapters/pi/test/extension.test.ts` (ledger: 56471e651b)
- ISC-11: verified 2026-10-03T18:41:03 — exit 0 in 0.01s — `grep -q 'adapters/claude-statusline/' AGENTS.md && grep -q 'install.py --statusline' AGENTS.md && grep -q 'node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts' AGENTS.md && ! grep -q 'lives in `~/dev/progress-outline`' AGENTS.md && ! grep -q 'in `~/dev/progress-outline`' future/STATUSLINE.md` (ledger: 0f91fda37a)
- Ask 1: met — the sources live in `adapters/claude-statusline/`, `install.py` installs them, and the live settings.json now points at `~/.local/share/isa/statusline` (backup `settings.json.isa-backup-20261003-184041`); the progress-outline repo was left untouched for the user to archive.
- Ask 2: met — answered in the reply: `wire-settings.cjs` is progress-outline's `scripts/wire-settings.cjs`, run by its `install.sh`; jolo-isa's `install.py` never touched `statusLine` before this change.
- Ask 3: met — the same keys (`_isaManaged`, `_isaInnerCommand`, legacy `_taskPlan*`) and the same `statusline-wrapper.cjs` composition, now in `install.py` (ISC-3..7, ISC-10); live render shows the ccstatusline line above the ISA rows.
- Goal: yes — the statusline is in the repo, `install.py --statusline` composes an existing statusLine exactly as wire-settings did, migrates the progress-outline entry (done on the real settings.json, ccstatusline kept), and uninstall restores it.
