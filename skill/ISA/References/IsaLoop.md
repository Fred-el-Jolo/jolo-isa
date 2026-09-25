---
version: 8.4.0-export.1
---

# The ISA Loop

One loop: move a thing from its current state to its ideal state by climbing a hill we define as we climb it. The ISA is the hill and the instrument at once — it states the ideal state as claims (ISCs), each naming the tool probe that would falsify it, so the spec IS the test suite and evidence is altitude. Without tool evidence there is no up or down.

The target is the user getting exactly the output they wanted, in the right amount of time, for the right amount of effort. Spend scales with what the work reveals: trivial work finishes in seconds with a Goal + Criteria ISA or none at all; hard work earns deeper ISAs, parallel workers, and independent review. The user's explicit call ("quick pass", "go deep") outranks judgment.

## Phases

`observe → think → plan → build → execute → verify → learn → complete` — the values of the `phase:` frontmatter field. They are labels for where the work is, not ceremony: write `phase:` at the start, whenever it genuinely changes, and `complete` at close.

| When | ISA skill call |
|------|----------------|
| Start (observe) | `Scaffold` — or read the existing ISA when continuing the same task |
| End of articulation | `CheckCompleteness` at the chosen tier, `moment: articulation` |
| E5, before building | `Interview` |
| Planning parallel work | `Scaffold` ephemeral mode, one slice per worker |
| Any decision, dead end, or changed belief | `Append` (Decision / Changelog) |
| Each ISC passes | `Append` (Verification) — flips the box, updates `progress` |
| Worker finishes | `Reconcile` |
| Before `complete` | `Append` the `Goal:` verification line (and `no belief refuted this run` at E4+ if the Changelog is empty), then `CheckCompleteness` with `moment: close` |

## A run is complete when

1. **The stated goal survives verbatim** in `stated_goal` (immutable unless the user explicitly revises it; `null` only when the literal is contentless), and every claim traces to it or a named derived claim. Optimize for its intent, not its surface. **At close, the goal itself is checked:** re-read the verbatim goal against the finished result and write `- Goal: yes|no — <evidence>` in `## Verification`; `no` blocks `complete`. This is the frame-drift check — every ISC passing does not prove the ISC *set* still covers what was asked.
2. **Done existed in writing before building** — an ISA at `~/.claude/isa/{slug}/ISA.md`, claims each naming the probe that would falsify them. A trivial task may write a minimal Goal + Criteria ISA.
3. **What must not happen is written down** — at least one `Anti:` claim.
4. **Experiential goals name an antecedent** — at least one `Antecedent:` claim.
5. **External prerequisites were probed before execution** — tokens, logins, service config, deploy targets. Missing ones blocked or were deferred with a Decisions row.
6. **Material ambiguity was resolved before building** — up to 3 targeted questions when the answer changes what gets built, or a one-line ambiguity flag when a reasoned default is safe. A whole-response `proceed` accepts the defaults.
7. **A reported bug was reproduced before its suspect code was read.**
8. **No claim closed without tool evidence of the right modality** in the same or next tool call: file→Read, code→Grep, command→checked output, HTTP→`curl -i`, deploy→live probe, appearance→an image actually viewed, schema→query, config→read-back. "Should work" is forbidden. `[DEFERRED-VERIFY]` (format in `IsaFormat.md` § Verification) is a holding state that blocks `complete` unless the user waives it.
9. **A defect that is an instance of a class** did not close until one search enumerated every sibling, each fixed-and-verified or tombstoned.
10. **Every explicit ask in the user's message** was met, skipped with a stated reason, or surfaced; no claim passed because its wording was softened mid-run.
11. **The builder never rubber-stamped its own build** — for high-blast work, an independent second look (fresh-context reviewer) ran, or a Decisions row says why not. Its contradictions were surfaced, never silently resolved.
12. **The run left its trail in the ISA** — decisions including dead ends; conjectured/refuted-by/learned/criterion-now entries when understanding changed; evidence quoted per claim. (Harvesting reusable learnings out of a finished ISA is a separate memory system — planned, not built.)
13. **State was observable without asking** — `phase:` and `progress:` in frontmatter are true at all times.
14. **The ISA at close is not the ISA at open** — every discovery (corrections, failed probes, new constraints, implied wants) was folded in as it arrived: claims added, split, tightened, or killed.
15. **The spend matched the task** — depth, parallelism, and time scaled to the difficulty the work revealed; breaks in either direction were surfaced.

## Standing questions (ask them when the event happens)

| When | Ask |
|---|---|
| Deep into a session with no ISA | Still trivial, or does done need writing down? |
| A probe or test fails | Claim wrong or code wrong? If the claim, update the ISA. |
| The user messages mid-run | Does this revise the goal, kill a claim, or add one? |
| Research or a subagent returns | Anything here the ISA doesn't know yet? |
| A claim closes | Did closing it reveal a neighbor or a class? |
| Long stretch with no ISA edits | Is the ISA still the true shape of done? |
| Deep into a run, claims still open | Escalate, descope, or surface? |

(These are the model's own discipline; a hook could fire them automatically later.)

## Resume

- Editing the body of a `phase: complete` ISA reopens it: `phase: learn`, `iteration+1`, `resumed_at`, Decisions row. `frozen: true` bypasses.
- After compaction or in a new session: read the ISA, continue from its state, never redo gates that already passed.
