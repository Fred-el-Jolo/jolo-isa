[ISA: ON — this prompt asks for work with a checkable end state]
Before any change, write the ISA for this task. Read {skill_dir}/SKILL.md first (the contract and
the numbered completion rules), then:
1. `isa new <slug> --goal "<verbatim span of the prompt>"` — creates {project_dir}/<stamp>_<slug>/ISA.md
   with frontmatter, stated_goal, asks and root filled, and binds it to this session.
2. Write Goal, Criteria (≥1 `Anti:`), Test Strategy with Write/Edit — never with shell commands.
3. `isa lint <ISA>` until clean; changes are refused until it is.
4. For behaviour/http/schema criteria, write the test and run `isa verify --red <ISA>` (it must
   fail) before building. Prove criteria with
   `isa verify <ISA> [ISC-N…]` — it runs the probes and ticks what passed. Self-attested criteria:
   `isa verify <ISA> ISC-N --attest "<evidence>"`. You never tick boxes yourself.
5. Finish with `isa close <ISA>` — it re-proves everything and closes. Your final answer quotes its summary.
The turn can't end without a bound ISA, and can't end with an unproven claim.
