# Future C — Project ISA (possible feature, not planned)

> **Status: removed from the skill on 2026-09-22.** The skill now supports task ISAs only (`~/.claude/isa/{slug}/ISA.md`). This folder keeps what was removed so it can be reconsidered later.

## The idea

A **project ISA** is one `ISA.md` at a repo's root that never closes. It is the living spec of an app: its Constraints, Out of Scope, Anti-criteria, and every claim the app must keep satisfying (a regression suite written as prose). Every task on the repo reads it and extends it. The value: rules like "patient data never leaves the server" are written once, and every future feature is checked against them.

## Why it was dropped for now

In LifeOS, a task on a project edited the project ISA **directly**. That mixes two lifetimes in one file:

- `phase:`, `progress:`, and the closing `Goal:` line describe *one task*, but they sit on a file that describes *the app forever*.
- A file that never closes has no clean `complete`, so the close rules (Goal line, CheckCompleteness before `complete`) had no natural moment to fire.

## Candidate design if it comes back: project = parent, task = child

This reuses the hierarchy mechanism already in the skill (`skill/ISA/References/IsaHierarchy.md`):

- **Project ISA = parent.** Holds Constraints, Out of Scope, Anti-criteria, standing ISCs. No task phase; `progress` counts standing claims.
- **Each task = its own task ISA with `parent: <project>`.** It inherits every project Constraint automatically, and closes normally with its own phase, progress, and Goal line.
- **At close**, claims that must hold forever are *promoted* into the project ISA (a Decisions row on both sides).
- Open questions: where the project ISA lives (`<repo>/ISA.md` vs `<repo>/.isa/`), whether an E3 floor still applies, and how `isa run` (see CLAUDE.md "Later") would re-run the standing claims.

## What was removed from the skill

| Where | What |
|-------|------|
| SKILL.md | "Two homes" table, Project ISA row, project-ISA E3 override paragraph and gotcha, Seed in the routing table, "floor for project ISAs" |
| Workflows | `Seed.md` (moved here as `Seed.md`: drafts a project ISA from README, package.json, commits, tests); Scaffold's `project` input and `<project-root>/ISA.md` output; CheckCompleteness's `max(tier, E3)` override; `.isa/_ephemeral/` slice path in Scaffold and Reconcile |
| References | Project-ISA location and override in IsaFormat; "Two Homes" and project system-of-record wording in IsaSystem; "persistent identity outlives every run" and the Seed row in IsaLoop |

`project:` survives in frontmatter only as an **optional label** on a task ISA ("which codebase this task is about") — useful for Future A memory indexing and a status line. It does not imply a project ISA exists.

`Seed.md` here is the last in-skill version (already stripped of LifeOS voice/paths, with the `context_sufficient`/`interview_invoked` fix). It still references project-ISA concepts by design.
