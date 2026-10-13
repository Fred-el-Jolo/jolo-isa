---
spec: 2026-10-13-isa-friction-01-spec.md
isa: 20261013-162332_isa-friction
closed: 2026-10-13
---

# Plan — ISA friction: fewer refusals, error-proof writing, probe runs and output, no forged clicks, real reviews

## Problem

Before BUILD, the PreToolUse gate refuses every `unknown` call, in every tier: any command the classifier can't prove only reads. That includes `python3 -c "print(1)"`, `node --test`, `python3 -m unittest`, a read-only `for` loop over `grep`, and `jq`. In the 2026-10-13 sessions this blocked an E1 task's scoping and a read-only analysis prompt (no profiler, no test could run), and pushed the model into workarounds that the guard then refused as well. The rule's intent, no project change before the ISA, needs only the recognised writes refused. A change made by a script can be caught later, where it matters: before the spec is committed.

The user's ack can also be forged. Every `isa` command is allowed at every stage, including `isa hook`, which trusts the event on its stdin. A model can pipe a made-up "the user answered Acknowledge" event into it from Bash, and `isa ack` then accepts it as the user's click.

## Vision

Working under ISA costs no friction: before BUILD the model runs any read, test or script that changes nothing it can be seen changing; it writes the ISA without trial and error; a failing probe says why; and only the user can click an ack or open the files for writing.

## Out of Scope

- Running probes in parallel.
- The gate's judgement of analysis-only prompts.
- The status line.
- The speed of this repo's own test suite, and how it mocks Jev (removed from S4 by the user).
- A script written to import the runtime and call its functions directly (e.g. `spec.record_click`): the classifier can't see it. That is a deliberate bypass, not a side door.

## Principles

- Refuse only what is recognised as a change; catch the rest once, when the spec is committed.
- Every rule is known before it can be broken, and every refusal carries the corrected command.
- A probe runs red, green and at close: once each.
- The user's click and the user's editor belong to the user: no tool call reaches them.

## Constraints

- The three foundations stay. FOUNDATION_2 holds: only `isa` commands write ISAs, specs, plans and `~/.isa`, and a `guarded` call is refused in every stage.
- No git call per tool call: git runs only inside `isa ack <spec>`, never in a hook.
- `runtime/` stays standard-library only, and every file stays under 50 KB.

## Goal

Before BUILD, in every tier (E1 to E4), any command runs except a recognised project change. When a spec is acked, the files changed outside the spec since `isa spec new` are listed, and the ack waits until they're gone. The `isa` commands and their docs give every rule before it can be broken. Each probe runs three times: red, green and regression. A failing probe shows why it failed, and a probe never seen failing is flagged. An ack comes only from the user's click: no tool call can feed the hooks an event. The user can edit a spec or an ISA through `isa open`.

## Criteria

- [x] ISC-1: Unknown commands run before BUILD
  - [x] ISC-1.1: In TRIAGE, SPEC DRAFT and ISA DRAFT, in an E1 and an E2 session, python3 -c, node --test, python3 -m unittest and a for loop of grep are allowed
  - [x] ISC-1.2: In the same stages, Write/Edit of a project file, rm, mv, a redirect into a project file and sed -i are refused, naming the stage and the next command
  - [x] ISC-1.3: Anti: a guarded call (a redirect into the ISA, python3 -c naming an ISA path) goes through in any stage
  - [x] ISC-1.4: Foundations.md, protocol.md, SKILL.md and AGENTS.md say what a recognised change is, and no longer say every project change waits for BUILD
- [x] ISC-2: The spec-ack check for non-spec changes
  - [ ] ISC-2.1: [DROPPED — duplicate: test_commits already proves a clean ack commits the spec alone, and ISC-9 runs it; the baseline is proven by ISC-2.2 and ISC-2.3]
  - [x] ISC-2.2: A file changed after isa spec new makes isa ack exit 1 listing its path, with nothing committed; once reverted, isa ack succeeds on the same click
  - [x] ISC-2.3: A file already changed before isa spec new is never listed
  - [x] ISC-2.4: The three spec-related example paths are never listed; docs/other.md and src/a.py are
  - [x] ISC-2.5: Anti: a hook runs git
- [x] ISC-3: Writing the ISA without errors
  - [x] ISC-3.1: --goal and --ask accept copied pieces with … and spacing differences, and a refusal quotes the closest piece of the user's words
  - [x] ISC-3.2: An --ask copied from an AskUserQuestion answer of the session is accepted
  - [x] ISC-3.3: An E1 ISA written only with per-criterion isa write lints clean; isa write Criteria or Test Strategy is refused, naming the per-criterion command
  - [x] ISC-3.4: isa write of an Anti sets kind regression, and refuses a probe without --fails-when at once, quoting the corrected command
  - [x] ISC-3.5: Anti: a --kind manual criterion needs a probe, gets run, or closes without isa attest
  - [x] ISC-3.6: isa write <spec> 'S4 — New' replaces S4 by its number; isa drop <spec> S4 removes it; both refused on an acked spec
  - [x] ISC-3.7: The classifier treats escaped backticks as text and parses for/while loops: a loop of isa commands is isa-cmd, a loop of grep is read
  - [ ] ISC-3.8: [DROPPED — S3 no longer asks for isa status --raw: cat already reads the session state]
  - [x] ISC-3.9: protocol.md states the user's-words rule, the Anti rule, the manual kind with isa attest, and the one way to write criteria
  - [x] ISC-3.10: Adding the first child under a leaf with a probe is refused, quoting isa write <ISA> ISC-k --no-probe; after it, the leaf has no probe entry and the child is accepted
- [x] ISC-4: Each probe runs three times
  - [x] ISC-4.1: isa verify --red runs the behaviour probes only
  - [x] ISC-4.2: isa verify runs the probes not green yet; run again with nothing changed it runs none and says so
  - [x] ISC-4.3: After a probe's command changes, isa verify runs that probe only, and isa verify ISC-N re-runs the one named
  - [x] ISC-4.4: Anti: isa close skips a probe or runs one twice
- [x] ISC-5: Proof output and small fixes
  - [x] ISC-5.1: A failing probe in isa verify shows the last 40 lines of its output, and runs/ISC-N.log holds all of it
  - [x] ISC-5.2: A probe failing at isa close shows the same output
  - [x] ISC-5.3: A behaviour probe passing at red: isa verify --red exits 0, ends with the ⚠ box naming it, and its red line reads red PASS ⚠ not seen failing
  - [x] ISC-5.4: isa close succeeds and lists that ISC under Never seen failing, in its summary and in the plan
  - [x] ISC-5.5: With ISA_EDITOR set to nvim, vim or vi, isa open starts the editor on the file with no -R
  - [ ] ISC-5.6: [DROPPED — duplicate: a hand edit is a text change, already caught by the changed-since-ack check (test_isc_change_breaks_ack, run by ISC-9)]
  - [x] ISC-5.7: The statusline README and status.py no longer call isa open read-only, and the README names no collect_iscs or leaf_iscs
- [x] ISC-6: The user's click can't be forged
  - [x] ISC-6.1: From a tool call, isa hook in all five forms (pipe, redirect, launcher path with env, python3 -m isa.cli, after &&) is refused as guarded in TRIAGE, SPEC DRAFT, BUILD and with the session OFF, while isa status, isa ack, isa lint and grep -n hook are not
  - [x] ISC-6.2: From a tool call, isa open, isa open spec and ISA_EDITOR=sed isa open isa are refused as guarded; isa open --print is not
  - [ ] ISC-6.3: [DROPPED — merged into ISC-6.1: one test checks both what is refused and what is not]
  - [ ] ISC-6.4: [DROPPED — duplicate: test_ack_click_at_post already records a real click through the hook, and ISC-9 runs it]
  - [x] ISC-6.5: Foundations.md and protocol.md say only the harness runs isa hook, an ack is asked with AskUserQuestion, and isa open is for the user's terminal
- [x] ISC-7: Answering Jev's flags with a real review
  - [x] ISC-7.1: isa review --answer with rebuttal: exits 1, naming keep:, drop:, fix: and reopen:
  - [x] ISC-7.2: A keep: answer that gives the spec as its reason (S<n>, the spec, Accepted when) is refused; one that says what would go unnoticed is accepted
  - [x] ISC-7.3: A drop: answer is refused while the flagged ISC is live, naming isa drop, and accepted after it
  - [x] ISC-7.4: A fix: answer is refused while the flagged ISC is unchanged since the review, and accepted after isa write changes it
  - [x] ISC-7.5: A checklist without a redundant: line is refused, naming it
  - [x] ISC-7.6: isa review's output, protocol.md and SKILL.md name the three questions, and none says rebuttal
- [x] ISC-8: Anti: runtime/ imports outside the standard library, or a runtime file reaches 50 KB
- [x] ISC-9: Anti: a test of today fails, or the examples stop linting

## Test Strategy

```yaml
- isc: ISC-1.1
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S1.test_unknown_runs_before_build
- isc: ISC-1.2
  anchors_to: S1
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S1.test_recognised_writes_refused
- isc: ISC-1.3
  anchors_to: S1
  kind: regression
  tool: python3 -m unittest tests.test_friction.S1.test_guarded_refused_everywhere
  fails-when: a guarded call returns no deny in some stage
- isc: ISC-1.4
  anchors_to: S1
  kind: doc
  tool: "grep -q -i recognised skill/ISA/References/Foundations.md && grep -q -i recognised runtime/isa/protocol.md && grep -q -i recognised skill/ISA/SKILL.md && grep -q -i recognised AGENTS.md && ! grep -q 'Project changes go through in BUILD only' skill/ISA/References/Foundations.md && ! grep -q 'goes through in BUILD only' AGENTS.md"
  fails-when: "one of the four docs lacks the word recognised, or keeps the BUILD-only sentence"
- isc: ISC-2.2
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S2.test_non_spec_change_refuses_ack
- isc: ISC-2.3
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S2.test_baseline_files_not_listed
- isc: ISC-2.4
  anchors_to: S2
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S2.test_spec_related_paths
- isc: ISC-2.5
  anchors_to: S2
  kind: regression
  tool: python3 -m unittest tests.test_friction.S2.test_no_git_in_hooks
  fails-when: "a fake git on PATH logs a call during a PreToolUse, PostToolUse or Stop event"
- isc: ISC-3.1
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S3.test_goal_pieces
- isc: ISC-3.2
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S3.test_ask_from_answer
- isc: ISC-3.3
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S3.test_per_criterion_only
- isc: ISC-3.4
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S3.test_anti_at_first_command
- isc: ISC-3.5
  anchors_to: S3
  kind: regression
  tool: python3 -m unittest tests.test_friction.S3.test_manual_kind
  fails-when: "lint asks a manual leaf for a probe, verify runs it, or close succeeds before isa attest"
- isc: ISC-3.6
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S3.test_spec_sections_by_number
- isc: ISC-3.7
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S3.test_classifier_quotes_and_loops
- isc: ISC-3.9
  anchors_to: S3
  kind: doc
  tool: "grep -q '…' runtime/isa/protocol.md && grep -q 'AskUserQuestion answer' runtime/isa/protocol.md && grep -q 'kind regression' runtime/isa/protocol.md && grep -q 'isa attest' runtime/isa/protocol.md && grep -q -- '--kind manual' runtime/isa/protocol.md && grep -q 'Edit or Write' runtime/isa/protocol.md"
  fails-when: one of the six phrases is missing from protocol.md
- isc: ISC-3.10
  anchors_to: S3
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S3.test_leaf_to_parent_no_probe
- isc: ISC-4.1
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S4.test_red_runs_behaviour_only
- isc: ISC-4.2
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S4.test_verify_skips_green
- isc: ISC-4.3
  anchors_to: S4
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S4.test_verify_changed_and_named
- isc: ISC-4.4
  anchors_to: S4
  kind: regression
  tool: python3 -m unittest tests.test_friction.S4.test_close_runs_each_once
  fails-when: a probe that appends to a counter file leaves a count other than 1 per close
- isc: ISC-5.1
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S5.test_failure_output_verify
- isc: ISC-5.2
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S5.test_failure_output_close
- isc: ISC-5.3
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S5.test_red_pass_flagged
- isc: ISC-5.4
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S5.test_close_lists_never_seen_failing
- isc: ISC-5.5
  anchors_to: S5
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S5.test_open_writable
- isc: ISC-5.7
  anchors_to: S5
  kind: doc
  tool: "! grep -n -i 'read-only\\|-R' adapters/claude-statusline/README.md runtime/isa/status.py | grep -q -i open && ! grep -q 'collect_iscs\\|leaf_iscs' adapters/claude-statusline/README.md"
  fails-when: "a line about isa open still says read-only or -R, or the README still names collect_iscs"
- isc: ISC-6.1
  anchors_to: S6
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S6.test_hook_from_tool_call_refused
- isc: ISC-6.2
  anchors_to: S6
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S6.test_open_from_tool_call_refused
- isc: ISC-6.5
  anchors_to: S6
  kind: doc
  tool: "grep -q 'isa hook' skill/ISA/References/Foundations.md && grep -q 'isa hook' runtime/isa/protocol.md && grep -q 'isa open' skill/ISA/References/Foundations.md && grep -q 'isa open' runtime/isa/protocol.md"
  fails-when: "Foundations.md or protocol.md doesn't mention isa hook or isa open"
- isc: ISC-7.1
  anchors_to: S7
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S7.test_rebuttal_removed
- isc: ISC-7.2
  anchors_to: S7
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S7.test_keep_needs_a_real_reason
- isc: ISC-7.3
  anchors_to: S7
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S7.test_drop_needs_the_drop
- isc: ISC-7.4
  anchors_to: S7
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S7.test_fix_needs_a_change
- isc: ISC-7.5
  anchors_to: S7
  kind: behaviour
  tool: python3 -m unittest tests.test_friction.S7.test_checklist_needs_redundant
- isc: ISC-7.6
  anchors_to: S7
  kind: doc
  tool: "grep -q 'Necessary' runtime/isa/review.py && grep -q 'Necessary' runtime/isa/protocol.md && grep -q 'Necessary' skill/ISA/SKILL.md && ! grep -q -i rebuttal runtime/isa/review.py runtime/isa/protocol.md skill/ISA/SKILL.md"
  fails-when: "one of the three files lacks the questions, or still says rebuttal"
- isc: ISC-8
  anchors_to: Constraints
  kind: regression
  tool: "python3 tests/check_stdlib.py runtime/ && test -z \"$(find runtime -path '*/__pycache__' -prune -o -type f -size +50k -print)\""
  fails-when: check_stdlib exits non-zero or find lists a file
- isc: ISC-9
  anchors_to: Constraints
  kind: regression
  tool: "python3 -m unittest tests.test_foundations tests.test_install tests.test_bash_classifier tests.test_derivation && \"$(mise which node)\" --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts && python3 tools/lint_isa.py skill/ISA/Examples/*.md skill/ISA/Examples/specs/*.md"
  fails-when: "a unittest, node test or example lint exits non-zero"
```

## Review

Reviewed 2026-10-13 16:59 · criteria #50bb54a1 · Jev: 1 request, 45 questions
- shared: S1 (unknown before BUILD), S3 (loops, escaped backticks) and S6 (isa hook / isa open guarded) all change classify.py; S7's answer rules and the checklist live in review.py; separate leaves, since each states a different outcome
- prerequisites: S4's "command changed since its green run" needs the probe command on the green run line, which isa verify already writes; S5.3/5.4 rely on the red run line, already written
- contradictions: none
- drift: none
- gaps: none
- context: ISC-8's probe was malformed: it counted __pycache__ files (two .pyc over 50 KB), so it failed at red with no source file over the limit; it now skips __pycache__. Earlier redundant pass: dropped ISC-3.8, 6.4, 5.6, 6.3 (merged into 6.1), 2.1; ISC-3.5 rewritten as an Anti

Flags (each needs an answer before the ISA ack):
- R1: serves ISC-1.3 — no 0.83 ≥ 0.70 — Does criterion ISC-1.3 ("Anti: a guarded call (a redirect into the ISA, python3 -c naming an ISA path) goes through in any stage", see `criteria`) help solve the spec's stated Problem and reach its Goal, and deliver what section S1 ("Unknown commands run before BUILD") asks for? Answer yes when the Problem needs what it claims; no when it is unrelated to the Problem and the Goal, or only restates a detail no part of the spec asks for. — answer: rebuttal: keep — unknown calls will now run before BUILD, and a guarded call is an unknown call naming an ISA path: if the new rule lets unknown through before checking guarded, a script writing the ISA passes unnoticed. Existing tests check a guarded call only in BUILD (test_perimeter_home).
- R2: covered S2 — no 0.78 ≥ 0.70 — Do the criteria under ISC-2 in `criteria` together cover everything section S2 ("The spec-ack check for non-spec changes") asks for in its Accepted-when lines? Answer no when an Accepted-when outcome has no criterion that would prove it. — answer: rebuttal: the clean ack is proven by test_commits, which ISC-9 runs, so ISC-2.1 was dropped as a duplicate; the other outcomes sit under ISC-2.2 to ISC-2.5
- R3: covered S6 — no 0.72 ≥ 0.70 — Do the criteria under ISC-6 in `criteria` together cover everything section S6 ("The user's click can't be forged") asks for in its Accepted-when lines? Answer no when an Accepted-when outcome has no criterion that would prove it. — answer: rebuttal: the real click is proven by test_ack_click_at_post through the real isa hook claude process, which ISC-9 runs; pi's adapter reaches the same engine function, and the new guard only classifies tool calls, so it can't reach that path
- R4: serves ISC-8 — no 0.87 ≥ 0.70 — Does criterion ISC-8 ("Anti: runtime/ imports outside the standard library, or a runtime file reaches 50 KB", see `criteria`) help solve the spec's stated Problem and reach its Goal? Answer yes when the Problem needs what it claims; no when it is unrelated to the Problem and the Goal, or only restates a detail no part of the spec asks for. — answer: rebuttal: keep — commands.py is already 33.5 KB and most of the new code goes there; no other check enforces the 50 KB limit, so a file over it would go unnoticed

## Verification

- Goal: yes — before BUILD only recognised writes wait (S1 tests); the spec's first ack lists non-spec files (S2); goal/asks take pieces and answers, criteria are written one at a time, Antis need fails-when at once, --no-probe, spec sections by number (S3); verify runs red behaviour-only, then only non-green probes (S4); failures show 40 lines + a log, red passes are flagged, isa open is writable (S5); isa hook / isa open are refused from tool calls (S6); review answers judge the criterion (S7); 38/38 probes pass, the existing suite included
