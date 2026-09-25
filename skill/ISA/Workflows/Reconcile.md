# Reconcile Workflow

Deterministic merge of an ephemeral feature-file excerpt back into the master ISA, keyed on stable ISC IDs. The cornerstone of the parallel-worker pattern — without this, ephemeral feature work drifts from master and creates the same "code drifts from spec" problem the ISA is meant to solve.

## When to invoke

- A feature-context agent (subagent, worktree worker, parallel coding-agent instance) finishes work on an ephemeral feature file.
- The work loop at LEARN: `Skill("ISA", "reconcile <ephemeral-path> → <master-path>")`
- User directly: `Skill("ISA", "reconcile <ephemeral-path> → <master-path>")`

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| ephemeral_path | yes | Path to the ephemeral feature file (`~/.isa/<project>/{slug}/_ephemeral/<feature>.md`) |
| master_path | yes | Path to the master ISA the ephemeral was derived from |
| dry_run | no | Default false. If true, report planned changes without writing. |

## Output

```yaml
status: applied | dry_run | aborted
ephemeral: <path>
master: <path>
applied:
  iscs_checked: [ISC-12, ISC-13, ISC-14, ISC-15, ISC-31]   # ISCs flipped to [x]
  verification_added: 5                                     # Verification entries appended
  deferred_added: 1                                         # [DEFERRED-VERIFY] lines carried over (no flip)
  decisions_added: 2                                        # Decisions entries appended
  changelog_added: 1                                        # Changelog entries appended
archived_to: ~/.isa/<project>/.../_ephemeral/.archive/AuthSystem-2026-04-15.md
errors:
  - isc: ISC-99
    reason: not present in master — ephemeral references unknown ID
```

## Procedure

### Step 2 — Read both files

Load ephemeral and master. Confirm ephemeral has the canonical header marker (`<!-- EPHEMERAL FEATURE FILE — derived from ... -->`); abort if not (refusing to merge anything that didn't come from Scaffold's ephemeral mode).

### Step 3 — Build the ISC ID merge plan

For each ISC in the ephemeral file:
- If `[x]` in ephemeral and `[ ]` in master: stage flip in master.
- If `[x]` in both: no-op.
- If `[ ]` in ephemeral: no-op (ephemeral hasn't completed it).
- If ID exists in ephemeral but not in master: ERROR — ID-stability violation.
- If ID was renumbered (sequence gap, tombstone shifted): ERROR — ID-stability violation.

### Step 4 — Stage Verification entries

Each ISC flipped in step 3 must have a corresponding entry in the ephemeral's `## Verification` section. Stage these entries to be appended to master's `## Verification`. Preserve quoted command output / file content / screenshot paths verbatim.

Also stage every `- ISC-N: [DEFERRED-VERIFY] — …` line from the ephemeral, even though its ISC did not flip — otherwise master would show an open ISC with no record of why. Deferred lines never flip a checkbox. Ignore any `Goal:` line in the ephemeral: the Goal check belongs to the master ISA at close.

### Step 5 — Stage Decisions entries

Append the ephemeral's **new** `## Decisions` entries to master's `## Decisions`, prefixed with `[from <feature>]:` for traceability. Preserve timestamps. Skip any row that master already contains when compared *without* the prefix — Scaffold copied some master Decisions into the slice as context, and those are not new decisions.

### Step 6 — Stage Changelog entries

If the ephemeral has any new `## Changelog` entries (conjecture/refutation/learning format), append them to master's `## Changelog` with a feature-context note: `[surfaced in <feature>]:`.

### Step 7 — Update master frontmatter

- `progress: M/N` recomputed per `References/IsaFormat.md` § Field Rules (leaf ISCs; dropped and waived excluded from N).
- `updated: <ISO-8601>` set to now.
- Nested parents whose leaves are now all `[x]` are ticked.
- `phase`: leave alone unless every non-dropped, non-waived leaf ISC is `[x]`, in which case set to `verify` (LEARN/complete is the caller's transition, not Reconcile's).

### Step 8 — Apply or dry-run

If `dry_run: true`, emit the YAML output and stop.

If `dry_run: false`, apply all staged changes via Edit/Write tools. Before appending any Verification, Deferred, Decisions, or Changelog entry, skip it if master already contains it verbatim (including its `[from <feature>]:` / `[surfaced in <feature>]:` prefix) — this is what makes a retry after a partial merge safe. Order:
1. Edit master ISA frontmatter.
2. Edit master ISC checkmarks in `## Criteria` / `## Bridge Criteria`.
3. Edit master `## Verification` (append).
4. Edit master `## Decisions` (append).
5. Edit master `## Changelog` (append).

### Step 9 — Archive the ephemeral file

`mv <ephemeral_path> <ephemeral_dir>/.archive/<feature>-<YYYY-MM-DD>.md`. The archive is permanent — useful for forensics, never deleted.

### Step 10 — Emit the report

Output the YAML report. The caller consumes this to know the merge happened.

## Conflict resolution

Reconcile is **deterministic** — there are no conflicts to resolve. Either an ISC ID exists in master and the merge is mechanical, or it doesn't and the merge aborts with an error.

If the ephemeral made structural ISC changes (split ISC-7 into ISC-7.1 / ISC-7.2), those changes belong in master via a separate Edit by the user before Reconcile runs. Reconcile does not invent IDs; it only flips checkmarks on existing ones.

If the ephemeral and master have diverged structurally (ephemeral is stale relative to master), abort and surface the divergence. The user must decide whether to re-extract a fresh ephemeral or back-port master changes manually.

## Failure modes

- **ID-stability violation:** ephemeral references ISC-N that doesn't exist in master. Abort. Do not silently drop the entry. Master is the source of truth; ephemeral cannot mint IDs.
- **Missing canonical header on ephemeral:** abort. Reconcile only operates on files Scaffold produced.
- **Verification entry missing for a flipped ISC:** soft warning. The flip is valid (ephemeral worker decided to mark it done), but the absence of evidence violates the no-close-without-evidence rule. Surface in the report; let the VERIFY pass catch it.
- **Master ISA modified during the merge:** Reconcile is single-threaded by design. If concurrent edits happen, the second Reconcile sees a different state and may report "ISC already checked" — that's correct behavior.

## Idempotency

Reconcile is idempotent by design. Checkmarks can't double-flip (an ISC already `[x]` is a no-op), and appended entries are skipped when master already contains them verbatim (Step 8). So re-running on the same ephemeral — e.g., after a merge that stopped before Step 9 archived it — produces no further changes and reports zero applied. Safe to retry.
