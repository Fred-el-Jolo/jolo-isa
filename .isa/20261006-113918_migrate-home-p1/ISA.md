---
task: "Build isa migrate --home (plan step P1)"
slug: 20261006-113918_migrate-home-p1
effort: E3
phase: complete
progress: 17/17
started: 2026-10-06T11:39:18
updated: 2026-10-06T11:48:02
root: .
stated_goal: "enc:v1:0ddf368a:5PM7ey2aSq7wPGpZ7loLUeCOb5fBckaNjTM7lUcm0sbHBg7Gc-m1N9ZdWKacwAmST4ll7mpTptArvkWfdGXqKD_jZW1KIjobTSDNeNLujTru8TA4wJkMGbGBMJbh2IqWia2gO80ZO35PFAI"
stated_goal_source: prompt
asks: ["enc:v1:0ddf368a:5PM7ey2aSq7wPGpZ7loLUeCOb5fBckaNjTM7lUcm0sbHBg7Gc-m1N9ZdWKacwAmST4ll7mpTptArvkWfdGXqKD_jZW1KIjobTSDNeNLujTru8TA4wJkMGbGBMJbh2IqWia2gO80ZO35PFAI", "enc:v1:0ddf368a:JUKjOh2fGf36qS9uuXWZKjcrymqXWJGvqColutankqiqFUE5ZXwP7uSPRkaqvIB5SGfxO6m6n4hesy3RZDUBwSoyHwSN9B7BSTCwqf27_VN6kmBGEyBbUzLCzAlAeF_STZhh3dcwCp6kWRo3wYManutx5dTMvmx-1ynPizSwqeNM1PkRcBaK", "enc:v1:0ddf368a:fq_zHSZI5KfrADVTGo7WG6d4Px9pcStEMtIh38K4hUVepUXVI4FCQT-bRmGGkUicO4PcNqbK8grdKmfEVmV2afUaV3SizbMenrCjYi2ybSiLpHQDHLa9S8TpeyuGpIXUZg", "enc:v1:0ddf368a:SiKJI5x0-WIDnEwmE1Zdyw0IsfKCEinZHA580uOLBmDvW4G7RXmhL5twFLrweKaUQc95TQ0cAZqhmjMYxjUApTqyHCErlUmgEnbA5k4xiUV3UuOVDd34wc86PIUhqRnSULuPmQyz2YezU39I_07sOg48Ftd-LaM9ZlAaF2qbJBrm2xPsJdfp", "enc:v1:0ddf368a:rwfr1VAY5b_n5uvRWhWDcGHB9fdbmdZmPXqW0yWVNhn8IX7rsgNuObaRDzrUeLBCSevRrdq6X_5tF5UvxgA5ftM7jHoKAUQD827N1pQ-lbcMf9wacA_v-EhXYpdg0nQHFRi9gC0-W_6riDbnaWHZZAlbfyO-mLZusOH7ARN-C9xZxg7HqhjxZstfpqz3hqnnSfpg4YCQwl8vRw", "enc:v1:0ddf368a:A9rmyGfgNm0DFJBcbKkv6u1JiDP8vSdoX_RlSK9_aBm9XcB6ZBCllQtY4ljnfkVkPkjA3JFoyxtQrK2nJ6gWul6orfipS_PGecM5WMs81mA08PKqmciUObSHEQXpFqD0Jh98xI-J9aM0aH8", "enc:v1:0ddf368a:ICX4lr6Vni3POZ-OPn8Gm78jISbNGqj-VXBRk62oPVdBXRR09ZPHlRfpJ4ybxWr43as-H7AUyG1J6VqiBW5Qt_uCSqjK4JWOWgJ4lMFzoNw76zxt4VZc", "enc:v1:0ddf368a:o_CZPF7NVvInhmm-2lrmbcQjxAyvsxvfsD9GGpxIcwo1gQ1ItSyXV0rZYJKtl7_EnLPpATPcr0SuyUa_YO4BHCzqaKH6zTt_ociYkEjFQz06bL3KdkNLWQghfg_GjhY8CX0cgIYDnj-XT3cDyxMHGNIl_I4mVC5xBmQa0UNI"]
context_sufficient: true
---

## Problem

Plan step P1 of `docs/plan/2026-10-06-local-isas-spec-driven.md` (spec § A.5, acceptance § 8.3). Four repos hold committed task ISAs under `<repo>/.isa/`, with an evidence ledger beside each, repo-relative `root:`, `.gitattributes` filter lines and a `filter.isa` git config section. Nothing moves them back to `~/.isa` yet, and the move must run while `crypt.py` still exists so a value still encrypted on disk can be opened. Today's `isa migrate` goes the other way (home → repo).

## Vision

The user runs `isa migrate --home --dry-run` in a repo, reads the exact list of moves, runs it for real, and pastes the one printed commit command. Afterwards each moved ISA lints clean in `~/.isa/<project-key>/`, every `(ledger: <id>)` line still resolves, and their sessions still find their ISA.

## Out of Scope

Running the migration on the real repos and deleting `~/.isa/key` (P2, the user's). Changing where `isa new` writes, removing `crypt.py`, `isa key`, the old `isa migrate` or any § 13 code (P3, P4). Docs (SKILL.md, AGENTS.md). Committing anything.

## Constraints

- Interfaces as the plan names them: `commands.migrate_home(args, out=print) -> int`, args `["--dry-run"]` or `[]`; it reuses `commands._rebind(moved)`.
- `runtime/` stays standard-library only.
- Test-first: the tests exist and `isa verify --red` records them failing before `migrate_home` is written.
- The repo's uncommitted `AGENTS.md` change, the untracked `.isa/20261006-*` folders, the real repos and `~/.isa/key` stay untouched.

## Goal

"enc:v1:0ddf368a:xIUYaNYsSsgt14spAM06eLWqEOQImuI-8WM2kunfqagY_WvzrgfX-z0QwN_plz63kUU1IayzltBCcEfz1VtusRMxDu65aiMrVdryFJNCAHgUmwwHl6hQciv-E8bsh-I5cr0b1fGItAOI" — run inside a git repo, `isa migrate --home` moves every `<repo>/.isa/<slug>/` to `~/.isa/<project-key>/<slug>/` with its ledger, absolute `root:` and decrypted values, rebinds sessions, removes the `.isa` git filter, prints the commit to run and commits nothing; `--dry-run` prints the same list and changes nothing. Every Done-when bullet of P1 is proven by a test in `tests/test_migrate_home.py`.

## Criteria

- [x] ISC-1: Every repo .isa slug folder, _ephemeral included, moves to the home project folder.
- [x] ISC-2: The ledger moves to the home evidence name, root/cwd absolute, ids unchanged.
- [x] ISC-3: A moved ISA's relative root becomes absolute and `isa lint` is clean.
- [x] ISC-4: An enc:v1 value is decrypted with the key; without a key replaced by "" and reported.
- [x] ISC-5: Sessions bound to a moved ISA are rebound to its new path.
- [x] ISC-6: The two .isa lines leave .gitattributes and the filter.isa git section is removed.
- [x] ISC-7: The root ISA.md stays byte-identical; a slug already at home is skipped and named.
- [x] ISC-8: The command prints the exact git rm/add/commit line and commits nothing.
- [x] ISC-9: `--dry-run` prints the same move list and changes no file.
- [x] ISC-10: Anti: this repo's .isa folders, .gitattributes or filter.isa config were migrated.
- [x] ISC-11: The full Python unit suite from AGENTS.md passes, with the new test module.
- [x] ISC-12: `python3 tests/check_stdlib.py runtime/` passes.
- [x] ISC-13: The pi extension and statusline node tests pass.
- [x] ISC-14: Anti: AGENTS.md or the earlier 2026-10-06 ISA folders changed.
- [x] ISC-15: The moved ledger's asks snapshot holds the asks verbatim, no hmac tags.
- [x] ISC-16: `migrate_home(args, out=print)` exists and calls `_rebind`.
- [x] ISC-17: Anti: ~/.isa/key was changed or removed.

## Test Strategy

```yaml
- isc: ISC-1
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: two slug folders (one with _ephemeral/) end up under ISA_HOME/<project_key(repo)>/, none left in <repo>/.isa
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestMove

- isc: ISC-2
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: ledger at evidence.ledger_path(new) = _state/evidence/<slug>-<sha256(real)[:12]>.jsonl, root/cwd absolute, ids equal, Verification ledger refs resolve
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestLedger

- isc: ISC-3
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: root . and root sub/dir rewritten to absolute paths; `isa lint` exits 0 on the moved ISA
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestRoot

- isc: ISC-4
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: an encrypted-on-disk ISA comes out plain with ISA_KEY; with no key its values read "" and the output names them
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestEncrypted

- isc: ISC-5
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: a session file bound to the repo ISA is bound to the home path after the move
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestRebind

- isc: ISC-6
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: .gitattributes deleted when only the two lines were there, other lines kept otherwise; `git config --get-regexp ^filter\.isa` empty
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestGitCleanup

- isc: ISC-7
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: root ISA.md bytes equal before/after; a slug present at home stays in the repo and is named in a skip line
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestUntouchedAndSkip

- isc: ISC-8
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: output holds the exact commit line; HEAD and the commit count unchanged
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestCommitLine

- isc: ISC-9
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: dry-run list lines equal the real run's; repo fingerprint and a content walk of repo + ISA home (logs aside) equal before/after
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestDryRun

- isc: ISC-10
  anchors_to: "spec §8.3"
  type: bash
  kind: regression
  check: this repo still has its .isa folders, the .gitattributes lines and filter.isa.required
  threshold: exit 0
  fails-when: "the migration ran on this repo: .isa/20261003-010436_* gone, the filter line gone from .gitattributes, or filter.isa unset"
  tool: test -f .isa/20261003-010436_notification-prompts-and-clear-isas/ISA.md && grep -qxF '.isa/**/*.md filter=isa' .gitattributes && test "$(git config --get filter.isa.required)" = true

- isc: ISC-11
  anchors_to: "spec §8.3"
  type: unit-test
  kind: regression
  check: the AGENTS.md unit list plus tests.test_migrate_home
  threshold: exit 0
  fails-when: "any test of the suite fails or errors"
  tool: python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install tests.test_status tests.test_evidence tests.test_shell_changes tests.test_feature_order tests.test_home_and_complete tests.test_seamless_projects tests.test_gate tests.test_commands tests.test_fingerprint tests.test_blocked tests.test_red tests.test_lint_v2 tests.test_purge tests.test_declaration tests.test_logs tests.test_ask tests.test_jev tests.test_m11 tests.test_m12 tests.test_migrate_home tests.flow.test_isa_flow

- isc: ISC-12
  anchors_to: "spec §8.3"
  type: bash
  kind: regression
  check: stdlib-only imports under runtime/
  threshold: exit 0
  fails-when: "a runtime module imports a non-stdlib package"
  tool: python3 tests/check_stdlib.py runtime/

- isc: ISC-13
  anchors_to: "spec §8.3"
  type: bash
  kind: regression
  check: node tests of both adapters
  threshold: exit 0
  fails-when: "an adapter test fails"
  tool: node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts

- isc: ISC-14
  anchors_to: "spec §8.3"
  type: bash
  kind: regression
  check: content hashes of AGENTS.md and the three earlier 2026-10-06 ISA folders equal those taken at the start
  threshold: exit 0
  fails-when: "AGENTS.md or a file in those folders differs from its hash at the start of this task"
  tool: test "$(sha256sum AGENTS.md | cut -c1-16)" = ec9bc8e688a1641b && test "$(find .isa/20261006-092030_local-isas-spec-driven-spec .isa/20261006-102222_superpowers-spec-plan-findings .isa/20261006-111307_spec-move-and-plan -type f | sort | xargs sha256sum | sha256sum | cut -c1-16)" = 9011b7e80e05f4b2

- isc: ISC-15
  anchors_to: "spec §8.3"
  type: unit-test
  kind: behaviour
  check: an `asks` row written as hmac tags in the repo ledger reads as the verbatim asks after the move
  threshold: exit 0
  tool: python3 -m unittest tests.test_migrate_home.TestAsksSnapshot

- isc: ISC-16
  anchors_to: "spec §8.3"
  type: bash
  kind: file
  check: inspect the signature and the source of commands.migrate_home
  threshold: exit 0
  fails-when: "migrate_home is missing, its signature differs from (args, out=print), or it does not call _rebind"
  tool: python3 -c "import inspect,sys; sys.path.insert(0,'runtime'); from isa import commands as c; s=inspect.signature(c.migrate_home); assert list(s.parameters)==['args','out'] and s.parameters['out'].default is print; assert '_rebind(' in inspect.getsource(c.migrate_home)"

- isc: ISC-17
  anchors_to: "spec §8.3"
  type: bash
  kind: regression
  check: the key file's mtime equals the one taken at the start
  threshold: exit 0
  fails-when: "~/.isa/key is gone or was rewritten"
  tool: test "$(stat -c %Y ~/.isa/key)" = 1790981575
```

## Features

```yaml
- name: move-and-ledger
  description: folders, ledger, root rewrite and asks snapshot of a plain repo ISA land at home and lint clean
  satisfies: [ISC-1, ISC-2, ISC-3, ISC-15, ISC-16]
  depends_on: []
  parallelizable: false
- name: decrypt-leftovers
  description: enc:v1 values still on disk are opened with the key, or blanked and reported
  satisfies: [ISC-4]
  depends_on: []
  parallelizable: false
- name: repo-cleanup-and-report
  description: sessions rebound, git filter removed, root ISA.md and existing slugs left alone, commit line printed
  satisfies: [ISC-5, ISC-6, ISC-7, ISC-8]
  depends_on: []
  parallelizable: false
- name: dry-run
  description: the same list with no file changed
  satisfies: [ISC-9]
  depends_on: []
  parallelizable: false
- name: suite-and-guards
  description: full suites green; this repo, AGENTS.md, earlier ISAs and the key untouched
  satisfies: [ISC-10, ISC-11, ISC-12, ISC-13, ISC-14, ISC-17]
  depends_on: []
  parallelizable: false
```

## Decisions

- 2026-10-06 11:45: refined: plan P1 says the ledger's `files` get rewritten absolute — its keys are relative to the probe `root` (`commands.named_files`), in home ledgers too, never repo-relative; `_changed_since_red` compares them across rows. They stay as they are, so rows written after the move still compare; only `root` / `cwd` (which `evidence.record` made repo-relative) become absolute.
- 2026-10-06 11:45: added ISC-15 (not a P1 bullet): a repo ledger's `asks` snapshot holds hmac tags; once the ISA is outside a repo lint compares the snapshot with the plain asks and would flag every one as removed, so bullet 3 ("`isa lint` is clean") needs the snapshot back to verbatim (spec § A.2).
- 2026-10-06 11:50: a slug already at home is skipped and the command exits 1 (the rest still runs): a partial move should not look like success to a script; the summary names the skipped slugs.
- 2026-10-06 11:50: an encrypted value that the key can't open (no key, or another key) is blanked to `""`, so no `enc:v1:` string reaches `~/.isa` (spec § A.5, Q8).

## Verification

- ISC-1: verified 2026-10-06T11:48:02 — exit 0 in 0.85s — `python3 -m unittest tests.test_migrate_home.TestMove` (ledger: 7169423f91)
- ISC-2: verified 2026-10-06T11:48:02 — exit 0 in 0.85s — `python3 -m unittest tests.test_migrate_home.TestLedger` (ledger: e98253035a)
- ISC-3: verified 2026-10-06T11:48:02 — exit 0 in 0.96s — `python3 -m unittest tests.test_migrate_home.TestRoot` (ledger: 1f567d1aae)
- ISC-4: verified 2026-10-06T11:48:02 — exit 0 in 1.73s — `python3 -m unittest tests.test_migrate_home.TestEncrypted` (ledger: 6564cbf5dd)
- ISC-5: verified 2026-10-06T11:48:02 — exit 0 in 0.86s — `python3 -m unittest tests.test_migrate_home.TestRebind` (ledger: 3e1187aab0)
- ISC-6: verified 2026-10-06T11:48:02 — exit 0 in 1.58s — `python3 -m unittest tests.test_migrate_home.TestGitCleanup` (ledger: fea2ec07f6)
- ISC-7: verified 2026-10-06T11:48:02 — exit 0 in 0.85s — `python3 -m unittest tests.test_migrate_home.TestUntouchedAndSkip` (ledger: 13a60c7fcb)
- ISC-8: verified 2026-10-06T11:48:02 — exit 0 in 0.86s — `python3 -m unittest tests.test_migrate_home.TestCommitLine` (ledger: ea84ea2111)
- ISC-9: verified 2026-10-06T11:48:02 — exit 0 in 1.03s — `python3 -m unittest tests.test_migrate_home.TestDryRun` (ledger: 52d298317e)
- ISC-10: verified 2026-10-06T11:48:02 — exit 0 in 0.0s — `test -f .isa/20261003-010436_notification-prompts-and-clear-isas/ISA.md && grep -qxF '.isa/**/*.md filter=isa' .gitattributes && test "$(git config --get filter.isa.required)" = true` (ledger: baca687793)
- ISC-11: verified 2026-10-06T11:48:02 — exit 0 in 90.31s — `python3 -m unittest tests.test_hooks tests.test_bash_classifier tests.test_state tests.test_install tests.test_status tests.test_evidence tests.test_shell_changes tests.test_feature_order tests.test_home_and_complete tests.test_seamless_projects tests.test_gate tests.test_commands tests.test_fingerprint tests.test_blocked tests.test_red tests.test_lint_v2 tests.test_purge tests.test_declaration tests.test_logs tests.test_ask tests.test_jev tests.test_m11 tests.test_m12 tests.test_migrate_home tests.flow.test_isa_flow` (ledger: e431d74800)
- ISC-12: verified 2026-10-06T11:48:02 — exit 0 in 0.14s — `python3 tests/check_stdlib.py runtime/` (ledger: e6fdcd1f20)
- ISC-13: verified 2026-10-06T11:48:02 — exit 0 in 4.34s — `node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts` (ledger: 08e7984911)
- ISC-14: verified 2026-10-06T11:48:02 — exit 0 in 0.01s — `test "$(sha256sum AGENTS.md | cut -c1-16)" = ec9bc8e688a1641b && test "$(find .isa/20261006-092030_local-isas-spec-driven-spec .isa/20261006-102222_superpowers-spec-plan-findings .isa/20261006-111307_spec-move-and-plan -type f | sort | xargs sha256sum | sha256sum | cut -c1-16)" = 9011b7e80e05f4b2` (ledger: bc0be58218)
- ISC-15: verified 2026-10-06T11:48:02 — exit 0 in 0.85s — `python3 -m unittest tests.test_migrate_home.TestAsksSnapshot` (ledger: 5d142af7c7)
- ISC-16: verified 2026-10-06T11:48:02 — exit 0 in 0.06s — `python3 -c "import inspect,sys; sys.path.insert(0,'runtime'); from isa import commands as c; s=inspect.signature(c.migrate_home); assert list(s.parameters)==['args','out'] and s.parameters['out'].default is print; assert '_rebind(' in inspect.getsource(c.migrate_home)"` (ledger: cacf9a169c)
- ISC-17: verified 2026-10-06T11:48:02 — exit 0 in 0.0s — `test "$(stat -c %Y ~/.isa/key)" = 1790981575` (ledger: 33b40d9fe7)
- Goal: yes — `isa migrate --home [--dry-run]` exists (`commands.migrate_home`, wired in `cli.py`), and tests/test_migrate_home.py proves each of P1's nine Done-when bullets on real git repos (ISC-1–9), plus the asks snapshot lint needs (ISC-15); the full suite, stdlib check and node tests pass.
- Ask 1: met — `isa migrate --home` built; 12 tests in tests/test_migrate_home.py (ISC-1–9, 15, 16).
- Ask 2: met — never run on a real repo (ISC-10: this repo's .isa/, .gitattributes and filter.isa intact); ~/.isa/key untouched (ISC-17); P2 not started.
- Ask 3: met — `isa verify --red` recorded every behaviour probe failing before `migrate_home` was written.
- Ask 4: met — the AGENTS.md unit list (plus the new module) and `python3 tests/check_stdlib.py runtime/` pass (ISC-11, ISC-12).
- Ask 5: met — AGENTS.md and the three earlier 2026-10-06 ISA folders hash as at the start (ISC-14).
- Ask 6: met — nothing committed; the final answer asks before committing, on a branch.
- Ask 7: met — the final answer quotes the `isa close` summary and stops.
- Ask 8: met — the final answer lists install.py, then the dry run and the run in each of the four repos.
