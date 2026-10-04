---
task: "Tell the model about the Continue pass"
slug: 20261004-174735_continue-pass-visible-to-model
effort: E2
phase: complete
progress: 9/9
started: 2026-10-04T17:47:35
updated: 2026-10-04T17:55:36
root: .
stated_goal: null
asks: ["enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"]
context_sufficient: true
---

## Problem

When the user picks **Continue without ISA**, `_record_choice` grants the pass but returns `{}`, so nothing reaches the model (pi: `ask_answer` → no context; Claude Code: PostToolUse → no context). The only model-facing text left is the pre-ask "If this prompt is a new task, it needs a new ISA (or a reopen)" line and a stale ON block from an earlier prompt, so the model hedges with an `ISA judge (model):` line that belongs only to a Jev outage (TODO.md, session pi-01a10298…, prompt 3).

## Goal

After a Continue pick, on pi and on Claude Code, the model receives a context that names the gate outcome (judge, score, the user's choice), says the Continue pass is active — no ISA, no judge line, the gate returns next prompt — and supersedes the pre-ask "needs a new ISA" line; the injected ON protocol states the pass too; Enable stays as it was, and a Continue at pi's settle never restarts the run.

## Criteria

- [x] ISC-1: pi `ask_answer` continue returns context naming the Continue pass.
- [x] ISC-2: That context names judge, score and the user's choice.
- [x] ISC-3: Claude Code PostToolUse continue returns the same model-facing context.
- [x] ISC-4: With an ISA bound, the context supersedes the pre-ask "new ISA" line.
- [x] ISC-5: The continue context forbids the `ISA judge (model):` line and an ISA.
- [x] ISC-6: The ON protocol block states what a Continue pass means.
- [x] ISC-7: The TODO.md fix items are all ticked.
- [x] ISC-8: Anti: a pi Continue answer carries a `block` that restarts the run.
- [x] ISC-9: Anti: any existing Python or node test fails.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"
  type: unit-test
  kind: behaviour
  check: pi continue context
  threshold: exit 0
  tool: python3 -m unittest tests.test_ask.TestContinueContext.test_pi_continue_context

- isc: ISC-2
  anchors_to: "enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"
  type: unit-test
  kind: behaviour
  check: gate outcome in the context
  threshold: exit 0
  tool: python3 -m unittest tests.test_ask.TestContinueContext.test_continue_names_the_gate

- isc: ISC-3
  anchors_to: "enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"
  type: unit-test
  kind: behaviour
  check: Claude Code continue context
  threshold: exit 0
  tool: python3 -m unittest tests.test_ask.TestContinueContext.test_claude_continue_context

- isc: ISC-4
  anchors_to: "enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"
  type: unit-test
  kind: behaviour
  check: supersedes the pre-ask line
  threshold: exit 0
  tool: python3 -m unittest tests.test_ask.TestContinueContext.test_continue_supersedes_the_pre_ask_line

- isc: ISC-5
  anchors_to: "enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"
  type: unit-test
  kind: behaviour
  check: no ISA, no judge line
  threshold: exit 0
  tool: python3 -m unittest tests.test_ask.TestContinueContext.test_continue_imposes_nothing

- isc: ISC-6
  anchors_to: "enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"
  type: bash
  kind: doc
  check: protocol mentions the pass
  threshold: exit 0
  tool: grep -q 'Continue without ISA' runtime/isa/protocol.md
  fails-when: "protocol.md says nothing about a Continue pick"

- isc: ISC-7
  anchors_to: "enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"
  type: bash
  kind: doc
  check: no open fix item
  threshold: exit 0
  tool: "! grep -q '^- \\[ \\]' TODO.md"
  fails-when: "an unticked `- [ ]` item is left in TODO.md"

- isc: ISC-8
  anchors_to: "enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"
  type: unit-test
  kind: behaviour
  check: no block on continue
  threshold: exit 0
  tool: python3 -m unittest tests.test_ask.TestContinueContext.test_pi_continue_never_blocks
  red: exempt — an Anti guarding the new context against reusing the enable branch's `block`; before the fix there was no context to leak
  fails-when: "the pi continue answer has a `block` key"

- isc: ISC-9
  anchors_to: "enc:v1:0ddf368a:raBIpkiKa8qgOGFZGdxsk58fUMxmtyi9-M6yfn53WKRFGe4ED6L-T_-gf-CoQDVl4B3Uwww4xSvND6QCpQ"
  type: bash
  kind: regression
  check: full suite
  threshold: exit 0
  tool: python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install tests.test_status tests.test_evidence tests.test_shell_changes tests.test_feature_order tests.test_home_and_complete tests.test_seamless_projects tests.test_gate tests.test_commands tests.test_fingerprint tests.test_blocked tests.test_red tests.test_lint_v2 tests.test_purge tests.test_declaration tests.test_logs tests.test_ask tests.test_jev tests.test_m11 tests.test_m12 tests.flow.test_isa_flow 2>/dev/null && node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts >/dev/null 2>&1
  fails-when: "any listed test fails"
```

## Decisions

- 2026-10-04: stated_goal null — candidate: "enc:v1:0ddf368a:fN5VaoRRP-QNcrzV2CKHoKLZxEYMSU3qG8eZvU6ZF58HWmK82Nga93F2ZLu9k-x5XUKElIU0AWtTcwM"
- 2026-10-04: the continue context is returned without `block`: pi's settle path uses `block` to restart the run, which a Continue must never do.
- 2026-10-04: refined: two pi tests (`extension.test.ts`) asserted that a Continue injects nothing — the bug itself; they now assert the Continue context and no ON block.

## Verification

- ISC-1: verified 2026-10-04T17:55:36 — exit 0 in 0.23s — `python3 -m unittest tests.test_ask.TestContinueContext.test_pi_continue_context` (ledger: ad1e780203)
- ISC-2: verified 2026-10-04T17:55:36 — exit 0 in 0.23s — `python3 -m unittest tests.test_ask.TestContinueContext.test_continue_names_the_gate` (ledger: 9678359455)
- ISC-3: verified 2026-10-04T17:55:36 — exit 0 in 0.23s — `python3 -m unittest tests.test_ask.TestContinueContext.test_claude_continue_context` (ledger: dd9e1b009e)
- ISC-4: verified 2026-10-04T17:55:36 — exit 0 in 0.35s — `python3 -m unittest tests.test_ask.TestContinueContext.test_continue_supersedes_the_pre_ask_line` (ledger: c2d7a60a92)
- ISC-5: verified 2026-10-04T17:55:36 — exit 0 in 0.23s — `python3 -m unittest tests.test_ask.TestContinueContext.test_continue_imposes_nothing` (ledger: 236484f55a)
- ISC-6: verified 2026-10-04T17:55:36 — exit 0 in 0.0s — `grep -q 'Continue without ISA' runtime/isa/protocol.md` (ledger: b87bffd7de)
- ISC-7: verified 2026-10-04T17:55:36 — exit 0 in 0.0s — `! grep -q '^- \[ \]' TODO.md` (ledger: 7e32880d25)
- ISC-8: verified 2026-10-04T17:55:36 — exit 0 in 0.23s — `python3 -m unittest tests.test_ask.TestContinueContext.test_pi_continue_never_blocks` (ledger: 19d598c291)
- ISC-9: verified 2026-10-04T17:55:36 — exit 0 in 84.96s — `python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install tests.test_status tests.test_evidence tests.test_shell_changes tests.test_feature_order tests.test_home_and_complete tests.test_seamless_projects tests.test_gate tests.test_commands tests.test_fingerprint tests.test_blocked tests.test_red tests.test_lint_v2 tests.test_purge tests.test_declaration tests.test_logs tests.test_ask tests.test_jev tests.test_m11 tests.test_m12 tests.flow.test_isa_flow 2>/dev/null && node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts >/dev/null 2>&1` (ledger: 543fac1fc2)
- Ask 1: met — all five TODO.md fix items done: Continue context on both harnesses (gate outcome folded in), supersedes the pre-ask line, protocol.md + SKILL.md state the pass, regression tests in tests/test_ask.py.
- Goal: yes — after a Continue pick the model now gets a context naming Jev's score, the user's choice and the pass (no ISA, no judge line), the exact gap that produced the stray `ISA judge (model):` line in the reported session.
