# ISA skill — standalone export

This folder is a port of the **ISA (Ideal State Artifact) skill** out of LifeOS, the personal AI setup it was built in, so it can run on a fresh Claude Code install with none of LifeOS present. Working here means refining the export. It is not a LifeOS checkout.

## Objective

1. **Port the ISA skill.** One markdown file (`ISA.md`) per task states what "done" means as testable criteria. The model writes it at the start and keeps it updated as the work goes.
2. **Keep the core ISA rules** (file shape, lifecycle, the five workflows) and the specs the skill directly depends on. Those specs are refined later.
3. **Drop all LifeOS infrastructure:** the Pulse dashboard, voice notifications, the `PROJECTS.md` routing, the LifeOS status line, the router and nudge hooks, and the `MEMORY/WORK` paths.
4. **Enforce it in every session.** A skill loads only when the model decides to, so hooks do the deciding: Claude Code hooks (user scope) and a pi extension call one shared engine that refuses mutations until an ISA exists and passes the gate, lints every ISA edit, and refuses once per prompt to end a turn while the ISA is stale. See § Enforcement.
5. **Future, not built yet:**
   - A: memory. Learn from completed ISAs and reuse those learnings when scaffolding new ones, with the user approving each item. See `future/MEMORY.md`.
   - B: an "ISA status" status line. See `future/STATUSLINE.md`.
   - C (possible, not planned): project ISAs, a living per-repo spec. Removed from the skill; see `future/project-isa/`.
   - D: TypeSafe / Jev judgments standing in for the model's self-grading (evidence check, verbatim goal selection, waiver hook, …). Analysis only; the wrapper is built in a separate repo. See `future/JEV.md`.

## Layout

```
isa-skill-export/
├── CLAUDE.md                     ← this file
├── skill/ISA/                    ← copy this to ~/.claude/skills/ISA/
│   ├── SKILL.md                  ← entry point: homes, frontmatter, 14 sections, tier gate, lifecycle rules, routing, gotchas
│   ├── Workflows/                ← Scaffold, Interview, CheckCompleteness, Reconcile, Append
│   ├── Examples/                 ← 12 reference ISAs (E1–E5 × code/art/design/ops/enterprise), all passing tools/lint_isa.py
│   └── References/
│       ├── IsaFormat.md          ← file-shape contract (wins on contradiction)
│       ├── IsaSystem.md          ← conceptual frame
│       ├── IsaHierarchy.md       ← multi-ISA trees (rare, load on demand)
│       └── IsaLoop.md            ← the work loop around the ISA (distilled from the LifeOS Algorithm)
├── runtime/                      ← the engine, installed to ~/.local/share/isa/runtime (Python stdlib only)
│   ├── bin/isa                   ← CLI launcher, symlinked to ~/.local/bin/isa
│   └── isa/
│       ├── engine.py             ← harness-neutral decisions: session_start, prompt, pre_tool, post_tool, stop
│       ├── classify.py           ← read / write / unknown for tool calls and Bash commands
│       ├── lint.py               ← the gate (same checks as CheckCompleteness can decide mechanically)
│       ├── state.py              ← ~/.isa layout, project keys, per-session state, prompt log
│       ├── yamlish.py            ← the YAML subset ISA files use (no PyYAML)
│       ├── cli.py                ← `isa ls|new|where|lint|hook`; the Claude Code adapter lives here
│       └── protocol.md           ← the text injected into every session
├── adapters/pi/isa.ts            ← pi extension → `isa hook pi` (installed to ~/.pi/agent/extensions/)
├── install.py                    ← install / --uninstall / --dry-run for both harnesses
├── tests/                        ← unit + end-to-end tests of the hooks, classifier, installer, YAML, lint parity
├── tools/
│   └── lint_isa.py               ← wrapper around runtime/isa/lint.py (repo convenience)
└── future/
    ├── MEMORY.md                 ← Future A: how LifeOS learns from ISAs today + target design
    ├── STATUSLINE.md             ← Future B: data contract for an ISA status line
    ├── project-isa/              ← Future C: project ISA idea, what was removed, the Seed workflow
    └── JEV.md                    ← Future D: where TypeSafe/Jev judgments plug into the skill
```

## Install on a fresh machine

```bash
python3 install.py --dry-run   # see what changes
python3 install.py             # install / update (idempotent)
python3 install.py --uninstall # remove everything except the ISAs in ~/.isa
```

Needs `python3` (standard library only) and, for pi, the pi agent at `~/.pi/agent`. The installer copies the runtime and the skill, links `~/.local/bin/isa`, merges hook entries and permissions (`Bash(isa:*)`, `Read`/`Edit(~/.isa/**)`, `Read(~/.claude/skills/ISA/**)`, `additionalDirectories: ~/.isa`) into `~/.claude/settings.json` — keeping every other entry and backing the file up first — and copies the pi extension. New sessions are gated from the start; a running Claude Code session picks the hooks up live.

The skill still loads from its description, and can be called directly (`Skill("ISA", "scaffold from prompt: <...> at tier E3")`), but nothing depends on that any more: the injected protocol tells the model to read `SKILL.md` whenever it writes an ISA.

## Where ISA files go

| Kind | Path |
|------|------|
| Task ISA | `~/.isa/<project>/{YYYYMMDD-HHMMSS_kebab-slug}/ISA.md` |
| Ephemeral slice | `~/.isa/<project>/{slug}/_ephemeral/<feature>.md` |
| Hook state | `~/.isa/_state/` (sessions, raw prompt log, `errors.log`) |

`<project>` is the git work-tree root (or the directory) relative to `$HOME`, with `/` → `-`: `~/dev/jolo-isa` → `dev-jolo-isa`. `isa ls` lists the current project's ISAs, `isa ls --all` every project's. This replaces LifeOS's `~/.claude/LIFEOS/MEMORY/WORK/{slug}/ISA.md`. The first export used `~/.claude/isa/`, but Claude Code treats everything under `~/.claude/` as sensitive and blocks writes there, so the home moved out. Override with `ISA_HOME`.

## Enforcement

One engine (`runtime/isa/engine.py`), two thin adapters. Every decision is deterministic code — no model calls in hooks — and each hook runs in < 50 ms.

| Step | Claude Code hook | pi event | What the engine does |
|------|------------------|----------|----------------------|
| Protocol known | `SessionStart` (every source) | `before_agent_start`, first run | Injects `protocol.md` (~20 lines), the session's bound ISA and this project's open ISAs. After compaction it re-injects the Goal and open ISCs. |
| Verbatim goal | `UserPromptSubmit` | `before_agent_start` | Logs the raw prompt. `stated_goal` must be a substring of a logged prompt (checked once, then remembered next to the ISA). |
| Done written first | `PreToolUse` (all tools) | `tool_call` → `block` | Refuses any `write`/`unknown` call until an ISA is bound **and** passes the articulation lint. Reads, ISA-folder writes, and temp-dir writes outside the project always pass. |
| Binding | `PostToolUse` | `tool_result` | Writing/editing `~/.isa/**/ISA.md` binds it to the session (no session id reaches the model). |
| ISA kept true | `PostToolUse` | `tool_result` → appended text | Lints every ISA edit and feeds the errors back; nudges every 5 project changes without an ISA update; nudges on failed commands. |
| No false "done" | `Stop` (exit 2) | `agent_before_settle` → `continue: true` | Blocks once per prompt if project files changed after the last ISA edit, or the ISA fails lint / the close gate. The second time it lets the turn end with a visible warning. |

Classification (`classify.py`): file tools are judged by path (project / temp / ISA folder); Bash commands are tokenized and each segment judged — an allowlist of read-only commands and read-only `git`/`gh` subcommands, known mutators (`rm`, `git commit`, `npm install`, redirects to project files, `sed -i`, …), and everything else `unknown` (gated before an ISA exists, not counted as staleness). MCP tools are judged by verb in the tool name. A project that lives under `/tmp` is still a project. The agent's own memory folder (`~/.claude/projects/*/memory/`) is agent state, like the ISA folder: never gated and never counted as a change, even when the project is `~/.claude` itself.

Failure policy: a hook that crashes fails **open** with a user-visible message and a line in `~/.isa/_state/errors.log` (a gate bug must not stop all work on the machine). pi blocks tools when a `tool_call` handler throws, so the extension catches its own errors.

There is no self-exemption: the model can't switch the gate off. A trivial change costs an E1 ISA (`## Goal` + `## Criteria` with one `Anti:`).

## What was kept, changed, dropped

### Kept as-is

- The 14-section locked order and the E1–E5 tiers (the gate itself now runs at two moments — see Changed).
- The three-guardrail taxonomy, and the `Anti:`, `Antecedent:` and `Bridge:` criteria.
- The Splitting Test, the one-probe-per-ISC rule, and the coverage gate (there are no count floors).
- ID stability and tombstones.
- The four-part Changelog, with partial entries refused.
- Verbatim capture of the stated goal (`stated_goal`, the 4 detection signals, the minimum-content rule) and the ambiguity check (at most 3 questions, `proceed` accepts defaults).
- Ephemeral slices and a deterministic Reconcile.
- All 12 examples, brought up to the spec (see Changed).

### Changed

| What | LifeOS | Export |
|------|--------|--------|
| Task ISA path | `LIFEOS/MEMORY/WORK/{slug}/` | `~/.claude/isa/{slug}/` |
| Project ISAs | Second home `<project>/ISA.md`, E3 floor, Seed workflow | **Removed.** Task ISAs only; `project:` stays as an optional label. Kept as a possible future feature in `future/project-isa/` (with the Seed workflow). |
| Voice notification | Required `curl localhost:31337/notify` in SKILL.md and every workflow | Removed. SKILL.md keeps a one-line text notice. Workflow steps start at **Step 2** because Step 1 was deleted; I kept the numbering so cross-references like "Step 3.5" still resolve. |
| Interview eligibility | `INTERVIEW_ELIGIBLE` hint from `TheRouter.hook.ts` (already deleted in LifeOS) | Tier E3 or higher asks questions; E1/E2 get a one-line flag instead |
| Goal-signal mismatch check | Compared against `GOAL_SIGNAL` from the router hook | Compared against the prompt itself |
| Version guards (`v6.4.0+ ISAs only`, legacy v6.x keys) | Present | Removed. A fresh install has no legacy ISAs. |
| Vocabulary | `principal_stated_goal` (+ `_source`/`_signal`/`_locked`), "principal", "euphoric surprise", "Bitter Pill discipline" | `stated_goal` (+ same suffixes), "user", "delight", "minimal-structure discipline" — in the skill and the examples |
| Frontmatter | Also had `effort_source`, `mode`, optimize-mode fields, `algorithm_config`, `response_mode`, density keys, `capabilities_invoked` | Core 8 fields plus the optional goal, hierarchy, continuation and journey fields (SKILL.md § Frontmatter) |
| Resume after complete | Done by a hook (`ISASync`: body-hash compare → `phase: learn`, `iteration+1`, Decisions row) | A **written rule** the model follows (SKILL.md § Lifecycle rules). `frozen: true` still opts out. |
| Test Strategy shape | Three conflicting shapes: a table in SKILL.md, a table with different column order in IsaFormat.md, and YAML lists with free-form types in all the examples. Probe types were tied to LifeOS skills. | **One shape: the YAML list the examples already use**, with keys `isc`, `anchors_to`, `type`, `check`, `threshold`, `tool`. Types `unit-test`, `property`, `bash`, `manual`, `screenshot`, `eval` are preferred; specific labels are allowed. The `property` entry shape and the E3+ "pure function → property test" rule are kept. |
| Picking a tier | Once decided by the LifeOS Algorithm, which dropped tiers in v8.4.0, so nothing chose one anymore | SKILL.md § Picking the tier: a one-line guide per tier, E3 when unsure, the user's call wins, and a tier change is logged as `refined:` |
| Frame-drift check (**new rule, not ported**) | v6.8 VERIFY-time "T1/T2/T3" check, undocumented and gone by v8.4.0; only ISC anchoring remained | Before `complete`, re-read the verbatim goal against the finished result and write `- Goal: yes\|no — <evidence>` in Verification. The latest Goal line must be `yes`. Wired into SKILL.md § Close, IsaLoop rule 1, IsaFormat § Verification, CheckCompleteness Step 5c, Append. |
| `interview_invoked` / `interview_ran` / `context_sufficient` | One flag, `interview_invoked`, set only by Scaffold — so the E5 "Interview ran" gate had nothing real to check, and Scaffold's 3 ambiguity questions would have counted as the Interview | `interview_invoked` = Scaffold's ambiguity questions; new `interview_ran: <ISO>` = the Interview workflow was offered (set when its first question is asked, so declining it can't make an E5 ISA unclosable — the outcome goes in `context_sufficient`). Interview also sets `context_sufficient: true` when it finishes with answers. |
| Completeness gate timing | One check "at the tier", run right after Scaffold — E4 demanded a Changelog (refuted beliefs) before any work, E5 demanded the Interview before it could run; both pushed the model to invent content | **Two moments.** `articulation`: sections 1–11 only. `close`: also Decisions / Changelog / Verification. Changelog at E4+ close can be replaced by a `no belief refuted this run` Decisions row. Verification is required at close at every tier. Goal-literal check runs at articulation only (the prompt may be gone later). Anchoring applies from E2 (E1 has no Test Strategy). |
| Waive / defer | "User waived it in Decisions" and `[DEFERRED-VERIFY]` mentioned but never given a format; Append refused the Goal line while a waived ISC was open | `waived: ISC-N — <reason>` (user only) and `- ISC-N: [DEFERRED-VERIFY] — <why> — follow-up: <what>` defined in IsaFormat + Append; waived ISCs leave the `progress` denominator; deferred ones block close unless waived |
| Features shape | Pipe-table notation in SKILL.md / IsaFormat vs YAML lists in all examples | YAML list (`name`, `description`, `satisfies`, `depends_on`, `parallelizable`), same as the examples |
| `progress` counting | "checked / total ISCs", undefined for nested and bridge ISCs | Leaf ISCs in Criteria + Bridge Criteria; parents not counted (ticked once all their leaves are); dropped and waived excluded from N |
| Anti-criteria at E1 | Soft in CheckCompleteness, "required at every tier" everywhere else | Hard at every tier |
| Bridge ISCs & slice deferrals | Append accepted Verification only for `## Criteria` IDs (bridge ISCs could never close); Reconcile dropped a worker's `[DEFERRED-VERIFY]` lines | Append accepts `## Bridge Criteria` IDs; Reconcile carries Deferred lines over without flipping |
| Reconcile safety | "Idempotent" claimed but Decisions / Changelog / Deferred lines were re-appended on any rerun; master Decisions copied into a slice as context came back as duplicates | Entries already in master (verbatim, or Decisions compared without the `[from <feature>]:` prefix) are skipped, so reruns after a partial merge add nothing |
| Gate precision | Granularity and Test Strategy coverage checked on every ISC, flagging nested parents and tombstones | Both apply to non-dropped leaf ISCs only |
| Ephemeral slices | No frontmatter, yet Append always updated `updated` / `progress`; slices also got an empty Verification section | Append skips frontmatter on slices (Reconcile recomputes master's); Verification appears with the first entry |
| Scaffold questions vs Interview | Interview listed Scaffold's ambiguity check as one of its invocations, so the 3 quick questions could set `interview_ran` and pass the E5 gate | Scaffold asks its own questions ("Question mechanics"), recorded as `interview_invoked` only; Interview.md says it is not used for them |
| The Algorithm | `LIFEOS/ALGORITHM/v8.4.0.md`, 15 completion rules plus LifeOS telemetry, audits and agents | `References/IsaLoop.md`: the same 15 rules minus LifeOS plumbing, plus the phase table and the nudge questions as standing questions |
| Examples | Written against older specs: probes inline in criterion text, ~94 Test Strategy entries for ~446 leaf ISCs, `progress` values that didn't match the checkboxes, ticked ISCs with no evidence, a comment above the frontmatter, YAML that didn't parse, horizontal Features in `e3-project` | All pass `tools/lint_isa.py`: one Test Strategy entry per leaf ISC (probes moved out of the criteria, except at E1), `progress` recomputed, every tick backed by a Verification line, compound ISCs split with IDs kept (canonical ISC-23/24/25/33, api-migration ISC-7), E5 examples carry `interview_ran`. Canonical now shows `stated_goal` + `anchors_to`; `e3-project` is now a **closed** ISA (waiver, Changelog, `Goal:` line) |
| `IsaFormat.md` / `IsaSystem.md` | Full, including version history, Pulse sync, the `[arch]` harvest tag, optimize mode | Trimmed to the file contract and the concepts |

### Dropped

Pulse and `work.json`; voice; `PROJECTS.md` routing; TELOS (Scaffold now draws Principles from "the user's stated values and past preferences"); the `[arch]` decision harvest; optimize/ideate/loop modes; cross-vendor audit agents (Forge/Cato/Grok), now "an independent second look"; all LifeOS skill bindings in probes (browser automation, hardening, evals); `IsaHtmlMirror.md` and `ISARender.ts` (the HTML mirror); the `CreateSkill` cross-reference.

## Hooks: how LifeOS wired the ISA (for reference)

No hook ever called the skill, and the skill never called a hook. They only met at the file path `…/MEMORY/WORK/<slug>/ISA.md`. None of these hooks were ported as-is; § Enforcement is the redesign (it covers the PreCompact/RestoreContext and LoadContext roles, and replaces the nudges and the VerificationGate idea with the Stop check):

| Hook (LifeOS `settings.json`) | Event | Role | Why it's not ported |
|-----|-------|------|------------------|
| `ISASync` | PostToolUse Write/Edit/MultiEdit | Mirrors frontmatter and criteria to `work.json` (read by Pulse), colors the kitty tab by phase, auto-rewinds a reopened complete ISA, queues the HTML render | Pulse only. The rewind is now a written rule. |
| `CheckpointPerISC` | PostToolUse Write/Edit/MultiEdit | One git commit per ISC that flips to `[x]`, in the repos listed in `~/.claude/checkpoint-repos.txt` | You handle commits yourself |
| `ISARenderOnStop` | Stop | Re-renders `ISA.html` for ISAs completed at least once | HTML mirror dropped |
| `PreCompact` / `RestoreContext` | PreCompact / PostCompact | Re-inject the first 40 lines of the active ISA around compaction | **Best candidate to port.** It keeps "done" in context through long runs. |
| `LoadContext` | SessionStart | Lists active ISAs with their progress | Candidate, together with the status line |
| `SessionCleanup` | SessionEnd | Forces `phase: complete` on the session's ISA | Harmful: it marks unverified work complete |
| `WorkCompletionLearning` | SessionEnd | Dumps the ISA criteria to `MEMORY/LEARNING/` | See `future/MEMORY.md` |
| `AlgorithmNudge` (via `PostToolObserver`) | PostToolUse / PostToolUseFailure | "stale ISA", "late ISA" and "probe failed" nudges | Now standing questions in `IsaLoop.md`. Note that `PostToolObserver` was never registered in LifeOS's `settings.json`, so only the probe-fail nudge ever ran there. |
| `VerificationGate` | Stop | Blocks done-claims that lack evidence. ISA edits don't count as evidence. | Belongs to the LifeOS output contract, not to the ISA |

## Review of what was cut from IsaFormat.md / IsaSystem.md

Each removed block was checked against one question: does anything in the skill, the workflows, or the completeness gate depend on it?

| Removed | Verdict | Why |
|---------|---------|-----|
| Version-history paragraphs, "Naming History" detail | Clutter | Changelog of LifeOS itself; no rule depends on it |
| `effort` values `standard…comprehensive` | Clutter (stale) | The skill and gate use E1–E5; the old names were a leftover |
| `effort_source`, `mode:` (iterate/optimize/ideate/loop) | Clutter | Set by LifeOS commands/modes; nothing in the skill reads them |
| Density keys, `context_checks_fired`, `frame_drift*` | Clutter (keys) | Already deleted in LifeOS; the gate grades only `context_sufficient` and `interview_ran` (`interview_invoked` is recorded, not graded). The *idea* behind frame-drift came back as a new rule: the `Goal:` verification line (see Changed) |
| `response_mode`, `algorithm_mode`, `capabilities_invoked` | Clutter | Pulse badges / retired router |
| Optimize mode: metric/eval fields, `algorithm_config`, `## Experiments`, guard-rail semantics | Clutter for now | A separate way of using ISAs (autonomous metric optimization) where ISCs become invariants. Nothing else needs it; re-add it as an extension if you ever want that mode |
| Legacy `## Context` section, bracket tags `[F]/[S]`, `ISC-A-N` numbering | Clutter | Pre-v5 formats; a fresh install has no such ISAs |
| "Goal optional for tiny tasks" | Clutter (contradicted) | The gate requires Goal even at E1 |
| Test Strategy per-type schema, `bun-property` entry shape, E3+ "pure function → property test" rule | **Needed, restored** | Without them the `property` type had no defined shape. Now in IsaFormat § Test Strategy |
| Features `intelligence` column | Clutter | LifeOS per-task model routing |
| `isa run` harness reference | Moved | Never built in LifeOS; kept as an idea under "Later" |
| `[arch]` decision tag | Moved | It's a memory-capture signal, so it now lives in `future/MEMORY.md` |
| Sync pipeline (ISASync → work.json → Pulse) | Clutter | Only the principle stays: the model writes, everything else reads |
| IsaSystem: twelve-section table, tier gate copy, workflows table | Clutter (duplicate) | Stale copies of what's in SKILL.md / IsaFormat |
| IsaSystem: relationships to LifeOS subsystems | Replaced | By "What reads the ISA" (loop, status line, memory) |

## Open notes

1. **Examples are checked mechanically.** Run `python3 tools/lint_isa.py skill/ISA/Examples/*.md` after any change to them or to the gate rules; expected: every file `ok`. The linter covers what a script can decide (sections, tier gate, Test Strategy coverage, `progress`, ticks vs evidence, close rules); atomicity and the honesty of a `Goal:` line stay judgment calls. It warns, without failing, on criteria over 20 words — about 60 remain in the E4/E5 files. No example is part of a hierarchy, so Dependencies / Bridge Criteria are shown nowhere yet.
2. **Criteria heading.** Write `## Criteria`. A future parser (status line) should also accept `## ISC Criteria` and `## IDEAL STATE CRITERIA`, which the LifeOS tooling emitted.

## Later (ideas noted, not planned yet)

- **`isa run` harness.** A CLI that reads `## Test Strategy`, runs each `tool:` command, compares the result to its `threshold:`, and reports pass/fail per ISC. That turns an ISA into a test suite you can run. LifeOS planned it but never built it. The YAML Test Strategy shape in `IsaFormat.md` is its input contract.
- **`[arch]` decision tag.** Recorded as an input for Future A in `future/MEMORY.md`.

## Source provenance

Exported 2026-09-22 from a LifeOS 7.1.1 install:

- skill `ISA` v1.0.13
- `IsaFormat.md` v1.5.19 (spec v2.13.0)
- `IsaSystem.md` v1.0.20
- `IsaHierarchy.md` v1.0.0
- Algorithm v8.4.0

## Working rules for this folder

- What installs: `skill/ISA/`, `runtime/`, `adapters/pi/isa.ts` (via `install.py`). `future/` and this file are design notes.
- Run the tests before installing: `python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install` and `node --test adapters/pi/test/extension.test.ts`. With PyYAML on `PYTHONPATH`, also `tests/test_yamlish.py` and `tests/test_lint_parity.py`.
- Keep `runtime/` standard-library only (`python3 tests/check_stdlib.py runtime/`).
- Keep it free of LifeOS: no `LIFEOS/` paths, no `localhost:31337`, no personal data. Check with `rg -n -i 'lifeos|31337|MEMORY/WORK|\btelos\b|\bpulse\b' skill/`. Expected: zero hits. Provenance lives only in this file (§ Source provenance), never inside `skill/`.
- When the skill's prose and `References/IsaFormat.md` disagree, fix both on purpose and note it here.
