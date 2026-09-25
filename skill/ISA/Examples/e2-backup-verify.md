---
task: "Add SHA-256 verification to a backup CLI's --verify mode"
slug: 20260315-094500_backup-sha256-verify
effort: E2
phase: execute
progress: 0/18
started: 2026-03-15T16:45:00Z
updated: 2026-03-21T22:00:00Z
---

<!-- Fictitious example. "rsync-verify" is a teaching project name; any resemblance to real tools is coincidental. -->

## Problem

The `rsync-verify` CLI copies a source directory to a backup destination and reports completion. It does not currently verify that the destination bytes match the source. Bit rot, partial copies, and silent FS corruption have caused three "successful" backups in the last quarter to land unrestorable. Operators want a `--verify` mode that hashes both sides and surfaces mismatches before the run reports success.

## Goal

Add a `--verify` flag that, after the rsync copy step completes, walks both source and destination, computes SHA-256 per file, compares hashes, and either exits 0 with a pass summary or exits 2 with a per-file mismatch report. The verification step must not double the run-time of a clean backup more than 1.5×.

## Criteria

### Verification correctness

- [ ] ISC-1: `rsync-verify --verify <src> <dst>` exits 0 when every source file's SHA-256 matches.
- [ ] ISC-2: `rsync-verify --verify <src> <dst>` exits 2 when ≥1 file mismatches.
- [ ] ISC-3: Each diverging file is printed to stderr as one `MISMATCH: <path>` line.
- [ ] ISC-4: A file missing from `<dst>` prints `MISSING: <path>` and forces exit 2.
- [ ] ISC-5: A file only in `<dst>` prints `EXTRA: <path>` and leaves exit code 0.
- [ ] ISC-6: Hashing streams file contents; no whole-file read for files over 64KB.

### Performance

- [ ] ISC-7: Verify-mode wall-clock on a 10GB tree is ≤ 1.5× no-verify wall-clock.
- [ ] ISC-8: Hashing worker pool never exceeds `os.cpus().length` concurrent workers.
- [ ] ISC-9: Peak RSS stays under 256MB while hashing a single 50GB file.

### CLI surface

- [ ] ISC-10: `rsync-verify --help` lists `--verify` with a one-sentence description.
- [ ] ISC-11: `--verify --json` emits `{passed, mismatches, missing, extra, elapsed_ms}` JSON on stdout.
- [ ] ISC-12: `--verify-only` verifies without ever invoking the rsync copy step.

### Error handling

- [ ] ISC-13: An unreadable source file prints `ERROR: cannot read <path>` and exits 3.
- [ ] ISC-14: SIGINT during verify prints `verify aborted at file <N>/<total>` and exits 130.

### Anti-criteria

- [ ] ISC-15: Anti: out of scope — `--verify` with an `ssh://` destination is rejected with an error.
- [ ] ISC-16: Anti: regression — a plain run without `--verify` never computes any hashes.
- [ ] ISC-17: Anti: privacy — verify mode never writes file contents to stdout, stderr, or logs.
- [ ] ISC-18: Anti: exit 0 is never returned while any MISMATCH or MISSING line was printed.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  check: clean backup verifies pass
  threshold: exit 0
  tool: ./test/integration/clean-tree.sh && rsync-verify --verify ./tmp/src ./tmp/dst

- isc: ISC-2
  type: bash
  check: corrupted backup fails verify
  threshold: exit 2
  tool: ./test/integration/clean-tree.sh && printf '\x00' >> ./tmp/dst/file7.bin && rsync-verify --verify ./tmp/src ./tmp/dst; test $? -eq 2

- isc: ISC-3
  type: bash
  check: stderr names the flipped file with the MISMATCH prefix
  threshold: 'exactly 1 line, equal to "MISMATCH: file7.bin"'
  tool: |-
    ./test/integration/flip-one.sh && rsync-verify --verify ./tmp/src ./tmp/dst 2>&1 >/dev/null | grep '^MISMATCH: '

- isc: ISC-4
  type: bash
  check: a deleted destination file is reported and fails the run
  threshold: '"MISSING: file3.bin" on stderr + exit 2'
  tool: ./test/integration/clean-tree.sh && rm ./tmp/dst/file3.bin && rsync-verify --verify ./tmp/src ./tmp/dst; test $? -eq 2

- isc: ISC-5
  type: bash
  check: an extra destination file is a warning only
  threshold: '"EXTRA: stray.bin" on stderr + exit 0'
  tool: ./test/integration/clean-tree.sh && touch ./tmp/dst/stray.bin && rsync-verify --verify ./tmp/src ./tmp/dst

- isc: ISC-6
  type: bash
  check: no whole-file buffer reads in the hash path
  threshold: zero matches (rg exits 1)
  tool: rg -n 'readFileSync|Buffer\.from\(|await .*\.arrayBuffer\(\)' src/verify/

- isc: ISC-7
  type: performance
  check: verify-mode ≤ 1.5× no-verify
  threshold: ratio ≤ 1.5
  tool: bash benchmarks/10gb-tree.sh

- isc: ISC-8
  type: unit-test
  check: pool high-water mark on a 1,000-file tree
  threshold: max concurrent workers ≤ os.cpus().length
  tool: bun test test/pool.test.ts -t "never exceeds cpu count"

- isc: ISC-9
  type: memory
  check: peak RSS during 50GB hash
  threshold: ≤ 256MB
  tool: bash benchmarks/large-file-rss.sh

- isc: ISC-10
  type: bash
  check: --help mentions --verify
  threshold: exactly 1 matching line
  tool: rsync-verify --help | grep -c -- '--verify '

- isc: ISC-11
  type: bash
  check: JSON output has the documented keys and types
  threshold: jq prints true
  tool: "rsync-verify --verify --json ./tmp/src ./tmp/dst | jq '(.passed|type==\"boolean\") and (.mismatches|type==\"array\") and (.missing|type==\"array\") and (.extra|type==\"array\") and (.elapsed_ms|type==\"number\")'"

- isc: ISC-12
  type: bash
  check: no rsync process spawned under --verify-only
  threshold: zero rsync execve calls
  tool: strace -f -e trace=execve rsync-verify --verify-only ./tmp/src ./tmp/dst 2>&1 | grep -c 'execve(".*/rsync"' | grep -qx 0

- isc: ISC-13
  type: bash
  check: permission-denied source file
  threshold: '"ERROR: cannot read" on stderr + exit 3'
  tool: ./test/integration/clean-tree.sh && chmod 000 ./tmp/src/file1.bin && rsync-verify --verify ./tmp/src ./tmp/dst; test $? -eq 3

- isc: ISC-14
  type: bash
  check: SIGINT mid-run
  threshold: '"verify aborted at file" on stderr + exit 130'
  tool: ./test/integration/sigint.sh   # starts verify on the 10GB tree, sends SIGINT after 2s, checks message + $?

- isc: ISC-15
  type: bash
  check: --verify with a remote destination is rejected
  threshold: 'stderr "ERROR: --verify requires local destination" + non-zero exit'
  tool: rsync-verify --verify ./tmp/src ssh://host/path 2>&1 | grep -q 'requires local destination'

- isc: ISC-16
  type: bash
  check: plain run opens no hash stream
  threshold: zero "hash:" lines in debug trace
  tool: RSYNC_VERIFY_DEBUG=1 rsync-verify ./tmp/src ./tmp/dst 2>&1 | grep -c '^hash:' | grep -qx 0

- isc: ISC-17
  type: bash
  check: file contents never appear in any output stream or log
  threshold: 0 occurrences of the fixture sentinel
  tool: rsync-verify --verify ./tmp/src ./tmp/dst 2>&1 | cat - ~/.cache/rsync-verify/*.log | rg -c "TEST_FIXTURE_SENTINEL_BYTES" | grep -qx 0

- isc: ISC-18
  type: property
  property: "exit code is 0 ⇔ mismatches = 0 ∧ missing = 0"
  generator: "random trees of 1–200 files, each file independently flipped / deleted / untouched / extra"
  runs: 500
  tool: bun test test/exit-code.property.test.ts
```

<!--
E2 medium ISA. Required sections: Problem, Goal, Criteria, Test Strategy.
Vision, Out of Scope, Principles, Constraints, Features, Decisions, Changelog, Verification omitted — the work surface is single-domain (one CLI, one feature) and the tier completeness gate doesn't require them. Four anti-criteria (ISC-15, 16, 17, 18) cover scope, regression, privacy, and a future-compat lock — typical E2 anti-criteria density.
-->
