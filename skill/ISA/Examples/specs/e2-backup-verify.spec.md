---
status: acked 2026-03-15 #4011704c
effort: E2
---

<!-- Fictitious example, the spec behind Examples/e2-backup-verify.md. An E2 spec is the short form: Problem, the change, Accepted when. Its project path would be docs/spec/2026-03-15-backup-verify.md. -->

# Backup verify mode

## Problem
`rsync-verify` reports success without checking the copied bytes. Three "successful" backups last quarter were unrestorable.

## Goal
A `--verify` flag hashes source and destination with SHA-256 after the copy and fails the run on any difference, at most 1.5× the time of a clean backup.
Said:
- add a verify mode that catches a bad copy before the run says it succeeded
Assumed:
- a file only in the destination is reported as `EXTRA:`, not fatal.
- `ssh://` destinations stay out of scope for now.

## S1 — The `--verify` flag
After the copy, walk both trees, hash each file (streamed, never read whole), compare.
Accepted when:
- [ ] A1: when every file matches, the run prints a pass summary and exits 0
- [ ] A2: each differing file prints `MISMATCH: <path>` and each absent one `MISSING: <path>`, and the run exits 2, never 0
- [ ] A3: on a 10 GB tree, `--verify` takes at most 1.5× the no-verify wall-clock
- [ ] A4: a run without `--verify` computes no hash

## Open questions
