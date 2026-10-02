---
kind: project
task: "ISA skill export: the skill, its engine and hooks, LifeOS-free"
effort: E3
started: 2026-10-03T01:04:37
updated: 2026-10-03T01:25:00
---

## Problem

The living spec of `jolo-isa`: the constraints and standing claims its code must keep satisfying. Task ISAs live in
`.isa/`; a criterion that must hold forever is promoted here (`promote: true`).

## Constraints

- The runtime (`runtime/`) uses the Python standard library only; Jev and `openssl` are reached as CLIs.
- `skill/` carries no LifeOS paths, ports or personal data; provenance lives only in AGENTS.md.
- No hook and no `isa` command calls a model CLI; the gate asks Jev under a hard deadline.
- The user's verbatim words never reach git in plain text; the project ISA never holds them.

## Criteria

- ISC-P1: The full Python unit suite passes.
- ISC-P2: The pi extension tests pass.
- ISC-P3: Every module under `runtime/` imports the standard library only.
- ISC-P4: `skill/` holds no LifeOS reference.
- ISC-P5: Every example ISA lints ok.
- ISC-P6: Every committed task ISA stores the user's words encrypted, and this file stays plain.
- ISC-P7: `install.py --dry-run` runs to the end.

## Test Strategy

```yaml
- isc: ISC-P1
  type: unit-test
  check: the suite AGENTS.md lists
  threshold: exit 0
  tool: python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install tests.test_status tests.test_evidence tests.test_shell_changes tests.test_feature_order tests.test_home_and_complete tests.test_seamless_projects tests.test_gate tests.test_commands tests.test_fingerprint tests.test_blocked tests.test_red tests.test_lint_v2 tests.test_purge tests.test_declaration tests.test_logs tests.test_ask tests.test_jev tests.test_m11 tests.test_m12

- isc: ISC-P2
  type: unit-test
  check: node test runner on the extension
  threshold: exit 0
  tool: node --test adapters/pi/test/extension.test.ts

- isc: ISC-P3
  type: bash
  check: stdlib import check
  threshold: exit 0
  tool: python3 tests/check_stdlib.py runtime/

- isc: ISC-P4
  type: bash
  check: the AGENTS.md grep, zero hits
  threshold: exit 0
  tool: "! rg -n -i 'lifeos|31337|MEMORY/WORK|\\btelos\\b|\\bpulse\\b' skill/"

- isc: ISC-P5
  type: bash
  check: lint_isa on every example
  threshold: all ok
  tool: test "$(python3 tools/lint_isa.py skill/ISA/Examples/*.md | grep -c '.md. ok$')" = "$(ls skill/ISA/Examples/*.md | wc -l)"

- isc: ISC-P6
  type: bash
  check: committed blobs read back at HEAD
  threshold: exit 0
  tool: python3 tools/check_committed_isas.py HEAD

- isc: ISC-P7
  type: bash
  check: the installer's dry run
  threshold: exit 0
  tool: python3 install.py --dry-run >/dev/null
```

## Decisions

- 2026-10-03 01:25: the standing claims are AGENTS.md's "Working rules for this folder", each with the probe it already names, plus the encryption check of § 13. The rule "fix skill prose and IsaFormat together" has no mechanical probe and stays in AGENTS.md.
