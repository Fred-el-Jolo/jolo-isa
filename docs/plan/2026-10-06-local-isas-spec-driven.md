---
status: acked 2026-10-06 #008f483e
spec: docs/spec/2026-10-06-local-isas-spec-driven.md
---

# Plan — Local ISAs, committed specs

Goal: Task ISAs live in `~/.isa` again with no encryption left, and every project follows spec → (plan) → ISA, enforced by the hooks in Claude Code and pi.

Approach: Undo SPEC-v2 § 13 first (move the ISAs home while the decryption code still exists, then delete it), so the spec work starts from the smaller codebase. Then build the spec layer from the inside out: a pure parser and lint, then locations and binding, then the ack, then the gate, then `isa new` and `isa close`. The docs and the global rules come last, once the behaviour they describe is real. Every step is built in one session (Q13). This plan predates the spec template, so the spec has no `S<n>:A<n>` ids: steps cover its § 8 acceptance items (`§8.N`), and § 8 is the list a step's ISA anchors to.

Files:
- `runtime/isa/state.py` — where task ISAs, specs, plans and the project ISA live
- `runtime/isa/evidence.py` — the ledger path (home only)
- `runtime/isa/commands.py` — `isa new` (seeded from a spec or plan), `isa close` (done marks), `isa migrate --home`
- `runtime/isa/specdoc.py` (new) — parse, lint, hash, ack records and done marks for specs and plans
- `runtime/isa/classify.py` — the `spec` path kind
- `runtime/isa/engine.py` — doc binding, the ack question, the stage rules of spec § 5.2
- `runtime/isa/lint.py`, `runtime/isa/rules.py` — ISA link rules (`spec:`, `plan:`, `no-spec:`, anchored bullets)
- `runtime/isa/cli.py` — command dispatch (`lint` of a spec or plan, `migrate --home`; `key`/`crypt` removed)
- `runtime/isa/crypt.py`, `runtime/isa/quotes.py` — deleted in P4
- `runtime/isa/protocol.md` — the ON block lines for the tier and the spec order
- `adapters/pi/isa.ts` — the ack select in pi
- `install.py` — the global rule block in both harnesses
- `skill/ISA/References/SpecDriven.md` (new), `skill/ISA/Examples/specs/` (new), `skill/ISA/SKILL.md`, `skill/ISA/References/IsaFormat.md`, `skill/ISA/Workflows/Scaffold.md` — the docs
- `tests/test_migrate_home.py` (new), `tests/test_project_isa.py` (new, replaces `tests/test_m12.py`), `tests/test_specdoc.py` (new), `tests/test_spec_flow.py` (new), `tests/test_install.py`, `adapters/pi/test/extension.test.ts` — the tests
- `AGENTS.md`, `ISA.md` — the repo's own notes and standing claims

Review focus:
- A session still bound to a `<repo>/.isa/…` path after the move reads as "no ISA bound": no crash, no refusal of every tool → P3
- The ack hash is the same across machines and editors: CRLF vs LF, a missing final newline, `[X]` written for `[x]` → P5
- Two sessions closing ISAs linked to the same spec: the second re-reads the file just before writing, so no tick is lost → P11
- Only the exact `Acknowledge` label is an ack: an "Other" answer saying "ack", or a pi select closed with Esc, is not → P7
- A spec written to a near-miss path (`docs/specs/`, `SPEC.md`, `docs/spec/x.txt`) is a project change, and the refusal names the right path → P9

- [x] P1 — `isa migrate --home` moves a repo's task ISAs back to `~/.isa` · E3 · covers §8.3 · Done: 2026-10-06
  Files: `runtime/isa/commands.py` (change: `migrate_home`), `runtime/isa/cli.py` (change: `migrate --home`), `tests/test_migrate_home.py` (new)
  Interfaces: produces `commands.migrate_home(args, out=print) -> int` (args: `["--dry-run"]` or `[]`); reuses `commands._rebind(moved: dict[str, str])`
  Done when:
  - run in a repo, every `<repo>/.isa/<slug>/` is moved to `~/.isa/<project-key>/<slug>/` (`state.project_key(repo)`), `_ephemeral/` included;
  - its `evidence.jsonl` becomes `~/.isa/_state/evidence/<slug>-<sha256(new real path)[:12]>.jsonl`, the name `evidence.ledger_path` computes for the new path, with `root` / `cwd` / `files` rewritten absolute and row ids unchanged;
  - `root: .` (or `root: sub/dir`) in each moved ISA becomes the absolute path, and `isa lint` is clean on it;
  - an `enc:v1:` value still on disk is decrypted with the key; without a key it is replaced by `""` and reported;
  - sessions bound to a moved ISA are rebound;
  - the `.isa/**/*.md filter=isa` and `.isa/**/evidence.jsonl merge=union` lines leave `.gitattributes` (the file is deleted when nothing else is in it), and `git config --remove-section filter.isa` runs;
  - the root `ISA.md` is untouched; a slug already in `~/.isa/<project-key>/` is skipped and named;
  - it prints `git rm -r --cached .isa && git add .gitattributes && git commit -m "Move task ISAs out of git"` and commits nothing;
  - `--dry-run` prints the same list and changes no file (a tree fingerprint before and after is equal).
- [x] P2 — Run the migration in the four repos, then retire the key · E2 · covers §8.3 · after P1 · Done: 2026-10-06
  Files: none in this repo; artifacts: `.isa/`, `.gitattributes` and `.git/config` of `~/dev/jolo-isa`, `~/dev/pi-quota-footer`, `~/dev/jev-kit`, `~/dev/jolo-pi`; `~/.isa/key`
  Done when:
  - `python3 install.py` ran first, so the installed `isa` has `migrate --home`;
  - in each of the four repos, after the user's commit: `git ls-files .isa` prints nothing and `git config --get-regexp '^filter\.isa'` prints nothing;
  - every moved ISA lints clean under `~/.isa/<project-key>/`, and every `(ledger: <id>)` line resolves;
  - the user deleted `~/.isa/key` (the model never touches it; `test ! -e ~/.isa/key`).
- [x] P3 — Task ISAs always live in `~/.isa` · E3 · covers §8.1, §8.4 · after P2 · Done: 2026-10-06
  Files: `runtime/isa/state.py`, `runtime/isa/evidence.py`, `runtime/isa/commands.py`, `runtime/isa/changes.py`, `runtime/isa/fingerprint.py`, `runtime/isa/engine.py`, `tests/test_project_isa.py` (new), `tests/test_state.py`, `tests/test_seamless_projects.py`
  Interfaces: `state.project_dir(cwd) -> str` always returns `os.path.join(state.home(), state.project_key(cwd))`; produces `state.project_isa_of(isa_path) -> str | None` (the project ISA of the repo holding the ISA's `root:`), used by `commands.promote_issues`; removes `state.repo_isa_dir` and `state.isa_repo`
  Done when:
  - `isa new` inside a git repo prints a path under `~/.isa/<project-key>/`; no `<repo>/.isa/` and no `.gitattributes` is created;
  - `root:` is written absolute; `evidence.ledger_path` has only the `_state/evidence` case, and `evidence.is_ledger_path` drops the `evidence.jsonl` case;
  - `changes.ISA_FILES` keeps `:(top,exclude)ISA.md` and drops `:(top,exclude).isa`;
  - `isa verify ISA.md` still re-proves the project ISA, and a `promote: true` criterion still blocks `isa close` until `(from <slug> ISC-N)` is in the project ISA;
  - the project-ISA and `promote:` tests from `tests/test_m12.py` pass in `tests/test_project_isa.py`;
  - a session file bound to a missing path reads as no ISA bound.
- [x] P4 — Remove the encryption and the other § 13 machinery · E3 · covers §8.2, §8.5 · after P3 · Done: 2026-10-06
  Files: `runtime/isa/crypt.py` (delete), `runtime/isa/quotes.py` (delete), `runtime/isa/cli.py`, `runtime/isa/commands.py`, `runtime/isa/engine.py`, `runtime/isa/evidence.py`, `runtime/isa/rules.py`, `runtime/isa/protocol.md`, `skill/ISA/SKILL.md`, `AGENTS.md`, `ISA.md`, `tests/test_m12.py` (delete), the live flow test in `tests/flow/`
  Done when:
  - `rg -nw 'crypt|quote-verified|ISA_KEY|filter\.isa|enc:v1' runtime/ skill/ adapters/` finds nothing;
  - gone: `isa crypt`, `isa key …`, `isa migrate` (both forms), PreToolUse's refusal of `isa key`, the missing-key messages, "not on this branch", `quote-verified` rows, HMAC asks (the snapshot stores asks verbatim), `[user words]` redaction, the project ISA's quote check;
  - SKILL.md's "Where ISA files live" says what spec § A.1 says, and its encryption paragraph is gone; AGENTS.md drops "Prompts encrypted in git" and the related rows;
  - the project ISA loses ISC-P6 and the constraint "The user's verbatim words never reach git…"; ISC-P1's test list is updated;
  - the full unit suite (as listed in AGENTS.md, without `tests.test_m12`) and the pi extension tests pass; `python3 tests/check_stdlib.py runtime/` passes; `python3 tools/lint_isa.py skill/ISA/Examples/*.md` reports every file `ok`.
- [x] P5 — Parse, lint and hash specs and plans · E3 · covers §8.16 · after P4 · Done: 2026-10-06
  Files: `runtime/isa/specdoc.py` (new), `runtime/isa/cli.py` (change: `isa lint` routes a spec or plan to `specdoc.lint`), `tests/test_specdoc.py` (new)
  Interfaces: produces
  - `specdoc.parse(text) -> dict`, with keys `kind` (`"spec"` | `"plan"`), `fm`, `sections` (`{"S2": {"title", "line", "bullets": {"A1": {"text", "ticked", "line"}}}}`), `steps` (`{"P2": {"line", "goal", "tier", "covers": [("S2", "A1")], "after": ["P1"], "files", "done_when", "ticked"}}`), `review_focus` (`[(text, "P2")]`);
  - `specdoc.ack_hash(text) -> str`: the first 8 hex of sha256 of the text with CRLF → LF, `status:` and `Done:` lines removed, `- [x] ` / `- [X] ` read as `- [ ] `, and a trailing `  (YYYY-MM-DD, ISA …)` removed;
  - `specdoc.lint(path, moment="draft") -> list[str]` (`moment`: `"draft"` | `"ack"`; a warning starts with `warn:`).
  Done when:
  - the spec rules of spec § B.3 hold: frontmatter `status`, `effort`; Said and Assumed under Goal; `S<n>` with `- [ ] A<n>:` bullets, ids unique in their section; no `TBD`, `TODO` or lone `…` outside backticks (a word quoted in backticks names a placeholder, it isn't one); no empty section; at `"ack"`, Open questions empty; Approaches from E3; `plan:` and a `second-look:` line from E4; `interview:` at E5;
  - the plan rules hold: every bullet covered (`covers S2` = all of S2), every `after` and Review focus target is a step, every step has Files and Done when, no placeholder, `warn:` over 3× the spec's bytes or when code blocks are most of the plan;
  - `ack_hash` gives one value for the same spec written with LF and with CRLF, with and without a final newline, and with `[x]` / `[X]` / `[ ]` ticks.
- [x] P6 — Where specs live, the `spec` path kind, the project ISA everywhere · E3 · covers §8.13, §8.4 · after P3 · Done: 2026-10-06
  Files: `runtime/isa/state.py`, `runtime/isa/classify.py`, `runtime/isa/commands.py` (change: `project_isa`), `tests/test_state.py`, `tests/test_bash_classifier.py`
  Interfaces: produces `state.doc_root(cwd) -> str` (the git work-tree root; else `cwd`; when that is `$HOME` or under a temp dir, `os.path.join(state.home(), state.project_key(cwd))`) and `state.is_spec_path(path) -> bool` (`<doc_root>/docs/spec/*.md` or `<doc_root>/docs/plan/*.md`); `classify.path_kind` returns `"spec"` for those; `commands.project_isa(root, out=print)` takes any doc root
  Done when:
  - outside git, specs go to `<dir>/docs/spec/`; in `$HOME` or a temp directory, to `~/.isa/<project-key>/docs/spec/`;
  - a Write to `docs/spec/x.md` classifies as `spec`; `docs/specs/x.md` and `docs/spec/x.txt` classify as `project`;
  - the first `isa new`, or the first spec written, creates `ISA.md` at the doc root when it is missing, in git and out of it; an `ISA.md` without `kind: project` is still left untouched.
- [x] P7 — Bind a spec, ask and record the ack (Claude Code) · E3 · covers §8.8, §8.15 · after P5, P6 · Done: 2026-10-06
  Files: `runtime/isa/engine.py`, `runtime/isa/specdoc.py`, `tests/test_spec_flow.py` (new)
  Interfaces: session key `st["doc"] = {"path": str, "kind": "spec" | "plan"}`, set when a spec or plan is written; constants `ACK_HEADER_SPEC = "Spec ack"`, `ACK_HEADER_PLAN = "Plan ack"`, `ACK_YES = "Acknowledge"`, `ACK_NO = "Request changes"`; produces `specdoc.record_ack(path, harness, session) -> str` (appends `{"path", "hash", "t", "harness", "session"}` to `~/.isa/_state/acks.jsonl` and returns the hash), `specdoc.ack_recorded(path, h) -> bool`, `specdoc.acked(path) -> bool` (the `status: acked … #h` line matches `ack_hash` of the file now)
  Done when:
  - writing a spec or plan binds it to the session; Q2 judges a prompt against the bound doc as it does against a bound ISA;
  - PreToolUse refuses an `AskUserQuestion` with header `Spec ack` / `Plan ack` while `specdoc.lint(path, "ack")` has errors, and names them;
  - PostToolUse records the ack only when the answer is exactly `Acknowledge`; then it tells the model to write `status: acked <YYYY-MM-DD> #<hash>` and, in a git repo, to run `git add <path> && git commit -m "Spec: <title> (acked)"` (`"Plan: …"` for a plan), that file only; outside git, no commit;
  - PreToolUse refuses a Write/Edit that introduces `status: acked … #h` when `ack_recorded(path, h)` is false, and lets the same Write through after the click.
- [x] P8 — The ack in pi · E2 · covers §8.12 · after P7 · Done: 2026-10-06
  Files: `adapters/pi/isa.ts`, `runtime/isa/engine.py` (change: `agent_before_settle` result), `adapters/pi/test/extension.test.ts`
  Interfaces: consumes P7's constants and `specdoc.record_ack`; the engine's settle result gains `{"ask": "Acknowledge <path>?", "options": ["Acknowledge", "Request changes"], "ask_kind": "ack", "ask_path": <path>}`, and the extension sends `ask_kind` and `ask_path` back in the `ask_answer` event
  Done when:
  - pi asks the ack at `agent_before_settle` when the bound spec or plan changed this turn and passes `specdoc.lint(path, "ack")`, and reports the answer to the engine;
  - a select closed with Esc (`undefined`) is reported as `Request changes`;
  - with no UI, nothing is asked and nothing is recorded.
- [x] P9 — The stage rules of spec § 5.2 in PreToolUse and Stop · E3 · covers §8.6 · after P7 · Done: 2026-10-06
  Files: `runtime/isa/engine.py`, `runtime/isa/protocol.md`, `tests/test_spec_flow.py`
  Interfaces: produces `engine._stage(st, cwd) -> str`, one of `"off"`, `"triage"`, `"spec_draft"`, `"spec_acked"`, `"plan_draft"`, `"plan_acked"`, `"build"`
  Done when:
  - in an ON session with nothing bound, a Write to `docs/spec/…` passes PreToolUse, and a project change is refused with "write the E1 ISA, or the spec, first";
  - during `spec_draft` / `plan_draft`, a project change and `isa new` (E2+) are refused with "spec not acknowledged yet" / "plan not acknowledged yet";
  - Stop does not refuse a turn that wrote a spec and ended on the ack question, or on its open questions; it refuses once a turn that changed the spec and asked neither;
  - an `unknown` command that changed project files before the ack is reported, and Stop refuses once with "project files changed before the spec was acknowledged — revert them or ask the user";
  - after the ack, Stop refuses a turn with no ISA bound, as today;
  - the refusal for a near-miss path names `docs/spec/YYYY-MM-DD-<slug>.md`;
  - `protocol.md` carries the tier rule and the order spec → ack → (plan → ack) → ISA.
- [x] P10 — `isa new --spec / --plan`, and the ISA link rules · E3 · covers §8.7, §8.17 · after P7 · Done: 2026-10-06
  Files: `runtime/isa/commands.py` (change: `new`), `runtime/isa/specdoc.py`, `runtime/isa/lint.py`, `runtime/isa/rules.py`, `tests/test_spec_flow.py`, `tests/test_lint_v2.py`
  Interfaces: `isa new <slug> (--spec <path>#S2[:A1,A2] | --plan <path>#P2 | --no-spec) [--tier E1..E5]`; ISA frontmatter `spec:` / `plan:` (a string or a list), `stated_goal_source: spec`; produces `specdoc.resolve(link) -> list[tuple[str, str]]` (the `(S, A)` bullets a link names) and `specdoc.seed(link) -> dict` (`goal`, `criteria: [(anchor, text)]`, `tier`, `constraints`, `review_focus`)
  Done when:
  - `isa new --spec X#S1` exits non-zero before X is acked, and after X is edited past its ack (`status:` and `Done:` lines and tick state excepted);
  - `isa new --plan Y#P3` exits non-zero while a step in P3's `after` is open;
  - the seeded ISA has its Goal from the spec Goal (or the step line), one draft criterion per linked bullet anchored to it (`anchors_to: "S2:A1"`), the tier from `effort:` (or the step), pointer lines `See <path>#S2` for Problem / Vision / Out of Scope / Constraints, and the spec's Constraints printed;
  - with `--plan Y#P2`, every Review focus line P2 owns is in the new ISA as a criterion;
  - lint: from E2, an ISA in a project with a doc root needs `spec:`, `plan:` or a `no-spec:` Decisions row; a linked bullet that no ISC anchors to is an error; pointer-line sections pass the tier gate; `stated_goal_source: spec` is checked against the linked file instead of the prompt log.
- [x] P11 — `isa close` writes the done marks · E3 · covers §8.9, §8.10, §8.11 · after P10 · Done: 2026-10-06
  Files: `runtime/isa/commands.py` (change: `close`), `runtime/isa/specdoc.py`, `tests/test_spec_flow.py`
  Interfaces: produces `specdoc.mark_done(path, bullets, slug, date) -> list[str]` (re-reads the file under `<path>.lock`, ticks bullets, appends `  (<date>, ISA <slug>)`, writes or replaces each section's `Done: <date> — <n>/<n> accepted (ISAs <slugs>)` line, ticks plan steps with ` · Done: <date>`, sets `status: done <date>` when every section is done, writes atomically, returns the changed lines)
  Done when:
  - a passing close on `spec: X#S1` ticks every S1 bullet a passing ISC anchors to, and leaves exactly one `Done:` line under `## S1`; a second close replaces it;
  - a failed close, or a close while X changed since its ack, writes nothing; the close refuses with "spec changed since its ack — ask the user to acknowledge it again";
  - a section closed by two ISAs: after `spec: X#S2:A1,A2` closes, A1 and A2 are ticked and S2 has no `Done:` line; after `spec: X#S2:A3` closes, the line reads `3/3 accepted` and names both ISAs; `ack_hash` is unchanged by the ticks;
  - with `plan: Y#P2`, a passing close ticks the bullets P2 covers and P2 itself, and sections whose bullets are all ticked get their `Done:` line;
  - two closes on one spec, run back to back from two processes, lose no tick.
- [x] P12 — The skill docs and the worked examples · E3 · covers §8.5, §8.16 · after P11 · Done: 2026-10-06
  Files: `skill/ISA/References/SpecDriven.md` (new), `skill/ISA/Examples/specs/` (new: `e2-backup-verify.spec.md`, `e3-help-redesign.spec.md`, `e4-api-migration.spec.md`, `e4-api-migration.plan.md`), `skill/ISA/SKILL.md`, `skill/ISA/References/IsaFormat.md`, `skill/ISA/Workflows/Scaffold.md`, `tools/lint_isa.py`, `AGENTS.md`
  Done when:
  - SpecDriven.md holds spec § B.10 rules 1–15, the red-flags table, both templates of § B.3, the done marks of § B.6 and the ownership table of § B.5, and names no outside source;
  - each example passes `specdoc.lint(path, "ack")`, and stays consistent with its ISA example (same goal, same scope);
  - `tools/lint_isa.py` also lints `skill/ISA/Examples/specs/*.md`, and every file reports `ok`;
  - `IsaFormat.md` line 21 is reworded as in spec § 6 (no parallel *proof* artifacts); Scaffold's ambiguity check says it runs at the spec draft for E2–E5;
  - SKILL.md links SpecDriven.md and stays under its current size;
  - `rg -n -i 'lifeos|31337|MEMORY/WORK|\btelos\b|\bpulse\b' skill/` finds nothing.
- [ ] P13 — The global rule block in both harnesses · E2 · covers §8.14 · after P12
  Files: `install.py`, `tests/test_install.py`
  Interfaces: produces `install.merge_block(text: str, block: str) -> str` and `install.strip_block(text: str) -> str`, with markers `<!-- isa:spec-driven:begin -->` / `<!-- isa:spec-driven:end -->`; the block text is spec § B.8's draft, shipped as a file next to the skill
  Done when:
  - `python3 install.py` writes the block into `~/.claude/CLAUDE.md` (created when missing) and into `~/.pi/agent/AGENTS.md` (only when `~/.pi/agent` exists), each file backed up before its first change, the user's own text around the block untouched;
  - a re-run leaves both files byte for byte unchanged;
  - `--uninstall` removes only the block; `--dry-run` writes nothing.
