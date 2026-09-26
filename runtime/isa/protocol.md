[ISA protocol — enforced by harness hooks]
Before changing anything (files, git, installs, remote systems) this session must have an ISA: one
markdown file stating what "done" means as testable criteria. Reading, searching and answering
questions are never gated. The hooks deny mutating tool calls until the ISA exists and passes the
completeness gate, lint every ISA edit, and refuse (once per prompt) to end a turn while the ISA is
stale or a `phase: complete` claim fails the close gate.

- Where: {project_dir}/<YYYYMMDD-HHMMSS>_<kebab-slug>/ISA.md  (`isa new <slug>` prints a fresh path;
  `isa ls` lists this project's ISAs). Writing or editing an ISA.md binds it to this session.
- Continuing earlier work: edit that ISA instead of making a new one. A new task gets a new ISA.
- Shape: {skill_dir}/SKILL.md is the contract (sections, tiers E1–E5, lifecycle). Before writing a
  new ISA, read it and the closest example in {skill_dir}/Examples/ — E1 needs only `## Goal` and
  `## Criteria` (with at least one `Anti:` ISC); bigger work needs more.
- `stated_goal` must be copied byte-for-byte from the user's prompt (the hook checks), or be null.
- As you work: prove each ISC with `isa verify <ISA> ISC-N` (runs its Test Strategy `tool:`; exit 0 =
  pass) and tick it right away with the Verification line it prints; keep `progress` and `phase` true.
  The hooks refuse a tick without a passing run newer than your last project change, and refuse other
  changes while a passed ISC is still unticked. Probes must be exact commands (no placeholders).
- Features tick in dependency order: an ISC whose Feature `depends_on` a Feature with open ISCs is
  refused until that Feature is done (in an earlier edit).
- Before `phase: complete`, run `isa verify <ISA>` (every probe) after your last change.
- Close: `phase: complete` only when every leaf ISC is verified or user-waived and a
  `- Goal: yes — <evidence>` line confirms the result delivers the stated goal.
- Read-only work can need an ISA too (reviews, audits, investigations, comparisons, plans): when a
  prompt gets an `ISA fit: strong` note, structure the work with an ISA even if nothing is changed.
- You cannot exempt yourself. If the user says to skip the ISA, write an E1 ISA that records that.
