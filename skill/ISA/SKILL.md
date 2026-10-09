---
name: ISA
version: 2.0.0
description: "Owns the Ideal State Artifact — one TASK ISA per piece of multi-step work, stating what done means as a tree of yes/no criteria, each proven by a probe; a spec first from E2, written and proven through `isa` commands only. USE WHEN ISA, ISC, ideal state, ideal state criteria, task specification, definition of done, spec this, what does done look like."
---

# ISA — Ideal State Artifact

Work with several dependent steps goes wrong quietly: a mistake in one step reaches the result unnoticed, "done" drifts, and nothing records what was proven. The ISA fixes that. Before the work it writes down what done means, as atomic yes/no criteria, each with the command that proves it. During the work, `isa` runs those commands and ticks only what passed.

**Read `References/Foundations.md` first.** It defines every entity, the lifecycle, and the one command for each action. This file is about writing a good ISA.

## The three foundations

1. **The entities** are the ones in `Foundations.md`: TASK, TASK ISA, Tier, ISC, Probe, SPEC, PLAN, Ack, Session, Gate, Lifecycle. There is nothing else.
2. **The decision tree:** no ISA → nothing; E1 → ISA → build; E2–E4 → spec → ack → ISA → ack → build. Nothing bypasses it.
3. **`isa` commands are the only writers** of ISAs, specs, plans and `~/.isa`. You write content through them: `isa write <file> <section>` with the text on stdin, `isa write <ISA> ISC-N`, `isa decide`, `isa answer`. You never write those files with Write, Edit or a script; the hooks refuse it. `isa --help` lists every command.

## State the tier, then follow its lifecycle

Say the tier in your first reply ("E2: a spec, then the ISA"), so the user can correct it.

- **E1:** `isa new <slug> --tier E1`. Write Problem, Goal, Criteria (one level), Test Strategy. Then `isa lint`, `isa verify --red`, the build, `isa verify`, `isa answer <ISA> goal "yes — <evidence>"`, `isa close`.
- **E2–E4:** `isa spec new <slug> --tier E2|E3|E4` and write it (`References/SpecDriven.md`). Then:
  - its open questions, then `isa lint`, then the `Spec ack` question, then `isa ack <spec>`;
  - `isa new --spec <spec>` (it seeds one parent per spec section), write the criteria, `isa review <ISA>`, `isa show <ISA> --trace` for the user, the `ISA ack` question, `isa ack <ISA>`;
  - BUILD as for E1. `isa close` writes the plan and commits.
- **An ack is the user's click** (AskUserQuestion, header `Spec ack` or `ISA ack`, options `Acknowledge` / `Request changes`), never yours. No project change goes through before it.
- **When the spec turns out wrong:** `isa reopen <spec>`, fix it, show the user `isa diff <spec>`, ask again, then `isa refine <ISA>`. Any criterion change after the ISA's ack needs a new ack too.

## Writing the criteria

- **One claim, one probe.** An ISC is a yes/no end state of 8–12 words that one command can decide. If two commands are needed, it is two ISCs. Split anything with "and" that a reader could approve half of.
- **A tree, as deep as the tier allows** (E1 1 level, E2 2, E3 3, E4 4 or more). A top-level ISC is a main part of the work (one per spec section from E2); its children are what proves it. A parent has no probe: its box counts its children.
- **Mainly from the spec, partly from context, and always labelled (E2+).** `isa new --spec` writes one parent per section, `ISC-k` for `Sk`; every leaf you add under it is anchored to `Sk` without asking. The spec never names everything, so:
  - **common ground** two or more sections rely on goes under `ISC-0`, built first (`isa write <ISA> ISC-0 "Common ground" --before ISC-1`), each leaf with `--serves S2+S3 --why "…"`;
  - a **prerequisite** of one section is that section's first child (`--before ISC-k.1`); several keep their order;
  - an **Anti** outside the sections is anchored to the Goal or the Constraints (`--anchors Goal`);
  - anything the spec doesn't state is marked `source: context`, with its `why` (`--source context --why "…"`).
  An end state that can't be probed is not a criterion: it is a Decisions row.
- **Review before the ISA ack.** `isa review <ISA>` takes your reading of the spec and the ISA whole, six lines on stdin, each a finding or `none`: `shared:`, `prerequisites:`, `contradictions:` (a real one reopens the spec), `drift:`, `gaps:`, `context:`. Jev then checks each leaf against the Problem and Goal and each section for coverage, in one request. Answer every flag (`isa review <ISA> --answer R<n> "rebuttal: …"`, or `fixed:`, `reopen:`). Then `isa show <ISA> --trace` shows the user every criterion's origin and probe, and the review; a criterion changed afterwards needs a new review.
- **At least one `Anti:` criterion**, saying what must not happen: the regression, the out-of-scope change, the shortcut that would pass the other criteria while breaking the intent.
- **Test Strategy, one entry per leaf** (`isc`, `anchors_to`, `kind`, `tool`, `fails-when`):
  - **Exit code only.** A probe passes iff it exits 0. Build the threshold into the command (`test "$(…)" -le 5`, `jq -e`), and negate a search for something that must never appear (`! rg -q 'x' f`).
  - **Red before green.** Write the test first, then `isa verify --red`: every behaviour probe must fail before the build. That failure is what gives the later pass its meaning.
  - **`fails-when`** goes on every probe that can't be seen failing first: an Anti, a doc, config or file check. It says what the probe would see if the claim were false, and writing it is where a probe that can't fail shows itself.
  - **`manual`** is for what only a human can check. `isa attest` it with the evidence; the close lists it as not machine-verified.
- **Write Criteria and Test Strategy once, as blocks (E1).** From E2 the Criteria are seeded, so each leaf is added with its probe: `isa write <ISA> ISC-k.n "<claim>" --probe "<command>"`. After that, change one ISC at a time (`isa write <ISA> ISC-N "<text>"`, `--probe "<command>"`, `isa drop`). A change unticks that ISC only.

## While building

- Prove as you go: `isa verify <ISA> ISC-N` after each part, never all at the end. A failing probe asks one question: is the claim wrong, or the code? Fix the one that is wrong, and keep the ISA true (`isa write`, `isa drop`, `isa decide`).
- Record decisions as they happen, dead ends included: `isa decide <ISA> "<what, and why>"`.
- Every explicit ask of the user goes in `asks` (verbatim, `isa write <ISA> asks`) and gets its line at the end (`isa answer <ISA> ask N "met — <evidence>"`).
- Before closing, re-read the user's words against the result, not against the criteria: `isa answer <ISA> goal "yes — <evidence>"` only if the result delivers what was meant. Then `isa close`, and quote its summary in your answer.

## Examples

`Examples/` holds one ISA per tier, written in this shape. Each one from E2 on has its spec in `Examples/specs/`, and every file lints `ok` (`tools/lint_isa.py`).

| File | Tier | Shows |
|---|---|---|
| `Examples/e1-minimal.md` | E1 | a `--no-color` flag: Problem, Goal, one level of criteria, one Anti |
| `Examples/e2-backup-verify.md` | E2 | a verify mode: two levels, every probe anchored to its spec section |
| `Examples/e3-help-redesign.md` | E3 | a `--help` redesign: three levels, common ground (`ISC-0`), a context leaf, a manual leaf, Decisions, the review |
| `Examples/e4-api-migration.md` | E4 | a REST → GraphQL migration: four levels, mid-build, red and verified lines |

## References

- `References/Foundations.md` — the entities, the lifecycle, the commands. It wins over this file on any contradiction.
- `References/SpecDriven.md` — how to write a spec: the template, the writing rules, the red flags.
