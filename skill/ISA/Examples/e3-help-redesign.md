---
task: "Redesign the duck CLI's --help for first-encounter clarity"
slug: 20260411-191500_duck-help-redesign
project: DuckHelpRedesign
effort: E3
phase: execute
progress: 5/36
started: 2026-04-11T02:15:00Z
updated: 2026-04-15T18:00:00Z
---

<!-- Fictitious example. "duck" is a teaching placeholder for an existing CLI tool whose --help output we are redesigning. -->

## Problem

The `duck` CLI's `--help` output is 187 lines, formatted as one block per flag in declaration order, with usage examples buried at line 142. New users land on it, scan for 4 seconds, hit Ctrl-C, and `man duck` instead. We track help-to-first-command time at 95 seconds (median for new installs) and the dominant time-sink in those 95 seconds is "scrolling through --help and giving up." The reference content is fine; the layout is not.

## Vision

A `duck --help` that a first-time user can read top-to-bottom in 30 seconds and walk away knowing: (a) what duck does in one sentence, (b) the two most-common invocations, (c) where to find more — and only after that, the full flag reference. Delight: a new user lands on the redesigned help, types one of the example invocations within 15 seconds, and it works. They never visit the man page on their first session.

## Out of Scope

- **No new flags or behavior.** Reference content stays identical; only layout, ordering, and density change.
- **No man-page redesign.** `man duck` is the deep reference; this work is the front door, not the library.
- **No interactive help (`duck help`).** Stays a one-shot stdout dump like every other Unix CLI.
- **No color support added or removed.** Existing color behavior stays; this is content-and-layout work.
- **No localization.** English only, same as the rest of duck.

## Principles

- The first 30 seconds are the entire user experience for 80% of new users. The output is optimized for them, not for power users (who use `man` or `--help <flag>`).
- A help screen is a teaching surface, not a reference dump. Reference belongs in `man`.
- Whitespace is a feature. Density alone is not friendliness.
- Examples teach faster than prose. The first concrete invocation goes above the first flag definition.
- Progressive disclosure: highest-information-per-pixel content first, full flag table last.

## Constraints

- Output stays plain text suitable for piping to `less`, `grep`, etc. — no terminal-control escapes for the layout itself.
- Total length ≤ 100 lines (current: 187 lines).
- Renders correctly at 80-column width (no wrapped lines that break alignment).
- Must include every flag the current help includes — no flag omissions.
- Build process: `duck --help` reads from a single template file at compile time; the redesign updates that template, not the runtime renderer.
- Backwards-compat: `duck --help | rg <flag-name>` continues to find each flag (so existing scripts that grep --help don't break).

## Goal

Ship a redesigned `duck --help` template (≤ 100 lines, 80-col safe) that opens with a one-sentence project summary, shows the two most-common usages as concrete examples, lists the flag reference grouped by category (not declaration order), and ends with a "see also" footer pointing at man + docs URL — all reference content preserved, all flags still grep-able, first-time-user help-to-first-command time drops from 95s median to ≤ 30s median.

## Criteria

### Length and layout

- [x] ISC-1: `duck --help` prints ≤ 100 lines (current baseline 187).
- [x] ISC-2: Every line of `duck --help` is ≤ 80 columns.
- [ ] ISC-3: Output has exactly three sections: Summary+Examples, Flag Reference, See Also.

### Top-section content

- [x] ISC-4: First non-blank line is one sentence of ≤ 80 characters.
- [ ] ISC-5: Examples block holds exactly 2 invocations, each with a one-line gloss.
- [ ] ISC-6: Each example invocation runs and exits 0 against the test fixtures.

### Flag reference

- [ ] ISC-7: Flags are grouped under at most 4 category headers.
- [ ] ISC-8: Each flag entry is exactly 2 lines: signature, then 4-space-indented description.
- [ ] ISC-9: Within each category, flags are in alphabetical order.
- [ ] ISC-10: Every flag from the old 187-line help appears in the new layout.

### See-also footer

- [ ] ISC-11: Footer holds exactly three items: man page, docs URL, version + short-sha.
- [ ] ISC-12: Footer URL sits on a single line of ≤ 80 characters.

### Backwards-compat

- [x] ISC-13: The existing per-flag grep finds every flag name in the new output.
- [x] ISC-14: `duck --help` still exits 0.
- [ ] ISC-15: `man duck` still points to `--help`, and that output opens with Examples.

### Performance

- [ ] ISC-16: New-user median time from `--help` to first real command is ≤ 30s.
- [ ] ISC-17: Help-screen render time stays under 50ms.

### Antecedent ISCs (experiential preconditions)

- [ ] ISC-18: Antecedent: every synonym swap in the line-1 description makes it less accurate or weaker.
- [ ] ISC-19: Antecedent: the two examples are the top two invocations from 30 days of telemetry.
- [ ] ISC-20: Antecedent: new users guess a random flag's category from its name ≥ 70% of the time.

### Voice and tone

- [ ] ISC-21: Each flag description is ≤ 80 characters and written in imperative mood.
- [ ] ISC-22: Zero "Note:" preambles appear in the help output.
- [ ] ISC-23: The word "please" appears nowhere in the help output.

### Anti-criteria

- [ ] ISC-24: Anti: out of scope — the flag count is unchanged from the baseline.
- [ ] ISC-25: Anti: regression — `duck --help`, `duck -h`, and `duck help` print identical output.
- [ ] ISC-26: Anti: footer drift — version and sha come from build-time placeholders, never hand-edited.
- [ ] ISC-27: Anti: density creep — no flag description wraps onto a second line.

### Migration discipline

- [ ] ISC-28: `docs/help-redesign-diff.md` captures the old-vs-new template diff.
- [ ] ISC-29: A release note of ≤ 300 words exists at `docs/release-notes/help-redesign.md`.
- [ ] ISC-30: Five anonymized user-test recordings are saved under `research/user-tests/help-redesign-2026-04/`.

### Minimal-structure discipline

- [ ] ISC-31: Every help section is between 4 and 70 lines long.
- [ ] ISC-32: The Examples block has no "useful flag combinations" appendix.

### Publishing

- [ ] ISC-33: The `templates/help.txt` commit message links the redesign Decisions entry.
- [ ] ISC-34: The new help ships behind a build flag for one release before default.
- [ ] ISC-35: Existing CI test `test/help-grep.sh` passes against the new template.

### Long-tail observation

- [ ] ISC-36: At day 30 after ship, the ISC-16 median still holds at ≤ 30s.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  check: --help line count
  threshold: ≤ 100
  tool: duck --help | wc -l

- isc: ISC-2
  type: bash
  check: lines longer than 80 columns
  threshold: "0"
  tool: duck --help | awk 'length>80' | wc -l

- isc: ISC-3
  type: bash
  check: section rule lines
  threshold: "3"
  tool: duck --help | rg -c '^[═─]{10,}'

- isc: ISC-4
  type: bash
  check: first non-blank line is one sentence ≤ 80 chars
  threshold: prints ok
  tool: duck --help | awk 'NF{print; exit}' | awk 'length<=80 && /\.$/ && gsub(/\. /,"&")==0 {print "ok"}'

- isc: ISC-5
  type: bash
  check: invocation lines and gloss lines in the Examples block
  threshold: 2 lines starting with "$ duck", each followed by an indented gloss
  tool: duck --help | sed -n '/^Examples/,/^[═─]/p' | rg -c -A1 '^  \$ duck'

- isc: ISC-6
  type: bash
  check: each example actually runs
  threshold: exit 0 on all
  tool: bash test/help-examples.sh

- isc: ISC-7
  type: bash
  check: category header count in Flag Reference
  threshold: 1–4
  tool: duck --help | sed -n '/^Flag Reference/,/^See Also/p' | rg -c '^[A-Z][A-Za-z ]+:$'

- isc: ISC-8
  type: unit-test
  check: every flag entry is signature line + one 4-space description line
  threshold: test passes
  tool: bun test test/help-layout.test.ts -t "two-line entries"

- isc: ISC-9
  type: unit-test
  check: flag order inside each category
  threshold: equal to sorted order
  tool: bun test test/help-layout.test.ts -t "alphabetized"

- isc: ISC-10
  type: bash
  check: every old flag is in new help
  threshold: empty diff
  tool: diff <(rg -o '^\s*--[a-z-]+' old-help.txt | tr -d ' ' | sort -u) <(rg -o '^\s*--[a-z-]+' new-help.txt | tr -d ' ' | sort -u)

- isc: ISC-11
  type: bash
  check: See Also footer lines
  threshold: 3 lines matching man / https / version patterns, in that order
  tool: duck --help | sed -n '/^See Also/,$p' | rg -c '^  (man duck|https://|duck v[0-9.]+ \([0-9a-f]{7}\))'

- isc: ISC-12
  type: bash
  check: footer URL line length
  threshold: ≤ 80
  tool: duck --help | rg '^  https://' | awk '{print length}'

- isc: ISC-13
  type: bash
  check: existing per-flag grep
  threshold: exit 0
  tool: bash test/help-grep.sh

- isc: ISC-14
  type: bash
  check: exit code
  threshold: "0"
  tool: duck --help >/dev/null; echo $?

- isc: ISC-15
  type: bash
  check: man page reference and Examples-first output
  threshold: both greps exit 0
  tool: man duck | grep -q 'see `--help`' && duck --help | awk 'NF' | sed -n 3p | grep -q '^Examples'

- isc: ISC-16
  type: manual
  check: median help-to-first-command time
  threshold: ≤ 30s median across 5 users
  tool: 5 user-test sessions, time-stamped recordings

- isc: ISC-17
  type: bash
  check: render time
  threshold: mean < 50 ms
  tool: hyperfine --warmup 3 --export-json /tmp/h.json 'duck --help' && jq '.results[0].mean*1000' /tmp/h.json

- isc: ISC-18
  type: manual
  check: 3 synonym-swapped paraphrases of line 1
  threshold: all 3 reviewers rate every paraphrase worse
  tool: review by 3 unfamiliar reviewers

- isc: ISC-19
  type: bash
  check: top two invocations in the last 30 days of telemetry
  threshold: equal to the two example commands
  tool: diff <(duck-telemetry top-invocations --days 30 -n 2) <(duck --help | rg -o '^  \$ \K.*')

- isc: ISC-20
  type: manual
  check: category-guess accuracy
  threshold: ≥ 70% across 5 users × 10 flags
  tool: structured user test with the four category names only

- isc: ISC-21
  type: eval
  check: description length and imperative mood
  threshold: 100% of descriptions ≤ 80 chars and judged imperative
  tool: bun test test/help-voice.test.ts   # length check + LLM-judge rubric "starts with an imperative verb"

- isc: ISC-22
  type: bash
  check: "Note: preambles"
  threshold: zero matches (rg exits 1)
  tool: rg '^\s*Note:' new-help.txt

- isc: ISC-23
  type: bash
  check: the word please
  threshold: zero matches (rg exits 1)
  tool: rg -wi 'please' new-help.txt

- isc: ISC-24
  type: bash
  check: flag count old vs new
  threshold: equal
  tool: test $(rg -c '^\s*--' old-help.txt) -eq $(rg -c '^\s*--' new-help.txt)

- isc: ISC-25
  type: bash
  check: --help, -h and help all match
  threshold: both diffs empty
  tool: diff <(duck --help) <(duck -h) && diff <(duck --help) <(duck help)

- isc: ISC-26
  type: bash
  check: placeholders in the template, no literal version
  threshold: 2 placeholders found, zero literal version strings
  tool: rg -c '\{\{(VERSION|SHA)\}\}' templates/help.txt && ! rg -q 'v[0-9]+\.[0-9]+\.[0-9]+' templates/help.txt

- isc: ISC-27
  type: unit-test
  check: description lines per flag
  threshold: exactly 1 for every flag
  tool: bun test test/help-layout.test.ts -t "single-line descriptions"

- isc: ISC-28
  type: bash
  check: diff document exists and holds a diff
  threshold: ≥ 1 line starting with + or -
  tool: rg -c '^[+-]' docs/help-redesign-diff.md

- isc: ISC-29
  type: bash
  check: release note word count
  threshold: 1–300
  tool: wc -w < docs/release-notes/help-redesign.md

- isc: ISC-30
  type: bash
  check: recording count
  threshold: "5"
  tool: ls research/user-tests/help-redesign-2026-04/*.mp4 | wc -l

- isc: ISC-31
  type: unit-test
  check: lines per section
  threshold: every section 4–70
  tool: bun test test/help-layout.test.ts -t "section lengths"

- isc: ISC-32
  type: bash
  check: combinations appendix
  threshold: zero matches (rg exits 1)
  tool: duck --help | rg -i 'combination|recipes|more examples'

- isc: ISC-33
  type: bash
  check: commit message references the Decisions entry
  threshold: ≥ 1 match
  tool: git log -1 --format=%B -- templates/help.txt | rg -c 'Decisions 2026-04'

- isc: ISC-34
  type: bash
  check: build flag introduced one release before it defaults on
  threshold: tag distance = 1
  tool: bash scripts/flag-release-distance.sh NEW_HELP

- isc: ISC-35
  type: bash
  check: CI grep test against the new template
  threshold: exit 0
  tool: bash test/help-grep.sh templates/help.txt

- isc: ISC-36
  type: bash
  check: day-30 median help-to-first-command time
  threshold: ≤ 30s
  tool: duck-telemetry help-to-first-command --since-ship 30d --stat median
```

## Features

```yaml
- name: TopSection
  description: One-sentence summary + 2 example invocations with annotations
  satisfies: [ISC-4, ISC-5, ISC-6, ISC-18, ISC-19]
  depends_on: []
  parallelizable: false  # the opener gates everything

- name: FlagReference
  description: Reorder flags into ≤ 4 categories, alphabetize within, 2-line entries
  satisfies: [ISC-7, ISC-8, ISC-9, ISC-10, ISC-20, ISC-21]
  depends_on: [TopSection]
  parallelizable: false

- name: SeeAlsoFooter
  description: Man-page ref + docs URL + version/sha
  satisfies: [ISC-11, ISC-12, ISC-26]
  depends_on: [FlagReference]
  parallelizable: true

- name: BackwardsCompat
  description: --help -h and help all produce same output; flag-grep still works
  satisfies: [ISC-13, ISC-14, ISC-15, ISC-25, ISC-35]
  depends_on: [FlagReference, SeeAlsoFooter]
  parallelizable: true

- name: UsabilityValidation
  description: 5 user-test sessions for help-to-first-command + category intuition
  satisfies: [ISC-16, ISC-20, ISC-30]
  depends_on: [TopSection, FlagReference, SeeAlsoFooter]
  parallelizable: true
```

## Decisions

- 2026-04-11 02:15: Three top-level sections — Summary+Examples / Flag Reference / See Also — locked. Resists the "one more category" temptation that ate the last help redesign attempt.
- 2026-04-12 14:00: ❌ DEAD END: Tried 5 categories instead of 4. Users in pilot test split 60/40 on which category three flags belonged to. Reverted to 4 categories with clearer names. Don't retry.
- 2026-04-13 09:00: refined: ISC-19 sharpened from "examples reflect common usage" to "examples are the two highest-frequency invocations from 30-day telemetry" — the first phrasing let me cherry-pick aspirational examples; the second forced honesty.
- 2026-04-13 22:00: refined: ISC-8 sharpened from "flags formatted clearly" to "exactly 2 lines per flag, line 1 fixed-width, line 2 indented 4 spaces" — vague aesthetic claims are how help screens drift back to inconsistent layout over time.
- 2026-04-14 11:30: ❌ DEAD END: Tried inline color highlighting for flag names. Broke piping to `grep` and `less` for users without color-aware pagers. Reverted to plain text. Don't retry.
- 2026-04-15 16:00: refined: ISC-16 added a 30-day post-ship probe (ISC-30) — without it, the redesign passes its launch test but could regress in 90 days as new flags are added without category discipline.

<!--
E3 design ISA. Required sections: Problem, Vision, Out of Scope, Constraints, Goal, Criteria, Features, Test Strategy.
Optional Principles included — the design has experiential goals (first 30 seconds, recognition, intuition) and principles do real work in the design pass.
Three Antecedent ISCs (ISC-18, 19, 20) carry the experiential contract: hard-to-vary one-sentence summary, telemetry-grounded examples, and intuitive categories. Anti-criteria (ISC-24, 25, 26, 27) cover scope, regression, drift, and density. The Decisions section shows two ❌ DEAD ENDs and three refinements — typical for a redesign where every aesthetic temptation needs to be tested against actual users.
-->
