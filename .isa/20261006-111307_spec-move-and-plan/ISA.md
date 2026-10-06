---
task: "Move the acked spec to docs/spec, write its plan"
slug: 20261006-111307_spec-move-and-plan
effort: E3
phase: complete
progress: 13/13
started: 2026-10-06T11:13:07
updated: 2026-10-06T11:23:11
root: .
stated_goal: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
stated_goal_source: prompt
asks: ["enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"]
context_sufficient: true
---

## Problem

The user acknowledged `future/SPEC-v3.md`. By the spec's own rules (Q7, Q14, § 5.5), an acked E4 spec moves to `docs/spec/2026-10-06-local-isas-spec-driven.md`, is committed alone, and gets a plan in `docs/plan/` with the same basename. That plan must itself be acknowledged and then committed. None of the spec's tooling exists yet: the ack is the user's typed word, and the hash and the lint checks are done by hand (bootstrap). The spec also predates its own template: it has no `S<n>` / `A<n>` ids, so plan steps cover its § 8 acceptance items instead.

## Vision

The user opens `docs/plan/…` and sees steps they could hand, one at a time, to a fresh session. Each step says which files, which names, which values, and what proves it, and nothing more.

## Out of Scope

No runtime, adapter, test, installer or skill change: the plan describes them. The spec body is not edited after the ack, apart from its frontmatter.

## Constraints

- The plan follows the spec's § B.3 template and § B.10 rules 10–15.
- Every file the plan names exists, or is marked `(new)`.
- Commits hold one file each: the spec, then the plan after its own ack.

## Goal

"enc:v1:0ddf368a:dN11tj93ajlzb4VqmRiWFHgA5CVrYSnfDhXJz3hdK1wac_G9YjS-k8m6fZwfCIE4senx7NUvRAXt7HyvSrasllUlx2Ek0w" — the acked spec sits at `docs/spec/2026-10-06-local-isas-spec-driven.md` with a matching `status: acked` hash, committed alone; `docs/plan/2026-10-06-local-isas-spec-driven.md` covers every § 8 acceptance item with ISA-sized steps, passes the § B.3 plan checks, and is acknowledged by the user and committed alone.

## Criteria

- [x] ISC-1: The spec sits at docs/spec/2026-10-06-local-isas-spec-driven.md, future/SPEC-v3.md gone.
- [x] ISC-2: The spec's status line carries the hash its content gives under § B.4.
- [x] ISC-3: The commit adding the spec holds that one file only.
- [x] ISC-4: No file outside .isa/ still points to future/SPEC-v3.md.
- [x] ISC-5: The plan exists with frontmatter status and the spec link.
- [x] ISC-6: The plan header has Goal, Approach, Files and Review focus lines, each pointing to an existing step.
- [x] ISC-7: Every plan step has tier, covers, Files and Done when; every after names a step.
- [x] ISC-8: Every § 8 acceptance item of the spec is covered by some plan step.
- [x] ISC-9: The plan is under 3× the spec's size and holds no TBD or TODO.
- [x] ISC-10: Every runtime/isa/*.py file the plan names exists or is marked new.
- [x] ISC-11: The user acknowledged the plan through the question tool.
- [x] ISC-12: The commit adding the plan holds that one file only.
- [x] ISC-13: Anti: a runtime, adapter, test, installer or skill file changes.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: file
  check: new path exists, old one gone
  threshold: exit 0
  fails-when: "the spec is not at the docs/spec path, or future/SPEC-v3.md still exists"
  tool: test -f docs/spec/2026-10-06-local-isas-spec-driven.md && test ! -e future/SPEC-v3.md

- isc: ISC-2
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: file
  check: recompute the § B.4 hash and compare with the status line
  threshold: status line matches
  fails-when: "the spec body changed after the status line was written, or the line is missing"
  tool: |-
    f=docs/spec/2026-10-06-local-isas-spec-driven.md; h=$(python3 -c "import re,hashlib,sys;t=open(sys.argv[1]).read().replace('\r\n','\n');L=[l for l in t.split('\n') if not re.match(r'^(status|Done):',l)];t='\n'.join(re.sub(r'\s+\(\d{4}-\d\d-\d\d, ISA [^)]*\)\s*$','',l.replace('- [x] ','- [ ] ',1)) for l in L);print(hashlib.sha256(t.encode()).hexdigest()[:8])" $f); grep -qE "^status: acked 2026-10-06 #$h$" $f

- isc: ISC-3
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: file
  check: the commit that added the spec names only it
  threshold: one path
  fails-when: "the spec is uncommitted, or its commit also holds other files"
  tool: |-
    f=docs/spec/2026-10-06-local-isas-spec-driven.md; c=$(git log --diff-filter=A --format=%H -- $f | tail -1); test -n "$c" && test "$(git diff-tree --no-commit-id --name-only -r $c)" = "$f"

- isc: ISC-4
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: file
  check: search for the old path outside the ISA folders
  threshold: no hit
  fails-when: "AGENTS.md or another file still names future/SPEC-v3.md"
  tool: "! rg -q --glob '!.isa/**' 'future/SPEC-v3' ."

- isc: ISC-5
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: file
  check: plan frontmatter
  threshold: status and spec lines
  fails-when: "no plan file, or no status: / spec: line pointing at the spec"
  tool: |-
    p=docs/plan/2026-10-06-local-isas-spec-driven.md; head -5 $p | grep -qE '^status: (draft|acked)' && head -5 $p | grep -qF 'spec: docs/spec/2026-10-06-local-isas-spec-driven.md'

- isc: ISC-6
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: doc
  check: header fields, and each Review focus target is a step
  threshold: all found
  fails-when: "a header field is missing, Review focus has more than 5 lines, or a target step does not exist"
  tool: |-
    p=docs/plan/2026-10-06-local-isas-spec-driven.md; for h in '^Goal: ' '^Approach: ' '^Files:' '^Review focus:'; do grep -qE "$h" $p || { echo "no $h"; exit 1; }; done; r=$(awk '/^Review focus:/{f=1;next} /^$/{f=0} f' $p | grep -oE '→ P[0-9]+'); n=$(echo "$r" | grep -c P); test "$n" -ge 1 && test "$n" -le 5 && for s in $(echo "$r" | grep -oE 'P[0-9]+'); do grep -qE "^- \[.\] $s — " $p || { echo "no step $s"; exit 1; }; done

- isc: ISC-7
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: doc
  check: per-step fields and after references
  threshold: no step missing a field
  fails-when: "a step lacks tier, covers, Files or Done when, or an after names no step"
  tool: |-
    p=docs/plan/2026-10-06-local-isas-spec-driven.md; awk '/^- \[.\] P[0-9]+ — /{if(s!=""&&(f==0||d==0)){print "incomplete " s; bad=1} s=$3; f=0; d=0; if($0 !~ / · E[1-5] · covers /){print "no tier/covers " s; bad=1}} /^  Files:/{f=1} /^  Done when:/{d=1} END{if(s!=""&&(f==0||d==0)){print "incomplete " s; bad=1} exit bad}' $p && for a in $(grep -oE '· after P[0-9]+(, P[0-9]+)*' $p | grep -oE 'P[0-9]+'); do grep -qE "^- \[.\] $a — " $p || { echo "no $a"; exit 1; }; done

- isc: ISC-8
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: doc
  check: each numbered § 8 item appears in some step's covers
  threshold: all covered
  fails-when: "an acceptance item number of the spec's § 8 appears in no step's covers list"
  tool: |-
    f=docs/spec/2026-10-06-local-isas-spec-driven.md; p=docs/plan/2026-10-06-local-isas-spec-driven.md; n=$(awk '/^## 8\. Acceptance/{x=1;next} /^## /{x=0} x' $f | grep -cE '^[0-9]+\. '); test "$n" -ge 10 && for k in $(seq 1 $n); do grep -E '^- \[.\] P[0-9]+ — ' $p | grep -qE "covers [^·]*§8\.$k([^0-9]|$)" || { echo "§8.$k"; exit 1; }; done

- isc: ISC-9
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: doc
  check: size ratio and placeholder scan
  threshold: plan bytes < 3 × spec bytes, no TBD/TODO
  fails-when: "the plan is 3× the spec or bigger, or contains TBD or TODO"
  tool: |-
    f=docs/spec/2026-10-06-local-isas-spec-driven.md; p=docs/plan/2026-10-06-local-isas-spec-driven.md; test $(wc -c < $p) -lt $((3 * $(wc -c < $f))) && ! sed -E 's/`[^`]*`//g' $p | grep -qE '\bTBD\b|\bTODO\b'

- isc: ISC-10
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: doc
  check: every .py name in the plan resolves or is marked (new)
  threshold: none missing
  fails-when: "the plan names a module that does not exist and is not marked (new)"
  tool: |-
    p=docs/plan/2026-10-06-local-isas-spec-driven.md; grep -oE '(runtime/isa/|tests/|tools/)?[a-z_0-9]+\.py' $p | sort -u | while read x; do b=${x##*/}; [ -e runtime/isa/$b ] || [ -e tests/$b ] || [ -e tests/flow/$b ] || [ -e tools/$b ] || [ "$b" = install.py ] || grep -qF "$b\` (new)" $p || grep -qF "$b (new)" $p || { echo "missing $x"; exit 1; }; done

- isc: ISC-11
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: manual
  kind: decision
  check: the user's answer to the plan ack question
  threshold: Acknowledge picked
  tool: AskUserQuestion "Acknowledge docs/plan/2026-10-06-local-isas-spec-driven.md?"

- isc: ISC-12
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: file
  check: the commit that added the plan names only it
  threshold: one path
  fails-when: "the plan is uncommitted, or its commit also holds other files"
  tool: |-
    p=docs/plan/2026-10-06-local-isas-spec-driven.md; c=$(git log --diff-filter=A --format=%H -- $p | tail -1); test -n "$c" && test "$(git diff-tree --no-commit-id --name-only -r $c)" = "$p"

- isc: ISC-13
  anchors_to: "enc:v1:0ddf368a:ivQ8yS9_Z67u_Rk0MXMfFV9owgAio6tsq3haw4USuQ2FAFvr9rXLDkhln2-MFYl-Cmefi5PNWSd5zb6SgjfgVexpg-3bT-Ji"
  type: bash
  kind: regression
  check: git status of the implementation folders
  threshold: empty
  fails-when: "git status lists a change under runtime/, adapters/, tests/, tools/, skill/ or install.py"
  tool: test -z "$(git status --porcelain -- runtime adapters tests tools skill install.py)"
```

## Features

```yaml
- name: MoveSpec
  description: frontmatter with the ack hash, git mv to docs/spec, references updated, committed alone
  satisfies: [ISC-1, ISC-2, ISC-3, ISC-4]
  depends_on: []
  parallelizable: false

- name: WritePlan
  description: the plan file, header, steps, coverage of § 8, size and name checks
  satisfies: [ISC-5, ISC-6, ISC-7, ISC-8, ISC-9, ISC-10, ISC-13]
  depends_on: [MoveSpec]
  parallelizable: false

- name: AckPlan
  description: the plan ack question, then the plan committed alone
  satisfies: [ISC-11, ISC-12]
  depends_on: [WritePlan]
  parallelizable: false
```

## Decisions

- 2026-10-06 refined: ISC-9 probe now ignores text in backticks. The plan names the placeholder words while stating P5's lint rule, which is a mention, not a placeholder. The same distinction went into P5's Done when, so the future spec lint won't flag a quoted rule.
- 2026-10-06: the spec was committed directly on `main` (6f74dc5), as the user's recent commits are; there was no branch for it.
- 2026-10-06: bootstrap. The ack was typed (the click mechanism is built in P7), and the hash was computed by hand with spec § B.4's rule. The spec has no S/A ids, so plan steps cover its § 8 items as `§8.N`.

## Verification

- ISC-1: verified 2026-10-06T11:23:11 — exit 0 in 0.0s — `test -f docs/spec/2026-10-06-local-isas-spec-driven.md && test ! -e future/SPEC-v3.md` (ledger: 19ae4eb3d6)
- ISC-2: verified 2026-10-06T11:23:11 — exit 0 in 0.03s — `f=docs/spec/2026-10-06-local-isas-spec-driven.md; h=$(python3 -c "import re,hashlib,sys;t=open(sys.argv[1]).read().replace('\r\n','\n');L=[l for l in t.split('\n') if not re.match(r'^(status|Done):',l)];t='\n'.join(re.sub(r'\s+\(\d{4}-\d\d-\d\d, ISA [^)]*\)\s*$','',l.replace('- [x] ','- [ ] ',1)) for l in L);print(hashlib.sha256(t.encode()).hexdigest()[:8])" $f); grep -qE "^status: acked 2026-10-06 #$h$" $f` (ledger: c350b2197e)
- ISC-3: verified 2026-10-06T11:23:11 — exit 0 in 0.01s — `f=docs/spec/2026-10-06-local-isas-spec-driven.md; c=$(git log --diff-filter=A --format=%H -- $f | tail -1); test -n "$c" && test "$(git diff-tree --no-commit-id --name-only -r $c)" = "$f"` (ledger: 30c0ba8766)
- ISC-4: verified 2026-10-06T11:23:11 — exit 0 in 0.01s — `! rg -q --glob '!.isa/**' 'future/SPEC-v3' .` (ledger: 1c231dd58f)
- ISC-5: verified 2026-10-06T11:23:11 — exit 0 in 0.0s — `p=docs/plan/2026-10-06-local-isas-spec-driven.md; head -5 $p | grep -qE '^status: (draft|acked)' && head -5 $p | grep -qF 'spec: docs/spec/2026-10-06-local-isas-spec-driven.md'` (ledger: 23322134c6)
- ISC-6: verified 2026-10-06T11:23:11 — exit 0 in 0.02s — `p=docs/plan/2026-10-06-local-isas-spec-driven.md; for h in '^Goal: ' '^Approach: ' '^Files:' '^Review focus:'; do grep -qE "$h" $p || { echo "no $h"; exit 1; }; done; r=$(awk '/^Review focus:/{f=1;next} /^$/{f=0} f' $p | grep -oE '→ P[0-9]+'); n=$(echo "$r" | grep -c P); test "$n" -ge 1 && test "$n" -le 5 && for s in $(echo "$r" | grep -oE 'P[0-9]+'); do grep -qE "^- \[.\] $s — " $p || { echo "no step $s"; exit 1; }; done` (ledger: b6af29ea47)
- ISC-7: verified 2026-10-06T11:23:11 — exit 0 in 0.02s — `p=docs/plan/2026-10-06-local-isas-spec-driven.md; awk '/^- \[.\] P[0-9]+ — /{if(s!=""&&(f==0||d==0)){print "incomplete " s; bad=1} s=$3; f=0; d=0; if($0 !~ / · E[1-5] · covers /){print "no tier/covers " s; bad=1}} /^  Files:/{f=1} /^  Done when:/{d=1} END{if(s!=""&&(f==0||d==0)){print "incomplete " s; bad=1} exit bad}' $p && for a in $(grep -oE '· after P[0-9]+(, P[0-9]+)*' $p | grep -oE 'P[0-9]+'); do grep -qE "^- \[.\] $a — " $p || { echo "no $a"; exit 1; }; done` (ledger: d6551222c4)
- ISC-8: verified 2026-10-06T11:23:11 — exit 0 in 0.03s — `f=docs/spec/2026-10-06-local-isas-spec-driven.md; p=docs/plan/2026-10-06-local-isas-spec-driven.md; n=$(awk '/^## 8\. Acceptance/{x=1;next} /^## /{x=0} x' $f | grep -cE '^[0-9]+\. '); test "$n" -ge 10 && for k in $(seq 1 $n); do grep -E '^- \[.\] P[0-9]+ — ' $p | grep -qE "covers [^·]*§8\.$k([^0-9]|$)" || { echo "§8.$k"; exit 1; }; done` (ledger: ac1148f67e)
- ISC-10: verified 2026-10-06T11:23:11 — exit 0 in 0.01s — `p=docs/plan/2026-10-06-local-isas-spec-driven.md; grep -oE '(runtime/isa/|tests/|tools/)?[a-z_0-9]+\.py' $p | sort -u | while read x; do b=${x##*/}; [ -e runtime/isa/$b ] || [ -e tests/$b ] || [ -e tests/flow/$b ] || [ -e tools/$b ] || [ "$b" = install.py ] || grep -qF "$b\` (new)" $p || grep -qF "$b (new)" $p || { echo "missing $x"; exit 1; }; done` (ledger: bce6e3653c)
- ISC-13: verified 2026-10-06T11:23:11 — exit 0 in 0.0s — `test -z "$(git status --porcelain -- runtime adapters tests tools skill install.py)"` (ledger: 4f2585b394)
- ISC-9: verified 2026-10-06T11:23:11 — exit 0 in 0.01s — `f=docs/spec/2026-10-06-local-isas-spec-driven.md; p=docs/plan/2026-10-06-local-isas-spec-driven.md; test $(wc -c < $p) -lt $((3 * $(wc -c < $f))) && ! sed -E 's/`[^`]*`//g' $p | grep -qE '\bTBD\b|\bTODO\b'` (ledger: 491b7ad88d)
- ISC-11: attested 2026-10-06T11:22:50 — AskUserQuestion header 'Plan ack', question 'Acknowledge docs/plan/2026-10-06-local-isas-spec-driven.md? …' — the user picked Acknowledge; plan hash 5afe3325 written into status (ledger: 9e59cd7f62)
- ISC-12: verified 2026-10-06T11:23:11 — exit 0 in 0.01s — `p=docs/plan/2026-10-06-local-isas-spec-driven.md; c=$(git log --diff-filter=A --format=%H -- $p | tail -1); test -n "$c" && test "$(git diff-tree --no-commit-id --name-only -r $c)" = "$p"` (ledger: d7e0b7d35c)
- Goal: yes — the acked spec is at docs/spec/2026-10-06-local-isas-spec-driven.md (hash 835d76a3, committed alone in 6f74dc5); the plan covers all 17 § 8 items in 13 steps, passed its checks, was acknowledged by the user's click, and was committed alone (1440aea, hash 5afe3325). No code changed.
- Ask 1: met — ack recorded in the spec's status line, spec moved and committed, plan written, acked and committed.
