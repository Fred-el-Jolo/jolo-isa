---
task: "Diagnose ISA continue-pass bug, write jolo-isa TODO"
slug: 20261003-184422_isa-gate-continue-bug
effort: E2
phase: complete
progress: 5/5
started: 2026-10-03T18:44:22
updated: 2026-10-05T21:35:00
root: .
stated_goal: "enc:v1:0ddf368a:0EddpHu5YWl-XdXl4V-jNi5JZg3CEf8DWfNpes9qOx0aTNUzqeoo1oZCfvnZBmwhS4p2HmT9s98u8Bso1oTeGHDBI8J0tG68rdrtUAypUtq19WNWdddc1gFa6qta_-Gb0BXb6IQ"
stated_goal_source: prompt
asks:
  - "enc:v1:0ddf368a:C3Fc2MyF3vULrbcvs7eO5ESXXLwbaxmMmkbaS5KfSkJpYGlhgBGL3wo4DdYgTOg"
  - "enc:v1:0ddf368a:I1otCIt-Fxhm8xesHxg4KCM5UYhG3x7FUo71iw_tnAht0_m8TJnBn_7e8Mu2bc2xeDsp37ffy5RXphaKFwk3f1BC_yMsGiqey-VGoP1TAr8J2VI"
context_sufficient: true
frozen: true
---

## Problem

On the session's second prompt (token analysis) the ISA gate behaved per spec — Jev scored 0.58, the pi dialog asked, the user chose "Continue without ISA" — yet the model answered with an `ISA judge (model): no` line, as if it had decided itself, overriding the user's pick. Root cause (verified in `runtime/isa/engine.py` and `adapters/pi/isa.ts`): the Continue pass is granted in engine state (`st["pass"] = pid`) but `_record_choice`/`_ask_answer` return `{}` for a continue choice — the model-facing injection after the pick is **empty**, while the only context the model did get (`_q1_ask`'s `pre` line, injected before the dialog) still says "If this prompt is a new task, it needs a new ISA (or a reopen)". Gate warns ("ISA gate — Jev 0.58 → asking you") are UI-only (`ctx.ui.notify`), never model context. The model is left with the stale ON-block from the previous prompt ("the turn can't end without a bound ISA… put `ISA judge (model): …` in your answer") and no signal that a Continue pass exists — so it hedges exactly as observed. The engine and enforcement worked; the model-facing contract after a Continue pick is the broken half.

## Constraints

- Analysis is grounded in the engine's own logs (`~/.isa/_state/logs/2026-10-03.jsonl`, prompt ids `pi-muslvrrwsigh-1..4`) and repo source — not recollection.
- The deliverable is a TODO file only: no source fix in this task (the user asked for analysis + TODO, not the fix).
- TODO goes in the jolo-isa repo root as `TODO.md`.

## Goal

"enc:v1:0ddf368a:qkUbOf3NmHT4LAhbrOzoreXTqN9JGacJqdtQpReuKJKpojRnAU4JHKDYHY21SnQubp_dkmGKdhXtZq5Jc8n2GfVj5zgyb105dr8fmT6LSovKmxV2HGSqikTlP6dOHdJbvyLT"

Done = `~/dev/jolo-isa/TODO.md` exists, documenting the diagnosed defect chain with its log evidence and exact code references (`_record_choice`/`_ask_answer` in `runtime/isa/engine.py`, the `judge()` flow in `adapters/pi/isa.ts`), and listing concrete fix items (model-facing context on Continue, superseding the stale pre-ask line, protocol/skill mention of the pass, regression test) — while the repo stays otherwise untouched.

## Criteria

- [x] ISC-1: TODO.md exists at jolo-isa repo root
- [x] ISC-2: TODO names the root-cause functions and both source files
- [x] ISC-3: TODO quotes the prompt-3 log evidence (Jev 0.58, choice continue)
- [x] ISC-4: TODO lists at least three concrete fix items
- [x] ISC-5: Anti: no tracked jolo-isa file modified besides TODO.md

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "enc:v1:0ddf368a:I1otCIt-Fxhm8xesHxg4KCM5UYhG3x7FUo71iw_tnAht0_m8TJnBn_7e8Mu2bc2xeDsp37ffy5RXphaKFwk3f1BC_yMsGiqey-VGoP1TAr8J2VI"
  type: bash
  kind: file
  tool: test -f /home/jolo/dev/jolo-isa/TODO.md
  check: the TODO file exists at the repo root
  threshold: test exits 0
  fails-when: "TODO.md does not exist at /home/jolo/dev/jolo-isa/"
- isc: ISC-2
  anchors_to: "enc:v1:0ddf368a:C3Fc2MyF3vULrbcvs7eO5ESXXLwbaxmMmkbaS5KfSkJpYGlhgBGL3wo4DdYgTOg"
  type: bash
  kind: doc
  tool: rg -q "_ask_answer" /home/jolo/dev/jolo-isa/TODO.md && rg -q "_record_choice" /home/jolo/dev/jolo-isa/TODO.md && rg -q "engine\.py" /home/jolo/dev/jolo-isa/TODO.md && rg -q "isa\.ts" /home/jolo/dev/jolo-isa/TODO.md
  check: the TODO cites _ask_answer and _record_choice and both files (engine.py, isa.ts)
  threshold: chain of rg -q exits 0
  fails-when: "any of the root-cause functions or source files is missing from TODO.md"
- isc: ISC-3
  anchors_to: "enc:v1:0ddf368a:C3Fc2MyF3vULrbcvs7eO5ESXXLwbaxmMmkbaS5KfSkJpYGlhgBGL3wo4DdYgTOg"
  type: bash
  kind: doc
  tool: rg -qi "jev 0\.58" /home/jolo/dev/jolo-isa/TODO.md && rg -q "muslvrrwsigh-3" /home/jolo/dev/jolo-isa/TODO.md
  check: the TODO quotes the prompt-3 gate evidence (score and prompt id)
  threshold: rg exits 0
  fails-when: "the log evidence (Jev 0.58 ask, prompt pi-muslvrrwsigh-3) is absent from TODO.md"
- isc: ISC-4
  anchors_to: "enc:v1:0ddf368a:I1otCIt-Fxhm8xesHxg4KCM5UYhG3x7FUo71iw_tnAht0_m8TJnBn_7e8Mu2bc2xeDsp37ffy5RXphaKFwk3f1BC_yMsGiqey-VGoP1TAr8J2VI"
  type: bash
  kind: doc
  tool: test "$(rg -c '^- \[ \]' /home/jolo/dev/jolo-isa/TODO.md)" -ge 3
  check: at least three checkbox fix items
  threshold: count >= 3
  fails-when: "TODO.md holds fewer than three actionable fix items"
- isc: ISC-5
  anchors_to: "enc:v1:0ddf368a:I1otCIt-Fxhm8xesHxg4KCM5UYhG3x7FUo71iw_tnAht0_m8TJnBn_7e8Mu2bc2xeDsp37ffy5RXphaKFwk3f1BC_yMsGiqey-VGoP1TAr8J2VI"
  type: bash
  kind: file
  tool: test -z "$(git -C /home/jolo/dev/jolo-isa status --porcelain -uno)"
  check: no tracked file in jolo-isa is modified (TODO.md arrives untracked; nothing else changes)
  threshold: git status (tracked only) prints nothing
  fails-when: "git status shows a modified tracked file in jolo-isa (a source fix happened, out of scope)"
```

## Decisions

- 2026-10-03 Diagnosis split: engine/enforcement worked per spec (pass granted, no blocks during the analysis turn); the defect is the empty model-facing result on Continue (`_record_choice` → `{}`) plus the un-superseded pre-ask line and UI-only warns. The model's judge line was the symptom, not the cause — though under the ambiguity the contract-correct move was to answer with no line at all.
- 2026-10-03 Deliverable is TODO only; the fix itself (engine context on Continue, tests) is listed as TODO items, not implemented — the user asked for analysis + TODO.
- 2026-10-03 Evidence source: `~/.isa/_state/logs/2026-10-03.jsonl` (events for `pi-muslvrrwsigh-3`: ask at t=1791045458.6, ask_answer choice=continue at t=1791045460.6) and `_state/prompts/pi-01a10298-….jsonl`.

## Verification

- ISC-1: verified 2026-10-03T18:47:19 — exit 0 in 0.0s — `test -f /home/jolo/dev/jolo-isa/TODO.md` (ledger: 6f3d0de1b0)
- ISC-2: verified 2026-10-03T18:47:19 — exit 0 in 0.01s — `rg -q "_ask_answer" /home/jolo/dev/jolo-isa/TODO.md && rg -q "_record_choice" /home/jolo/dev/jolo-isa/TODO.md && rg -q "engine\.py" /home/jolo/dev/jolo-isa/TODO.md && rg -q "isa\.ts" /home/jolo/dev/jolo-isa/TODO.md` (ledger: 4dffbdfdea)
- ISC-3: verified 2026-10-03T18:47:19 — exit 0 in 0.01s — `rg -qi "jev 0\.58" /home/jolo/dev/jolo-isa/TODO.md && rg -q "muslvrrwsigh-3" /home/jolo/dev/jolo-isa/TODO.md` (ledger: 3b99beb18d)
- ISC-4: verified 2026-10-03T18:47:19 — exit 0 in 0.0s — `test "$(rg -c '^- \[ \]' /home/jolo/dev/jolo-isa/TODO.md)" -ge 3` (ledger: a307b9295c)
- ISC-5: verified 2026-10-03T18:47:19 — exit 0 in 0.0s — `test -z "$(git -C /home/jolo/dev/jolo-isa status --porcelain -uno)"` (ledger: 8d30f4cd85)
- Ask 1: met — the gate flow was reconstructed from the engine's own log (Jev 0.58 → ask → choice=continue at `pi-muslvrrwsigh-3`) and the source (`_record_choice`/`_ask_answer` return `{}` on continue; pre-ask line never superseded; warns UI-only) — the bootstrap is not wrecked, the Continue pass is granted and enforced, but it is invisible to the model, which then follows stale ON-block instructions (ISC-2/ISC-3 evidence in the TODO).
- Ask 2: met — `~/dev/jolo-isa/TODO.md` created with symptom, log evidence, root cause and five fix items (ISC-1–ISC-4); repo otherwise untouched (ISC-5).
- Goal: yes — the analysis is grounded in tool-read logs and source, and the TODO file exists at the requested repo root with the diagnosis and actionable fixes; the fix itself stays out of scope as asked.
