[ISA: ON — this prompt is work with several dependent steps]
State the tier first, then follow its lifecycle. Every step has its `isa` command; ISAs, specs, plans and ~/.isa
are written by these commands only (Write, Edit or a script on them is refused). The skill: {skill}/SKILL.md.

- E1 (one level of criteria, no spec): `isa new <slug> --tier E1` → write it → BUILD.
- E2–E4 (2, 3, 4+ levels): `isa spec new <slug> --tier E2|E3|E4` → write it → its open questions → `isa lint` →
  the `Spec ack` question → `isa ack <spec>` → `isa new --spec <spec>` (one parent per section) → write the ISA →
  `isa review <ISA>` (seven-line checklist on stdin; answer each flag) → `isa show <ISA> --trace` for the user →
  the `ISA ack` question → `isa ack <ISA>` → BUILD.
  Where a leaf sits says where it came from: under ISC-k it serves Sk; common ground two sections share goes under
  `ISC-0` (`--before ISC-1`, leaves with `--serves S2+S3 --why`); a section's prerequisites are its first children
  (`--before ISC-k.1`); an Anti outside the sections `--anchors Goal`; anything the spec doesn't state
  `--source context --why "<why>"`.

Before BUILD only a recognised project change waits: Write/Edit of a project file, `rm`, `mv`, `cp`, `npm`…, a
redirect into a project file, `sed -i`, a git write. Any other command runs (a script, a test, a read). The spec's
first ack lists the files changed outside the spec since `isa spec new` and waits until they're reverted. Edit
project files with Edit or Write in BUILD; a script that names an ISA, a spec or ~/.isa is refused in every stage.

The user's words: `--goal`, `--ask` and `isa write <ISA> asks` are pieces copied from the session's prompts or an
AskUserQuestion answer of the user; leave text out with `…`, spacing doesn't count, each part is copied exactly.
Write: `isa write <file> <section>` (text on stdin; a spec's `S<n> — <title>` replaces S<n>; `isa drop <spec> S<n>
"<why>"` removes one), then one criterion at a time, in every tier: `isa write <ISA> ISC-N "<text>" --probe
"<command>" --kind behaviour`; `isa drop <ISA> ISC-N "<why>"`; `isa decide <ISA> "<text>"` for a decision.
At least one `Anti:` criterion: it is `--kind regression` with `--fails-when "<what it would see>"` (so is any kind
but behaviour). A leaf has one probe, a parent none: before giving a leaf children, `isa write <ISA> ISC-N
--no-probe`. Nothing to run: `--kind manual`, ticked with `isa attest <ISA> ISC-N "<evidence>"`.
Review: Jev's flags and the checklist's `redundant:` line ask of each criterion: Necessary? (what would go wrong,
unnoticed, without it) Duplicate? (another criterion or an existing test proves it) Malformed? (vague claim, a probe
that misses it, the wrong kind). Answer `keep: <what would go unnoticed>`, `drop: …` after `isa drop`, `fix: …`
after `isa write`, or `reopen: …` — never where the criterion came from.
Acks: ask with AskUserQuestion, header `Spec ack` or `ISA ack`, options `Acknowledge` / `Request changes`; the click
is the user's — then `isa ack <file>`. Only the harness runs `isa hook`, and `isa open` is for the user's terminal:
both are refused from a tool call (`isa open --print` gives the path). An acked spec changes only after
`isa reopen <spec>`; show the user `isa diff <file>` before asking again; then `isa refine <ISA>`. Any criterion
change after the ISA's ack needs a new ack.
BUILD: `isa verify --red <ISA>` (the behaviour probes must fail first; one that passes is flagged ⚠), the work,
`isa verify <ISA>` (runs the probes not green yet; `isa verify <ISA> ISC-N` re-runs one; a failure shows its last
40 lines), `isa answer <ISA> goal "yes — <evidence>"` (and `ask N`), then `isa close <ISA>` — it re-proves
everything once, writes the plan (E2+) and commits. Quote its summary in your answer.
Run `isa verify` and `isa close` with a 600000 ms timeout.
