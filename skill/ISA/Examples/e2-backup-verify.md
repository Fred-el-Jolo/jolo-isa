---
task: "Backup verify mode"
slug: 20260315-094500_backup-verify
effort: E2
phase: draft
progress: 0/5
started: 2026-03-15T09:45:00
updated: 2026-03-15T10:10:00
root: /home/me/dev/rsync-verify
spec: specs/e2-backup-verify.spec.md
spec_hash: dfe8934f
---

<!-- Fictitious example ("rsync-verify" is a teaching name). E2: a spec first, two levels of criteria, every probe anchored to its spec section. -->

## Problem

`rsync-verify` reports success without checking the copied bytes. Three "successful" backups last quarter were unrestorable.

## Vision

An operator trusts a green run: when it says done, the backup restores.

## Out of Scope

`ssh://` destinations; repairing a bad copy.

## Principles

- A backup tool that can be wrong silently is worse than one that fails loudly.

## Constraints

- SHA-256, streamed: a file is never read whole.
- At most 1.5× the wall-clock of a backup without `--verify`.

## Goal

A `--verify` flag hashes source and destination with SHA-256 after the copy and fails the run on any difference, at most 1.5× the time of a clean backup.

## Criteria

- [0/5] ISC-1: `--verify` catches every bad copy.
  - [ ] ISC-1.1: A clean tree verifies with exit 0 and a pass summary.
  - [ ] ISC-1.2: A changed file prints `MISMATCH:` and exits 2.
  - [ ] ISC-1.3: A missing file prints `MISSING:` and exits 2.
  - [ ] ISC-1.4: A 10 GB tree verifies within 1.5× the plain backup time.
  - [ ] ISC-1.5: Anti: a run without `--verify` computes a hash.

## Test Strategy

```yaml
- isc: ISC-1.1
  anchors_to: S1
  kind: behaviour
  tool: ./test/clean-tree.sh
- isc: ISC-1.2
  anchors_to: S1
  kind: behaviour
  tool: ./test/mismatch.sh
- isc: ISC-1.3
  anchors_to: S1
  kind: behaviour
  tool: ./test/missing.sh
- isc: ISC-1.4
  anchors_to: S1
  kind: regression
  tool: './test/bench.sh --ratio-max 1.5'
  fails-when: "the verify run takes more than 1.5 times the plain run"
- isc: ISC-1.5
  anchors_to: S1
  kind: regression
  tool: '! RSYNC_VERIFY_TRACE=1 ./rsync-verify ./tmp/src ./tmp/dst 2>&1 | grep -q sha256'
  fails-when: "a plain run logs a sha256 call"
```
