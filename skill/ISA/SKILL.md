---
name: ISA
version: 1.1.0-export.1
description: "Owns the Ideal State Artifact — one markdown file (ISA.md) holding a task's articulated ideal state; scaffolds, interviews, scores completeness, reconciles feature excerpts to master, and appends decisions/changelog/verification across a locked fourteen-section order. USE WHEN ISA, ISC, ideal state, ideal state criteria, task specification, hill-climb, articulating done, definition of done, spec this, what does done look like."
effort: medium
---

# ISA — Ideal State Artifact

When a workflow runs, say so in one line: `Running the **WorkflowName** workflow in the **ISA** skill to ACTION...`

## What it is, and why

The ISA is the single document that articulates "done" for anything whose ideal state we pursue — a project, an application, a library, infrastructure, a work session, an art piece, a strategic decision. It serves five identities at once: ideal state articulation, test harness, build verification, done condition, system of record. This skill owns the canonical template, the five workflows that generate, deepen, score, append to and reconcile it across sessions and agents, and the example library.

Most work starts without a written, testable definition of what finished looks like, so "done" drifts (the goal settled for at the end isn't the one held at the start, and nothing records which was right), vague criteria let anything pass, decisions and dead ends get forgotten and re-litigated, and sessions or agents share no record of what was verified. The ISA fixes "done" as a hard-to-vary explanation: atomic, probe-able criteria, stable IDs that survive edits, and an audit trail of what was conjectured, refuted and learned. It is one markdown file — YAML frontmatter plus a locked fourteen-section body — and the model is its only writer (Write/Edit or the workflows); a tier completeness gate decides which sections each effort level requires.

---

## Where ISA files live

**Task ISAs are local; the project ISA is committed.** Every task ISA lives in `~/.isa/<project>/{slug}/ISA.md` (`slug = YYYYMMDD-HHMMSS_kebab-description`), in a git repo too, with its ephemeral slices in `_ephemeral/` beside it and its evidence ledger in `~/.isa/_state/evidence/`. `<project>` is the git work-tree root (or the directory) relative to `$HOME`, with `/` → `-`. Nothing under `~/.isa` is ever committed, so a task ISA stays on the machine it was written on. `root:` is the absolute path of the project every probe runs in. `isa where` prints the folder, `isa ls` lists its ISAs.

A git repo's **project ISA** is `<repo>/ISA.md`, committed with the code. It is the living spec (`kind: project`): constraints and standing claims (`- ISC-P<n>: …`, no checkbox, re-proved with `isa verify ISA.md`, never closed, never bound to a session), created as a skeleton by the first `isa new` when missing. A task criterion that must hold forever gets `promote: true` in its Test Strategy entry, and you copy it into the project ISA as `- ISC-P<n>: <claim> (from <task slug> ISC-<m>)`; `isa close` refuses until it is there. Specs and plans sit beside it, committed too (`docs/spec/`, `docs/plan/`): when to write them, the templates, the ack and the done marks are in `References/SpecDriven.md`.

## The gate

With the hooks installed (the repo's `install.py`), the harness enforces this loop and judges every prompt that needs a decision once, on arrival — by **Jev** (the `jev` CLI, jev-kit) when available, else by **you**. The user sees who judged (`ISA gate — Jev 0.31 → asking you`).

- **No ISA bound, or the bound one is finished — "is this work?"** Work is a deliverable that could be done wrong in ways the reply alone would not reveal: a change, a fix, a review or audit, a written plan or comparison, finding out why the user's own system misbehaves. Not work: looking something up, showing what a file contains, explaining, discussing, small talk, a straightforward operation whose failure the tool reports (commit, run the tests), or the user asking for no ISA. A yes turns the session **ON**: write the ISA first. Anything else goes to the user. A slash command is judged with its skill's description.
- **An open ISA is bound — "continuation or new task?"** (Jev only, never asks). A continuation edits the existing ISA. A new task needs its own ISA (`isa new`); once it is bound, the open one is marked *paused* (a side task you will come back to) or *superseded* in its ledger, and stays resumable — edit it again while no other open ISA is bound. Editing another ISA (fixing a note, a review adding a finding) changes its content, never the binding.
- **When Jev is unavailable** (off, not installed, out of credit, past its deadline) you answer the first question yourself, with one line anywhere in your reply: `ISA judge (model): yes|no|unsure — <one-line reason>`. `yes` → write the ISA before the work. The turn can't end without the line or an ISA.
- **The user decides whatever is not a yes** — except a clear no (Jev below `jev_quiet`, 0.3), which goes on without a question. You ask — *"ISA is not enabled for this prompt (<judge>: <score or verdict> — <reason>). Continue?"* with **Continue without ISA (Recommended)** and **Enable ISA** (Claude Code: with AskUserQuestion, as the injected text says; pi asks by itself) — and follow their pick. Continue grants the *Continue pass*: no ISA gate for the rest of that prompt (changes go through, no ISA is required at the end, and no `ISA judge (model):` line — the injected text names the pass and overrides earlier ISA instructions for that prompt); the next prompt is judged again. Nobody to ask (a headless run) or `{"ask_without_isa": false}` in `~/.isa/config.json`: the prompt goes on without an ISA.

A session that is OFF turns ON the moment a change is attempted. While ON, changes are refused until an ISA is bound and passes the articulation gate, every ISA edit is linted, and a turn can't end without a bound ISA or with an unproven claim. `isa new` (or writing an `ISA.md` under `~/.isa/` while no open ISA is bound) binds an ISA to the session; a skill finds it with `isa current [--json]`.

Jev also advises, never blocking: `isa verify` warns when it doubts a probe that can't be seen failing first, and `isa close` shows its view of the goal, each ask, and the evidence behind each self-attested tick or tick never seen failing. `{"jev": false}` in `~/.isa/config.json` turns Jev off; `jev_gate` (0.8), `jev_quiet` (0.3) and `jev_doubt` (0.5) set its lines. When a command prints a `Jev:` line (out of credit, over budget, down), relay it to the user word for word.

## You write the content; the `isa` commands write the state

| Step | Command | What it does |
|------|---------|--------------|
| Start | `isa new <slug> --goal "<verbatim span of the prompt>"` | Creates the ISA with frontmatter, `stated_goal` and `root` filled, and binds it |
| Write | Write/Edit | `asks` (each explicit ask, copied verbatim from the prompt), Goal, Criteria, Test Strategy (with `fails-when:` where no red run is possible), Decisions… — never a shell command on an ISA.md |
| Check | `isa lint <ISA>` | Recomputes `progress`, then the gate; changes are refused until it is clean |
| Red | `isa verify --red <ISA>` | Before building: records each behaviour/http/schema probe failing (the baseline) |
| Prove | `isa verify <ISA> [ISC-N…]` | Runs the probes from `root`, ticks what passed, unticks what regressed, writes the Verification lines |
| Attest | `isa verify <ISA> ISC-N --attest "<evidence>"` | Ticks a `manual` / `screenshot` / `eval` criterion with your evidence |
| Close | `isa close <ISA>` | Re-runs every probe; sets `phase: complete` only when all pass and the close gate holds; prints the summary your final answer quotes |

Neither you nor a skill ticks a box or writes a generated Verification line, `progress` or `phase: complete` — the hooks refuse it and name the command. Run `isa verify` and `isa close` with a **600000 ms Bash timeout** (or in the background when the suite is slow): the default 120 s can stop a long run halfway, which corrupts nothing but leaves the ISA open.

**Prove as you go, red before green.** Prefer test-first where a probe is runnable (unit/property test, `bash`, `curl`, `SELECT`), and always for a behaviour/http/schema criterion: write it first and run `isa verify --red <ISA>` before building: it must fail — that red baseline gives the later pass its meaning. Then build and `isa verify` at once; don't batch at VERIFY. Screenshot-only or manual probes are exempt. Features tick in dependency order: a criterion whose Feature `depends_on` an unfinished Feature passes but waits, and a later run ticks it (IsaFormat § Features).

**Only the exit code counts.** A probe passes iff it exits 0; `isa verify` never reads its output. Build the threshold into the command (`jq -e`, `test "$(…)" -le 5`), and negate a search for something that must never appear (`! rg -q 'pattern' file`) — a bare `rg` exits 0 exactly when the forbidden thing is found.

**`fails-when`.** From E2, a mechanical probe whose ISC can't be seen failing first — an `Anti:` ISC, a `kind:` without the red step (config, doc, file, decision, visual, regression), or `red: exempt …` — says what it would see if the claim were false: `fails-when: "<observation>"`. Writing it is where a probe that can't fail (`true`, a grep standing in for running the code) shows itself; `isa close` lists it beside each ISC never seen failing.

---

## Frontmatter

```yaml
---
task: "8 word task description"          # imperative, ≤60 chars, the deliverable
slug: YYYYMMDD-HHMMSS_kebab-description
project: <name>                          # optional label: which codebase this task is about
effort: E3                               # E1..E5 — drives the completeness gate
phase: observe                           # observe|think|plan|build|execute|verify|learn|complete (complete: `isa close` only)
progress: 0/12                           # engine-owned: checked / total leaf ISCs, dropped & waived excluded
started: <ISO-8601>                      # set once
updated: <ISO-8601>                      # every edit
root: /home/me/dev/app                   # engine-owned: the project every probe runs in
asks: ["<verbatim span>", ...]           # you copy each explicit ask from the prompt (lint checks it is verbatim); each needs a `- Ask N:` line at close
# optional
iteration: 2                             # set when a completed ISA is reopened
resumed_at: <ISO-8601>                   # when the last reopen happened
frozen: true                             # completed ISA that must not reopen on edit
stated_goal: "verbatim quote"           # + _source / _signal / _locked (see Scaffold Step 3a)
context_sufficient: true                 # outcome of the ambiguity check
interview_invoked: false                 # Scaffold's ambiguity check asked questions
interview_ran: <ISO-8601>                # set by the Interview workflow — the E5 gate
parent: <slug>                           # hierarchy only — see References/IsaHierarchy.md
children: [<slug>, ...]
---
```

`phase` and `progress` are the machine-readable status surface — anything that displays ISA state (a status line, a dashboard) reads them. Set `phase` at the start and whenever it genuinely changes; `isa close` sets `complete`. `progress` is recomputed by every `isa` command (status readers count the criteria themselves in between).

---

## Completion rules

A run is complete when all fifteen hold. Each rule says how it is enforced — its **teeth**:

- **HOOK** — refused mechanically by a hook or a command;
- **CHECK** — a gate a command runs and records, on facts it can verify;
- **SHAPE** — a command requires a row in the right format, but can't check that it is true;
- **SELF** — honest self-attestation, listed to the user at close.

| # | The run is complete when… | Teeth |
|---|---------------------------|-------|
| 1 | **The stated goal survives verbatim** in `stated_goal` (copied byte-for-byte, never paraphrased; immutable unless the user revises it; `null` only when the literal is contentless), every claim traces to it or to a named derived claim, and at close `- Goal: yes — <evidence>` confirms the result delivers its *intent*, not its surface — the frame-drift check, since all ISCs passing doesn't prove the ISC set still covers what was asked. The literal is the evidence anchor, not the optimization target: hitting "p95 < 200ms" through a percentile-calc edge case passes the surface and fails the intent. `no` blocks the close. | HOOK (`isa new --goal` and lint check the span) + CHECK (`isa close` needs `Goal: yes`) |
| 2 | **Done existed in writing before building** — the ISA passes its articulation gate before the first change. | HOOK (changes refused until it does) |
| 3 | **What must not happen is written down** — at least one `Anti:` criterion, at every tier. | HOOK (lint) |
| 4 | **Experiential goals name an antecedent** — for art, design, content, anything that has to "land", at least one `Antecedent:` criterion names a precondition that reliably produces the target experience. Verifiable goals (build, deploy, schema) don't need one. | SELF |
| 5 | **External prerequisites were probed before execution** — tokens, logins, service config, deploy targets; a missing one blocked or was deferred in Decisions. | SELF |
| 6 | **Material ambiguity was resolved before building** — up to 3 targeted questions, or a stated reasoned default; `context_sufficient` set. A whole-response `proceed` accepts the defaults. | CHECK (lint at articulation) |
| 7 | **A reported bug was reproduced before its suspect code was read**, and the fix went upstream when one fix kills the class. Not reproduced → a `repro-bypass: pure-additive \| non-isolable \| repro would cause damage — <why>` row. | SELF + SHAPE |
| 8 | **No claim closed without tool evidence of the right type** — file → read it, code → run it, command → its checked output, HTTP → `curl -i`, web/UI → a real browser or HTTP probe, appearance → an image actually looked at, motion → a frame scrub, schema → a query, config → read-back. The entry's `kind:` sets the minimum probe type (table in IsaFormat § Test Strategy); "should work" never closes anything. | HOOK (only `isa verify` ticks) + CHECK (`kind:` table, downgrades); choosing `kind:` is SELF |
| 9 | **A defect that is one instance of a class** closed only after one search enumerated every sibling — each fixed and verified, or tombstoned: `class-sweep: <class> — N siblings via <probe>; M fixed, K tombstoned` (required by close for a Test Strategy `class:`). | SHAPE + SELF |
| 10 | **Every explicit ask was met, skipped with a reason, or surfaced** — one `- Ask N:` line per entry of `asks`; scope narrowed only where the user ratified it; no claim passed because its wording was softened mid-run. A depth directive ("go deep", "quick pass") is an ask. | SHAPE (`isa close`: a missing line is unmet) + SELF |
| 11 | **The builder never rubber-stamped its own build** — work with a `risk: high` ISC, or at E4+, got an independent second look or a row saying why not (`second-look:`); contradictions surfaced (two re-calls, then escalate to the user); every finding dispositioned (`finding: … — adopted / rebutted / deferred`). | SHAPE + SELF |
| 12 | **The run left its trail in the ISA** — decisions including dead ends; conjectured / refuted-by / learned / criterion-now entries when understanding changed; evidence per claim. | SHAPE (lint, E4+) + SELF |
| 13 | **State was observable without asking** — `phase` and `progress` true. | HOOK (the engine writes `progress` and `complete`) |
| 14 | **The ISA at close is not the ISA at open** — every discovery (user corrections, failed probes, new constraints, implied wants) was folded in right away: criteria added, split, tightened, or killed; an ISA untouched after one is stale. Falsifier: failed probes or user corrections in the transcript with no ISA edit after them. | SELF + nudge (a failed probe asks "claim wrong or code wrong?") |
| 15 | **The spend matched the task** — depth, parallelism and time scaled to what the work revealed; breaks either way surfaced. A depth directive with no visible effect is a break. | SELF |

---

## Lifecycle rules (the file is written and updated, never left stale)

- **Reopen after complete.** Editing the body of a `phase: complete` ISA means the work resumed: set `phase: learn`, increment `iteration` (start at 2), add `resumed_at: <ISO-8601>`, and append a Decisions row `refined: reopened after complete — <why>`. `frozen: true` opts out (the edit is a pure correction). It closes again only through `isa close`.
- **Waive or defer, never fudge.** A probe that genuinely can't run yet gets a `- ISC-N: [DEFERRED-VERIFY] — <why> — follow-up: <what>` Verification line; the ISC stays `[ ]`. Only the user can waive an ISC, and the row quotes them: `waived: ISC-N — "<their words>"`; waived ISCs leave the `progress` denominator.
- **Close.** `isa close <ISA>` sets `phase: complete` only when every non-dropped leaf ISC is ticked by `isa verify` or waived by the user (the engine ticks a nested parent once all its leaves are); a `- Goal: yes` line (rule 1) and one `- Ask N:` line per ask exist; the close gate holds at the ISA's tier (CheckCompleteness with `moment: close`), including the `second-look:` / `class-sweep:` rows the rules call for, and no item is still blocked from an earlier turn; and its re-run of every mechanical probe passes without changing the tree. Self-attested ticks and ticks with no red baseline are listed to the user.
- **Close contract.** Your final answer quotes the `isa close` summary — which claims closed on what evidence, which are self-attested or have no red baseline, what was waived, deferred, or asked — instead of paraphrasing it.

---

## The Fourteen-Section Body (locked order)

The fourteen sections are a *capacity*, not a requirement: the tier gate decides which are required; a section not required and not yet written is absent (Decisions, Changelog, Verification until there is something real to record), never empty. Length is never graded; one sentence can be exactly right. **Order is fixed**.

| # | Section | Purpose | Written At |
|---|---------|---------|------------|
| 1 | `## Problem` | What is broken or missing right now that makes the ideal state worth pursuing | OBSERVE |
| 2 | `## Vision` | What delight looks like — experiential intent, 1–5 sentences | OBSERVE |
| 3 | `## Out of Scope` | Anti-vision — what is *not* included in this ideal state, declared upfront in prose | OBSERVE |
| 4 | `## Principles` | Substrate-independent truths (Deutsch reach) the work must respect | OBSERVE |
| 5 | `## Constraints` | Immovable architectural mandates that bound the solution space | OBSERVE |
| 6 | `## Dependencies` | Cross-ISA needs, one machine-readable `requires: <slug> — <contract>` line each — only when the ISA participates in a hierarchy | OBSERVE |
| 7 | `## Goal` | The hard-to-vary spine — 1–3 sentences naming verifiable done | OBSERVE |
| 8 | `## Criteria` | Atomic ISCs (Ideal State Criteria) — one binary tool probe each, including derived `Anti:` ISCs | OBSERVE → EXECUTE |
| 9 | `## Bridge Criteria` | Cross-ISA integration ISCs (`Bridge:` prefix) verified across the seam as a distinct VERIFY pass — only when the ISA has siblings | OBSERVE → EXECUTE |
| 10 | `## Test Strategy` | Per-ISC verification — one YAML entry per leaf ISC (`isc`, `anchors_to`, `type`, `kind`, `check`, `threshold`, `tool`, and `risk` when the ISC touches secrets, auth, money or deploys); shape in `References/IsaFormat.md` | OBSERVE/PLAN |
| 11 | `## Features` | Work breakdown — one YAML entry per vertical slice (`name`, `description`, `satisfies`, `depends_on`, `parallelizable`); shape in `References/IsaFormat.md` | PLAN |
| 12 | `## Decisions` | Timestamped decision log including dead ends; `refined:` prefix for Goal/ISC restructures | any phase |
| 13 | `## Changelog` | Conjecture / refuted-by / learned / criterion-now entries — Deutsch error-correction trail | LEARN |
| 14 | `## Verification` | Evidence per ISC — generated by `isa verify` from its ledger — plus your `- Ask N:`, `[DEFERRED-VERIFY]` and `- Goal:` lines | VERIFY |

`## Dependencies` and `## Bridge Criteria` are **conditional-required**: mandatory when the ISA has any `parent:`/`children:`/cross-ISA relationship, omitted for a standalone single-ISA task. Multi-ISA trees are rare — full mechanics in `References/IsaHierarchy.md`.

ISC line format: `- [ ] ISC-N: <end state, 8–12 words, binary>` — all ISCs number sequentially in one pool; `Anti:` / `Antecedent:` / `Bridge:` prose prefixes carry the kind. Nested IDs (`ISC-4.1`) are allowed; the one-probe rule applies at the leaves.

**Features are vertical slices, not horizontal layers.** Each `## Features` entry cuts end-to-end to a verifiable increment satisfying ≥1 ISC — not "the data layer" then "the API layer." A Feature you can't independently verify on its own is a horizontal slice; re-slice it vertically.

**The Changelog format is non-negotiable.** Every entry needs all four pieces (`conjectured`, `refuted by`, `learned`, `criterion now`) in that order. Append refuses a partial C/R/L; with any piece missing, the entry is a Decision, not a Changelog. The format is what makes the Deutsch error-correction trail auditable across sessions.

---

## Three-Guardrail Taxonomy (Principles vs Constraints vs Anti-criteria)

Adjacent concepts. Distinguished by **who they bind**.

| Guardrail | Binds | Tone | Example | Lives In |
|-----------|-------|------|---------|----------|
| **Principles** | The *thinking* | Aspirational, generalizable | "User-facing systems prioritize responsiveness." | `## Principles` |
| **Constraints** | The *solution space* | Immovable, non-negotiable | "We do not roll our own cryptography — OAuth via industry-standard libraries only." | `## Constraints` |
| **Out of Scope** | The *vision* | Declared, explicit, prose | "Mobile native apps are not part of v1." | `## Out of Scope` |
| **Anti-criteria** | The *test surface* | Granular, testable, yes/no | "Anti: /admin returns 200 in v1 build." | `## Criteria` (with `Anti:` prefix) |

The first three are author-stated (declarative). Anti-criteria are derived from Out of Scope plus regression-prevention concerns — they are how Out of Scope, Constraints and Principles become probe-able. No anti-criterion at OBSERVE is a hard CheckCompleteness failure.

---

## Tier Completeness Gate (HARD at all tiers)

Quality gates, not section counts. Checked at two moments: **articulation** (done written down, nothing built) and **close** (before `phase: complete`). Articulation sections (1–11) are checked at both; record sections (Decisions, Changelog, Verification) only at close, because they record what happened and must never be invented early. CheckCompleteness reports each section `present` / `missing` / `empty` (never acceptable) / `not-yet` (a record section at articulation); at articulation a miss blocks building, at close it blocks `phase: complete`.

| Tier | Articulation sections | Record sections at close |
|------|----------------------|--------------------------|
| **E1** | Goal, Criteria | Verification |
| **E2** | Problem, Goal, Criteria, Test Strategy | Verification |
| **E3** | Problem, Vision, Out of Scope, Constraints, Goal, Criteria, Features, Test Strategy | Verification |
| **E4** | All eleven (Dependencies/Bridge Criteria only when cross-ISA links exist) | Decisions, Changelog\*, Verification |
| **E5** | Same as E4 | Same as E4, plus the Interview workflow ran before BUILD (`interview_ran`) |

\* Satisfied by ≥1 C/R/L entry, or by a Decisions row `no belief refuted this run`. A Changelog is never faked.

**Picking the tier.** Choose it from the work itself — blast radius, number of subsystems, how far "done" could drift — not from the prompt's length. The user's explicit call ("quick pass", "go deep", "E4") always wins.

| Tier | Looks like | Example |
|------|-----------|---------|
| E1 | One small change, minutes, nothing to decide | add a `--no-color` flag |
| E2 | One bounded change in one domain; mostly mechanical but must be proven | SHA-256 verify mode; rotate a CI credential |
| E3 | A feature or small project with several parts, or anything experiential. **Default when unsure.** | a CLI tool; an essay; a `--help` redesign |
| E4 | Cross-cutting work over many subsystems or users, with decisions worth recording | REST → GraphQL migration; brand identity |
| E5 | Multi-week, multi-team, or high-blast-radius (money, auth, personal data, compliance) | HIPAA patient portal; a 12-track album |

The tier can change mid-run when the work reveals more (or less) than expected: update `effort:` and log a Decisions row `refined: tier E2 → E3 — <why>`.

---

## Workflow Routing

Match the verb in the request to a workflow. When ambiguous, default to Scaffold for new ISAs and CheckCompleteness for audits.

| Verb / Intent | Workflow | File |
|---------------|----------|------|
| "scaffold", "create", "generate", "new ISA from this prompt", "extract feature as ephemeral" | **Scaffold** | `Workflows/Scaffold.md` |
| "interview me", "fill in the ISA", "deepen", "ask me questions" | **Interview** | `Workflows/Interview.md` |
| "check", "audit", "score this ISA", "is it complete?" | **CheckCompleteness** | `Workflows/CheckCompleteness.md` |
| "reconcile", "merge feature file back", "ephemeral → master" | **Reconcile** | `Workflows/Reconcile.md` |
| "append decision", "append changelog", "append goal line", "answer the asks", "record C/R/L entry" | **Append** | `Workflows/Append.md` (ISC evidence lines come from `isa verify`, not from Append) |

Typical call points (the skill is invocation-agnostic — the same from a loop or called directly by the user):

- Start of work: `isa new`, then `Skill("ISA", "scaffold from prompt at tier T")` fills the body.
- End of articulation: `isa lint <ISA>`; for the judgment parts, `Skill("ISA", "check completeness of <path> at tier T")`.
- Planning parallel work: `Skill("ISA", "extract feature <name> as ephemeral file from <master-isa-path>")`; after the worker: `Skill("ISA", "reconcile <ephemeral-path> → <master-path>")`.
- Any time: `Skill("ISA", "append decision|changelog|verification to <path>: ...")`.

---

## ID stability and ephemeral feature files

**ISC IDs never re-number on edit.** When the Splitting Test produces a finer-grained version of `ISC-7`, `ISC-7` stays as the parent and the children become `ISC-7.1`, `ISC-7.2`. A dropped ISC leaves a tombstone, `- [ ] ISC-N: [DROPPED — see Decisions YYYY-MM-DD]`, so references in Decisions, Changelog and Verification stay valid. Reconcile is keyed on these IDs: renumbering breaks ephemeral feature-file merges silently, and it looks like "the worker's checkmarks didn't land in master."

**Ephemeral files (parallel workers).** To work a feature in an isolated context (a subagent, a worktree, a parallel coding-agent instance), Scaffold's ephemeral mode (`ephemeral_feature` input) writes a derived slice of the master to `_ephemeral/<feature>.md`: the Vision and Goal as read-only context, the relevant Constraints, the ISCs in the feature's `satisfies:` list with stable IDs, and the matching Test Strategy entries (no Verification section — it appears with the worker's first entry). A fresh-context agent works against that file alone. At completion, Reconcile merges its Decisions, Changelog entries and `[DEFERRED-VERIFY]` lines back to master, runs `isa verify <master>` on the slice's ISCs — the engine ticks what passes there; a worker's checkmarks are never copied over — and archives the slice under `_ephemeral/.archive/`.

**Ephemeral files are derived views, never sources of truth, never hand-edited as policy — and master content is never hand-edited from one: the master ISA is what persists; the ephemeral is what gets archived.** Reconcile is deterministic — there are no conflicts to resolve: an ISC ID either exists in master (mechanical merge) or doesn't (abort with an ID-stability violation). Structural changes made in the ephemeral (splitting ISC-7 into ISC-7.1/ISC-7.2) go into master by a separate Edit by the user *before* Reconcile runs.

---

## Examples

`Examples/` holds reference ISAs spanning tier (E1–E5) × domain (code / art / design / ops / marketplace / enterprise). Each passes the gate for its tier and phase: one Test Strategy entry per leaf ISC, probes out of the criterion text (except at E1, which has no Test Strategy), ticks backed by Verification lines. None is part of a hierarchy, so none shows Dependencies or Bridge Criteria — see `References/IsaHierarchy.md`. Read the canonical showpiece before scaffolding a new ISA and copy its section headers; pick the example closest to your domain + scale as a template; read `e3-project.md` to see a closed ISA.

| File | Tier | Purpose |
|------|------|---------|
| `Examples/canonical-isa.md` | E5 | **BeanLine** — peer-to-peer specialty-coffee marketplace. The showpiece: every standalone section populated, a verbatim `stated_goal` with every probe anchored to it (`anchors_to`), nested ISCs, property probes, real-feeling Decisions and a four-piece C/R/L Changelog. Read first. |
| `Examples/e1-minimal.md` | E1 | Add a `--no-color` flag to a CLI tool. Goal + 4 ISCs only — the fast-path floor. |
| `Examples/e2-backup-verify.md` | E2 | SHA-256 verification for a backup CLI's `--verify` mode. 18 ISCs. |
| `Examples/e2-rotate-credential.md` | E2 | Rotate a production deploy credential in CI — the ISA applied to ops/runbook work. |
| `Examples/e3-project.md` | E3 | An arxiv metadata extractor CLI — **closed** (`phase: complete`). Every ISC verified, one user waiver, a Changelog entry, and the closing `Goal:` line. |
| `Examples/e3-essay.md` | E3 | A 1500-word essay. Experiential goal, antecedent ISCs, post-publish reception probes. |
| `Examples/e3-help-redesign.md` | E3 | Redesign a CLI's `--help` output. Antecedents + usability tests. |
| `Examples/e4-api-migration.md` | E4 | REST → GraphQL with 6-month backwards-compat. 73 ISCs, every section populated. |
| `Examples/e4-brand-identity.md` | E4 | **Cardinal** — brand identity for a fintech startup. 56 ISCs, 6 antecedents. |
| `Examples/e5-desktop-app.md` | E5 | **WattWatch** — desktop home-energy monitor. Populated Changelog. |
| `Examples/e5-album.md` | E5 | **Mariner Frequencies** — 12-track album over 6 months. Long-form experiential. |
| `Examples/e5-enterprise.md` | E5 | **Beacon Health Alliance** — HIPAA patient portal. Compliance anti-criteria, parallel features. The E5 reference Scaffold reads. |

## References

- `References/IsaFormat.md` — the file-shape contract (frontmatter fields, section schemas, ISC grammar, probe-type vocabulary). **It wins on contradiction:** if this skill's prose drifts from it, reconcile them deliberately — don't silently pick one.
- `References/IsaSystem.md` — the conceptual frame (five identities, three guardrails).
- `References/IsaHierarchy.md` — multi-ISA trees, Dependencies, Bridge Criteria. Load only when an ISA has `parent:`/`children:`.
- `References/SpecDriven.md` — spec → ack → (plan → ack) → ISA: tiers, templates, writing rules, done marks.
- `References/IsaLoop.md` — the work loop the skill serves (articulate, build, verify, fold back): phases, standing questions, resume. The skill owns the artifact, not the loop; the completion rules are in this file.
