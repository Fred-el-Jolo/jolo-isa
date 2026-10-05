# SKILL.md split — bring the skill body under the Level-2 budget

Status: **spec, not implemented** (2026-10-05; Q3, Q6, Q7 and Q8 decided the same day, § 8; the e5-enterprise shortening is planned in § 10; framework hardening moved to `future/ISA-HARDENING.md`). Follows the 2026-10-04 dedup pass (`.isa/20261004-180722_shorten-skill-md/`), which removed duplicated wording only: 5797 → 5124 words. This spec covers the next step: moving reference material out of `skill/ISA/SKILL.md` into files one level deep, without losing a fact.

## Contents

1. Goal
2. Budget
3. Inventory
4. Moves
5. Dependencies (incl. 5.1 Claude Code and pi)
6. Acceptance
7. Rollout (phases: rename, pi install, split)
8. Decisions and open questions
9. Out of scope
10. Plan: shorten `Examples/e5-enterprise.md` below 50 KB
11. Hardening the ISA framework → moved to `future/ISA-HARDENING.md`

## 1. Goal

SKILL.md holds only what the model needs on **every** ISA task: the commands and who writes what, the gate behaviour, the frontmatter, the fifteen completion rules, the lifecycle rules, the section and tier gates, and the workflow routing. Everything needed only in some situations (scaffolding from an example, parallel workers, Jev tuning, picking a tier, the guardrail theory) moves to a reference or workflow file that SKILL.md links directly. Every fact stays reachable, and the move is checkable mechanically.

Why it matters more here than for a typical skill: a skill body normally loads only when the model chooses to use the skill. Here the ON block (`runtime/isa/protocol.md`, `engine.py`) tells the model to read SKILL.md at the start of every ON session, so the body is paid on every task.

The same engine serves **Claude Code and pi** (`adapters/pi/isa.ts` forwards the engine's text unchanged), so both harnesses read the same SKILL.md through the same ON-block path. The split must work for both; § 5.1 lists what differs. In pi the budget matters at least as much: pi may run non-Claude models with smaller context windows, and every ON session pays the body.

## 2. Budget

Anthropic's skill guidance (platform.claude.com, *Agent Skills overview* and *Skill authoring best practices*) and the Agent Skills specification that pi implements (agentskills.io/specification, pi `docs/skills.md`), all read 2026-10-05. They agree on every row unless the row says otherwise:

| Guideline | Value | SKILL.md today |
|---|---|---|
| Level-2 body (loaded when triggered) | "Under 5k tokens" (Anthropic); "< 5000 tokens recommended" (Agent Skills spec) | ~8,000 tokens (body 31,925 chars; file 32,430 chars, 5124 words) ❌ |
| Body length | under 500 lines | 259 lines ✅ |
| `name` | ≤ 64 chars, lowercase letters/numbers/hyphens; the Agent Skills spec also requires it to match the parent directory | `ISA` ⚠️ (see § 8, Q3) |
| `description` | ≤ 1,024 chars, what + when, third person | 430 chars ✅ |
| Frontmatter fields | Agent Skills spec: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` (pi also reads `disable-model-invocation`) | also `version`, `effort`, outside the spec ⚠️ (see § 8, Q3) |
| Per-read limit (pi `read` tool) | 2,000 lines or 50 KB (51,200 bytes), whichever comes first; the rest needs an offset read | largest reference: `IsaFormat.md`, 32,924 bytes, 443 lines ✅; but `Examples/e5-enterprise.md` is 59,164 bytes ❌ (§ 8, Q8) |
| References | relative paths from the skill root (Agent Skills spec), one level deep from SKILL.md (both); a TOC on files over 100 lines (Anthropic) | one level deep ✅; 5 files over 100 lines have no TOC ❌ |

Token figures here are estimated at ~4 chars/token. Acceptance (§ 6) uses a character budget so it can be checked offline. Exact counts can come from the token-counting API when a key is at hand.

- **Target A (this spec, required):** body ≤ **23,500 chars (~5,900 tokens, −28%)**. Reached by moving content only; no rule text is reworded.
- **Target B (the guidance's figure):** body ≤ **20,000 chars (~5,000 tokens)**. Moves alone land at ~22.7k, so Target B needs Q1 (~1,500), Q2 (~900) and about 300 more (for example, the encryption-forms list going to IsaFormat with a one-line rule left behind). That is a decision for the user, not part of Target A.

## 3. Inventory

Measured on the working tree at 2026-10-05 (`awk` split on `^## ` + `wc`). Size includes the heading's own section body, not the heading line.

| # | Section | Words | Chars | Needed on every task? |
|---|---|---|---|---|
| 1 | What it is, and why | 201 | 1,271 | No: background |
| 2 | Where ISA files live | 319 | 1,958 | Mostly: paths, the encryption quoting rule |
| 3 | The gate | 585 | 3,379 | Mostly: the bullets yes; Jev tuning no |
| 4 | You write the content; the `isa` commands write the state | 478 | 2,840 | Yes |
| 5 | Frontmatter | 240 | 1,962 | Core fields yes; optional fields sometimes |
| 6 | Completion rules | 840 | 4,868 | Yes |
| 7 | Lifecycle rules (the file is written and updated, never left stale) | 254 | 1,533 | Yes |
| 8 | The Fourteen-Section Body (locked order) | 574 | 3,575 | Table yes; Features/Changelog format notes at write time |
| 9 | Three-Guardrail Taxonomy (Principles vs Constraints vs Anti-criteria) | 153 | 1,028 | No: theory; one line suffices |
| 10 | Tier Completeness Gate (HARD at all tiers) | 365 | 2,324 | Gate table yes; tier-picking table at scaffold time |
| 11 | Workflow Routing | 208 | 1,496 | Routing table yes; call-point list no |
| 12 | ID stability and ephemeral feature files | 280 | 1,894 | ID rule yes; ephemeral mechanics only with parallel workers |
| 13 | Examples | 357 | 2,417 | No: only when scaffolding |
| 14 | References | 101 | 751 | Yes (it is the index of what moved) |
| | **Total** | **5,124** (incl. frontmatter) | **32,430** (file) | |

## 4. Moves

A **move** cuts the text out of SKILL.md and pastes it **verbatim** into the destination. If the destination already says the same thing, the duplicate is dropped there or here, and the drop is recorded. A **pointer** is the one line left behind in SKILL.md. Each destination is linked directly from SKILL.md (one level deep).

| SKILL.md section | Stays in SKILL.md | Moves out | Destination | Est. chars saved |
|---|---|---|---|---|
| What it is, and why | 2 sentences: what an ISA is, the five identities | "Without it…" problem paragraph; the file shape and only-writer sentence | `References/IsaSystem.md` (it already holds the five identities) | ~950 |
| Where ISA files live | Task ISA paths, `isa where`/`ls`, the encryption quoting rule and key rule | The project ISA paragraph (`kind: project`, `ISC-P<n>`, `promote: true`), with a one-line pointer | `References/IsaFormat.md` (new § Project ISA) | ~700 |
| The gate | The four bullets, the OFF→ON paragraph, the `Jev:` relay rule | Jev advice at verify/close, the `{"jev": false}` switch, the `jev_gate` / `jev_quiet` / `jev_doubt` lines | new `References/IsaGate.md` | ~550 |
| You write the content… | All | — | — | 0 |
| Frontmatter | Core fields (`task` … `asks`) and the status-surface paragraph | The `# optional` block (iteration, resumed_at, frozen, stated_goal suffixes, context_sufficient, interview_*, parent/children) | `References/IsaFormat.md` § Frontmatter (merge; IsaFormat wins on contradiction) | ~650 |
| Completion rules | All (see § 8, Q2 for Target B) | — | — | 0 |
| Lifecycle rules | All | — | — | 0 |
| The Fourteen-Section Body | Intro, table, conditional-required note, ISC line format | "Features are vertical slices…" and "The Changelog format is non-negotiable…" paragraphs | `References/IsaFormat.md` § Features / § Changelog (both already state the shape; keep only the sentences IsaFormat lacks) | ~900 |
| Three-Guardrail Taxonomy | One line: "Principles bind the thinking, Constraints the solution space, Out of Scope the vision, Anti-criteria the test surface — derived from Out of Scope plus regression concerns; see IsaSystem." | The table and the derivation paragraph | `References/IsaSystem.md` § Three-Guardrail Taxonomy (already exists; merge the examples) | ~850 |
| Tier Completeness Gate | Two-moment paragraph, the gate table, its footnote, the "Picking the tier" rule sentence, the mid-run tier change rule | The "Looks like / Example" tier table | `Workflows/Scaffold.md` (it picks the tier; its input table already points at "SKILL.md § Picking the tier") | ~650 |
| Workflow Routing | The routing table | "Typical call points" list | `References/IsaLoop.md` § Call points | ~650 |
| ID stability and ephemeral feature files | The ID-stability paragraph (never renumber, `ISC-N.M`, tombstones, why) | The ephemeral mechanics and the Reconcile-determinism paragraph, with a one-line pointer | `Workflows/Reconcile.md` (Reconcile/ephemeral) and `Workflows/Scaffold.md` (ephemeral mode inputs) | ~1,450 |
| Examples | 3 lines: read `canonical-isa.md` first, pick the closest example, the index is `Examples/README.md` | The intro paragraph and the 12-row table | new `Examples/README.md` | ~2,000 |
| References | All, plus the two new files | — | — | −150 (grows) |
| **Total** | | | | **~9,200 → body ~22,700 chars** |

The estimates are within ~10%. The Target A check (§ 6) settles it; if the result is over 23,500, the first fallback is § 8, Q1.

Rules for the moves:

- **Verbatim.** Moved text is not reworded on the way. Rewording is a separate change with its own review.
- **One level deep.** Every new or grown destination is linked from SKILL.md's References list. No destination sends the reader on to a third file for a fact it took over.
- **Paths that resolve in both harnesses.** Pointers use paths relative to the skill root (`References/IsaGate.md`), as the Agent Skills spec asks. Both harnesses tell the model the skill's folder when they load it as a skill: Claude Code's Skill tool announces its base directory, and pi's system prompt lists each skill's `<location>` with the instruction "When a skill file references a relative path, resolve it against the skill directory" (`dist/core/skills.js`, `formatSkillsForPrompt`). But on every ON session the model reaches SKILL.md through the ON block's absolute path instead, where nothing is announced. So SKILL.md's References section opens with one line saying that paths are relative to the folder holding this SKILL.md (`~/.claude/skills/isa/` when installed).
- **No Claude-Code-only instructions in moved text.** The call-point list uses `Skill("isa", "…")` (after the rename), which is a Claude Code tool call. pi's model has no Skill tool: it loads a skill by reading the file, and the user can type `/skill:isa …`, which pi expands to the skill's content (`agent-session.js`, once Phase 2 makes pi discover it). This is the one exception to "verbatim": the list moves to `IsaLoop.md` and gains a harness-neutral lead line, "In any harness: read `Workflows/<Name>.md` and follow it; in Claude Code `Skill("isa", "…")` does the same; in pi the user can type `/skill:isa <request>`." The same goes for anything harness-specific: when a moved line names one harness's tool (`AskUserQuestion`, a `Bash` timeout in ms), it keeps the other harness's form beside it, as § The gate already does ("pi asks by itself").
- **Size per file.** No skill file may grow past what one pi read returns: 2,000 lines and 50 KB. `IsaFormat.md` takes the most (~2,250 chars), which brings it to ~35 KB.
- **TOC.** Every destination over 100 lines gets a `## Contents` list at the top, which the guidance requires. That covers `IsaFormat.md` (443), `Scaffold.md` (227), `CheckCompleteness.md` (187), `Append.md` (121) and `Reconcile.md` (106). `CheckCompleteness.md` and `Append.md` get one even though nothing moves into them, so the skill as a whole meets the guidance.
- **Contradictions.** Where a destination already says something different from the moved text, IsaFormat wins (SKILL.md § References). The difference is resolved on purpose and noted in AGENTS.md, as the working rules require.

## 5. Dependencies

What reads SKILL.md or points into it. Each must still work after the split.

| Where | What it relies on | Action |
|---|---|---|
| `runtime/isa/protocol.md:2` (ON block) | "Read {skill_dir}/SKILL.md first (the contract and the numbered completion rules)" | No change: the contract and rules stay. |
| `runtime/isa/engine.py:280`, `:306` | "read …/SKILL.md, then `isa new <slug>`" | No change. |
| `runtime/isa/engine.py:740` | "read …/SKILL.md and the closest example first" | SKILL.md's Examples pointer must name `Examples/README.md`, so the closest example can be found in one hop. Optionally mention the index in the message too (needs a test update: see below). |
| `runtime/isa/skills.py:35` | Reads a slash command's skill **description** from `SKILL.md` | No change: the frontmatter is untouched. |
| `tests/test_gate.py:85` | Asserts the injected text contains `…/skill/ISA/SKILL.md` | No change unless the engine text changes. |
| `tests/test_declaration.py:57` | Asserts `"SKILL.md"` in the injected context | No change. |
| `tests/test_m11.py:348` | Writes its own fixture SKILL.md | Unaffected. |
| `install.py:196` | `shutil.copytree` of `skill/ISA/` (wholesale) | New files ship automatically; `Read(~/.claude/skills/ISA/**)` already covers them. |
| `skill/ISA/Workflows/Scaffold.md:16` | "see SKILL.md § Picking the tier" | Repoint to its own new tier table. |
| `skill/ISA/References/IsaLoop.md:11` | "SKILL.md § Completion rules" | No change (stays). |
| `skill/ISA/References/IsaFormat.md:9`, `IsaSystem.md:12` | Describe SKILL.md as holding "the workflows" | Reword when touching these files: SKILL.md holds the rules and the routing. |
| `future/JEV.md:57` | "SKILL.md § Continuation vs new task" | **Already stale.** The 2026-10-04 dedup merged that rule into § The gate. Repoint. |
| `future/JEV.md:89`, `AGENTS.md:176` | "SKILL.md § Picking the tier" | Repoint to `Workflows/Scaffold.md` if the table moves; the rule sentence stays in SKILL.md. |
| `future/STATUSLINE.md:26`, `AGENTS.md:174` | "SKILL.md § Lifecycle rules" | No change (stays). |
| `tools/lint_isa.py` on `Examples/*.md` | The examples themselves | `Examples/README.md` is not an ISA. Check that `lint_isa.py Examples/*.md` either skips it or is run on an explicit list; otherwise exclude it. |

### 5.1 Claude Code and pi

| Topic | Claude Code | pi | Consequence for the split |
|---|---|---|---|
| How the skill is found | Installed to `~/.claude/skills/ISA` (`install.py:252`), discovered from its description; `Skill("ISA", …)` loads it and announces its base directory | **Today pi never discovers the skill**: `install.py` copies it only to `~/.claude/skills/`, and pi loads skills from `~/.pi/agent/skills/`, `.pi/skills/`, `~/.agents/skills/`, `.agents/skills/` and the paths in the `skills` array of `~/.pi/agent/settings.json`. pi has full Agent Skills support: it lists each discovered skill's name, description and `<location>` in the system prompt, tells the model to resolve relative paths against that folder, and registers `/skill:<name>` (`dist/core/skills.js`, `system-prompt.js`, `agent-session.js`). Phase 2 (§ 7) adds the skill to that `skills` array | Every pointer must also work as a plain file read from the ON block's path, where nothing announces the folder (§ 4) |
| ON block and gate text | `UserPromptSubmit` / `SessionStart` inject the engine's text | `before_agent_start` injects the same text (`adapters/pi/isa.ts` adds no skill text of its own) | `engine.py:740` ("read SKILL.md and the closest example first") must work in both, so the Examples pointer in SKILL.md names `Examples/README.md` by path |
| Reading a file | `Read`, 2,000 lines by default | `read`, 2,000 lines or 50 KB per call | Per-file size rule (§ 4); the one example over it is § 8, Q8 |
| Permissions | `Read(~/.claude/skills/ISA/**)` covers new files | No permission layer | Nothing to add in either |
| Slash commands | `/ISA` (after the rename, `/isa`) judged by its description (`skills.py`) | `/skill:isa` once Phase 2 lands. `skills.py` scans pi's four folders but not the settings `skills` array, so the gate would not find the description for `/skill:isa` | Phase 2 also teaches `skills.py` to read `skills` from `~/.pi/agent/settings.json` (and the project `.pi/settings.json`) |
| Bash timeout | `timeout` in **ms**; default 120 s, so the skill says 600000 ms | Optional per-call `timeout` in **seconds**; no default, but the model may set one, and a run past it is killed with "Command timed out after N seconds" (`dist/core/tools/bash.js`) | The line must name both units; see § 8, Q7 (decided) |
| `Skill("ISA", …)` in the workflows | Works | No Skill tool | Each workflow's "Invocation" list (`Scaffold.md:7-9`, `Interview.md:9-10`, `Append.md:9-12`, `CheckCompleteness.md:9`, `Reconcile.md:10-11`) only describes callers, and a reader already in the file has arrived, so it is harmless in pi and stays. The exception is the ephemeral header that `Scaffold.md:220` writes into every slice ("Reconcile via `Skill("ISA", …)`"): it instructs a worker, who may run in pi. Give it the neutral form when Scaffold.md is touched in rollout step 3. |
| Tests | `tests/test_gate.py`, `tests/test_declaration.py` | `adapters/pi/test/extension.test.ts` | Both run in § 6, check 11 |

## 6. Acceptance

Each check is a command that exits 0 when it passes. These become the Test Strategy of the implementation ISA.

1. **Budget (Target A).** The SKILL.md body without its frontmatter is ≤ 23,500 chars:
   `test "$(awk 'f>=2{print} /^---$/{f++}' skill/ISA/SKILL.md | wc -c)" -le 23500`. Target B uses 20,000.
2. **No fact lost.** Every line of the fact-token list (`.isa/20261004-180722_shorten-skill-md/facts.txt`, 180 tokens taken from the pre-dedup SKILL.md) is found in SKILL.md **or** in one of the destination files: `SKILL.md`, `References/*.md`, `Workflows/*.md`, `Examples/README.md`.
3. **Moves are verbatim.** Every line removed from SKILL.md (`git diff` `-` lines, ignoring blank lines and pointer lines) appears exactly in some destination file, or is listed in the implementation ISA's Decisions as a dropped duplicate with the line that keeps its meaning.
4. **One level deep.** Every file a pointer names is in SKILL.md's References list, and that list links each new file (`IsaGate.md`, `Examples/README.md`).
5. **TOCs.** Every `.md` under `skill/ISA/References` and `skill/ISA/Workflows` over 100 lines has a `## Contents` heading.
6. **One pi read per file.** Every file the split creates or grows (SKILL.md, `References/`, `Workflows/`, `Examples/README.md`) is at most 2,000 lines and 51,200 bytes (50 KB). The ISA examples are excluded; see § 8, Q8:
   `! find skill/ISA/SKILL.md skill/ISA/References skill/ISA/Workflows skill/ISA/Examples/README.md -name '*.md' | while read -r f; do [ "$(wc -l <"$f")" -le 2000 ] && [ "$(wc -c <"$f")" -le 51200 ] || echo "$f"; done | grep -q .`
7. **No Skill()-only routing.** SKILL.md has no `Skill("ISA"` line left, and `IsaLoop.md`, which receives the call points, gives the harness-neutral form:
   `! rg -qi 'Skill\("isa"' skill/isa/SKILL.md && grep -qF 'read `Workflows/<Name>.md` and follow it' skill/isa/References/IsaLoop.md`
   The workflows' own "Invocation" lines are out of this check (§ 5.1).
8. **Frontmatter unchanged.** The first 6 lines of SKILL.md match `HEAD`.
9. **No dangling anchors.** `rg -n 'SKILL\.md §' skill future AGENTS.md` lists only headings that exist in the new SKILL.md, or bold run-in titles that are still there (`Picking the tier`).
10. **Examples still lint.** `python3 tools/lint_isa.py skill/ISA/Examples/[ce]*.md` (every example, not the README) reports every file `ok`.
11. **Tests.** The full unit list from AGENTS.md § Working rules passes, plus the node tests: `node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts`.
12. **Still free of LifeOS:** `! rg -q -i 'lifeos|31337|MEMORY/WORK|\btelos\b|\bpulse\b' skill/`.
13. **Behaviour, Claude Code (manual, recorded with `--attest`).** In a fresh session with the installed skill, a prompt that turns ON produces an ISA that passes `isa lint` with SKILL.md as the only skill file read before `isa new`. A scaffolding prompt reads `Examples/README.md` and one example.
14. **Behaviour, pi session (manual, recorded with `--attest`).** The same two prompts in a fresh pi session with the extension installed: the model resolves every pointer it follows to a file under `~/.claude/skills/ISA/` (no "file not found" on a relative path), reads no file truncated, and produces a linting ISA. Run it with the model the user runs pi with day to day.

## 7. Rollout (phases: rename, pi install, split)

Three changes, each with its own ISA and commit, in this order. The rename comes first because the pi install needs the final name, and the split comes last so its pi session check (§ 6, check 14) runs on the discovered skill. Paths elsewhere in this spec name today's layout (`skill/ISA`, `~/.claude/skills/ISA`); after Phase 1 read them as `skill/isa`, `~/.claude/skills/isa`.

**Phase 0.** Commit the 2026-10-04 dedup, so each later diff contains only its own change.

**Phase 1: rename to `isa` and conform the frontmatter (Q3, decided).**
1. `git mv skill/ISA skill/isa`; `name: isa`.
2. Frontmatter fields outside the Agent Skills spec: `version` moves under `metadata:` (`metadata: { version: "1.1.0-export.1" }`). Before moving `effort`, check whether Claude Code reads it from skill frontmatter: if it does, keep it (pi warns, does not fail); if not, move it under `metadata` too.
3. Update every reference: 69 occurrences in 28 files (`rg -l 'skill/ISA|skills/ISA|Skill\("ISA"'`, excluding `tests/evals/` and `.isa/`). They include:
   - `engine.skill_dir()` default (`~/.claude/skills/ISA` → `isa`; `ISA_SKILL_DIR` unchanged);
   - `install.py` (target folder, the `Read(~/.claude/skills/isa/**)` permission);
   - `runtime/isa/lint.py`;
   - the five workflows' `Skill("ISA", …)` lines;
   - the root `ISA.md`;
   - AGENTS.md and the `future/` notes;
   - the tests (`test_gate.py:85` path assertion, `test_hooks`, `test_m12`, …) and `adapters/pi/test/extension.test.ts`.
4. Migration in `install.py`:
   - remove an old `~/.claude/skills/ISA` it installed, and its `Read(~/.claude/skills/ISA/**)` permission, backing up `settings.json` first as it already does;
   - `--uninstall` removes both names.
5. Acceptance:
   - `rg -q 'skills/ISA|skill/ISA|Skill\("ISA"'` finds nothing outside `tests/evals/`, `.isa/` and the Changed table in AGENTS.md;
   - the full test list passes;
   - a fresh install leaves only `~/.claude/skills/isa`;
   - `name` passes the Agent Skills rule (`^[a-z0-9]+(-[a-z0-9]+)*$`, equal to the folder name).

**Phase 2: install the skill for pi (Q6, decided).**
1. `install.py` adds `~/.claude/skills/isa` to the `skills` array of `~/.pi/agent/settings.json`:
   - merged, idempotent, the file backed up first, the same way it already installs the pi extension;
   - `--uninstall` removes the entry.
   - One copy serves both harnesses. A second copy under `~/.agents/skills/` was rejected: two copies drift, and other Agent Skills hosts would pick it up unasked.
2. `runtime/isa/skills.py` also reads the `skills` arrays of the global and project pi settings, so a `/skill:isa` prompt is judged with the skill's description like any other slash command.
3. Acceptance:
   - a pi session lists `isa` in its skills, with its location;
   - `/skill:isa scaffold …` expands;
   - `tests/test_install.py` covers the merge, the re-run and the uninstall on a temp settings file;
   - the node extension tests pass.

**Phase 3: the split (this spec).**
1. Open a task ISA (E3) whose Test Strategy is § 6.
2. Create the destinations (`Examples/README.md`, `References/IsaGate.md`, new sections in IsaFormat/IsaSystem/IsaLoop/Scaffold/Reconcile) and add the TOCs.
3. Cut from SKILL.md and leave the pointers.
4. Repoint the anchors in § 5. Fix `future/JEV.md:57` regardless of the split.
5. Apply Q7 and Q8 (§ 8) and the e5-enterprise shortening (§ 10).
6. Run § 6. Then `python3 install.py`, and repeat checks 13 and 14 against the installed copy.
7. Note the split in AGENTS.md (Layout tree: the two new files; "Changed" table: one row).

## 8. Decisions and open questions

**Decided (2026-10-05):**

- **Q3. Rename to `isa`: yes.** `name: ISA` broke both specs (lowercase only; the Agent Skills spec also wants it to equal the folder name), and `version` / `effort` are outside the Agent Skills fields. → Phase 1.
- **Q6. Install the skill for pi: yes.** → Phase 2, through pi's own `skills` setting rather than a second copy.

- **Q7. Same timeout as Claude Code in both harnesses (decided 2026-10-05, the user's call).** pi's `bash` has an optional per-call `timeout` in seconds and no default. A model that sets a short one by habit (60, 120) kills a long `isa verify` or `isa close` halfway, just as Claude Code's 120 s default would. The first proposal said "omit it in pi", but omitting means no bound at all, so a hung probe would hang the session. The same ten minutes in both is simpler and bounds that. The line in SKILL.md and `protocol.md` becomes: "Run `isa verify` and `isa close` with a 10-minute timeout: Claude Code `timeout: 600000` (ms), pi `timeout: 600` (seconds); or in the background when the suite is slow." This is a rule-text change, applied in Phase 3 step 5 with the ON-block text (`tests/test_gate.py` / `test_declaration.py` may assert on it).
- **Q8. `Examples/e5-enterprise.md` over pi's 50 KB read (approved 2026-10-05), plus shortening it below 50 KB (planned, § 10).**
  - **Approved:**
    - `Examples/canonical-isa.md` becomes the E5 reference in `Scaffold.md:30`. It is already E5 (`effort: E5`, `interview_ran` set, all 12 sections), 33 KB, and Scaffold reads it on every run anyway.
    - `e5-enterprise.md` becomes an optional domain example (regulated / compliance work) in `Examples/README.md`.
    - An E5 scaffold no longer reads a second large example: about 15k tokens saved in both harnesses.
  - **Shortening it below 50 KB: approved as a plan (2026-10-05), see § 10.**

**Still open:**

- **Q1. Gate bullets and the injected text.** The hooks already inject situation-specific instructions: the ask wording, the judge line, the Continue pass. Should SKILL.md keep only the rule ("every prompt is judged once; follow the injected instruction; the user decides what isn't a yes") and move the verbatim ask text and the pass details to `References/IsaGate.md`? That saves ~1,500 chars, the largest single step toward Target B. The risk is that the model sees the details only when the hook injects them, which is also exactly when it needs them.
- **Q2. The Teeth column.** It tells the model which rules are self-attested, so it matters for honesty at close. Moving it to IsaLoop saves ~900 chars but separates each rule from how it is enforced. Recommendation: keep it, and prefer Q1 for Target B.
- **Q4. Evaluations.** The guidance asks for at least three evaluations and testing on Haiku, Sonnet and Opus. The repo has one live flow test (Sonnet, `tests/flow/test_isa_flow.py`). pi runs other models (today the user's default is `glm-5.3` via `zai`), which strengthens the case. Should the split be gated on running it before and after, once per harness?
- **Q5. Stale homes in the references.** `IsaFormat.md:44` and `Scaffold.md:24` give ephemeral slices as `~/.isa/<project>/{slug}/_ephemeral/`. In a repo they now live in `<repo>/.isa/{slug}/_ephemeral/` (SPEC-v2 § 13). Fix it when those files are touched in Phase 3?

## 9. Out of scope

- Rewording any rule. Phase 3 is a move, not a rewrite; the only added or changed text is the harness-neutral lead line, the root-path line (§ 4), and the Q7 and Q8 lines.
- Changing the description, the triggers, or the hook and engine behaviour.
- Implementing anything in this file: Phases 1 and 2 and the § 10 shortening are specified only far enough to order and check them. Each gets its own ISA, which may refine the steps.
- The workflow files' own length, except adding TOCs.

## 10. Plan: shorten `Examples/e5-enterprise.md` below 50 KB

**Why.** pi's `read` returns at most 50 KB (51,200 bytes) per call; the file is 59,164 bytes. Q8 already stops Scaffold from requiring it, but anyone who opens it in pi still gets a cut read, and it is the largest file in the skill.

**Target.** ≤ 50,000 bytes, leaving ~1.2 KB of headroom under 51,200 for later edits. That means cutting ≥ 9,164 bytes. The hard floor is 7,964 (to 51,200).

**What must not change.**
- The 68 ISCs and their IDs.
- The section list (12 sections).
- `effort: E5`, `phase: execute` and `interview_ran`.
- Every `[x]` keeps its Verification line, and every `[ ]` stays open.
- The anti-criteria ISC-60 to ISC-68 keep their claim; only wording may tighten.
- The three-phase rollout story (ISC-52 to ISC-59) and the Decisions and Changelog it relies on stay.

**Steps, measured on today's file, in this order. Measure after each one; steps 1–4 always apply (they fix real defects), and step 5 only as far as needed.**

| # | Step | Measured basis | Saves |
|---|---|---|---|
| 1 | **Ledger references → today's form.** Replace `(ledger: 20260108-070000_beaconhealth-portal-v1-82ecd4413037#L<n>)` with `(ledger: <10-hex>)`, the form `isa verify` writes now (`commands.py:_ref`). The example has no ledger, so use a deterministic stand-in: the first 10 hex of `sha256` of the old reference. A one-off script, because hand edits of 47 lines invite slips. `commands.py:959` (`OLD_REF`) already converts the old form for real ISAs, so this is the same migration. | 47 refs = 3,047 bytes → ~940 | ~2,100 |
| 2 | **Criteria ≤ 14 words each** (SKILL.md asks 8–12). 62 of 68 are longer and 31 exceed lint's 20-word warning. Rule: keep the end state, the actor and one bound; any number or list the Test Strategy entry's `check`/`threshold` does not already carry moves there. Read both before cutting. Example: ISC-6 "Idle timeout is 15 minutes for clinician/admin/auditor and 30 minutes for patient; absolute session lifetime is 12 hours." → "Idle timeouts are 15 min (staff) and 30 min (patients); sessions end at 12 h." | criteria section 10,684 bytes | ~3,000 |
| 3 | **Decisions rows ≤ ~170 bytes:** date, the choice, what it beat, one-clause reason, approval date if any. All 19 rows stay. | 5,646 bytes, ~300 per row | ~1,800 |
| 4 | **Opening sections about −20%** (Problem, Vision, Out of Scope, Principles, Constraints). Every item stays; only the sentences shrink. | 7,720 bytes | ~1,500 |
| 5 | **Test Strategy `check` / `threshold` that repeat the criterion's words:** keep the measurable part only. | 17,518 bytes, 59 `check` + 59 `threshold` lines | ~1,000–1,500 |
| | **Total** | | **~9,400–9,900 → ~49.3–49.8 KB** |

**Fallback, if steps 1–5 land above 50,000:** drop the "Build, Deploy, Release" group (ISC-47 to ISC-51) with its Test Strategy entries, Verification lines and `satisfies` references, about 2.5 KB. Other examples already show deploy criteria (`e2-rotate-credential`, `e4-api-migration`). The gap in IDs is fine in an example, but a Decisions row must say why ISC-47 to ISC-51 are absent. This needs the user's OK at the time, because it removes content.

**Checks** (they become the Test Strategy of this step's ISA):
1. `test "$(wc -c < skill/isa/Examples/e5-enterprise.md)" -le 50000`
2. `python3 tools/lint_isa.py skill/isa/Examples/e5-enterprise.md` prints `ok` with no "over 20 words" warning.
3. Same ISC IDs as before: `diff <(git show HEAD:<path> | grep -o '^ *- \[.\] ISC-[0-9.]*' | sed 's/^ *//') <(grep -o '^ *- \[.\] ISC-[0-9.]*' <path> | sed 's/^ *//')` is empty (or, under the fallback, differs only by ISC-47 to ISC-51).
4. Same section headings, in the same order.
5. `grep -c '^- isc:'` and the number of `[x]` lines are unchanged (except under the fallback).
6. **Manual, attested:** the anti-criteria and the phase story still say the same thing (side-by-side read of ISC-52 to ISC-68).

## 11. Hardening the ISA framework

Moved to its own spec, `future/ISA-HARDENING.md` (2026-10-05), to be done after this spec's phases. It holds the error analysis written while drafting this spec, the proposals H1–H6, and an issue log for the live-testing phase.
