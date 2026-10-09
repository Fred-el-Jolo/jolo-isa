[ISA: ON — this prompt is work with several dependent steps]
State the tier first, then follow its lifecycle. Every step has its `isa` command; ISAs, specs, plans and ~/.isa
are written by these commands only (Write, Edit or a script on them is refused). The skill: {skill}/SKILL.md.

- E1 (one level of criteria, no spec): `isa new <slug> --tier E1` → write it → BUILD.
- E2–E4 (2, 3, 4+ levels): `isa spec new <slug> --tier E2|E3|E4` → write it → its open questions → `isa lint` →
  the `Spec ack` question → `isa ack <spec>` → `isa new --spec <spec>` (one parent per section) → write the ISA →
  `isa review <ISA>` (six-line checklist on stdin; answer each flag) → `isa show <ISA> --trace` for the user →
  the `ISA ack` question → `isa ack <ISA>` → BUILD.
  Where a leaf sits says where it came from: under ISC-k it serves Sk; common ground two sections share goes under
  `ISC-0` (`--before ISC-1`, leaves with `--serves S2+S3 --why`); a section's prerequisites are its first children
  (`--before ISC-k.1`); an Anti outside the sections `--anchors Goal`; anything the spec doesn't state
  `--source context --why "<why>"`.

Write: `isa write <file> <section>` (text on stdin; on E1, Criteria and Test Strategy once, as a block), then one
criterion at a time: `isa write <ISA> ISC-N "<text>"`, `isa write <ISA> ISC-N --probe "<command>" --kind behaviour`,
`isa drop <ISA> ISC-N "<why>"`; `isa decide <ISA> "<text>"` for a decision. At least one `Anti:` criterion; a leaf
has one probe, a parent none; a probe that can't be seen failing first gets `--fails-when "<what it would see>"`.
Acks: ask with AskUserQuestion, header `Spec ack` or `ISA ack`, options `Acknowledge` / `Request changes`; the click
is the user's — then `isa ack <file>`. An acked spec changes only after `isa reopen <spec>`; show the user
`isa diff <file>` before asking again; then `isa refine <ISA>`. Any criterion change after the ISA's ack needs a new ack.
BUILD: `isa verify --red <ISA>` (behaviour probes must fail first), the work, `isa verify <ISA>`, `isa attest <ISA>
ISC-N "<evidence>"` for a manual leaf, `isa answer <ISA> goal "yes — <evidence>"` (and `ask N`), then
`isa close <ISA>` — it re-proves everything, writes the plan (E2+) and commits. Quote its summary in your answer.
Run `isa verify` and `isa close` with a 600000 ms timeout.
