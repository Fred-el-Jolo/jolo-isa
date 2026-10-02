# Append Workflow

Canonical writer for the model-owned entries of the three record sections of an ISA: `## Decisions`, `## Changelog`, and the `- Goal:`, `- Ask N:` and `[DEFERRED-VERIFY]` lines of `## Verification`. The Deutsch conjecture/refutation/learning Changelog format is novel and easy to mangle with free-form editing — this workflow owns the canonical entry shape so it doesn't degrade across projects.

**Not Append's job: ISC evidence.** The `- ISC-N:` lines that prove a criterion (`verified` / `attested` / `regressed`) are written by `isa verify` from its ledger, together with the tick and `progress` — never by hand (the hooks refuse it). When an ISC can pass, run `isa verify <ISA> ISC-N` (or `isa verify <ISA> ISC-N --attest "<evidence>"` for a manual / screenshot / eval criterion).

## When to invoke

- The work loop at any phase when a non-obvious decision is made: `Skill("ISA", "append decision to <isa-path>: <text>")`
- The work loop at LEARN when understanding evolved: `Skill("ISA", "append changelog to <isa-path>: <conjecture> / <refutation> / <learning>")`
- Before `isa close`: `Skill("ISA", "append goal line to <isa-path>: yes|no — <evidence>")` and one Ask line per entry of `asks`
- When a probe genuinely can't run yet: `Skill("ISA", "append deferred to <isa-path>: ISC-N — <why> — <follow-up>")`
- User directly when adding an entry by hand.

## Entry types

### Type 1 — Decision

Timestamped log line. Use the `refined:` prefix when the decision changes the Goal or restructures the ISC set.

**Schema:**

```
- YYYY-MM-DD HH:MM: <decision text>
- YYYY-MM-DD HH:MM: refined: <what was refined and why>
- YYYY-MM-DD HH:MM: ❌ DEAD END: Tried <X> — failed because <Y> (don't retry)
- YYYY-MM-DD HH:MM: waived: ISC-N — "<the user's words, verbatim>"
- YYYY-MM-DD HH:MM: refined: ISC-N probe downgraded — <why>
- YYYY-MM-DD HH:MM: second-look: <who/what reviewed, where its findings are> | skipped — <why>
- YYYY-MM-DD HH:MM: finding: <text> — adopted (<diff/ISC>) | rebutted (<reason>) | deferred (<task>)
- YYYY-MM-DD HH:MM: class-sweep: <class> — N siblings via <probe>; M fixed, K tombstoned
- YYYY-MM-DD HH:MM: repro-bypass: pure-additive | non-isolable | repro would cause damage — <why>
- YYYY-MM-DD HH:MM: no belief refuted this run
```

**Inputs:** `text` (required), `kind` (optional: `decision` | `refined` | `dead-end` | `waived` | `downgrade` | `second-look` | `finding` | `class-sweep` | `repro-bypass` | `no-refutation`)

- `waived` — only on the user's explicit say-so; the model never waives its own criteria. The row quotes the user byte-for-byte (lint checks the quote against the prompts of the ISA's sessions). A waived ISC stays `[ ]`, leaves the `progress` denominator, and no longer blocks close.
- `downgrade` — required when a probe is weakened after the first `isa verify` (runnable → self-attested, a weaker `kind:`, a `tool:` removed, or self-attesting an ISC whose probe failed).
- `second-look` / `class-sweep` — `isa close` requires them when a `risk: high` ISC or E4+ (second-look) or a Test Strategy `class:` (class-sweep) calls for them. The command checks the shape, not the truth: write what actually happened.
- `no-refutation` — written at close when understanding never changed, so an E4+ ISA can close without inventing a Changelog entry.

### Type 2 — Changelog (the Deutsch C/R/L entry)

Structured entry capturing how thinking evolved.

**Schema:**

```
- YYYY-MM-DD | conjectured: <what we believed>
  refuted by: <evidence that broke the belief>
  learned: <what the evidence taught us>
  criterion now: <which ISC was added/changed/dropped as a result>
```

**Inputs:** All four fields required (`conjectured`, `refuted_by`, `learned`, `criterion_now`).

**Format invariant:** The four-line shape is non-negotiable. If any of the four pieces is missing, this is a Decision entry, not a Changelog entry. Refuse to write a partial C/R/L; surface the missing piece and ask.

### Type 3 — Verification lines the model writes

**Goal line (once per iteration, at close):** `- Goal: yes|no — <evidence the finished result delivers the intent of the verbatim goal>`. Takes `verdict` (`yes`/`no`) + `evidence`; refuse if evidence is empty. Written after the last ISC passes. See `References/IsaFormat.md` § Verification.

**Ask lines (at close, one per entry of the frontmatter `asks`, in order):** `- Ask N: met — <evidence>`, `- Ask N: skipped — <why>`, or `- Ask N: surfaced — <what was raised with the user>`. A missing line counts as unmet and `isa close` refuses.

**Deferred line:** `- ISC-N: [DEFERRED-VERIFY] — <why it can't be probed now> — follow-up: <what, when>`. Used when the probe genuinely can't run yet (e.g., needs a production deploy that hasn't happened). The ISC stays `[ ]` and blocks close until `isa verify` proves it or the user waives it.

## Procedure

### Step 2 — Resolve target ISA and section

Read the ISA at `isa_path`. Find the target section (`## Decisions` | `## Changelog` | `## Verification`). If the section doesn't exist, create it at its place in the fourteen-section order: right after the last present section that precedes it. Decisions, Changelog, and Verification are always the last three, in that order — so an E1 ISA with only Goal and Criteria gets `## Verification` right after `## Criteria`.

### Step 3 — Validate the entry shape

| Type | Required pieces | Refuse if... |
|------|-----------------|--------------|
| Decision | text + timestamp | text is empty |
| Decision — `waived` | isc_id + the user's verbatim words | the user didn't explicitly ask for the waiver |
| Decision — shape rows | the schema above | the row doesn't match its schema |
| Changelog | conjectured + refuted_by + learned + criterion_now + date | any of the four C/R/L pieces is missing |
| Verification — Goal line | verdict (`yes`/`no`) + evidence | evidence is empty, or a non-dropped, non-waived ISC is still `[ ]` |
| Verification — Ask line | N + status (+ reason for `skipped`) | N is not an entry of `asks` |
| Verification — Deferred line | isc_id + reason + follow-up | isc_id doesn't exist, or reason/follow-up is empty |
| Verification — an `- ISC-N:` evidence line | — | always: run `isa verify` instead |

**Refuse mode:** If validation fails, do not write. Surface the missing piece. The whole point of Append is to keep these sections clean — silently writing partial entries defeats it.

### Step 4 — Format the entry

Use the schemas above verbatim. Prefer single-line entries over multi-line where the schema permits. For Changelog entries, use the four-line indented form exactly.

### Step 5 — Append to the section

Edit the ISA with Edit/Write (never a shell command): append the entry to the end of the target section, preserving prior entries. You may set `updated: <ISO-8601>`; leave `progress` to the engine (`isa lint` recomputes it, e.g. after a waiver).

**On an ephemeral slice** (file carries the `<!-- EPHEMERAL FEATURE FILE … -->` header and no frontmatter): skip every frontmatter update. Reconcile merges the slice's Decisions, Changelog and Deferred lines into master.

### Step 7 — Return the appended block

Output the exact text that was appended, plus the path. Caller can re-emit for confirmation.

## Why this workflow exists

The Deutsch C/R/L Changelog format is the most opinionated piece of the ISA doctrine and the easiest to dilute. Three failure modes if there's no canonical writer:

1. **Free-form prose creep:** "we changed our minds about X" instead of the four-piece structure.
2. **Half-entries:** `conjectured` + `criterion now` without the refutation evidence in between.
3. **Format drift:** different projects evolve different conventions, breaking cross-project search and tooling.

Append is the gate for every model-written record entry. The evidence for each criterion has a stricter gate still: only `isa verify` writes it, from a probe it ran.

## Interaction with Reconcile

The Reconcile workflow (merging an ephemeral feature file back to master) calls Append internally for each Decisions, Changelog, and Deferred entry it stages. This means Reconcile's output passes the same shape validation as direct Append calls — the merge cannot smuggle in malformed entries.

## Failure modes

- **Concurrent edits:** Append reads the ISA, decides where to insert, then writes. If the file is edited mid-flight (an `isa verify` run rewrites it too), the second write may meet stale text — re-read the ISA and retry.
- **Section header missing:** Append creates the section if absent, in canonical position. If the canonical position is ambiguous (file is malformed), abort and surface the structural problem.
- **ISC ID mismatch on a Deferred line:** the ISC must exist. Refuse to write a line for an ID that isn't in `## Criteria` or `## Bridge Criteria` — this is the same ID-stability contract Reconcile relies on.
