# Reconcile Workflow

Deterministic merge of an ephemeral feature-file excerpt back into the master ISA, keyed on stable ISC IDs. The cornerstone of the parallel-worker pattern — without this, ephemeral feature work drifts from master and creates the same "code drifts from spec" problem the ISA is meant to solve.

**A worker's checkmarks are never copied.** Ticks in the master ISA are engine-owned: only `isa verify` writes them, from a probe it ran against the master's `root`. So Reconcile merges what the worker *wrote* (Decisions, Changelog, Deferred lines) and then asks the engine to prove what the worker *claims*: it runs `isa verify <master> <the ISCs the worker ticked>`, which ticks what passes there.

## When to invoke

- A feature-context agent (subagent, worktree worker, parallel coding-agent instance) finishes work on an ephemeral feature file, and its code changes are in the master's project.
- The work loop at LEARN: `Skill("ISA", "reconcile <ephemeral-path> → <master-path>")`
- User directly: `Skill("ISA", "reconcile <ephemeral-path> → <master-path>")`

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| ephemeral_path | yes | Path to the ephemeral feature file (`~/.isa/<project>/{slug}/_ephemeral/<feature>.md`) |
| master_path | yes | Path to the master ISA the ephemeral was derived from |
| dry_run | no | Default false. If true, report planned changes without writing or running probes. |

## Output

```yaml
status: applied | dry_run | aborted
ephemeral: <path>
master: <path>
applied:
  claimed: [ISC-12, ISC-13, ISC-14, ISC-15, ISC-31]        # ticked in the ephemeral
  proven: [ISC-12, ISC-13, ISC-14, ISC-31]                 # ticked in master by `isa verify`
  failed: [ISC-15]                                         # claimed but its probe fails in master
  deferred_added: 1                                        # [DEFERRED-VERIFY] lines carried over
  decisions_added: 2                                       # Decisions entries appended
  changelog_added: 1                                       # Changelog entries appended
archived_to: ~/.isa/<project>/.../_ephemeral/.archive/AuthSystem-2026-04-15.md
errors:
  - isc: ISC-99
    reason: not present in master — ephemeral references unknown ID
```

## Procedure

### Step 2 — Read both files

Load ephemeral and master. Confirm ephemeral has the canonical header marker (`<!-- EPHEMERAL FEATURE FILE — derived from ... -->`); abort if not (refusing to merge anything that didn't come from Scaffold's ephemeral mode).

### Step 3 — Build the ISC claim list

For each ISC in the ephemeral file:
- If `[x]` in ephemeral: add it to `claimed` (it will be proven, not copied).
- If `[ ]` in ephemeral: no-op (ephemeral hasn't completed it).
- If ID exists in ephemeral but not in master: ERROR — ID-stability violation.
- If ID was renumbered (sequence gap, tombstone shifted): ERROR — ID-stability violation.

### Step 4 — Stage Deferred lines

Stage every `- ISC-N: [DEFERRED-VERIFY] — …` line from the ephemeral — otherwise master would show an open ISC with no record of why. Ignore the ephemeral's evidence lines (they are not proof in master) and any `Goal:` / `Ask N:` line (those belong to the master ISA at close).

### Step 5 — Stage Decisions entries

Append the ephemeral's **new** `## Decisions` entries to master's `## Decisions`, prefixed with `[from <feature>]:` for traceability. Preserve timestamps. Skip any row that master already contains when compared *without* the prefix — Scaffold copied some master Decisions into the slice as context, and those are not new decisions.

### Step 6 — Stage Changelog entries

If the ephemeral has any new `## Changelog` entries (conjecture/refutation/learning format), append them to master's `## Changelog` with a feature-context note: `[surfaced in <feature>]:`.

### Step 7 — Apply or dry-run

If `dry_run: true`, emit the YAML output and stop.

If `dry_run: false`, apply the staged entries via Edit (never a shell command on the ISA). Before appending any Deferred, Decisions, or Changelog entry, skip it if master already contains it verbatim (including its `[from <feature>]:` / `[surfaced in <feature>]:` prefix) — this is what makes a retry after a partial merge safe. Order:
1. Edit master `## Decisions` (append).
2. Edit master `## Changelog` (append).
3. Edit master `## Verification` (append the Deferred lines).

### Step 8 — Prove the claims in master

Run `isa verify <master_path> <claimed ISC IDs>`. The engine runs each probe from the master's `root`, ticks what passes (in Feature dependency order), writes the evidence lines, recomputes `progress` and syncs nested parents. Record `proven` and `failed` from its output. A failed claim stays `[ ]` — report it; the worker's tick was not evidence.

Red baselines: if the worker ran `isa verify --red <master_path> ISC-N` before building, those red rows count here; otherwise behaviour/http/schema ISCs are ticked `(no red baseline)` and listed at close.

### Step 9 — Archive the ephemeral file

`mv <ephemeral_path> <ephemeral_dir>/.archive/<feature>-<YYYY-MM-DD>.md`. The archive is permanent — useful for forensics, never deleted.

### Step 10 — Emit the report

Output the YAML report. The caller consumes this to know the merge happened.

## Conflict resolution

Reconcile is **deterministic** — there are no conflicts to resolve. Either an ISC ID exists in master and the merge is mechanical, or it doesn't and the merge aborts with an error.

If the ephemeral made structural ISC changes (split ISC-7 into ISC-7.1 / ISC-7.2), those changes belong in master via a separate Edit by the user before Reconcile runs. Reconcile does not invent IDs.

If the ephemeral and master have diverged structurally (ephemeral is stale relative to master), abort and surface the divergence. The user must decide whether to re-extract a fresh ephemeral or back-port master changes manually.

## Failure modes

- **ID-stability violation:** ephemeral references ISC-N that doesn't exist in master. Abort. Do not silently drop the entry. Master is the source of truth; ephemeral cannot mint IDs.
- **Missing canonical header on ephemeral:** abort. Reconcile only operates on files Scaffold produced.
- **A claim fails in master:** not an abort — the probe is the judge. Report it under `failed`; the ISC stays open for the next loop.
- **Master ISA modified during the merge:** Reconcile is single-threaded by design; `isa verify` rewrites the master, so re-read it before any further edit.

## Idempotency

Reconcile is idempotent by design. Appended entries are skipped when master already contains them verbatim (Step 7), and `isa verify` on an already-ticked ISC just re-proves it. So re-running on the same ephemeral — e.g., after a merge that stopped before Step 9 archived it — adds no entries. Safe to retry.
