---
status: acked 2026-10-06 #2b9e4f43
effort: E4
plan: docs/plan/2026-10-06-local-isas-spec-driven.md
---

# Local ISAs, committed specs

## Contents

1. Status
2. What ISA is (skill, engine, hooks)
3. Part A — ISAs back in `~/.isa` (revert SPEC-v2 § 13)
4. Part B — spec-driven development
5. Workflow and enforcement, tier by tier
6. Other specs this touches
7. Open questions and decisions
8. Acceptance
9. Rollout

## 1. Status

**Spec, for discussion. Nothing is implemented.** First draft 2026-10-06. Iteration 2 (same day) records the user's answers to Q1–Q11 (§ 7; all decided). Iteration 3 adds the writing rules for specs and plans (§ B.10) and Q12–Q15. It also moves ISA creation after the acknowledgement and adds the per-tier workflow (§ 5). Part A reverts SPEC-v2 § 13 (M12, built 2026-10-03). Part B is new. Once the user acknowledges this file, it moves to `docs/spec/2026-10-06-local-isas-spec-driven.md` (Q7).

Why, in the user's words after two days with M12: too many files in git, and they are not human-readable; too much machinery (key, filter, import/export); and the benefit, finishing on one computer a task started on another, did not happen in practice. A committed spec that the user acknowledges, then implements, is the better shared artifact.

The core split this spec proposes:

| Artifact | Audience | Lives | Committed (in git) | Checked by |
|---|---|---|---|---|
| Spec (`docs/spec/`) | people | the project | yes | the user's acknowledgement |
| Plan (`docs/plan/`), E4–E5 only | people | the project | yes | the user's acknowledgement |
| Project ISA (`ISA.md` at the project root) | people + engine | the project | yes | `isa verify ISA.md` (standing claims) |
| Task ISA | engine + model | `~/.isa` | **no** | `isa verify` / `isa close` (probes) |

The spec is checked by a person and the ISA by the machine. Each layer owns different facts, and a lower layer points to a higher one instead of restating it (§ B.5).

## 2. What ISA is (skill, engine, hooks)

It is not a Claude Code plugin, and it is more than a skill. It has three parts, installed together by `install.py`:

1. **A skill** (`skill/ISA/` → `~/.claude/skills/ISA/`): the ISA file format, the five workflows, the examples. On its own it is advice: a skill loads only when the model decides to load it.
2. **An engine and CLI** (`runtime/` → `~/.local/share/isa/runtime`, `isa` on PATH; Python stdlib only): the gate decisions, lint, `isa new|lint|verify|close`, the evidence ledger.
3. **Adapters that make it mandatory**: Claude Code user-scope hooks merged into `~/.claude/settings.json` (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop, … → `isa hook claude`), and a pi extension (`adapters/pi/isa.ts` → `~/.pi/agent/extensions/`). There is also an optional statusline (`adapters/claude-statusline/`).

A Claude Code plugin can bundle skills and hooks, so parts 1 and 3 could ship as one. The installer also merges permissions, `additionalDirectories` and the statusLine into `settings.json`, and links a CLI on PATH. Whether a plugin can do all of that has not been checked, and it is out of scope here.

## 3. Part A — ISAs back in `~/.isa` (revert SPEC-v2 § 13)

### A.1 Locations

| What | Where | Committed |
|---|---|---|
| Task ISA (any project, git or not) | `~/.isa/<project>/<slug>/ISA.md` | no |
| Its ephemeral slices | `~/.isa/<project>/<slug>/_ephemeral/` | no |
| Its ledger | `~/.isa/_state/evidence/<slug>-<hash>.jsonl` | no |
| Sessions, prompt logs, debug logs, `errors.log`, ack records | `~/.isa/_state/sessions/`, `prompts/`, `~/.isa/_state/logs/`, `errors.log`, `acks.jsonl` (new) | no (the logs are unchanged: they never left) |
| Project ISA proof | `~/.isa/_state/project/<key>.jsonl` | no (unchanged) |
| Project ISA, specs, plans | at the project root, see § B.1 | yes, in a git repo |

Rules:

- Everything under `~/.isa` is local and never committed, and `isa` never writes `<repo>/.isa/` again.
- `<project>` keeps today's key: the git work-tree root (or the directory) relative to `$HOME`, with `/` → `-`.
- This is today's non-repo branch made the only branch. `state.project_dir` always returns `ISA_HOME/<project-key>`. `evidence.ledger_path` keeps only its `_state/evidence` case, and `evidence.is_ledger_path` drops the `evidence.jsonl` case.
- `root:` becomes absolute again, as for non-repo ISAs today (the repo-relative case in `commands.py` `new` goes).
- Debug logs: no change. They live in `~/.isa/_state/logs/` (`logs.py`), and `isa purge-logs` keeps working.

### A.2 What goes

| Mechanism | Where it lives today | Fate |
|---|---|---|
| The git clean/smudge filter, AES-CTR + HMAC through `openssl`, the long-running filter protocol | `crypt.py` (439 lines) | **deleted** (after the migration of § A.5 has used it) |
| The quoting forms (`user: "…"`, the Goal's opening quote as an encrypted span) and `[user words]` redaction | `quotes.py` (75 lines), `evidence.record` | **deleted**. The `waived: ISC-N — "<words>"` rule (SPEC-v2 § 6.5) stays; it is older than § 13 and keeps its own regex in `rules.py` |
| `isa crypt`, `isa key new\|import\|export\|status` | `cli.py` | **deleted**, with PreToolUse's refusal of `isa key` commands |
| `.gitattributes` lines (`filter=isa`, `merge=union`) and `filter.isa.*` in `.git/config` | written by `crypt.setup_repo` / `ensure_filter` | **deleted**. The migration removes the existing ones |
| `isa migrate` (home → repo) | `commands.migrate` | **replaced** by the one-shot reverse move (§ A.5), then deleted |
| `quote-verified` ledger rows; HMAC entries in the `asks` snapshot | `rules.py` (§ 13.4 block), `commands._asks_snapshot` | **deleted**. The snapshot stores the asks verbatim, as before M12, and lint checks quotes against this machine's prompt log only |
| Missing-key hard stop (Option A) | `engine.py` (prompt hook, PreToolUse), `commands.py` (`new`, `verify`, `close`) | **deleted** |
| "The bound ISA is not on this branch" (§ 13.4b) | `engine.py`, `cli.py` (`isa ls`) | **deleted**: ISAs no longer follow branches |
| `.isa` in the fingerprint and change-check exclusions | `changes.ISA_FILES` | `:(top,exclude).isa` goes; `ISA.md` stays excluded |
| The project ISA's check against the user's quotes | `crypt.lint_project` | **deleted** (Q9: privacy is the user's call, not the tool's) |
| SKILL.md "The user's words are encrypted in git" paragraph; AGENTS.md "Prompts encrypted in git" | docs | **deleted**; "Where ISA files live" is rewritten from § A.1 and § B.1 |
| `ISA_KEY` in the live flow test sandbox | `tests/flow/` | **deleted** |
| `tests/test_m12.py` (34 tests) | tests | the encryption, key, branch and migrate tests are **deleted**; the project-ISA and `promote:` tests are kept (moved to a smaller test file) |
| Project ISA ISC-P6 and its constraint ("the user's verbatim words never reach git…") | `ISA.md` | **deleted** (Q9) |

### A.3 What stays

- **Ledger row `id`s and `(ledger: <id>)` Verification lines.** They are robust without merges too, and reverting them would churn every existing ISA.
- **Readers sort rows by `t`.** Harmless.
- **The `machine` field on rows.** Harmless. It can be dropped later.
- **Classification.** The project root's `ISA.md` stays an ISA path, never a project change.
- **The project ISA**, in full (§ A.4).

### A.4 The project ISA stays committed

The project root's `ISA.md` (`kind: project`) **stays committed** in a git repo and is the only ISA file there. It is **mandatory** (Q6): the first `isa new` or the first spec in a project creates the skeleton when it is missing, in git repos and elsewhere (§ B.1). It keeps every rule it has today: standing claims `- ISC-P<n>:` without a checkbox, Test Strategy entries, `isa verify ISA.md`, never bound, never closed, proof in `~/.isa/_state/project/<key>.jsonl`. A root `ISA.md` of another meaning (no `kind: project`) is still never overwritten; `isa` says so once.

What changes:

- **`promote: true`** finds the project ISA through the task ISA's `root:`, no longer through `state.isa_repo`, which is gone. `isa close` still refuses while a promoted criterion has no `(from <slug> ISC-N)` line there. The slug in that line exists on one machine only. That is accepted: the line states the claim, and the slug is only provenance.
- Its check against the user's quotes goes (§ A.2).

### A.5 Migration (one shot)

Four repos have committed task ISAs today: `jolo-isa` (9 folders, 17 tracked files), `pi-quota-footer` (4, 8), `jev-kit` (3, 6), `jolo-pi` (2, 4). Each also has a root `ISA.md` (`kind: project`) and the `.gitattributes` lines.

`isa migrate --home [--dry-run]`, run inside a repo, does this:

1. For each `<repo>/.isa/<slug>/`: verify that no `enc:v1:` value is left on disk. The smudge filter keeps the files plain; any value that is still encrypted is decrypted with the key, which is why this step runs **before** `crypt.py` is deleted. Then move the folder to `~/.isa/<project>/<slug>/`.
2. Move `evidence.jsonl` to `~/.isa/_state/evidence/<slug>-<hash>.jsonl` (the hash of the **new** path), and rewrite its repo-relative `root` / `cwd` / `files` to absolute paths. Row ids are unchanged, so every `(ledger: <id>)` line still resolves.
3. Rewrite `root: .` (or `root: sub/dir`) in each moved ISA to the absolute path.
4. Rebind the sessions bound to a moved ISA.
5. Remove the two `.isa` lines from `.gitattributes` (and delete the file if nothing else is left in it), and run `git config --remove-section filter.isa`.
6. Leave the root `ISA.md` alone.
7. Print the commit the user runs: `git rm -r --cached .isa && git add .gitattributes && git commit -m "Move task ISAs out of git"`. `isa` never commits.

Failure modes:

- A `<repo>/.isa/` that is not tracked (never committed): moved the same way.
- A slug that already exists in `~/.isa/<project>/`: skipped, and reported.
- No key while an `enc:v1:` value remains: that value is dropped (Q8: the old quotes have no value). The ISA still moves.

### A.6 Git history

**Decided (Q8):** the old encrypted quotes are of no use. After the four migrations, the user deletes `~/.isa/key`. The history is not rewritten: without the key the values are noise, and a rewrite would mean force-pushing four repos for nothing.

### A.7 What is given up, on purpose

Resuming an in-flight ISA on another machine. On machine B you start a new ISA from the same spec section or plan step (§ B.5). The spec and the plan are what travel, because they are what people read.

## 4. Part B — spec-driven development

### B.1 Where specs and plans live

It applies everywhere, git or not (Q5). The **project root** is the git work-tree root, or else the session's directory:

```
<project root>/
├── ISA.md                              ← project ISA (standing claims), mandatory
└── docs/
    ├── spec/YYYY-MM-DD-<slug>.md       ← one spec per piece of work
    └── plan/YYYY-MM-DD-<slug>.md       ← its plan, E4–E5 only, same basename as the spec
```

| Project | Specs, plans, project ISA | Committed |
|---|---|---|
| Git repo | `<repo>/docs/spec/`, `<repo>/docs/plan/`, `<repo>/ISA.md` | yes, by the user, with the code |
| Outside git | `<dir>/docs/spec/`, `<dir>/docs/plan/`, `<dir>/ISA.md` | no git |
| `$HOME` itself, or a temp directory | `~/.isa/<project>/docs/spec/`, `docs/plan/`, `ISA.md` | no (nothing is written into `$HOME` or `/tmp` directly) |

- The file is named `YYYY-MM-DD-<slug>.md`, with the date the spec was started and a topic slug, **never a version number** (Q7). The date keeps `ls` in time order. The shared basename pairs a plan with its spec without a lookup.
- A spec is never moved or renamed after its first acknowledgement, because ISAs and plans link to it.

### B.2 Which tier gets what

The **work tier** (E1–E5, picked as today from blast radius and drift) decides the documents. It is written in the spec's frontmatter. It is not the tier of each ISA: under a plan, each step's ISA has its own tier, usually E2–E3 (§ B.5).

| Tier | Spec | Plan | ISAs | Acknowledgements |
|---|---|---|---|---|
| **E1** | none | none | one, as today | none (the ISA's own gate) |
| **E2** | short spec: Problem, the change, "Accepted when" (≤ ~30 lines) | none | usually one, linked to the spec | spec |
| **E3** | full spec (template § B.3) | none | one or more, each linked to spec sections | spec |
| **E4** | full spec + Decisions, after a second look | yes | one per plan step, created when the step starts | spec, then plan |
| **E5** | as E4, after the Interview ran (it moves from the ISA to the spec) | yes | one per plan step | spec, then plan |

The user can always say "no spec" for E2–E3. The ISA then records `no-spec: the user's call` in Decisions (Q1).

### B.3 Spec template (and plan template)

The writing rules behind these templates are in § B.10.

```markdown
---
status: draft            # draft | acked YYYY-MM-DD #<hash8> | done YYYY-MM-DD
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
- [ ] A2: <…>

## S2 — <…>

## Decisions          (dead ends and rejected approaches; E4–E5: the durable ones, and the second-look: line)
## Open questions     (empty at ack)
```

- **Section ids `S1`, `S2`, … are stable**, like ISC ids: never renumbered. A dropped section keeps its heading with `[DROPPED — <why>]`. Only `S<n>` sections are deliverable and get a done marker.
- "Accepted when" bullets are the seeds of the ISA criteria, and the unit of done (§ B.6). Each has a stable id (`A1`, `A2`, … within its section; full name `S2:A1`). The ISA turns them into atomic, probe-able ISCs, anchored back to the bullet, and does not copy them.
- **Spec lint** (`isa lint <spec>`) checks the shape only:
  - the frontmatter fields;
  - Said and Assumed under Goal;
  - at least one `S<n>` section, each with "Accepted when:" bullets written `- [ ] A<n>:`, with ids unique in their section;
  - no placeholder (TBD, TODO, a lone `…`) and no empty section;
  - an empty Open questions section at ack time;
  - Approaches from E3;
  - `plan:` and a `second-look:` line from E4;
  - `interview:` at E5.

Plan (E4–E5):

```markdown
---
status: draft            # draft | acked YYYY-MM-DD #<hash8> | done YYYY-MM-DD
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
- [ ] P2 — <…> · E3 · covers S1:A3, S2 · after P1
  Interfaces: consumes `<name>` from P1; produces …
  Done when: …
```

A step is ISA-sized: the smallest unit with its own test cycle (§ B.10). Plan lint checks:

- every Accepted-when bullet is covered by some step (`covers S2` covers all of S2's bullets);
- every `after` and every Review focus target names an existing step;
- every step has Files and "Done when";
- no placeholder;
- the size, with a warning when the plan is over 3× the spec's size or mostly code blocks.

### B.4 Acknowledgement

"Acknowledged" means that the user, not the model, said yes to this exact content. Reviewing the spec and the plan is the user's responsibility (Q2); the tool only makes sure that the yes was the user's and still matches the text.

- A0 — plain text (no teeth): the user writes "ack" and the model writes `status: acked`. Rejected: the model can fake it or skip it.
- **A1 — a click, recorded (Recommended, decided):**
  - The model asks the ack question (§ 5.6) only once spec lint passes. The user clicks **Acknowledge** or **Request changes**.
  - On Acknowledge, the engine records `{path, hash, t, session}` in `~/.isa/_state/acks.jsonl`. The hash is the sha256 of the file without its `status:` and `Done:` lines, with tick state ignored (`[x]` read as `[ ]`) and the `(date, ISA …)` suffixes removed.
  - The model then writes `status: acked 2026-10-06 #a1b2c3d4` (the first 8 hex of the hash). PreToolUse refuses that line when no ack record matches it, so the model can't ack on the user's behalf.
  - Because the hash is in the file, any machine can tell whether a committed spec still matches what was acked: it recomputes the hash and compares. No local record is needed to *read* an ack, only to *write* one.
  - An edit to an acked spec breaks the match: the spec reads as **changed since ack** until the user acks it again.
- A2 — `isa ack <path>` typed by the user. Rejected: it costs a command where A1 costs a click.

**Committed at once (Q14).** In a git repo the model commits the acked file right after the ack, and only that file: `git add <spec> && git commit -m "Spec: <title> (acked)"`. The plan is committed the same way after its ack, and so is a re-ack. These are the only commits the workflow makes by itself; code commits stay the user's call. Outside git, nothing is committed.

One rule for both harnesses: **an ack is the explicit go for what it covers.** For E2–E3, acking the spec means "implement it". For E4–E5, acking the spec means "write the plan", and acking the plan means "implement it". The pi IRON LAW ("act only when the user explicitly says so") and the ISA gate meet here.

### B.5 Plan and ISA — do they collide?

Yes, unless each layer owns different facts. Today an E4 ISA would restate the spec (Problem, Vision, Out of Scope, Constraints) and the plan (Features = work breakdown with `depends_on`). That is the same content written three times, in three styles, and it drifts. The fix is ownership: each fact has one home, and the other layers point to it.

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

The notion *"for E4–E5, write the ISA plan after validating the spec"* — the options:

| Option | What the plan is | Verdict |
|---|---|---|
| **P1 — a plan of ISA seeds, ISAs created just in time (Recommended)** | `docs/plan/…`: each step is written as the seed of one future ISA (goal line, tier, `covers S<n>`, "Done when"). When the step starts, `isa new --plan docs/plan/x.md#P2` scaffolds its ISA from the seed. | Reviewable and acked in git; each ISA is written with what the earlier steps taught; nothing is duplicated. |
| P2 — a parent ISA with child ISAs (`References/IsaHierarchy.md`) | A parent ISA in `~/.isa` whose Features are the steps | The machinery exists, but the plan would be local, dense, and not reviewable in git. |
| P3 — one big E4 ISA, its Features as the plan | Nothing in git | Nothing to ack in a readable form; the ISA grows toward the 50 KB read limit (ISA-HARDENING § 1). |
| P4 — every step's ISA scaffolded right after the plan ack | All ISAs up front | Criteria written before anything is learned; by step 3 they are stale. |

So under P1 "write the ISA plan" means yes: the plan is the list of ISAs to come. They are created one at a time, when each step starts.

**Where the E4–E5 rigor goes.** Under P1 the E4–E5 requirements move up to the committed documents, and the step ISAs stay E2–E3:

| E4–E5 requirement today (in the ISA) | Under P1 |
|---|---|
| Decisions section at close | the spec's Decisions (design) and the plan (order) |
| Changelog (conjectured / refuted / learned / criterion now) | a spec Decisions entry when understanding changes. A changed spec needs a re-ack |
| Interview (E5, `interview_ran`) | runs before the spec ack, recorded as `interview:` in the spec |
| Independent second look (`second-look:`) | on the spec before its ack. Per step only for `risk: high` ISCs, as today |
| All eleven articulation sections | the spec has them. The step ISA points to them |

**What lint changes in a linked ISA.** With a `spec:` or `plan:` link, Problem, Vision, Out of Scope and Constraints may be a single pointer line. `stated_goal` may come from the document instead of the prompt (`stated_goal_source: spec`, copied verbatim from the step or Goal line, and lint checks it against that file). That way a prompt like "go" doesn't leave the goal null. Goal, Criteria (with `Anti:`) and Test Strategy stay required.

### B.6 Marking a spec section done

The unit of done is the **acceptance bullet**, not the section. A section that takes one ISA and a section that takes four are handled the same way, with or without a plan. All the marks are written by `isa close` (Q3):

```markdown
## S2 — Ledger back in ~/.isa
Done: 2026-10-09 — 3/3 accepted (ISAs 20261008-101500_ledger-home, 20261009-091200_migrate-repos)
Accepted when:
- [x] A1: isa new prints a path under ~/.isa/<project>/  (2026-10-08, ISA 20261008-101500_ledger-home)
- [x] A2: every (ledger: <id>) line still resolves  (2026-10-08, ISA 20261008-101500_ledger-home)
- [x] A3: the four repos track no .isa/ files  (2026-10-09, ISA 20261009-091200_migrate-repos)
```

- **Bullet ids.** Each "Accepted when" bullet is a checkbox with an id, `A1`, `A2`, …, numbered within its section. Ids are stable like ISC ids: never renumbered, and a dropped bullet stays as `- [ ] A3: [DROPPED — <why>]`. A bullet's full name is `S2:A1`.
- **Links.** A task ISA names what it implements:
  - `spec: docs/spec/2026-10-06-x.md#S2` means every bullet of S2;
  - `spec: docs/spec/2026-10-06-x.md#S2:A1,A2` means only those (a list of such links is allowed);
  - `plan: docs/plan/2026-10-06-x.md#P2` means the bullets that P2 `covers`.
- **Proof, not closing, ticks a bullet.** Each linked bullet must be the `anchors_to` of at least one ISC in the ISA's Test Strategy (`anchors_to: "S2:A1"`). Lint refuses a linked bullet that no ISC anchors to. On a successful close, `isa close` ticks each linked bullet whose anchored ISCs all passed, and appends `(date, ISA <slug>)` to the bullet. A bullet linked by an ISA whose close fails stays `[ ]`.
- **Section done.** When every bullet of `S<n>` is ticked (or dropped), the same close writes the section's `Done:` line under its heading. The line counts the bullets and names every ISA that ticked one. A later close replaces it and never adds a second.
- **Plan step.** A plan step's `[x]` is written when its ISA closes and every bullet it covers is ticked: `- [x] P2 — … · Done: 2026-10-08`.
- **Spec and plan done.** When every section is done, the spec's frontmatter becomes `status: done YYYY-MM-DD`. The plan's status follows its last step.
- **Ticks never break the ack.** Tick state, the `(date, ISA …)` suffix, and the `Done:` and `status:` lines are left out of the ack hash (§ B.4).
- **One writer, after the proof.** These marks are the only project changes `isa close` makes, and it makes them only after the close passed, so the tree it proved stays the tree it proved. Without the hooks installed, the model writes the same marks by hand after a passing close.
- **A tick is history, not a guarantee.** It records that a closed ISA proved the bullet once. Keeping it true is the project ISA's job (`promote: true` turns it into a standing claim).
- **Status without a tool.** `rg '^- \[ \] A' docs/spec/` lists every open bullet, `grep -L '^Done:' docs/spec/*.md` the specs with open sections, and `rg '^- \[ \] P' docs/plan/` the open steps.

### B.7 The gate, with specs

The stage-by-stage rules are in § 5. In short:

- Spec and plan files are articulation, like ISA files. `classify` puts `docs/spec/**` and `docs/plan/**` under the project root in a new kind `spec`: allowed without a bound ISA and never counted as a project change. The ack is their gate, as lint is the ISA's. (Under the current rule, this very spec needed an ISA of its own.)
- Writing a spec binds it to the session, as writing an ISA does. Q2 ("continuation or new task?") then applies to the bound spec or plan as it does to a bound ISA.
- The ON block (`protocol.md`) gets the tier rule and the order: spec, ack, (plan, ack), ISA.

### B.8 Global rules (Claude Code and pi)

The rule has to hold in every session and both harnesses, including before any hook fires and in sessions the gate left OFF. The global instruction files are:

- Claude Code: `~/.claude/CLAUDE.md` (user memory, loaded in every project; it does not exist on this machine yet).
- pi: `~/.pi/agent/AGENTS.md` (exists; holds the IRON LAW).

The same block goes in both, between markers, written by `install.py` (Q4). Draft:

```markdown
<!-- isa:spec-driven:begin -->
## Spec-driven work

Work goes spec → (plan) → ISA → code, in every project. Pick the work tier first (E1–E5, ISA skill § Picking the tier) and say it.

- **E1**: no spec. ISA only.
- **E2–E3**: write `docs/spec/YYYY-MM-DD-<slug>.md` at the project root (template: ISA skill, References/SpecDriven.md). Ask the user to acknowledge it. Then implement it with ISAs linked to its sections (`isa new --spec docs/spec/…#S<n>`).
- **E4–E5**: check the outline with the user, write the spec, ack. Then `docs/plan/YYYY-MM-DD-<slug>.md` (same basename): ISA-sized steps, each one future ISA. Ack the plan. Then one ISA per step, created when the step starts (`isa new --plan …#P<n>`).

Writing rules and red flags: ISA skill, References/SpecDriven.md. In a git repo, commit the spec (and the plan) right after its ack, that file only.

No ISA before the ack: the ISA depends on the spec. An acknowledgement is the user's explicit go for exactly what it covers. Never acknowledge on the user's behalf, and never start code before it. If the build shows the spec is wrong, edit the spec and ask again; don't let the ISA drift from it. Specs, plans and the root `ISA.md` are committed in a git repo. Task ISAs live in `~/.isa` and are not.
<!-- isa:spec-driven:end -->
```

The details (templates, the done marker, the ownership table of § B.5) go in a new skill reference, `skill/ISA/References/SpecDriven.md`, and the global block points there. That keeps the always-loaded text to about 230 words.

### B.9 New code (estimate, for the later plan)

| Piece | Where |
|---|---|
| `spec` path kind; the non-git and `$HOME`/temp locations | `classify.py`, `state.py` |
| Spec binding, stages, Stop and PreToolUse rules of § 5 | `engine.py` |
| Spec and plan lint, ack record, hash, `status: acked` ownership | `specdoc.py (new)`, `engine.py` (PostToolUse / pi `ask_answer`), `adapters/pi/isa.ts` |
| `spec:` / `plan:` / `no-spec:` lint; pointer-line sections; `stated_goal_source: spec` | `lint.py`, `rules.py` |
| `isa new --spec / --plan` (seeded scaffold, ack check, step order) | `commands.py`, `specdoc.py (new)` |
| Bullet ticks (`A<n>` anchored by a passing ISC), section `Done:` line, plan tick, `status: done`, close refused on a changed spec; lint: every linked bullet anchored | `commands.py` (`close`), `specdoc.py (new)` |
| Spec lint (Said/Assumed, placeholders, Approaches) and plan lint (Files, Review focus targets, size warning) | `specdoc.py (new)` |
| `isa new --plan`: Review focus lines as criteria of the owning step, the spec's Constraints shown | `commands.py`, `specdoc.py (new)` |
| Templates, SpecDriven reference (§ B.10 rules, red flags), the three worked examples, SKILL.md / protocol.md lines | `skill/ISA/References/SpecDriven.md`, `skill/ISA/Examples/specs/`, `protocol.md` |
| Global block, install and uninstall | `install.py` |

### B.10 Writing a spec and a plan

These rules go into `skill/ISA/References/SpecDriven.md`. Some come from two outside skills the user reads often (superpowers' brainstorming and writing-plans, read 2026-10-06), reworked for the ISA flow. The ISA process is the reference: nothing is taken as it is, and the skill names no outside source (Q12).

**The spec**

1. **State the tier first; it only goes up.** Say the work tier before the first question ("this looks E3: a spec, no plan"), so the user can correct it. Between two tiers, take the heavier one. During the work the tier only goes up: hidden complexity raises it (say so, then take the new tier's steps), and nothing lowers it, because a lower tier would skip an ack. A step ISA's own tier can still move either way, as today.
2. **Said, then assumed.** The Goal opens with two lists. **Said**: what the user asked for, in their words. **Assumed**: what the model filled in. Most of the ack is the user correcting Assumed. An empty Assumed list means the request was complete, or that nobody looked hard enough.
3. **Questions.** Ask about purpose, constraints and what success looks like first. Use multiple choice where possible (`AskUserQuestion` options). Independent questions go in one call (at most 3). A question that depends on an earlier answer waits for that answer. On pi, ask one per message. Never ask again what the request already says. At E5, run the Interview.
4. **Scope before detail.** A request that covers several independent subsystems becomes several specs, each with its own ack and plan. Split before refining anything.
5. **Approaches (E3+).** Give 2–3 approaches with their trade-offs, the recommended one first. The ones not chosen go into Decisions as dead ends, with the reason. Cut every feature the Goal does not need.
6. **One section, one unit.** Each `S<n>` is one part with one purpose: what it does, how it is used, what it depends on.
   - Code: components with clear interfaces that follow the codebase's patterns. Targeted fixes to code the work touches are in; unrelated refactors are out.
   - Other work (an essay, a brand, an ops change): one deliverable part per section.
   - Size each section to its complexity: a few sentences, up to about 300 words.
7. **Accepted when** names observable outcomes, with the exact values (limits, names, copy) the user gave or agreed to. These are the seeds of the ISA criteria.
8. **Outline check (E4–E5).** Before writing the sections in full, show the outline: Said / Assumed, the chosen approach, and the `S<n>` titles with one line each. Ask one question: **Outline OK / Change it**. It is not an ack. It records nothing and allows nothing beyond writing the full spec. It exists so that a wrong cut is caught before 300 words per section are written.
9. **Self-review before the ack.**
   - Spec lint checks what a script can (§ B.3).
   - The model checks the rest: no two sections contradict each other; no requirement can be read two ways (if one can, pick a reading and write it down); the scope fits one plan.

**The plan (E4–E5)**

10. **Write for the next step's ISA author.** That reader is the model who will write step P3's ISA in a fresh session, without the conversation and without having seen P1 built. A plan is **the set of decisions that reader cannot make alone**: which files, which names and interfaces, which values from the spec, what proves each step. Leave out anything that reader would decide the same way. There are two ways to fail: a plan longer than the code it describes has written the code, and a line that decides nothing ("handle edge cases", "add tests") is a gap.
11. **Header.** Goal (one sentence) and Approach (2–3 sentences), the spec link, then two lists:
    - **Files:** each file created or changed, with its one responsibility (for non-code work, the artifacts).
    - **Review focus:** at most five inputs or failure modes that the spec implies but no step's "Done when" covers, most likely first, each naming its owning step. `isa new --plan` adds each line to that step's ISA as an `Anti:` or behaviour criterion, so it becomes a probe instead of a reminder.
12. **Steps.** Each step has:
    - a goal line, a tier, `covers S<n>` and `after`;
    - **Files**;
    - **Interfaces**, when the work is code: what the step consumes from earlier steps and produces for later ones, with exact names and types. This is how a later step's ISA learns them;
    - "Done when", with the spec's exact values.

    There are no sub-steps. Test-first, red then green, and the evidence belong to the step's ISA (`isa verify --red` → build → `isa verify`), not to the plan.
13. **Step size.** A step is the smallest unit with its own test cycle that a reviewer could reject while approving its neighbour. Setup, configuration and docs fold into the step that needs them (the ISA's vertical-slice rule).
14. **Constraints stay in the spec.** The plan points to them. `isa new --plan` shows them to whoever writes the step's ISA, so nothing is copied and nothing drifts.
15. **Self-review before the ack.**
    - Plan lint checks what a script can (§ B.3).
    - The model checks that the names in one step's Interfaces match their use in later steps, and that every Review focus line has an owning step.

**Red flags** (in SpecDriven.md, next to the rules):

| Thought | Reality |
|---|---|
| "It's small, I'll call it E1 and skip the spec" | Reaching for a lower tier to skip a step is exactly the doubt: take the heavier tier. |
| "The spec is clear, I'll start while they read it" | The gate is the click, not the spec's length. Ask, then wait. |
| "They acked the spec, so the plan is fine too" | An ack covers the file it was given for. The plan gets its own. |
| "It grew, but I'm almost done" | Hidden complexity raises the tier now. Say so. |
| "The ISA criteria cover it, no need to touch the spec" | When the build shows the spec is wrong, the spec changes and is acked again. |
| "I'll put the test steps in the plan to be safe" | The step's ISA owns the probes. The plan owns the decisions. |

**Worked examples** (built in M14 under `skill/ISA/Examples/specs/`, and checked by spec and plan lint as the ISA examples are checked by `tools/lint_isa.py`):

- an E2 short spec, from `e2-backup-verify`;
- an E3 spec, from `e3-help-redesign`;
- an E4 spec with its plan, from `e4-api-migration`.

Each stays consistent with its ISA example.

## 5. Workflow and enforcement, tier by tier

The rule that changes from today: **No ISA before the ack.** For E2–E5 the ISA depends on the spec, so the engine neither requires nor accepts an ISA (`isa new` refuses) until the spec, and for E4–E5 the plan, is acknowledged. Until then the session's deliverable is the document, and code changes are refused because the spec is not acknowledged yet, not because an ISA is missing. E1 keeps today's flow: the ISA comes first.

### 5.1 The flow

```text
 user prompt
     │
     ▼
 Gate Q1: is it work? ── no (Jev < 0.3, or the user picks "Continue without ISA") ──► OFF: nothing enforced
     │
     │ yes (Jev ≥ 0.8, the model's "yes", or the user picks "Enable ISA")
     ▼
 TRIAGE — the model states the tier in its reply
     │
     ├── E1 ───────────────────────────────────────────────┐
     │                                                     │
     ├── E2/E3 ── SPEC DRAFT ◄──────────┐                  │
     │              │ (questions)       │ Request changes  │
     │              ▼                   │                  │
     │            [ Acknowledge spec? ] ┘                  │
     │              │ Acknowledge                          │
     │              ▼                                      │
     │            SPEC ACKED ── isa new --spec …#S1 ───────┤
     │                                                     │
     └── E4/E5 ── [ Outline OK? ] ── Change it ↺
                    │ Outline OK
                    ▼
                  SPEC DRAFT (E5: Interview; E4+: second look)
                    ▼
                  [ Acknowledge spec? ] ── Request changes ↺
                    │ Acknowledge
                    ▼
                  PLAN DRAFT
                    ▼
                  [ Acknowledge plan? ] ── Request changes ↺
                    │ Acknowledge
                    ▼
                  PLAN ACKED ── isa new --plan …#P<n> (next open step) ──┤
                                                                         │
     ┌───────────────────────────────────────────────────────────────────┘
     ▼
 BUILD — one ISA bound: isa lint → isa verify --red → code → isa verify → isa close
     │
     ▼
 isa close passes ──► E1: done
                  ──► E2/E3: its bullets ticked; a section whose bullets are all ticked gets "Done:"; all done → spec status: done
                  ──► E4/E5: its bullets and [x] P<n>; "Done:" on sections now complete → next step, or plan + spec done
```

### 5.2 What each stage enforces

The engine knows the stage from files and records only: the bound document or ISA, the `status:` line and its hash, `acks.jsonl`.

| Stage | How the engine knows | The model may | PreToolUse refuses | Stop refuses the turn end when | User question |
|---|---|---|---|---|---|
| **OFF** | the gate did not say yes, or the Continue pass | anything | nothing | the prompt was not settled (no judge line, no answer) | the gate question, only when Jev is unsure or unavailable |
| **TRIAGE** | ON; nothing bound to the session | read; `isa new --tier E1`; write a spec | every project change: "write the E1 ISA, or the spec, first" | neither an E1 ISA nor a spec draft exists | — |
| **SPEC DRAFT** | a spec bound, no ack matching its hash | write the spec; read; ask questions | project changes; `isa new` (E2+): "spec not acknowledged yet"; the ack question while spec lint fails; a model-written `status: acked` | the spec changed this turn and the turn ends without the ack question, unless its open questions were just asked | clarifying questions, then the spec ack |
| **SPEC ACKED** (E2–E3) | the hash in `status: acked` matches the file | `isa new --spec <path>#S<n>`, then build | project changes until an ISA linking this spec is bound and passes articulation | no ISA bound (today's rule: the ack was the go) | — |
| **PLAN DRAFT** (E4–E5) | spec acked; a plan bound, no matching ack | write the plan | project changes; `isa new`: "plan not acknowledged yet"; the ack question while plan lint fails | the plan changed this turn and the turn ends without the ack question | the plan ack |
| **PLAN ACKED** | the plan's hash matches | `isa new --plan <path>#P<n>` for the next open step | project changes until that step's ISA is bound and passes articulation; `isa new` for a step whose `after` steps are open | no ISA bound | — |
| **BUILD** | an ISA bound | build | today's rules (articulation, ownership, ledger) | today's rules (lint errors, unproven ticks, ticks out of order, …) | today's (a waiver is the user's) |
| **CLOSE** | `isa close` runs | — | — | — | none. `isa close` refuses while the linked spec or plan changed since its ack, and then writes the `Done:` marks |

An `unknown` shell command that changed project files before the ack is reported, and Stop refuses once: *"project files changed before the spec was acknowledged — revert them or ask the user"*.

### 5.3 E1 — no spec

1. The gate says yes. The model states "E1 — no spec".
2. `isa new <slug> --tier E1 --goal "<span>"`, then Goal + Criteria (with one `Anti:`), then `isa lint`. Until lint passes, PreToolUse refuses every project change, and Stop refuses a turn that ends with no ISA (as today).
3. Code, then `isa verify`, then `isa close`.
4. No user question beyond the gate.

If the work turns out bigger, the model raises `effort:` (with a `refined:` row). From E2 the ISA's lint needs a `spec:` link to an acked spec, so further changes are refused until the spec is written and acked. The ISA stays bound, and the model adds the link after the ack.

### 5.4 E2 and E3 — spec, no plan

1. The gate says yes. The model states "E3 — spec, no plan".
2. The model writes `docs/spec/YYYY-MM-DD-<slug>.md` (`status: draft`, `effort: E3`), which binds it to the session. No ISA: PreToolUse refuses `isa new` and every project change with "spec not acknowledged yet".
3. Ambiguities (at most 3; Scaffold's ambiguity check moves here) go into Open questions and are asked. The turn may end on them. The answers are folded into the spec, and Open questions is emptied.
4. `isa lint <spec>` passes, then the model asks the spec ack.
   - Request changes: the model edits and asks again (step 4).
   - Acknowledge: the engine records it, the model writes `status: acked <date> #<hash8>`, and in a git repo commits the spec (that file only).
5. In the same turn (the ack is the go): `isa new --spec <path>#S1,S2` scaffolds the ISA. Its Goal comes from the spec's Goal, draft criteria from the linked "Accepted when" bullets (each anchored to its bullet), the tier from `effort:`, and the context sections are pointer lines. Stop now refuses a turn without a bound ISA.
6. `isa lint`, then `isa verify --red`, then code, then `isa verify`, then `isa close`. The close ticks the linked bullets that its passing ISCs anchor to, and writes `Done:` under each section whose bullets are now all ticked.
7. Bullets left, in S1 or elsewhere: another ISA (`--spec …#S1:A3` or `…#S3`). When all are done, `status: done`.

E2 differs only in the size of the spec and usually has one ISA for the whole spec. If the user says "no spec", the model runs `isa new --tier E2 --no-spec` with `no-spec: the user's call` in Decisions, and the flow is E1's.

### 5.5 E4 and E5 — spec, then plan

1. Steps 1–3 of § 5.4, with `effort: E4` (or E5). Before the sections are written in full, the outline check: Said / Assumed, the chosen approach, the `S<n>` titles with one line each, and one question, **Outline OK / Change it** (§ B.10 rule 8). It is not an ack and records nothing.
2. Before the ack question, spec lint requires:
   - E4+: a `second-look:` line in the spec's Decisions (an independent review, by a subagent or a person, or the reason there was none);
   - E5: the Interview ran (`interview: <date>`).
3. Spec ack and commit, as § 5.4 step 4. This ack is the go for the **plan**, not for code. PreToolUse still refuses project changes and `isa new`.
4. The model writes `docs/plan/YYYY-MM-DD-<slug>.md` (same basename): steps P1…Pn, each with a tier, `covers S<n>`, `after`, and "Done when". Plan lint passes, then the model asks the plan ack (with Request changes looping back). On Acknowledge, it commits the plan.
5. Then `isa new --plan <path>#P1` scaffolds the step's ISA from its seed: tier, Files and Interfaces from the step, the Review focus lines the step owns as criteria, and the spec's Constraints shown. The build happens here, in this session (Q13). `isa new` refuses a step whose `after` steps are open.
6. BUILD as in § 5.4 step 6. The close ticks the bullets P1 covers, ticks P1, and writes `Done:` on each section whose bullets are now all ticked, whichever steps ticked them.
7. The next step: `isa new --plan …#P2`, in the same session or a later one; the plan ack covers all its steps. The last close sets the plan and the spec to `done`.
8. Changing the plan or the spec midway: edit it, and it reads "changed since ack". The open ISA keeps building, but its `isa close` and the next `isa new` refuse until the user acknowledges the change.

### 5.6 Questions the user sees

| # | Question | When | Claude Code | pi | Answers |
|---|---|---|---|---|---|
| 1 | "ISA is not enabled for this prompt (…). Continue?" | the gate didn't settle it (as today) | the model asks with `AskUserQuestion` (injected text); PostToolUse reads the answer | the extension asks with `ctx.ui.select` at `input` | Continue without ISA / Enable ISA |
| 2 | Clarifying questions (at most 3) / the Interview at E5 | the spec draft has open questions | the model asks with `AskUserQuestion` | the model asks in its reply; the user answers in the next prompt | free |
| 2b | "Outline OK?" (Said / Assumed, approach, S-titles) | E4–E5, before the full spec | the model asks with `AskUserQuestion`; nothing is recorded | the model asks in its reply | Outline OK / Change it |
| 3 | "Acknowledge docs/spec/…?" | spec lint passes and Open questions is empty | `AskUserQuestion`, header `Spec ack`; PreToolUse refuses it while spec lint fails; PostToolUse records the answer | the extension asks with `ctx.ui.select` at `agent_before_settle`, when a bound spec changed this turn and passes lint | Acknowledge / Request changes (+ notes) |
| 4 | "Acknowledge docs/plan/…?" | E4–E5, plan lint passes | same, header `Plan ack` | same | Acknowledge / Request changes |
| 5 | Re-ack: "docs/spec/… changed since your ack: <changed sections>. Acknowledge?" | an acked spec or plan was edited | same as 3 / 4 | same as 3 / 4 | Acknowledge / Request changes |

The user is not asked for a tier. The model states it, the user sees it in the reply and in the spec's `effort:`, and can correct it with a word (Q10).

Headless runs (`claude -p`, pi without a UI) can't answer questions 3–5. They stop at SPEC DRAFT or PLAN DRAFT, and can implement only documents acked earlier.

### 5.7 Edge cases

- **Acked yesterday, built today.** A new session's prompt "implement S2" passes the gate. Then `isa new --spec …#S2` checks the hash in the committed `status:` line against the file, which also works on another machine.
- **One section, several ISAs.** Each ISA links the bullets it delivers (`#S2:A1,A2`, then `#S2:A3`). The first close ticks A1 and A2 and leaves S2 open. The last close ticks A3 and writes S2's `Done:` line, which names both ISAs. In parallel sessions it is the same: whichever close ticks the last bullet writes the line.
- **A spec section dropped after the ack**: that is an edit, so it needs a re-ack.
- **The tier raised during the spec draft** (E3 → E4): the model edits `effort:`, and spec lint then asks for the second look and the plan. It is still a draft, so there is nothing to re-ack.
- **The user changes the tier** ("this is E2"): the model edits `effort:` in the draft.

## 6. Other specs this touches

- **SPEC-v2 § 13**: gets a status line, *"Reverted by docs/spec/2026-10-06-local-isas-spec-driven.md Part A"*. Its text stays as history.
- **SKILL-SPLIT** (not built): do Part A first. It deletes the encryption paragraph of SKILL.md (about 2,000 characters), which shrinks what the split must move. Its Q5 (stale `~/.isa` homes for ephemeral slices) becomes moot.
- **ISA-HARDENING** (not built): H1 migrates "the repo's existing `.isa/` ISAs". After § A.5 they are in `~/.isa/dev-jolo-isa/`; H1 targets that folder instead.
- **Scaffold workflow**: its ambiguity check moves to the spec draft for E2–E5 (§ 5.4 step 3). It stays in Scaffold for E1.
- **`References/IsaFormat.md` line 21** (*"Don't invent parallel artifacts… no separate test specs. The ISA covers this surface."*) contradicts the spec layer. Reworded: no parallel *proof* artifacts. The spec holds acceptance in human words, the ISA holds the probes and the evidence (§ B.5), and nothing else claims either.

## 7. Open questions and decisions

- **Q1. E2 weight.** An E2 change with a spec + ack + ISA is three steps where one used to do. **Recommended:** keep the matrix, with the E2 spec capped at the short form (§ B.2), and let the user say "no spec". **Decided (2026-10-06):** as recommended.
- **Q2. Acknowledgement teeth.** A0 (text), A1 (a click, recorded), or A2 (`isa ack` typed by the user)? **Recommended:** A1. **Decided (2026-10-06):** A1. The user acks by clicking, and reviewing the spec and the plan is the user's responsibility.
- **Q3. Who writes `Done:`.** `isa close`, or the model by hand? **Recommended:** `isa close`. **Decided (2026-10-06):** `isa close`. The view the user asked for: yes, with four guards. (1) It writes only after a passing close, so `Done:` always means proven. (2) It replaces rather than appends, so a second close never duplicates. (3) `Done:` and `status:` are left out of the ack hash, so marking done never breaks the ack. (4) Close refuses while the spec changed since its ack, so `Done:` always refers to acked text. The one new thing: it is the first `isa` command that writes a project file, which the user commits with the code.
- **Q4. Who writes the global rule files.** What the question is: Claude Code loads `~/.claude/CLAUDE.md` into every session, in every project; pi loads `~/.pi/agent/AGENTS.md` the same way. These files are yours (pi's already holds your IRON LAW), and the § B.8 text has to get into both. Either `install.py` inserts it between two marker comments, refreshes it on every install, and removes only that block on `--uninstall`, never touching your own text around it. Or you paste it once yourself and keep it in step by hand whenever the workflow changes. The hooks enforce the workflow either way; the global text is what makes the model plan spec-first before any hook fires, and in sessions the gate left OFF. **Recommended:** `install.py`. **Decided (2026-10-06):** (a), `install.py` manages the marked block in both files.
- **Q5. Scope.** Git repos only, or everywhere? **Recommended:** git only. **Decided (2026-10-06):** everywhere, git or not, ISA and spec (§ B.1 gives the locations).
- **Q6. The project ISA skeleton.** Stop creating `ISA.md` automatically? **Recommended:** stop. **Decided (2026-10-06):** no. `ISA.md` is mandatory, and the first `isa new` or spec in a project creates it (§ A.4).
- **Q7. This repo's own specs.** Move to `docs/spec/`? **Recommended:** move this spec once acked; leave the older `future/` files. **Decided (2026-10-06):** yes, with names by topic, never by version. This file becomes `docs/spec/2026-10-06-local-isas-spec-driven.md`.
- **Q8. Git history.** **Recommended:** leave it, keep the key. **Decided (2026-10-06):** the old encrypted quotes are useless. Delete the key after migration, and don't rewrite history or do anything else (§ A.6).
- **Q9. Quoting the user in committed files.** It could still happen where the model writes committed text: a spec, a plan, the project ISA, a commit message. `Done:` lines never hold the user's words. **Recommended:** one self-attested line in the global block. **Decided (2026-10-06):** the user's responsibility. For a privacy-sensitive repo, the user picks private hosting. No rule, no lint, and the project ISA's quote check goes too (§ A.2).
- **Q10. Confirming the tier.** The tier decides spec or no spec, so declaring E1 is how a model would skip the spec. **Recommended:** no extra click. The model states the tier in its reply and in `effort:`, and the user corrects it with a word. Add teeth later only if the debug logs show E1 used for multi-file work. **Decided (2026-10-06):** as recommended.
- **Q11. Building in the same turn as the ack.** After Acknowledge, the model goes straight to `isa new` and the build in the same turn. **Recommended:** yes (the ack is the go). A user who wants to stop picks Request changes or says so in the notes. **Decided (2026-10-06):** yes.
- **Q12. Outside skills.** Adopt superpowers' brainstorming / writing-plans as they are, or keep the ISA process as the reference? **Recommended:** the ISA process, with their ideas reworked into it (§ B.10). **Decided (2026-10-06):** the ISA process is the reference and what is being built. The outside skills are a source of ideas, worked into ISA, never included as they are.
- **Q13. Execution mode at the plan ack.** Build in this session, or one subagent per step? **Recommended:** both, defaulting to here. **Decided (2026-10-06):** build here only, for now. pi has no subagents yet, and ISA is tested in a single session first. Subagent per step is recorded under Later (§ 9).
- **Q14. Commits.** Should the model commit the spec and the plan after their acks? **Recommended:** yes. **Decided (2026-10-06):** yes, that file only (§ B.4). Code commits are unchanged.
- **Q15. Outline check for E4–E5** before the full spec? **Recommended:** yes, one question. **Decided (2026-10-06):** yes (§ B.10 rule 8).

## 8. Acceptance (for the implementation)

Part A:

1. `isa new` inside a git repo prints a path under `~/.isa/<project>/`. Nothing is created under `<repo>/.isa/`, and no `.gitattributes` is written.
2. `rg -nw 'crypt|quote-verified|ISA_KEY|filter\.isa|enc:v1' runtime/ skill/ adapters/` finds nothing once § A.5 has shipped and run.
3. In each of the four repos: `git ls-files .isa` is empty after the user's commit, `git config --get-regexp '^filter\.isa'` prints nothing, and the moved ISAs `isa lint` clean in `~/.isa/<project>/`, with every `(ledger: <id>)` line resolving.
4. `isa verify ISA.md` still re-proves the project ISA. `promote: true` still blocks a close until the project line exists. A project without `ISA.md` gets one from its first `isa new`, in git and out of it.
5. The full unit suite and the pi extension tests pass. `python3 tools/lint_isa.py skill/ISA/Examples/*.md` reports every file `ok`.

Part B:

6. In an ON session with nothing bound: a Write to `docs/spec/…` passes PreToolUse, a project change is refused with "write the E1 ISA, or the spec, first", and a turn that wrote a spec and ends on the ack question is not refused by Stop.
7. `isa new --spec X#S1` exits non-zero before X is acked and after X is edited post-ack (with `status:` and `Done:` lines excepted).
8. A model Write that sets `status: acked … #<hash>` with no matching ack record is refused. After the user clicks Acknowledge, the same Write passes.
9. A passing `isa close` on an ISA with `spec: X#S1` ticks every S1 bullet that a passing ISC anchors to and leaves exactly one `Done:` line under `## S1`. A second close replaces it. A failed close, or a close while X changed since its ack, writes nothing. Lint refuses a linked bullet that no ISC anchors to.
10. A section closed by two ISAs: after the first closes (`spec: X#S2:A1,A2`), A1 and A2 are ticked and S2 has no `Done:` line. After the second closes (`spec: X#S2:A3`), S2's `Done:` line reads `3/3 accepted` and names both ISAs. Ticking does not change the ack hash.
11. With `plan: Y#P2`, a passing close ticks the bullets P2 covers and P2 itself, and sections whose bullets are all ticked get their `Done:` line. `isa new --plan Y#P3` is refused while P3's `after` step is open.
12. The pi extension asks the spec ack at `agent_before_settle` when a bound spec changed and passes lint, and reports the answer to the engine.
13. Outside git, specs go to `<dir>/docs/spec/`. In `$HOME` or a temp directory they go to `~/.isa/<project>/docs/spec/`.
14. `install.py` writes the global block (Q4): a re-run leaves both files byte for byte unchanged, and `--uninstall` removes only the block.
15. In a git repo, the commit right after a spec or plan ack holds that file only. Outside git, no commit is attempted.
16. Spec lint refuses a spec without Said / Assumed, with a placeholder, or (E3+) without Approaches. Plan lint warns on a plan over 3× its spec's size, and refuses a step without Files or a Review focus line without an owning step.
17. `isa new --plan Y#P2` puts the Review focus lines that P2 owns into the new ISA as criteria.

## 9. Rollout

1. **M13a — move home.** Ship `isa migrate --home` while `crypt.py` still exists. The user runs it in the four repos, commits the removal, and deletes `~/.isa/key`.
2. **M13b — remove § 13.** Delete the code, CLI commands, docs and tests of § A.2. Update AGENTS.md and the project ISA. Reinstall.
3. **M14 — spec-driven.** § B.9 and § 5. By its own rule this spec is E4 work, so after the user acks it, this file moves to `docs/spec/2026-10-06-local-isas-spec-driven.md`, and its plan is `docs/plan/2026-10-06-local-isas-spec-driven.md`, with M13a, M13b and the M14 pieces as steps.

**Later (not planned):**

- **Subagent per step** (Q13): the plan ack would offer "one subagent per step". A fresh agent builds each step's ISA against an ephemeral slice, a second one gives the independent second look, and Reconcile merges the slice back. This waits until pi supports subagents and ISA has been tested in single sessions.
