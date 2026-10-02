# ISA skill — standalone export

This folder is a port of the **ISA (Ideal State Artifact) skill** out of LifeOS, the personal AI setup it was built in, so it can run on a fresh Claude Code install with none of LifeOS present. Working here means refining the export. It is not a LifeOS checkout.

## Objective

1. **Port the ISA skill.** One markdown file (`ISA.md`) per task states what "done" means as testable criteria. The model writes it at the start and keeps it updated as the work goes.
2. **Keep the core ISA rules** (file shape, lifecycle, the five workflows) and the specs the skill directly depends on. Those specs are refined later.
3. **Drop all LifeOS infrastructure:** the Pulse dashboard, voice notifications, the `PROJECTS.md` routing, the LifeOS status line, the router and nudge hooks, and the `MEMORY/WORK` paths.
4. **Enforce it in every session.** A skill loads only when the model decides to, so hooks do the deciding: Claude Code hooks (user scope) and a pi extension call one shared engine. Every prompt is looked at once, with no model call (clear work → the session is ON; an unsure prompt → the model writes an ISA or says `ISA: not needed — <reason>`); while ON, changes wait for an ISA that passes the gate, the `isa` commands own the ISA's state (ticks, evidence lines, `progress`, `phase: complete`), and a turn can't end without an ISA or with an unproven claim. See § Enforcement and `future/SPEC-v2.md`.
5. **Future, not built yet:**
   - A: memory. Learn from completed ISAs and reuse those learnings when scaffolding new ones, with the user approving each item. See `future/MEMORY.md`.
   - B: an "ISA status" status line. The data side is built (`isa status --json`, `runtime/isa/status.py`); the Claude Code renderer lives in `~/dev/progress-outline`. See `future/STATUSLINE.md`.
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
│       ├── engine.py             ← harness-neutral decisions: session_start, prompt (the gate), pre_tool, post_tool, stop
│       ├── fit.py / fit.md       ← the gate's free pre-filter (yes / no / unsure → the model declares) + what it protects
│       ├── classify.py           ← read / isa-cmd / unknown / write / isa-shell-edit for tool calls and Bash commands
│       ├── lint.py               ← the gate as a pure file check (tools/lint_isa.py uses it on the examples)
│       ├── rules.py              ← lint rules that need the ledger or the prompt log (downgrades, waiver quotes, asks)
│       ├── commands.py           ← `isa new | verify | close | lint`: the only writers of an ISA's engine-owned state
│       ├── isafile.py            ← engine writes: ticks, generated Verification lines, progress, nested parents
│       ├── evidence.py           ← the evidence ledger and proof status (proven / unproven / self-attested)
│       ├── fingerprint.py        ← tree fingerprint of a probe root (temp-index `write-tree`, or a capped walk)
│       ├── problems.py           ← the Stop problems as stable codes, and the `blocked` escalation in the ledger
│       ├── state.py              ← ~/.isa layout, project keys, per-session state, prompt log
│       ├── yamlish.py            ← the YAML subset ISA files use (no PyYAML)
│       ├── changes.py            ← did an `unknown` shell command change project files? (git status + mtimes)
│       ├── config.py             ← ~/.isa/config.json (`ask_without_isa`, `jev`; both default on); a broken file means the defaults
│       ├── jev.py / jev/         ← Jev through the `jev` CLI (jev-kit): deadlines, parsing, outage messages + the 4 ISA presets
│       ├── logs.py               ← debug log location and `isa purge-logs` (day files older than 7 days; never state)
│       ├── status.py             ← read-only view of a session's mode and bound ISA (`isa status`), for status lines
│       ├── cli.py                ← `isa ls|new|where|lint|fit|verify|close|status|purge-logs|hook`; the Claude Code adapter lives here
│       └── protocol.md           ← the ON block injected when a session turns ON
├── adapters/pi/isa.ts            ← pi extension → `isa hook pi` (installed to ~/.pi/agent/extensions/)
├── install.py                    ← install / --uninstall / --dry-run for both harnesses
├── tests/                        ← unit + end-to-end tests of the hooks, gate, commands, fingerprint, lint rules, installer
├── tools/
│   └── lint_isa.py               ← wrapper around runtime/isa/lint.py (repo convenience)
└── future/
    ├── MEMORY.md                 ← Future A: how LifeOS learns from ISAs today + target design
    ├── STATUSLINE.md             ← Future B: data contract for an ISA status line
    ├── project-isa/              ← Future C: project ISA idea, what was removed, the Seed workflow
    ├── JEV.md                    ← Future D: where TypeSafe/Jev judgments plug into the skill
    └── SPEC-v2.md                ← the v2 design: gate, commands, evidence, rules (implemented M1–M7)
```

## Install on a fresh machine

```bash
python3 install.py --dry-run   # see what changes
python3 install.py             # install / update (idempotent)
python3 install.py --uninstall # remove everything except the ISAs in ~/.isa
```

Needs `python3` (standard library only) and, for pi, the pi agent at `~/.pi/agent`. The installer copies the runtime and the skill, links `~/.local/bin/isa`, merges hook entries and permissions (`Bash(isa:*)`, `Read`/`Edit(~/.isa/**)`, `Read(~/.claude/skills/ISA/**)`, `additionalDirectories: ~/.isa`) into `~/.claude/settings.json` — keeping every other entry and backing the file up first — and copies the pi extension. New sessions are gated from the start; a running Claude Code session picks the hooks up live.

The skill still loads from its description, and can be called directly (`Skill("ISA", "scaffold from prompt: <...> at tier E3")`), but nothing depends on that any more: when a session turns ON, the ON block tells the model to read `SKILL.md` first.

## Where ISA files go

| Kind | Path |
|------|------|
| Task ISA | `~/.isa/<project>/{YYYYMMDD-HHMMSS_kebab-slug}/ISA.md` |
| Ephemeral slice | `~/.isa/<project>/{slug}/_ephemeral/<feature>.md` |
| Hook state | `~/.isa/_state/` (sessions, prompt log with cwd/project/context, the evidence ledger, the debug log `logs/YYYY-MM-DD.jsonl`, `errors.log`) |

`<project>` is the git work-tree root (or the directory) relative to `$HOME`, with `/` → `-`: `~/dev/jolo-isa` → `dev-jolo-isa`; `$HOME` itself is `_home`. Only `_state` is reserved. `isa ls` lists the current project's ISAs, `isa ls --all` every project's. This replaces LifeOS's `~/.claude/LIFEOS/MEMORY/WORK/{slug}/ISA.md`. The first export used `~/.claude/isa/`, but Claude Code treats everything under `~/.claude/` as sensitive and blocks writes there, so the home moved out. Override with `ISA_HOME`.

## Enforcement

One engine (`runtime/isa/engine.py`), two thin adapters. Every hook decision is deterministic code: no hook and no `isa` command calls a model or opens a network connection (SPEC-v2 § 11). Hooks never run probes and never write an ISA; the `isa` commands do both. Design and rationale: `future/SPEC-v2.md`.

**The gate and the session mode.** Each prompt is looked at once: *is this a request for work with a checkable end state — something that will be either done or not done — rather than a question or a conversation?* The free pre-filter (`fit.py`) answers the clear cases: greetings and thanks → no (OFF), a work verb with an object or an explicit ISA mention → yes (ON, with the ON block). Everything else is `unsure` (questions, explanations, a short "go" that means what it approves) and is left to the running model: the hook injects one line asking it to write the ISA, or to start its answer with `ISA: not needed — <one-line reason>`. Stop checks that line as a string in the last assistant message (Claude Code: `last_assistant_message`, else the transcript; pi: the adapter sends it), and refuses once when there is neither an ISA nor the line. The user sees `ISA: ON|OFF|unsure — <reason>`.

**Asking the user before going on without an ISA** (on by default; `{"ask_without_isa": false}` in `~/.isa/config.json` turns it off, and a missing or broken config keeps it on — `config.py`). For an unsure prompt the model wants to answer without an ISA, the user is asked *"ISA is not enabled for this prompt (<reason>). Continue?"* — **Continue without ISA** (default) or **Enable ISA**. Claude Code: the injected line tells the model to ask with `AskUserQuestion`; the hooks read the answer from the tool call (PostToolUse), and Stop accepts the declaration only once the user was asked (refused once otherwise). pi: the extension asks with `ctx.ui.select` when Stop sees the declaration, and reports the pick (engine event `ask_answer`). **Enable ISA** switches the session ON: the ON rules apply and an ISA is required. Nobody to ask — `claude -p` (hooks see `CLAUDE_CODE_SESSION_ATTENDED=0` / `CLAUDE_CODE_ENTRYPOINT=sdk-cli`), pi without a UI, or a failed question tool: the declaration stands. Each step logs `ask`, `asked`, `choice` and the model's `reason`.

A session starts OFF. It turns ON for good on a yes, on a `write` call (refused: the change waits for an ISA), on an `unknown` shell command that turns out to have changed project files, or when an ISA is bound. OFF sessions get nothing from the engine; the user sees `ISA: OFF — <reason>` / `ISA: ON — <reason>`. While the bound ISA is `complete`, new prompts go through the pre-filter again: a yes needs a new ISA (or a reopen) before the turn ends, an unsure one a new ISA, a reopen or the declaration line. `ISA_MODE=off|on` is the user's override (off: every hook silent; on: ON from the first prompt). A v1 session file reads ON exactly when it has an open bound ISA.

| Step | Claude Code hook | pi event | What the engine does |
|------|------------------|----------|----------------------|
| ON block | `SessionStart` (when ON) / `UserPromptSubmit` (on the OFF → ON switch) | `before_agent_start` | Injects `protocol.md`: read SKILL.md, then `isa new`, write the content, `isa lint`, `isa verify --red`, `isa verify`, `isa close`. On resume or after compaction: also the bound ISA, its Goal and open ISCs, and the items still `blocked`. |
| The gate | `UserPromptSubmit` | `before_agent_start` | Logs the prompt (with cwd, project, previous assistant message), runs the pre-filter while OFF or after a closed ISA, records the mode; on `unsure`, injects the declaration line. Every ISA hook has the same 15 s limit (Claude Code settings; pi `ISA_HOOK_TIMEOUT_MS`). |
| Done written first | `PreToolUse` | `tool_call` → `block` | While ON: refuses `write` / `unknown` calls until an ISA is bound and passes the articulation lint. `isa new|lint|verify|close` (`isa-cmd`) always pass. |
| Ownership | `PreToolUse` | `tool_call` | Refuses a model Write/Edit of an ISA that ticks a box, adds or changes a generated Verification line, sets `phase: complete`, changes `root`, or writes a wrong `progress` (unticking is allowed). Refuses a shell command writing onto an ISA.md (`isa-shell-edit`). The ledger is never written by a tool. |
| Binding | `PostToolUse` | `tool_result` | `isa new` (the path it printed) or a Write/Edit of `~/.isa/**/ISA.md` binds the ISA and switches the session ON. |
| ISA kept true | `PostToolUse` | `tool_result` → appended text | Lints every ISA edit (on the text the commands would leave — `progress` and orphaned lines are recomputed, never reported) plus the ledger-aware rules; nudges every 5 project changes without an ISA edit; a failed `isa verify` asks "claim wrong or code wrong?". |
| No false "done" | `Stop` (exit 2) | `agent_before_settle` → `continue: true` (completed runs only) | An unsure prompt still OFF: an ISA bound, or the `ISA: not needed — <reason>` line, else refuse once. While ON: no bound ISA → refuse, even on a turn that changed nothing (a review is work too; the clarify-first scaffold — Goal + questions + `context_sufficient: false` — ends the turn that created it only). Then, on turns where something happened: lint errors, a tick without a passing `isa verify` (or `--attest`) row, a tick out of dependency order, a `complete` ISA not written by `isa close`, every criterion ticked while still open. Once per prompt; the second time the turn ends with a warning and the open problems become `blocked`. |

**The commands own the state.** `isa new <slug> --goal "<span>"` scaffolds the frontmatter (`root`, `stated_goal` checked against the project's logged prompts with Scaffold's minimum-content rule, `asks: []` for the model to fill with verbatim spans — lint checks them against the ISA's sessions, and the first `isa verify` snapshots them) and the hook binds it. `isa verify` runs probes from `root` (or an entry's `cwd:` / `root:`), records each run in the evidence ledger (`~/.isa/_state/evidence/`), ticks what passed (Feature dependency order applied within the run), unticks what regressed, and writes the generated Verification line; `--attest "<evidence>"` ticks a self-attested ISC; `--red` records the failing baseline. `isa close` re-runs every probe and writes `phase: complete` only when all pass without changing the tree and `lint --close` holds — that re-run is what makes a close fresh, so no hook tracks freshness. `isa lint` recomputes `progress`, nested parents and orphaned lines first. All of them refuse to run probes before the ISA passes articulation. Probes run with the caller's environment minus its `ISA_*` variables (`ISA_HOME` stays). Run `isa verify` / `isa close` with a long Bash timeout (600000 ms): Claude Code's default 120 s can stop a long close halfway.

**Jev (on by default, never blocking).** With the `jev` CLI on PATH (`ISA_JEV_BIN` overrides), the engine asks Jev, through jev-kit as consumer `isa`, with this repo's presets first on `JEV_KIT_PRESETS` (`runtime/isa/jev/`: `isa-gate`, `isa-probe`, `isa-goal`, `isa-ask`). `{"jev": false}` in `~/.isa/config.json` means no call at all. The calls:
- **Gate:** an `unsure` prompt; an answer ≥ 0.8 turns the session ON with the ON block (1.5 s deadline).
- **Probes:** the first `isa verify` of each probe that can't be seen failing first; once per (ISC, probe text), with a warning below 0.5 (3 s).
- **Close:** `isa close` asks about the goal and each ask line and prints them under "Jev (advisory — never blocks the close)" (3 s).

Every call is killed at its deadline, never retried (jev-kit's breaker decides about later attempts), applied add-only, and logged as a `jev` row. A call that was not served falls back to the baseline and tells the user once per session and kind (hooks), or prints one `Jev:` line (commands; the ON block asks the model to relay it): *"Jev credit looks exhausted (<detail>). ISA keeps working on its baseline checks. To fix: top up TypeSafe credits, then run `jev reset`; or stop the attempts with `jev disable` (every jev-kit consumer) or `"jev": false` in ~/.isa/config.json (ISA only)."*, the daily-budget message (exit 5), or *"Jev unavailable (<reason>: <detail>)…"*. Measured live on 2026-10-02: 446–513 ms per call. `isa status` shows the session's last Jev call.

**Debug log.** Every hook event and every `isa new|lint|verify|close|purge-logs` writes one JSON row to `~/.isa/_state/logs/YYYY-MM-DD.jsonl` (`logs.py`): step, harness, session, prompt id, project, decision, ms, plus step details (pre-filter verdict and mode change, tool and kind, Stop problem codes, the declaration found or not, a command's ISCs passed/failed and exit code). No prompt or ISA text is copied in. A write failure is swallowed — a log never changes a hook's result. `isa status` reads the session's last gate verdict from it. The user reviews these logs from real sessions (SPEC-v2 § 11.6); `isa purge-logs [--days 7] [--dry-run]` deletes day files older than 7 days, run by hand.

**Evidence.** Each ledger row carries the tree's fingerprint (`fingerprint.py`: a temp-index `git write-tree` — content only, ignored files out, the real index untouched — or a capped walk outside git). A batch that changes the tree is reported, recorded as `changed`, and refused by `isa close`. Red-then-green: a behaviour/http/schema ISC at E2+ ticks plainly only after a failed red run of the same probe text on a different tree; otherwise it is marked `(no red baseline)` and listed at close — never blocked. When Stop lets a turn end with problems open, they are appended to the ledger as `blocked` keys (`no-isa` lives in the session); `isa verify` / `isa lint` append `unblocked` once a key no longer holds, and `isa close` refuses while one is open.

**Lint rules (spec § 6).** `kind:` on every Test Strategy entry from E2, and the probe types each kind refuses (a `behaviour` claim can't be proven by `manual` or by a grep-only probe); a `risk:` declaration on entries that mention secrets, auth, money, deploys…; `risk: high` can't be self-attested and needs a `second-look:` row at close (as does E4+); a probe downgrade after the first `isa verify` needs a `refined: ISC-N probe downgraded` row; `waived:` quotes the user, checked against the ISA's sessions; each `asks` entry a verbatim span of a prompt of the ISA's sessions, one `- Ask N:` line per ask at close; `fails-when:` on mechanical probes whose ISC can't get a red baseline (Anti, a kind without the red step, `red: exempt`); `class-sweep:` for `class:` entries; `context_sufficient` set from E2. ISAs started before 2026-10-02 get warnings, not errors, for these.

Classification (`classify.py`): file tools are judged by path (project / temp / ISA folder); Bash commands are tokenized and each segment judged — an allowlist of read-only commands and read-only `git`/`gh` subcommands, `isa new|lint|verify|close` (`isa-cmd`), shell writes onto an ISA.md (`isa-shell-edit`), known mutators (`rm`, `git commit`, `npm install`, redirects to project files, `sed -i`, …), and everything else `unknown`. An `unknown` shell command counts as a project change when it actually changed project files (`changes.py`: `git status --porcelain` before and after, or a capped walk outside git). Gitignored files never count. MCP tools are judged by verb in the tool name. A project that lives under `/tmp` is still a project. The agent's own memory folder (`~/.claude/projects/*/memory/`) is agent state: never gated and never counted.

Failure policy: a hook that crashes fails **open** with a user-visible message and a line in `~/.isa/_state/errors.log` (a gate bug must not stop all work on the machine). pi blocks tools when a `tool_call` handler throws, so the extension catches its own errors.

There is no self-exemption: the model can't switch the gate off — only the user can (`ISA_MODE=off`). A trivial change costs an E1 ISA (`## Goal` + `## Criteria` with one `Anti:`).

**Rule 6 and `context_sufficient`.** SPEC-v2 § 2 words rule 6 as "requires `context_sufficient: true`"; lint requires the field to be *set* (true or false), because `false` keeps its v1 meaning — a reasoned default accepted via `proceed` (Scaffold Step 3.5) — and SKILL.md, IsaFormat and the workflows say so.

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

- ~~**`isa run` harness.**~~ Built as `isa verify` (see § Enforcement, "Proven ticks"). It judges by exit code only; `threshold:` stays descriptive, so a non-exit-code threshold must be built into the command.
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
- Run the tests before installing: `python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install tests.test_fit tests.test_status tests.test_evidence tests.test_shell_changes tests.test_feature_order tests.test_home_and_complete tests.test_seamless_projects tests.test_gate tests.test_commands tests.test_fingerprint tests.test_blocked tests.test_red tests.test_lint_v2 tests.test_purge tests.test_declaration tests.test_logs tests.test_ask tests.test_jev tests.flow.test_isa_flow` and `node --test adapters/pi/test/extension.test.ts`. No test calls a model or the real `jev`; `HookCase` drops every inherited `ISA_*` variable and points `ISA_JEV_BIN` at nothing (`tests/test_jev.py` uses a fake `jev`; `ISA_FLOW_LIVE=1 python3 -m unittest tests.flow.test_jev_live` makes six real calls), and the declaration tests put tripwire `claude` / `pi` / `jev` CLIs on PATH that fail the test if a hook calls them. With PyYAML on `PYTHONPATH`, also `tests/test_yamlish.py` and `tests/test_lint_parity.py`.
- The whole-flow test (`tests/flow/test_isa_flow.py`, SPEC-v2 § 9) is live and paid (two Sonnet 5.5 sessions, about $0.30): `ISA_FLOW_LIVE=1 python3 -m unittest tests.flow.test_isa_flow`. It writes `flow/<stamp>/` (articulation and final ISA, timeline, verdict, transcripts, sandbox state) into the `eval-results` worktree at `tests/evals/results/` and commits it there. A run that dies on an API error is neither graded nor committed. Without the switch it is skipped.
- Keep `runtime/` standard-library only (`python3 tests/check_stdlib.py runtime/`).
- Keep it free of LifeOS: no `LIFEOS/` paths, no `localhost:31337`, no personal data. Check with `rg -n -i 'lifeos|31337|MEMORY/WORK|\btelos\b|\bpulse\b' skill/`. Expected: zero hits. Provenance lives only in this file (§ Source provenance), never inside `skill/`.
- When the skill's prose and `References/IsaFormat.md` disagree, fix both on purpose and note it here.
