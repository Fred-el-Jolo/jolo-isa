---
status: "acked 2026-10-13 #2e86701f"
effort: E3
---

# ISA friction: fewer refusals, error-proof writing, probe runs and output, no forged clicks, real reviews

## Problem

Before BUILD, the PreToolUse gate refuses every `unknown` call, in every tier: any command the classifier can't prove only reads. That includes `python3 -c "print(1)"`, `node --test`, `python3 -m unittest`, a read-only `for` loop over `grep`, and `jq`. In the 2026-10-13 sessions this blocked an E1 task's scoping and a read-only analysis prompt (no profiler, no test could run), and pushed the model into workarounds that the guard then refused as well. The rule's intent, no project change before the ISA, needs only the recognised writes refused. A change made by a script can be caught later, where it matters: before the spec is committed.

The user's ack can also be forged. Every `isa` command is allowed at every stage, including `isa hook`, which trusts the event on its stdin. A model can pipe a made-up "the user answered Acknowledge" event into it from Bash, and `isa ack` then accepts it as the user's click.

And the review doesn't remove what isn't needed. Jev flags a criterion that may be unnecessary; the model answers with a `rebuttal:` naming the spec line it came from, and the criterion stays.

## Goal

Before BUILD, in every tier (E1 to E4), any command runs except a recognised project change. When a spec is acked, the files changed outside the spec since `isa spec new` are listed, and the ack waits until they're gone. The `isa` commands and their docs give every rule before it can be broken. Each probe runs three times: red, green and regression. A failing probe shows why it failed, and a probe never seen failing is flagged. An ack comes only from the user's click: no tool call can feed the hooks an event. The user can edit a spec or an ISA through `isa open`. The review keeps only the criteria that are needed, not duplicated and well formed.
Said:
- "We'll go with option 1": TRIAGE refuses only recognised writes and lets `unknown` run
- "Do not check with git on every unknown command, check when we are about to commit the spec if other NON-SPEC files have been modified (we could have SPEC-RELATED updated / created files)"
- "The simplication on unknow commands is valid for any type (E1-4). No more frictions."
- "isa commands should be documented & coded a way that it prevents any errors"
- "each test should run one time for red, one time for green, and one time at the end for regression"
- "return full test error instead of just \"exit 1\""
- "Tell me why there is some process where you need to simulate an \"isa\" or \"spec\" ack. this should not happen."
- "ok just fill the hole"
- "remove S4 second half"
- "i don't want impl to occur before ack, even if the plan probe does bot match the reality. i changed my mind: flag the probe red run in a special way"
- "some ISX might not need probes": answered with the `manual` kind and `isa attest` (S3)
- "isa open should open the doc in write mode. As it is in readonly, i cannot update the spec/isa if i need to."
- "do not link back the items to the spec, but have a realistic review of them. Check if there are necessary, duplicates, or malformed items. Add a section for this in the spec"
Assumed:
- "before BUILD" means every stage before it: TRIAGE, SPEC DRAFT, SPEC ACKED, ISA DRAFT and ISA REFINE;
- E1 has no spec to commit, so it has no check: `isa close` commits only what changed since `isa new`, as today;
- changes made by `unknown` commands after the spec's ack (ISA DRAFT) are not checked either: `isa close` treats them like the user's own earlier changes and leaves them out of its commit, as today;
- a green probe isn't re-run by `isa verify` when later work changes the code: `isa close` is its regression run;
- "the hole" is a tool call running the hook entry point (S6); this repo's own tests, which fake clicks to test the ack, don't change;
- a hand edit by the user follows the same rules as any change: an edited acked file needs a new ack;
- the three questions apply to every criterion, not only to Jev's flags: the checklist's `redundant:` line (S7).

## Out of scope

- Running probes in parallel.
- The gate's judgement of analysis-only prompts.
- The status line.
- The speed of this repo's own test suite, and how it mocks Jev (removed from S4 by the user).
- A script written to import the runtime and call its functions directly (e.g. `spec.record_click`): the classifier can't see it. That is a deliberate bypass, not a side door.

## Constraints

- The three foundations stay. FOUNDATION_2 holds: only `isa` commands write ISAs, specs, plans and `~/.isa`, and a `guarded` call is refused in every stage.
- No git call per tool call: git runs only inside `isa ack <spec>`, never in a hook.
- `runtime/` stays standard-library only, and every file stays under 50 KB.

## Approaches

1. **`unknown` runs before BUILD, and the spec's ack checks once for non-spec changes (chosen).** It costs nothing per call. The commit of the spec is the point where a stray change would be swept in or noticed.
2. **`unknown` runs, with a `git status` before and after every `unknown` call.** Rejected by the user: a git call on every command.
3. **Keep the lock, and stop the gate turning analysis prompts ON.** Rejected: `unknown` would still be refused in SPEC DRAFT and ISA DRAFT.
4. **Compare the ISA files' hashes after each call, in place of the text-mention guard.** Not now: it changes FOUNDATION_2's enforcement.

## S1 — Unknown commands run before BUILD

The PreToolUse gate in `engine.py` changes for every tier, E1 to E4, and every stage before BUILD (TRIAGE, SPEC DRAFT, SPEC ACKED, ISA DRAFT, ISA REFINE):
- an `unknown` call goes through;
- a recognised project change (`write`) is still refused, naming the stage and the next command. That covers Write, Edit, MultiEdit or NotebookEdit on a project file, a known write command (`rm`, `mv`, `cp`, `npm`…), a redirect into a project file, `sed -i`, and a git write.

`guarded` and the CLOSED stage don't change. Foundations.md (Lifecycle), protocol.md, SKILL.md and AGENTS.md say what a recognised change is, and that the spec's ack checks the rest (S2).
Accepted when:
- in TRIAGE, SPEC DRAFT and ISA DRAFT, `python3 -c "print(1)"`, `node --test x.test.ts`, `python3 -m unittest tests.x` and `for f in a b; do grep -n x "$f"; done` are allowed, in an E1 session and in an E2 session
- in the same stages, a Write or Edit of a project file, `rm a.txt`, `mv a b`, `echo x > a.txt` and `sed -i s/a/b/ a.txt` are refused, and the refusal names the stage and the next command
- a `guarded` call (`echo x > <ISA>`, `python3 -c` naming an ISA path) is refused in every stage, as today
- the four docs no longer say that only reads and `isa` commands run before BUILD

## S2 — The spec-ack check for non-spec changes

`isa spec new` records the project's files that are already changed (modified, added, deleted or untracked): the spec's baseline. When `isa ack <spec>` is about to commit the spec, it compares the work tree with that baseline. Every file changed since, other than the spec itself and its spec-related files, is a non-spec change: work done before BUILD by an `unknown` command. If there is one, the ack is refused and nothing is committed. The user's click stays recorded, so `isa ack <spec>` succeeds once those changes are reverted or moved to a spec-related path. The check uses the same git helpers as `isa close` (`gitops.snapshot`, `gitops.changed_since`). Outside a git repo there is no check.

**Spec-related** means a path under `docs/` with a folder or file name that starts with the spec's `<date>-<slug>`, at any depth. Examples: `docs/2026-10-13-isa-friction-diagram.svg`, `docs/2026-10-13-isa-friction/flow.png`, `docs/assets/2026-10-13-isa-friction/x.png`.
Accepted when:
- with no non-spec change, `isa ack <spec>` commits the spec alone, as today
- a file changed after `isa spec new` by something other than an `isa` command makes `isa ack <spec>` exit 1, listing its path, and nothing is committed
- after that file is reverted, `isa ack <spec>` succeeds on the same click
- a file already changed before `isa spec new` is never listed
- the three example spec-related paths above are never listed; `docs/other.md` and `src/a.py` are
- the check runs `git` only inside `isa ack`, never in a hook

## S3 — Writing the ISA without errors

Every rule the commands enforce is written down before it can be broken, and every refusal carries the corrected command.
- **The user's words.** The goal and the asks (`--goal`, `--ask`, `isa write <ISA> asks`) are pieces copied from the user's words: the session's prompts, and the user's answers to AskUserQuestion. A piece may leave out text in between with `…`, as long as each part is copied exactly. Differences in spacing and line breaks don't count. A refused piece is answered with the closest pieces of the user's words, to copy.
- **One way to write criteria, in every tier.** `isa write <ISA> ISC-N "<text>" --probe "<cmd>" --kind K [--fails-when F]` writes a criterion and its probe in one call, E1 to E4. Writing Criteria and Test Strategy as a block is removed, so the model never writes YAML.
- **An Anti at the first command.** `isa write` on an `Anti:` criterion sets `--kind regression` itself, and refuses a probe without `--fails-when` on the spot, quoting the corrected command.
- **A criterion with nothing to run.** It is `--kind manual`, with no command: it is never run at red, green or close, and is ticked with `isa attest <ISA> ISC-N "<evidence>"`, one line saying why it holds. There is no kind that passes without evidence. A claim that needs no proof at all is not a criterion: it goes in Decisions, or is dropped.
- **A leaf that becomes a parent.** Adding the first child under a leaf that has a probe is refused, quoting `isa write <ISA> ISC-k --no-probe`, which removes that leaf's probe. So a parent never keeps a probe that no command can remove.
- **Spec sections by number.** `isa write <spec> "S4 — <title>"` replaces the section numbered S4, renaming it, instead of adding a second S4. `isa drop <spec> S<n> "<why>"` removes a section from a draft spec.
- **Classifier fixes.**
  - Backslash-escaped backticks and `\$(` inside double quotes are not command substitution.
  - `for` and `while` loops are parsed, so the body is classified: a loop of `isa` and read commands is an `isa` command.
- **One place for the rules.** protocol.md, injected when a session turns ON, states every rule the commands and lint enforce. The guard on scripts that name an ISA path stays; protocol.md says project files are edited with Edit or Write.
Accepted when:
- `--goal "update the status line ISA handler"` is accepted from the prompt "I want you to update the status line ISA handler: …"; `--goal "update the status line … handler"` is accepted; `--goal "update the ISA status line"` is refused with "update the status line ISA handler" quoted as the closest piece
- an `--ask` copied from an AskUserQuestion answer of the session is accepted
- an E1 ISA written only with `isa write <ISA> ISC-N "<text>" --probe …` lints clean, and `isa write <ISA> Criteria` or `Test Strategy` is refused, naming the per-criterion command
- `isa write <ISA> ISC-3 "Anti: x" --probe "true"` with no `--fails-when` exits 1 and quotes the command with `--fails-when "<what it would see>"`; with it, the entry has `kind: regression`
- `isa write <ISA> ISC-4 "x" --kind manual` with no `--probe` lints clean; `isa verify --red`, `isa verify` and `isa close` don't run it; `isa close` refuses until `isa attest <ISA> ISC-4 "<evidence>"`
- with ISC-7 a leaf that has a probe, `isa write <ISA> ISC-7.1 "x"` exits 1 quoting `isa write <ISA> ISC-7 --no-probe`; after that command, ISC-7 has no Test Strategy entry, `isa write <ISA> ISC-7.1 "x" --probe "true"` succeeds, and lint reports no parent probe
- in a draft spec with `## S4 — Old`, `isa write <spec> "S4 — New"` leaves one S4 section, headed `S4 — New`; `isa drop <spec> S4 "x"` removes it; both are refused on an acked spec
- the classifier rates `isa new x --goal "a \`b\` c"` and `for n in 1 2; do isa write F ISC-$n --probe x; done` as `isa-cmd`, and `for f in a b; do grep x "$f"; done` as `read`
- protocol.md states the user's-words rule, the Anti rule, the manual kind with `isa attest`, and the one way to write criteria

## S4 — Each probe runs three times

A probe runs once red, once green and once at close, in every project.
- **Red.** `isa verify --red` runs the behaviour probes only. A regression or Anti probe has no red run: its `fails-when` says what failure would look like.
- **Green.** `isa verify` runs only the probes that aren't green yet, and those whose command changed since their green run. `isa verify ISC-N` re-runs one on purpose; that is the exception, after work that could affect it.
- **Regression.** `isa close` runs every probe once.
Accepted when:
- in an ISA with three behaviour probes and one regression probe:
  - `isa verify --red` runs the three behaviour probes only;
  - then `isa verify` runs all four;
  - a second `isa verify`, with nothing changed, runs none and says so;
  - after `isa write <ISA> ISC-2 --probe "<new>"`, `isa verify` runs ISC-2 only, and `isa verify ISC-1` runs ISC-1;
  - `isa close` runs all four once

## S5 — Proof output and small fixes

- **Failure output.** `isa verify` and `isa close` print, for each failing probe, the last 40 lines of its stdout and stderr, and write its full output to `<ISA folder>/runs/ISC-N.log`.
- **A behaviour probe that passes at red is flagged, not refused.** Red stays after the ISA ack, and nothing changes the acked ISA there. `isa verify --red` still exits 0, but:
  - its output ends with a box naming each such ISC: "⚠ ISC-N passed before the build: this probe proves nothing yet";
  - that ISC's red line in the ISA's Verification reads `red PASS ⚠ not seen failing`, so `isa show` shows it;
  - the summary of `isa close`, and the plan (E2+), list them under "Never seen failing".
  The probe still counts when it passes later: nothing is blocked.
- **`isa open` opens the file for writing.** The user may edit a spec or an ISA by hand: `isa open` no longer adds `-R` for vi, vim and nvim. FOUNDATION_2 binds the model, not the user: `isa open` starts an editor in the user's terminal, never through a tool call. A hand edit of an acked file is caught as today: an ISA changed since its ack goes back to ISA DRAFT and needs a new ack; a spec changed since the ISA was derived sends the ISA to ISA REFINE. The docstring, `isa --help` and the statusline README stop saying read-only.
- **Stale doc.** `adapters/claude-statusline/README.md` names the helpers `isa status` really uses (`isafile.parse`, `isafile.leaves`, `isafile.progress`), not `collect_iscs` and `leaf_iscs`.
Accepted when:
- a probe `sh -c 'echo first; seq 1 100; echo boom >&2; exit 3'` fails in `isa verify` with `boom` and `100` in the output and `first` absent, and the log file holds all 102 lines
- `isa close` shows the same output for a probe that fails at close
- `isa verify --red` with a `behaviour` probe `true` exits 0, ends with the ⚠ box naming that ISC, and writes `red PASS ⚠ not seen failing` on its red line
- after that ISC passes `isa verify`, `isa close` succeeds and lists it under "Never seen failing", in its summary and in the plan
- with `ISA_EDITOR` set to `nvim`, `vim` or `vi`, `isa open` starts the editor with the file and no `-R`
- an ISA acked, then edited by hand, is in ISA DRAFT with "changed since its ack", as with any other change
- `rg -n -- '-R|read-only' adapters/claude-statusline/README.md runtime/isa/status.py` finds nothing about `isa open`, and `rg -n 'collect_iscs|leaf_iscs' adapters/` finds nothing

## S6 — The user's click can't be forged

Only the harness runs the hooks: Claude Code runs `isa hook claude` from settings.json, and pi's extension starts `isa hook pi` itself, neither through a tool call. Today `classify.py` lets every `isa` command through, and `isa hook` trusts the event it reads on stdin, so a Bash call that pipes in a made-up "AskUserQuestion answered Acknowledge" event records a click that `isa ack` accepts.

The same goes for `isa open` once it opens files for writing (S5): from a tool call, `ISA_EDITOR="sed -i …" isa open` would write the spec or the ISA. Only the user runs it, in their terminal.

The classifier rates as `guarded`, refused in every stage and with the session OFF, a tool call that runs:
- `isa hook …`;
- `isa open …`, except `isa open … --print`, which only prints the path;
- with any launcher path (`isa`, `~/.local/bin/isa`, `runtime/bin/isa`), and with environment assignments or wrappers in front;
- or as `python3 -m isa.cli …` or `python3 <path>/isa/cli.py …`;
- and the same inside a pipeline, a `;` or `&&` list, a loop or a substitution.

The refusal says that only the harness runs `isa hook`, that an ack is asked with AskUserQuestion, and that `isa open` is for the user's terminal. Foundations.md (FOUNDATION_2) and protocol.md say so.
Accepted when:
- `echo '{}' | isa hook claude`, `isa hook pi < e.json`, `ISA_HOME=/tmp/x ~/.local/bin/isa hook claude < e.json`, `python3 -m isa.cli hook claude < e.json` and `true && isa hook claude` are refused as `guarded` in TRIAGE, SPEC DRAFT and BUILD, and with the session OFF
- `isa open`, `isa open spec` and `ISA_EDITOR=sed isa open isa` are refused as `guarded` in the same stages; `isa open --print` is not
- `isa status`, `isa ack <spec>`, `isa lint <spec>` and `grep -n hook runtime/isa/cli.py` are not refused: the word `hook` alone isn't the entry point
- the harnesses' own calls still record a real click: one Claude Code event and one pi event through the real `isa hook` process each add a row to `acks.jsonl`

## S7 — Answering Jev's flags with a real review

Jev's `serves` flag asks whether a criterion is needed at all. Today it is answered with `rebuttal:`, which `isa review` itself suggests, and the model rebuts by pointing at the spec line the criterion came from. That proves where it came from, not that it is needed: in this task's own review, three of the four flagged criteria, and one unflagged, were not needed.

A flag is answered by judging the criterion itself, on three questions:
- **Necessary?** What would go wrong, unnoticed, without it?
- **Duplicate?** Does another criterion, or a test an existing probe already runs, prove the same thing?
- **Malformed?** Is the claim vague, does the probe miss the claim, or is the kind wrong?

The answers to `isa review <ISA> --answer R<n> "<answer>"` become:
- `keep: <what would go unnoticed without it>`. A `keep:` that gives the spec as its reason (it names a section `S<n>`, "the spec" or "Accepted when") is refused: where a criterion comes from is not why it is needed;
- `drop: <duplicate of … | not needed because …>`, accepted only once the ISC is dropped (`isa drop`);
- `fix: <what was malformed, and the change>`, accepted only once the ISC's text or probe changed since the review;
- `reopen: <the spec change>`, as today.

`rebuttal:` and `fixed:` are removed. The same three questions apply to every criterion, flagged or not: the checklist gets a seventh line, `redundant:`, naming the criteria the model finds unnecessary, duplicated or malformed, or `none`. `isa review`'s output, protocol.md and SKILL.md give the three questions and the four answers.
Accepted when:
- `isa review <ISA> --answer R1 "rebuttal: x"` exits 1, naming `keep:`, `drop:`, `fix:` and `reopen:`
- `--answer R1 "keep: S3 asks for it"` and `"keep: the spec's Accepted when names it"` are refused; `"keep: without it a broken parser would pass unnoticed"` is accepted
- `--answer R1 "drop: duplicate of ISC-7"` is refused while the flagged ISC is live, naming `isa drop <ISA> ISC-N`, and accepted after it
- `--answer R1 "fix: …"` is refused while the flagged ISC is unchanged since the review, and accepted after `isa write` changes it
- a checklist without a `redundant:` line is refused, naming it
- `isa review`'s output, protocol.md and SKILL.md name the three questions, and none of them says `rebuttal`

## Decisions

- 2026-10-13: Approach 1, chosen by the user: `unknown` runs before BUILD in every tier, checked once at the spec's ack, with no git call per command.
- 2026-10-13: a non-spec change refuses the spec's ack and lists the files (the user's answer).
- 2026-10-13: spec-related paths are `docs/` files and folders, at any depth, whose name starts with `<date>-<slug>` (the user's answer).
- 2026-10-13: S1–S7 stay in one spec (the user's answer).
- 2026-10-13: the goal and the asks stay copied pieces of the user's words, which may leave text out with `…`. The user's answers to questions count as their words (the user's answers).
- 2026-10-13: one per-criterion `isa write` for every tier, with loops of `isa` commands allowed; a batch command was not chosen (the user's answer).
- 2026-10-13: each probe runs once red, once green and once at close. A re-run is the exception, asked for by naming the ISC (the user's answer).
- 2026-10-13: S4 keeps only the probe runs; this repo's suite speed and mocks are removed (the user's answer).
- 2026-10-13: the forged-click hole is closed in this spec (S6): a tool call can't run the hook entry point. Rules for this repo's own tests are not added (the user's answer).
- 2026-10-13: S5's failure output (last 40 lines, full log in `runs/ISC-N.log`) and the README fix accepted (the user's answers).
- 2026-10-13: `isa verify --red` stays after the ISA ack; a behaviour probe that passes there is flagged, never refused, and nothing is run before the ack (the user's answer).
- 2026-10-13: a criterion with nothing to run is `manual`, ticked with `isa attest` and one line of evidence; no evidence-free "pass" kind (the user's answer).
- 2026-10-13: `isa open` opens for writing, and only the user runs it; a separate tool was not chosen, since it would need the same guard (the user's answer).
- 2026-10-13: `isa status --json --raw` removed from S3: `cat` already reads the session state at every stage; it was not needed (the user's answer to the review).
- 2026-10-13: Jev's flags are answered by judging the criterion (necessary, duplicate, malformed), never by citing the spec (S7, the user's answer).
- 2026-10-13: a leaf with a probe becomes a parent only after `isa write <ISA> ISC-k --no-probe`, found when ISC-7 turned into S7's parent (the user's answer).

## Open questions
