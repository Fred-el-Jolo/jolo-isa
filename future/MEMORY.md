# Future A — ISA ↔ Memory

> **Status: not built.** This file records how the source system (LifeOS) learns from ISAs today, and the target design for this export. Nothing here is implemented in `skill/`.

## What LifeOS does today when an ISA completes

Three separate mechanisms, none owned by the ISA skill:

| Mechanism | Trigger | What it produces | Quality |
|-----------|---------|------------------|---------|
| `WorkCompletionLearning.hook.ts` | SessionEnd | `MEMORY/LEARNING/{ALGORITHM\|SYSTEM}/YYYY-MM/<date>_<time>_work_<slug>.md` containing the ISA title, duration, the raw `## Criteria` block, counts of files changed / tools / agents, and three **unfilled** reflection prompts ("Was the approach straightforward…?"). Only fires if files changed or work was manual. | Mechanical dump. No insight is extracted; nothing reads these files back automatically. |
| Algorithm rule 12 "Learning Router" | Model, at `learn` | Each learning is routed as a diff: default **SKIP**; `knowledge`→Knowledge archive, `rule`→CLAUDE.md / operational rules, `gotcha`→the owning skill's Gotchas, `state`→projects file, `identity`/`doctrine`/`hook`/`permission`→surfaced to the user. | Good idea, pure self-discipline, no index. |
| Reflection record | Model, at `learn` | One JSONL line in `MEMORY/LEARNING/REFLECTIONS/algorithm-reflections.jsonl` (operational fields: effort, duration, criteria counts, within_budget). | Telemetry about the loop, not reusable knowledge. |

The ISA itself already holds the richest learnable material: `## Decisions` (especially `❌ DEAD END` rows), `## Changelog` C/R/L entries, and `refined:` rows. LifeOS never harvests those structurally.

Also relevant: `SessionCleanup.hook.ts` force-sets `phase: complete` at SessionEnd, and `PreCompact`/`RestoreContext` re-inject the ISA head into context around compaction. See `CLAUDE.md` § Hooks for the full list.

## Target design (to refine)

**Capture — at `phase: complete`:**
- Extract candidate learnings from the ISA, not from a transcript: every `❌ DEAD END`, every Changelog C/R/L entry, every `refined:` Decision, the final Constraints and Anti-criteria.
- Show them to the user as a short list; the user keeps, edits, or drops each one. **No silent writes** — direct user input is the gate.
- Store kept items as small typed entries (`gotcha` / `constraint` / `dead-end` / `pattern` / `preference`) with: source ISA slug, project, tags, date.

**Index:**
- One index file (or small SQLite) mapping tags / project / keywords → entries. Deterministic, greppable, no embeddings required for v1.

**Reuse — at Scaffold time:**
- Before Step 3b (derive the residue), query the index by project + keywords from the prompt.
- Surface at most ~5 matches to the user: "these past learnings look relevant — include?" Accepted ones seed `## Constraints`, `## Out of Scope`, `Anti:` ISCs, or a Decisions row citing the source slug.

**Design input kept from LifeOS — the `[arch]` tag.** LifeOS let a Decision be tagged `- 2026-06-14 12:00: [arch] JSONL for streaming state — …` when it set a structure, contract, or convention that *other* tasks must follow (not a local call like "which library for this feature"). A tool harvested `[arch]` rows from completed ISAs into a system-wide log. That's exactly a capture signal for this memory: tag at write time, harvest at `complete`. Dropped from the spec until this exists.

**Open questions:**
- Where does the store live — `~/.claude/isa/_memory/` or per codebase (keyed by the task ISA's optional `project:` label)?
- If project ISAs come back (`future/project-isa/`), do they carry their own learnings, or always the global store?
- Expiry / freshness: when does a learning go stale?
- Should the Append workflow tag entries as "memory-worthy" at write time, to make capture cheaper?
