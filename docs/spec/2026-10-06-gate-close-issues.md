---
status: done 2026-10-07 #5b712a52
effort: E3
---

# ISA foundations: the entities, the decision tree, and `isa` as the only writer

## Problem
The skill grew three layers that each say what done means (spec bullets, plan steps, ISA criteria), names that mean the same unit (task, step, ISA), and side machinery nobody reads (project ISA, slices, hierarchies, Features, an evidence ledger, prompt logs). The decision tree can be bypassed (`--no-spec`, binding an ISA to skip the gate's question, `--spec` on an E4 spec), and the model does ISA work with its own scripts (an ack hash in `python3`, a status line by hand, a log read), which the hooks then refuse or misread. Building plan 2026-10-06-local-isas-spec-driven showed each of these.

## Goal
Three foundations, written once and enforced everywhere: FOUNDATION_0 the entities, FOUNDATION_1 the decision tree, FOUNDATION_2 the `isa` commands as the only way to create, read, change or delete an ISA entity; everything else in the repo that they make obsolete is removed.
Said:
- let's redefine all those entities. Let's call this FOUNDATION_0
- FONDATION_1 was my triage above statement, but we will get rid of PLAN
- FOUNDATION_2 is the fact that only 'isa' commands can be used to CRUD specific entities
- E0: no ISA. E1: ISA ISC 1-level, no vision, out of scope, constraints, features. E2: ISA ISC 2-level. E3: ISA ISC 3-levels. E4: ISA ISC 4-levels. No more E5. E2,E3,E4 all have all ISA sections.
- remove features. Plan the possibility to run a parent's children in parallel (subagent future stuff). But now by default: sequential
- Ack from E3. Before the question, All sections down to ## Criteria should be displayed for the user the quickly ack if possible
- draft / acked
- OK drop it.
- Remove every redundant info in ~/.isa
- add a DEBUG flag for keeping verbose session data, but the strict minimum should be created without DEBUG
- Keep all files under 50k, review the whole repo to remove obsolete stuff.
- every ISA step & action should have its associated tool
- PROJECT ISA: remove it completely
- Ephemeral slice: remove it completely
- Created once TASK ISA is closed
- the user cannot re-ack […] without a clear, very succint overview of what has changed
- For now focus only on tests about the foundations
- only when an ISA closes, and only when a spec exists (E2+). also copy Decisions (dead ends, why X over Y)? include also Verification but not evidences or probes
- Until then, IMPL is blocked, yes (can not IMPL without ACKED SPEC !!!)
- always put docs in <CWD>/docs
- i am not interested with already existing isa files. You can remove them all.
- it should be the user manual demande "Continue / impl / work on  the spec xxx.md"
Assumed:
- the tier of this spec is E3 under the engine as installed (spec, then one ISA), since an E4 there would force the plan these foundations remove.
- the ISC depth of a tier: E1 one level, E2 up to 2, E3 up to 3, E4 4 levels or more (no cap).
- E1's ISA has Problem, Goal, Criteria, Test Strategy and Verification; E2–E4 have every section (Problem, Vision, Out of scope, Principles, Constraints, Goal, Criteria, Test Strategy, Decisions, Verification). The Changelog section goes: what it held is a Decisions row.
- the spec exists from E2; the spec is always acked; the TASK ISA is acked from E2 too, so every tier with a spec acks both.
- a spec has no done status and no marks; the plan file written at close is what records done.
- the plan file is written at close from E2 (E1 has no spec, so no plan), and copies Problem, Vision, Out of scope, Principles, Constraints, Goal, Criteria, Test Strategy, Decisions, and Verification without its run lines (the Goal, Ask and deferred lines only).
- after a spec is reopened, no project change goes through until it is acked again and its ISA refined (progress kept, open ISCs updated, acked again).
- a spec is finished when its plan file exists; resuming one is the user's request ("work on the spec …"), never detected at session start.
- the spec's "Accepted when" lines carry no checkbox and no id; an ISC anchors to its section (`anchors_to: S2`).
- the spec and the plan always go to `<cwd>/docs/`, the session's working directory, in git or not; outside git nothing is committed.
- Q2 (continuation or new task, mid-session) stays as it is; a fresh session continues an open ISA from the ISA file and its spec alone.
- every existing ISA and every file under `~/.isa/_state/` is deleted once the new engine is installed; nothing old is migrated.
- Jev stays the gate's judge; the advisory calls at verify and close stay.
- the verbatim checks of `stated_goal` and `asks` read the current session's prompts, kept in its session file (the last 20), not in a separate prompt log.

## Out of scope
Subagents and parallel children (only the field that will allow them, `parallel:`, is reserved). Memory (Future A), the `[arch]` tag. The status line renderer beyond reading the new layout. Migrating the old ISAs in `~/.isa`: they are deleted, not converted. Detecting an unfinished spec at session start.

## Constraints
- `runtime/` stays standard-library only; every file in the repo stays under 50 KB.
- With DEBUG off, no hook writes anything but the session file, and no `isa` command writes anything but the entity it acts on: no extra file, no extra model text.
- The hooks fail open on a crash, as today.

## Approaches
1. Rewrite the foundations first (one reference, the command set, the lint), then delete what they make obsolete, then fix the rest (chosen): the foundations decide what stays.
2. Patch each bug in the current design: keeps every layer the foundations remove. Rejected.
3. A new engine beside the old one: two systems to keep in step while the old one is retired. Rejected.

## S1 — FOUNDATION_0: the entities
Done: 2026-10-07 — 3/3 accepted (ISAs 20261007-005757_foundations)
One reference, `skill/ISA/References/Foundations.md`, defines every entity once: TASK (the unit of work, one TASK ISA at `~/.isa/<project>/<stamp>_<slug>/ISA.md`), tier (E0–E4), ISC (`- [ ] ISC-3:` for a leaf, `- [2/3] ISC-3:` for a parent, `Anti:` for what must not happen), probe (the `tool:` of a leaf's Test Strategy entry), SPEC, PLAN (the record written at close), ack, session, gate, lifecycle. SKILL.md links it and repeats none of it.
Accepted when:
- [x] A1: `Foundations.md` defines exactly these entities, each in one entry, and SKILL.md names no other entity  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A2: the project ISA, ephemeral slices, hierarchies (`parent:`, `children:`, Dependencies, Bridge Criteria), Features, plan steps, `promote:`, `--no-spec` and the evidence ledger are gone from `runtime/`, `skill/` and `install.py`  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A3: the commands that served them are gone (`isa verify ISA.md` on a project ISA, `isa migrate`, the Reconcile workflow, `IsaHierarchy.md`)  (2026-10-07, ISA 20261007-005757_foundations)

## S2 — Tiers and criteria levels
Done: 2026-10-07 — 4/4 accepted (ISAs 20261007-005757_foundations)
The tier sets the documents and the depth of the criteria tree: E0 no ISA; E1 ISA only, one level; E2 spec and ISA, up to 2 levels; E3 up to 3; E4 4 levels or more. A parent ISC has no probe: its box shows its children's progress, `[done/total]`, and it is complete when they all are. Children run in order. `parallel: true` is reserved on a child, for later: a child marked so may run alongside its parallel siblings while the others keep their order (subagents, out of scope); lint refuses it for now.
Accepted when:
- [x] A1: lint refuses an ISC nested deeper than its tier allows (E1 1, E2 2, E3 3; E4 has no cap), naming the ISC and the limit  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A2: lint refuses a Test Strategy entry for a parent ISC, and a leaf without one  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A3: `isa verify` writes a parent's box as `[done/total]` from its leaves, and `[x]` once all are done  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A4: lint refuses `effort: E5`, an E1 ISA holding Vision, Out of scope, Constraints or Features, and an E2–E4 ISA missing one of its sections  (2026-10-07, ISA 20261007-005757_foundations)

## S3 — FOUNDATION_1: the gate and the lifecycle
Done: 2026-10-07 — 4/4 accepted (ISAs 20261007-005757_foundations)
The gate asks one question of every prompt: "Does this message ask for work with several dependent steps, where a mistake in one step could carry into the final result unnoticed unless each step is checked — as opposed to a quick exchange, or a 1–3 step action whose failure would be immediate and evident?" Yes → ON (tier E1 or more); otherwise the user decides as today, and E0 means nothing is enforced. While ON, the lifecycle is fixed:
- E1: ISA DRAFT → BUILD → CLOSED.
- E2–E4: SPEC DRAFT → SPEC ACKED → ISA DRAFT → ISA ACKED → BUILD → CLOSED.
A spec reopened during BUILD sends the task back to SPEC DRAFT; after its re-ack the ISA is refined and acked again before BUILD resumes.
Accepted when:
- [x] A1: the `isa-gate` preset and the model's judge instruction ask exactly that question  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A2: in each lifecycle stage, PreToolUse refuses every project change the stage does not allow, naming the stage and the next command  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A3: a prompt whose gate question is due can't end its turn unanswered, even when an ISA was bound during the turn  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A4: an E2–E4 ISA can't be created without an acked spec, and can't enter BUILD without its own ack  (2026-10-07, ISA 20261007-005757_foundations)

## S4 — SPEC
Done: 2026-10-07 — 6/6 accepted (ISAs 20261007-005757_foundations)
`<cwd>/docs/YYYY-MM-DD-<slug>-01-spec.md`, from E2, committed in a git repo: Problem, Goal (Said / Assumed), Out of scope, Constraints, Approaches (from E3), then `## S<n> — <part>` sections with their "Accepted when" lines. Its status is `draft` or `acked YYYY-MM-DD #<hash8>`. It is the TASK ISA's source; an ISA links it (`spec:`) and its ISCs anchor to its sections.
Accepted when:
- [x] A1: `isa spec new` writes the file at that path from the template, `status: draft`, and binds it  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A2: spec lint holds the shape rules and refuses a checkbox, an id or a done mark in "Accepted when"  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A3: an acked spec can change only after `isa reopen`, which sets it back to `draft` and keeps the acked text for the summary  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A4: before a re-ack, `isa diff` prints the spec's title and one line per section added, removed or changed since its last ack, and nothing else  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A5: while a spec is reopened, or acked again but its ISA not yet refined, PreToolUse refuses every project change  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A6: `isa new --spec X` builds a new ISA from an acked spec when none exists for it here, binds the existing one when it does, and refuses when the spec's plan file exists (the spec is finished)  (2026-10-07, ISA 20261007-005757_foundations)

## S5 — The TASK ISA and its proof
Done: 2026-10-07 — 6/6 accepted (ISAs 20261007-005757_foundations)
The ISA is written through `isa write`, never by Write/Edit: each section once as a block, then Criteria and Test Strategy only one ISC at a time (`isa write <ISA> ISC-3.12 "<text>"`, `--probe "<command>"` for its Test Strategy entry, a new id to add one, `isa drop <ISA> ISC-3.12 "<why>"` for a tombstone). Once the ISA is acked, any change to an ISC breaks the ack until the user acks again, shown the change by `isa diff`. Its Test Strategy holds one entry per leaf: `isc`, `anchors_to`, `kind`, `tool`, and `fails-when` where no red run applies. `isa verify` runs probes and writes, in the ISA's Verification, one line per run (red or green); there is no separate ledger. From E2, before its ack, `isa show <ISA> --to Criteria` prints every section down to Criteria for the user.
Accepted when:
- [x] A1: `isa write <ISA> <section>` writes a section from stdin and lints the result; a second block write of Criteria or Test Strategy is refused  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A2: `isa write <ISA> ISC-N` changes one ISC's text or probe, adds a new id whose parent exists and whose depth fits the tier, unticks only that ISC (its parents recount), and `isa drop` leaves a tombstone whose id is never reused  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A3: after the ISA's ack, any `isa write` or `isa drop` on an ISC makes the ISA read "changed since its ack", and BUILD changes are refused until the user acks it again  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A4: `isa verify --red` and `isa verify` write `ISC-N: red … exit N` and `ISC-N: verified … exit 0` lines into Verification, and no file under `~/.isa/_state/evidence/` exists  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A5: a behaviour ISC ticks plainly only after a failed red line of the same probe; otherwise its line says `(no red baseline)`  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A6: `isa show <ISA> --to Criteria` prints the sections from Problem through Criteria and nothing below  (2026-10-07, ISA 20261007-005757_foundations)

## S6 — Close, PLAN and commits
Done: 2026-10-07 — 4/4 accepted (ISAs 20261007-005757_foundations)
`isa close` re-runs every probe, then writes `<cwd>/docs/YYYY-MM-DD-<slug>-02-plan.md` (from E2, same basename as the spec) as the record of the work, then commits. The plan holds Problem, Vision, Out of scope, Principles, Constraints, Goal, Criteria, Test Strategy, Decisions, and Verification without its run lines. Commits follow the lifecycle: the spec after its ack (`isa ack`), the implementation and the plan after a passing close, in a git repo only. The implementation commit holds the files changed since `isa new` recorded the work tree, nothing else.
Accepted when:
- [x] A1: a passing E2–E4 close writes the plan file with exactly those sections, from the ISA as closed, and no `verified`/`red` run line  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A2: `isa ack <spec>` commits the spec alone, and a passing close commits the files changed since `isa new`, then the plan  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A3: a failed close writes nothing and commits nothing; outside git nothing is committed  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A4: a file the user changed before `isa new` is left out of the implementation commit  (2026-10-07, ISA 20261007-005757_foundations)

## S7 — FOUNDATION_2: `isa` commands are the only writers
Done: 2026-10-07 — 3/3 accepted (ISAs 20261007-005757_foundations)
Every action of the lifecycle has one command; the hooks refuse every other way to change an ISA, a spec, a plan or anything under `~/.isa` (Write, Edit, a redirect, a script).

| Action | Command |
|---|---|
| start a spec (E2+) | `isa spec new <slug> --tier E2..E4` |
| start an ISA | `isa new <slug> --tier E1`, or `isa new --spec <spec>` |
| write a section (once) | `isa write <file> <section>` (text on stdin) |
| change, add or drop one ISC | `isa write <ISA> ISC-N "<text>"`, `isa write <ISA> ISC-N --probe "<command>"`, `isa drop <ISA> ISC-N "<why>"` |
| add a decision | `isa decide <ISA> "<text>"` |
| show | `isa show <file> [--to <section>]` |
| check the shape | `isa lint <file>` |
| record an ack (after the user's click) | `isa ack <file>` |
| reopen an acked spec | `isa reopen <spec>` |
| what changed since the ack | `isa diff <file>` |
| refine the ISA after a spec change | `isa refine <ISA>` |
| prove | `isa verify <ISA> [--red] [ISC-N…]`, `isa attest <ISA> ISC-N "<evidence>"` |
| answer the goal and the asks | `isa answer <ISA> goal "<yes — evidence>"`, `isa answer <ISA> ask N "<met — evidence>"` |
| close | `isa close <ISA>` |
| read | `isa ls`, `isa status`, `isa current`, `isa where`, `isa log` (DEBUG) |

Accepted when:
- [x] A1: every action above runs through its command, and the protocol block and SKILL.md name only these commands  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A2: PreToolUse refuses a Write or Edit of an ISA, a spec or a plan, and a shell command or script writing to one of them or under `~/.isa`, naming the command to use  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A3: `isa ack <file>` refuses without the user's recorded click on that file's current hash  (2026-10-07, ISA 20261007-005757_foundations)

## S8 — Minimal state and DEBUG
Done: 2026-10-07 — 3/3 accepted (ISAs 20261007-005757_foundations)
Without DEBUG, `~/.isa` holds only the ISA folders, `<project>/acks.jsonl`, `config.json` and `_state/sessions/`. With `ISA_DEBUG=1` (or `"debug": true` in `config.json`), hooks and commands also write `_state/logs/YYYY-MM-DD.jsonl`.
Accepted when:
- [x] A1: a full E2 lifecycle with DEBUG off creates no file outside the ISA folder, the spec, the plan, `acks.jsonl` and one session file  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A2: with DEBUG off, no hook or command opens a log file, and the text the model receives is the same as with DEBUG on  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A3: `_state/prompts/`, `_state/evidence/`, `_state/project/` and `.projects.json` are no longer written or read  (2026-10-07, ISA 20261007-005757_foundations)

## S9 — Repo cleanup and tests
Done: 2026-10-07 — 5/5 accepted (ISAs 20261007-005757_foundations)
Everything the foundations make obsolete goes. The tests prove the foundations first; a test of a removed path is deleted, not rewritten.
Accepted when:
- [x] A1: no file in the repo is 50 KB or more  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A2: `tests/test_foundations.py` proves S2, S3, S5, S7 and S8 end to end through the hooks and the commands  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A3: the design notes the foundations replace (`future/SPEC-v2.md`, `future/SKILL-SPLIT.md`, `future/ISA-HARDENING.md`, `future/project-isa/`) are deleted, and AGENTS.md describes only what exists, with § Later split into Issues and Future tasks  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A4: the examples follow the foundations (E1–E4, no Features, specs without done marks), and every one lints `ok`  (2026-10-07, ISA 20261007-005757_foundations)
- [x] A5: after the new engine is installed, `~/.isa` holds no ISA, ledger, prompt log or session file from before it  (2026-10-07, ISA 20261007-005757_foundations)

## Decisions
- 2026-10-07: tier E3 under the engine as installed, not E4: an E4 there forces a plan, the entity these foundations remove. Lowering a draft's tier is allowed (§ 5.7 of the 2026-10-06 spec); the rule "the tier only goes up" exists to keep an ack from being skipped, and none is.
- 2026-10-07: the evidence ledger is dropped: once only `isa` writes the ISA, the ISA's own Verification lines are the record, and `isa close` re-runs every probe (so tree fingerprints add nothing).
- 2026-10-07: the plan-step warning and the "`~/.isa` is never a project" fix are dropped: the first has no step left to warn about, the second disappears once no script does ISA work.
- 2026-10-07: content commands: a section is written once as a block (`isa write <file> <section>` from stdin); after that, Criteria and Test Strategy change one ISC at a time (`isa write <ISA> ISC-N`, `isa drop`), so every change is targeted and touches no other tick. Any ISC change after the ISA's ack needs a new ack (the user's call, 2026-10-07; "main steps only" and "none" were the other options).

## Open questions
