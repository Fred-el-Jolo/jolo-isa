# Foundations

Three foundations, and nothing else:

- **FOUNDATION_0 — the entities.** Each is defined once, below.
- **FOUNDATION_1 — the decision tree.** No ISA → nothing. ISA → pick the tier: E1 → IMPL; E2–E4 → SPEC → IMPL. Nothing bypasses it.
- **FOUNDATION_2 — `isa` commands are the only writers.** An ISA, a spec, a plan and anything under `~/.isa` are created, changed and closed by `isa` commands only. A Write, an Edit, a redirect or a script on them is refused. Reading is free.

## FOUNDATION_0 — the entities

### TASK
A unit of work the user asks for: several dependent steps, where a mistake in one step could carry into the final result unnoticed unless each step is checked. A quick exchange, or a 1–3 step action whose failure is immediate and obvious, is not a task (tier E0: nothing is enforced). One task, one TASK ISA.

### TASK ISA
The task's work notebook: `~/.isa/<project>/<YYYYMMDD-HHMMSS>_<slug>/ISA.md`, local, never committed. It states what done means as criteria, proves each one with a probe, and records the decisions. Its sections, in this order:

- **Problem, Vision, Out of Scope, Principles, Constraints, Goal:** what and why.
- **Criteria:** the tree of ISCs.
- **Test Strategy:** one probe per leaf.
- **Decisions:** one row per decision, dead ends included.
- **Review** (E2+): the review before the ISA ack, written by `isa review` only.
- **Verification:** written by the commands only.

E1 has no Vision, Out of Scope or Constraints. From E2 every section up to Test Strategy is required. `<project>` is the git root (else the directory) relative to `$HOME`, with `/` → `-`.

### Tier
How heavy the task is. It decides the documents and how deep the criteria tree may go:

| Tier | Documents | Criteria depth |
|---|---|---|
| E0 | none | — |
| E1 | TASK ISA | 1 level |
| E2 | SPEC, then TASK ISA | up to 2 levels |
| E3 | SPEC, then TASK ISA | up to 3 levels |
| E4 | SPEC, then TASK ISA | 4 levels or more |

Pick it from the work, not from the prompt's length; between two tiers, take the heavier one. The user's call wins.

### ISC
One yes/no claim, an Ideal State Criterion, in a tree:

```
- [1/2] ISC-3: My feature
  - [x] ISC-3.1: My feature's backend answers the new query
  - [ ] ISC-3.2: My feature's front end shows the answer
- [ ] ISC-4: Anti: the old endpoint stops answering
```

A leaf has a box `[ ]` / `[x]` and one probe. A parent has no probe: its box shows its children, `[done/total]`, and turns `[x]` when all of them are done. The id follows the nesting, two spaces per level. `Anti:` marks something that must not happen, and every ISA has at least one. A dropped ISC stays as a tombstone, `[DROPPED — <why>]`, and its id is never reused. Children run in order (`parallel: true` on a child is reserved for later and refused for now).

### Probe
The command that proves one leaf: its `## Test Strategy` entry, a YAML list item.

```yaml
- isc: ISC-3.1
  anchors_to: S2                    # E2+: the section its parent ISC-2 stands for, or Goal / Constraints
  kind: behaviour                   # behaviour | regression | doc | config | file | manual
  tool: python3 -m unittest tests.test_api.Query
  fails-when: "…"                  # what it would see if the claim were false — required unless kind is behaviour
```

From E2, where a leaf sits says where it came from:

- **under `ISC-k`:** it comes from spec section `Sk` (`anchors_to: Sk`, set when the leaf is added);
- **under `ISC-0`, Common ground:** a state two or more sections rely on, built first (`serves: S2+S3`, `why:`);
- **elsewhere:** an Anti anchored to the Goal or the Constraints, or anything else marked `source: context` with its `why:`.

Any leaf the spec doesn't state carries `source: context` and its `why`. It passes exactly when it exits 0, run from the project root. A behaviour probe is run red first (`isa verify --red`): it must fail before the build. A passing run with no failed red run of the same command is marked `(no red baseline)`. A `manual` leaf is attested with evidence instead.

### SPEC
What is wanted, in the user's words: `<cwd>/docs/YYYY-MM-DD-<slug>-01-spec.md`, from E2, committed. It holds:

- Problem;
- Goal, with a `Said:` list and an `Assumed:` list;
- Out of scope and Constraints;
- Approaches (from E3);
- one `## S<n> — <part>` section per deliverable part, each with its `Accepted when:` lines.

Its status is `draft` or `acked YYYY-MM-DD #<hash8>`, with no done marks. It is the TASK ISA's source: the ISA links it (`spec:`), and each probe anchors to one of its sections. When an acked spec changes (`isa reopen`), the ISA must be refined (`isa refine`) and acked again before the work goes on. Writing rules: `SpecDriven.md`.

### PLAN
What remains of a task: `<cwd>/docs/YYYY-MM-DD-<slug>-02-plan.md`, written by `isa close` from E2, committed. It copies the closed ISA's sections from Problem through Test Strategy, its Decisions, its Review, and its Verification minus the run lines. A spec whose plan exists is finished. The TASK ISA can be deleted afterwards; the plan stays.

### Ack
The user's click on **Acknowledge**, never the model's. It is asked with AskUserQuestion: header `Spec ack` or `ISA ack`, options `Acknowledge` / `Request changes`. Each click is recorded in `~/.isa/<project>/acks.jsonl` with the file's hash. `isa ack <file>` then writes it into the file, and refuses without that click. A spec is acked from E2, and its TASK ISA is acked from E2 as well. The ISA ack waits for a review of the criteria as they are (`isa review`), with every Jev flag answered, and the user reads `isa show <ISA> --trace` before it. Any later change breaks the ack. Before asking again, `isa diff <file>` shows the user what changed.

### Session
One Claude Code or pi session: OFF or ON, at most one bound ISA or spec, and its last prompts (`~/.isa/_state/sessions/`). `isa new` and `isa spec new` bind what they create.

### Gate
Each prompt is judged once, by Jev, else by the running model (`ISA judge (model): yes|no|unsure — <reason>`), on one question: is this a TASK? A yes turns the session ON. A clear no lets the prompt go on. Anything else goes to the user, *Continue without ISA* or *Enable ISA*, and that question can't be skipped. With an ISA or spec open, the gate asks instead whether the prompt continues it or starts a new task.

### Lifecycle
What the session is doing; it decides which changes go through:

    E1      TRIAGE → ISA DRAFT → BUILD → CLOSED
    E2–E4   TRIAGE → SPEC DRAFT → SPEC ACKED → ISA DRAFT → BUILD (the ISA acked) → CLOSED

Project changes go through in BUILD only. Every refusal names the stage and the next command. A reopened spec sends the task back to SPEC DRAFT; after its new ack, `isa refine` and a new ISA ack lead back to BUILD.

## FOUNDATION_2 — one command per action

| Action | Command |
|---|---|
| start a spec (E2+) | `isa spec new <slug> --tier E2` (or E3, E4) |
| start the ISA | `isa new <slug> --tier E1`, or `isa new --spec <spec>` (seeded from it, one parent per section; an open ISA of that spec is bound again) |
| write a section | `isa write <file> <section>`, the text on stdin (E1: Criteria and Test Strategy once, as a block) |
| change, add or drop one ISC | `isa write <ISA> ISC-N "<text>"`, `isa write <ISA> ISC-N --probe "<command>" [--kind K] [--fails-when F] [--anchors S2\|Goal\|Constraints]`, `isa drop <ISA> ISC-N "<why>"` |
| place it, say where it came from | `--before ISC-M` (a new criterion before its sibling), `--serves S2+S3 --why "…"` (under ISC-0), `--source context --why "…"` |
| review the ISA before its ack (E2+) | `isa review <ISA>` (the six-line checklist on stdin, then Jev's check), `isa review <ISA> --answer R<n> "<answer>"` |
| the task line, the asks | `isa write <ISA> task "<text>"`, `isa write <ISA> asks` (one verbatim ask per line) |
| add a decision | `isa decide <ISA> "<text>"` |
| read | `isa show <file> [--to Criteria \| --trace]`, `isa lint <file>`, `isa ls`, `isa status`, `isa current`, `isa where` |
| record an ack (after the click) | `isa ack <file>` |
| change an acked spec | `isa reopen <spec>`, then `isa diff <spec>` for the user, then the ack; then `isa refine <ISA>` |
| prove | `isa verify <ISA> [--red] [ISC-N…]`, `isa attest <ISA> ISC-N "<evidence>"` |
| answer the goal and the asks | `isa answer <ISA> goal "yes — <evidence>"`, `isa answer <ISA> ask N "met — <evidence>"` |
| close | `isa close <ISA>`: re-runs every probe, writes the plan (E2+), commits the work, then the plan |
| debug | `isa log` (with DEBUG on), `isa purge-logs` |

**Commits.** In a git repo:

- `isa ack <spec>` commits the spec, alone;
- a passing `isa close` commits the files the task changed (never one the user had changed before `isa new`), then the plan.

Outside git nothing is committed.

**State.** `~/.isa` holds the ISA folders, `<project>/acks.jsonl`, `config.json` and one file per session. With DEBUG on (`ISA_DEBUG=1`, or `"debug": true` in `~/.isa/config.json`), a debug log goes to `~/.isa/_state/logs/` too. With DEBUG off nothing else is written.
