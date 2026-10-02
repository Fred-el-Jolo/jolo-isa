---
version: 2.14.0-export.1
---

# ISA Format Specification

> **The ISA — Ideal State Artifact — is one markdown file with five identities: ideal state articulation, test harness, build verification, done condition, and system of record.** Its ISCs (Ideal State Criteria) are the testable claims that decompose it. The artifact is universal: same primitive whether the unit is software, science, art, a decision, an application, a CLI tool, a library, infrastructure — anything whose ideal state we're articulating.

This file is the file-shape contract. `IsaSystem.md` is the conceptual frame; `SKILL.md` holds the workflows. On contradiction, this file wins.

**Who writes what.** The model writes the content with Write/Edit (or the ISA skill workflows): every section, every criterion's text, the Test Strategy, Decisions, Changelog, and the `- Goal:`, `- Ask N:` and `[DEFERRED-VERIFY]` lines. The engine — the `isa` commands — writes the *state*: checkbox ticks, the generated Verification lines (`verified` / `attested` / `regressed`), `progress`, `phase: complete`, and `root`. The hooks refuse a model edit that would touch an engine-owned part and name the command to use; a shell command writing onto an ISA.md is refused too (edit it with Write/Edit). Anything else — a status line, a dashboard, a hook — only reads it.

## What an ISA Is

1. **Ideal state articulation** — the written hard-to-vary explanation of "done" (Deutsch sense)
2. **Test harness** — ISCs ARE the tests, with named probes; for complex projects the ISCs cover application logic, performance, security, RBAC, build, deploy
3. **Build verification** — passing the ISCs verifies what was built
4. **Done condition** — task complete when all ISCs pass
5. **System of record** — for the thing being articulated

**Don't invent parallel artifacts.** No `acceptance.yaml`, no `acceptance.ts`, no separate test specs. The ISA covers this surface. For complex apps the ISA naturally has many more ISCs — API behavior, performance budgets, security model, RBAC, auth flow, data integrity invariants. They aren't "in addition to" the ISA — they ARE the ISA.

Each ISC is a testable claim — one part of the explanation that can be tried against reality and either pass or fail. Hard-to-variability and testability are the same property: an ISC is hard-to-vary **if and only if** you can name a test that would falsify it. The whole ISA is hard-to-vary when removing or weakening any part changes what "done" means.

**The ISA is a living explanation.** It tightens through pursuit. The Goal sharpens, ISCs split or merge, decompositions clarify — driven by user feedback, tool output, research, and ISCs failing verification. Hard-to-variability is the **outcome** of the process, not its precondition.

**Worked example.** Same goal, two ISC framings:

```
Goal: ship the onboarding email with paid-tier confirmation.

Fluff:        - [ ] ISC-N: Email is delivered to the user.
              (Trivially passable — almost any send path satisfies it. You can't
              name a test that would distinguish "delivered" from "delivered to spam.")

Load-bearing: - [ ] ISC-N: Email arrives in primary inbox (not Promotions/Spam) within 60s.
              (Names a specific test that would fail; removing it lets a "delivered
              to spam" outcome pass.)
```

## Filename and Location

- **ISA:** `~/.isa/<project>/{slug}/ISA.md` — one per piece of work (a long-lived per-repo project ISA is not supported; possible future feature). Created at the start of the work with `isa new <slug> --goal "<verbatim span>"` (it writes the frontmatter and binds the ISA to the session), closed by `isa close <ISA>` (`phase: complete`).
- **Ephemeral feature slices:** `~/.isa/<project>/{slug}/_ephemeral/<feature>.md`. Archived to `_ephemeral/.archive/<feature>-<YYYY-MM-DD>.md` after Reconcile.

## Frontmatter (YAML)

Core fields:

```yaml
---
task: "8 word task description"           # What this work is
slug: YYYYMMDD-HHMMSS_kebab-task          # Unique ID, directory name
project: <name>                           # Optional label: which codebase this task is about
effort: E3                                # E1|E2|E3|E4|E5 — completeness-gate tier
phase: observe                            # observe|think|plan|build|execute|verify|learn|complete (complete: `isa close` only)
progress: 0/8                             # checked / counted leaf criteria — engine-owned, recomputed by every `isa` command
started: 2026-02-24T02:00:00Z             # Creation timestamp (ISO 8601)
updated: 2026-02-24T02:00:00Z             # Last modification timestamp (ISO 8601)
root: /home/me/dev/app                    # engine-owned: the project every probe runs in (written by `isa new`)
asks: ["list each one with its line number", "don't change any files"]   # the prompt's explicit asks
---
```

`asks` holds every explicit ask of the user's prompt as a verbatim span. You write it — `isa new` leaves `[]` and calls no model. Lint checks each entry is a byte-for-byte span of a prompt of the ISA's sessions (an error under v2). The first `isa verify` snapshots the list; removing an ask after that needs a `refined:` Decisions row. At close, each needs a `- Ask N:` line in Verification (see § Verification).

Optional — continuation:

```yaml
iteration: 2                              # Set to 2 on first reopen, incremented after
resumed_at: 2026-03-01T10:00:00Z          # When the last reopen happened
frozen: true                              # A completed ISA that must not reopen on edit
```

Optional — hierarchy (see `IsaHierarchy.md`):

```yaml
parent: 20260706-tolkien-world            # slug of the parent ISA
children:                                 # slugs of child ISAs this one rolls up
  - 20260706-combat-system
```

A child **inherits every ancestor `## Constraints`**; overriding one is a parent-level renegotiation logged in the parent's `## Decisions`. Both fields are omitted for a standalone ISA (the common case).

Optional — stated goal:

```yaml
stated_goal: "verbatim user quote, byte-for-byte"   # NEVER paraphrased
stated_goal_source: prompt                          # prompt | conversation | explicit-revision
stated_goal_signal: 2                               # 1-4 — which detection signal fired
stated_goal_locked: 2026-05-12T17:23:56Z            # ISO-8601 timestamp of capture
```

**Required-when:** goal detection fired AND the minimum-content rule passed (≥ 6 tokens AND propositional content). Otherwise omitted, or `null` with the candidate logged in Decisions.

**Lifecycle:** immutable unless the user explicitly revises the literal. Revision is a `## Decisions` row `refined: stated_goal: was "<old>" now "<new>"`, and `_source` flips to `explicit-revision`.

| # | Detection signal | Pattern |
|---|--------|---------|
| 1 | Named metric + threshold | quantitative target ("p95 < 200ms", "70k subscribers") |
| 2 | Explicit outcome assertion | "I want X" / "achieve X" / "do this" |
| 3 | Completion condition | "until X" / "such that X" |
| 4 | Structural/design directive | explicit verb-object on the system ("absorb", "replace", "unify") |

Multi-literal: the first detected wins; the others demote to derived Constraints.

Optional — ambiguity check outcome:

```yaml
context_sufficient: true                  # false when a reasoned default was accepted via `proceed` or an ambiguity flag
interview_invoked: false                  # true when Scaffold's ambiguity check asked its (≤3) questions
interview_ran: 2026-02-24T02:10:00Z       # set when the Interview workflow asks its first question — what the E5 gate checks
```

Optional — journey summary (handy for a status line):

```yaml
current_state: "Code has 47 type errors blocking deploy"   # the "before", one line, immutable
ideal_state: "Zero type errors, deploy passes CI"          # the "after", aligned with Goal
```

Unknown keys are tolerated by readers; never fail on them.

### Field Rules

- `task`: Imperative mood, max 60 chars. Describes the deliverable, not the process.
- `slug`: `YYYYMMDD-HHMMSS_kebab-description`.
- `effort`: The completeness-gate tier (see below).
- `phase`: Set at the start and whenever it genuinely changes; `complete` is written only by `isa close`, after it re-runs every probe.
- `progress`: `M/N`, counted over **leaf** ISCs in `## Criteria` and `## Bridge Criteria`. A parent with nested children (`ISC-7` over `ISC-7.1`, `ISC-7.2`) is not counted — the engine ticks it when all its leaves are ticked or waived. N excludes tombstoned (dropped) and waived ISCs; M = checked leaves. Engine-owned: `isa lint`, `isa verify` and `isa close` recompute it, so it can lag between commands — status readers count the criteria themselves. Leave it alone (writing the right number is harmless; a wrong one is refused).
- `root`: Engine-owned. Every probe runs with this as its cwd (a Test Strategy entry may add `cwd:` relative to it, or its own `root:`).
- `started`: Set once. Never modified.
- `updated`: Set on every Edit/Write.

## Body Sections

**Fourteen sections in fixed order.** Each appears only when populated — never create empty placeholder sections.

| # | Section | Purpose | Written At |
|---|---------|---------|------------|
| 1 | `## Problem` | What is broken or missing right now | OBSERVE |
| 2 | `## Vision` | Experiential intent — what delight looks like | OBSERVE |
| 3 | `## Out of Scope` | Anti-vision — what is *not* included, declared in prose | OBSERVE |
| 4 | `## Principles` | Substrate-independent truths the work must respect | OBSERVE |
| 5 | `## Constraints` | Immovable architectural mandates (plus every Constraint inherited from `parent:`) | OBSERVE |
| 6 | `## Dependencies` | Cross-ISA needs, one line each: `requires: <slug> — <what/contract>`. Omit when there are none. | OBSERVE |
| 7 | `## Goal` | Hard-to-vary spine — 1–3 sentences naming verifiable done | OBSERVE |
| 8 | `## Criteria` | Atomic ISCs (one binary tool probe each), including derived `Anti:` / `Antecedent:` | OBSERVE → EXECUTE |
| 9 | `## Bridge Criteria` | Cross-ISA integration ISCs: `- [ ] ISC-N: Bridge: <what must hold across the seam>`, with `anchors_to: cross: <slug>` in Test Strategy. Omit when the ISA has no siblings. | OBSERVE → EXECUTE |
| 10 | `## Test Strategy` | One YAML entry per leaf ISC naming its probe (`isc`, `anchors_to`, `type`, `check`, `threshold`, `tool`) — see § Test Strategy | OBSERVE/PLAN |
| 11 | `## Features` | Work breakdown — one YAML entry per vertical slice (`name`, `description`, `satisfies`, `depends_on`, `parallelizable`) — see § Features | PLAN |
| 12 | `## Decisions` | Timestamped log including dead ends; `refined:` prefix | any phase |
| 13 | `## Changelog` | Conjecture / refuted-by / learned / criterion-now entries | LEARN |
| 14 | `## Verification` | Evidence per ISC (leaf + bridge) | VERIFY |

### Tier Completeness Gate (HARD at every tier)

Checked at two moments. **Articulation sections** (1–11) are written up front and checked at articulation and at close. **Record sections** (Decisions, Changelog, Verification) fill up as the work happens and are checked **at close only** — never invented to pass an early check.

| Tier | Articulation sections | Record sections at close |
|------|----------------------|--------------------------|
| **E1** | Goal, Criteria | Verification |
| **E2** | Problem, Goal, Criteria, Test Strategy | Verification |
| **E3** | Problem, Vision, Out of Scope, Constraints, Goal, Criteria, Features, Test Strategy | Verification |
| **E4** | All eleven* | Decisions, Changelog†, Verification |
| **E5** | All eleven* | Same as E4, plus `interview_ran` set (Interview run before BUILD) |

\* `## Dependencies` and `## Bridge Criteria` are **conditional-required**: mandatory when the ISA has any `parent:`/`children:`/cross-ISA relationship, omitted otherwise.

† Satisfied by ≥1 C/R/L entry, or by a Decisions row `no belief refuted this run` — a Changelog is never faked.

### Three-Guardrail Taxonomy

Principles bind the **thinking** (substrate-independent); Constraints bind the **solution space** (immovable); Out of Scope binds the **vision** (declarative anti-vision); Anti-criteria bind the **test surface** (granular `Anti:` ISCs derived from the first three).

### ID-Stability Rule

ISC IDs never re-number on edit. Splits become `ISC-N.M` (parent preserved); drops become tombstones (`- [ ] ISC-N: [DROPPED — see Decisions YYYY-MM-DD]`). Reconcile depends on this; renumbering breaks ephemeral feature reconciliation silently.

### Goal

The hard-to-vary spine of the explanation — 1 to 3 sentences. If `stated_goal` is set, its verbatim quote is the first sentence, in quotes. If you can edit the Goal without changing the ISC set, the Goal isn't load-bearing. If the Goal stays and the ISCs drift away from it, the decomposition is wrong. Sharpen it as work surfaces signal; log structural changes in `## Decisions` with `refined:`.

### Criteria

```markdown
- [ ] ISC-1: Criterion text (8-12 words, binary testable, state not action)
- [ ] ISC-2: Another criterion
- [ ] ISC-3: Anti: What must NOT happen
- [ ] ISC-4: Antecedent: Precondition that reliably produces the target experience
```

**Rules:**
- Each criterion: 8–12 words, describes an end state (not an action)
- Binary testable: either true or false, no judgment required
- **Atomic**: one verifiable thing per criterion — no compound statements
- ID format `ISC-N`; all ISCs number sequentially in one pool; the `Anti:` / `Antecedent:` / `Bridge:` prose prefix carries the kind
- Ticks (`- [x]`) are written by `isa verify`, which runs the probe and ticks what passed — never by hand (the hooks refuse it). Prove each criterion as soon as it can pass; don't batch at VERIFY. Unticking an ISC yourself is allowed (an honest regression)
- The engine ticks a nested parent once all its leaves are ticked, and recomputes `progress`

**The Splitting Test (apply to every criterion):**
- Contains "and"/"with"/"including" joining two verifiable things? → split
- Can part A pass while part B fails independently? → split
- Contains "all"/"every"/"complete"? → enumerate what that means
- Crosses domain boundaries (UI/API/data/logic)? → one per boundary
- Can't name the probe that would verify it? → not atomic yet, split

**Granularity rule:** split until each criterion is one binary tool probe — a single tool call (Read, Grep, Bash, curl, screenshot, SELECT, or user-recognizes-on-encounter for experiential ISCs) returns yes/no. This rule **is** the operational form of hard-to-variability.

**Nested ISCs** are allowed for organization: `ISC-1` → `ISC-1.1`, `ISC-1.2` → `ISC-1.1.1`. The granularity rule applies at the **leaf**; parents pass when all descendant leaves pass. Flat is fine when the ISA is small.

**Coverage gate (no count floors).** Every subsystem named in Vision/Goal has a container ISC, and every container decomposes via the Splitting Test until each leaf is one probe. A 24-leaf ISA passes if it covers the surface; a 300-leaf ISA fails if a named subsystem has none. Never split to hit a number.

**Doctrinal minimums:** anti-criteria ≥ 1 (a goal with zero failure modes worth naming is under-specified). Antecedent ≥ 1 when the goal is experiential.

### Test Strategy

One entry per leaf ISC, as a YAML list inside a fenced block (key order doesn't matter; this is the shape every example uses):

````markdown
## Test Strategy

```yaml
- isc: ISC-3
  anchors_to: literal              # literal | derived: <sub-claim> | cross: <slug> — required when stated_goal is set
  type: bash
  check: HTTP status + content-type
  threshold: 200 + text/html
  tool: curl -i https://example.com
```
````

| Key | Meaning |
|-----|---------|
| `isc` | The ISC ID this entry verifies (must exist in `## Criteria` / `## Bridge Criteria`) |
| `anchors_to` | What the ISC traces to: the verbatim goal (`literal`), a named derived sub-claim, or a sibling ISA for bridge ISCs |
| `type` | Probe form — prefer the vocabulary below |
| `kind` | What the ISC claims — sets the minimum probe type (table below). Required from E2 |
| `check` | What is being checked, in words |
| `threshold` | The pass condition — the value that makes it yes/no |
| `tool` | The exact command, file, or procedure that runs the probe |
| `risk` | `high`, or `low — <why>`. Required when the ISC or its probe mentions secrets, tokens, credentials, passwords, auth, logins, permissions, payments, billing, money, invoices, deploys, prod, publish, release or push |
| `red` | `exempt — <why>`: this behaviour/http/schema probe can't be run red first (see red-then-green) |
| `cwd` | Directory the probe runs in, relative to the ISA's `root` |
| `root` | Another project (path relative to `$HOME`) the probe runs in — for an ISA spanning projects |
| `class` | Tags the ISC as one instance of a defect class: close then needs a `class-sweep:` row |
| `fails-when` | What the probe would see if the claim were false. Required from E2 on a mechanical probe whose ISC can't be seen failing first: an `Anti:` ISC, a `kind:` without the red step (config, doc, file, decision, visual, regression), or `red: exempt`. `isa close` lists it beside each ISC never seen failing |

**Mechanical vs self-attested.** Every type except `manual`, `screenshot` and `eval` is *mechanical*: its `tool` is a shell command that `isa verify <ISA> ISC-N` runs from the ISA's `root`, and it **passes iff it exits 0** — so build any other threshold into the command (`test "$(… | wc -l)" -eq 12`). Write it relative to the project (no `cd /absolute/path`; use `cwd:`). The `tool` must be runnable exactly as written: a placeholder (`<session-id>`, `…`) is a lint error. `isa verify` records each result in an engine-owned evidence ledger (`evidence.jsonl` beside a repo ISA, else under `~/.isa/_state/`; never written by hand) together with a fingerprint of the project tree, then ticks what passed, unticks what regressed, and writes the Verification line. `isa close` re-runs every mechanical probe and closes only when all pass — that re-run is what makes the close fresh. A probe must only observe: one that changes the tree is reported, recorded, and refused at close.

`manual`, `screenshot` and `eval` ISCs — and ISCs with no Test Strategy entry (E1) — are *self-attested*: `isa verify <ISA> ISC-N --attest "<evidence>"` ticks them with your evidence, and the close summary lists them to the user as not machine-verified.

**`kind:` sets the minimum probe type** (errors for ISAs started under v2, warnings for older ones):

| `kind` | The ISC claims | Refused |
|--------|----------------|---------|
| `behaviour` | code does X when run | `manual` / `screenshot` / `eval`, and a grep-only probe (it reads text, it doesn't run the code) |
| `http` | an endpoint answers X | same as behaviour |
| `schema` | data has shape X (query it) | `manual`, grep-only |
| `regression` | something must stay true | `manual` / `screenshot` / `eval` |
| `config` | a setting has value X (read it back) | `manual` |
| `visual` | it looks like X | a grep-only probe (look at it: `screenshot`, `eval`) |
| `file` | a file exists / contains X | — |
| `doc` | a prose deliverable | — |
| `decision` | a choice was made and recorded | — |

"Grep-only" means every command of the probe only reads text (`grep`, `rg`, `test`, `cat`, `head`, `tail`, `wc`).

**`risk: high`** ISCs can't be self-attested: a `manual` / `screenshot` / `eval` probe is a lint error (and `--attest` is refused) unless the user waives the ISC; and close needs a `second-look:` Decisions row. `risk: low — <why>` reasons are listed in the close summary.

**Red-then-green** (behaviour / http / schema ISCs at E2+, except `Anti:`, `kind: regression` and `red: exempt — <why>`): write the test, run `isa verify --red <ISA>` before building (it records the failing baseline and ticks nothing), then build and `isa verify`. A green run ticks plainly only when an earlier *failed* red run of the same probe text saw a different tree; otherwise it is ticked `(no red baseline)` and the close lists it next to the self-attested ones, with the reason. A probe that passes its red run can't fail — `isa lint` warns that it proves nothing. Nothing is ever blocked for lack of a baseline. ISCs that can never get a red run carry `fails-when:` instead: the claim it would take to fail, written down, so a probe that can't fail shows itself to the writer and to the reader of the close summary.

**Probe downgrades are visible.** Once the first `isa verify` has snapshotted the Test Strategy, turning a runnable probe into a self-attested one, weakening `kind:`, removing a `tool:`, or self-attesting an ISC whose probe failed needs a Decisions row `refined: ISC-N probe downgraded — <why>`; without it, lint fails.

**Probe types.** Prefer these; a more specific label (`deploy-probe`, `parity-test`, …) is fine when none fits, as long as `tool` + `threshold` still make it binary.

| Type | Probe form | When to use |
|------|------------|-------------|
| `unit-test` | test runner on a file/pattern exits 0 | Example-based correctness — fixed-input deterministic code |
| `property` | property-based test with generator + run count | Universal claims — pure functions, parsers, serializers, math, data transforms |
| `bash` | shell command exits 0 / output matches | grep, diff, curl, jq probes |
| `manual` | user recognizes it on encounter | Experiential ISCs — design, voice, "feels right" |
| `screenshot` | an image of the rendered output, actually looked at | UI rendering and appearance |
| `eval` | rubric / LLM-judge passes | Agent transcript quality, multi-turn flows |

**`property` entries** replace `check`/`threshold` with the claim and its input space:

```yaml
- isc: ISC-N
  anchors_to: literal
  type: property
  property: "round-trip: parse(serialize(x)) ≡ x"
  generator: "fc.record({ ...frontmatter schema })"   # bounded to the function's real input domain
  runs: 1000                                          # 10000 for invariant-critical, 100 for slow generators
  tool: bun test test/isa-utils.property.test.ts -t "round-trips"
```

**`bash` entries** — the workhorse: any shell command whose **exit code** decides it (`isa verify` never reads the output). `tool` is the exact command; `threshold` describes the pass condition, which the command itself must enforce: `jq -e '<test>'`, `test "$(… | wc -l)" -le 5`, `rg -q` for "appears". For "never appears" negate it — `! rg -q 'pattern' file` — because `rg 'pattern'` exits 0 exactly when the forbidden thing is found. A command that only prints a value (`wc -l`, `jq '.x'`, `--count`, `sort -u`) passes whatever the value.

```yaml
- isc: ISC-4
  type: bash
  check: no secret-looking strings in the build output
  threshold: zero matches (rg exits 1)
  tool: rg -n -i 'api[_-]?key|secret|BEGIN [A-Z ]*PRIVATE KEY' dist/

- isc: ISC-5
  type: bash
  check: health endpoint reports the new schema version
  threshold: "3"
  tool: curl -s https://api.example.com/health | jq -r '.schema_version'

- isc: ISC-6
  type: bash
  check: CLI startup time
  threshold: mean < 50 ms
  tool: hyperfine --warmup 3 --export-json /tmp/h.json 'mycli --version' && jq '.results[0].mean*1000' /tmp/h.json

- isc: ISC-7
  type: bash
  check: --help output matches the approved golden file
  threshold: empty diff (exit 0)
  tool: diff <(mycli --help) test/golden/help.txt

- isc: ISC-8
  type: bash
  check: invalid config is rejected with the documented exit code
  threshold: exit code 2
  tool: mycli --config test/fixtures/bad.toml; test $? -eq 2
```

**At E3+, every ISC about a pure function SHOULD have a `property` entry.** When property form doesn't apply (impure function, externally driven dependency, infinite-state machine), say why in `## Decisions`.

**Anti-ISCs default to universal form at E3+.** "API_KEY isn't in env" becomes "∀ env-var-name in spawned env: name !~ /API_KEY|AUTH_TOKEN/i" — a property over the failure pattern, not one instance. Example form is fine when the input domain is small and finite.

**Blast-radius probe strictness.** When an ISC touches high-blast surface — secrets, auth, personal data, money movement, a push to a public remote, a prod deploy — mark it `risk: high`: its probe must be deterministic (`bash` / `unit-test` / `property`; never `manual`, and never a `screenshot` alone), the satisfying change should land as a small, line-readable diff, and the close needs a `second-look:` row. Low-blast ISCs can be verified empirically without a line-by-line read.

### Features

One YAML entry per vertical slice — an end-to-end, independently verifiable increment (never a horizontal layer):

````markdown
## Features

```yaml
- name: ListingPipeline
  description: Submit → pending review → approved → public
  satisfies: [ISC-5, ISC-6, ISC-7]
  depends_on: []
  parallelizable: false

- name: BrowseAndSearch
  description: Paginated browse, filters, substring search
  satisfies: [ISC-10, ISC-11]
  depends_on: [ListingPipeline]
  parallelizable: true
```
````

`name` is what ephemeral mode looks up; `satisfies` lists the ISC IDs a slice worker receives; `depends_on` names other Features.

**`depends_on` is enforced (dependency order).** A Feature is done when every counted leaf ISC it `satisfies` is ticked. `isa verify` ticks in that order: within one run it ticks a dependency's ISCs before its dependents'; a dependent ISC whose dependency still has open ISCs passes but *waits* (its pass is recorded, it never freezes other work) and is ticked by a later run once the dependency is done. ISCs in no Feature, or in Features without `depends_on`, are unconstrained. An unknown `depends_on` name or a dependency cycle is a lint error.

### Decisions

Timestamped decision log, any phase. Include dead ends — failed approaches prevent future sessions from re-exploring them.

```markdown
- 2026-02-24 02:00: Chose X over Y because Z
- 2026-02-24 02:30: ❌ DEAD END: Tried B — failed because C (don't retry)
- 2026-02-24 03:00: refined: Goal sharpened — added "without breaking external API" after research surfaced consumer count
- 2026-02-24 03:15: refined: ISC-7 split into ISC-7.1 / ISC-7.2 — Verify probe revealed two distinct failure modes
- 2026-02-24 05:00: waived: ISC-12 — "load test can wait for the staging env next month"
- 2026-02-24 05:30: refined: ISC-9 probe downgraded — the vendor sandbox is gone, checked by hand against the dashboard
- 2026-02-24 05:45: second-look: a fresh-context reviewer read the auth diff, findings below
- 2026-02-24 05:50: finding: token logged at debug level — adopted (ISC-14)
- 2026-02-24 05:55: class-sweep: unescaped SQL — 4 siblings via rg -n 'execute(f"'; 4 fixed, 0 tombstoned
- 2026-02-24 05:58: repro-bypass: pure-additive — a new flag, no bug to reproduce
- 2026-02-24 06:00: no belief refuted this run
```

Use `refined:` whenever a decision changes the Goal or restructures the ISC set. `waived:` is written only on the user's explicit say-so and **quotes the user verbatim** (`waived: ISC-N — "<their words>"`; lint checks the quote against the prompts of the ISA's sessions); a waived ISC stays `[ ]`, leaves the `progress` denominator, and no longer blocks close. `no belief refuted this run` lets an E4+ ISA close without a Changelog when understanding genuinely never changed.

Rows the commands check by shape (they can't check that the row is true — that stays honest self-attestation):

| Row | Required when | Shape |
|-----|---------------|-------|
| `second-look:` | close, with any `risk: high` ISC or `effort` E4+ | `second-look: <who/what reviewed, where its findings are> \| skipped — <why>` |
| `finding:` | a review produced findings | `finding: <text> — adopted (<diff/ISC>) \| rebutted (<reason>) \| deferred (<task>)` |
| `class-sweep:` | close, for each Test Strategy `class:` | `class-sweep: <class> — N siblings via <probe>; M fixed, K tombstoned` |
| `repro-bypass:` | a reported bug was not reproduced first | `repro-bypass: pure-additive \| non-isolable \| repro would cause damage — <why>` |
| `refined: ISC-N probe downgraded — <why>` | a probe was weakened (see Test Strategy) | — |

### Changelog

Deutsch error-correction trail. Four parts, always, in order (see `Workflows/Append.md`):

```markdown
- 2026-03-22 | conjectured: <what we believed>
  refuted by: <evidence that broke the belief>
  learned: <what the evidence taught us>
  criterion now: <which ISC was added/changed/dropped as a result>
```

### Verification

Evidence for each criterion (leaf and bridge), one `- Ask N:` line per ask, and a closing `Goal:` line — one per iteration; a reopened ISA adds a new one and only the latest counts.

The ISC lines are **generated**: `isa verify` writes them from its ledger (`verified` for a passing probe, `attested` for `--attest`, `regressed` when a ticked probe fails again), with a `(ledger: …#L<n>)` reference a reader can check. You never write or edit those — the hooks refuse it. You write the `[DEFERRED-VERIFY]`, `- Ask N:` and `- Goal:` lines.

```markdown
- ISC-1: attested 2026-03-01T10:02:11 — layout renders correctly in /tmp/x.png, looked at (ledger: 20260301-090000_x-3f2a9c1d0e4b#L4)
- ISC-2: verified 2026-03-01T10:03:40 — exit 0 in 2.1s — `bun test` (ledger: 20260301-090000_x-3f2a9c1d0e4b#L7)
- ISC-3: verified 2026-03-01T10:03:40 — exit 0 in 0.2s — `! rg -n 'SSN' out/` (no red baseline) (ledger: 20260301-090000_x-3f2a9c1d0e4b#L8)
- ISC-7: regressed (passed at 2026-03-01T09:40:02) — FAIL 2026-03-01T10:03:40 — exit 1 — `npm test -- -t "cap"`
- ISC-12: [DEFERRED-VERIFY] — needs the staging env, not provisioned yet — follow-up: rerun k6 once staging is up
- Ask 1: met — every endpoint listed with its check
- Ask 2: skipped — the user dropped the load test (see the waiver)
- Goal: yes — "get p95 latency under 200ms": load test over the full request mix (not a sample) reports p95 = 182 ms (k6 summary, run 2026-03-01)
```

**`- Ask N:` lines** answer the frontmatter `asks` in order: `met`, `skipped — <why>`, or `surfaced` (raised with the user, not done). A missing line counts as unmet and `isa close` refuses.

**`[DEFERRED-VERIFY]`** is a holding state for a probe that genuinely can't run yet. The ISC stays `[ ]` and blocks `complete` until it is probed or the user waives it (`waived:` Decision).

**The `Goal:` line (frame-drift check).** Every ISC can pass while the *set* of ISCs has drifted onto an easier neighbor of what was asked. So before `phase: complete`, re-read the verbatim goal (`stated_goal`, or the Goal section's first sentence when that is null) and answer, against the finished result: does this deliver the *intent* of that sentence, not just its surface? Write `- Goal: yes — <evidence>` or `- Goal: no — <what's missing>`. A `no` blocks `complete`: add the missing ISCs (or get the user's explicit narrowing, logged as a `refined:` Decision) and climb again.

## Continuation / Rework

- A follow-up that continues the same task edits the existing ISA; a genuinely new task gets a new slug.
- Editing the body of a `phase: complete` ISA reopens it: `phase: learn`, `iteration` incremented (2 on the first reopen), `resumed_at` set, and a Decisions row naming why. `frozen: true` bypasses this (pure corrections). It closes again only through `isa close`.
- After a context compaction or a new session: read the ISA, continue from its current state, never redo gates that already passed.

## Design Rationale

- **Few frontmatter fields**: only fields something actually reads (the loop, a status line). Dead fields waste tokens.
- **Fixed section order, empty sections never appear**: every section has one purpose; boilerplate is noise.
- **Checkboxes over EARS/BDD**: simpler to parse, write, and verify.
- **YAML frontmatter**: universal standard (Jekyll, Hugo, Astro, Kiro, spec-kit).
- **Universal primitive**: the same structure serves software, science, art, decisions. Hard-to-variability is the quality standard for the writing; testability is its operational form; refinement through pursuit is the living document.
- **Minimal-structure discipline**: no structural field a smarter model would render unnecessary.

The artifact was called "PRD" before being renamed ISA — it pairs with ISC and stresses that the output is a tangible, verifiable artifact.
