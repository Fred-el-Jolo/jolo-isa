---
name: ISA
version: 1.0.13-export.1
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

Every ISA is a **task ISA**: `~/.isa/<project>/{slug}/ISA.md`, with `slug = YYYYMMDD-HHMMSS_kebab-description`. It is created at the start of a piece of work and closed at `phase: complete`. Ephemeral feature slices live beside it at `~/.isa/<project>/{slug}/_ephemeral/<feature>.md`. `<project>` is the project key — the git work-tree root (or the directory) as a path relative to `$HOME` with `/` → `-` (`~/dev/app` → `dev-app`); `isa where` prints it, `isa ls` lists that project's ISAs, `isa new <slug>` prints a fresh path.

When the ISA hooks are installed (see the repo's `install.py`), the harness enforces this loop in every session: mutating tool calls are refused until an ISA is bound and passes the articulation gate, every ISA edit is linted, and a turn can't end (once per prompt) while the ISA is stale or a `complete` claim fails the close gate. Writing or editing an `ISA.md` under `~/.isa/` is what binds it to the session.

(A long-lived per-repo "project ISA" is not supported — it is a possible future feature, not part of this skill.)

---

## Frontmatter

```yaml
---
task: "8 word task description"          # imperative, ≤60 chars, the deliverable
slug: YYYYMMDD-HHMMSS_kebab-description
project: <name>                          # optional label: which codebase this task is about
effort: E3                               # E1..E5 — drives the completeness gate
phase: observe                           # observe|think|plan|build|execute|verify|learn|complete
progress: 0/12                           # checked / total leaf ISCs, dropped & waived excluded — always true
started: <ISO-8601>                      # set once
updated: <ISO-8601>                      # every edit
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

`phase` and `progress` are the machine-readable status surface — anything that displays ISA state (a status line, a dashboard) reads them. Keep them true: set `phase` at the start, whenever it genuinely changes, and to `complete` at close; recompute `progress` the moment an ISC flips.

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
| 10 | `## Test Strategy` | Per-ISC verification — one YAML entry per leaf ISC (`isc`, `anchors_to`, `type`, `check`, `threshold`, `tool`); shape in `References/IsaFormat.md` | OBSERVE/PLAN |
| 11 | `## Features` | Work breakdown — one YAML entry per vertical slice (`name`, `description`, `satisfies`, `depends_on`, `parallelizable`); shape in `References/IsaFormat.md` | PLAN |
| 12 | `## Decisions` | Timestamped decision log including dead ends; `refined:` prefix for Goal/ISC restructures | any phase |
| 13 | `## Changelog` | Conjecture / refuted-by / learned / criterion-now entries — Deutsch error-correction trail | LEARN |
| 14 | `## Verification` | Evidence that each ISC passed — quoted command output, file content, screenshot path | VERIFY |

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
- **Check ISCs immediately.** Run a mechanical ISC's probe through `isa verify <ISA> ISC-N`; the moment it passes, flip `[ ]`→`[x]`, paste the Verification line it prints, and recompute `progress`. Don't batch at VERIFY. The hooks enforce this: a tick without a fresh passing `isa verify` run is refused, and so is any other project change while a passed ISC waits to be ticked (IsaFormat § Test Strategy). Features tick in dependency order: an ISC whose Feature `depends_on` an unfinished Feature can't be ticked yet (IsaFormat § Features).
- **No ISC closes without tool evidence of the right modality:** file→Read, code→Grep, command→its checked output, HTTP→`curl -i`, appearance→an image actually viewed, schema→a query, config→read-back. "Should work" never closes an ISC.
- **Reopen after complete.** Editing the body of a `phase: complete` ISA means the work resumed: set `phase: learn`, increment `iteration` (start at 2), add `resumed_at: <ISO-8601>`, and append a Decisions row `refined: reopened after complete — <why>`. `frozen: true` opts out (the edit is a pure correction).
- **Continuation vs new task.** A follow-up that continues the same task edits the existing ISA; a genuinely new task gets a new slug.
- **Waive or defer, never fudge.** A probe that genuinely can't run yet gets a `- ISC-N: [DEFERRED-VERIFY] — <why> — follow-up: <what>` Verification line; the ISC stays `[ ]`. Only the user can waive an ISC (`waived: ISC-N — <reason>` in Decisions); waived ISCs leave the `progress` denominator.
- **Close.** `phase: complete` only when all three hold:
  1. Every non-dropped leaf ISC is `[x]` with a Verification entry, or waived by the user. (A nested parent is ticked once all its leaves are.)
  2. A `- Goal: yes — <evidence>` line confirms the finished result delivers the verbatim goal's intent. This is the frame-drift check: all ISCs passing doesn't prove the ISC set still covers what was asked.
  3. CheckCompleteness passes at the ISA's tier with `moment: close`.
  4. Every mechanical tick is re-proven after the last project change: run `isa verify <ISA>` (all probes) last, then close. Self-attested ticks (`manual`, `screenshot`, `eval`, no probe) are listed to the user.

---

## Workflow Routing

Match the verb in the request to a workflow. When ambiguous, default to Scaffold for new ISAs and CheckCompleteness for audits.

| Verb / Intent | Workflow | File |
|---------------|----------|------|
| "scaffold", "create", "generate", "new ISA from this prompt", "extract feature as ephemeral" | **Scaffold** | `Workflows/Scaffold.md` |
| "interview me", "fill in the ISA", "deepen", "ask me questions" | **Interview** | `Workflows/Interview.md` |
| "check", "audit", "score this ISA", "is it complete?" | **CheckCompleteness** | `Workflows/CheckCompleteness.md` |
| "reconcile", "merge feature file back", "ephemeral → master" | **Reconcile** | `Workflows/Reconcile.md` |
| "append decision", "append changelog", "append verification", "record C/R/L entry" | **Append** | `Workflows/Append.md` |

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

A fresh-context agent operates against the ephemeral file alone. At completion, `Reconcile` deterministically merges ISC checkmarks, Verification evidence, Decisions entries, and any new Changelog entries back to master, then archives the ephemeral file under `_ephemeral/.archive/`.

**Ephemeral files are derived views. They are never sources of truth. They are never hand-edited as policy. The master ISA is what persists.**

---

## The loop this skill serves

The skill owns the artifact, not the work loop. The loop that uses it — articulate done, build, verify each claim on tool evidence, fold what was learned back in — is summarized in `References/IsaLoop.md`. Typical call points:

- Start of work: `Skill("ISA", "scaffold from prompt at tier T")` → returns the ISA path.
- End of articulation and before closing: `Skill("ISA", "check completeness of <path> at tier T")` → pass/fail + gap report.
- Planning parallel work: `Skill("ISA", "extract feature <name> as ephemeral file from <master-isa-path>")`.
- After a worker finishes: `Skill("ISA", "reconcile <ephemeral-path> → <master-path>")`.
- Any time: `Skill("ISA", "append decision|changelog|verification to <path>: ...")`.

The skill is invocation-agnostic — it works the same whether called from a loop or directly by the user.

## References

- `References/IsaFormat.md` — the file-shape contract (frontmatter fields, section schemas, ISC grammar, probe-type vocabulary).
- `References/IsaSystem.md` — the conceptual frame (five identities, three guardrails).
- `References/IsaHierarchy.md` — multi-ISA trees, Dependencies, Bridge Criteria. Load only when an ISA has `parent:`/`children:`.
- `References/IsaLoop.md` — the work loop around the ISA and what "a run is complete" means.
