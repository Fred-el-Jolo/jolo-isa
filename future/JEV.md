# Future D — TypeSafe / Jev judgments for the ISA skill

> **Status: analysis only, not built.** The Jev wrapper will be built in a separate repo and session. This file is the handoff: what to build, where it plugs into the skill, and what must stay in code. Written 2026-09-25 from the live TypeSafe docs (jev-1.13).

## Why Jev here

The ISA skill asks the model to **grade its own work** in many places: is this criterion atomic, does this evidence really close it, did the user really waive this. Jev (TypeSafe's System One model) can answer these questions from outside the model. It gives a separate, calibrated second opinion that behaves the same every session. It can also run where the main model isn't involved at all: in hooks, a status line, and the future memory layer.

- Jev returns typed answers only: **Choice** (one of N options, with probabilities and confidence), **Score** (a position on ordered levels) and **Noul** (the probability that something is true). It does not generate text.
- According to the docs, most calls take about 100 ms. Input costs $0.042 per million tokens, and output is free. Each call can send up to 32k tokens of state plus the longest question (64k in total per request).
- Jev is **not** a replacement for the agent's LLM. It sits inside code as a decision step.

## Integration shape

The skill is prompts-only, and Jev can only be called from code. Each opportunity therefore needs one of three things:

| Mechanism | Used for |
|-----------|----------|
| A small `bun` tool the skill calls, e.g. `skill/ISA/Tools/<Name>.ts`, returning JSON | Checks inside workflows (Scaffold, CheckCompleteness) |
| A Claude Code hook (PreToolUse / UserPromptSubmit / PostToolUse) | Enforcement, and nudges when the model isn't asking itself |
| The future memory layer / status line (Future A / B) | Capture, reranking, "which ISA is active" |

SDK: `@typesafe-ai/sdk` (JavaScript/TypeScript), endpoint `POST /v1/systemone`, key in `TYPESAFE_API_KEY`. Pin a versioned model ID (e.g. `jev-1.13.0`) once thresholds are tuned; aliases can change under you.

**Advisory vs enforcing.** Only the hook that blocks an edit (#3) enforces anything. Everything else injects a signal the model can ignore. The [skill-suggestion cookbook](https://docs.typesafe.ai/cookbooks/skill_suggestion.md) shows the shape: add one line to the context and let the agent decide.

## Best fits, ranked

### 1. Evidence check at close — CheckCompleteness (close)

- **Replaces:** the model deciding its own evidence proves the claim.
- **State:** `{ criterion, threshold, evidence }` for each Verification line.
- **Question:** **Choice** `supports` / `contradicts` / `says_nothing`, with each option defined in the criteria.
- **Code keeps:** numeric thresholds (e.g. "p95 = 182 ms < 200 ms"), which are compared in code because Jev is weak at arithmetic. Code also decides what to do with the answer: accept when confidence is high, otherwise flag it to the user.
- **Why first:** it maps one-to-one onto the [citation-check cookbook](https://docs.typesafe.ai/cookbooks/citation_check.md). It protects the one thing the ISA exists for, without the builder grading itself (IsaLoop rule 11).

### 2. Capturing the stated goal verbatim — Scaffold Step 3a

- **Replaces:** the model *retyping* the user's sentence "byte-for-byte", which it can quietly paraphrase.
- **Code:** splits the prompt into sentences/clauses. This is the candidate list, so check that it covers the whole prompt.
- **Questions:** **Choice** "which sentence states the goal?" (+ `none`); **Choice** for which of the 4 signals applies (+ `none`); **Noul** "does it carry propositional content?".
- **Code keeps:** the "under 6 tokens" rule, because the docs say Jev can't count. Code also *copies* the chosen span, so verbatim is guaranteed.
- **Pattern:** "select instead of generate" ([value-extraction cookbook](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook.md)).

### 3. "Only the user can waive" — PreToolUse hook on ISA edits

- **Replaces:** a rule the model is trusted to follow (`Workflows/Append.md` § waived).
- **Trigger:** an Edit/Write to an `ISA.md` that adds a `waived: ISC-N` line.
- **State:** `{ last_user_message, isc_id, isc_text }`.
- **Question:** **Noul** "Did the user explicitly authorize waiving `isc_id`?" A low probability blocks the edit.
- **Extension:** the same guard could cover new `[DROPPED]` tombstones, i.e. dropping a criterion to make the ISA pass.

### 4. Mid-run messages and continuation — UserPromptSubmit hook

- **Replaces:** the model remembering to ask itself (SKILL.md § Continuation vs new task; IsaLoop § Standing questions) and LifeOS's old tool-call counters.
- **Questions:**
  - **Choice** over the open ISAs (each as `task` + goal line) + `new task` + `no ISA needed`.
  - **Choice** `revises goal` / `adds criterion` / `kills criterion` / `no change`, against the active ISA's Goal and Criteria.
- **Output:** one advisory line injected into context, e.g. "This looks like a continuation of <slug>; it may kill ISC-7."
- **Bonus:** it answers the status line's "which ISA is active?" question (Future B).

### 4b. Does this prompt need an ISA? — UserPromptSubmit hook (stand-in built)

- **Replaces:** `runtime/isa/fit.py`, a keyword/length heuristic that scores each prompt against the statement in `runtime/isa/fit.md` (strong / maybe / none + reasons). It exists so read-only work — reviews, audits, investigations, comparisons, plans — gets structured by an ISA even though the mutation gate never fires for it.
- **State:** `{ prompt, fit_statement (fit.md), bound_isa_summary }`.
- **Question:** **Choice** `needs_isa` / `continues_bound_isa` / `no_isa` with each option defined from fit.md; plus a **Noul** "is the outcome something the user will rely on?".
- **Code keeps:** the small-talk / slash-command short-circuit and the output wording; callers use `fit.score()` / `fit.advice()`, so the swap is local.
- **Why a stand-in first:** the heuristic is soft by design (context only, never a deny or Stop block). A model judgment is what would make it safe to enforce.

### 5. Splitting Test and granularity — CheckCompleteness Step 5

- **Replaces:** keyword rules ("contains *and* / *all* → split"). "Black and white theme" contains *and* but is one claim.
- **For each leaf ISC:** one **Noul** per test: joins two independently verifiable things? contains a scope word that needs enumerating? crosses UI/API/data?
- **For each Test Strategy entry:** **Noul** "Would running `tool` and comparing the result to `threshold` give yes/no with no judgment?"
- **Batching:** send all questions over the same state in one call ([parallel questions cookbook](https://docs.typesafe.ai/cookbooks/parallel_questions.md)). An E4 ISA with ~70 ISCs × 4 questions fits in one call.

### 6. Blast-radius classification — IsaFormat § Blast-radius probe strictness

- **Replaces:** the model noticing that an ISC touches something dangerous.
- **For each ISC:** one **Noul** per surface (secrets, auth, personal data, money, public push, prod deploy). Use one Noul per label, because several can apply at once.
- **Code enforces:** "high-blast ISC → deterministic probe type (`bash` / `unit-test` / `property`)".

### 7. "Is the goal experiential?" — Scaffold Step 8

- **Noul** over Goal + Vision. The answer decides whether an `Antecedent:` criterion is mandatory, which is a gate, so it should get the same answer every time.

### 8. Picking the tier — SKILL.md § Picking the tier

- [Composite scoring](https://docs.typesafe.ai/patterns/composite-scoring.md): one **Score** each for blast radius, breadth, drift risk and duration. Code maps them to E1–E5 with weights you set.
- **Result:** the same task gets the same tier across sessions, and you can retune the weights without calling Jev again.

## Worth trying, but weaker

- **Frame-drift / the `Goal:` line** (CheckCompleteness 5c): **Choice** `delivers the intent` / `delivers the surface only` / `doesn't deliver`, run next to the model's own Goal line. This is multi-hop reasoning, which the docs list as a weak spot. Use it as an alarm when the two disagree, never as the gate itself. It could also run at articulation: "does the ISC set cover the goal's intent?".
- **Ambiguity check** (Scaffold 3.5): **Noul** "does this request support ≥2 readings that would lead to materially different builds?". It helps because the model that wants to start building is the one deciding whether to ask.
- **Coverage gate** (CheckCompleteness 5): Jev can't *list* subsystems, because that is generating text. What it can do: for each Goal/Vision sentence, a **Choice** "which ISC covers this?" (+ `none`). A confident `none` is a gap.
- **Anchoring plausibility**: **Noul** "does ISC-N actually serve the stated goal / its named sub-claim?". It catches an ISC wearing a made-up `derived:` anchor.
- **Artifact presence** (CheckCompleteness 5b, E4+): **Noul** for each (ISC, candidate section) pair, "does this section contain the surface the ISC claims?".
- **`proceed` override** (Scaffold 3.5): the exact-match rule is deliberately fail-closed, so keep it. A **Choice** `answered` / `accepted defaults` / `mixed` could handle near-misses such as French ("vas-y"), but Jev is English-first, so test that before relying on it.
- **Late-ISA nudge**: **Noul** "does the work described need a written definition of done?", instead of a tool-call counter.
- **Agent/research results**: **Noul** "does this result contain a fact or constraint the ISA's criteria don't reflect?". This is limited by how much state fits in one call.

## Future A (memory) — a natural home

- **Capture:** a **Choice** for the learning type (`gotcha` / `constraint` / `dead-end` / `pattern` / `preference` / `not reusable`), plus a **Noul** asking the old `[arch]` test: "does this bind *other* tasks?".
- **Reuse at scaffold:** code retrieves candidates by grep, BM25 or project tag. Jev reranks them with a relevance **Score** per (prompt, learning) pair plus an "applies at all?" **Noul** ([rerank cookbook](https://docs.typesafe.ai/cookbooks/rerank_typesafe.md)). The user approves the top few.

## Keep in code (Jev would be worse)

Reconcile merging and dedupe, ID stability, progress counting, section order and presence, Changelog 4-part validation, frontmatter, token counts, dates, numeric thresholds, and status-line rendering. The docs name counting, arithmetic and date comparison as Jev's weak spots, and they say to keep anything computable in code.

## Risks to weigh

- **Privacy.** Every call sends ISA text to TypeSafe's API. The docs say customer data isn't used for training, but zero data retention is enterprise-only. For bky ISAs (a psychologist app), keep Jev off anything with client details, or filter them out before the call.
- **Literal reading.** Jev "answers the question you wrote, not the one you meant". Write boundary cases into each question's criteria, and test on real ISAs.
- **Language.** English is the primary training language. Test French prompts separately and watch confidence.
- **State size and distractors.** Accuracy drops when state carries irrelevant detail. Send only the fields each question needs (for one criterion, its ISC and its evidence, not the whole ISA).
- **Thresholds.** Every confidence cut-off in the cookbooks is an example. Tune yours on real ISAs, and scale them with risk (a blocking hook needs a stricter one than a nudge).

## Suggested build order

1. **#1 Evidence check.** One `Tools/CheckEvidence.ts`, wired into CheckCompleteness at close. Smallest, highest value, cookbook exists.
2. **#2 Verbatim goal selection.** One `Tools/SelectGoal.ts`, wired into Scaffold Step 3a.
3. **#3 Waiver hook.** A PreToolUse hook. This is the first thing that actually enforces a rule.
4. Then #4 (UserPromptSubmit hook), which the status line (Future B) can reuse.

## Sources (live docs, read 2026-09-25)

[Index](https://docs.typesafe.ai/llms.txt) · [How to build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md) · [Jev with coding agents](https://docs.typesafe.ai/introduction/coding-agents.md) · [Primitives](https://docs.typesafe.ai/primitives.md) · [Confidence](https://docs.typesafe.ai/confidence.md) · [Models](https://docs.typesafe.ai/models.md) · [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md) · [Citation check](https://docs.typesafe.ai/cookbooks/citation_check.md) · [Skill suggestion](https://docs.typesafe.ai/cookbooks/skill_suggestion.md) · [Composite scoring](https://docs.typesafe.ai/patterns/composite-scoring.md) · [Value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook.md)
