---
version: 1.0.20-export.1
---

# ISA System

The ISA — Ideal State Artifact — is the universal primitive that holds the articulated ideal state of any thing whose ideal state we are pursuing. Project, application, library, infrastructure, work session, art piece, strategic decision: one document that articulates done, drives the build, verifies the build, and records how understanding evolved.

Companion documents:

- **Format spec** — `IsaFormat.md` — the file-shape contract. Wins on any contradiction.
- **Skill** — `../SKILL.md` — the five workflows (Scaffold, Interview, CheckCompleteness, Reconcile, Append).
- **Loop** — `IsaLoop.md` — the work loop that uses the ISA and when each workflow fires.

## Five Identities

1. **Ideal state articulation** — the written hard-to-vary explanation of done, in the Deutsch sense. Removing or weakening any part changes what done means.
2. **Test harness** — the ISCs *are* the tests. Every ISC names a single binary tool probe; the collection of probes is the full test surface.
3. **Build verification** — passing the ISCs verifies what was built. No separate acceptance suite.
4. **Done condition** — the task is complete when every ISC passes. `progress: N/N` and `phase: complete` are mechanical consequences of the ISC truth state.
5. **System of record** — the single authoritative description of the work's ideal state, decisions, and evidence, across sessions and agents.

The identities exist because pursuit is iterative: at OBSERVE the ISA is articulation; at PLAN it is the work breakdown; at BUILD it is the contract being met; at VERIFY it is the test harness; at LEARN it is the system of record being refined.

**The literal is the evidence anchor, not the optimization target.** When the user states the goal explicitly, it is captured verbatim into `stated_goal:` and every downstream check verifies against it. But the build optimizes for the *intent* the literal expresses, not its surface: hitting `p95=199ms` by exploiting a percentile-calc edge case that misses 12% of requests passes the surface and fails the intent. An independent second look (a fresh-context reviewer) is the probe that surfaces this drift.

## Three-Guardrail Taxonomy

| Guardrail | Binds | Tone | Lives In | Example |
|-----------|-------|------|----------|---------|
| **Principles** | The *thinking* | Aspirational, generalizable, substrate-independent | `## Principles` | "User-facing systems prioritize responsiveness." |
| **Constraints** | The *solution space* | Immovable, non-negotiable | `## Constraints` | "We do not roll our own cryptography." |
| **Out of Scope** | The *vision* | Declared, explicit, prose anti-vision | `## Out of Scope` | "Mobile native apps are not part of v1." |
| **Anti-criteria** | The *test surface* | Granular, testable, yes/no | `## Criteria` (`Anti:` prefix) | "Anti: `/admin` returns 200 in v1 build." |

The first three are author-stated. **Anti-criteria are derived** — they are how Out of Scope, Constraints, and Principles become probe-able. Out of Scope says "no user accounts in v1"; the anti-criterion says "Anti: `/api/login` returns 404 in v1 build."

**Derived-from-literal anchoring.** When `stated_goal:` is set, every ISC traces to either the literal or a named derived sub-claim, via the `anchors_to` key of its `## Test Strategy` entry (`literal`, `derived: <sub-claim>`, or `cross: <slug>` for bridge ISCs). E1 ISAs have no Test Strategy, so anchoring applies from E2 up. Anti-criteria, antecedents, and infrastructure ISCs all qualify as derived sub-claims — permissive about *what* derives, strict about *naming* the derivation.

## Where ISAs live

One ISA per piece of work, at `~/.claude/isa/{slug}/ISA.md`: created at the start, closed at `phase: complete`. A long-lived per-repo "project ISA" is a possible future feature, not supported now.

## Ephemeral Feature Files

When a feature is worked in an isolated context (a subagent, a worktree, a parallel coding-agent instance), Scaffold's ephemeral mode produces a derived slice: Vision and Goal as read-only context, the relevant Constraints, the feature's ISCs with stable IDs, and their Test Strategy entries (no Verification section until the worker's first entry). The worker operates on the slice alone; Reconcile merges checkmarks, Verification, Decisions, and Changelog back into master and archives the slice.

**Ephemeral files are derived views.** Never sources of truth, never hand-edited as policy. ID stability is what makes this safe.

## ID Stability Rule

ISC IDs never re-number on edit. Splits become `ISC-7.1`, `ISC-7.2` under a preserved `ISC-7`; drops leave a tombstone (`- [ ] ISC-N: [DROPPED — see Decisions YYYY-MM-DD]`) so references in Decisions, Changelog, and Verification stay valid. Renumbering would make Reconcile fail silently — "the worker did the work but the merge didn't take."

## What reads the ISA

Only the model writes the ISA. Everything else reads it:

- **The work loop** (`IsaLoop.md`) — scaffolds at the start, checks completeness before closing, reconciles and appends along the way.
- **A status line** (planned, not built) — reads `task`, `phase`, `progress`, `effort` from the frontmatter.
- **A memory system** (planned, not built) — harvests learnings from completed ISAs and feeds relevant past ones into new scaffolds.
