---
task: "Findings: superpowers spec/plan skills vs ISA process"
slug: 20261006-102222_superpowers-spec-plan-findings
effort: E1
phase: complete
progress: 5/5
started: 2026-10-06T10:22:22
updated: 2026-10-06T10:24:20
root: .
stated_goal: "enc:v1:0ddf368a:834sH48mH2jCxLZ-BtoIve_OHZYpyx_5jVs9c4w68Wabq3OCM7wHEXRS8aAE75TVzNGHMgEd67oMLVMVNOLVuDC9_0bsB9RidZadIa8aerF_7Z_n0t3XvrtyEQ"
stated_goal_source: prompt
asks: ["enc:v1:0ddf368a:tWSU5_37XFoEA7oFQkQsv8RcVERQrP6JtB81Rd3vt4ZHDWqfKOGvAhv4g5bx894FrRmz0SBhzonz8w", "enc:v1:0ddf368a:Wl3VjIzM_6X0gR-EEX4KZJhoZ2alPiowFF2TR9Gv6COH9i8vXVu0xJL4jGEuRlKCGU4bSMgvcd0X7nj1rWA", "enc:v1:0ddf368a:834sH48mH2jCxLZ-BtoIve_OHZYpyx_5jVs9c4w68Wabq3OCM7wHEXRS8aAE75TVzNGHMgEd67oMLVMVNOLVuDC9_0bsB9RidZadIa8aerF_7Z_n0t3XvrtyEQ"]
---

## Goal

"enc:v1:0ddf368a:gwqQxL9h2Y4k3iKUB9QZUesnov1597KEtRmlgtEsyv-BPXQwqZjewVscxkLd9-BViEuw33snm8YE7lOPHsklLfGH7g7xf_defdBj41snX-HCCFftXx8jDho" — read superpowers' brainstorming and writing-plans skills, and present in the reply what to adopt, adapt, or reject for the ISA spec → plan → ISA process (SPEC-v3), without changing any file yet.

## Criteria

- [x] ISC-1: Both upstream SKILL.md files were fetched and read in full this session.
- [x] ISC-2: The reply maps each adopted idea to its ISA-process adaptation, not a copy.
- [x] ISC-3: The reply names where superpowers conflicts with the ISA process and resolves each.
- [x] ISC-4: The reply ends with questions or a proposal for the user to decide.
- [x] ISC-5: Anti: future/SPEC-v3.md is changed in this turn (probe: `! grep -qi superpowers future/SPEC-v3.md`).

## Verification

- ISC-1: attested 2026-10-06T10:24:03 — curl'd raw brainstorming/SKILL.md (285 lines) and writing-plans/SKILL.md (204 lines) to the scratchpad and read both with Read, offset 0, no truncation (ledger: d1530fe46e)
- ISC-2: attested 2026-10-06T10:24:03 — reply section 'Adopt, adapted' maps each idea (triage+ratchet, said/assumed, questions, approaches, scope split, self-review, red flags; plan reader, header, Interfaces, right-sizing, Review focus, proportion) to its ISA form (spec lint, S-sections, step ISA seeds, Anti: ISCs) (ledger: 0d12718300)
- ISC-3: attested 2026-10-06T10:24:03 — reply section 'Where it conflicts' lists 7 conflicts (code-only vs any domain, TDD micro-steps vs ISA red/green, constraint duplication vs single owner, per-section chat approval vs hash-bound click, auto-commit, prose gate vs hooks, two flows side by side) each with a resolution (ledger: d67073aa64)
- ISC-4: attested 2026-10-06T10:24:03 — reply ends with 4 decisions for the user (superpowers replaced or kept, execution mode in the plan ack, commits, E4-E5 outline check) (ledger: 534d29d2de)
- ISC-5: attested 2026-10-06T10:24:11 — ran `! grep -qi superpowers future/SPEC-v3.md` → exit 0 (no mention); the spec file was not written this turn (ledger: 26b2cef651)
- Goal: yes — both skills read in full; the reply gives the adoptions (each adapted to spec lint, S-sections, step-ISA seeds), the conflicts with their resolutions, and the decisions left to the user; no file besides this ISA changed.
- Ask 1: met — inspiration taken: about 15 ideas from the two skills, each reshaped for the ISA flow.
- Ask 2: met — nothing copied: each idea is restated in ISA terms; the code-only and TDD-step parts are rejected or moved to the ISA.
- Ask 3: met — presented in the reply; nothing written to the spec yet.
