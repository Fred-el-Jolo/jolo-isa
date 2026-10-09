# Writing a spec

From E2, work starts from a spec: what the user wants, in their words, acknowledged by them before anything is built. The TASK ISA is then derived from it (`isa new --spec`), and at close the ISA's record becomes the plan. The entities and the commands are in `Foundations.md`; this file is about writing the spec well.

## The template

`isa spec new <slug> --tier E2|E3|E4` writes this skeleton at `<cwd>/docs/YYYY-MM-DD-<slug>-01-spec.md`. Each part is written with `isa write <spec> <part>`, the text on stdin:

```markdown
---
status: draft            # draft | acked YYYY-MM-DD #<hash8> — written by `isa ack`, never by hand
effort: E2
---

# <title>

## Problem
## Goal
<one or two sentences>
Said:
- <what the user asked for, in their words>
Assumed:
- <what you filled in; the user corrects these at the ack>
## Out of scope
## Constraints          (immovable limits, exact values)
## Approaches           (from E3: 2–3 options, the chosen one first, why)

## S1 — <a deliverable part>
<what it does, how it is used, what it depends on>
Accepted when:
- <observable outcome, with the exact values>

## Decisions
## Open questions       (empty at the ack)
```

- **"Accepted when" lines are plain.** No checkbox, no id, no done mark: a spec says what is wanted, never what is done. The ISA turns each line into criteria anchored to its section (`anchors_to: S1`), one top-level ISC per section.
- **Sections are stable.** Never renumber `S1`, `S2`, …: the ISA's anchors point at them.
- **`isa lint <spec>` checks the shape.** That covers the frontmatter, the title, Said and Assumed, at least one `S<n>` section with Accepted when lines, no placeholder (TBD, TODO) and no empty section, Approaches from E3, and Open questions empty at the ack.

## Writing rules

1. **State the tier first.** Say it before the first question ("this looks E3"), so the user can correct it. Between two tiers, take the heavier one. Hidden complexity raises the tier during the draft: change `effort:` and say so.
2. **Said, then assumed.** The Goal opens with two lists. **Said** holds what the user asked for, in their words. **Assumed** holds what you filled in. Most of the ack is the user correcting Assumed. An empty Assumed list means the request was complete, or that nobody looked hard enough.
3. **Questions.** Ask about purpose, constraints and what success looks like first. Use multiple choice where possible (AskUserQuestion options). Independent questions go in one call (at most 3); a question that depends on an earlier answer waits for it. On pi, ask one per message. Never ask again what the request already says. Open questions go in `## Open questions`, which may end a turn; the answers are folded into the spec, and the section is emptied before the ack.
4. **Scope before detail.** A request that covers several independent subsystems becomes several specs, each with its own ack. Split before refining anything.
5. **Approaches (from E3).** Give 2–3 approaches with their trade-offs, the recommended one first. The ones not chosen go into Decisions as dead ends, with the reason. Cut every feature the Goal does not need.
6. **One section, one unit.** Each `S<n>` is one part with one purpose: what it does, how it is used, what it depends on. For code, that means components with clear interfaces that follow the codebase's patterns. For other work (an essay, a brand, an ops change), one deliverable part per section. Size each section to its complexity, from a few sentences up to about 300 words.
7. **Accepted when** names observable outcomes, with the exact values (limits, names, copy) the user gave or agreed to.
8. **Outline check (E4).** Before writing the sections in full, show the outline: Said / Assumed, the chosen approach, and the `S<n>` titles with one line each. Ask one question: **Outline OK / Change it**. It is not an ack and records nothing. It catches a wrong cut before the sections are written.
9. **Self-review before the ack.** `isa lint` checks what a script can. You check the rest: no two sections contradict each other; no requirement can be read two ways (if one can, pick a reading and write it down); the scope fits one ISA.

## The ack, and changing an acked spec

- When the spec lints clean and Open questions is empty, ask the user with AskUserQuestion. Use header `Spec ack`, the question naming the file ("Acknowledge docs/…-01-spec.md?"), and options exactly `Acknowledge` / `Request changes`. On Acknowledge, `isa ack <spec>` writes `status: acked …` and, in a git repo, commits the spec alone. The ack is the go: `isa new --spec <spec>`.
- An acked spec changes only after `isa reopen <spec>`. The ISA's work then stops until the spec is acked again. Before asking, show the user `isa diff <spec>`: the title and one line per changed section, so they ack a change they can see. Then `isa refine <ISA>` keeps the progress, you update the criteria the change touches, and the ISA is acked again.
- To resume an unfinished spec (on another machine, in a fresh session), run `isa new --spec <spec>` when the user asks for it. It rebuilds the ISA from the spec, or binds the open one. `isa verify` then ticks whatever is already built. A spec whose plan exists is finished, and `isa new --spec` refuses it.

## From the spec to the ISA

The criteria come mainly from the spec and partly from context, and the ISA says which is which.

1. **The seed.** `isa new --spec` writes one parent per section, `ISC-k` for `Sk`, with the section's title. Each leaf you add under it (`isa write <ISA> ISC-k.n "<claim>" --probe "<command>"`) is anchored to `Sk` without asking. Write the leaves from the section's Accepted-when lines, as end states a probe can decide.
2. **What the spec doesn't name.** Read the spec and the ISA whole, and add:
   - **common ground** two or more sections rely on, under `ISC-0`, built first (`isa write <ISA> ISC-0 "Common ground" --before ISC-1`), each leaf with `--serves S2+S3 --why "…"`;
   - a section's **prerequisites** as its first children (`--before ISC-k.1`), in the order they must hold;
   - **Antis** outside the sections, anchored to the Goal or the Constraints (`--anchors Goal`);
   - anything else the spec doesn't state, marked `source: context` with its `why` (`--source context --why "…"`).
   A contradiction between two sections is not patched in the ISA: reopen the spec.
3. **The review.** `isa review <ISA>` records that reading: six lines on stdin, each a finding or `none` (`shared:`, `prerequisites:`, `contradictions:`, `drift:`, `gaps:`, `context:`). Jev then checks, in one request, that each leaf serves the spec's Problem and Goal and that each section's criteria cover its Accepted-when lines. Every flag gets an answer (`isa review <ISA> --answer R<n> "rebuttal: …"`, or `fixed:` / `reopen:`).
4. **The trace.** `isa show <ISA> --trace` is what the user reads before the `ISA ack`: the common ground, each section with its Accepted-when lines and the criteria and probes under it, the Antis and context items, the review and its answers, and a coverage footer.

## Red flags

| Thought | Reality |
|---|---|
| "It's small, I'll call it E1 and skip the spec" | Reaching for a lower tier to skip a step is exactly the doubt: take the heavier tier. |
| "The spec is clear, I'll start while they read it" | The gate is the click, not the spec's length. Ask, then wait. |
| "They acked the spec, so the ISA is fine too" | An ack covers the file it was given for. The ISA gets its own. |
| "It grew, but I'm almost done" | Hidden complexity raises the tier now. Say so. |
| "The criteria cover it, no need to touch the spec" | When the build shows the spec is wrong, the spec is reopened and acked again. |
| "A small edit to the spec won't need a new ack" | Every change after the ack breaks it. `isa reopen`, then `isa diff` for the user, then the ack. |
