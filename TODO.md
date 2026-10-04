# TODO — the Continue pass is invisible to the model

Diagnosed 2026-10-03, session `pi-01a10298-2323-7147-869c-28d29cb06ee4` (jev-kit), prompt 3.

## Symptom (user report)

Prompt 3 ("token cost analysis") was judged Jev 0.58 → not settled → the pi dialog asked
Continue/Enable; the user chose **Continue without ISA**. The model then answered with an
`ISA judge (model): no — …` line — a self-judge line that belongs only when **Jev is
unavailable** — looking like the model decided *after* and *against* the user's pick.

## Evidence (engine log `~/.isa/_state/logs/2026-10-03.jsonl`)

| t | prompt_id | step | event |
|---|-----------|------|-------|
| 1791045458.617 | `pi-muslvrrwsigh-3` | prompt | judge=jev score=**0.58** → ask="extension", outcome=ask, warn "ISA gate — Jev 0.58 → asking you" |
| 1791045460.580 | `pi-muslvrrwsigh-3` | ask_answer | asked=true **choice="continue"**, decision=none |

Enforcement then behaved correctly for the rest of the prompt (the pass held; no tool
blocks, no stop-gate). The engine side is per spec; the model-facing half is not.

## Root cause

1. `runtime/isa/engine.py` — `_record_choice()` (≈ line 359): on `choice != "enable"` it
   grants the pass (`st["pass"] = st["gate"]["pid"]`) and **returns `{}`**.
   `_ask_answer()` therefore returns `{}` → `adapters/pi/isa.ts` `judge()` gets no
   `res.context` → **nothing is injected** telling the model a Continue pass is active.
   Contrast the `enable` branch, which returns a full context block.
2. `runtime/isa/engine.py` — `_q1_ask()` (≈ line 602): for `ask == "extension"` the only
   context returned is the **pre-dialog** status line ("If this prompt is a new task, it
   needs a new ISA (or a reopen)"). After a Continue pick that line is never retracted or
   amended — it reads as a standing order to ISA-up, the opposite of the user's choice.
3. Gate **warns are UI-only** (`isa.ts` `warn()` → `ctx.ui.notify`): "ISA gate — Jev 0.58 →
   asking you" never reaches the model, so the transcript has no trace that a dialog
   happened or how it was answered.
4. The stale ON-block from the previous prompt (injected with its judge-line recipe and
   "the turn can't end without a bound ISA") stays in context with nothing per-prompt
   superseding it under a Continue pass. The model hedged exactly as instructed by stale
   rules → the observed `ISA judge (model):` line. (Model-side note: the contract-correct
   move under a Continue pass is *no* judge line at all.)

## Fix items

- [x] `engine.py` `_record_choice`/`_ask_answer`: on continue, return a model-facing
      context — e.g. "The user chose Continue without ISA for this prompt: answer directly,
      no ISA, no `ISA judge (model):` line; the gate returns next prompt." (mirror of the
      enable branch; also covers the no-`pre` case in `_q1_ask`'s `ask == "extension"`
      branch, which currently injects nothing at all).
- [x] `engine.py` `_q1_ask`: make the Continue answer context explicitly **supersede** the
      pre-ask "needs a new ISA (or a reopen)" line, so the model never holds both.
- [x] Protocol/skill (`_on_block`/`_judge_text`/SKILL.md § 12): state the Continue pass in
      the injected protocol itself, so a pass is interpretable from injected context alone,
      without memory of a previous prompt's ON-block.
- [x] Consider folding the gate outcome (score + ask + choice) into the model-facing
      injection or a `display: true` transcript marker, so the ask/answer is auditable
      in-session instead of only in `~/.isa/_state/logs`.
- [x] Regression tests (`tests/test_ask.py`): score in (0.3, 0.8) + UI + choice=continue →
      injected context is non-empty, mentions Continue, and imposes no ISA/judge-line
      obligation; enable → existing ON block unchanged.

## Fixed 2026-10-04

`_record_choice` now returns `_continue_text()` on a Continue (or a failed question): the gate's judge and
score, the user's pick, the pass (no ISA, no judge line, earlier ISA protocol off for this prompt), and that
it supersedes the pre-ask "needs a new ISA (or a reopen)" line. pi gets it at `input` (no `block`, so a
Continue at settle never restarts the run); Claude Code gets it as PostToolUse context. `protocol.md` and
SKILL.md state the pass. Tests: `tests.test_ask.TestContinueContext`.
