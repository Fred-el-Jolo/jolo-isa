# ISA framework hardening — fewer framework errors, smaller ISA files, an issue log for live testing

Status: **spec, not implemented** (2026-10-05). Scheduled **after the SKILL-SPLIT phases** (`future/SKILL-SPLIT.md` § 7: rename, pi install, split); the one exception worth considering is the issue log (§ 4), which is independent and most useful if it exists when live testing starts. Moved here from `future/SKILL-SPLIT.md` § 11, where it was written; the analysis (§§ 1–3) is unchanged, the issue log (§ 4) is new.

## Contents

1. Status and context
2. Errors seen
3. Proposals
4. Issue log for the live-testing phase
5. Order
6. Acceptance

## 1. Status and context

**Question.** Are the ISA update errors seen while writing `future/SKILL-SPLIT.md` (session of 2026-10-04/05) normal, or can the framework prevent them? The answer has to respect the ISA file's own size: pi reads 50 KB per call, and every byte of an ISA is read again on each reopen.

**Size today.** The six ISAs in this repo's `.isa/` are 5.6–21.2 KB. In every one, the generated Verification section is about as large as the Test Strategy (spec ISA: 6,527 vs 7,629 bytes), because each Verification line repeats the probe command in full (`commands.py:504`, `` `{tool}` ``). That makes Verification about 30% of a typical ISA. The SKILL-SPLIT spec's ISA (`.isa/20261005-130712_skill-md-split-spec/`) reached 21 KB after four reopens, and 25.6 KB after its fifth, so a long-lived ISA can approach the 50 KB read limit.

The ISA framework here means the hooks (`runtime/isa/engine.py`), the `isa` commands (`commands.py`, `cli.py`), lint (`lint.py`, `rules.py`, `yamlish.py`) and the classifier (`classify.py`), shared by Claude Code and pi.

## 2. Errors seen

**Errors seen, by class:**

| # | Seen | Cause | Normal? |
|---|---|---|---|
| E1 | Edit refused: "Found 2 matches" | The probe text being edited also appears in the generated Verification line, which quotes it | Framework: generated text duplicates hand-written text |
| E2 | Edit refused: "String not found" | The model left the `[ ]` checkbox out of the line it matched | Normal model slip |
| E3 | Lint error "no entry for leaf ISCs …" or "ISC-N is not an ISC in Criteria" (3 times, the last while writing this section) | Criteria and their Test Strategy entries were added in two edits, and PostToolUse linted the half-done state | Framework: the pair has no single-step way to be written |
| E4 | YAML parse error (3 times: `/skill:`, `timeout: 600`, `ledger: <…>`) | `: ` inside a plain YAML value; correct YAML behaviour (`yamlish.py:76`) | Partly: the message names the problem but not the fix |
| E5 | "no fenced ```yaml list" | The closing fence was missing; the message suggests no block at all | Framework: message points the wrong way |
| E6 | Probe regressions after rewording (ISC-1, ISC-14, ISC-15) | Doc probes grep exact sentences of a file the task itself edits | Normal, and the gate worked: each forced a `refined:` row |
| E7 | Six reopens (two of the dedup ISA, four of this spec's), three edits each (`phase`, `iteration` + `resumed_at`, Decisions row) | No single command for a reopen | Framework: friction, 18 edits this session |
| E8 | `python3 - <<EOF` scripts rewrote the bound ISA.md twice and passed as `unknown` | `classify.py` spots shell edits only through literal path arguments (`sed -i`, `>`, `tee`, `cp`/`mv`); the path inside a heredoc body is dropped (`_drop_heredoc_bodies`) | Framework gap: the ownership rules are never checked on such a write |
| E9 | About 15 "file changed on disk since you last read it" notices | Every `isa` command rewrites the ISA (`progress`, Verification) | Normal; less churn would come from H1 |

## 3. Proposals

**Proposals, most value first. Each says what it does to the ISA file's size.**

- **H1. Verification lines cite the probe by hash instead of repeating it** (fixes E1, cuts size).
  - `- ISC-3: verified <stamp> — exit 0 in 0.0s — probe 9f3c2a1b (ledger: <id>)`, where the hash is the first 8 hex of the ledger's existing `tool_sha`.
  - The probe text stays in Test Strategy (one copy). `isa close` still prints the commands.
  - Lint gains a check it could not do before: a ticked ISC whose current probe hash differs from its Verification line was verified with another probe, so it is shown as stale.
  - **Size:** Verification shrinks ~70–85% (spec ISA: ~6.5 KB → ~1.5 KB, about −24% of the file).
  - **Cost:** the file alone no longer shows the exact command that was run at verify time; git history of the Test Strategy does.
  - Existing ISAs: migrate with the same mechanism as `OLD_REF` (`commands.py:959`).
  - Attested lines keep their evidence text (it is the evidence). Lint warns past ~400 characters (the ISC-3 attest here is ~900).
- **H2. One step for "criterion + its Test Strategy entry"** (fixes E3, most E4, part of E2).
  - Cheap version first: PostToolUse lint reports a leaf ISC that has no Test Strategy entry yet as a **hint**, not an error. PreToolUse still refuses project changes until the pair is complete, so nothing gets weaker.
  - Full version: `isa isc add <ISA> "<claim>" --kind … --tool … [--fails-when …]` writes both, picks the next ID, and always emits `tool: |-` blocks, so `: ` never breaks YAML.
  - **Size:** neutral. **Cost:** a new command for the model to learn; Write/Edit stays allowed.
- **H3. A reopen command** (fixes E7). `isa reopen <ISA> --why "<text>"` sets `phase: learn`, increments `iteration`, sets `resumed_at`, and appends the `refined: reopened after complete — <why>` row in one step. The Stop hook's "reopen it" message names it.
  - **Size:** neutral (the same row as by hand).
- **H4. Catch shell writes to an ISA after the fact** (closes E8). After any `unknown` command, compare the bound ISA's content hash before and after (the hook already runs `changes.py` for project files). If it changed, run the same ownership check and lint as for a Write/Edit:
  - a tick, a generated line or `phase: complete` written this way becomes a `shell-edited` blocked key, cleared by `isa lint`, like `ledger-changed`;
  - a content-only change gets a warning ("use Write/Edit").
  - **Size:** neutral. **Cost:** one hash per `unknown` command.
- **H5. Lint messages that say the fix** (E4, E5).
  - The YAML error adds: "quote the value or write it as a `|-` block".
  - The fence check distinguishes "no ```yaml block" from "```yaml opened at line N is never closed".
  - IsaFormat's Test Strategy examples use `tool: |-` for any command containing `: `.
  - **Size:** neutral (+1 line for a `|-` entry).
- **H6. A size guard** (keeps ISAs readable in one pi read).
  - `isa lint` warns when an ISA passes 40 KB, and `isa status` shows the size.
  - With H1 in place, few ISAs should ever get there.
  - The warning suggests the existing remedies: split into ephemeral slices or a child ISA (IsaHierarchy), or close and start a new ISA rather than a sixth reopen.
- **No change for E2, E6, E9.**
  - E2 is a model slip. H2 means fewer hand edits, so fewer chances.
  - E6 is the gate working as intended. Add one line to IsaFormat § Test Strategy: for `kind: doc` on a file the task itself rewrites, prefer structural checks (heading exists, order, counts) over exact sentences.
  - E9 shrinks with H1.

## 4. Issue log for the live-testing phase

**Goal.** One short log that lists only the framework's own trouble, the kind E1–E9 above describes, so that after each live-testing day the user can see what went wrong in the ISA machinery and how often, without reading the full day logs. Its counts decide which H-proposal comes next and show whether a fix worked (before/after).

**What it is not.** A failing probe on buggy code is work, not a framework issue: the model answers "claim wrong or code wrong?". Normal gate decisions are not issues either. Jev outages are already logged and told to the user. None of these go in.

**Where.** `~/.isa/_state/issues/YYYY-MM-DD.jsonl`, one JSON row per issue, written like the day logs (`logs.py`: `t` added, a write failure swallowed, never changes a hook's result). It is a separate file, not a filter over `~/.isa/_state/logs/`, so it stays short enough to read whole. The day logs keep their rows unchanged, and each issue row carries the same `prompt` id, so the full context is one grep away.

**Row.** `{t, harness, session, prompt, project, isa (slug only), code, source (hook name or command), isc (IDs, if any), detail (fixed vocabulary), n (count, if aggregated)}`.

**Privacy: the log never copies text.** No prompt, ISA, probe or error-message text, and no `old_string`. A tool's error message is matched against a fixed pattern list only to pick the code. An unmatched message becomes `edit-other`, with no text. A test seeds an ISA, a prompt and a probe with a sentinel string and asserts the string never appears under `issues/`.

**Codes:**

| Code | What | Detected by | Class |
|---|---|---|---|
| `edit-ambiguous` | A Write/Edit of an `ISA.md` failed: the text matched more than once | `_tool_failed` (`engine.py:1174`) gains a branch for non-shell tools on ISA paths. Claude Code: `PostToolUseFailure`; pi: `tool_result` with `isError` | E1 |
| `edit-no-match` | A Write/Edit of an `ISA.md` failed: the text was not found | same | E2 |
| `edit-stale` | A Write/Edit of an `ISA.md` failed because the file changed since it was read | same | E9 |
| `edit-other` | Any other failed Write/Edit of an `ISA.md` | same | — |
| `lint-pair-missing` | Lint after an ISA edit: a leaf ISC without a Test Strategy entry, or an entry without its ISC | `_post_tool` (`engine.py:1095`), from the lint result | E3 |
| `yaml-parse` | Lint could not parse a YAML block (`detail`: section, line number) | `lint.py:102` (frontmatter), `lint.py:233` (Test Strategy / Features), via `_post_tool` and `isa lint` | E4 |
| `yaml-block-missing` | "no fenced ```yaml list", split into `fence-unclosed` once H5 lands | `lint.py:229` | E5 |
| `probe-regressed` | `isa verify` unticked an ISC that had passed. `detail`: `probe-changed` when the probe's `tool_sha` differs from the passing run, otherwise `tree-changed` | `commands.py:490` | E6 |
| `reopen` | A `phase: complete` ISA was edited back open (`detail`: `by-edit` or `by-command` once H3 lands) | `_pre_tool` (`engine.py:699`) records the target ISA's `phase` before a Write/Edit; `_post_tool` compares it after | E7 |
| `ownership-refused` | PreToolUse refused a model write to an ISA: a tick, a generated line, `progress`, `phase: complete` or `root` (`detail`: which) | `_ownership_refusal` (`engine.py:901`) | — |
| `isa-shell-edit` | A shell command writing onto an `ISA.md` was refused | `engine.py:706` | — |
| `isa-script-edit` | An `unknown` command changed the bound ISA's content, e.g. a `python3` heredoc | Until H4, `_post_tool` compares the bound ISA's mtime and size before and after shell tools; H4 replaces this with a content hash and the ownership check | E8 |
| `gate-refused` | A change was refused: no ISA bound, or the ISA fails articulation (`detail`: `no-isa` or `articulation`) | `engine.py:738`, `engine.py:752` | — (friction measure) |
| `stop-refused` | Stop refused the turn (`detail`: the problem codes from `problems.py`) | `_stop` (`engine.py:1269`) | — |
| `stop-blocked` | The second refusal let the turn end with problems recorded as `blocked` | `engine.py:1320` | — |
| `command-error` | `isa new`, `lint`, `verify` or `close` exited 2 (`detail`: a reason code such as `no-key`, `not-articulated`, `close-refused` or `unknown-isa`, never the message) | `cli.py` `main` (`cli.py:41`), from the commands' exit paths | — |
| `hook-crash` | A hook failed open; the stack trace stays in `errors.log` | `cli.py:297` | — |

**Reader.** `isa issues [--since YYYY-MM-DD] [--session ID] [--code CODE] [--summary] [--md]`:
- plain: one line per row;
- `--summary`: counts per code with the first and last time, and the E-class;
- `--md`: a markdown table ready to paste into a review.

Read-only, like `isa status`. The model may run it: it holds no user words.

**Switch.** `{"issue_log": true}` in `~/.isa/config.json`, **on by default during the live-testing phase**; a missing or broken config keeps the default (`config.py`). `ISA_ISSUE_LOG=0|1` overrides it for tests. The end of the testing phase is a dated Decision that flips the default to off, which is a one-line change. The rows cost a few hundred bytes a day.

**Retention.** `isa purge-logs` also purges `issues/` day files, with its own default of 30 days, so a testing phase's history survives a weekly purge. As with the day logs, the age comes from the file name.

**ISA file size.** None: issues never touch an ISA or its ledger.

**Review loop.** After each live-testing day, run `isa issues --summary`. Map each code to its E-class, re-rank §3's proposals by count, and record the ranking in the hardening ISA's Decisions. When a proposal ships, its code's count before and after is its evidence.

## 5. Order

1. **Issue log (§ 4) first.** It measures the problems, so it must exist before any fix to give before/after counts. It is independent of the SKILL-SPLIT phases, so pulling it forward when live testing starts is an option for the user, not part of this plan's default order.
2. Then §3's proposals in the order below, re-ranked by the issue counts once there are some:

**Order:** H5 and H2 (cheap version) first, as small changes. Then H1 with its migration and H3. Then H4, then H6. Each change gets its own ISA and tests: `test_commands.py` for H1/H2/H3, `test_bash_classifier.py` + `test_hooks.py` for H4, `test_lint_v2.py` for H5/H6. These come after Phases 1–3 of `future/SKILL-SPLIT.md` § 7, or between them if they unblock work. They do not depend on the split.

## 6. Acceptance

Per item, each in its own ISA:

- **Issue log:**
  - every code in § 4 is produced by a test that triggers it, through both adapters where the event exists (Claude Code hooks, pi `tool_result` / `tool_call`);
  - the sentinel test proves no text leaks;
  - `isa issues --summary` groups correctly;
  - `ISA_ISSUE_LOG=0` writes nothing;
  - a write failure never changes a hook's result (`tests/test_logs.py` style);
  - `purge-logs` honours the 30-day default.
- **H1–H6:** the tests named in § 5, plus for H1 the migration of the repo's existing `.isa/` ISAs, after which lint is clean and Verification is smaller (measured).
- **No regression:** the full test list from AGENTS.md § Working rules and the node tests pass after each item.
