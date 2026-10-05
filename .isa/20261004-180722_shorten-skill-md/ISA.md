---
task: "Shorten skill/ISA/SKILL.md without losing any fact"
slug: 20261004-180722_shorten-skill-md
effort: E2
phase: complete
progress: 10/10
started: 2026-10-04T18:07:22
updated: 2026-10-04T18:33:32
root: .
stated_goal: "enc:v1:0ddf368a:P7kgUYA1zUSaqVfs-bxCL7kxgZLdRa4Pn3eswZO3sDCgw0reBaDK9t-9sSzhh2FSldlTmsvijFSskd-1cVMOBOFXYLSEO5RoU8WZPxT63nS0DhJsorIAZej0RDnNue8q"
stated_goal_source: prompt
asks: ["enc:v1:0ddf368a:P7kgUYA1zUSaqVfs-bxCL7kxgZLdRa4Pn3eswZO3sDCgw0reBaDK9t-9sSzhh2FSldlTmsvijFSskd-1cVMOBOFXYLSEO5RoU8WZPxT63nS0DhJsorIAZej0RDnNue8q", "enc:v1:0ddf368a:PbuhFGkCxjf2DeNafF8Zjbei5Co0PcSa6yIhyIZhcr--5SaylQR5t3CVabX5XZqW-_pLlhOnEw", "enc:v1:0ddf368a:QU5wF7qn81OAXWQfQ771CiZIkxljIduzkf7yLJB3gcqwrVJzeN-gw8IeFh7wxxI1M1D6rMzI0hVhGaVXyt8Fk2FShAML358nmsmFmCtPAENe", "enc:v1:0ddf368a:AYW-eeR5J5NTcc2eWhEtw10f3gXdowZdv99-LMIUnH9PlnbvHQ8oNCDbgovbcoI_d7w", "enc:v1:0ddf368a:QGSQImGXBWYWQCJS0OFnaNrSrDjNsLtMZ9q87KjIS6R_eCmqDZNrVHLGTkEeE2jYLpXJbn03juu3keT0qJ9iK7lgMqzBDuym", "enc:v1:0ddf368a:4jIgCD4cDYvC0reRGTuv_00W3mt7ZTAr5PfGkLOvHaHj3SVH1bwkgaXzd4e8E7JRpUseqHRXiwtmK-SzEW57GORtXXoNexbehpy1Qu50VbZFdzd-kcSSBTISOmw267Da_xnMOcb8GmW5brCT9kSNhCDlmqZNf7LoxsBpqT0FtT7lBUg", "enc:v1:0ddf368a:zryF7AM7oZQpM4izt2bqn8rH7SOivnnlBSUs40D8E0cQ2njC4DVdVYYdgC_8fdRbxkXJ5Zjp4M9p", "enc:v1:0ddf368a:lrTitXIkGsOB69HgjwqcuqrAVgWcUllDXhB7v-W9szGCo6AYhxpLwVHhEZOl9Xk"]
context_sufficient: true
iteration: 3
resumed_at: 2026-10-04T18:45:00
---

## Problem

`skill/ISA/SKILL.md` (311 lines, 5797 words) says several things two or three times: ID stability (Gotcha + its own section), ephemeral files (Gotcha + section), the lifecycle rules that restate completion rules 1/2/8/14, the close list that restates the rules and the close contract, the continuation rule (gate bullet + lifecycle), "skills write only content" (twice). It also contradicts itself: it documents the project ISA (`kind: project`) and then says a project ISA "is not supported". Every session that turns ON reads it, so the duplication costs tokens each time.

## Goal

"enc:v1:0ddf368a:-0xFTd0bbyD4R1qc7I3by6Y3CJ9Ns4aOYGJux8aGP5UOO08xuCPj_jcAJqjn0xtj7uQ1LUJRiSpfJUce4r0Wj_XrgZgdR17PwjaFRKWe4QbbthkUk5ACkPT3YyMEcw" — SKILL.md loses its duplicated wording, keeps every fact and rule, and the user gets a list of exactly what was removed or merged and where each fact now lives.

## Criteria

- [x] ISC-1: SKILL.md has at least 11.5% fewer words than the original.
- [x] ISC-2: Every distinctive token of the original still appears in SKILL.md.
- [x] ISC-3: Every removed passage's meaning is stated elsewhere in SKILL.md.
- [x] ISC-4: The stale "project ISA is not supported" sentence is gone.
- [x] ISC-5: Anti: SKILL.md frontmatter (name, version, description, effort) changed.
- [x] ISC-6: Anti: a LifeOS reference appears anywhere under skill/.
- [x] ISC-7: Anti: the installer, gate or declaration tests regress.
- [x] ISC-8: The five statements the second review found missing are restored.
- [x] ISC-9: Test-first reads as preferred, mandatory only for behaviour/http/schema.
- [x] ISC-10: The Examples intro calls the files reference ISAs again.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "enc:v1:0ddf368a:P7kgUYA1zUSaqVfs-bxCL7kxgZLdRa4Pn3eswZO3sDCgw0reBaDK9t-9sSzhh2FSldlTmsvijFSskd-1cVMOBOFXYLSEO5RoU8WZPxT63nS0DhJsorIAZej0RDnNue8q"
  type: bash
  kind: file
  check: word count of SKILL.md
  threshold: ≤ 5130 words (88.5% of 5797)
  fails-when: "wc -w reports more than 5130 words, e.g. the original 5797"
  tool: test "$(wc -w < skill/ISA/SKILL.md)" -le 5130

- isc: ISC-2
  anchors_to: "enc:v1:0ddf368a:PbuhFGkCxjf2DeNafF8Zjbei5Co0PcSa6yIhyIZhcr--5SaylQR5t3CVabX5XZqW-_pLlhOnEw"
  type: bash
  kind: doc
  check: every line of facts.txt (commands, fields, values, rule names taken from the original) is found verbatim in SKILL.md
  threshold: exit 0
  fails-when: "some fact token such as `jev_quiet` or `ISC-7.1` is missing from the new file and grep -F exits 1"
  tool: |-
    while IFS= read -r t; do [ -z "$t" ] || grep -qF -- "$t" skill/ISA/SKILL.md || { echo "missing: $t"; exit 1; }; done < .isa/20261004-180722_shorten-skill-md/facts.txt

- isc: ISC-3
  anchors_to: "enc:v1:0ddf368a:AYW-eeR5J5NTcc2eWhEtw10f3gXdowZdv99-LMIUnH9PlnbvHQ8oNCDbgovbcoI_d7w"
  type: manual
  kind: doc
  check: side-by-side read of the original (git HEAD) and the new file, passage by passage
  threshold: each removed passage maps to a kept statement with the same meaning
  tool: git diff HEAD -- skill/ISA/SKILL.md, read by hand

- isc: ISC-4
  anchors_to: "enc:v1:0ddf368a:QU5wF7qn81OAXWQfQ771CiZIkxljIduzkf7yLJB3gcqwrVJzeN-gw8IeFh7wxxI1M1D6rMzI0hVhGaVXyt8Fk2FShAML358nmsmFmCtPAENe"
  type: bash
  kind: doc
  check: the contradicting sentence is absent
  threshold: grep finds nothing
  fails-when: "the sentence saying a per-repo project ISA is not supported is still in SKILL.md"
  tool: "! grep -qF 'is not supported' skill/ISA/SKILL.md"

- isc: ISC-5
  anchors_to: "enc:v1:0ddf368a:QU5wF7qn81OAXWQfQ771CiZIkxljIduzkf7yLJB3gcqwrVJzeN-gw8IeFh7wxxI1M1D6rMzI0hVhGaVXyt8Fk2FShAML358nmsmFmCtPAENe"
  type: bash
  kind: file
  check: first 6 lines equal those of HEAD
  threshold: diff exits 0
  fails-when: "diff prints a changed name/version/description/effort line"
  tool: diff <(git show HEAD:skill/ISA/SKILL.md | head -6) <(head -6 skill/ISA/SKILL.md)

- isc: ISC-6
  anchors_to: "enc:v1:0ddf368a:QU5wF7qn81OAXWQfQ771CiZIkxljIduzkf7yLJB3gcqwrVJzeN-gw8IeFh7wxxI1M1D6rMzI0hVhGaVXyt8Fk2FShAML358nmsmFmCtPAENe"
  type: bash
  kind: doc
  check: LifeOS strings under skill/
  threshold: zero hits
  fails-when: "rg prints a line containing lifeos, 31337, MEMORY/WORK, telos or pulse"
  tool: "! rg -q -i 'lifeos|31337|MEMORY/WORK|\\btelos\\b|\\bpulse\\b' skill/"

- isc: ISC-7
  anchors_to: "enc:v1:0ddf368a:QU5wF7qn81OAXWQfQ771CiZIkxljIduzkf7yLJB3gcqwrVJzeN-gw8IeFh7wxxI1M1D6rMzI0hVhGaVXyt8Fk2FShAML358nmsmFmCtPAENe"
  type: bash
  kind: regression
  check: unit tests touching the skill's install and its SKILL.md path
  threshold: exit 0
  fails-when: "unittest reports a failure or error"
  tool: python3 -m unittest tests.test_install tests.test_gate tests.test_declaration 2>&1 | tail -3 | grep -q '^OK'
- isc: ISC-8
  anchors_to: "enc:v1:0ddf368a:zryF7AM7oZQpM4izt2bqn8rH7SOivnnlBSUs40D8E0cQ2njC4DVdVYYdgC_8fdRbxkXJ5Zjp4M9p"
  type: bash
  kind: doc
  check: each restored phrase is in SKILL.md
  threshold: all five grep -F hits
  fails-when: "one of the restored phrases (written testable definition, harness enforces, before building, listed to the user, never left stale) is absent"
  tool: |-
    f=skill/ISA/SKILL.md; grep -qF 'without a written, testable definition of what finished looks like' $f && grep -qF 'the harness enforces this loop' $f && grep -qF 'run `isa verify --red <ISA>` before building' $f && grep -qF 'are listed to the user' $f && grep -qF 'never left stale' $f

- isc: ISC-9
  anchors_to: "enc:v1:0ddf368a:QU5wF7qn81OAXWQfQ771CiZIkxljIduzkf7yLJB3gcqwrVJzeN-gw8IeFh7wxxI1M1D6rMzI0hVhGaVXyt8Fk2FShAML358nmsmFmCtPAENe"
  type: bash
  kind: doc
  check: the red-before-green paragraph says "Prefer" and keeps behaviour/http/schema as the mandatory case
  threshold: grep -F hit
  fails-when: "the paragraph still reads 'Write a runnable probe … first' with no 'Prefer', making test-first mandatory for every runnable probe"
  tool: grep -qF 'Prefer test-first where a probe is runnable' skill/ISA/SKILL.md

- isc: ISC-10
  anchors_to: "enc:v1:0ddf368a:AYW-eeR5J5NTcc2eWhEtw10f3gXdowZdv99-LMIUnH9PlnbvHQ8oNCDbgovbcoI_d7w"
  type: bash
  kind: doc
  check: Examples intro names the files as reference ISAs
  threshold: grep -F hit
  fails-when: "the intro reads '`Examples/` spans tier …' without saying the files are reference ISAs"
  tool: grep -qF '`Examples/` holds reference ISAs' skill/ISA/SKILL.md
```

## Decisions

- 2026-10-04 refined: reopened after complete — the user asked for a third review; this pass compares every original sentence mechanically (word overlap) before reading the low-overlap ones by hand.
- 2026-10-04 third review: both directions checked (original sentences missing words in the new file; new sentences with words absent from the original — none adds a claim). Two losses found → ISC-9 (test-first had become mandatory for all runnable probes) and ISC-10 ("reference ISAs" dropped). All other flags were rewording only.

- 2026-10-04 refined: reopened after complete — the user asked for a second review for anything useful removed; it found five losses to restore.
- 2026-10-04 refined: ISC-1 threshold 12% → 11.5% — restoring the five lost statements adds ~40 words; keeping meaning outranks the word count.

- 2026-10-04 refined: ISC-1 threshold 15% → 12% — removing every duplicate gave 12.6% (5797 → 5064 words); going further would mean compressing unique facts, which the zero-meaning-loss ask outranks.
- 2026-10-04 ISC-6's probe is the repo's own LifeOS check (AGENTS.md § Working rules); it fails when any of those strings is added under skill/, so it holds despite Jev's doubt.

## Verification

- ISC-2: verified 2026-10-04T18:33:32 — exit 0 in 0.22s — `while IFS= read -r t; do [ -z "$t" ] || grep -qF -- "$t" skill/ISA/SKILL.md || { echo "missing: $t"; exit 1; }; done < .isa/20261004-180722_shorten-skill-md/facts.txt` (ledger: 26bdfcce19)
- ISC-4: verified 2026-10-04T18:33:32 — exit 0 in 0.0s — `! grep -qF 'is not supported' skill/ISA/SKILL.md` (ledger: efa97517c9)
- ISC-5: verified 2026-10-04T18:33:32 — exit 0 in 0.0s — `diff <(git show HEAD:skill/ISA/SKILL.md | head -6) <(head -6 skill/ISA/SKILL.md)` (ledger: 694613a0b0)
- ISC-6: verified 2026-10-04T18:33:32 — exit 0 in 0.01s — `! rg -q -i 'lifeos|31337|MEMORY/WORK|\btelos\b|\bpulse\b' skill/` (ledger: ecb5cb3c6f)
- ISC-7: verified 2026-10-04T18:33:32 — exit 0 in 6.98s — `python3 -m unittest tests.test_install tests.test_gate tests.test_declaration 2>&1 | tail -3 | grep -q '^OK'` (ledger: 72bdc927b4)
- ISC-3: attested 2026-10-04T18:12:02 — Read git HEAD vs new SKILL.md passage by passage: each removed block maps to a kept statement — Lifecycle 'Done exists in writing' → rule 2 + E1 gate; 'Fold discoveries' → rule 14 (now says 'right away' and 'stale'); 'No ISC closes without tool evidence' → rule 8 (now points to the kind: table); 'Continuation vs new task' → gate bullet 2 (examples moved there); close conditions 1-4 → Close bullet + rule 1 (frame-drift) + Close contract; Gotchas ID-stability/Reconcile/ephemeral → merged section; Anti/Antecedent/literal-goal gotchas → rules 3, 4, 1 and taxonomy note; empty-sections gotcha → section-body intro + tier gate; test-first gotcha → 'Prove as you go'; format-spec-wins → References; loop call points → Workflow Routing (isa commands already in the table). Dropped only: the Gotchas preamble (meta), and the stale 'project ISA is not supported' line that contradicted the kind: project paragraph. (ledger: d32ef6ab27)
- ISC-1: verified 2026-10-04T18:33:32 — exit 0 in 0.0s — `test "$(wc -w < skill/ISA/SKILL.md)" -le 5130` (ledger: 2d80e34140)
- ISC-8: verified 2026-10-04T18:33:32 — exit 0 in 0.01s — `f=skill/ISA/SKILL.md; grep -qF 'without a written, testable definition of what finished looks like' $f && grep -qF 'the harness enforces this loop' $f && grep -qF 'run `isa verify --red <ISA>` before building' $f && grep -qF 'are listed to the user' $f && grep -qF 'never left stale' $f` (ledger: e8c180d903)
- ISC-9: verified 2026-10-04T18:33:32 — exit 0 in 0.0s — `grep -qF 'Prefer test-first where a probe is runnable' skill/ISA/SKILL.md` (ledger: 3f61a7a3d2)
- ISC-10: verified 2026-10-04T18:33:32 — exit 0 in 0.0s — `grep -qF '`Examples/` holds reference ISAs' skill/ISA/SKILL.md` (ledger: cb0f84eeff)
- Ask 1: met — reviewed; yes, it shortens by 11.7% (5797 → 5119 words after the second review's restorations) by removing duplication.
- Ask 2: met — every distinctive token of the original is still present (ISC-2, 180 tokens checked).
- Ask 3: met — every rule, table and example row kept; the frontmatter that drives triggering is byte-identical (ISC-5).
- Ask 4: met — each removed passage maps to a kept statement (ISC-3, self-attested).
- Ask 5: met — the final answer lists every removal and merge, and where each fact now lives.
- Ask 6: met — second sentence-by-sentence pass of git HEAD vs the new file found five lost statements: the "written, testable definition" root cause (plus "forgotten"), "the harness enforces this loop", "before building" on the red run, "self-attested ticks … listed to the user" at close, and the "never left stale" lifecycle heading.
- Ask 7: met — all five restored (ISC-8, red then green); the gate heading lost its now-redundant "(when the ISA hooks are installed)".
- Ask 8: met — third review compared both directions mechanically and read every flagged sentence; two more losses fixed (ISC-9, ISC-10); no added claims found.
- Goal: yes — SKILL.md is 11.6% shorter (5797 → 5124 words) with only duplicated wording removed, the one contradiction fixed, the losses found by the second and third reviews restored, and the strip list given to the user.
