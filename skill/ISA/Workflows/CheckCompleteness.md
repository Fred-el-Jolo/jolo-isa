# CheckCompleteness Workflow

Score an existing ISA against the tier completeness gate and return a structured pass/fail + gap report. The gate is HARD at every tier and runs at two moments: **articulation** (done is written down, nothing built yet) and **close** (about to set `phase: complete`). Some sections can only honestly exist at close, so each moment checks different things.

## When to invoke

- End of articulation — Scaffold Step 9, after an Interview, or the work loop before building: `moment: articulation`.
- Before closing — the work loop right before `phase: complete`: `moment: close`.
- User directly: `Skill("ISA", "check completeness of <isa-path> at tier <tier>")` — moment inferred (see Inputs).

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| isa_path | yes | Path to the ISA to score |
| tier | no | The completeness bar (E1 / E2 / E3 / E4 / E5). Default: the ISA's `effort:` |
| moment | no | `articulation` or `close`. Default: `close` when `phase` is `verify`, `learn`, or `complete`, or the caller is about to close; otherwise `articulation` |
| strict | no | Default true. If false, downgrade hard fails to soft warnings. |

## Output

```yaml
status: pass | fail
tier: E4
moment: articulation
required_sections:
  Problem: present
  Vision: present
  Out of Scope: missing
  Principles: present
  Constraints: present
  Dependencies: absent     # conditional — required only when cross-ISA links exist
  Goal: present
  Criteria: present
  Bridge Criteria: absent  # conditional — required only when cross-ISA links exist
  Test Strategy: present
  Features: present
  Decisions: not-yet       # record section — checked at close only
  Changelog: not-yet
  Verification: not-yet
gaps:
  - section: Out of Scope
    severity: hard
    reason: required at E4, missing entirely
isc_quality:
  total_leaves: 24             # counted per IsaFormat § Field Rules (progress)
  coverage_gaps: 0             # Vision/Goal subsystems with no container criterion
  granularity_violations: 0
  anti_criteria_count: 2
  antecedent_present: true
  test_strategy_orphans: 0     # leaf ISCs with no Test Strategy entry naming a probe
  id_stability_violations: 0
  open_at_close: 0             # close only — non-dropped, non-waived ISCs still [ ]
```

## Procedure

### Step 2 — Read the ISA

Load `isa_path`. Parse frontmatter and section headers. Resolve `tier` and `moment` (see Inputs).

### Step 3 — Look up what is required at this moment

Sections fall into two groups by when they can honestly exist:

| Group | Sections | Checked at |
|-------|----------|------------|
| **Articulation sections** | Problem, Vision, Out of Scope, Principles, Constraints, Dependencies, Goal, Criteria, Bridge Criteria, Test Strategy, Features | articulation **and** close |
| **Record sections** | Decisions, Changelog, Verification | close only — they record what happened, so they can't be demanded before anything happened. Never invent them to pass an articulation check. |

Requirements per tier:

| Tier | Articulation sections required | Record sections required at close |
|------|-------------------------------|-----------------------------------|
| E1 | Goal, Criteria | Verification |
| E2 | Problem, Goal, Criteria, Test Strategy | Verification |
| E3 | Problem, Vision, Out of Scope, Constraints, Goal, Criteria, Features, Test Strategy | Verification |
| E4 | All eleven (Dependencies / Bridge Criteria only when cross-ISA links exist) | Decisions, Changelog\*, Verification |
| E5 | Same as E4 | Same as E4, plus frontmatter `interview_ran` set |

\* The Changelog records refuted beliefs, so it can't be forced. At E4+ close it is satisfied by ≥1 C/R/L entry **or** by a Decisions row `no belief refuted this run` (the Changelog section then stays absent — empty sections never appear).

### Step 4 — Classify each section required at this moment

| Classification | Test |
|----------------|------|
| `present` | Section header exists and body has content — length is not graded; a one-sentence section can be exactly right |
| `missing` | Section header doesn't exist |
| `empty` | Section header exists, body is whitespace only — never acceptable (empty sections never appear) |

Sections not required at this moment are reported as `not-yet` (record sections at articulation) or `absent` (conditional sections that don't apply).

### Step 5 — Audit ISC quality (both moments)

Walk every ISC in `## Criteria` and `## Bridge Criteria`:

- **Granularity** — every non-dropped **leaf** ISC names a single binary tool probe (or has one inferable from its phrasing). Compound "and/with" criteria fail. Nested parents are containers, not probes — they are exempt.
- **Coverage** — every subsystem named in Vision/Goal has a container criterion decomposed until each leaf is one binary tool probe; never split to hit a number. A subsystem with no container criterion is a coverage gap.
- **Anti-criteria (HARD at every tier)** — at least one ISC has the `Anti:` prefix. Most often forgotten; this check is the teeth.
- **Test Strategy coverage (HARD fail at E2+)** — every non-dropped leaf ISC has a `## Test Strategy` entry naming its probe (tombstones need none). Orphan leaves fail (E1 has no Test Strategy section, so exempt).
- **Antecedent** — when the goal is experiential, at least one ISC has the `Antecedent:` prefix.
- **ID stability** — every ISC has a unique sequential ID. No collisions, no gaps from renumbering. Tombstones (e.g., `ISC-7: [DROPPED — see Decisions 2026-04-15]`) are valid.
- **Anchoring (E2+)** — when frontmatter `stated_goal:` is set, every ISC must have an `anchors_to` value in its Test Strategy entry (`literal`, `derived: <sub-claim>`, or `cross: <slug>` for bridge ISCs). Orphan ISCs (no traceable anchor) are a hard failure. E1 is exempt: it has no Test Strategy section.

### Step 5a — Goal-literal check (articulation only)

Runs only at `moment: articulation`, when the originating prompt is in hand. At close the prompt may be gone (new session, compaction) — skip rather than guess. Applies whether or not the frontmatter has a `stated_goal` key (a missing key is exactly what a missed capture looks like).

- If the originating prompt clearly matched one of Scaffold's four goal signals (metric+threshold, explicit outcome, completion condition, structural directive) AND `stated_goal:` is absent, empty, or null → hard failure: "literal capture missed — prompt stated a goal but Scaffold did not preserve it."
- If `stated_goal:` is a non-null string but is < 6 tokens or fails the minimum-content rule → hard failure: "literal violates minimum-content rule — should have been `null`."

### Step 5b — Artifact-Presence Check (E4+, both moments)

For every ISC marked `[x]` in `## Criteria` that claims a named design surface (e.g., "the proposal includes X", "the design names Y", "a table appears"), scan the ISA body for that surface textually:

- If the surface is asserted complete by an `[x]` but no textual evidence appears in the ISA body → hard failure: "ISC claims surface that does not exist in artifact (system-of-record violation)."
- The ISA artifact must contain its own design surface, not reference ephemeral chat context. The system-of-record identity (one of the five) requires this.

### Step 5c — Goal-delivery check (close only)

The **latest** `- Goal: …` line in `## Verification` must say `yes`, and must come after the last ISC Verification entry (a reopened ISA carries one Goal line per iteration; only the newest counts). No Goal line after the last ISC closed, or a latest line saying `no`, is a hard failure: "frame-drift check not passed — ISCs pass but the goal's intent is not shown delivered."

### Step 5d — Open, deferred, and waived ISCs (close only)

- Every non-dropped leaf ISC is `[x]` with a Verification entry, **or** waived by a Decisions row `waived: ISC-N — <user's reason>` (only the user can waive).
- A `- ISC-N: [DEFERRED-VERIFY] — …` Verification line keeps the ISC `[ ]`. At close, every deferred ISC must also be waived.
- Any other non-dropped, non-waived ISC still `[ ]` → hard failure: "open criteria at close: ISC-…".

### Step 6 — Compose the report

Emit the structured YAML output above. Set `status: pass` only when zero hard severity gaps. `strict: false` downgrades hard severity to warnings (used during interview when the user is mid-stream).

### Step 7 — Block on hard gaps

At `moment: articulation`, hard gaps block building — fill them first. At `moment: close`, hard gaps block the `phase: complete` transition — the caller must fill them before declaring done.

## Severity table

| Gap | Checked at | E1 | E2 | E3 | E4 | E5 |
|-----|-----------|----|----|----|----|----|
| Goal missing | both | hard | hard | hard | hard | hard |
| Criteria missing | both | hard | hard | hard | hard | hard |
| Problem missing | both | — | hard | hard | hard | hard |
| Test Strategy missing | both | — | hard | hard | hard | hard |
| Vision missing | both | — | — | hard | hard | hard |
| Out of Scope missing | both | — | — | hard | hard | hard |
| Constraints missing | both | — | — | hard | hard | hard |
| Features missing | both | — | — | hard | hard | hard |
| Principles missing | both | — | — | — | hard | hard |
| Verification missing | close | hard | hard | hard | hard | hard |
| Decisions missing | close | — | — | — | hard | hard |
| Changelog missing and no `no belief refuted this run` Decisions row | close | — | — | — | hard | hard |
| `interview_ran` missing | close | — | — | — | — | hard |
| Anti-criteria count = 0 (≥1 `Anti:` ISC required) | both | hard | hard | hard | hard | hard |
| Leaf ISC without a Test Strategy entry naming its probe | both | — | hard | hard | hard | hard |
| Antecedent missing (experiential) | both | hard | hard | hard | hard | hard |
| ID-stability violation | both | hard | hard | hard | hard | hard |
| Coverage gap (Vision/Goal subsystem with no container criterion; Goal-only at E2) | both | — | soft | hard | hard | hard |
| Granularity violation | both | hard | hard | hard | hard | hard |
| Anchoring violation (orphan ISC, when `stated_goal` is set) | both | — | hard | hard | hard | hard |
| Goal-literal violation (Step 5a) | articulation | hard | hard | hard | hard | hard |
| `Goal:` line missing or `no` (Step 5c) | close | hard | hard | hard | hard | hard |
| Open or unwaived-deferred ISC (Step 5d) | close | hard | hard | hard | hard | hard |
| Artifact-presence violation | both | — | — | — | hard | hard |
| `context_sufficient` missing | both | — | hard | hard | hard | hard |

## Failure modes

- **Frontmatter missing or malformed:** abort with explicit error. The frontmatter is non-negotiable.
- **ISC body parsing fails:** treat as zero ISCs and surface the parse error.
