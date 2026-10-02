---
name: ISA
version: 1.1.0-export.1
description: "Owns the Ideal State Artifact — one markdown file (ISA.md) holding a task's articulated ideal state; scaffolds, interviews, scores completeness, reconciles feature excerpts to master, and appends decisions/changelog/verification across a locked fourteen-section order. USE WHEN ISA, ISC, ideal state, ideal state criteria, task specification, hill-climb, articulating done, definition of done, spec this, what does done look like."
effort: medium
---

# ISA — Ideal State Artifact

When a workflow runs, say so in one line: `Running the **WorkflowName** workflow in the **ISA** skill to ACTION...`

## What It Does

The ISA is the single document that articulates "done" for any thing whose ideal state we are pursuing — a project, an application, a library, infrastructure, a work session, an art piece, a strategic decision. It serves five identities at once: ideal state articulation, test harness, build verification, done condition, system of record. This skill owns the canonical template, the workflows that generate and refine ISAs, and the example library.

## The Problem

Most work starts without a written, testable definition of what finished looks like, so "done" drifts — the goal in your head at the start isn't the goal you settle for at the end, and there's no record of which one was right. Criteria stay vague enough that anything passes, decisions and dead ends get forgotten and re-litigated, and when work spans multiple sessions or multiple agents there's no shared source of truth for what's been verified. The ISA fixes "done" as a hard-to-vary explanation with atomic, probe-able criteria, a stable-ID structure that survives edits, and an audit trail of what was conjectured, refuted, and learned.

## How It Works

The ISA is a single markdown file with YAML frontmatter and a locked fourteen-section body. The model is the only writer (Write/Edit or these workflows). A tier completeness gate decides which sections are required at which effort level, and five workflows generate, deepen, score, append to, and reconcile the artifact across sessions and agents.

---

## Where ISA files live

Every ISA is a **task ISA**: `~/.isa/<project>/{slug}/ISA.md`, with `slug = YYYYMMDD-HHMMSS_kebab-description`. It is created at the start of a piece of work and closed at `phase: complete`. Ephemeral feature slices live beside it at `~/.isa/<project>/{slug}/_ephemeral/<feature>.md`. `<project>` is the project key — the git work-tree root (or the directory) as a path relative to `$HOME` with `/` → `-` (`~/dev/app` → `dev-app`); `isa where` prints it, `isa ls` lists that project's ISAs, `isa new <slug>` creates a fresh one and prints its path.

When the ISA hooks are installed (see the repo's `install.py`), the harness enforces this loop. Every prompt is judged once: work with a checkable end state turns the session **ON** (a review counts — nothing has to change on disk), a question or a conversation leaves it **OFF**, and a misjudged OFF turns ON the moment a change is attempted. While ON, changes are refused until an ISA is bound and passes the articulation gate, every ISA edit is linted, and a turn can't end without a bound ISA or with an unproven claim. `isa new` (or writing/editing an `ISA.md` under `~/.isa/`) binds an ISA to the session.

**You write the content; the `isa` commands write the state.**

| Step | Command | What it does |
|------|---------|--------------|
| Start | `isa new <slug> --goal "<verbatim span of the prompt>"` | Creates the ISA with frontmatter, `stated_goal`, `asks` and `root` filled, and binds it |
| Write | Write/Edit | Goal, Criteria, Test Strategy, Decisions… — never a shell command on an ISA.md |
| Check | `isa lint <ISA>` | Recomputes `progress`, then the gate; changes are refused until it is clean |
| Red | `isa verify --red <ISA>` | Before building: records each behaviour/http/schema probe failing (the baseline) |
| Prove | `isa verify <ISA> [ISC-N…]` | Runs the probes from `root`, ticks what passed, unticks what regressed, writes the Verification lines |
| Attest | `isa verify <ISA> ISC-N --attest "<evidence>"` | Ticks a `manual` / `screenshot` / `eval` criterion with your evidence |
| Close | `isa close <ISA>` | Re-runs every probe; sets `phase: complete` only when all pass and the close gate holds; prints the summary your final answer quotes |

You never tick a box or write a generated Verification line, `progress`, or `phase: complete` yourself — the hooks refuse it and name the command.

(A long-lived per-repo "project ISA" is not supported — it is a possible future feature, not part of this skill.)

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
asks: ["<verbatim span>", ...]           # the prompt's explicit asks; each needs a `- Ask N:` line at close
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
| 1 | **The stated goal survives verbatim** in `stated_goal` (immutable unless the user revises it; `null` only when the literal is contentless), every claim traces to it or to a named derived claim, and at close `- Goal: yes — <evidence>` confirms the result delivers its *intent*, not its surface. `no` blocks the close. | HOOK (`isa new --goal` and lint check the span) + CHECK (`isa close` needs `Goal: yes`) |
| 2 | **Done existed in writing before building** — the ISA passes its articulation gate before the first change. | HOOK (changes refused until it does) |
| 3 | **What must not happen is written down** — at least one `Anti:` criterion. | HOOK (lint) |
| 4 | **Experiential goals name an antecedent** — at least one `Antecedent:` criterion. | SELF |
| 5 | **External prerequisites were probed before execution** — tokens, logins, service config, deploy targets; a missing one blocked or was deferred in Decisions. | SELF |
| 6 | **Material ambiguity was resolved before building** — up to 3 targeted questions, or a stated reasoned default; `context_sufficient` set. A whole-response `proceed` accepts the defaults. | CHECK (lint at articulation) |
| 7 | **A reported bug was reproduced before its suspect code was read**, and the fix went upstream when one fix kills the class. Not reproduced → a `repro-bypass: pure-additive \| non-isolable \| repro would cause damage — <why>` row. | SELF + SHAPE |
| 8 | **No claim closed without tool evidence of the right type** — file → read it, code → run it, command → its checked output, HTTP → `curl -i`, web/UI → a real browser or HTTP probe, appearance → an image actually looked at, motion → a frame scrub, schema → a query, config → read-back. The entry's `kind:` sets the minimum probe type; "should work" never closes anything. | HOOK (only `isa verify` ticks) + CHECK (`kind:` table, downgrades); choosing `kind:` is SELF |
| 9 | **A defect that is one instance of a class** closed only after one search enumerated every sibling — each fixed and verified, or tombstoned: `class-sweep: <class> — N siblings via <probe>; M fixed, K tombstoned` (required by close for a Test Strategy `class:`). | SHAPE + SELF |
| 10 | **Every explicit ask was met, skipped with a reason, or surfaced** — one `- Ask N:` line per entry of `asks`; scope narrowed only where the user ratified it; no claim passed because its wording was softened mid-run. A depth directive ("go deep", "quick pass") is an ask. | SHAPE (`isa close`: a missing line is unmet) + SELF |
| 11 | **The builder never rubber-stamped its own build** — work with a `risk: high` ISC, or at E4+, got an independent second look or a row saying why not (`second-look:`); contradictions surfaced (two re-calls, then escalate to the user); every finding dispositioned (`finding: … — adopted / rebutted / deferred`). | SHAPE + SELF |
| 12 | **The run left its trail in the ISA** — decisions including dead ends; conjectured / refuted-by / learned / criterion-now entries when understanding changed; evidence per claim. | SHAPE (lint, E4+) + SELF |
| 13 | **State was observable without asking** — `phase` and `progress` true. | HOOK (the engine writes `progress` and `complete`) |
| 14 | **The ISA at close is not the ISA at open** — every discovery (corrections, failed probes, new constraints, implied wants) was folded in as it arrived: criteria added, split, tightened, or killed. Falsifier: failed probes or user corrections in the transcript with no ISA edit after them. | SELF + nudge (a failed probe asks "claim wrong or code wrong?") |
| 15 | **The spend matched the task** — depth, parallelism and time scaled to what the work revealed; breaks either way surfaced. A depth directive with no visible effect is a break. | SELF |

**Close contract.** Your final answer quotes the `isa close` summary — which claims closed on what evidence, which are self-attested or have no red baseline, what was waived, deferred, or asked — instead of paraphrasing it.

---

## The Fourteen-Section Body (locked order)

Every ISA may have up to fourteen body sections. The tier completeness gate decides which are required at which effort tier; sections never appear empty. **Order is fixed**.

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

`## Dependencies` and `## Bridge Criteria` are **conditional-required**: mandatory when the ISA has any `parent:`/`children:`/cross-ISA relationship, omitted (like any empty section) for a standalone single-ISA task. Multi-ISA trees are rare — full mechanics in `References/IsaHierarchy.md`.

ISC line format: `- [ ] ISC-N: <end state, 8–12 words, binary>` — all ISCs number sequentially in one pool; `Anti:` / `Antecedent:` / `Bridge:` prose prefixes carry the kind. Nested IDs (`ISC-4.1`) are allowed; the one-probe rule applies at the leaves.

---

## Three-Guardrail Taxonomy (Principles vs Constraints vs Anti-criteria)

Adjacent concepts. Distinguished by **who they bind**.

| Guardrail | Binds | Tone | Example | Lives In |
|-----------|-------|------|---------|----------|
| **Principles** | The *thinking* | Aspirational, generalizable | "User-facing systems prioritize responsiveness." | `## Principles` |
| **Constraints** | The *solution space* | Immovable, non-negotiable | "We do not roll our own cryptography — OAuth via industry-standard libraries only." | `## Constraints` |
| **Out of Scope** | The *vision* | Declared, explicit, prose | "Mobile native apps are not part of v1." | `## Out of Scope` |
| **Anti-criteria** | The *test surface* | Granular, testable, yes/no | "Anti: /admin returns 200 in v1 build." | `## Criteria` (with `Anti:` prefix) |

The first three are author-stated (declarative). Anti-criteria are derived — they are how Out of Scope, Constraints, and Principles become probe-able.

---

## Tier Completeness Gate (HARD at all tiers)

Quality gates, not section counts — sections exist because content exists. The gate is checked at two moments: **articulation** (done written down, nothing built) and **close** (before `phase: complete`). Articulation sections (1–11) are checked at both; record sections (Decisions, Changelog, Verification) only at close, because they record what happened and must never be invented early.

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

`CheckCompleteness` enforces this gate: at articulation a miss blocks building; at close it blocks `phase: complete`.

---

## Lifecycle rules (the file is written and updated, never left stale)

- **Done exists in writing before building.** For any non-trivial task, the ISA (Goal + Criteria at minimum) is written before the first build step.
- **Fold discoveries in as they arrive.** Corrections from the user, failed probes, new constraints, implied wants → add, split, tighten, or kill ISCs right away. The ISA at close is not the ISA at open; an ISA untouched after a surprising discovery is stale.
- **Prove ISCs as you go.** For a behaviour/http/schema criterion, write its test first and run `isa verify --red <ISA>` before building (the probe must fail — that red baseline is what makes the later pass mean something). Then build, and run `isa verify <ISA> [ISC-N…]`: it runs each probe from the ISA's `root`, ticks what passes, unticks what regressed, and writes the Verification line. Don't batch at VERIFY. Self-attested criteria (`manual`, `screenshot`, `eval`) are ticked with `isa verify <ISA> ISC-N --attest "<evidence>"`. Features tick in dependency order: a criterion whose Feature `depends_on` an unfinished Feature passes but waits, and a later run ticks it (IsaFormat § Features).
- **No ISC closes without tool evidence of the right type** — see completion rule 8 and the `kind:` table in IsaFormat § Test Strategy. "Should work" never closes an ISC.
- **Reopen after complete.** Editing the body of a `phase: complete` ISA means the work resumed: set `phase: learn`, increment `iteration` (start at 2), add `resumed_at: <ISO-8601>`, and append a Decisions row `refined: reopened after complete — <why>`. `frozen: true` opts out (the edit is a pure correction). It closes again only through `isa close`.
- **Continuation vs new task.** A follow-up that continues the same task edits the existing ISA; a genuinely new task gets a new ISA (`isa new`).
- **Waive or defer, never fudge.** A probe that genuinely can't run yet gets a `- ISC-N: [DEFERRED-VERIFY] — <why> — follow-up: <what>` Verification line; the ISC stays `[ ]`. Only the user can waive an ISC, and the row quotes them: `waived: ISC-N — "<their words>"`; waived ISCs leave the `progress` denominator.
- **Close.** `isa close <ISA>` sets `phase: complete` only when all four hold:
  1. Every non-dropped leaf ISC is ticked (by `isa verify`) or waived by the user. (The engine ticks a nested parent once all its leaves are.)
  2. A `- Goal: yes — <evidence>` line confirms the finished result delivers the verbatim goal's intent — the frame-drift check: all ISCs passing doesn't prove the ISC set still covers what was asked. One `- Ask N:` line answers each ask.
  3. The close gate holds at the ISA's tier (CheckCompleteness with `moment: close`), including the `second-look:` / `class-sweep:` rows the rules call for, and no item is still blocked from an earlier turn.
  4. `isa close` succeeded: it re-runs every mechanical probe, and every one passes without changing the tree. Self-attested ticks and ticks with no red baseline are listed to the user.

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

---

## Gotchas

The highest-information-density part of this skill. Each entry captures a non-obvious failure mode that has bitten real ISA work.

- **ID-stability is the cornerstone of Reconcile — never re-number on edit.** When the Splitting Test produces a finer-grained version of `ISC-7`, preserve `ISC-7` as the parent and add `ISC-7.1`, `ISC-7.2`, etc. Even when an ISC is dropped, leave a tombstone (`- [ ] ISC-N: [DROPPED — see Decisions YYYY-MM-DD]`). Reconcile keys on stable IDs; renumbering breaks ephemeral feature-file merges silently and the failure mode looks like "the worker's checkmarks didn't land in master."
- **Ephemeral files are derived views, never sources of truth.** Scaffold's ephemeral mode (`ephemeral_feature` input) produces a slice of the master ISA under `_ephemeral/<feature>.md`. Workers operate against that slice; Reconcile merges back. Hand-editing master content from an ephemeral file is policy-forbidden — the master is what persists; the ephemeral is what gets archived.
- **The Changelog format is non-negotiable.** Every entry needs all four pieces (`conjectured`, `refuted by`, `learned`, `criterion now`) in that order. Append refuses to write a partial C/R/L; if any of the four is missing, the entry is a Decision, not a Changelog. The format is what makes the Deutsch error-correction trail auditable across sessions.
- **Empty sections never appear.** The fourteen-section body is a *capacity*, not a *requirement* at every tier. Sections not required and not yet written are simply absent from the file — including Decisions, Changelog, and Verification until there is something real to record. CheckCompleteness distinguishes `present` / `missing` / `empty` (never acceptable) / `not-yet` (a record section at articulation). Section length is never graded; a one-sentence section can be exactly right.
- **Anti-criteria are derived from Out of Scope plus regression-prevention concerns.** They are how the prose-guardrails (Out of Scope, Constraints, Principles) become probe-able. At least one is required at every tier; the absence of an anti-criterion at OBSERVE is a hard CheckCompleteness failure.
- **Antecedents are required when the goal is experiential.** For art, design, content, and anything that has to "land," at least one ISC must use the `Antecedent:` prefix to name a precondition that reliably produces the target experience. Verifiable goals (build, deploy, schema) don't need antecedents; experiential goals always do.
- **Reconcile is deterministic — there are no conflicts to resolve.** Either an ISC ID exists in master (mechanical merge) or it doesn't (abort with ID-stability violation). If the ephemeral made structural changes (split ISC-7 into ISC-7.1/ISC-7.2), those structural changes belong in master via a separate Edit by the user *before* Reconcile runs.
- **The literal goal is the evidence anchor, not the optimization target.** `stated_goal` is copied byte-for-byte and never paraphrased; build for the intent it expresses, not its surface (hitting "p95 < 200ms" through a percentile-calc edge case passes the surface and fails the intent).
- **The format spec wins on contradiction.** `References/IsaFormat.md` is the file-shape contract. If this skill's prose ever drifts from the format spec, reconcile them deliberately — don't silently pick one.
- **Features are vertical slices, not horizontal layers.** Each `## Features` entry cuts end-to-end to a verifiable increment satisfying ≥1 ISC — not "the data layer" then "the API layer." A Feature you can't independently verify on its own is a horizontal slice; re-slice it vertically.
- **Prefer test-first probes (red-before-build).** Where an ISC's probe is a *runnable* test (unit/property test, `bash`, `curl`, `SELECT`), write it so it FAILS before EXECUTE and passes after — the probe exists and is red before the build, green after. Probes that can only be a screenshot or manual check are exempt.

---

## Examples

The `Examples/` directory holds reference ISAs spanning the tier (E1–E5) × domain (code / art / design / ops / marketplace / enterprise) matrix. Every example passes the completeness gate for its tier and phase: one Test Strategy entry per leaf ISC, probes out of the criterion text (except at E1, which has no Test Strategy), ticks backed by Verification lines. None is part of a hierarchy, so none shows Dependencies or Bridge Criteria — see `References/IsaHierarchy.md`. Read the canonical showpiece before scaffolding a new ISA — copy its section headers, then populate. Pick the example closest to your domain + scale as a template; read `e3-project.md` to see what a closed ISA looks like.

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

---

## ID Stability Rule

**ISC IDs never re-number on edit.** When the Splitting Test produces a finer-grained version of `ISC-7`, the original number is preserved as the parent and children become `ISC-7.1`, `ISC-7.2`, etc. Do not collapse the numbering even if the ISC is dropped — leave a tombstone marker so historical references in Decisions, Changelog, and Verification remain valid.

This rule exists because `Reconcile` is keyed on ISC IDs. If IDs renumber across edits, ephemeral feature-file reconciliation breaks silently. The renumbering ban is what makes feature-file workflows safe.

---

## Ephemeral Feature Files (parallel-worker pattern)

When a feature is to be worked in an isolated context (a subagent, a worktree, a parallel coding-agent instance), invoke:

```
Skill("ISA", "extract feature <name> as ephemeral file from <master-isa-path>")
```

`Scaffold` (ephemeral mode) produces a derived view containing only the slice relevant to that feature: the Vision and Goal as read-only context, the relevant Constraints, the ISCs in the feature's `satisfies:` list with stable IDs, and the matching Test Strategy entries. (No Verification section yet — it appears with the worker's first entry.)

A fresh-context agent operates against the ephemeral file alone. At completion, `Reconcile` merges its Decisions, Changelog entries and `[DEFERRED-VERIFY]` lines back to master, then runs `isa verify <master>` on the slice's ISCs — the engine ticks what passes there (a worker's checkmarks are never copied over) — and archives the ephemeral file under `_ephemeral/.archive/`.

**Ephemeral files are derived views. They are never sources of truth. They are never hand-edited as policy. The master ISA is what persists.**

---

## The loop this skill serves

The skill owns the artifact, not the work loop. The loop that uses it — articulate done, build, verify each claim on tool evidence, fold what was learned back in — is summarized in `References/IsaLoop.md`. Typical call points:

- Start of work: `isa new <slug> --goal "<span>"`, then `Skill("ISA", "scaffold from prompt at tier T")` fills the body.
- End of articulation: `isa lint <ISA>`; for the judgment parts, `Skill("ISA", "check completeness of <path> at tier T")`.
- While building: `isa verify --red <ISA>` before the change, `isa verify <ISA>` after it; `isa close <ISA>` to finish.
- Planning parallel work: `Skill("ISA", "extract feature <name> as ephemeral file from <master-isa-path>")`.
- After a worker finishes: `Skill("ISA", "reconcile <ephemeral-path> → <master-path>")`.
- Any time: `Skill("ISA", "append decision|changelog|verification to <path>: ...")`.

The skill is invocation-agnostic — it works the same whether called from a loop or directly by the user.

## References

- `References/IsaFormat.md` — the file-shape contract (frontmatter fields, section schemas, ISC grammar, probe-type vocabulary).
- `References/IsaSystem.md` — the conceptual frame (five identities, three guardrails).
- `References/IsaHierarchy.md` — multi-ISA trees, Dependencies, Bridge Criteria. Load only when an ISA has `parent:`/`children:`.
- `References/IsaLoop.md` — the work loop around the ISA: phases, standing questions, resume (the completion rules are in this file, § Completion rules).
