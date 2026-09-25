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
- As you work: tick an ISC only with tool evidence, add its `## Verification` line, keep
  `progress` and `phase` true. After changing project files, update the ISA before ending the turn.
- Close: `phase: complete` only when every leaf ISC is verified or user-waived and a
  `- Goal: yes — <evidence>` line confirms the result delivers the stated goal.
- You cannot exempt yourself. If the user says to skip the ISA, write an E1 ISA that records that.
