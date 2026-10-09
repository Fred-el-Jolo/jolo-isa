---
status: "acked 2026-10-09 #3d2ccfe7"
effort: E3
---

# Spec-derived criteria: the seed, origins, the review, Jev's check, the trace

## Problem

In the review-fixes task (2026-10-08), `isa new --spec` copied only the skeleton from the spec: the task, the spec link and its hash, and Problem, Out of Scope, Constraints and Goal. All 27 criteria and their probes were written by the model, from the spec and from session context. The result was close to the spec, but only because the model chose to write it that way:
- lint only checks that each `S<n>` has one anchored criterion;
- nothing records whether a criterion came from the spec or from context;
- nothing checks that the criteria serve the stated problem, or cover each section;
- drift went uncaught (ISC-4.1 says "ten" commands where S4 lists nine);
- the ack screen (`isa show --to Criteria`) shows no probe at all.

Two sections can also rest on a shared base that no spec section names, so the criteria can't come from the spec alone.

## Goal

An E2–E4 ISA starts from its spec's sections, and every leaf says where it came from. A model review of the spec and the ISA, read whole, adds common ground, prerequisites, Antis and context items. Jev then checks each leaf against the stated Problem and Goal, and each section for coverage, in one request. The model answers every flag, and the user sees all of it, probes included, at the ISA ack.
Said:
- i would like to be sure that the criteria are created mainly from the spec, and partly from previous context
- for A i don't want to fall in the trap that the Isa only get what's in the spec
- a section in the spec should have a parent ISC => OK. but parent isc or top level standalone isc can also be created without spec section
- maybe a 2-steps isc creation: create isc from the spec sections, and a contradictory/ architectural review to create common grounds/ factorized / prerequisites steps
- i like strong & good jev questions. however i am more doubtful about the 28 calls … could we handle it in one call ?
- i am not sure treating the isa line by line sections against isc is a good idea after all. could we have just a unique question-review in jev of the isc against the stated probelm ? and a model review of the whole files ?
- picked: Jev per leaf + per section, in one request; the seed writes one parent per section, nothing else
- have one threshold per jev question. also about the prerequisite being last child of previous isc. what about multiple prerequisites?
Assumed:
- anchors stay at section level (`anchors_to: S2`, as today); Accepted-when lines get no address, hash or per-line criterion.
- the order of criteria is their dependency (children run in order), so a prerequisite needs a place, not a new field.
- shared ground lives in one reserved parent, `ISC-0` "Common ground", built first.
- a criterion added by the review is an end state with its own probe; an architecture choice that can't be probed is a Decisions row.
- the review is bound to the criteria as they are, like the ack: a criterion change after it needs a new review.
- a contradiction between sections always reopens the spec.
- every Jev flag gets the model's answer (fixed, reopen, or a written rebuttal), shown at the ack; Jev never blocks on its own.
- when Jev is unavailable, the review is the model's alone and says so.
- E1 is unchanged: no spec, so no seed, no origins, no review.

## Out of scope

Line-level anchors (an address and a hash per Accepted-when line, one seeded criterion per line). A blind-derivation subagent. A strict mode where every context item must first go into the spec. Tuning thresholds against the real Jev (the tests use a fake Jev and test the plumbing only). Memory (Future A). E1 ISAs.

## Constraints

- `runtime/` stays standard-library only; every file stays under 50 KB (a new module where `commands.py`, 31 KB, would grow too large).
- Lint and every hook stay deterministic and never call Jev: Jev runs only inside `isa review`, and the ack gate reads the review stored in the ISA.
- One Jev request per review while the state plus all questions fit in 64k tokens and the state plus the longest question in 32k (estimated at 4 characters per token); never one request per pair of sections.
- With DEBUG off, no file is written beyond the ISA, the spec, the plan, `acks.jsonl` and the session file.
- Tests use a fake Jev; no test calls the real one.

## Approaches

1. Seed one parent per spec section; each leaf declares its origin at section level; the model reviews the spec and the ISA whole; Jev checks each leaf against the Problem and Goal, and each section for coverage, in one request; a trace view shows it at the ack (chosen). Light machinery: no line addresses, so a spec edit moves nothing.
2. Line-level: one seeded criterion per Accepted-when line, with a positional address, a hash and a drift check each. Precise, but fragile under every spec edit, and it pushes the ISA to mirror the spec's wording. Rejected by the user (2026-10-09).
3. One single Jev question over the whole tree ("do these criteria address the stated problem?"). One number that says nothing about which criterion or section is off. Rejected.

## S1 — The seed

`isa new --spec` writes the Criteria from the spec's sections: each `S<k>` becomes a parent, `ISC-k`, with the section's title, and nothing more. The model writes every leaf under it, one ISC at a time (`isa write <ISA> ISC-k.n "<text>"`). The seeded Criteria count as the block written once.
Accepted when:
- on a spec with sections S1 and S2, `isa new --spec` writes `ISC-1` and `ISC-2` with the section titles and no leaf
- until a section's parent has a leaf, lint lists `ISC-k (Sk): no criterion yet`
- a block write of Criteria on a seeded ISA is refused, as today
- `isa write <ISA> ISC-1.1 "<text>"` adds a leaf under `ISC-1`, and its Test Strategy entry gets `anchors_to: S1` without being asked
- `isa new <slug> --tier E1` writes the same skeleton as today

## S2 — Origins and coverage

Where a leaf sits says where it came from:
- **under `ISC-k`:** from section Sk, so `anchors_to: Sk`;
- **under `ISC-0`, "Common ground":** a state two or more sections rely on, so `serves: Sa+Sb` and `why:`;
- **a top-level leaf:** an Anti anchored to the Goal or the Constraints, or anything else, marked as context.

Any leaf may carry `source: context` with a `why:` when the spec doesn't state it. `isa write <ISA> ISC-N` sets these with `--serves`, `--why` and `--source context`.

Prerequisites are placed by order, since children run in order:
- several prerequisites of one section are its first children, in the order they must hold;
- a prerequisite of several sections, or a section needing part of another section's result, is an `ISC-0` leaf serving all of them;
- prerequisites that depend on each other keep that order inside `ISC-0` or inside their section;
- from E3, a prerequisite with parts of its own is a parent with its own leaves.

`isa write <ISA> ISC-N "<text>" --before ISC-M` places a new criterion just before its sibling `ISC-M`. Without it, a new criterion goes after its last sibling, as today.
Accepted when:
- lint refuses a leaf under `ISC-k` anchored to anything but `Sk`
- lint refuses a leaf under `ISC-0` without `serves:` naming two or more sections, or without `why:`
- lint refuses a top-level leaf that is neither an Anti anchored to `Goal` or `Constraints` nor marked `source: context`
- lint refuses `source: context` without `why:`
- `isa write <ISA> ISC-2.4 "<text>" --before ISC-2.1` writes `ISC-2.4` as the first child of `ISC-2`, and a second new child `--before ISC-2.1` lands between them, so two prerequisites keep their order
- `--before` refuses a criterion that isn't a sibling (a different parent) and an existing criterion (moving one is out of scope)
- the four examples (`skill/ISA/Examples/`) follow these rules, and `tools/lint_isa.py` reports `ok` for all seven files
- an E1 ISA lints exactly as today

## S3 — The review

`isa review <ISA>` records the model's review of the spec and the ISA, read whole, and runs Jev's check (S4). The model's checklist comes on stdin, six lines, each a finding or `none`:
- `shared:` states that two or more sections rely on, and that nothing proves yet;
- `prerequisites:` what one section needs first;
- `contradictions:` sections that can't both hold;
- `drift:` criteria that say something other than their section (a count, a name, a value);
- `gaps:` how every criterion could pass while the Goal is missed;
- `context:` what the criteria take from outside the spec.

The command writes `## Review` in the ISA, a section only `isa review` writes. It holds the checklist, each Jev flag (id, question, score, answer), and the hash of the criteria it reviewed. `isa review <ISA> --answer R<n> "<answer>"` answers one flag, starting with `fixed:`, `reopen:` or `rebuttal:`.
Accepted when:
- `isa review` refuses a checklist missing any of its six lines, naming them, and refuses an E1 ISA
- a `contradictions:` line other than `none` is refused while the spec is acked: the spec is reopened first
- a review writes `## Review` with the checklist, every flag, and `reviewed: <hash8>` of the current Criteria and Test Strategy
- the `ISA ack` question is denied at PreToolUse, and `isa ack` refuses, while the ISA has no review for its current criteria or holds an unanswered flag; both name `isa review`
- a criterion changed after the review makes the stage read "changed since its review", and the next `ISA ack` question is denied until `isa review` runs again
- `--answer` refuses an answer not starting with `fixed:`, `reopen:` or `rebuttal:`, and refuses `reopen:` while the spec is still acked
- the plan written at close holds `## Review` after `## Decisions`

## S4 — Jev's challenge in one request

The review sends Jev one state, as named JSON fields: the spec's Problem, Goal and sections (titles and Accepted-when text), and the criteria tree with each leaf's origin, `why` and probe. It asks two kinds of Noul in the same request, each with its own threshold in `config.json` (the existing `jev_gate`, `jev_quiet` and `jev_doubt` are unchanged):
- **per leaf, "serves":** does this criterion help solve the stated Problem and reach the Goal (and, under `ISC-k`, what Sk asks for)? It is flagged when the probability of no reaches `jev_serves` (default 0.7).
- **per section, "covered":** do the criteria under `ISC-k` together cover what Sk's Accepted-when lines ask for? It is flagged when the probability of no reaches `jev_covered` (default 0.7).
Accepted when:
- with a fake Jev that counts calls, the review of an ISA with 8 sections and 27 leaves makes exactly one request of 35 questions
- with no config, `jev_serves` and `jev_covered` are 0.7, and `jev_gate`, `jev_quiet` and `jev_doubt` keep their current defaults
- with `jev_serves` set to 0.9 and `jev_covered` left at 0.7, a leaf answered no at 0.8 is not flagged and a section answered no at 0.8 is
- when the state and the questions exceed the token budget, the review splits them along section boundaries into the fewest requests that fit
- each flag in `## Review` carries its question, the ISC or section it is about, its threshold and Jev's score
- with Jev unavailable, the review records the checklist alone, and `## Review` says `Jev: unavailable — model only`
- with a fake Jev that fails the test when called, lint and every hook event run without calling it

## S5 — The trace at the ISA ack

`isa show <ISA> --trace` is what the user reads before the `ISA ack`, in build order:
1. Common ground: each `ISC-0` leaf with its `serves`, `why` and probe.
2. Each section: its Accepted-when lines as the spec states them, then its leaves with their probes, the context ones marked.
3. The top-level Antis and context leaves.
4. The review: its checklist, and each flag with its answer.
5. A footer.

The ack instructions name `--trace` in place of `--to Criteria`.
Accepted when:
- `isa show <ISA> --trace` prints those five blocks in that order, with every leaf's probe command
- the footer reads `<n>/<n> sections covered · <n> common · <n> context · review ✓ (Jev)`, or `review: model only`, or `review: missing`
- the ISA DRAFT stage text, `runtime/isa/protocol.md` and `skill/ISA/SKILL.md` name `isa show <ISA> --trace` before the ISA ack
- `skill/ISA/References/Foundations.md`, `SKILL.md` and `SpecDriven.md` describe the seed, the origins, the review and the trace; `isa review` is in `isa --help` and in the command table

## Decisions

## Open questions
