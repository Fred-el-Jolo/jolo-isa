<!-- isa:spec-driven:begin -->
## ISA work

Work with several dependent steps follows one lifecycle, in every project. Pick the tier first and say it (ISA skill, References/Foundations.md):

- **E0**: a quick exchange, or a 1–3 step action whose failure is obvious: no ISA.
- **E1**: `isa new <slug> --tier E1` → write it (one level of criteria) → build → `isa close`.
- **E2–E4**: `isa spec new <slug> --tier E2` (or E3, E4) → write the spec → the user's `Spec ack` → `isa ack <spec>` → `isa new --spec <spec>` (one parent per section) → write the ISA (2, 3, 4+ levels of criteria) → `isa review <ISA>` → `isa show <ISA> --trace` → the user's `ISA ack` → `isa ack <ISA>` → build → `isa close` (it writes the plan and commits).

ISAs, specs, plans and ~/.isa are written only by `isa` commands (`isa --help`). An ack is the user's click, never yours, and no code starts before it. If the build shows the spec is wrong, `isa reopen` it and ask the user again.
<!-- isa:spec-driven:end -->
