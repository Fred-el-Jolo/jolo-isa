---
spec: 2026-10-09-spec-derived-criteria-01-spec.md
isa: 20261009-180247_spec-derived-criteria
closed: 2026-10-09
---

# Plan — Spec-derived criteria: the seed, origins, the review, Jev's check, the trace

## Problem

In the review-fixes task (2026-10-08), `isa new --spec` copied only the skeleton from the spec: the task, the spec link and its hash, and Problem, Out of Scope, Constraints and Goal. All 27 criteria and their probes were written by the model, from the spec and from session context. The result was close to the spec, but only because the model chose to write it that way:
- lint only checks that each `S<n>` has one anchored criterion;
- nothing records whether a criterion came from the spec or from context;
- nothing checks that the criteria serve the stated problem, or cover each section;
- drift went uncaught (ISC-4.1 says "ten" commands where S4 lists nine);
- the ack screen (`isa show --to Criteria`) shows no probe at all.

Two sections can also rest on a shared base that no spec section names, so the criteria can't come from the spec alone.

## Vision

At the ISA ack, the user sees where every criterion came from: a spec section, common ground two sections share, an Anti, or context the spec never stated. Each one has been read against the stated problem by the model and by Jev, and every doubt has an answer on the page.

## Out of Scope

Line-level anchors (an address and a hash per Accepted-when line, one seeded criterion per line). A blind-derivation subagent. A strict mode where every context item must first go into the spec. Tuning thresholds against the real Jev (the tests use a fake Jev and test the plumbing only). Memory (Future A). E1 ISAs.

## Principles

- The engine places and labels criteria; the model writes them. The engine never invents a criterion's text beyond a section title.
- Deterministic gates (lint, hooks, the ack gate) read only what is stored in the ISA; Jev runs inside `isa review` alone.
- Each acceptance line starts as a failing test in `tests/test_derivation.py`, which reuses the harness of `tests/test_foundations.py` (that file is 36 KB, so the new tests live apart).
- Existing tests that ack an ISA learn the review step through their helper, not test by test.

## Constraints

- `runtime/` stays standard-library only; every file stays under 50 KB (a new module where `commands.py`, 31 KB, would grow too large).
- Lint and every hook stay deterministic and never call Jev: Jev runs only inside `isa review`, and the ack gate reads the review stored in the ISA.
- One Jev request per review while the state plus all questions fit in 64k tokens and the state plus the longest question in 32k (estimated at 4 characters per token); never one request per pair of sections.
- With DEBUG off, no file is written beyond the ISA, the spec, the plan, `acks.jsonl` and the session file.
- Tests use a fake Jev; no test calls the real one.

## Goal

An E2–E4 ISA starts from its spec's sections, and every leaf says where it came from. A model review of the spec and the ISA, read whole, adds common ground, prerequisites, Antis and context items. Jev then checks each leaf against the stated Problem and Goal, and each section for coverage, in one request. The model answers every flag, and the user sees all of it, probes included, at the ISA ack.

## Criteria

- [x] ISC-0: Common ground: the shared states the five sections rely on.
  - [x] ISC-0.1: `## Review` is parsed from the ISA and written only by `isa review`.
  - [x] ISC-0.2: Test Strategy keeps `serves`, `source` and `why` through every write.
  - [x] ISC-0.3: `jev.py` sends one ad-hoc request of many questions through `jev ask`.
- [x] ISC-1: The seed: `isa new --spec` writes one parent per section.
  - [x] ISC-1.1: The seed writes one titled parent per spec section and no leaf.
  - [x] ISC-1.2: Lint lists `ISC-k (Sk): no criterion yet` for an empty seeded parent.
  - [x] ISC-1.3: A Criteria block write on a seeded ISA is refused.
  - [x] ISC-1.4: A new leaf under `ISC-k` gets `anchors_to: Sk` unasked.
  - [x] ISC-1.5: Anti: `isa new --tier E1` writes a skeleton different from before.
- [x] ISC-2: Origins and coverage: where a leaf sits says where it came from.
  - [x] ISC-2.1: Lint refuses a leaf under `ISC-k` anchored to another section.
  - [x] ISC-2.2: Lint refuses an `ISC-0` leaf lacking two served sections or a `why`.
  - [x] ISC-2.3: Lint refuses an unmarked top-level leaf that isn't an anchored Anti.
  - [x] ISC-2.4: Lint refuses `source: context` without a `why`.
  - [x] ISC-2.5: `--before` places prerequisites in order among their siblings.
    - [x] ISC-2.5.1: `--before ISC-2.1` makes the new criterion `ISC-2`'s first child.
    - [x] ISC-2.5.2: A second `--before ISC-2.1` lands between, keeping both prerequisites' order.
    - [x] ISC-2.5.3: `--before` refuses a non-sibling target and an existing criterion.
  - [x] ISC-2.6: The four examples follow the origin rules and all seven files lint ok.
  - [x] ISC-2.7: The E3 example shows an `ISC-0` common-ground leaf and a context leaf.
  - [x] ISC-2.8: Anti: an E1 ISA lints differently than before.
- [x] ISC-3: The review: `isa review` records the model's whole-file review.
  - [x] ISC-3.1: `isa review` refuses a checklist missing any of its six lines, and E1.
  - [x] ISC-3.2: A `contradictions:` finding is refused while the spec is still acked.
  - [x] ISC-3.3: A review writes the checklist, every flag and `reviewed: <hash8>`.
  - [x] ISC-3.4: The ISA ack waits for a current, fully answered review.
    - [x] ISC-3.4.1: The `ISA ack` question is denied without a review, naming `isa review`.
    - [x] ISC-3.4.2: `isa ack` refuses while a flag is unanswered, naming `isa review`.
    - [x] ISC-3.4.3: A criterion changed after the review denies the next ack question.
  - [x] ISC-3.5: `--answer` refuses a bad prefix, and `reopen:` while the spec is acked.
  - [x] ISC-3.6: The plan written at close holds `## Review` after `## Decisions`.
- [x] ISC-4: Jev's check runs in one request with its own thresholds.
  - [x] ISC-4.1: 8 sections and 27 leaves make one request of 35 questions.
  - [x] ISC-4.2: `jev_serves` and `jev_covered` default to 0.7; older thresholds keep theirs.
  - [x] ISC-4.3: The two thresholds act independently (0.9 vs 0.7, scored 0.8).
  - [x] ISC-4.4: Over the token budget, the review splits along sections into fewest requests.
  - [x] ISC-4.5: Each flag records its question, subject, threshold and Jev's score.
  - [x] ISC-4.6: With Jev unavailable, `## Review` says `Jev: unavailable — model only`.
  - [x] ISC-4.7: Anti: lint or a hook event calls Jev.
- [x] ISC-5: The trace shows origins, probes and the review at the ISA ack.
  - [x] ISC-5.1: `isa show --trace` prints its five blocks in order with every probe.
  - [x] ISC-5.2: The trace footer reads `✓ (Jev)`, `model only` or `missing` as stated.
  - [x] ISC-5.3: The stage text, `protocol.md` and `SKILL.md` name `--trace` before the ack.
  - [x] ISC-5.4: The skill docs, `isa --help` and the command table describe the new pieces.
- [x] ISC-6: AGENTS.md's pre-install test list runs `tests/test_derivation.py`.
- [x] ISC-7: Anti: a pre-install test suite fails after the change.
- [x] ISC-8: Anti: `runtime/` imports beyond stdlib, or a tracked file reaches 50 KB.

## Test Strategy

```yaml
- isc: ISC-0.1
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Common.test_review_section
  serves: S3+S5
  why: "the review writes it (S3), the trace and the plan read it (S5)"
- isc: ISC-0.2
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Common.test_origin_fields_roundtrip
  serves: S2+S5
  why: "lint checks the origin fields (S2), the trace prints them (S5)"
- isc: ISC-0.3
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Common.test_jev_adhoc_one_request
  serves: S3+S4
  why: presets hold fixed questions; the review (S3) needs one request of per-leaf questions (S4)
- isc: ISC-1.1
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Seed.test_parents_only
- isc: ISC-1.2
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Seed.test_empty_parent_listed
- isc: ISC-1.3
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Seed.test_block_write_refused
- isc: ISC-1.4
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Seed.test_leaf_inherits_anchor
- isc: ISC-1.5
  anchors_to: S1
  kind: regression
  tool: python3 -m unittest tests.test_derivation.Seed.test_e1_unchanged
  fails-when: the E1 skeleton of isa new changed
- isc: ISC-2.1
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Origins.test_wrong_section_anchor
- isc: ISC-2.2
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Origins.test_common_ground_rules
- isc: ISC-2.3
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Origins.test_top_level_leaf
- isc: ISC-2.4
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Origins.test_context_needs_why
- isc: ISC-2.5.1
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Origins.test_before_first
- isc: ISC-2.5.2
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Origins.test_before_keeps_order
- isc: ISC-2.5.3
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Origins.test_before_refusals
- isc: ISC-2.6
  anchors_to: S2
  kind: doc
  tool: "python3 tools/lint_isa.py skill/ISA/Examples/*.md skill/ISA/Examples/specs/*.md"
  fails-when: an example breaks the origin rules once lint checks them
- isc: ISC-2.7
  anchors_to: S2
  kind: behaviour
  tool: "grep -q 'serves:' skill/ISA/Examples/e3-help-redesign.md && grep -q 'source: context' skill/ISA/Examples/e3-help-redesign.md"
  source: context
  why: the examples are how the skill teaches the shape; the spec asks only that they lint
- isc: ISC-2.8
  anchors_to: S2
  kind: regression
  tool: python3 -m unittest tests.test_derivation.Origins.test_e1_lint_unchanged
  fails-when: an E1 ISA gets a new lint error or loses one
- isc: ISC-3.1
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Review.test_checklist_required
- isc: ISC-3.2
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Review.test_contradiction_needs_reopen
- isc: ISC-3.3
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Review.test_review_written
- isc: ISC-3.4.1
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Review.test_ack_question_needs_review
- isc: ISC-3.4.2
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Review.test_ack_needs_answers
- isc: ISC-3.4.3
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Review.test_change_needs_new_review
- isc: ISC-3.5
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Review.test_answer_rules
- isc: ISC-3.6
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Review.test_plan_has_review
- isc: ISC-4.1
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.JevCheck.test_one_request
- isc: ISC-4.2
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.JevCheck.test_defaults
- isc: ISC-4.3
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.JevCheck.test_thresholds_independent
- isc: ISC-4.4
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.JevCheck.test_budget_split
- isc: ISC-4.5
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.JevCheck.test_flag_fields
- isc: ISC-4.6
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.JevCheck.test_unavailable
- isc: ISC-4.7
  anchors_to: S4
  kind: regression
  tool: python3 -m unittest tests.test_derivation.JevCheck.test_no_jev_in_lint_or_hooks
  fails-when: lint or a hook event reaches the fake Jev
- isc: ISC-5.1
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Trace.test_blocks_in_order
- isc: ISC-5.2
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Trace.test_footer
- isc: ISC-5.3
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Trace.test_ack_names_trace
- isc: ISC-5.4
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_derivation.Trace.test_docs_and_help
- isc: ISC-6
  anchors_to: Goal
  kind: behaviour
  tool: "grep -q 'tests.test_derivation' AGENTS.md"
  source: context
  why: AGENTS.md lists the suites to run before installing; a new test file is not run unless listed
- isc: ISC-7
  anchors_to: Goal
  kind: regression
  tool: "python3 -m unittest tests.test_foundations tests.test_install tests.test_bash_classifier tests.test_derivation && node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts"
  fails-when: "any test of the pre-install suites fails, old or new"
- isc: ISC-8
  anchors_to: Goal
  kind: regression
  tool: "python3 tests/check_stdlib.py runtime/ && test -z \"$(git ls-files runtime tests skill | xargs stat -c '%s %n' | awk '$1>=51200')\""
  fails-when: "a change imports a non-stdlib module or grows a tracked file to 50 KB (anchored to Goal: lint has no Constraints anchor yet)"
```

## Decisions

- 2026-10-09 18:05: Review by hand (isa review does not exist yet). shared: the Review section (S3+S5), the origin fields (S2+S5), one ad-hoc Jev request (S3+S4) -> ISC-0.1..0.3. prerequisites: ISC-0 runs first; S3 needs the ad-hoc Jev path. contradictions: none. drift: S4 says 35 questions for 8 sections and 27 leaves, ISC-4.1 keeps it; S2 has 8 accepted lines, ISC-2.1..2.8 cover them. gaps: the existing test helpers ack ISAs without a review, so the new ack gate would break them; covered by ISC-7 and the helper Principle. context: ISC-2.7 (an example shows the shape), ISC-6 (AGENTS.md runs the new test file).
- 2026-10-09 18:27: Origins beyond the spec letter: a leaf under a top-level parent that is not a spec section (and not ISC-0) is treated as outside the sections, like a top-level leaf (an Anti anchored to Goal/Constraints, or source: context). The user asked that parents without a spec section be possible; this gives them a rule.
- 2026-10-09 18:27: ISC-4.7 reads the spec line "lint and every hook event run without calling it" with ISA_MODE=on: the gate (UserPromptSubmit) calls Jev by design when the mode is auto; the test proves that no hook calls the review check and that lint never does.
- 2026-10-09 18:27: A partly served Jev check (one request of several failed) is recorded as unavailable — model only, with no flags: a review never shows half of Jev as if it were all of it.
- 2026-10-09 18:27: Context, beyond the spec: skill/global-rules.md (the block in CLAUDE.md) now names isa review and isa show --trace in the E2-E4 path, so the always-loaded rules match the protocol block.
- 2026-10-09 18:33: Two older tests followed the new spec: Close.test_plan_file now expects Review between Decisions and Verification (S3); Proof.test_isc_change_breaks_ack kept as is, and the stage text for an ISA changed after its ack names both its ack and the review it needs.

## Verification

- Goal: yes — isa new --spec seeds one parent per section; lint enforces each leaf's origin (section, ISC-0 common ground, Anti, context with why); isa review records the six-line model review and runs Jev in one request with jev_serves/jev_covered at 0.7; the ISA ack waits for a current, answered review; isa show --trace shows origins, probes and the review; 40/40 probes, every suite green
- Ask 1: met — spec 6fc377a acked after three revisions (section-level anchors, per-question thresholds at 0.7, prerequisites by order with --before); S1–S5 built and proven by tests/test_derivation.py
