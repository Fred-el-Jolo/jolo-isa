---
task: "Move ISA hardening to its own spec, add an issue log"
slug: 20261005-134746_isa-hardening-spec
effort: E2
phase: complete
progress: 8/8
started: 2026-10-05T13:47:46
updated: 2026-10-05T13:50:10
root: .
stated_goal: "enc:v1:0ddf368a:0elUnq2Af4J329CuMDaUuguGpVHOEMjsLm4kfcAIPCE_rCIBDT05co5X9ZP0tojAQXGBXOhVO8PQ7lHloQD5UyE3kFjzgRGAtEf8RP13etHwSmNpRYKpcGY"
stated_goal_source: prompt
asks: ["enc:v1:0ddf368a:0elUnq2Af4J329CuMDaUuguGpVHOEMjsLm4kfcAIPCE_rCIBDT05co5X9ZP0tojAQXGBXOhVO8PQ7lHloQD5UyE3kFjzgRGAtEf8RP13etHwSmNpRYKpcGY", "enc:v1:0ddf368a:SlcNZ6_YKyAby7oPwEFoqGs1M7oY7Xq0u0r9hAcT12paA4HVQB2uNFWlXIEe218F3wA6JA54iJyeLFGK6xN8DCtv1haUksUYHc_w1OEtTAB2Xd9o4r3RR8T7_ZYCdL1hiSfLCaEb-ziP_kaVzVUpPFNxlLilMC8v9czFs7DFf3VV4kHzjlyxIhy69CIcYPSQ3m2S-V_aT7_IJUGsgoaBXy2Qr3fiJj4AKA", "enc:v1:0ddf368a:qHIChT2PL1zMClvc7k3MiRvi2lmmmfUvQ39Mk4NJJzVOoJsh_sMcjFv4KbBVLdCDS35DpGbkklS6-g"]
context_sufficient: true
---

## Problem

The framework-hardening analysis (error classes E1–E9, proposals H1–H6) sits as § 11 of `future/SKILL-SPLIT.md`, which is about the skill split; at 38.9 KB that spec is nearing pi's 50 KB read, and the hardening work is scheduled after the split. There is also no single place listing the framework's own errors (refused ISA edits, YAML/lint failures, shell rewrites of an ISA, probe regressions) for review during the first live-testing phase: the day logs record every hook event, and `errors.log` only hook crashes.

## Goal

"enc:v1:0ddf368a:bisqSrhMMWQKFPTrmSKZCPFMIdOMQ7TyTWH-L7DYug9D4-j1uHXg9Rbnx9jNZmLTnH4XpjGJL9FPNDpsSblpdDFFUnfMh0qCiSymbACAl8VDokjUW51R" — `future/ISA-HARDENING.md` holds the whole former § 11 plus a specified issue log for framework errors during live testing; SKILL-SPLIT.md keeps a one-line pointer; nothing is implemented.

## Criteria

- [x] ISC-1: future/ISA-HARDENING.md exists with Status, Errors, Proposals, Issue log, Order, Acceptance sections.
- [x] ISC-2: Every E1–E9 row and H1–H6 proposal is in the new file.
- [x] ISC-3: SKILL-SPLIT.md keeps no § 11 body, only a pointer to the new file.
- [x] ISC-4: The issue-log section specifies location, event codes, privacy rule, reader command, and switch.
- [x] ISC-5: The new spec says it is scheduled after the SKILL-SPLIT phases.
- [x] ISC-6: Each issue code names the hook or command that detects it, checked against the code.
- [x] ISC-7: AGENTS.md layout lists future/ISA-HARDENING.md.
- [x] ISC-8: Anti: any runtime, adapter, test, installer or skill file changes.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "enc:v1:0ddf368a:0elUnq2Af4J329CuMDaUuguGpVHOEMjsLm4kfcAIPCE_rCIBDT05co5X9ZP0tojAQXGBXOhVO8PQ7lHloQD5UyE3kFjzgRGAtEf8RP13etHwSmNpRYKpcGY"
  type: bash
  kind: doc
  check: required headings present
  threshold: all six
  fails-when: "the file is missing or a heading is absent"
  tool: |-
    f=future/ISA-HARDENING.md; for h in Status Errors Proposals 'Issue log' Order Acceptance; do grep -qE "^## ([0-9]+\. )?$h" $f || { echo "no $h"; exit 1; }; done

- isc: ISC-2
  anchors_to: "enc:v1:0ddf368a:0elUnq2Af4J329CuMDaUuguGpVHOEMjsLm4kfcAIPCE_rCIBDT05co5X9ZP0tojAQXGBXOhVO8PQ7lHloQD5UyE3kFjzgRGAtEf8RP13etHwSmNpRYKpcGY"
  type: bash
  kind: doc
  check: rows and proposals moved
  threshold: E1–E9 table rows and H1–H6 bullets found
  fails-when: "an E row or an H proposal is missing from the new file"
  tool: |-
    f=future/ISA-HARDENING.md; for e in E1 E2 E3 E4 E5 E6 E7 E8 E9; do grep -q "^| $e |" $f || exit 1; done; for h in H1 H2 H3 H4 H5 H6; do grep -q "^- \*\*$h\. " $f || exit 1; done

- isc: ISC-3
  anchors_to: "enc:v1:0ddf368a:0elUnq2Af4J329CuMDaUuguGpVHOEMjsLm4kfcAIPCE_rCIBDT05co5X9ZP0tojAQXGBXOhVO8PQ7lHloQD5UyE3kFjzgRGAtEf8RP13etHwSmNpRYKpcGY"
  type: bash
  kind: doc
  check: old spec has no E rows or H bullets, and names the new file
  threshold: no hits for rows; one pointer hit
  fails-when: "SKILL-SPLIT.md still has '| E1 |' rows or H bullets, or never names ISA-HARDENING.md"
  tool: |-
    f=future/SKILL-SPLIT.md; ! grep -q '^| E[1-9] |' $f && ! grep -q '^- \*\*H[1-6]\. ' $f && grep -qF 'ISA-HARDENING.md' $f

- isc: ISC-4
  anchors_to: "enc:v1:0ddf368a:SlcNZ6_YKyAby7oPwEFoqGs1M7oY7Xq0u0r9hAcT12paA4HVQB2uNFWlXIEe218F3wA6JA54iJyeLFGK6xN8DCtv1haUksUYHc_w1OEtTAB2Xd9o4r3RR8T7_ZYCdL1hiSfLCaEb-ziP_kaVzVUpPFNxlLilMC8v9czFs7DFf3VV4kHzjlyxIhy69CIcYPSQ3m2S-V_aT7_IJUGsgoaBXy2Qr3fiJj4AKA"
  type: bash
  kind: doc
  check: issue-log section has its parts
  threshold: grep hits inside the section
  fails-when: "the section lacks a file path, a code table, a no-text privacy rule, the `isa issues` reader, or the config switch"
  tool: |-
    t=$(sed -n '/^## [0-9]*\.\? *Issue log/,/^## [0-9]*\.\? *Order/p' future/ISA-HARDENING.md); echo "$t" | grep -qF '~/.isa/_state/issues/' && echo "$t" | grep -q '^| `' && echo "$t" | grep -qi 'never copies' && echo "$t" | grep -qF '`isa issues' && echo "$t" | grep -qF '"issue_log"'

- isc: ISC-5
  anchors_to: "enc:v1:0ddf368a:0elUnq2Af4J329CuMDaUuguGpVHOEMjsLm4kfcAIPCE_rCIBDT05co5X9ZP0tojAQXGBXOhVO8PQ7lHloQD5UyE3kFjzgRGAtEf8RP13etHwSmNpRYKpcGY"
  type: bash
  kind: doc
  check: status names the order
  threshold: grep hit
  fails-when: "the status line does not say it comes after the SKILL-SPLIT phases"
  tool: grep -qF 'after the SKILL-SPLIT phases' future/ISA-HARDENING.md

- isc: ISC-6
  anchors_to: "enc:v1:0ddf368a:qHIChT2PL1zMClvc7k3MiRvi2lmmmfUvQ39Mk4NJJzVOoJsh_sMcjFv4KbBVLdCDS35DpGbkklS6-g"
  type: manual
  kind: doc
  check: each issue code's detector exists in runtime/isa (hook handler or command) as named
  threshold: every code row traced to a function or file:line
  tool: grep each named function / line in runtime/isa

- isc: ISC-7
  anchors_to: "enc:v1:0ddf368a:0elUnq2Af4J329CuMDaUuguGpVHOEMjsLm4kfcAIPCE_rCIBDT05co5X9ZP0tojAQXGBXOhVO8PQ7lHloQD5UyE3kFjzgRGAtEf8RP13etHwSmNpRYKpcGY"
  type: bash
  kind: doc
  check: AGENTS.md layout line
  threshold: grep hit
  fails-when: "AGENTS.md does not name ISA-HARDENING.md"
  tool: grep -qF 'ISA-HARDENING.md' AGENTS.md

- isc: ISC-8
  anchors_to: "enc:v1:0ddf368a:0elUnq2Af4J329CuMDaUuguGpVHOEMjsLm4kfcAIPCE_rCIBDT05co5X9ZP0tojAQXGBXOhVO8PQ7lHloQD5UyE3kFjzgRGAtEf8RP13etHwSmNpRYKpcGY"
  type: bash
  kind: file
  check: nothing outside future/, AGENTS.md and .isa changed by this task
  threshold: git diff clean on code paths; SKILL.md still at the earlier task's 5124 words
  fails-when: "git diff lists a runtime/adapter/test/installer/reference/workflow/example file, or SKILL.md's word count moved"
  tool: git diff --quiet HEAD -- runtime adapters tests install.py skill/ISA/References skill/ISA/Workflows skill/ISA/Examples && test "$(wc -w < skill/ISA/SKILL.md)" -eq 5124
```

## Verification

- ISC-1: verified 2026-10-05T13:50:10 — exit 0 in 0.01s — `f=future/ISA-HARDENING.md; for h in Status Errors Proposals 'Issue log' Order Acceptance; do grep -qE "^## ([0-9]+\. )?$h" $f || { echo "no $h"; exit 1; }; done` (ledger: bcc4e61346)
- ISC-2: verified 2026-10-05T13:50:10 — exit 0 in 0.02s — `f=future/ISA-HARDENING.md; for e in E1 E2 E3 E4 E5 E6 E7 E8 E9; do grep -q "^| $e |" $f || exit 1; done; for h in H1 H2 H3 H4 H5 H6; do grep -q "^- \*\*$h\. " $f || exit 1; done` (ledger: 3bb8dabb63)
- ISC-3: verified 2026-10-05T13:50:10 — exit 0 in 0.0s — `f=future/SKILL-SPLIT.md; ! grep -q '^| E[1-9] |' $f && ! grep -q '^- \*\*H[1-6]\. ' $f && grep -qF 'ISA-HARDENING.md' $f` (ledger: e3f6a6d04c)
- ISC-4: verified 2026-10-05T13:50:10 — exit 0 in 0.01s — `t=$(sed -n '/^## [0-9]*\.\? *Issue log/,/^## [0-9]*\.\? *Order/p' future/ISA-HARDENING.md); echo "$t" | grep -qF '~/.isa/_state/issues/' && echo "$t" | grep -q '^| `' && echo "$t" | grep -qi 'never copies' && echo "$t" | grep -qF '`isa issues' && echo "$t" | grep -qF '"issue_log"'` (ledger: 84552db12d)
- ISC-5: verified 2026-10-05T13:50:10 — exit 0 in 0.0s — `grep -qF 'after the SKILL-SPLIT phases' future/ISA-HARDENING.md` (ledger: 907297a458)
- ISC-7: verified 2026-10-05T13:50:10 — exit 0 in 0.0s — `grep -qF 'ISA-HARDENING.md' AGENTS.md` (ledger: d440a920a8)
- ISC-8: verified 2026-10-05T13:50:10 — exit 0 in 0.01s — `git diff --quiet HEAD -- runtime adapters tests install.py skill/ISA/References skill/ISA/Workflows skill/ISA/Examples && test "$(wc -w < skill/ISA/SKILL.md)" -eq 5124` (ledger: d2cfe29edb)
- ISC-6: attested 2026-10-05T13:49:58 — All 15 cited lines printed with sed and match the named code: engine.py:699 _pre_tool, :706 isa-shell-edit branch, :738/:752 gate refusals, :901 _ownership_refusal, :1095 _post_tool, :1174 _tool_failed, :1269 _stop, :1320 record_blocked; lint.py:102/:233 YamlError, :229 'no fenced yaml list'; commands.py:490 regressed line; cli.py:41 main, :297 errors.log. pi: adapters/pi/isa.ts:153 routes isError tool_result to tool_failed; Claude Code PostToolUseFailure is in install.py EVENTS. The reopen row was corrected to stash phase in _pre_tool, since _post_tool alone cannot see the old phase. (ledger: 11d55c0bb4)
- Ask 1: met — future/ISA-HARDENING.md holds the former § 11 (context, E1–E9, H1–H6, order) and says it comes after the SKILL-SPLIT phases; SKILL-SPLIT.md § 11 is now a pointer (ISC-1, 2, 3, 5).
- Ask 2: met — § 4 specifies the issue log: ~/.isa/_state/issues/ day files, 17 codes each with its detector, a no-text privacy rule with a sentinel test, `isa issues` reader, `issue_log` switch on during live testing, 30-day retention, a review loop (ISC-4, ISC-6).
- Ask 3: met — the issue log is § 4 of the new spec and first in its order.
- Goal: yes — the hardening work has its own spec scheduled after the split, with an issue log ready to specify live-testing review; nothing implemented.
