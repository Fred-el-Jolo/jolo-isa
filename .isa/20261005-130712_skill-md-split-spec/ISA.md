---
task: "Spec the SKILL.md split under the skill token budget"
slug: 20261005-130712_skill-md-split-spec
effort: E2
phase: complete
progress: 21/21
started: 2026-10-05T13:07:12
updated: 2026-10-05T13:40:45
root: .
stated_goal: "enc:v1:0ddf368a:3hfJE2MplxP5cUeV28MytPSht2WcD1YdURh_GIvmNUbiFt_T8pQydaYcJjBsSZZExYjM71-lVA34gd6dZTGO5FxPSFAOOJFZVNns"
stated_goal_source: prompt
asks: ["enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4", "enc:v1:0ddf368a:FQBhERaWywG7OjEWdixrBYOFuGq4ERSrrRcVqgTi418JLrOlJUiIkQyoFYoLog", "enc:v1:0ddf368a:M6-vN2wH05u5GiYz9GF8QEtn-uI4MeRUuSXxj7XK_C0lQjw6S8oo7Gzs37B3R454scdbEWvfhbLTWx-F8YKUi9XNY87GYElnmBu2t6-6OA", "enc:v1:0ddf368a:CND1rneKW6UsOYX95rUSvh8Mn8US0Qx32qNKrBp628njEcq8y7bGH0i4ni7QjbsxIK37FqZk4KwHhdNPPefghk9y", "enc:v1:0ddf368a:D32eUwNW7gdxTtKO1-FYjjhvw1D6Im1s9AMJLT6yb4AgfhZCmep_pHhDzMa3hUSgoGoKIBL5IRJwrMFT", "enc:v1:0ddf368a:aAMR-Fa5aj7572hGwKzHa0-jen72Xa6D_pzhdLc54joILv8FUlp-Og-sG3IAN83kvQk4R62f9w", "enc:v1:0ddf368a:mQMcLuRlhTmwLEFAhrvea-wA9_Ibq1V9AW4LItU2a2kcoDDyi8N6rg6j", "enc:v1:0ddf368a:hiND80FzD3W3Pv8g11X40tcI2iDPJ2taX17okgbN037Zd-sQWYBZIvRry4rfDUDXnfPYRLvADgPM7zP4fYEiCHgOuSjQs0Zb", "enc:v1:0ddf368a:yTOTc_xkRv9s7ilk34MTGyZItbtHt-rcwcJAgGvmYUt4A4eZBMMQ1L9Q0VB8mIiA9yNrCsa--QrAVB4zkobP", "enc:v1:0ddf368a:nfVQh3mANPmwKT-7oi3HfvK1kYfDXM3MXpGMVer7_vUE9Bv0C5l0JuozNsvDLtranQw9zCtSL99BVic7chYl2GQ2OCO-wvxPYuUbiIHCFL1IFms8WdLCuXqLunpw7-ntog", "enc:v1:0ddf368a:am1r4d4qqWRZSW3aaWCxVYxMXiuw7oC2ySorSIAUhBYEo30egbBdVwrXcoKq6fzzk0DQg6xYXre8FWWGrwNIhjklNHlfI8GVk34S9Zdk", "enc:v1:0ddf368a:4-ioDJmX-BqqJBFBGESaBsigVCGyZDY02KPasC4wND8I4XRHZd_b_rQ7biDrUJwNoE2W3eyZli-9hIbrobxaybwE1Us3_tXZDBoIY9PC", "enc:v1:0ddf368a:RbZYe19uHMxwd8jj4Otv4Wi6kPECQWWHmIYFiIjg42AR5LoCWeRunflcVmJLWZ-PYxk7DWWdpN5NvwFIiOH6w9I3hGVeapyk3U1XoLbqdZB9pXSWazeFEyF6MvLHw_u69P0Fp1TVqGo5pNkn7EdxTMFmIwFQnUqpbg3s9FQ", "enc:v1:0ddf368a:Z7HMNcAgOcz7c9RwaGyN1KiHGXCPno8wM4JDVIj1GubR0P3OwrOmjeCQenzgGC2DafeiQcxZ0qTMvqwh3PMt", "enc:v1:0ddf368a:zvTk_h1kIy4UlJfC_UDyhE3i6-FffDxBtentu97MozUIxBLys-eHek5y0knk0gZAhvNY0DiTPd3EbjyAkRoZD8Wri8wKiJzLg1aIWdpTBLKzmZcr5bEQxMLnraPdcVYdvmyADd1T4kKV3DVQCCeBtgHh", "enc:v1:0ddf368a:6-5CvNmZJFRcpbxOigeIG5SnOdIfGWKr7NF9W64IR5TjIT5M2WvW7iFAt9rRr-n0sjYDJiDoA3T3mqsh0FkBqZ7u9ypP8z28uI6WQqDYGHZQxLquW89HjnQQYw", "enc:v1:0ddf368a:JM8BB0CKxt1iipPn5yckxAsx0gh1s8cWpn1lmXZ1zy544w-pQlk6Udw5VTKHjEvLkHz10uLDww5rw_RpeID9i5nH"]
context_sufficient: true
iteration: 5
resumed_at: 2026-10-05T15:00:00
---

## Problem

`skill/ISA/SKILL.md` is ~8k tokens (5124 words, 32 KB) against the ~5k-token body budget of the skill authoring guidance, and the ON block makes every ON session read it in full. The previous answer sketched a split (keep the rules, move reference material one level deep) but only as chat text; nothing records the plan, its inventory, its dependencies or how to prove it lost nothing.

## Goal

"enc:v1:0ddf368a:L49taIpxpQcZyI_oyWsvQRpWNe_NJBMV_shEqa9Nna7ZZMAQdWojyC0kbCWB3snqODe0cYmZ2bvnEaKJyK4juowHpRq7TIa--Q" — `future/SKILL-SPLIT.md` specifies the split: budget, per-section keep/move table with destinations, the dependencies that read SKILL.md, the acceptance checks (token budget, fact preservation, tests), and open questions — while no skill, runtime, adapter, test or installer file changes.

## Criteria

- [x] ISC-1: future/SKILL-SPLIT.md exists with Goal, Budget, Inventory, Moves, Dependencies, Acceptance, Decisions-and-open-questions sections.
- [x] ISC-2: Every current SKILL.md `##` heading is assigned in the spec's Moves table.
- [x] ISC-3: The spec's Dependencies section names engine.py and the tests that read SKILL.md.
- [x] ISC-4: The spec's Acceptance section requires the fact-token check and a numeric token budget.
- [x] ISC-5: The spec's sizes match measurements taken from the current files.
- [x] ISC-6: Anti: any skill, runtime, adapter, test or installer file changes.
- [x] ISC-7: AGENTS.md layout lists future/SKILL-SPLIT.md beside the other future notes.
- [x] ISC-8: The spec states how pi reaches the skill and pi's read limits.
- [x] ISC-9: The spec's acceptance has a pi session check and a per-file size check.
- [x] ISC-10: The spec makes the moved call points usable without Claude Code's Skill tool.
- [x] ISC-11: The spec turns the Q3 rename and Q6 pi install into ordered rollout phases.
- [x] ISC-12: The spec describes pi's skill support from pi's code: location, relative paths, settings.
- [x] ISC-13: Q7 states pi's bash has an optional per-call timeout in seconds.
- [x] ISC-14: Q8 proposes canonical-isa.md as the E5 reference, nothing trimmed.
- [x] ISC-15: Anti: an item is recorded as decided without the user's decision.
- [x] ISC-16: Q7 sets the same 10-minute timeout in both harnesses' units.
- [x] ISC-17: The spec plans e5-enterprise.md below 50 KB with measured cuts.
- [x] ISC-18: Anti: e5-enterprise.md is modified at this spec stage.
- [x] ISC-19: Section 11 classifies each seen error and proposes fixes with size effects.
- [x] ISC-20: Section 11 states measured ISA sizes and the Verification share.
- [x] ISC-21: Section 11's error table and code citations match this session's facts.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4"
  type: bash
  kind: doc
  check: each required heading is present
  threshold: all seven grep hits
  fails-when: "the file is missing or one of the seven headings is absent"
  tool: |-
    f=future/SKILL-SPLIT.md; for h in Goal Budget Inventory Moves Dependencies Acceptance 'Decisions and open questions'; do grep -qE "^## ([0-9]+\. )?$h" $f || { echo "no $h"; exit 1; }; done

- isc: ISC-2
  anchors_to: "enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4"
  type: bash
  kind: doc
  check: every `## ` heading of SKILL.md appears in the spec
  threshold: exit 0
  fails-when: "a SKILL.md heading such as `Three-Guardrail Taxonomy` has no row in the spec"
  tool: |-
    grep '^## ' skill/ISA/SKILL.md | sed 's/^## //' | while IFS= read -r h; do grep -qF -- "$h" future/SKILL-SPLIT.md || { echo "unassigned: $h"; exit 1; }; done

- isc: ISC-3
  anchors_to: "enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4"
  type: bash
  kind: doc
  check: dependencies named
  threshold: grep hits for engine.py, test_gate and test_declaration
  fails-when: "the spec omits the engine's ON-block text or a test that asserts on SKILL.md"
  tool: f=future/SKILL-SPLIT.md; grep -qF engine.py $f && grep -qF test_gate $f && grep -qF test_declaration $f

- isc: ISC-4
  anchors_to: "enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4"
  type: bash
  kind: doc
  check: acceptance names facts.txt-style check and a token number
  threshold: both grep hits
  fails-when: "no fact-preservation check or no numeric budget in Acceptance"
  tool: f=future/SKILL-SPLIT.md; grep -qi 'fact' $f && grep -qE '[0-9][0-9,]* tokens' $f

- isc: ISC-5
  anchors_to: "enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4"
  type: manual
  kind: doc
  check: compare the spec's per-section word counts to a fresh wc of each section
  threshold: every figure within 5%
  tool: awk section split of skill/ISA/SKILL.md + wc -w, read against the Inventory table

- isc: ISC-6
  anchors_to: "enc:v1:0ddf368a:FQBhERaWywG7OjEWdixrBYOFuGq4ERSrrRcVqgTi418JLrOlJUiIkQyoFYoLog"
  type: bash
  kind: file
  check: nothing under skill/, runtime/, adapters/, tests/ or install.py changed beyond the previous task's SKILL.md edit
  threshold: git diff clean on those paths; SKILL.md still 5124 words
  fails-when: "git diff lists a file under those paths, or SKILL.md's word count moved from 5124"
  tool: git diff --quiet HEAD -- runtime adapters tests install.py skill/ISA/References skill/ISA/Workflows skill/ISA/Examples && test "$(wc -w < skill/ISA/SKILL.md)" -eq 5124

- isc: ISC-7
  type: bash
  anchors_to: "enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4"
  kind: doc
  check: AGENTS.md mentions the new note
  threshold: grep hit
  fails-when: "AGENTS.md has no line naming SKILL-SPLIT.md"
  tool: grep -qF 'SKILL-SPLIT.md' AGENTS.md

- isc: ISC-8
  anchors_to: "enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4"
  type: bash
  kind: doc
  check: pi facts present
  threshold: "grep hits for 'pi never discovers', ~/.agents/skills, 50 KB and /skill:"
  fails-when: "the spec does not say pi never discovers the skill, or omits pi's 2000-line / 50 KB read limit"
  tool: f=future/SKILL-SPLIT.md; grep -qF '~/.agents/skills' $f && grep -qF '50 KB' $f && grep -qF '/skill:' $f && grep -qi 'pi never discovers' $f

- isc: ISC-9
  anchors_to: "enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4"
  type: bash
  kind: doc
  check: acceptance names a pi session and a per-file size limit
  threshold: grep hits
  fails-when: "the acceptance list still has only a Claude Code session check, or no per-file size check"
  tool: f=future/SKILL-SPLIT.md; sed -n '/^## 6\./,/^## 7\./p' $f | grep -qi 'pi session' && sed -n '/^## 6\./,/^## 7\./p' $f | grep -qF '51,200'

- isc: ISC-10
  anchors_to: "enc:v1:0ddf368a:bvp18soepTCSZJpTH4WBs-z9UBmkRMw-IPjWAEJzcbArgw_QY5wDQ58Hu3eCDdQxJCIA6yRCWxeqrMYXev4"
  type: bash
  kind: doc
  check: the spec requires a harness-neutral form for the Skill() call points
  threshold: grep hit
  fails-when: "the call points move verbatim with only Skill(\"ISA\", …), which pi has no tool for"
  tool: grep -qF 'read `Workflows/<Name>.md` and follow it' future/SKILL-SPLIT.md

- isc: ISC-11
  anchors_to: "enc:v1:0ddf368a:CND1rneKW6UsOYX95rUSvh8Mn8US0Qx32qNKrBp628njEcq8y7bGH0i4ni7QjbsxIK37FqZk4KwHhdNPPefghk9y"
  type: bash
  kind: doc
  check: rollout has the three phases in order, rename before pi install before split
  threshold: line numbers increasing
  fails-when: "a phase heading is missing or the phases are out of order"
  tool: |-
    f=future/SKILL-SPLIT.md; a=$(grep -n '^\*\*Phase 1: rename' $f | cut -d: -f1); b=$(grep -n '^\*\*Phase 2: install the skill for pi' $f | cut -d: -f1); c=$(grep -n '^\*\*Phase 3: the split' $f | cut -d: -f1); [ -n "$a" ] && [ -n "$b" ] && [ -n "$c" ] && [ "$a" -lt "$b" ] && [ "$b" -lt "$c" ]

- isc: ISC-12
  anchors_to: "enc:v1:0ddf368a:M6-vN2wH05u5GiYz9GF8QEtn-uI4MeRUuSXxj7XK_C0lQjw6S8oo7Gzs37B3R454scdbEWvfhbLTWx-F8YKUi9XNY87GYElnmBu2t6-6OA"
  type: bash
  kind: doc
  check: pi skill facts cite formatSkillsForPrompt, the relative-path instruction and the settings skills array
  threshold: grep hits
  fails-when: "the spec still claims pi never announces a skill's folder, or omits the settings skills array"
  tool: f=future/SKILL-SPLIT.md; grep -qF 'formatSkillsForPrompt' $f && grep -qF 'resolve it against the skill directory' $f && grep -qF 'skills` array' $f && ! grep -qF 'Neither harness tells the model where this skill lives' $f

- isc: ISC-13
  anchors_to: "enc:v1:0ddf368a:CND1rneKW6UsOYX95rUSvh8Mn8US0Qx32qNKrBp628njEcq8y7bGH0i4ni7QjbsxIK37FqZk4KwHhdNPPefghk9y"
  type: bash
  kind: doc
  check: Q7 text
  threshold: grep hits, old wrong claim gone
  fails-when: "Q7 still says the timeout line means nothing in pi"
  tool: f=future/SKILL-SPLIT.md; grep -qF 'optional per-call `timeout` in seconds' $f && ! grep -qF 'so the line means nothing there' $f

- isc: ISC-14
  anchors_to: "enc:v1:0ddf368a:CND1rneKW6UsOYX95rUSvh8Mn8US0Qx32qNKrBp628njEcq8y7bGH0i4ni7QjbsxIK37FqZk4KwHhdNPPefghk9y"
  type: bash
  kind: doc
  check: Q8 proposal
  threshold: grep hit
  fails-when: "Q8 has no proposal naming canonical-isa.md as the E5 reference"
  tool: grep -qF '`Examples/canonical-isa.md` becomes the E5 reference' future/SKILL-SPLIT.md

- isc: ISC-15
  anchors_to: "enc:v1:0ddf368a:CND1rneKW6UsOYX95rUSvh8Mn8US0Qx32qNKrBp628njEcq8y7bGH0i4ni7QjbsxIK37FqZk4KwHhdNPPefghk9y"
  type: bash
  kind: doc
  check: decided items name the user's decision; the § 11 hardening is labelled as proposals, not decisions
  threshold: grep hits
  fails-when: "Q7 lacks '(decided … the user's call)', the e5 shortening is not marked 'approved as a plan', or § 11 has no 'Proposals' heading"
  tool: |-
    f=future/SKILL-SPLIT.md; grep -qF "(decided 2026-10-05, the user's call)" $f && grep -qF 'approved as a plan (2026-10-05)' $f && sed -n '/^## 11\./,$p' $f | grep -qF '**Proposals, most value first.'

- isc: ISC-16
  anchors_to: "enc:v1:0ddf368a:am1r4d4qqWRZSW3aaWCxVYxMXiuw7oC2ySorSIAUhBYEo30egbBdVwrXcoKq6fzzk0DQg6xYXre8FWWGrwNIhjklNHlfI8GVk34S9Zdk"
  type: bash
  kind: doc
  check: Q7 gives the same 10 minutes in each harness's unit
  threshold: grep hits for both forms
  fails-when: "Q7 still tells pi to omit the timeout, or misses the 600-second form"
  tool: |-
    f=future/SKILL-SPLIT.md; grep -qF 'pi `timeout: 600` (seconds)' $f && grep -qF 'Claude Code `timeout: 600000` (ms)' $f && ! grep -qF 'pi omit `timeout`' $f

- isc: ISC-17
  anchors_to: "could we shorten the file to 50 k ?"
  type: bash
  kind: doc
  check: § 10 exists with target, a steps table, a fallback and checks including the byte limit
  threshold: structural grep hits inside § 10
  fails-when: "§ 10 is missing, or lacks the Target, the Fallback, the ledger-ref step, or a wc -c check at 50000"
  tool: |-
    f=future/SKILL-SPLIT.md; t=$(sed -n '/^## 10\./,/^## 11\./p' $f); echo "$t" | grep -qF '**Target.**' && echo "$t" | grep -qF '**Fallback' && echo "$t" | grep -qF '(ledger: <10-hex>)' && echo "$t" | grep -qF -- '-le 50000'

- isc: ISC-19
  anchors_to: "enc:v1:0ddf368a:zvTk_h1kIy4UlJfC_UDyhE3i6-FffDxBtentu97MozUIxBLys-eHek5y0knk0gZAhvNY0DiTPd3EbjyAkRoZD8Wri8wKiJzLg1aIWdpTBLKzmZcr5bEQxMLnraPdcVYdvmyADd1T4kKV3DVQCCeBtgHh"
  type: bash
  kind: doc
  check: § 11 classifies each error (normal vs framework) and gives proposals with a size effect
  threshold: E1–E9 rows, H1–H6 proposals, a Size line per proposal
  fails-when: "an error class row or a proposal is missing, or a proposal says nothing about ISA size"
  tool: |-
    f=future/SKILL-SPLIT.md; t=$(sed -n '/^## 11\./,$p' $f); for e in E1 E2 E3 E4 E5 E6 E7 E8 E9; do echo "$t" | grep -q "^| $e |" || exit 1; done; for h in H1 H2 H3 H4 H5 H6; do echo "$t" | grep -q "^- \*\*$h\. " || exit 1; done; [ "$(echo "$t" | grep -c 'Size')" -ge 6 ]

- isc: ISC-20
  anchors_to: "enc:v1:0ddf368a:6-5CvNmZJFRcpbxOigeIG5SnOdIfGWKr7NF9W64IR5TjIT5M2WvW7iFAt9rRr-n0sjYDJiDoA3T3mqsh0FkBqZ7u9ypP8z28uI6WQqDYGHZQxLquW89HjnQQYw"
  type: bash
  kind: doc
  check: § 11 states measured ISA sizes and the Verification share
  threshold: grep hits for the measured sizes
  fails-when: "§ 11 gives no measured ISA size or no Verification-vs-Test-Strategy figure"
  tool: |-
    t=$(sed -n '/^## 11\./,$p' future/SKILL-SPLIT.md); echo "$t" | grep -qF '5.6–21.2 KB' && echo "$t" | grep -qF '6,527 vs 7,629 bytes'

- isc: ISC-21
  anchors_to: "enc:v1:0ddf368a:6-5CvNmZJFRcpbxOigeIG5SnOdIfGWKr7NF9W64IR5TjIT5M2WvW7iFAt9rRr-n0sjYDJiDoA3T3mqsh0FkBqZ7u9ypP8z28uI6WQqDYGHZQxLquW89HjnQQYw"
  type: manual
  kind: doc
  check: the error table matches what happened in this session (counts and causes), and the code citations exist
  threshold: each E-row traceable to a tool result in the transcript; each cited file:line shows the named code
  tool: read the transcript's refused edits / lint errors / regressions against the table; grep the cited lines

- isc: ISC-18
  anchors_to: "could we shorten the file to 50 k ?"
  type: bash
  kind: file
  check: e5-enterprise.md untouched (spec stage)
  threshold: git diff clean
  fails-when: "git diff shows e5-enterprise.md changed"
  tool: git diff --quiet HEAD -- skill/ISA/Examples/e5-enterprise.md
```

## Decisions

- 2026-10-05 refined: reopened after complete — the user approved Q7, asked for the e5-enterprise shortening as a plan, and asked whether this session's ISA update errors are normal or the framework can prevent them (ISA file size in mind), as a dedicated section of the plan.

- 2026-10-05 refined: ISC-14 probe — Q8's canonical-as-E5-reference line changed from proposal wording ("Make … the E5 reference") to approved wording ("… becomes the E5 reference"); same claim.
- 2026-10-05 refined: ISC-15 and ISC-17 probes — the e5 shortening moved from a Q8 proposal into its own § 10 (approved as a plan), and its target became ≤ 50,000 bytes because the measured step estimates land at 49.3–49.8 KB, above the first-drafted 49,000. Both probes now check structure inside § 10/§ 11 rather than exact sentences, which is the § 11 E6 lesson applied.
- 2026-10-05 refined: ISC-15 — Q7 and Q8 moved from Proposed to Decided by the user, so "they sit under Proposed" no longer holds; the claim now is that each decided item names the user's decision and the unapproved e5 shortening is labelled a proposal.
- 2026-10-05 refined: reopened after complete — user (Enable ISA) suggested the same timeout as Claude Code for Q7, approved Q8, and asked whether e5-enterprise.md can be shortened to 50 KB.

- 2026-10-05 refined: ISC-1 heading list — § 8 became "Decisions and open questions" once Q3/Q6 were decided; the probe checks the new heading (same strength: seven exact headings).
- 2026-10-05 Corrections from the user, both right: (1) pi has full skill support — read from its code this time (skills.js formatSkillsForPrompt lists <location> and tells the model to resolve relative paths; settings.json `skills` array; /skill:name expansion in agent-session.js), so the spec's "neither harness announces the folder" was wrong and is gone. (2) pi's bash has an optional per-call timeout in seconds; my "means nothing in pi" was wrong. Q7 and Q8 recorded as proposals, not decisions — the user asked for a proposal on Q8 and questioned Q7, deciding neither.
- 2026-10-05 Phase 2 installs via pi's settings `skills` array (one copy) instead of ~/.agents/skills (second copy, picked up by other hosts) — the user already registers skills that way.
- 2026-10-05 refined: reopened after complete — user decided Q3 (rename to isa) and Q6 (install for pi), challenged Q7 (pi timeouts) and the pi skill-support finding, and asked for a Q8 proposal.

- 2026-10-05 refined: reopened after complete — the user asked to review the spec with pi in mind and fix it.
- 2026-10-05 pi review, sources: pi 1.0.0 `docs/skills.md`, `dist/core/tools/truncate.js` (2000 lines / 50 KB per read), `dist/core/tools/bash.js` (timeout in seconds, no default), agentskills.io/specification; `install.py:252` copies the skill only to ~/.claude/skills. Findings folded into the spec: pi never discovers the skill (reads it only via the ON-block path); Skill() call points don't exist in pi; per-file read limit; ms-vs-seconds timeout; frontmatter fields outside the Agent Skills spec; the ephemeral header in Scaffold.md:220; e5-enterprise.md at 59 KB.
- 2026-10-05 Acceptance check 7 was first drafted over every file containing Skill("ISA"; that would have failed on the five workflows the split never touches. Scoped to SKILL.md + IsaLoop.md; the workflows' Invocation lines are noted as harmless in § 5.1.
- 2026-10-05 Acceptance check 6 dry-run failed on Examples/e5-enterprise.md (59,164 bytes). Scoped to the files the split creates or grows; the example became Q8.

- 2026-10-05 Best-practice figures re-read from platform.claude.com (overview: Level 2 "Under 5k tokens"; best practices: < 500 lines, name lowercase, TOC over 100 lines) instead of quoted from memory.
- 2026-10-05 Target A set to 23,500 chars, not the 22,000 first drafted: the per-row savings sum to ~9,200, not ~10,000, and the body (without frontmatter) is 31,925 chars, so moves alone reach ~22.7k. The 5k-token figure became Target B, gated on the user's Q1/Q2 decisions.
- 2026-10-05 ISC-5's attest says the description is 446 chars; a re-measure gives 430 (quotes and key excluded). The spec carries 430.

## Verification

- ISC-1: verified 2026-10-05T13:40:45 — exit 0 in 0.01s — `f=future/SKILL-SPLIT.md; for h in Goal Budget Inventory Moves Dependencies Acceptance 'Decisions and open questions'; do grep -qE "^## ([0-9]+\. )?$h" $f || { echo "no $h"; exit 1; }; done` (ledger: 162b8d526b)
- ISC-2: verified 2026-10-05T13:40:45 — exit 0 in 0.02s — `grep '^## ' skill/ISA/SKILL.md | sed 's/^## //' | while IFS= read -r h; do grep -qF -- "$h" future/SKILL-SPLIT.md || { echo "unassigned: $h"; exit 1; }; done` (ledger: 2bc2e8e8f9)
- ISC-3: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `f=future/SKILL-SPLIT.md; grep -qF engine.py $f && grep -qF test_gate $f && grep -qF test_declaration $f` (ledger: 7762ec06fa)
- ISC-4: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `f=future/SKILL-SPLIT.md; grep -qi 'fact' $f && grep -qE '[0-9][0-9,]* tokens' $f` (ledger: b416cad0e2)
- ISC-6: verified 2026-10-05T13:40:45 — exit 0 in 0.01s — `git diff --quiet HEAD -- runtime adapters tests install.py skill/ISA/References skill/ISA/Workflows skill/ISA/Examples && test "$(wc -w < skill/ISA/SKILL.md)" -eq 5124` (ledger: fff74beff0)
- ISC-7: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `grep -qF 'SKILL-SPLIT.md' AGENTS.md` (ledger: 750202feb3)
- ISC-5: attested 2026-10-05T13:10:53 — Inventory rows copied from the awk per-section split + wc of the working tree (e.g. Completion rules 840 words / 4,868 chars, Examples 357 / 2,417); sections sum to 4,955 words + 169 in frontmatter/title = 5,124 = wc -w; body 31,925 chars = awk frontmatter-stripped wc -c; file 32,430 = wc -c; description 446 chars = line 4 minus quotes and key. Savings column re-added by shell: 9,200 → body ~22,700. (ledger: 0c9e5b94ce)
- ISC-8: verified 2026-10-05T13:40:45 — exit 0 in 0.01s — `f=future/SKILL-SPLIT.md; grep -qF '~/.agents/skills' $f && grep -qF '50 KB' $f && grep -qF '/skill:' $f && grep -qi 'pi never discovers' $f` (ledger: e85927b891)
- ISC-9: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `f=future/SKILL-SPLIT.md; sed -n '/^## 6\./,/^## 7\./p' $f | grep -qi 'pi session' && sed -n '/^## 6\./,/^## 7\./p' $f | grep -qF '51,200'` (ledger: 18c28eaf3b)
- ISC-10: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `grep -qF 'read `Workflows/<Name>.md` and follow it' future/SKILL-SPLIT.md` (ledger: c3710f12eb)
- ISC-11: verified 2026-10-05T13:40:45 — exit 0 in 0.01s — `f=future/SKILL-SPLIT.md; a=$(grep -n '^\*\*Phase 1: rename' $f | cut -d: -f1); b=$(grep -n '^\*\*Phase 2: install the skill for pi' $f | cut -d: -f1); c=$(grep -n '^\*\*Phase 3: the split' $f | cut -d: -f1); [ -n "$a" ] && [ -n "$b" ] && [ -n "$c" ] && [ "$a" -lt "$b" ] && [ "$b" -lt "$c" ]` (ledger: 95c57b35d7)
- ISC-12: verified 2026-10-05T13:40:45 — exit 0 in 0.01s — `f=future/SKILL-SPLIT.md; grep -qF 'formatSkillsForPrompt' $f && grep -qF 'resolve it against the skill directory' $f && grep -qF 'skills` array' $f && ! grep -qF 'Neither harness tells the model where this skill lives' $f` (ledger: 0733eb58b1)
- ISC-13: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `f=future/SKILL-SPLIT.md; grep -qF 'optional per-call `timeout` in seconds' $f && ! grep -qF 'so the line means nothing there' $f` (ledger: 50774b411c)
- ISC-14: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `grep -qF '`Examples/canonical-isa.md` becomes the E5 reference' future/SKILL-SPLIT.md` (ledger: e3ab85ea8e)
- ISC-15: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `f=future/SKILL-SPLIT.md; grep -qF "(decided 2026-10-05, the user's call)" $f && grep -qF 'approved as a plan (2026-10-05)' $f && sed -n '/^## 11\./,$p' $f | grep -qF '**Proposals, most value first.'` (ledger: efe1435225)
- ISC-16: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `f=future/SKILL-SPLIT.md; grep -qF 'pi `timeout: 600` (seconds)' $f && grep -qF 'Claude Code `timeout: 600000` (ms)' $f && ! grep -qF 'pi omit `timeout`' $f` (ledger: 17bfbe2489)
- ISC-17: verified 2026-10-05T13:40:45 — exit 0 in 0.01s — `f=future/SKILL-SPLIT.md; t=$(sed -n '/^## 10\./,/^## 11\./p' $f); echo "$t" | grep -qF '**Target.**' && echo "$t" | grep -qF '**Fallback' && echo "$t" | grep -qF '(ledger: <10-hex>)' && echo "$t" | grep -qF -- '-le 50000'` (ledger: 366d854de3)
- ISC-18: verified 2026-10-05T13:40:45 — exit 0 in 0.0s — `git diff --quiet HEAD -- skill/ISA/Examples/e5-enterprise.md` (ledger: be2318a3ee)
- ISC-19: verified 2026-10-05T13:40:45 — exit 0 in 0.02s — `f=future/SKILL-SPLIT.md; t=$(sed -n '/^## 11\./,$p' $f); for e in E1 E2 E3 E4 E5 E6 E7 E8 E9; do echo "$t" | grep -q "^| $e |" || exit 1; done; for h in H1 H2 H3 H4 H5 H6; do echo "$t" | grep -q "^- \*\*$h\. " || exit 1; done; [ "$(echo "$t" | grep -c 'Size')" -ge 6 ]` (ledger: 16d902b8ac)
- ISC-20: verified 2026-10-05T13:40:45 — exit 0 in 0.01s — `t=$(sed -n '/^## 11\./,$p' future/SKILL-SPLIT.md); echo "$t" | grep -qF '5.6–21.2 KB' && echo "$t" | grep -qF '6,527 vs 7,629 bytes'` (ledger: 37a1cbcfc3)
- ISC-21: attested 2026-10-05T13:40:36 — E-table checked against this session's tool results: E1 'Found 2 matches' x1, E2 'String not found' x1, E3 x3 (spec iter 2 ISC-8..10, iter 3 ISC-11..15, iter 5 ISC-19..21), E4 YAML x3 (/skill:, timeout: 600, ledger: <..>), E5 missing fence x1 (dedup ISA), E6 regressions ISC-1/ISC-14 + rewrites ISC-15/17, E7 6 reopens (dedup 2, spec 4) after correcting 5→6, E8 python heredoc ISA rewrites x2. Citations confirmed by sed/grep: commands.py:504 `{tool}` in the verified line, yamlish.py:76 the mapping error, commands.py:959 OLD_REF, classify.py:204 _drop_heredoc_bodies; ledger stores tool_sha (evidence.py:58). (ledger: f03d3f5533)
- Ask 1: met — future/SKILL-SPLIT.md: goal, budget (from the re-read Anthropic docs), measured inventory, per-section moves with destinations, dependencies, 11 acceptance checks, rollout, 5 open questions, out of scope.
- Ask 2: met — nothing under skill/, runtime/, adapters/, tests/ or install.py changed (ISC-6); only the spec and one AGENTS.md layout line were written.
- Ask 3: met — spec § 5.1 (Claude Code vs pi table), pi rows in § 2 Budget, pi session check 14, Q6–Q8; facts read from pi 1.0.0's own docs and code.
- Ask 4: met — all findings written into the spec (ISC-8, ISC-9, ISC-10); two acceptance checks fixed after dry runs.
- Ask 5: met — the final answer is a short summary.
- Ask 6: met — Q3 recorded as decided; Phase 1 (rename to isa + frontmatter conformance, 69 refs in 28 files, install migration) specified (ISC-11).
- Ask 7: met — Q6 recorded as decided; Phase 2 installs through pi's settings `skills` array and teaches skills.py to read it (ISC-11).
- Ask 8: met — confirmed from pi's bash.js: optional per-call timeout in seconds, no default; the wrong claim removed; Q7 now a two-harness wording proposal (ISC-13).
- Ask 9: met — Q8 proposal: canonical-isa.md (E5, 33 KB, already read) becomes the E5 reference; e5-enterprise.md stays as an optional domain example with a two-reads note; nothing trimmed (ISC-14).
- Ask 10: met — read pi's skills.js / system-prompt.js / agent-session.js / settings; the spec now describes pi's location listing, relative-path instruction, settings array and /skill: expansion (ISC-12).
- Ask 11: met — no reason against it; Q7 now sets 10 minutes in both (Claude Code 600000 ms, pi 600 s), decided (ISC-16).
- Ask 12: met — Q8 approved part recorded; shortening e5-enterprise.md to ≤ 50 KB planned with measured cuts (~8.4 KB → ~50.8 KB), a fallback and acceptance, not implemented (ISC-17, ISC-18).
- Ask 13: met — the final answer lists the causes of the previous turn's ISA errors, causes only.
- Ask 14: met — spec § 10: target ≤ 50,000 bytes, five measured steps (~9.4–9.9 KB), fallback needing the user's OK, six checks (ISC-17).
- Ask 15: met — spec § 11: nine error classes, each marked normal or framework, six proposals H1–H6 with order and tests (ISC-19).
- Ask 16: met — sizes measured on all six repo ISAs; every proposal states its size effect; H1 cuts ~24% of an ISA, H6 adds a 40 KB lint warning (ISC-20).
- Ask 17: met — both are dedicated sections (§ 10, § 11) of future/SKILL-SPLIT.md and listed in its Contents.
- Goal: yes — the split is specified for both harnesses with measurable acceptance and no implementation done; the 5k-token target is honestly marked as needing the user's Q1/Q2 decisions.
