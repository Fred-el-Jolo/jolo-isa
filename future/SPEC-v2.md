# ISA v2 — design spec

Status: **implemented (M1–M7, 2026-10-02)** on branch `spec-v2-review`; **§ 11 revision (judge-free baseline, Jev on by default) specified, not implemented (M8–M10)**; the live whole-flow run `flow/20261002-125119` on `eval-results` passed 14/14 stages. It comes out of the 2026-10-01 eval session: batch
`20261001-202941` on branch `eval-results`, and the reviews of runs A (review, no ISA) and B (bug fix,
closed ISA). Each section says what changes, the exact behaviour, where it lives (hook / engine /
command / skill), how it fails, and how it is tested. § Milestones orders the work.
It folds in six review rounds (2026-10-01/02); their choices are listed under § Decisions.

## 0. Principles

1. **Iron law.** Every piece of work with a checkable end state gets an ISA. Only work the gate
   question answers NO for is exempt, plus an explicit user opt-out (§ 1.6). "Read-only" is no longer
   a category.
2. **The model owns the content, the engine owns the state.** The model writes prose and criteria
   with Write/Edit. Ticks, generated Verification lines, `progress`, `phase: complete`, `root:` and
   the ledger (including `blocked` rows, § 4.5) are written only by `isa` commands (§ 3).
3. **Hooks never run probes and never write the ISA.** Hooks read the ISA, the ledger and the session
   state, then allow, refuse or add context. Probes run only inside `isa verify` / `isa close`, which
   the model calls. Hooks may append rows to the ledger and session state, never to `ISA.md`.
4. **One model call in the hook path:** the gate question (§ 1). Every other hook decision stays
   deterministic. Other judge uses (§ 7) run inside commands, never inside hooks.
5. **Fail toward ON.** If the gate can't decide, the session is ON. A silent OFF is the worse
   mistake under the iron law.
6. **Hooks fail open.** An engine crash still lets the tool call through, with a visible message
   (unchanged from v1). The difference: a judge *error* counts as an ON verdict, not as no decision.

---

## 1. ISA mode: the per-prompt gate

### 1.1 Gate question

> **Is this a request for work with a checkable end state — something that will be either done or not
> done — rather than a question or a conversation?**

Answer: `yes` or `no`, plus a one-line reason. Examples:

| Prompt | Verdict |
|---|---|
| "Review utils.py for bugs and list each one with its line number." | yes (done = every function checked, every bug listed) |
| "test_dates.py is failing. Fix the bug…" | yes |
| "make the report faster" | yes (ambiguous scope, still an end state) |
| "why is the build slow?" / "find out why test_dates fails" | yes (an investigation of the user's own system: done = cause found with evidence) |
| "what does `is_leap` do?" | no |
| "thanks, looks good" / "hi" | no |
| "explain the difference between X and Y" / "how does git rebase work?" | no (general knowledge, or code explained as written) |
| "write a plan for X" / "compare A and B and recommend one" | yes (the deliverable can be checked) |

### 1.2 Judge pipeline (UserPromptSubmit / pi `before_agent_start`)

1. **Pre-filter (`fit.py`, free, deterministic).** It returns `yes`, `no` or `unsure`:
   - `no` for greetings and thanks ("hi", "thanks, looks good");
   - `unsure` for short affirmatives ("go", "ok do it", "yes", "fix these"): they usually authorise
     work proposed in the turn before, which only the judge, with context, can see;
   - `yes` for prompts with explicit work verbs plus an object (fix, add, implement, refactor, write,
     review, migrate, deploy…), or an explicit ISA mention. These skip the judge (a false YES is the
     accepted cost, § 1.7);
   - `unsure` for everything else.

   The rules apply in this order: greeting/thanks → `no`, short affirmative → `unsure`, work verb →
   `yes`. So "fix these" is `unsure` (judged with context), not `yes`.
2. **Judge call**, only when the pre-filter says `unsure` and the session is OFF, or ON with its bound
   ISA `complete` (§ 1.3). An ON session with an open ISA is never re-judged. No verdict cache: the
   same prompt rarely repeats within one OFF session, and a repeated "ok" may mean something else
   each time, since its context changes.
3. **The verdict is recorded** in session state and in `~/.isa/_state/judge.jsonl`:
   `{t, harness, session, prompt_id, source: prefilter|judge|override|error, verdict, reason, ms}`.

`ISA_JUDGE` selects the backend:

| Value | Call | Notes |
|---|---|---|
| `auto` (default) | `claude` in Claude Code sessions, `pi` in pi sessions; `heuristic` if that CLI is missing | `auto` never picks `api`: a key in the environment is not consent to bill it from every session |
| `api[:model]` | Messages API over stdlib `urllib`, model `claude-haiku-4-5-20251001`, structured JSON output, no tools; needs `ANTHROPIC_API_KEY` | Opt-in only. Avoids a CLI cold start (~1 s instead of several) |
| `claude[:model]` | `claude -p --model claude-haiku-4-5-20251001 --output-format json --json-schema '<verdict schema>' --tools "" --setting-sources project --strict-mcp-config --disable-slash-commands --no-session-persistence`, prompt on stdin, cwd = an empty temp dir, env `ENABLE_CLAUDEAI_MCP_SERVERS=false ISA_JUDGE_CHILD=1` | Same isolation as the eval runner |
| `pi[:provider/model]` | `pi -p --mode json --no-session --no-extensions --no-skills --no-context-files --no-tools --model <model> -- <prompt>`, env `ISA_JUDGE_CHILD=1` | Model from `ISA_JUDGE_PI_MODEL` |
| `heuristic` | Pre-filter only; `unsure` → `yes` | Offline / CI |
| `jev` | Later (see `future/JEV.md`) | Same interface |

The judge prompt is a fixed template, `runtime/isa/gate.md`: the question, the examples table, the
tail of the previous assistant message (last 2,000 chars), the user's prompt, and "Answer with JSON
{verdict, reason}". The context is what lets "go" after a proposed review be judged `yes`. Claude
Code: read from the hook input's `transcript_path`; pi: from the session messages the extension
passes in. Missing context (first prompt, unreadable transcript) → the prompt alone. `asks_extract`
(§ 7) gets the same context, so asks proposed by the assistant and confirmed by "go" are extracted.

**Recursion guard:** when `ISA_JUDGE_CHILD=1`, every engine event returns `{}` immediately, so the
judge's own session runs no ISA hook.

**Time limit:** judge timeout `ISA_JUDGE_TIMEOUT` (default 12 s). Timeout, a non-zero exit or
unparseable output → verdict `yes`, source `error` (fail toward ON). The harness limits must exceed
it, or the harness kills the engine and the session silently stays OFF:
- Claude Code: the installer raises the `UserPromptSubmit` hook timeout to 20 s; the other hooks stay
  at 15 s.
- pi: the adapter gives the `prompt` engine call its own limit, `ISA_PROMPT_TIMEOUT_MS` (default
  20000); every other event keeps `ISA_HOOK_TIMEOUT_MS` (default 5000). The call is synchronous
  (`spawnSync`), so pi's UI waits for the judge; `ms` in `judge.jsonl` measures that cost.

**Background gate — decided at M7: stay synchronous.** Times measured on 2026-10-02 from the `ms` field of `judge.jsonl` (`claude` backend, Haiku 4.5):

| Prompts | How the gate answered | Time |
|---|---|---|
| Clear work requests, e.g. the flow's YES prompt ("Add two things to todo.py…") or "review utils.py for bugs" | pre-filter | 0 ms |
| "go" (with context), "sounds good", "why is the build slow?", "can you compare … and pick one?", "what does cmd_list print?" | judge, 5 direct calls | 4.1–7.6 s, median 6.2 s |
| The flow's NO question | judge, live flow runs | 6.9 s and 4.2 s |

The wait happens only on prompts the pre-filter can't settle, which are mostly questions and short approvals, and it stays well under the 12 s judge timeout and the 20 s hook limit. A background judge would save that wait, but its verdict would arrive after the prompt. On a `yes` the ON block would then reach the model only at its first PreToolUse refusal or at Stop, which is exactly the run-A failure this spec fixes (a review that never sees the protocol). Revisit if the median rises above about 8 s, or if a cheaper backend (`api`) becomes the default.

### 1.3 State machine

Stored in the session file: `mode: off|on`, `mode_reason`, `mode_since`, `mode_source`.

```
            prompt verdict yes ─────────────┐
 (new) OFF ─┤                               ▼
            prompt verdict no → stays OFF   ON  (sticky for the rest of the session)
            write call while OFF ──────────▶ ON  (the call is refused, see 1.4)
            unknown call that changed files ▶ ON  (detected after it ran, see 1.4)
```

- **OFF → ON** on a `yes` verdict; on a `write` call made while OFF (the gate misjudged; the change
  itself is evidence); on an `unknown` call that, once it ran, turns out to have changed project
  files (`mode_source: change`); or when an ISA is bound (`mode_source: binding`): a session with a
  bound open ISA is always ON, so a model that wrote its ISA unprompted is not refused as if it had
  none. An `unknown` call that changed nothing leaves the session OFF: `unknown` means "can't tell",
  not "changed". Other `isa-cmd` calls (§ 3.3) never switch the mode.
- **ON is sticky:** a session never goes back to OFF. A new session starts OFF and undecided.
- **A finished task doesn't end the gate.** While the bound ISA is `complete`,
  new prompts are judged again (pre-filter, then judge on `unsure`). A `yes` records
  `needs_isa_since: <prompt_id>`, and Stop then treats the session as having no ISA until an ISA is
  bound, or the complete one reopened, after that prompt. Without this, a second review in a session
  whose first ISA closed would escape the gate (run A again).
- **Compaction or a resumed session** keeps the stored mode. A session file with no `mode` (written by
  v1, e.g. a session running during the upgrade) reads as ON when it has an open bound ISA, and as OFF
  otherwise.

### 1.4 What each event does in each mode

| Event | OFF | ON |
|---|---|---|
| SessionStart | Injects nothing (mode undecided) | Re-injects the ON block plus the bound ISA status and its open `blocked` items (resume / compaction) |
| UserPromptSubmit | Runs the gate. NO: user sees `ISA: OFF — <reason>`; model context gets nothing. YES: switch ON, user sees `ISA: ON — <reason>`, model gets the **ON block** | Status line of the bound ISA, or "no ISA bound yet". Bound ISA `complete`: runs the gate again (§ 1.3); YES → "new task: new ISA, or reopen" |
| PreToolUse, read / `isa-cmd` | allow | allow (`isa verify` / `isa close` refuse their own probes before articulation, § 3.2) |
| PreToolUse, write | **Switch ON**, refuse: "ISA: ON — this change needs an ISA first." plus the ON block | v1 gate: needs a bound ISA that passes articulation; plus the ownership rules (§ 3.3) |
| PreToolUse, unknown | Allow, taking v1's change snapshot (`changes.py`) | v1 gate, as for write |
| PostToolUse | `unknown` that changed project files → switch ON (`mode_source: change`); Stop then requires an ISA for the turn. Otherwise nothing | v1: lint feedback, nudges; binding and mtime refresh for `isa-cmd` (§ 3.3); tick feedback replaced by the runner (§ 4) |
| Stop | nothing | v1 checks, **plus: no bound ISA (or `needs_isa_since` unmet, § 1.3) → refuse to end the turn once, whether or not anything changed** (fixes run A) |

The Stop no-ISA check runs before the "nothing happened this turn" early return in `_stop`, since a
review turn changes nothing. Its refusal text gives the model two exits:

> No ISA yet. Write it now (`isa new <slug> --goal "<span>"`, then Goal, Criteria, Test Strategy).
> If you are asking the user to clarify before you can define done, run `isa new`, write the Goal and
> your questions under Decisions, and set `context_sufficient: false` — that is enough to end the turn.

Lint accepts such a scaffold (`phase: observe`, `context_sufficient: false`, a Goal, at least one
question — a Decisions line ending in `?` — no Criteria yet) at Stop
**only on the turn that created the ISA**: the session records the `prompt_id` at binding, and a
Stop on any later prompt with the ISA still in that shape is refused like a missing ISA. Otherwise a
review could end every turn on a token question, which is run A again. The articulation gate still
guards the first project change. Like every Stop refusal, it fires once per prompt.

So an unknown call while OFF runs: a question answered by running code (`python3 -c …`, `pytest`)
stays a question. Only an observed change flips the session, and then the change is already made,
so the ISA comes after it: Stop refuses to end that turn without one, as for any change with no ISA.

User-visible lines go through `systemMessage` in Claude Code and `ctx.ui.notify` in pi.

### 1.5 OFF block / ON block

**OFF block:** empty. In OFF mode the model sees nothing from the ISA system.

**ON block** (`runtime/isa/protocol.md`, rewritten, ~12 lines; `{…}` are filled in):

```
[ISA: ON — this prompt asks for work with a checkable end state]
Before any change, write the ISA for this task. Read {skill_dir}/SKILL.md first (the contract and
the numbered completion rules), then:
1. `isa new <slug> --goal "<verbatim span of the prompt>"` — creates {project_dir}/<stamp>_<slug>/ISA.md
   with frontmatter, stated_goal, asks and root filled, and binds it to this session.
2. Write Goal, Criteria (≥1 `Anti:`), Test Strategy with Write/Edit — never with shell commands.
3. `isa lint <ISA>` until clean; changes are refused until it is.
4. For behaviour/http/schema criteria, write the test and run `isa verify --red <ISA>` (it must
   fail) before building. Prove criteria with
   `isa verify <ISA> [ISC-N…]` — it runs the probes and ticks what passed. Self-attested criteria:
   `isa verify <ISA> ISC-N --attest "<evidence>"`. You never tick boxes yourself.
5. Finish with `isa close <ISA>` — it re-proves everything and closes. Your final answer quotes its summary.
The turn can't end without a bound ISA, and can't end with an unproven claim.
```

The v1 bullets that move into SKILL.md: continuation vs new task, folding in discoveries,
`stated_goal` rules, Feature order, "you cannot exempt yourself". The v1 bullet that made read-only
work a special case is **deleted**, and its counterpart in `fit.md` / `fit.py` advice is deleted too.

### 1.6 Explicit opt-out (the "very specific cases")

- `ISA_MODE=off` in the environment: the user disables the system for a session. Recorded as
  `mode_source: override`.
- `ISA_MODE=on`: forces ON from the first prompt (e.g. the eval harness).
- `ISA_MODE=auto` (default): the gate decides.
- The model can't change the mode. A user prompt saying "skip the ISA" goes through the gate like any
  other prompt.

### 1.7 Failure modes

| Failure | Behaviour |
|---|---|
| Judge CLI missing | `heuristic`, logged once per session |
| Judge slow / errors | `yes` (ON), `source: error`, user sees `ISA: ON — judge unavailable (<why>)` |
| Harness kills the engine before the judge returns | Prevented by the limits in § 1.2; a kill is logged by the adapter as a hook error |
| False NO | The first mutation switches ON. Only answers with no change at all escape; the judge log makes those measurable in evals |
| False YES | The cost is an ISA for a small task (E1 is a minute of work), or one Stop refusal on a question turn. Accepted |

---

## 2. Skill and rules on the model's path

1. **SKILL.md gets a "Completion rules" section** right after Frontmatter: the 15 rules below,
   numbered, each with its enforcement level (teeth). `References/IsaLoop.md` keeps the loop prose
   and the standing questions, and points back to that section instead of duplicating it.
2. Fix the bug "Close … when all three hold" (four items are listed): it becomes "all four hold",
   and item 4 becomes "`isa close` succeeded" (it re-proves every probe).
3. The ON block names SKILL.md as the file to read first; SKILL.md names `isa new`, `lint`,
   `verify` (with `--red` and `--attest`) and `close` in Lifecycle.

Teeth: **HOOK** = refused mechanically by a hook or a command · **CHECK** = a gate a command runs and
records, on facts it can verify · **SHAPE** = a command requires a row in the right format, but can't
check that it's true · **SELF** = honest self-attestation, listed to the user at close.

| # | Rule (short form; full text goes in SKILL.md) | Teeth in v2 | Restored detail (lost in the v1 export) |
|---|---|---|---|
| 1 | The stated goal survives verbatim; every claim traces to it; at close `Goal: yes\|no` is written and `no` blocks | HOOK (`isa new --goal` checks the span, lint checks it) + CHECK (`isa close` requires `Goal: yes`; judge advisory, § 7) | — |
| 2 | Done existed in writing before building | HOOK (gate) | — |
| 3 | ≥1 `Anti:` claim | HOOK (lint) | — |
| 4 | Experiential goals name an `Antecedent:` | SELF | — |
| 5 | External prerequisites probed before execution; missing → blocked or deferred in Decisions | SELF | — |
| 6 | Material ambiguity resolved before building (≤3 questions, or a stated reasoned default); `context_sufficient` set | CHECK (lint at articulation: E2+ requires `context_sufficient: true` before the first change) | — |
| 7 | A reported bug is reproduced before its suspect code is read; the fix goes upstream when one fix kills the class | SELF + bypass row | Bypass row `repro-bypass: pure-additive \| non-isolable \| repro would cause damage — <why>` in Decisions |
| 8 | No claim closes without tool evidence of the right type | HOOK (runner ticks, § 4) + CHECK (`kind:` rules and downgrade check, § 6); the `kind:` choice itself is SELF at articulation until `probe_adequacy` (§ 7) | Type list incl. web/UI → real browser or HTTP probe, appearance → image viewed, motion → frame scrub |
| 9 | A defect that is an instance of a class closes only after one search enumerated every sibling | SHAPE + SELF | Decisions line `class-sweep: <class> — N siblings via <probe>; M fixed, K tombstoned`; `isa close` requires it when an ISC is tagged `class:` |
| 10 | Every explicit ask was met, skipped with a reason, or surfaced; scope narrowed only when ratified; no claim softened mid-run; a depth directive is an ask | SHAPE + SELF (`isa close` requires one `- Ask N:` line per entry in `asks:`) | `asks:` frontmatter list (extracted by `isa new`, § 3.2) + `- Ask N: met\|skipped — <why>\|surfaced` lines; a missing line is unmet → close refused |
| 11 | The builder never rubber-stamps its own build: high-blast work gets an independent second look or a row saying why not; contradictions surfaced (two re-calls, then escalate); findings dispositioned | SHAPE + SELF (§ 6.3) | `risk: high` or E4+ triggers it; `second-look:` row; findings `adopted (diff) \| rebutted (reason) \| deferred (task)` |
| 12 | The run left its trail: decisions incl. dead ends; C/R/L Changelog when understanding changed | SHAPE + SELF (lint shape at E4+) | — |
| 13 | State observable: `phase`, `progress` true at all times | HOOK (engine writes and recomputes `progress` and `complete`) | — |
| 14 | The ISA at close is not the ISA at open: discoveries folded in as they arrived | SELF + nudge | Falsifier stated: "failed probes or user corrections in the transcript with zero ISA edits after them"; the nudge fires on a failed `isa verify` with no ISA edit before the next change |
| 15 | Spend matched the task; breaks in either direction surfaced; a depth directive with no visible effect is a break | SELF | — |

**Close contract** (restored): the final answer quotes the `isa close` summary (claims closed and on
what evidence, self-attested claims, deferred claims, open asks) instead of paraphrasing it.

**Always-on nudges** (restored, in the ON block or PostToolUse): "a skill matches this prompt → use
it" is out of scope (it depends on the harness). "Depth directive with no ISA" is covered by the
gate.

---

## 3. Commands and ownership

### 3.1 Ownership

| Part of ISA.md | Model-owned | Engine-owned |
|---|---|---|
| Body sections Problem … Decisions, Changelog | ✔ (Write/Edit) | |
| Criteria lines: text, adding, splitting, dropping (tombstones) | ✔ | |
| Criteria checkbox `[ ]` → `[x]` | | ✔ `isa verify` (incl. `--attest`); nested parents by any engine write |
| Criteria checkbox `[x]` → `[ ]` (untick, honest regression) | ✔ allowed | |
| Test Strategy entries | ✔ (a `type`/`kind` downgrade is checked, § 6.4) | |
| Generated `## Verification` ISC lines (`verified` / `attested` / `regressed`) | | ✔ from the ledger |
| `## Verification` `[DEFERRED-VERIFY]` lines | ✔ | |
| `## Verification` `- Goal:` and `- Ask N:` lines | ✔ (judgment), checked by `isa close` | |
| Frontmatter `task`, `effort`, `phase` (any value except `complete`), `context_sufficient`, `interview_*`, `iteration`, `resumed_at`, `frozen` | ✔ | |
| Frontmatter `asks` | additions ✔; a removal needs a `refined:` Decisions row | ✔ extracted at creation |
| Frontmatter `slug`, `started`, `stated_goal` (+ `_source`) | written by `isa new`; afterwards edited only on an explicit user revision (lint checks the logged prompt) | ✔ at creation |
| Frontmatter `progress`, `phase: complete`, `root` | | ✔ |
| Frontmatter `updated` | either | either |
| `~/.isa/_state/**` (ledger incl. `blocked` rows, sessions, judge log) | | ✔ (v1 rule kept) |

`updated` is not checked: the engine sets it on its own writes and the model may set it. Making it
engine-owned would need a hook writing the ISA after every model edit (§ 0.3).

**Engine-owned fields never make the model stuck.** The model may add, split, drop or untick ISCs,
which changes the right `progress` value and can orphan a generated Verification line it may not edit.
So a stale `progress` or an orphaned generated line is never a model-facing lint error: `isa lint`,
`isa verify` and `isa close` each recompute `progress` and drop orphaned generated Verification lines
(the ISC was dropped, unticked by the model, or renumbered) before they check anything.

The hooks call the same lint, but never write (§ 0.3). The **hook-side lint** (PreToolUse gate,
PostToolUse feedback, Stop) suppresses the `progress` and orphaned-line errors instead of fixing them,
and writes nothing; the next `isa` command fixes the file. So `progress` in the file can lag between
commands: status readers (`isa status`, a status line) compute it from the Criteria themselves, and
rule 13's "true at all times" holds for what they show, not for the raw frontmatter.

**Nested parents.** v1 ticks a parent (`ISC-4` over `ISC-4.1`, `ISC-4.2`) once all its leaves are.
A parent has no probe, so `isa verify` never proves it. The engine ticks a nested parent itself,
on every write (`isa verify`, `lint`, `close`): `[x]` when every non-dropped leaf under it is ticked
or waived, `[ ]` again when one regresses or is unticked. A parent gets no Verification line and no
ledger row, and lint never asks for one. The model can't tick a parent either (§ 3.3).

**Generated vs model-written Verification lines.** A generated line is an `- ISC-N:` line whose text
starts with `verified`, `attested` or `regressed` (§ 4.4). `[DEFERRED-VERIFY]` lines stay model-owned
(v1 Append format `- ISC-N: [DEFERRED-VERIFY] — <why> — follow-up: <what>`), as do `- Goal:` and
`- Ask N:` lines.

### 3.2 Command set

All commands take the ISA path explicitly: a CLI child process can't reliably learn which session
called it, so there is no session default. Exit codes: 0 ok · 1 check failed · 2 usage error.

#### `isa new <slug> [--tier E1..E5] [--goal "<span>"]`
- Creates `~/.isa/<project>/<YYYYMMDD-HHMMSS>_<slug>/ISA.md` with frontmatter: `task` (empty quoted,
  for the model), `slug`, `effort` (default E3), `phase: observe`, `progress: 0/0`, `started`,
  `updated`, `root` (project root of cwd), `stated_goal` and `asks`.
- When `isa new` is run inside `ISA_HOME` (cwd in an ISA folder), `root` comes from that ISA's own
  `root:` field, never the ISA folder itself, which has no git root and would make probes run there.
- `isa new` has no session, so it fills `stated_goal` and `asks` as a best effort from the project's
  most recent logged prompt (which can belong to another session in the same project). v1 prompt
  rows are `{t, id, text}` per session file, so v2 adds `cwd` and `project` to each prompt row
  (`_prompt` knows both); that is what makes "the project's prompts" a lookup.
  - `stated_goal`: with `--goal`, the span is written as given (exit 1 if no logged prompt of the
    project contains it). Without `--goal`, the latest prompt is used only when it is ≤ 300 chars,
    holds no code fence or pasted block, and passes the Scaffold minimum-content rule (≥ 6 tokens
    with propositional content; "go" or "fix these" fail it); otherwise `null`, plus a comment
    telling the model to select a verbatim span. `--goal` spans must pass the minimum-content rule
    too (exit 1 otherwise).
  - `asks`: extracted from that prompt, with the previous assistant message as context (§ 1.2), by
    the judge (`asks_extract`, § 7). On a judge error the list is left empty with a comment, and the
    model writes it.
  - The context reaches `isa new` through the log: `_prompt`, which has the hook input,
    stores the tail of the previous assistant message in the prompt row
    (`{t, id, text, cwd, project, context}`), and `isa new` reads it from the row it uses.
- The real check happens at binding: the binding hook checks the span against this session's logged
  prompts (v1 `stated_goal` rule) and reports a mismatch as lint feedback, and Stop refuses while it
  stands.
- Creates no body sections: the model writes them.
- Prints the path. The hooks bind it: PostToolUse binds the path `isa new` printed, the same way a
  Write of an ISA binds it in v1, and records the current `prompt_id` (§ 1.4).
- v1 behaviour (print a fresh path only) stays available as `isa new --path-only`.

#### `isa lint [--close] <ISA>…`
- Recomputes `progress` and drops orphaned generated lines first (§ 3.1), then checks.
- Unchanged checks, plus § 6 rules and the ownership checks (an engine-owned field that disagrees
  with the ledger, e.g. an `[x]` leaf with no ledger tick row → error; nested parents have no probe
  and are exempt, § 3.1).
- The moment is chosen automatically (v1 `auto`); `--close` forces the close moment. `isa check` is
  **not** added.

#### `isa verify [--red] <ISA> [ISC-N…] [--attest "<evidence>"]`
- Runs the probes of the selected mechanical ISCs (default: all mechanical, open and ticked), with
  cwd = `root` (or the entry's `cwd:`, relative to `root`).
- `isa verify` and `isa close` refuse to run probes until the ISA passes articulation lint (exit 1,
  the lint errors printed). The model writes `tool:` and `isa-cmd` is always allowed (§ 3.3), so
  without this a probe could make changes before the ISA exists in a checkable form.
- Takes one fingerprint before the batch and one after (§ 4.2). If they differ, it prints
  "probe changed the tree: <paths>" and records the rows with the *after* fingerprint; `isa close`
  then refuses until a run leaves the tree unchanged.
- A batch that changed the tree is also recorded as a project change: a `changed` ledger row with
  the paths, which counts for the nudges, and every close summary lists "changed by probe: <paths>".
  Edits routed through a probe are therefore never silent, even when a later run is stable.
- Records one ledger row per ISC (schema § 4.1).
- **Green mode (default):** for each passing ISC that may be ticked (proven per § 4.2, not blocked by
  Feature order, red requirement met or marked per § 4.6), the engine **rewrites the ISA**: `[ ]` →
  `[x]`, adds or replaces the generated `- ISC-N:` Verification line, recomputes `progress`, sets
  `updated`, appends an `unblocked` ledger row for matching `blocked` items. For each failing ISC that
  was ticked: `[x]` → `[ ]`, Verification line replaced by `- ISC-N: regressed (passed at <stamp>) —
  FAIL <stamp> — exit <n> — <probe>`, and the summary lists it as regressed, not as a new failure.
- **Red mode (`--red`):** runs the probes and records `run: red` rows; never ticks; prints which ISCs
  failed as expected and which already pass ("already green before the change: is the probe testing
  anything?").
- **`--attest "<evidence>"`** (exactly one ISC): only for self-attested ISCs (`manual`, `screenshot`,
  `eval`, or no probe). Refused for mechanical ISCs ("run `isa verify`") and for `risk: high` ISCs
  (§ 6.2: those need a mechanical probe, or the user waives the ISC, which takes it out of the count).
  Records a ledger row `{kind: attest, evidence}`, ticks, writes `- ISC-N: attested <stamp> —
  <evidence>`. Listed to the user at close as "not machine-verified" (v1 notice kept).
- The first `isa verify` run of an ISA (red, green or attest) appends a `strategy` ledger row: the
  `type`, `kind` and `tool_sha` of every Test Strategy entry. § 6.4 compares against it.
- Prints the run table and "ISA updated: ticked ISC-…, unticked ISC-…, progress n/m — re-read the ISA
  before editing it."
- Writes the ISA atomically: temp file + rename.

#### `isa close <ISA>`
1. Re-runs every mechanical probe (as `isa verify` does). This re-run is what makes the close fresh
   (§ 4.2); it needs no session state.
2. Requires: every counted leaf ISC ticked or user-waived; every mechanical probe passed in this
   re-run, and the batch left the tree unchanged; no open `blocked` items in the ledger;
   `isa lint --close` clean; one `- Goal: yes — …` line (latest Goal line is `yes`); one
   `- Ask N:` line per `asks:` entry, where a missing `- Ask N:` line counts as unmet and refuses the
   close; § 6.3 `second-look:` when it applies; § 2 rule 9 `class-sweep:` when it applies.
3. Optional judge (§ 7): `goal_met` and `asks_met` advisory verdicts recorded in the ledger; not
   blocking in v2.
4. On success writes `phase: complete`, `progress`, `updated` and prints the **close summary**:
   proven claims (with probe + stamp), attested claims, `(no red baseline)` claims, `risk: low`
   reasons, type/kind downgrades, changed by probe, waived, deferred, regressed-then-fixed, asks.
   Exit 0.
5. On failure changes nothing, prints each failure, exit 1.

#### `isa status [--json]`
- Unchanged, plus `mode` (`on|off`, reason), open `blocked` items (from the ledger), and the latest
  judge verdict.

### 3.3 Enforcement in hooks

**Classification of `isa` itself.** `isa ls`, `where`, `fit` and `status` stay `read`. `isa new`,
`lint`, `verify` and `close` become a new kind, `isa-cmd`:
- PreToolUse: always allowed, in OFF and ON, bound or not — they are how the model gets out of a
  refusal. They never switch the mode and never count as a project change.
- PostToolUse: refresh the stored ISA mtime (so the engine's write is not taken for a model shell
  edit) and, for `isa new`, bind the printed path.
- Project files a probe changes are not tracked by the hook: `isa verify` reports them itself (§ 3.2).

**PreToolUse on Write/Edit of an ISA.** The proposed text is computed as v1 `_proposed()` does, then
compared with the current file:
- A checkbox flipped `[ ]` → `[x]` → refused: "ticks are written by `isa verify`".
- A generated `- ISC-N:` Verification line added or changed → refused (removing an orphaned one is
  left to the engine, § 3.1).
- `progress` or `root` changed, or `phase` set to `complete` → refused, with the command to use.
- Everything else → allowed (the v1 articulation and reopen rules still apply).

**Shell edits of an ISA.** Commands whose text names an ISA path (`sed -i`, `tee`, `>`, `cp`, `mv`
onto `…/ISA.md`) → refused: "edit the ISA with Write/Edit". Classifier change: these become
`isa-shell-edit`, not `write`. An unrecognised script that moved the ISA's mtime (v1 shell-edit
detection) → the PostToolUse lint reports any engine-owned field that disagrees with the ledger; Stop
refuses.

---

## 4. Evidence (build-order items 1–4)

### 4.1 Ledger row v2

`~/.isa/_state/evidence/<slug>-<hash>.jsonl`, one JSON object per line:

```json
{"v": 2, "t": 1759350000.1, "isc": "ISC-2", "kind": "verify|attest|close",
 "run": "green|red", "tool_sha": "…", "files": {"tests/test_x.py": "sha256:…"},
 "ok": true, "exit": 0, "secs": 0.04, "root": "/home/u/dev/app", "cwd": "/home/u/dev/app",
 "fingerprint": "sha256:…", "tail": "last 800 chars", "evidence": null}
```

`files` holds one hash per file the probe names (§ 4.6). The ledger also carries `blocked` /
`unblocked` rows (§ 4.5), `strategy` snapshot rows (§ 6.4) and `changed` rows (§ 3.2).
v1 rows (no `v`) are read as `fingerprint: null`: they never serve as a red baseline, and an open v1
ISA is re-proven by its first `isa close` like any other.

### 4.2 Proven and fresh (item #1 + #6)

An ISC is **proven** when its latest green row has `ok` and a `tool_sha` equal to the hash of the
current probe.

**Freshness is a property of the close, not of the rows.**
Because `isa close` re-runs every mechanical probe and requires every one to pass, the proofs it
accepts are by construction about the code as it is at close. A tick made mid-run may go stale;
that is harmless, since the close re-proves it. So neither the hooks nor the close need v1's
`last_mutation` timestamps for freshness (they stay only for nudges and for "did anything happen
this turn"), and nothing needs the session: `isa close` is self-contained. A change after
`phase: complete` is already refused by the v1 "finished ISA" rule.

The **fingerprint** keeps two jobs only:
1. the red-baseline check — the red and green runs saw different code (§ 4.6);
2. detecting probes that change the tree — taken before and after each batch (§ 3.2), which also
   makes the close's "re-proven" claim honest: a batch that changed the tree did not prove the final
   tree.

**Fingerprint of a root** (git: a hash of the content, so a commit that changes no file changes
nothing):
- Git work tree: copy the index to a temp file, then
  `GIT_INDEX_FILE=<tmp> git add -A -- . && GIT_INDEX_FILE=<tmp> git write-tree`, appending
  `':(exclude)<ISA_HOME relative to root>'` only when `ISA_HOME` lies inside `root` (git rejects a
  pathspec outside the work tree, and in the normal setup `~/.isa` is outside it). The tree id covers
  tracked and untracked non-ignored files; gitignored files never count (v1 rule). The real index is
  never touched.
- Not git: the `changes.py` walk (path, size, mtime_ns; capped at 5,000 files / 2 s); above the cap →
  `fingerprint: "uncomputable"` (`isa close` reports it, and the red check falls back to
  `(no red baseline)`). This one is not a content hash: a `touch` invalidates it outside git.
- Computed by `isa verify` / `isa close` only. Hooks never compute or cache a fingerprint; Stop
  checks only the ledger rows and the ISA.

### 4.3 Fixed root (item #7)

- `root:` in the frontmatter, written by `isa new` (project root of cwd). Engine-owned.
- Probes run with cwd = `root`; an entry may set `cwd: <path relative to root>`.
- Lint warning on probes starting with `cd /absolute/path` ("use root/cwd").
- ISAs spanning several projects (v1 `.projects.json`): an entry may set `root:` to a path relative
  to `$HOME` (`root: dev/other-app`). Not a project key: keys replace `/` with `-`, so
  `dev-jolo-isa-tests` can't be turned back into a path. The fingerprint is computed per distinct root.

### 4.4 Generated Verification line (item #1)

Format, written only by the engine:
```
- ISC-2: verified 2026-10-01T20:30:56 — exit 0 in 0.04s — `python3 -c "…"` (ledger: <slug>-<hash>#L17)
- ISC-5: attested 2026-10-01T20:31:10 — screenshot viewed: /tmp/shot.png shows the new header (ledger: …#L18)
- ISC-7: regressed (passed at 2026-10-01T20:30:56) — FAIL 2026-10-01T20:32:00 — exit 1 — `npm test -- -t "cap"`
- ISC-9: verified 2026-10-01T20:33:02 — exit 0 in 1.2s — `pytest -q tests/test_cap.py` (no red baseline) (ledger: …#L24)
```

The `#L<n>` reference lets a reader (or lint) check the line against the ledger.

### 4.5 `blocked` escalation (item #8)

- Stop refuses once per prompt; the second check on the same prompt lets the turn end with a warning
  (v1). When Stop lets a turn end with problems still open, the engine appends one ledger row:
  `{"kind": "blocked", "t": …, "items": [{"code": "tick-unproven", "isc": "ISC-4"}, {"code":
  "close-no-goal"}]}`. The ISA file is not written (§ 0.3), so the model's next Edit never meets a
  stale `old_string`, and the mtime-based shell-edit detection is not tripped.
- Each item is a stable key — a `code` from a fixed list (one per Stop problem: `no-isa`,
  `lint-error`, `tick-unproven`, `tick-order`, `close-no-goal`, …) plus `isc` when it concerns one —
  with the human text derived from it. `isa verify` / `isa lint` re-evaluate each open key and append
  `{"kind": "unblocked", "items": [<keys>]}` for those that no longer hold. The open list is the
  replay of those rows, matched by key, never by text.
- The ledger is per ISA, so a problem with no ISA has no ledger: `no-isa` is kept in session state
  (`blocked_no_isa: <prompt_id>`), shown the same way, and cleared when an ISA is bound.
- The ledger, unlike the ISA folder, can't be written by the model, so the list can't be deleted
  around the check.
- Open items are shown in SessionStart / ON re-injection, in `isa status`, and in the user-visible
  Stop warning. `isa close` refuses while any item is open.

### 4.6 Red-then-green (item #5)

- **Applies to** mechanical ISCs at E2+ whose `kind:` is `behaviour`, `http` or `schema` (§ 6.1),
  except `Anti:` ISCs, `kind: regression`, and entries with `red: exempt — <why>` (the reason is
  shown at close).
- **Recorded** by `isa verify --red`, after the test exists and before the implementation: the model
  writes the test file (a project change, allowed once the ISA passes articulation), runs `--red`, then
  builds. There is no gate on the first project change: the engine can't tell a test file from an
  implementation file, and gating the first change would refuse the test itself.
- **Checked at the green tick:** a green row ticks normally only when an earlier failed red row
  exists with the same `tool_sha` and a different `fingerprint` — the same probe as written now, run
  against different code. A probe whose command text was weakened after the red run no longer
  matches. Without a matching red row the ISC is still ticked, its line is marked
  `(no red baseline)`, and `isa close` lists it with the self-attested items.
- **Files named by the probe** (path tokens of the `tool:` that exist under `root`) are hashed one
  by one into the row's `files`. They never decide the match: a `behaviour` probe usually runs the
  very file the change edits (`python3 todo.py done 1`), so a hash over all named files would differ
  between red and green and drop almost every baseline. Instead, the close summary lists, next to the
  ISC, each named file whose hash differs between the red and the green row ("changed since red:
  tests/test_x.py, todo.py"). The reader sees whether the test itself moved; the code under test is
  expected to. Known limit: tests reached indirectly (`pytest -k cap`, `npm test`) are not listed.
- A red row that **passed** (already green before the change) is not a baseline: the ISC gets
  `(no red baseline)` like a missing red run, and a lint warning "probe can't fail: it proves nothing"
  (never an error — an error would block every change, and its only fix, `red: exempt`, is written by
  the model, so it would add friction without a check). `isa close` lists it.
- **Known limit:** a probe that greps for text the change will add is red before and green after, so
  it passes this rule. That case is caught by § 6.1 (`behaviour` can't be a grep) and, later, by the
  probe-adequacy judge (§ 7).

---

## 5. Hook changes summary (engine.py)

| Function | Change |
|---|---|
| `_prompt` | Gate (§ 1.2) while OFF or while the bound ISA is `complete` (→ `needs_isa_since`, § 1.3); logs `cwd` and `project` with the prompt; mode switch, ON block on the OFF → ON transition, user-visible mode line. The fit advice is removed |
| `_session_start` | OFF/undecided: nothing. ON: ON block + status + open `blocked` items + Goal/open ISCs after compaction (v1 content) |
| `_pre_tool` | `isa-cmd` → allow. OFF + write → switch ON + refuse. OFF + unknown → allow with the change check (snapshot here, verdict in `_post_tool`, § 1.4). ON: v1 gate + ownership rules (§ 3.3); the pending-tick refusal is **removed** (the runner ticks); no red-baseline gate (§ 4.6) |
| `_tick_gate` | Replaced by the ownership check: the model can't tick at all |
| `_post_tool` | OFF: an `unknown` call that changed project files switches ON (`mode_source: change`). ON: tick-related feedback removed; lint feedback kept; 5-change nudge kept; `isa-cmd`: mtime refresh, and binding of the path `isa new` printed; any binding switches the session ON (§ 1.3); new nudge: failed `isa verify` → "claim wrong or code wrong?" (rule 14) |
| `_stop` | ON + no bound ISA, or `needs_isa_since` with no ISA bound after it → block once with the two-exit text (§ 1.4), checked before the "nothing happened this turn" early return; the scaffold exit only on the creating prompt; hook-side lint (§ 3.1); no fingerprint work (§ 4.2); a turn let through with problems open → `blocked` ledger row with item codes (§ 4.5) |
| `ISA_JUDGE_CHILD` | Every event → `{}` |

Adapters (the context of § 1.2 needs plumbing on both sides):
- Claude Code: `_claude_in` (`cli.py`) forwards transcript_path from the hook input into the engine
  event; `_prompt` reads the last assistant message from that JSONL file.
- pi: `before_agent_start` already carries the prompt event and `agent_before_settle` the Stop. Two
  changes: the `prompt` engine call uses `ISA_PROMPT_TIMEOUT_MS` (§ 1.2) instead of the 5 s default,
  and it passes the tail of the last assistant message from the session (today it sends only
  `{prompt}`).

---

## 6. Lint rules (items #2, #3, #4)

### 6.1 `kind:` sets the minimum probe type

Each Test Strategy entry gets a `kind:` from E2 (lint error if missing at E2+; warning at E1):

| kind | Allowed `type` | Refused |
|---|---|---|
| `behaviour` (code does X when run) | unit-test, property, bash (running the code) | manual, grep-only `bash` (a `tool:` whose commands are all `grep`/`rg`/`test -f`/`cat`) |
| `http` | bash with `curl -i`/`http`, unit-test against a server | manual, grep-only |
| `visual` | screenshot (image viewed), eval | grep-only |
| `file` (a file exists / contains X) | bash (grep, test -f, read-back) | — |
| `config` | bash read-back | manual |
| `schema` | bash/sql query | manual, grep-only |
| `doc` (prose deliverable) | eval, manual, bash | — |
| `decision` (a choice recorded) | manual | — |
| `regression` (must stay true) | any mechanical | manual |

"Grep-only" is decided by the classifier's tokenizer: every segment's command is in
`{grep, egrep, rg, test, [, cat, head, wc}` and no segment runs project code.

### 6.2 High-risk ISCs can't be self-attested

- The keyword list
  `secret|token|credential|password|auth|login|permission|payment|billing|money|invoice|deploy|prod|production|publish|release|push`
  (case-insensitive, word boundaries) only forces a `risk:` declaration on a matching entry: it
  must say `risk: high` or `risk: low — <why>`. Missing → lint error at E3+, warning below. The
  keywords also match ordinary code (a stack push, a lexer token), so a match alone has no other
  consequence.
- `risk: high` has the consequences: type `manual`/`screenshot`/`eval` → lint error and `--attest`
  refused. The fix is a mechanical probe, or the user waives the ISC (§ 6.5), which takes it out of
  the count; and § 6.3 applies.
- `risk: low — <why>` reasons are listed in the close summary.

### 6.3 Skipping the second look is written down

- If the ISA has any `risk: high` ISC or `effort` ≥ E4, `isa close` requires a Decisions row:
  `second-look: <who/what reviewed, where its findings are> | skipped — <why>`.
- Findings from a review are dispositioned in Decisions:
  `finding: <text> — adopted (<diff/ISC>) | rebutted (<reason>) | deferred (<task>)`.

### 6.4 A probe downgrade is visible

The model writes `type:` and `kind:`, so relabelling a failing `bash` probe as `kind: decision, type:
manual` and attesting it would tick it. Lint compares each entry with the `strategy`
snapshot taken by the first `isa verify` run (§ 3.2) and with the ISC's last failing run. The
snapshot comes from a command, so no hook has to track a per-ISA "first change"; an ISA never
verified has no snapshot and nothing to downgrade from yet.
- A downgrade — mechanical → self-attested `type`, a `kind:` with a weaker minimum (§ 6.1), or a
  `tool:` removed — relative to the snapshot or after a failing run needs a Decisions row
  `refined: ISC-N probe downgraded — <why>`; without it, lint error.
- Every downgrade is listed in the close summary.

### 6.5 `waived:` carries the user's words

Only the user can waive. A waiver must quote them:
`waived: ISC-N — "<verbatim user words>"`, and lint checks the quote against the prompt log of the
ISA's sessions, as it checks `stated_goal`. Those sessions are found by scanning the
session files whose `bound` is the ISA in `~/.isa/_state/sessions/` (v2 adds a `bound_history` list
to the session file so a session that later switched ISA still counts). A waiver with no matching
quote is a lint error (a warning for ISAs started before v2).

---

## 7. Judge interface (item #6, beyond the gate)

`runtime/isa/judge.py`:

```python
def judge(question: str, payload: dict, *, backend=None, timeout=None) -> dict:
    """→ {"verdict": "yes"|"no"|"unsure", "reason": str, "source": "...", "ms": int, ...}"""
```

Questions (each a template under `runtime/isa/judge/`):

| Question | Called from | Effect in v2 |
|---|---|---|
| `gate` (§ 1.1) | UserPromptSubmit | Decides the mode (blocking) |
| `asks_extract`: "list each explicit ask in this prompt, verbatim" | `isa new` | Fills `asks:`; the model may add, a removal needs a `refined:` row |
| `probe_adequacy`: "does this probe, as written, fail when ISC-N is false?" | `isa lint` at articulation, once per (ISC, tool_sha), cached | Warning only |
| `goal_met`: "does the result described by the Verification lines deliver the stated goal?" | `isa close` | Recorded + shown; not blocking |
| `asks_met`: "is each ask's line honest given the ISA?" | `isa close` | Recorded + shown; not blocking |

Time limits: `gate` and `asks_extract` use `ISA_JUDGE_TIMEOUT` (12 s), since the gate runs inside a hook. The three advisory questions use `ISA_ADVICE_TIMEOUT` (default 60 s): they run in commands, and a batched `probe_adequacy` over 7 probes was measured past 12 s on 2026-10-02.

Promotion from advisory to blocking is a later decision, made on eval data (false-positive rate).

---

## 8. Migration

- **Finished ISAs** (`phase: complete`) are never re-linted against v2 rules (v1 principle).
- **Open v1 ISAs:** no `root` → `isa verify` writes it on its first run (cwd's project root). When
  that cwd is inside `ISA_HOME`, it refuses instead (exit 2, "no root: run it from the project"),
  since the ISA folder has no git root and would become the root (same rule as `isa new`, § 3.2). No
  `kind:`, no `risk:` declaration, or a `waived:` row without a quote → warning, not error, for ISAs
  whose `started` predates v2. v1 ledger rows → no red baseline (§ 4.1).
- **Running sessions:** the hooks call the installed runtime on every event, so sessions running
  during the upgrade switch to v2 mid-task. Their session files have no `mode`: ON with an open bound
  ISA, OFF otherwise (§ 1.3). Their prompt rows have no `project` until the next prompt.
- **Examples** (`skill/ISA/Examples/*.md`): add `kind:` (and `risk:` where a keyword matches) to every
  Test Strategy entry, regenerate Verification lines in the v2 format, quote the user in `waived:`
  rows, and add `root:`, `asks:` and `second-look:` rows where the rules require them.
  `tools/lint_isa.py skill/ISA/Examples/*.md` must stay all `ok`.
- **Installer:** a separate timeout for `UserPromptSubmit` (20 s), `ISA_JUDGE` and
  `ISA_PROMPT_TIMEOUT_MS` documented, the `Bash(isa:*)` permission kept.
- **AGENTS.md:** § Enforcement rewritten from this spec; "read-only advice" text removed.

---

## 9. Whole-flow test

`tests/flow/test_isa_flow.py`: stdlib only, opt-in (`ISA_FLOW_LIVE=1`), one live Claude Code
session (Sonnet 5.5) in a sealed sandbox (fresh git project, private `ISA_HOME`, repo skill and
runtime, the eval runner's isolation flags), `ISA_JUDGE=claude`. Two prompts in **two separate
sessions**:

**Session 1 — YES:** the todo fixture, "Add two things to todo.py: a `done <id>` command … `[x]` …
`[ ]`". Stages asserted in order, each with evidence:

1. The gate verdict is `yes` (judge log), and the user line `ISA: ON` was emitted.
2. The ON block was injected (UserPromptSubmit context).
3. The model read `skill/ISA/SKILL.md`.
4. `isa new` ran and the session is bound to the path it printed; the ISA has `root`, `asks`, and a
   `stated_goal` that is a substring of the prompt.
5. `isa lint` is clean before the first project change; the first project change was not refused
   for missing ISA/lint.
6. For each ISC that needs it, a failed red row precedes the green row with the same `tool_sha` and
   a different fingerprint; or the line is marked `(no red baseline)` (reported). Named files whose
   hash moved between red and green are reported; a test file listed as changed since red is
   flagged in `verdict.md`.
7. The model never wrote a checkbox, a generated Verification line, `progress` or `phase: complete`
   (no ownership refusal needed, or refusals seen and recovered — reported).
8. The acceptance script passes; only allowed files changed.
9. `isa close` exit 0; `phase: complete`; its re-run passed every mechanical probe and left the tree
   unchanged; the final answer quotes the close summary.

**Session 2 — NO:** "what does `cmd_list` in todo.py print?". Asserted: the gate verdict is `no`,
the user line `ISA: OFF`, no ISA file, no context injected, and the Stop hook stays silent.

**Output:** `flow/<timestamp>/` on branch `eval-results`, containing `ISA.articulation.md`
(snapshot at the first project change), `ISA.final.md`, `timeline.md` (each tool call, hook
decision, ISA edit and gate verdict), and `verdict.md` (stage table). Also printed in the
terminal. Cost estimate: $0.30–0.60 per run.

---

## 10. Milestones

Each milestone is one ISA, ends with the full unit suite green, and changes nothing outside its list.

### M1 — Gate and mode (fixes run A)
`judge.py` (gate only; `claude`, `pi`, `heuristic` backends, and the opt-in `api`), `gate.md`,
`engine._prompt/_session_start/_pre_tool/_stop` mode logic (Stop no-ISA check before the early
return, two-exit text, lint accepting a `context_sufficient: false` scaffold on the creating prompt
only), `ISA_MODE`, `ISA_JUDGE_CHILD`, new `protocol.md` (ON block), `fit.py` pre-filter verdicts
(advice removed), installer timeout, pi `ISA_PROMPT_TIMEOUT_MS`, assistant context forwarded by both
adapters and logged in the prompt row. Tests: state machine (OFF stays OFF
on no, OFF → ON on yes / write / a changing unknown call, sticky ON;
an unknown command that changes nothing keeps an OFF session OFF), judge backends with a fake
`claude`/`pi` on PATH and a
fake API server, `auto` never picks `api`, timeout → ON, pi prompt timeout above the judge timeout,
recursion guard, "go" pre-filtered `unsure` and judged `yes` when the previous assistant message
proposed a review (fake transcript), Stop blocks ON + no ISA on a turn with no change, the scaffold
exit accepted on the creating prompt and refused on the next, OFF sessions silent, binding while OFF
switches ON (no refusal on the next edit), a v1 session file without `mode` read correctly, a review
prompt after a closed ISA re-judged and blocked at Stop until a new ISA is bound.

### M2 — Commands and ownership (items #9 + #1)
prompt rows with `cwd` and `project`, `isa verify` / `isa close` articulation precondition,
`isa new` (scaffold, `--goal`, `asks: []` — extraction comes in M6 —, binding from its printed path
with the session-side `stated_goal` check), `isa lint --close`, `isa verify` ticking + generated
Verification lines + `--attest` + regressed lines + the `strategy` snapshot row, `progress` recompute
and orphan cleanup in lint/verify/close, hook-side lint (no writes, engine-field errors suppressed),
`isa close` (re-runs every probe; no fingerprint yet, so no tree-change check), ownership refusals in
PreToolUse with `[DEFERRED-VERIFY]` lines left model-owned, `_tick_gate` and pending-tick refusal
removed, classifier `isa-cmd` (with mtime refresh) and `isa-shell-edit`. Tests: an engine tick round
trip, model tick refused, model `[DEFERRED-VERIFY]` line allowed, untick allowed and its orphaned line
dropped, adding an ISC never leaves a model-facing `progress` error, a nested parent ticked by the
engine when its last leaf passes and unticked when one regresses, `isa new` refusing a "go" goal
(minimum-content) and taking `root` from the ISA when run inside one, attest rules, the close summary,
close fails when a ticked probe now fails, atomic write, an Edit after the engine rewrite (stale
old_string) gives a clear error, an `isa verify` run never reported as a shell edit.

### M3 — Root and fingerprint (items #7 + #6)
`root:`, per-entry `cwd:`, fingerprint (`write-tree` with a temp index and the conditional
`ISA_HOME` exclude, and the walk), one fingerprint before and after each batch, the close's
tree-change check, ledger v2, migration of v1 rows. Tests: any content change (Edit, heredoc,
formatter) changes it; `git commit` alone does not; an ignored file doesn't; the real index is
untouched; `ISA_HOME` outside the repo and inside it both work; a probe that writes a file is reported
and blocks close; non-git cap → uncomputable; a `touch` changes the non-git fingerprint; multi-root.

### M4 — `blocked` (item #8)
A Stop that lets a turn end with problems open appends a `blocked` ledger row with item codes; shown
at start/status; `unblocked` rows from verify/lint, matched by code; close refused while open. Tests:
block → resume session → shown → fix → cleared; reworded problem text still clears by code; the ISA
file is never written by a hook.

### M5 — Red-then-green (item #5)
`isa verify --red`, the red check at the green tick (same `tool_sha`, different fingerprint),
exemptions, `(no red baseline)` marking, "can't fail" lint warning. Tests: test file written then red
then green → normal tick; probe weakened after red → `(no red baseline)`; a `true` probe → warning and
`(no red baseline)`, never a blocking error; test file weakened after red (same command) →
baseline kept and the test file listed as changed since red; a probe running `todo.py` keeps its
baseline across the implementation change; grep-of-new-text accepted (documented limit); Anti
exempt.

### M6 — Lint rules and rules on the path (items #2, #3, #4 + § 2)
`kind:` table, keyword → `risk:` declaration, `risk: high` consequences, downgrade check (§ 6.4),
quoted `waived:` (§ 6.5), `second-look:` / `finding:` rows, `asks:` via `asks_extract` + `- Ask N:`
lines, `class-sweep:`, `repro-bypass:`, SKILL.md "Completion rules" with teeth (incl. SHAPE),
IsaLoop.md trimmed, the "all four hold" fix, examples migrated, AGENTS.md § Enforcement rewritten.
Tests: each lint rule positive/negative, examples all `ok`, LifeOS-free check.

### M7 — Judge beyond the gate (item #6) + whole-flow test
`probe_adequacy`, `goal_met`, `asks_met` (advisory), the § 9 flow test; one live flow run committed
on `eval-results`; the background-gate decision (§ 1.2) taken on the `ms` data. Restoring the stashed
eval harness (`evals-wip-20261001`) and re-running its batch against v2 is the natural follow-up,
decided then.

---

## 11. Revision (2026-10-02): a judge-free baseline, Jev on top

M1–M7 shipped with model-call judges. Measured in use, they are too slow and too fragile for a system that has to be extremely reliable:
- **The gate (in the UserPromptSubmit hook):** Haiku took 4.1–7.6 s on every prompt the pre-filter left `unsure`. A 429 rate limit or an outage flips it to "fail toward ON", so a plain question then gets ISA busywork at Stop.
- **`probe_adequacy` (`isa lint`):** one batch took 11–26 s, then over 60 s on an 11-probe ISA, and the time grows with the ISA.
- **`extract_asks` (`isa new`) and `goal_met` / `asks_met` (`isa close`):** these are the same calls, with the same failure modes.

This revision replaces them with a baseline that makes **no model call anywhere**. Every hook and every `isa` command becomes deterministic. Jev, called through jev-kit, runs on top as a fast extra layer. It is **on by default for the whole system** and switched off system-wide in `~/.isa/config.json` (§ 11.3). There is no per-project switch, for Jev or for ISA.

### 11.1 Reliability rules

1. **Correct with Jev off.** The baseline is complete on its own. With Jev off, unavailable, out of credit or slow, behaviour is exactly the baseline. Nothing needs Jev in order to be correct.
2. **Engine deadline.** The engine kills each `jev` call at its own hard limit: 1.5 s in hooks, 3 s in commands. jev-kit's breaker does a different job: it makes calls fail fast after repeated failures. It does not bound a single call.
3. **Add-only.** A Jev verdict can only add: turn the session ON early, or add a warning or a note. A Jev "no", a low-confidence answer or no answer always falls back to the baseline, so a wrong Jev answer never removes a check.
4. **Advisory until calibrated.** No Jev verdict blocks anything. Each judgment can be made blocking later, one at a time, on eval data (§ 11.6).

### 11.2 Judgment points

| Judgment | Baseline (always on, no model call) | Jev (on by default) | Deadline | Not served |
|---|---|---|---|---|
| Gate (UserPromptSubmit) | Pre-filter `yes` → ON plus the ON block; `no` → OFF. For `unsure`, inject one line: *"If this asks for work with a checkable end state, write an ISA first; otherwise start your answer with `ISA: not needed — <reason>`."* At Stop, an unsure prompt needs a bound ISA or that line in the last assistant message (a string check). | Noul "is this a request for work with a checkable end state?"; ≥ 0.8 → ON plus the ON block on the prompt | 1.5 s | Baseline line |
| Asks (`isa new`) | `isa new` makes no model call. The model writes `asks:` as verbatim spans, and lint checks each span against the logged prompts. The asks list in force at the first `isa verify` is recorded in the ledger; removing an ask afterwards needs a `refined:` row. | None (Jev can't produce text spans) | — | — |
| Probe adequacy | A `fails-when: "<what the probe sees when the claim is false>"` field, required from E2 on every entry that can't get a red baseline (Anti, config/doc/file/decision, `(no red baseline)`). Lint checks only that it is present. Red-then-green stays the real proof. The close summary shows `fails-when` next to each "never seen failing" ISC. | One Noul per such ISC at its first `isa verify`, given the ISC, probe and `fails-when`; < 0.5 → a warning | 3 s per batch | No warning |
| Goal / asks met (`isa close`) | `- Goal:` and `- Ask N:` lines written by the model, with their shape checked by lint | One Noul per line, shown under the close summary | 3 s | "not judged (Jev unavailable)" |
| Waiver quote | Deterministic substring check (unchanged) | None, stays in code | — | — |

Removed from the runtime: the `claude`, `pi` and `api` backends, `gate.md` and `judge/*.md`, `ISA_JUDGE`, `ISA_ADVICE`, `ISA_ADVICE_TIMEOUT` and `ISA_JUDGE_TIMEOUT`. Jev is the only judge, and the config file of § 11.3 is its only switch. The installer's 20 s UserPromptSubmit timeout drops back to the common 15 s.

### 11.3 Jev on by default, one system-wide switch

- **On by default** for every session and every project. Nothing has to be configured beyond jev-kit itself (`jev` on PATH and a key).
- **The only switch is system-wide.** `~/.isa/config.json` (`$ISA_HOME/config.json`) with `{"jev": false}` turns Jev off for ISA everywhere. A missing file, unreadable JSON or a missing key means on. A broken config never stops ISA; the engine logs the parse error and carries on. jev-kit's own `jev disable [--for 2h]` also stops it, for every consumer of jev-kit.
- **No per-project switch,** for Jev or for ISA (the user's call, 2026-10-02). A consequence to keep in mind: ISA text from every project is sent to TypeSafe, bky included. The system switch is the only way to stop that.
- **Asking before going on without an ISA (built in M8):** `{"ask_without_isa": true}` (the default) in the same file. When the model wants to answer an unsure prompt without an ISA, the user is asked "ISA is not enabled for this prompt (<reason>). Continue?" — Continue without ISA (default) / Enable ISA — after the model decided: by the model through AskUserQuestion in Claude Code, by the extension's own dialog in pi. Enable ISA switches the session ON. Headless runs (no one to ask) keep the declaration alone. Asked only for unsure prompts, never for those the pre-filter settled.
- **Presets** live in this repo (`runtime/isa/jev/*.json`). The engine runs `jev run isa-<question> --consumer isa` with `JEV_KIT_PRESETS=<runtime>/isa/jev`, which comes first on jev-kit's search path. The model ID is pinned in each preset (`jev-1.13.0`).
- **Measured on 2026-10-02:** `jev check` takes about 110 ms (CLI startup only). Two real `jev run` calls with a 3-question preset took 482 ms and 432 ms end to end, which leaves about 3× margin under the 1.5 s hook deadline.

### 11.4 Credit shortage and other outages

Jev credit is low, so running out is an expected state, not an edge case.

- **What jev-kit does.** An API failure is returned with a non-zero exit (`4` unavailable, `5` local budget) and `unavailable: {reason, detail}`. A 401/403 is `auth` and trips the `isa` consumer's breaker at once. Other API errors, out-of-credit responses included, are `error` and trip it after 5 consecutive failures. While tripped, calls return `tripped` without touching the network. After the 60 s cooldown, one probe call decides whether to close the breaker again. The ISA engine never retries; the breaker governs the attempts.
- **What the engine does.** Every not-served call falls back to the baseline (§ 11.2) and is logged in `judge.jsonl` (`served: false`, `reason`, `detail`, `ms`). The engine reads a credit problem from the `detail` text: `credit|balance|insufficient|payment|billing|quota|402`, case-insensitive.
- **What the user sees.** Once per session and per kind of problem, as a hook `systemMessage` (it reaches the user directly). When the not-served call came from an `isa` command, the line goes into the command's output, and the ON block tells the model to relay any `Jev:` line to the user word for word:
  - Credit: `Jev credit looks exhausted (<detail>). ISA keeps working on its baseline checks. To fix: top up TypeSafe credits, then run \`jev reset\`; or stop the attempts with \`jev disable\` (every jev-kit consumer) or \`"jev": false\` in ~/.isa/config.json (ISA only).`
  - Local budget (exit 5): `Jev's daily budget for consumer "isa" is used up (<detail>). ISA keeps working on its baseline checks; raise the budget in ~/.config/jev-kit/config.json or wait for the window to roll.`
  - Anything else (`tripped`, `error`, `auth`, `no_key`): `Jev unavailable (<reason>: <detail>). ISA keeps working on its baseline checks; \`jev status\` shows the breaker.`
- **`isa status`** shows the last Jev state for the session (served, or the reason).
- **Follow-up in jev-kit (separate repo):** classify an out-of-credit response (HTTP 402 or the provider's credit error) as its own `credit` reason that trips the breaker at once, like `auth`. Then neither the user nor the engine has to read the `detail` text.

### 11.5 Timeout fixes from the 2026-10-02 audit

The audit's finding: the gate is the only model call inside a hook; the three command calls are listed in § 11.2; the only other work on the hook path is one `git status` (5 s cap) plus a walk capped at 5,000 files.
- **pi:** the default `ISA_HOOK_TIMEOUT_MS` goes from 5000 to 15000, matching Claude Code's 15 s. At 5 s it equalled git's own cap, so a large repo could kill the hook and fail it open (the tool call would run ungated).
- **`isa verify` / `isa close` inside the model's Bash tool:** Claude Code stops a Bash command at 120 s by default, while a probe may run up to 600 s and `isa close` re-runs every probe in sequence. The ON block and SKILL.md tell the model to run them with a 600000 ms Bash timeout, or with `run_in_background` when the suite is slow. `isa close` prints its elapsed time. A killed run corrupts nothing (the ISA is written atomically at the end), but it leaves the ISA open.
- **`isa new` makes no model call** (§ 11.2, asks), so it is instant and can't fail on the network.

### 11.6 Calibration by reviewing real sessions

There are no eval tests for the judgments. The user reviews the debug log of real sessions, and that review decides any promotion of a Jev judgment to blocking, and at what threshold. French prompts are looked at separately.

**Debug log.** Every ISA step appends one JSON row to `~/.isa/_state/logs/YYYY-MM-DD.jsonl` (the local date). The engine writes it; a write failure is ignored, because a log must never block or fail a hook.
- Common fields: `"t"` (epoch seconds), `"step"`, `"harness"`, `"session"`, `"prompt_id"`, `"project"`, `"ms"` (time the step took).
- `"step"` is one of `session_start`, `prompt` (pre-filter verdict, mode before/after, the declaration line injected or not), `pre_tool` (tool, kind, decision `allow|deny`, reason code), `post_tool` (binding, lint error count, change counted), `stop` (problem codes, blocked or let through, the `ISA: not needed` line found or not), `jev` (question, served or not, reason/detail when not, answer, confidence, latency, whether it changed anything), and `cmd` (`new|lint|verify|close|purge-logs`: ISA path, ISCs run, pass/fail counts, exit code).
- Prompt text and ISA text are not copied into the log. The prompt log and the ISA already hold them; the debug row refers to them by `prompt_id` and path.
- `isa status` reads the latest `jev` row of the session to show the Jev state. This replaces `judge.jsonl`, which goes away.

**Retention.** `isa purge-logs [--days N] [--dry-run]` deletes the day files whose date (from the file name, never the mtime) is more than N days old, 7 by default. **Not scheduled** for now; it is run by hand. **Never purged:** the evidence ledger, sessions, prompt logs, `errors.log` and the ISAs. They are state that open ISAs depend on (stated-goal and waiver checks read the prompt logs), not debug logs.

### 11.7 Milestones

- **M8, judge-free baseline:** the gate's declaration line and Stop check; `asks` written by the model plus the ledger snapshot; `fails-when` and the close-summary listing; all model calls removed from the runtime; the debug log writer (§ 11.6) on every step; the pi limit and the Bash timeout guidance; skill, ON block and examples updated. (`isa purge-logs` already exists.) Tests: every judgment point with no model available; Stop refusing an unsure prompt with neither an ISA nor the line; the whole-flow test re-run with `ISA_JUDGE=off`.
- **M9, Jev layer:** the `~/.isa/config.json` switch, the presets, the `jev` backend with engine deadlines, add-only application, `jev` rows in the debug log, the user messages of § 11.4. Tests with a fake `jev` CLI: served, slow (killed at the deadline), exit 4 `error` with a credit `detail` (the credit message, shown once), exit 4 `tripped`, exit 5, garbled output, `"jev": false` in the config (no call made), an unreadable config (Jev stays on).
- **M10, calibration:** review of the debug logs from real sessions (§ 11.6), with no eval tests.


## Decisions

Taken in the spec review of 2026-10-01:

1. **Gate pre-filter:** obvious YES prompts skip the judge (cheaper, faster); a false YES is accepted.
2. **Judge model:** Haiku 4.5 via `claude` (or the opt-in `api`).
   **Still open:** the default pi provider/model (`ISA_JUDGE_PI_MODEL`).
3. **Red-then-green scope:** E2+ for `behaviour`/`http`/`schema`, checked at the green tick (§ 4.6).
4. **`asks:` list:** extracted by the judge at `isa new` (a command, so allowed by § 0.4); the model
   may add asks.
5. **Judge verdicts at close:** advisory in v2, promoted on eval data.
6. **`isa attest`:** folded into `isa verify ISC-N --attest "<evidence>"` — one command, one
   ownership path.
7. **Flow test location:** standalone `tests/flow/` for now.

Taken in the second review round (same day):

8. **Freshness** comes from `isa close` re-running every probe; the fingerprint only serves the red
   check and tree-change detection (§ 4.2).
9. **Hooks never write the ISA**, including `blocked` (ledger rows with item codes) and `progress`
   (hook-side lint suppresses, commands fix).
10. **`api` is opt-in** and there is no verdict cache.
11. **The Stop scaffold exit** is valid on the creating prompt only.

Taken in the third review round (same day; findings double-checked against the spec and the v1 code,
two dropped as false positives):

12. **A finished task doesn't end the gate:** prompts are re-judged while the bound ISA is
    `complete`, and Stop enforces a new ISA after a `yes` (§ 1.3).
13. **Binding switches ON**, and a session file without `mode` is ON exactly when it has an open
    bound ISA (§ 1.3, § 8).
14. **Probes can't launder changes:** `isa verify` / `isa close` need articulation first, and a batch
    that changed the tree is a recorded, reported project change (§ 3.2).
15. **Prompt rows carry `cwd` and `project`** (§ 3.2); a hash of the files the probe names joins the
    red check (§ 4.6; reworked in round four); **`no-isa`** lives in session state (§ 4.5).

Taken in the fourth review round (same day, after installing the `project_key` fix):

16. **Short affirmatives are `unsure`**, and the judge and `asks_extract` see the previous assistant
    message, so "go" after a proposal is judged in context (§ 1.2).
17. **`stated_goal` keeps the Scaffold minimum-content rule** at `isa new` (§ 3.2).
18. **The engine ticks nested parents** from their leaves; lint exempts them from ledger rows (§ 3.1).
19. **Named files are hashed per file and reported, never matched:** the code under test always
    changes between red and green, so matching on it would drop every baseline (§ 4.6).
20. **Per-entry `root` is a path relative to `$HOME`** (§ 4.3), and `isa new` inside an ISA folder
    takes `root` from that ISA (§ 3.2).

Taken in the fifth review round (same day; all findings double-checked, none false):

21. **Assistant context is logged with the prompt** (`context` in the prompt row), so `isa new`
    can use it without a session; both adapters forward it (§ 3.2, § 5).
22. **Pre-filter rule order is explicit**, and "ok" is no longer claimed to be answered without the
    judge (§ 1.2).
23. **A v1 ISA without `root`** is never given one from a cwd inside `ISA_HOME` (§ 8).
24. **v1 classifier fix shipped alongside:** a backtick or `$(` inside single quotes is text, not
    command substitution. Under v2 the old behaviour would have switched an OFF session ON on a
    read-only `grep` of markdown.

Taken in the sixth review round:

25. **OFF splits by kind:** a `write` switches ON and is refused; an `unknown` call runs, and
    switches ON only if v1's change check sees it changed project files (§ 1.3, § 1.4, § 5). A
    question answered by running code stays a question.
26. **Red is conditional in the ON block:** only behaviour/http/schema criteria get the red step,
    matching § 4.6.
27. **No model call in the runtime by default (§ 11):** the gate, asks, probe adequacy and close
    verdicts each have a deterministic baseline; the model-call judges move to the offline eval
    harness. Reason: measured latency (4–60+ s) and failure under rate limits made the hook path fragile.
28. **Jev is on by default for the whole system, and add-only (§ 11.1, § 11.3):** one switch,
    `"jev": false` in `~/.isa/config.json`; no per-project switch for Jev or ISA (the user's call,
    bky included). A Jev verdict can only add a check or a warning, and is advisory until calibrated.
29. **Credit shortage is an expected state (§ 11.4):** jev-kit's breaker governs the attempts, the
    engine falls back to the baseline, and the user gets one clear message with the actions.
30. **Debug logs replace eval tests (§ 11.6):** every ISA step is logged per day; the user reviews
    real sessions; `isa purge-logs` keeps 7 days, run by hand for now.
