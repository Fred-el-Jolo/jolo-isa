---
status: "acked 2026-03-15 #dfe8934f"
effort: E2
---

<!-- Fictitious example, the spec behind Examples/e2-backup-verify.md. In a project it would be docs/2026-03-15-backup-verify-01-spec.md. -->

# Backup verify mode

## Problem

`rsync-verify` reports success without checking the copied bytes. Three "successful" backups last quarter were unrestorable.

## Goal

A `--verify` flag hashes source and destination with SHA-256 after the copy and fails the run on any difference, at most 1.5× the time of a clean backup.
Said:
- add a verify mode that catches a bad copy before the run says it succeeded
Assumed:
- a file only in the destination is reported as `EXTRA:`, not fatal.

## Out of scope

`ssh://` destinations; repairing a bad copy.

## Constraints

- SHA-256, streamed: a file is never read whole.
- At most 1.5× the wall-clock of a backup without `--verify`.

## S1 — The `--verify` flag

After the copy, walk both trees, hash each file, compare.
Accepted when:
- when every file matches, the run prints a pass summary and exits 0
- each differing file prints `MISMATCH: <path>` and each absent one `MISSING: <path>`, and the run exits 2
- on a 10 GB tree, `--verify` takes at most 1.5× the no-verify wall-clock
- a run without `--verify` computes no hash

## Decisions

## Open questions
