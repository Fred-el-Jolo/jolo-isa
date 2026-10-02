---
version: 8.4.0-export.2
---

# The ISA Loop

One loop: move a thing from its current state to its ideal state by climbing a hill we define as we climb it. The ISA is the hill and the instrument at once — it states the ideal state as claims (ISCs), each naming the tool probe that would falsify it, so the spec IS the test suite and evidence is altitude. Without tool evidence there is no up or down.

The target is the user getting exactly the output they wanted, in the right amount of time, for the right amount of effort. Spend scales with what the work reveals: trivial work finishes in seconds with a Goal + Criteria ISA; hard work earns deeper ISAs, parallel workers, and independent review. The user's explicit call ("quick pass", "go deep") outranks judgment.

**What "a run is complete" means is `SKILL.md` § Completion rules** — the fifteen numbered rules, each with how it is enforced (HOOK / CHECK / SHAPE / SELF). This file describes the loop around them.

## Phases

`observe → think → plan → build → execute → verify → learn → complete` — the values of the `phase:` frontmatter field. They are labels for where the work is, not ceremony: write `phase:` at the start and whenever it genuinely changes; `isa close` writes `complete`.

| When | Call |
|------|------|
| Start (observe) | `isa new <slug> --goal "<span>"`, then `Scaffold` — or read the existing ISA when continuing the same task |
| End of articulation | `isa lint <ISA>`, and `CheckCompleteness` at the chosen tier (`moment: articulation`) for the judgment parts |
| E5, before building | `Interview` |
| Planning parallel work | `Scaffold` ephemeral mode, one slice per worker |
| Before building a behaviour/http/schema claim | write its test, then `isa verify --red <ISA>` (it must fail) |
| Any decision, dead end, or changed belief | `Append` (Decision / Changelog) |
| A claim can pass | `isa verify <ISA> ISC-N` — it runs the probe, ticks what passed, writes the evidence line (`--attest "<evidence>"` for manual / screenshot / eval) |
| Worker finishes | `Reconcile`, then `isa verify <master>` |
| Before `complete` | `Append` the `- Ask N:` lines and the `Goal:` line (and `no belief refuted this run` at E4+ if the Changelog is empty), then `isa close <ISA>` — it re-runs every probe and closes only when all pass |

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

(The hooks ask two of them for you: a failed `isa verify` probe, and five project changes without an ISA edit.)

## Resume

- Editing the body of a `phase: complete` ISA reopens it: `phase: learn`, `iteration+1`, `resumed_at`, Decisions row. `frozen: true` bypasses. It closes again through `isa close`.
- After compaction or in a new session: read the ISA, continue from its state, never redo gates that already passed. Items still blocked from an earlier turn are shown at session start; fix them, and `isa verify` / `isa lint` clear them.
