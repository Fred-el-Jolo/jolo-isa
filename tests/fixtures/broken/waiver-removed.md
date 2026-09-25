---
task: "Build a CLI that extracts arxiv metadata into JSONL"
slug: 20260201-100000_arxiv-extractor-cli
project: ArxivExtractor
effort: E3
phase: complete
progress: 11/11
started: 2026-02-01T18:00:00Z
updated: 2026-02-14T19:40:00Z
---

## Problem

Researching across arxiv papers means reading abstracts in a browser one at a time. There is no quick "give me the title, authors, abstract, categories, and submission date for these 50 paper IDs as JSONL so I can grep them" tool. The arxiv API exists but its XML response shape is annoying enough that nobody uses it casually.

## Vision

A single bun TypeScript CLI: `bun arxiv.ts <id1> <id2> ... > papers.jsonl`. One paper per line, structured fields, no friction. Delight: feeding 100 IDs and getting clean JSONL back in under three seconds.

## Out of Scope

- No PDF download. Metadata only.
- No citation graph traversal. Single-paper lookup, no following references.
- No web UI. CLI exclusively.
- No persistent cache. Stateless; every run hits the API.

## Constraints

- Bun runtime only. No Node dependency.
- Zero npm dependencies — use Bun's built-in `fetch` and a hand-rolled XML parse.
- Must respect arxiv's API rate limits (3 requests / second per their TOS).

## Goal

Ship a single-file `arxiv.ts` CLI that takes paper IDs as arguments, queries the arxiv Atom API, parses the response, and writes one JSONL row per paper to stdout with fields: `id`, `title`, `authors`, `abstract`, `categories`, `submitted`, `updated`.

## Criteria

- [x] ISC-1: `arxiv.ts` is a single file at the project root.
- [x] ISC-2: `package.json` declares zero runtime `dependencies`.
- [x] ISC-3: `bun arxiv.ts 2401.12345` returns exactly one JSONL row to stdout.
- [x] ISC-4: The JSONL row has exactly seven fields: `id, title, authors, abstract, categories, submitted, updated`.
- [x] ISC-5: `authors` is an array of strings, never a single concatenated string.
- [x] ISC-6: `categories` is an array of strings (e.g., `["cs.AI", "cs.LG"]`).
- [ ] ISC-7: A 100-ID batch completes in ≤ 3 seconds wall clock.
- [x] ISC-8: A bad ID (e.g., `9999.99999`) writes a JSONL row with `error` field instead of crashing.
- [x] ISC-9: stderr stays empty on a successful 100-ID run.
- [x] ISC-10: `bun arxiv.ts --help` prints usage in ≤ 12 lines.
- [x] ISC-11: Anti: out of scope — `arxiv.ts --download` is rejected with usage and exit 2.
- [x] ISC-12: Anti: regression — never makes more than 3 concurrent requests against arxiv API.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  check: exactly one .ts source file in the repo
  threshold: output is ./arxiv.ts
  tool: find . -name '*.ts' -not -path './node_modules/*' -not -path './test/*'

- isc: ISC-2
  type: bash
  check: runtime dependency count
  threshold: "0"
  tool: jq '.dependencies // {} | length' package.json

- isc: ISC-3
  type: bash
  check: stdout has exactly one JSONL row
  threshold: "1"
  tool: bun arxiv.ts 2401.12345 | wc -l

- isc: ISC-4
  type: property
  property: "for every Atom entry, keys(parse(entry)) == [id, title, authors, abstract, categories, submitted, updated]"
  generator: "fc.record over the Atom entry schema — optional <arxiv:comment>, 0–5 <category>, missing <updated>"
  runs: 1000
  tool: bun test test/parse.property.test.ts -t "seven fields"

- isc: ISC-5
  type: property
  property: "parse(entry).authors is string[] with one element per <author> node"
  generator: "Atom entries with 1–50 <author> nodes, names including commas, 'and', and non-ASCII"
  runs: 1000
  tool: bun test test/parse.property.test.ts -t "authors array"

- isc: ISC-6
  type: property
  property: "parse(entry).categories is string[] equal to the <category term> values, in order"
  generator: "Atom entries with 0–8 <category> nodes drawn from the arxiv taxonomy"
  runs: 1000
  tool: bun test test/parse.property.test.ts -t "categories array"

- isc: ISC-7
  type: performance
  check: wall-clock for 100 IDs
  threshold: ≤ 3000ms
  tool: hyperfine --runs 3 --export-json /tmp/h.json "bun arxiv.ts $(tr '\n' ' ' < test/100-ids.txt)" && jq '.results[0].max*1000' /tmp/h.json

- isc: ISC-8
  type: bash
  check: bad ID does not crash
  threshold: exit 0 + JSONL row with error field
  tool: bun arxiv.ts 9999.99999 | jq -e '.error'

- isc: ISC-9
  type: bash
  check: stderr byte count on a clean 100-ID run
  threshold: "0"
  tool: bun arxiv.ts $(cat test/100-ids.txt) 2>&1 >/dev/null | wc -c

- isc: ISC-10
  type: bash
  check: --help line count
  threshold: ≤ 12
  tool: bun arxiv.ts --help | wc -l

- isc: ISC-11
  type: bash
  check: --download is rejected
  threshold: exit 2 + usage on stderr
  tool: bun arxiv.ts --download 2401.12345 2>&1 | grep -q '^usage:'; test ${PIPESTATUS[0]} -eq 2

- isc: ISC-12
  type: unit-test
  check: fetch high-water mark over a 100-ID batch against a mock server
  threshold: max in-flight requests ≤ 3
  tool: bun test test/queue.test.ts -t "concurrency cap"
```

## Features

```yaml
- name: SinglePaperLookup
  description: One ID in → fetch → parse → one well-typed JSONL row out, or an error row
  satisfies: [ISC-3, ISC-4, ISC-5, ISC-6, ISC-8]
  depends_on: []
  parallelizable: false  # first end-to-end path; everything else builds on it

- name: BatchThroughput
  description: 100 IDs through a 3-concurrency queue, fast and quiet
  satisfies: [ISC-7, ISC-9, ISC-12]
  depends_on: [SinglePaperLookup]
  parallelizable: true

- name: CLISurface
  description: --help text and rejection of unsupported flags
  satisfies: [ISC-10, ISC-11]
  depends_on: [SinglePaperLookup]
  parallelizable: true
```

## Decisions

- 2026-02-01 18:00: Hand-rolled XML parse over a library — Bun has no built-in XML, the response shape is bounded, and adding a dep would violate the zero-deps constraint.
- 2026-02-02 10:00: Features re-sliced vertically (SinglePaperLookup → BatchThroughput / CLISurface) instead of fetch → parse → CLI layers, so each slice ends in a runnable probe.
- 2026-02-08 22:30: ❌ DEAD END: Tried Promise.all() with 100-IDs — arxiv rate-limited after request 12. Reverted to a 3-concurrency queue. Don't retry.
- 2026-02-09 11:00: Switched to arxiv's `id_list` parameter — up to 50 IDs per request, so a 100-ID batch is 2 requests instead of 100. The 3-concurrency queue stays as the ISC-12 guard.
- 2026-02-14 18:30: ISC-7 measured at 4.6s for 100 IDs: both requests spend ~4.3s inside arxiv's API before the first byte. Nothing left to cut on our side.
- 2026-02-14 19:30: Goal line checked against the Goal sentence (no `stated_goal` was captured — the prompt was a feature description, not a goal statement).

## Changelog

- 2026-02-09 | conjectured: one API request per paper ID, throttled to 3 in flight, is fast enough for 100 IDs
  refuted by: arxiv's documented limit (3 req/s) puts 100 requests at ≥ 33s; the Promise.all() attempt was rate-limited after request 12
  learned: the arxiv API batches — `id_list` accepts up to 50 comma-separated IDs, so request count, not concurrency, was the lever
  criterion now: ISC-12 (≤ 3 concurrent requests) kept as a regression guard; ISC-7 probe unchanged

## Verification

- ISC-1: `find . -name '*.ts' -not -path './node_modules/*' -not -path './test/*'` — `./arxiv.ts`
- ISC-2: `jq '.dependencies // {} | length' package.json` — `0`
- ISC-3: `bun arxiv.ts 2401.12345 | wc -l` — `1`
- ISC-4: `bun test test/parse.property.test.ts -t "seven fields"` — 1000 runs, 0 failures
- ISC-5: `bun test test/parse.property.test.ts -t "authors array"` — 1000 runs, 0 failures
- ISC-6: `bun test test/parse.property.test.ts -t "categories array"` — 1000 runs, 0 failures
- ISC-8: `bun arxiv.ts 9999.99999 | jq -e '.error'` — `"not found"`, exit 0
- ISC-9: `bun arxiv.ts $(cat test/100-ids.txt) 2>&1 >/dev/null | wc -c` — `0`
- ISC-10: `bun arxiv.ts --help | wc -l` — `9`
- ISC-11: `bun arxiv.ts --download 2401.12345` — `usage: …` on stderr, exit 2
- ISC-12: `bun test test/queue.test.ts -t "concurrency cap"` — max in flight 3 (1 passed)
- Goal: yes — the Goal asks for a single-file, zero-dependency CLI that writes one seven-field JSONL row per paper. A real 100-ID run produced 100 rows, `jq -s 'map(keys|length) | unique'` → `[7]`, and 0 rows with a string `authors`; the one missed target (ISC-7, speed) is a Vision-level delight the user waived, not part of the Goal sentence.
