[ISA: ON — this prompt asks for work with a checkable end state]
Before any change, write down what done means. Order: spec → ack → (plan → ack) → ISA. State the tier
in your reply first:
- E1 — the ISA first: one small change, no spec (`isa new <slug> --tier E1`, then the steps below).
- E2–E3: the spec first, {spec_dir}/YYYY-MM-DD-<slug>.md (`status: draft`, `effort:`); ask its open
  questions, `isa lint` it, then ask the user's ack (header `Spec ack`, options `Acknowledge` /
  `Request changes`; pi asks it itself when your turn ends). Until the ack, code changes and
  `isa new` wait. The ack is the go: then the ISA.
- E4–E5: the spec and its ack, then the plan (docs/plan/, same basename) and its ack (header
  `Plan ack`); then one ISA per plan step.
For the ISA, read {skill_dir}/SKILL.md first (the contract and the numbered completion rules), then:
1. `isa new <slug> --goal "<verbatim span of the prompt>"` — creates {project_dir}/<stamp>_<slug>/ISA.md
   with frontmatter, stated_goal and root filled, and binds it to this session.
2. With Write/Edit (never shell commands): `asks:` (each explicit ask, copied verbatim from the prompt),
   Goal, Criteria (≥1 `Anti:`), Test Strategy. A probe that can't be seen failing first (Anti, a
   config/doc/file kind) gets `fails-when: "<what it sees when the claim is false>"`.
3. `isa lint <ISA>` until clean; changes are refused until it is.
4. For behaviour/http/schema criteria, write the test and run `isa verify --red <ISA>` (it must
   fail) before building. Prove criteria with
   `isa verify <ISA> [ISC-N…]` — it runs the probes and ticks what passed. Self-attested criteria:
   `isa verify <ISA> ISC-N --attest "<evidence>"`. You never tick boxes yourself.
5. Finish with `isa close <ISA>` — it re-proves everything and closes. Your final answer quotes its summary.
Run `isa verify` and `isa close` with a 600000 ms Bash timeout (or in the background when the suite is
slow): the default 120 s can stop a long run halfway, leaving the ISA open. When a command prints a
`Jev:` line (Jev out of credit, over budget or down), relay it to the user word for word.
The turn can't end without a bound ISA (E2–E5 before the ack: on the spec's ack question or its open
questions instead), and can't end with an unproven claim.
Later prompts are judged again (SPEC-v2 § 12): a new task gets its own ISA (the open one is marked paused);
when Jev is unavailable after a finished ISA, put `ISA judge (model): yes|no|unsure — <reason>` in your answer.
When the user picks Continue without ISA for a later prompt, this block does not apply to that prompt: answer
with no ISA and no `ISA judge (model):` line (that line is only for a Jev outage).
