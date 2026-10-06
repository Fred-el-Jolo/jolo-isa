# Spec-driven work — specs, plans, and the ISAs that build them

Work goes **spec → ack → (plan → ack) → ISA → code**, in every project, git or not. The spec says *what* done means in the user's words and is acknowledged by the user; the plan (E4–E5) cuts it into ISA-sized steps; each ISA turns its part into probes and proves them. This file holds the templates, the writing rules, the red flags, who owns which fact, the ack and the done marks. The `isa` commands and the hooks enforce the order; the worked examples are in `Examples/specs/`.

---

## Which tier gets what

The **work tier** (SKILL.md § Picking the tier) decides the documents. It is written in the spec's `effort:`. Under a plan, each step's ISA has its own tier, usually E2–E3.

| Tier | Spec | Plan | ISAs | Acknowledgements |
|---|---|---|---|---|
| **E1** | none | none | one | none (the ISA's own gate) |
| **E2** | short: Problem, the change, "Accepted when" (about 30 lines) | none | usually one, linked to the spec | spec |
| **E3** | full (template below) | none | one or more, each linked to spec sections | spec |
| **E4** | full, plus Decisions and a `second-look:` line | yes | one per plan step, created when the step starts | spec, then plan |
| **E5** | as E4, after the Interview ran (`interview:`) | yes | one per plan step | spec, then plan |

The user can say "no spec" for E2–E3: `isa new <slug> --tier E2 --no-spec` writes `no-spec: the user's call` in Decisions, and the flow is E1's.

**Where they live.** `<project root>/docs/spec/YYYY-MM-DD-<slug>.md` and `<project root>/docs/plan/` with the same basename, where the project root is the git work-tree root, else the session's directory (in `$HOME` itself or a temp directory: `~/.isa/<project>/docs/`). The date is the day the spec was started — never a version number. A spec is never moved or renamed after its first ack: ISAs and plans link to it. In a git repo specs and plans are committed; task ISAs never are.

---

## The spec template

```markdown
---
status: draft            # draft | acked YYYY-MM-DD #<hash8> | done YYYY-MM-DD #<hash8>
effort: E3
plan: docs/plan/2026-10-06-<slug>.md   # E4–E5 only
interview: 2026-10-06    # E5 only: the Interview ran
---

# <Title>

## Problem
## Goal
<one or two sentences>
Said:
- <what the user asked for, in their words>
Assumed:
- <what the model filled in; the user corrects these at the ack>
## Out of scope
## Constraints          (immovable limits, exact values)
## Approaches           (E3+: 2–3 options, the chosen one first, why)

## S1 — <a deliverable part>
<what it does, how it is used, what it depends on>
Accepted when:
- [ ] A1: <observable outcome, with the exact values>
- [ ] A2: <another outcome>

## S2 — <the next part>

## Decisions          (dead ends and rejected approaches; E4–E5: the durable ones, and the second-look: line)
## Open questions     (empty at ack)
```

- **Section ids `S1`, `S2`, … are stable**, like ISC ids: never renumbered. A dropped section keeps its heading with `[DROPPED — <why>]`. Only `S<n>` sections are deliverable and get a done mark.
- **Bullet ids `A1`, `A2`, …** are numbered within their section and never renumbered; a dropped bullet stays as `- [ ] A3: [DROPPED — <why>]`. Its full name is `S2:A1`. The bullets are the seeds of the ISA criteria and the unit of done: the ISA turns each into atomic, probe-able ISCs anchored back to it (`anchors_to: "S2:A1"`), and does not copy it.
- **Spec lint** (`isa lint docs/spec/…`; `--moment ack` before the ack question) checks the shape only: the frontmatter; Said and Assumed under Goal; at least one `S<n>` section with `- [ ] A<n>:` bullets under `Accepted when:`, ids unique in their section; no placeholder (TBD, TODO, a lone `…`) and no empty section; Open questions empty at the ack; Approaches from E3; `plan:` and a `second-look:` line from E4; `interview:` at E5.

## The plan template (E4–E5)

```markdown
---
status: draft            # draft | acked YYYY-MM-DD #<hash8> | done YYYY-MM-DD #<hash8>
spec: docs/spec/2026-10-06-<slug>.md
---

# Plan — <Title>

Goal: <one sentence>
Approach: <2–3 sentences>
Files:
- `<path>` — <its one responsibility>          (for non-code work: the artifacts)
Review focus:
- <input or failure mode the spec implies, no step covers> → P2
  (at most five, most likely first; an empty list means checked, none found)

- [ ] P1 — <one-line goal of the step> · E2 · covers S1:A1,A2
  Files: `<path>` (create), `<path>` (change)
  Interfaces: produces `<name(args) -> type>`          (when the work is code)
  Done when: <bullets, with the spec's exact values>
- [ ] P2 — <the next step> · E3 · covers S1:A3, S2 · after P1
  Interfaces: consumes `<name>` from P1; produces `<name(args) -> type>`
  Done when: <bullets>
```

**Plan lint** checks: every Accepted-when bullet is covered by some step (`covers S2` covers all of S2); every `after` and every Review focus target names an existing step; every step has Files and "Done when"; no placeholder; and it warns when the plan is over 3× its spec's size or mostly code blocks.

---

## Writing a spec

1. **State the tier first; it only goes up.** Say the work tier before the first question ("this looks E3: a spec, no plan"), so the user can correct it. Between two tiers, take the heavier one. During the work the tier only goes up: hidden complexity raises it (say so, then take the new tier's steps), and nothing lowers it, because a lower tier would skip an ack. A step ISA's own tier can still move either way.
2. **Said, then assumed.** The Goal opens with two lists. **Said**: what the user asked for, in their words. **Assumed**: what you filled in. Most of the ack is the user correcting Assumed. An empty Assumed list means the request was complete, or that nobody looked hard enough.
3. **Questions.** Ask about purpose, constraints and what success looks like first. Use multiple choice where possible (`AskUserQuestion` options). Independent questions go in one call (at most 3); a question that depends on an earlier answer waits for it. On pi, ask one per message. Never ask again what the request already says. At E5, run the Interview. This is Scaffold's ambiguity check, moved to the spec draft for E2–E5: the questions go into Open questions, the answers are folded into the spec, and Open questions is emptied before the ack.
4. **Scope before detail.** A request that covers several independent subsystems becomes several specs, each with its own ack and plan. Split before refining anything.
5. **Approaches (E3+).** Give 2–3 approaches with their trade-offs, the recommended one first. The ones not chosen go into Decisions as dead ends, with the reason. Cut every feature the Goal does not need.
6. **One section, one unit.** Each `S<n>` is one part with one purpose: what it does, how it is used, what it depends on. Code: components with clear interfaces that follow the codebase's patterns; targeted fixes to code the work touches are in, unrelated refactors are out. Other work (an essay, a brand, an ops change): one deliverable part per section. Size each section to its complexity, from a few sentences up to about 300 words.
7. **Accepted when** names observable outcomes, with the exact values (limits, names, copy) the user gave or agreed to. These are the seeds of the ISA criteria.
8. **Outline check (E4–E5).** Before writing the sections in full, show the outline — Said / Assumed, the chosen approach, the `S<n>` titles with one line each — and ask one question: **Outline OK / Change it**. It is not an ack: it records nothing and allows nothing beyond writing the full spec. It catches a wrong cut before 300 words per section are written.
9. **Self-review before the ack.** Spec lint checks what a script can. You check the rest: no two sections contradict each other; no requirement can be read two ways (if one can, pick a reading and write it down); the scope fits one plan.

## Writing a plan (E4–E5)

10. **Write for the next step's ISA author.** That reader is the model who will write step P3's ISA in a fresh session, without the conversation and without having seen P1 built. A plan is **the set of decisions that reader cannot make alone**: which files, which names and interfaces, which values from the spec, what proves each step. Leave out anything that reader would decide the same way. Two ways to fail: a plan longer than the code it describes has written the code, and a line that decides nothing ("handle edge cases", "add tests") is a gap.
11. **Header.** Goal (one sentence) and Approach (2–3 sentences), the spec link, then two lists. **Files**: each file created or changed, with its one responsibility (for non-code work, the artifacts). **Review focus**: at most five inputs or failure modes that the spec implies but no step's "Done when" covers, most likely first, each naming its owning step. `isa new --plan` adds each line to that step's ISA as a criterion, so it becomes a probe instead of a reminder.
12. **Steps.** Each step has a goal line, a tier, `covers S<n>` and `after`; **Files**; **Interfaces** when the work is code (what the step consumes from earlier steps and produces for later ones, with exact names and types — this is how a later step's ISA learns them); and "Done when", with the spec's exact values. There are no sub-steps: test-first, red then green, and the evidence belong to the step's ISA (`isa verify --red` → build → `isa verify`), not to the plan.
13. **Step size.** A step is the smallest unit with its own test cycle that a reviewer could reject while approving its neighbour. Setup, configuration and docs fold into the step that needs them (the ISA's vertical-slice rule).
14. **Constraints stay in the spec.** The plan points to them. `isa new --plan` shows them to whoever writes the step's ISA, so nothing is copied and nothing drifts.
15. **Self-review before the ack.** Plan lint checks what a script can. You check that the names in one step's Interfaces match their use in later steps, and that every Review focus line has an owning step.

## Red flags

| Thought | Reality |
|---|---|
| "It's small, I'll call it E1 and skip the spec" | Reaching for a lower tier to skip a step is exactly the doubt: take the heavier tier. |
| "The spec is clear, I'll start while they read it" | The gate is the click, not the spec's length. Ask, then wait. |
| "They acked the spec, so the plan is fine too" | An ack covers the file it was given for. The plan gets its own. |
| "It grew, but I'm almost done" | Hidden complexity raises the tier now. Say so. |
| "The ISA criteria cover it, no need to touch the spec" | When the build shows the spec is wrong, the spec changes and is acked again. |
| "I'll put the test steps in the plan to be safe" | The step's ISA owns the probes. The plan owns the decisions. |

---

## Who owns what

Spec, plan and ISA would collide if each restated the others. Each fact has one home; the other layers point to it.

| Concern | Spec | Plan | Task ISA |
|---|---|---|---|
| Why, problem, scope, constraints | **owns** | — | one pointer line: `See docs/spec/…#S2` |
| Done, in human words | **owns** ("Accepted when") | **owns** per step ("Done when") | — |
| Done, as probes | — | — | **owns** (Criteria + Test Strategy + `Anti:`) |
| Order and dependencies between steps | — | **owns** | — (its Features only split its own step) |
| Decisions | durable, design-level | step order, splits | in-run, local |
| Evidence | — | — | **owns** (the ledger) |
| Status | `status:` + `Done:` lines | `[x]` per step | `phase`, `progress` |
| Lifetime | the project's | until the work is done | one task, one machine |
| Checked by | the user (ack) | the user (ack) | the engine (probes) |

Under a plan, the E4–E5 rigor lives in the committed documents and the step ISAs stay E2–E3: design decisions and the `second-look:` line go in the spec's Decisions, the order in the plan, the Interview runs before the spec ack. A linked ISA (`spec:` or `plan:` in its frontmatter) may give Problem, Vision, Out of Scope and Constraints as one pointer line each, and may take `stated_goal` from the document (`stated_goal_source: spec`, copied verbatim from the Goal or the step line; lint checks it against that file). Goal, Criteria (with `Anti:`) and Test Strategy stay required, and lint refuses a linked bullet that no ISC anchors to.

## The ack

"Acknowledged" means the user — not you — said yes to this exact content, by a click.

- When spec lint passes at `ack` and Open questions is empty, ask with `AskUserQuestion`, header `Spec ack` (or `Plan ack`), options exactly **Acknowledge** / **Request changes**, the question naming the file ("Acknowledge docs/spec/…?"). pi asks by itself when your turn ends.
- On Acknowledge the engine records the ack; you then write `status: acked YYYY-MM-DD #<hash8>` with Edit, changing nothing else, and in a git repo commit that file alone (`Spec: <title> (acked)`). Writing that line without a recorded ack is refused.
- The hash ignores the `status:` and `Done:` lines, tick state and the done suffixes, so the marks below never break an ack, while any other edit does: the document then reads "changed since its ack" until the user acks it again. Code commits stay the user's call.
- **An ack is the explicit go for what it covers.** E2–E3: the spec ack means "implement it" — `isa new --spec docs/spec/…#S1` in the same turn. E4–E5: the spec ack means "write the plan", the plan ack means "implement it" — `isa new --plan docs/plan/…#P1`, one step's ISA at a time, each created when its step starts (`isa new` refuses a step whose `after` steps are open).

## Done marks

The unit of done is the **acceptance bullet**. Every mark is written by `isa close`, after a passing close, and only there — never by hand while the hooks are installed:

```markdown
## S2 — Ledger back in ~/.isa
Done: 2026-10-09 — 3/3 accepted (ISAs 20261008-101500_ledger-home, 20261009-091200_migrate-repos)
Accepted when:
- [x] A1: isa new prints a path under ~/.isa/<project>/  (2026-10-08, ISA 20261008-101500_ledger-home)
- [x] A2: every (ledger: <id>) line still resolves  (2026-10-08, ISA 20261008-101500_ledger-home)
- [x] A3: the four repos track no .isa/ files  (2026-10-09, ISA 20261009-091200_migrate-repos)
```

- **Links.** `spec: docs/spec/x.md#S2` is every bullet of S2; `#S2:A1,A2` only those (a list of links is allowed); `plan: docs/plan/x.md#P2` the bullets P2 covers.
- **Proof, not closing, ticks a bullet.** A passing close ticks each linked bullet whose anchored ISCs all passed and appends `  (date, ISA <slug>)`. A bullet whose ISC was waived, or whose ISA's close failed, stays `[ ]`.
- **Section done.** When every live bullet of `S<n>` is ticked (dropped ones don't count), the same close writes the section's one `Done:` line under its heading, naming every ISA that ticked a bullet (read back from the suffixes). A later close replaces the line, never adds a second.
- **Plan step.** A step's `[x]` is written when its ISA closes and every bullet it covers is ticked: `- [x] P2 — … · Done: 2026-10-08`. A step that covers no `S<n>` bullet ticks on its close alone.
- **Spec and plan done.** When every live bullet is ticked, the spec's status becomes `status: done YYYY-MM-DD #<hash8>`, keeping its ack hash so it still reads as unchanged; the plan's follows its last step. Neither ever comes from an empty set.
- **Refusals.** `isa close` refuses before running anything while a linked spec or plan changed since its ack — "spec changed since its ack — ask the user to acknowledge it again" — and a failed close writes nothing. Two closes on one spec at once lose no tick: each re-reads the file under `<path>.lock` just before writing.
- **A tick is history, not a guarantee.** It records that a closed ISA proved the bullet once. Keeping it true is the project ISA's job (`promote: true` turns it into a standing claim).
- **Status without a tool.** `rg '^- \[ \] A' docs/spec/` lists the open bullets, `grep -L '^Done:' docs/spec/*.md` the specs with open sections, `rg '^- \[ \] P' docs/plan/` the open steps.

---

## Worked examples

Each is the spec (and plan) behind an ISA example, with the same goal and scope, and passes the ack lint (`tools/lint_isa.py Examples/specs/*.md`):

| File | Tier | Shows |
|---|---|---|
| `Examples/specs/e2-backup-verify.spec.md` | E2 | the short form: Problem, Goal with Said / Assumed, one section — behind `e2-backup-verify.md` |
| `Examples/specs/e3-help-redesign.spec.md` | E3 | a full spec: Constraints with exact values, three Approaches, four sections — behind `e3-help-redesign.md` |
| `Examples/specs/e4-api-migration.spec.md` | E4 | Decisions with the `second-look:` line, and S1 done: ticked bullets, their suffixes, the `Done:` line — behind `e4-api-migration.md` |
| `Examples/specs/e4-api-migration.plan.md` | E4 | its plan: Files, Review focus, four steps with Interfaces, P1 ticked by its close |
