---
task: "Write an essay on why productivity advice fails founders"
slug: 20260317-203000_essay-productivity-fails-founders
project: ProductivityEssay
effort: E3
phase: execute
progress: 5/34
started: 2026-03-17T03:30:00Z
updated: 2026-03-21T15:00:00Z
---

<!-- Fictitious example. The essay topic is a teaching placeholder; any resemblance to real essays or authors is coincidental. -->

## Problem

I have a thesis about why generic productivity advice (`time-blocking`, `deep work`, `eat the frog`) lands wrong for someone running a 6-month-old startup with no team. The thesis is in my head; it isn't on the page. A draft I started a week ago reads like a list of complaints rather than an argument with a clear shape — opening hook is weak, the through-line dies in the third section, the closing punches air. Without a structural framework, the essay will keep failing the same way.

## Vision

A 1500-word essay that a first-time founder reads in eight minutes, recognizes their own situation in the second paragraph, follows a single load-bearing argument through three movements, and arrives at a conclusion that reframes their relationship to productivity advice — not "ignore it" but "ignore most of it for now, and here's how to tell which 20% applies." Delight: a reader closes the tab, opens a notes file, and writes one sentence about which productivity advice they're going to ignore for the next 90 days. They tell one friend.

## Out of Scope

- **Not a productivity-advice listicle.** No "5 productivity hacks for founders." The essay is structural critique, not new advice.
- **Not a manifesto.** No "Here's the new way." The conclusion is calibration, not replacement.
- **No founder name-checks.** No anecdotes that depend on knowing a specific founder's story; the argument has to land for a reader who's never read TechCrunch.
- **Not a Twitter thread.** Long-form, single document, lands as one continuous read.
- **Not a research paper.** Zero citations, zero footnotes; the argument's force comes from clarity, not external authority.

## Principles

- The reader's recognition in the second paragraph is the load-bearing moment. Without it, nothing else lands.
- One thesis, one through-line. Cut anything that requires the reader to hold a second argument in parallel.
- Concrete > abstract. Every claim has a concrete situation behind it; otherwise the claim reads as platitude.
- The closing must do work — name something the reader will do differently — not just summarize.
- Voice is conversational-direct. No "Here's the thing", no "It turns out". No academic hedging.

## Constraints

- 1500 words ± 100 (1400–1600 final).
- Three sections only — opening, middle, close. No subheaders.
- Reading time ≤ 8 minutes at 200wpm.
- Zero footnotes, zero citations, zero "as <famous person> says".
- No bulleted lists in the body (one allowed in the close if it earns its place; otherwise zero).
- Published as a single Markdown file with frontmatter; no embedded images, no pull quotes.

## Goal

Ship a 1400–1600-word essay in three sections that opens with a concrete first-time-founder situation the reader recognizes within 30 seconds, develops a single thesis ("most productivity advice was built for a different game"), and closes with a calibration tool the reader can apply within 24 hours — a one-question filter for which advice to keep and which to drop.

## Criteria

### Word count and structure

- [x] ISC-1: Final body word count falls between 1400 and 1600.
- [x] ISC-2: Exactly three `##` section headers, and no deeper subheaders.
- [ ] ISC-3: Each section is 350–700 words.
- [ ] ISC-4: Reading time is ≤ 8 minutes at 200 words per minute.

### Argument structure

- [x] ISC-5: Opening section ends with a one-sentence thesis statement.
- [ ] ISC-6: Middle section advances the thesis through ≥ 3 distinct concrete examples.
- [ ] ISC-7: Close names one calibration tool a reader can apply within 24 hours.
- [ ] ISC-8: Through-line test: a reader can state the thesis in ≤ 20 words after one read.

### Voice and tone

- [x] ISC-9: Zero occurrences of the listed AI-writing tics ("Here's the thing", "It turns out", …).
- [ ] ISC-10: Zero footnotes, numeric citations, or "as <person> says" formulations.
- [ ] ISC-11: Every section has one sentence ≤ 8 words and one ≥ 28 words.
- [ ] ISC-12: First-person plural ("we", "us", "our") appears at most 5 times.

### Antecedent ISCs (preconditions for the target experience)

- [x] ISC-13: Antecedent: the second paragraph opens on a situation most first-time founders recognize as theirs.
- [ ] ISC-14: Antecedent: synonym-swapping any noun or verb in the thesis visibly weakens it.
- [ ] ISC-15: Antecedent: the close's one-question filter is usable without re-reading the essay.

### Minimal-structure discipline

- [ ] ISC-16: No paragraph could move to another essay without rewriting its first sentence.
- [ ] ISC-17: Removing any sampled sentence detectably weakens the argument or rhythm.

### Anti-criteria

- [ ] ISC-18: Anti: out of scope — the essay contains no numbered list of productivity hacks.
- [ ] ISC-19: Anti: regression — no sentence runs longer than 50 words.
- [ ] ISC-20: Anti: voice — the essay names no famous founder as an authority.
- [ ] ISC-21: Anti: scope — the essay proposes no new named productivity framework or method.

### Iteration discipline

- [ ] ISC-22: At least 3 drafts exist in `drafts/` before the final.
- [ ] ISC-23: The final draft was read aloud once before publishing.
- [ ] ISC-24: At least 2 unfamiliar readers gave first-impression feedback before publishing.

### Publishing

- [ ] ISC-25: `essay.md` frontmatter holds `title`, `published_at`, `word_count`, `reading_time_min`.
- [ ] ISC-26: The platform preview renders three sections with no broken formatting.
- [ ] ISC-27: A pull-quote of ≤ 280 characters is saved in `pullquote.txt`.
- [ ] ISC-28: `cuts-on-deck.md` lists candidate cuts for a 200-words-shorter version.

### Post-publish delight probes

- [ ] ISC-29: Within 7 days, ≥ 1 reader names one piece of advice they'll drop.
- [ ] ISC-30: Within 14 days, ≥ 1 reader forwards the essay to a founder unprompted.

### Personal discipline

- [ ] ISC-31: `cuts.md` preserves at least 500 words of edited-out material.
- [ ] ISC-32: `started` and `published_at` are at least 4 days apart.
- [ ] ISC-33: A Decisions entry names the paragraph that caused the most rewriting.
- [ ] ISC-34: At least one ❌ DEAD END Decisions entry records an abandoned draft direction.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  check: total words in body (frontmatter excluded)
  threshold: 1400–1600
  tool: awk '/^---$/{c++; next} c==2' essay.md | wc -w

- isc: ISC-2
  type: bash
  check: header counts
  threshold: 3 `##` headers, 0 `###`+ headers
  tool: rg -c '^## ' essay.md; rg -c '^###' essay.md

- isc: ISC-3
  type: bash
  check: words per section
  threshold: every section 350–700
  tool: awk '/^## /{if(n)print n; n=0; next} {n+=NF} END{print n}' essay.md

- isc: ISC-4
  type: bash
  check: body words / 200
  threshold: ≤ 8.0
  tool: echo "scale=1; $(awk '/^---$/{c++; next} c==2' essay.md | wc -w) / 200" | bc

- isc: ISC-5
  type: manual
  check: last sentence of the opening section is the thesis
  threshold: author and one reader both point to the same sentence
  tool: read the opening section; ask one reader "which sentence is the claim?"

- isc: ISC-6
  type: manual
  check: count of distinct concrete situations in the middle section, none needing outside knowledge
  threshold: ≥ 3
  tool: read the middle section and list each example in one line

- isc: ISC-7
  type: manual
  check: the close ends on one named, applicable tool
  threshold: the tool can be written as one question
  tool: read the close section

- isc: ISC-8
  type: manual
  check: 3 unfamiliar readers each summarize the thesis in ≤ 20 words
  threshold: ≥ 2/3 summaries agree within ±10 words
  tool: send essay to 3 reader-test slots, collect 1-sentence summaries

- isc: ISC-9
  type: bash
  check: AI-writing tics
  threshold: zero matches (rg exits 1)
  tool: rg -i "here's the thing|it turns out|not just .* — it's" essay.md

- isc: ISC-10
  type: bash
  check: footnotes, numeric citations, appeal-to-person phrasing
  threshold: zero matches (rg exits 1)
  tool: rg '\[\^?\d+\]|\bas [A-Z][a-z]+ (says|said|wrote)' essay.md

- isc: ISC-11
  type: bash
  check: min and max sentence length per section
  threshold: every section min ≤ 8 and max ≥ 28
  tool: python3 scripts/sentence-lengths.py essay.md --per-section

- isc: ISC-12
  type: bash
  check: first-person plural count
  threshold: ≤ 5
  tool: rg -o -w -i 'we|us|our' essay.md | wc -l

- isc: ISC-13
  type: manual
  check: 5 unfamiliar founder readers answer "is this you?" about paragraph two
  threshold: ≥ 3/5 say yes
  tool: 5-person reader test, post-read 1-question survey

- isc: ISC-14
  type: manual
  check: 3 synonym-swapped paraphrases of the thesis, read side by side with the original
  threshold: each paraphrase loses meaning a reader can name
  tool: write the 3 paraphrases, then hand all 4 to one reader

- isc: ISC-15
  type: manual
  check: 5 readers given only the close section say what to do next
  threshold: ≥ 4/5 describe the filter correctly
  tool: close-only reader test

- isc: ISC-16
  type: manual
  check: paragraph-portability review
  threshold: every paragraph has a phrase anchoring it to this essay's argument
  tool: read each paragraph in isolation

- isc: ISC-17
  type: manual
  check: read-aloud removal test on 3 randomly chosen sentences
  threshold: each removal is noticed as a loss
  tool: shuf -n 3 on the sentence list, read aloud with and without each

- isc: ISC-18
  type: bash
  check: numbered list items
  threshold: zero matches (rg exits 1)
  tool: rg '^\d+\. ' essay.md

- isc: ISC-19
  type: bash
  check: longest sentence
  threshold: ≤ 50 words
  tool: python3 scripts/sentence-lengths.py essay.md --max

- isc: ISC-20
  type: bash
  check: famous-founder names
  threshold: zero matches (rg exits 1)
  tool: rg -i 'paul graham|sam altman|peter thiel|naval|elon|jeff bezos|steve jobs' essay.md

- isc: ISC-21
  type: bash
  check: framework-introduction phrasing
  threshold: zero matches (rg exits 1)
  tool: rg -i 'introducing the|the [A-Z][a-z]+ (method|framework|system)\b' essay.md

- isc: ISC-22
  type: bash
  check: draft count
  threshold: ≥ 3
  tool: ls drafts/ | wc -l

- isc: ISC-23
  type: bash
  check: read-aloud Decisions row
  threshold: ≥ 1 match
  tool: rg -c -i 'read.aloud' ISA.md

- isc: ISC-24
  type: bash
  check: Decisions rows citing a reader before publish
  threshold: ≥ 2 distinct reader initials
  tool: rg -o 'reader [A-Z]{2}' ISA.md | sort -u | wc -l

- isc: ISC-25
  type: bash
  check: required frontmatter keys
  threshold: 4 of 4 present
  tool: awk '/^---$/{c++; next} c==1' essay.md | rg -c '^(title|published_at|word_count|reading_time_min):'

- isc: ISC-26
  type: screenshot
  check: platform preview of the final draft
  threshold: three section headers visible, no raw markdown, no broken links
  tool: screenshot of the platform preview, viewed

- isc: ISC-27
  type: bash
  check: pull-quote length
  threshold: 1–280 characters
  tool: test -s pullquote.txt && test $(wc -m < pullquote.txt) -le 280

- isc: ISC-28
  type: bash
  check: candidate-cut list exists and is non-empty
  threshold: ≥ 1 list item
  tool: rg -c '^- ' cuts-on-deck.md

- isc: ISC-29
  type: manual
  check: ≥ 1 reader names a specific piece of advice they're dropping
  threshold: 1 within 7 days
  tool: monitor replies, comments, DMs for 7 days

- isc: ISC-30
  type: manual
  check: unprompted forward to another founder
  threshold: ≥ 1 within 14 days
  tool: referrer report from web analytics, or a direct message saying so

- isc: ISC-31
  type: bash
  check: words of preserved cuts
  threshold: ≥ 500
  tool: wc -w < cuts.md

- isc: ISC-32
  type: bash
  check: days between started and published_at
  threshold: ≥ 4
  tool: python3 -c "import yaml,sys,datetime as d; f=yaml.safe_load(open('essay.md').read().split('---')[1]); print((f['published_at']-f['started']).days)"

- isc: ISC-33
  type: bash
  check: most-rewritten-paragraph Decisions row
  threshold: ≥ 1 match
  tool: rg -c -i 'most rewriting|most rewritten' ISA.md

- isc: ISC-34
  type: bash
  check: dead-end Decisions rows
  threshold: ≥ 1
  tool: rg -c 'DEAD END' ISA.md
```

## Features

```yaml
- name: OpenerSituation
  description: Concrete first-time-founder situation that reader recognizes in 30s
  satisfies: [ISC-3, ISC-5, ISC-13, ISC-16]
  depends_on: []
  parallelizable: false  # opener gates everything else

- name: MiddleArgument
  description: Three distinct concrete examples advancing the single thesis
  satisfies: [ISC-3, ISC-6, ISC-11, ISC-14, ISC-16]
  depends_on: [OpenerSituation]
  parallelizable: false  # the through-line is sequential

- name: CalibrationClose
  description: One-question filter the reader can apply within 24h
  satisfies: [ISC-3, ISC-7, ISC-15, ISC-30]
  depends_on: [MiddleArgument]
  parallelizable: false

- name: VoicePass
  description: AI-writing-pattern scrub + sentence-length variance + first-person discipline
  satisfies: [ISC-9, ISC-10, ISC-11, ISC-12, ISC-19, ISC-20]
  depends_on: [CalibrationClose]
  parallelizable: true  # cosmetic pass on full draft

- name: ReaderFeedback
  description: Two unfamiliar reader passes; second-paragraph recognition probe
  satisfies: [ISC-8, ISC-13, ISC-15, ISC-23, ISC-24]
  depends_on: [VoicePass]
  parallelizable: true  # readers are independent
```

## Decisions

- 2026-03-17 03:30: Three sections, no subheaders, locked. The form constraint forces the through-line to be load-bearing.
- 2026-03-18 11:00: ❌ DEAD END: Tried opening with a quote from a public figure. Felt borrowed; reader's recognition stayed external. Reverted to a concrete-situation opener. Don't retry.
- 2026-03-19 22:30: refined: ISC-13 sharpened from "readers find the opening relatable" to "≥ 3/5 founder readers mark 'yes, that's me' to the second paragraph specifically." The first phrasing was unfalsifiable; the second isolates the load-bearing moment.
- 2026-03-20 09:00: ❌ DEAD END: Tried structuring the middle as five examples instead of three. The fifth and fourth examples started repeating each other; cut to three with one extended. Don't retry.
- 2026-03-20 14:30: refined: ISC-7 sharpened from "close offers a takeaway" to "close names a specific calibration tool the reader can apply within 24 hours." Vague closes are why most essays of this shape fail to land.
- 2026-03-21 09:00: refined: ISC-12 added (≤ 5 first-person plural) after a draft read like a "we should all" sermon. The essay is observation, not exhortation.

<!--
E3 art ISA. Required sections: Problem, Vision, Out of Scope, Constraints, Goal, Criteria, Features, Test Strategy.
Optional Principles included because the essay is experiential and the principles do real work in the writing pass.
Three Antecedent ISCs (ISC-13, 14, 15) carry the experiential-goal contract: they name the preconditions that reliably produce the target reader experience. Without them, ISC-29 and ISC-30 (post-publish reception) would be unfalsifiable hopes rather than testable claims. Anti-criteria (ISC-18, 19, 20, 21) cover scope, regression, voice, and a future-essay-drift trap. The Decisions section shows two ❌ DEAD ENDs and three refinements — typical density for a first draft of an essay that knows its shape but is still finding its load-bearing moments.
-->
