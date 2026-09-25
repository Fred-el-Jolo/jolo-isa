---
version: 1.0.0-export.1
---

# ISA Hierarchy & Cross-ISA Integration

> On-demand reference. Single-ISA work is the leaf case and covers virtually all real tasks — in the archive this skill was extracted from, 0 of 472 ISAs used `parent:`/`children:`/Bridge Criteria. This machinery exists for genuinely large builds (a Tolkien-scale world, an enterprise product). Load it only when an ISA declares `parent:` or `children:`.

Anything too big for one file is a **tree of ISAs**, not one monolith with 35,000 criteria.

**Linking.** An ISA declares its place in the tree via frontmatter `parent: <slug>` and `children: [<slug>, …]`. The parent holds product intent (a small Goal + a few container ISCs); each child owns one subsystem's closure. Children may have children. Divergent branches (Team A's vision vs Team B's) are tracked the same way — divergence is explicit and auditable, never silent drift.

**Constraint inheritance (HARD).** A child ISA's `## Constraints` implicitly include every ancestor Constraint. A child ISC may not violate an inherited Constraint; if it must, that's a parent-level renegotiation logged in the parent's `## Decisions`, not a quiet child override.

**Dependencies (`## Dependencies`).** Each ISA states what it needs from siblings/ancestors as machine-readable lines — `requires: auth-isa — valid session-token contract`. Before scaffolding criteria for an ISA with `## Dependencies`, load those ISAs into context so the work is written against the real contracts, not guesses. (In practice most `## Dependencies` entries name files, tools, or CLIs rather than sibling ISAs — that's fine; it is the prerequisites list.)

**Bridge criteria (`## Bridge Criteria`).** A leaf ISC verifies a subsystem in isolation. A **bridge ISC** verifies the *seam* between two ISAs and lives in the parent (or the more central of the two): `- [ ] ISC-N: Bridge: Psionic willpower cost never exceeds the Magic resource budget`, with `anchors_to: cross: magic-isa` in Test Strategy. Bridge criteria run as a distinct VERIFY pass after leaf criteria.

**Blast radius (detection, not auto-resolution).** When a linked ISA changes, walk the dependency graph and list every downstream ISC that now needs re-verification (`changing willpower cost touches magic-isa: 7 ISCs, race-isa: 3`). Show it before building so the change is a decision, not a surprise. Which team's conflicting criterion wins is a human call.

**When to split into a tree (judgment, not a count).** One ISA until a single file stops being legible — usually when Vision/Goal names subsystems that each carry their own Vision, Constraints, and independent test surface. A website is one ISA; an RPG world is a master ISA plus subsystem ISAs. Don't pre-split a medium app that fits in one file.
