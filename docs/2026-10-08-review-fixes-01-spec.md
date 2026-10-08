---
status: "acked 2026-10-08 #09413a8a"
effort: E2
---

# Review fixes: the perimeter, the stages of `isa verify`, closed work, forged acks, commits

## Problem

The review of 848222f..HEAD (2026-10-08) found eight bugs in the engine built on the three foundations. The two high ones break the foundations themselves:
- FOUNDATION_2: shell commands that reach `~/.isa` or a spec through `$HOME`, or through a `cd` earlier in the same command, are classified as plain project writes and go through in BUILD. Commit 6888294 opened the `cd` case.
- FOUNDATION_1: `isa verify` runs arbitrary probes in any stage, so work can start before the user's ack.
The rest: after an E2+ close the session stays bound to the finished spec, whose next command is refused; a closed ISA can still be changed, and `isa ack` sets it back to BUILD with no new click; an ack question can arrive with its answer pre-filled by the model; a failed commit at close is silent; a staged rename loses its old path in the work commit; and an `isa` command with `$(isa …)` counts as a project change.

## Goal

Each of the eight bugs is fixed in `runtime/`, each fix is proven by a test that fails on the current code, and every existing suite still passes.
Said:
- fix all these bugs with a proper spec
Assumed:
- "all these bugs" are findings 1–8 of the review, including the `--timeout abc` crash listed under 8.
- a probe that the classifier judges `guarded` is refused when it is written (`isa write … --probe`) and when it would run (`isa verify`, `isa close`): probes are commands like any other under FOUNDATION_2.
- PreToolUse runs before Claude Code shows the question to the user, so any `answers` present at PreToolUse came from the model; denying those is enough, and PostToolUse keeps reading the answer where it finds it today.
- a close whose commit fails still closes (the probes passed); the summary names what was not committed and why, and the user commits by hand.
- after the close, `python3 install.py` installs the fixed engine, so the hooks of the next sessions use it.

## Out of scope

Sandboxing probes beyond the classifier check (a probe that runs a script can still do what the script does). The `ISA: ` binding of any `isa` command's output. The open items in AGENTS.md § Issues. Parsing nested `$(…)`: a nested substitution stays `unknown`.

## Constraints

- `runtime/` stays standard-library only; every file stays under 50 KB.
- Every case in `tests/test_bash_classifier.py` keeps its current kind, the `MENTIONS` table included (a commit message naming `~/.isa` stays a `write`).
- The hooks still fail open on a crash.

## S1 — The perimeter sees $HOME, cd and git -C

`classify.bash` resolves `$HOME` and `${HOME}` like `~`. It follows a `cd <dir>` (and `pushd`) from one segment to the next, so later relative targets are judged in that directory. It judges `git -C <dir>` / `--git-dir` / `--work-tree` against that directory. In code (an `unknown` command) it also recognises `.isa` as a path component next to a HOME lookup.
Accepted when:
- `echo x > $HOME/.isa/p/x/ISA.md`, `echo x > ${HOME}/.isa/p/x/ISA.md`, `cp /tmp/a $HOME/.isa/p/x/ISA.md`, `rm -rf $HOME/.isa`, `sed -i s/a/b/ $HOME/.isa/p/x/ISA.md` and `echo x | tee $HOME/.isa/p/x/ISA.md` classify as `guarded`
- `cd ~/.isa/p/x && rm ISA.md`, `cd ~/.isa/p/x && echo hi > ISA.md` and `cd docs && cp /tmp/a 2026-10-06-x-01-spec.md` classify as `guarded`
- `git -C ~/.isa commit -am x` and `cd ~/.isa && git add -A` classify as `guarded`
- `python3 -c "import os; open(os.environ['HOME']+'/.isa/x','w')"` classifies as `guarded`
- `cd src && rm x` stays `write` and `cd /tmp && rm x` stays `read`
- through the Claude Code hook, `rm -rf $HOME/.isa/<project>` in BUILD is denied with the perimeter message

## S2 — isa verify runs in BUILD only, and never a guarded probe

`isa verify` (with or without `--red`) checks the stage before running anything. From E2, the ISA must be acked as it is now, its spec acked, and the spec unchanged since the ISA was derived. E1 is unchanged: an E1 ISA that lints is in BUILD. A probe is a shell command like any other, so the classifier judges it when it is written and before it runs.
Accepted when:
- on an E2+ ISA that is not acked as it is now, `isa verify` and `isa verify --red` exit 1, run no probe, leave the ISA byte-identical, and name the next step (`isa show <ISA> --to Criteria`, then the `ISA ack` question)
- the same refusal when its spec is reopened (`isa ack` of the spec next) or changed since the ISA was derived (`isa refine` next)
- an E1 ISA that lints still verifies as today
- `isa write <ISA> ISC-N --probe "<cmd>"` refuses a command that `classify.bash` judges `guarded`, quoting it, and the ISA is unchanged
- `isa verify` and `isa close` refuse an ISA that holds a `guarded` probe, before running any probe

## S3 — A finished spec unbinds

A spec whose plan exists is finished. When the bound ISA is closed, the gate drops both the ISA and its spec from the session, and the stage never offers `isa new --spec` for a finished spec.
Accepted when:
- after an E2 close, the next prompt that turns ON leaves neither the closed ISA nor its spec bound, and a project change is refused with the TRIAGE message
- a bound spec whose plan exists is not treated as open: the next prompt gets Q1, not Q2, and no hook text names `isa new --spec` for it

## S4 — A closed ISA can't change

Every command that writes a TASK ISA refuses one with `phase: complete`, with the one message `isa write` gives today.
Accepted when:
- on a closed ISA, `isa write`, `drop`, `decide`, `verify`, `attest`, `answer`, `ack`, `refine` and `close` exit 1 with "this ISA is closed; new work gets a new ISA", and the file is byte-identical
- `isa show`, `isa diff` and `isa lint` still read a closed ISA

## S5 — No pre-filled answer

An answer the model wrote into its own AskUserQuestion input is not the user's click. PreToolUse refuses such a question when it holds an ack question or the gate question. PostToolUse is unchanged: answers that reach it came from the user.
Accepted when:
- PreToolUse denies an AskUserQuestion holding a `Spec ack` or `ISA ack` question, or the gate's question, whose `tool_input.answers` is non-empty; the denial says the answer is the user's, and no click is recorded
- an ack question with no `answers` at PreToolUse, answered `Acknowledge` at PostToolUse, still records the click and `isa ack` then succeeds

## S6 — A failed commit is reported

`gitops.commit` tells "nothing to commit" apart from a failed `git commit`, and `isa close` and `isa ack <spec>` print the failure. The close still completes: its probes passed.
Accepted when:
- in a repo whose pre-commit hook exits 1, a passing E2 close completes and prints `Not committed: the work — <git's first error line>` and the same for `the plan`
- in that repo, `isa ack <spec>` acks the spec and prints `Not committed: the spec — <git's first error line>`
- a close with nothing to commit prints no `Not committed` line

## S7 — A rename commits both paths

`gitops.dirty` keeps both paths of a rename entry (`R`), so the work commit holds the deletion and the addition.
Accepted when:
- after `isa new`, `git mv a.txt b.txt` and a passing close, the work commit deletes `a.txt` and adds `b.txt`, and `git status --porcelain` is empty

## S8 — isa commands compose

A command made only of `isa` commands and read commands, inside and outside its `$(…)` (no nesting), is an `isa` command. Anything else with `$(…)` keeps today's kind. `isa verify --timeout` takes whole seconds.
Accepted when:
- `isa show "$(isa ls | head -1)"` and `isa new x --tier E1 && isa show "$(isa where | tail -1)"` classify as `isa-cmd`
- `rg foo $(cat list)` stays `unknown`, and `isa show "$(rm x)"` is not `isa-cmd`
- `isa verify <ISA> --timeout abc` exits 1 with `--timeout takes whole seconds` and no traceback

## Decisions

## Open questions
