<!-- isa:spec-driven:begin -->
## Spec-driven work

Work goes spec → (plan) → ISA → code, in every project. Pick the work tier first (E1–E5, ISA skill § Picking the tier) and say it.

- **E1**: no spec. ISA only.
- **E2–E3**: write `docs/spec/YYYY-MM-DD-<slug>.md` at the project root (template: ISA skill, References/SpecDriven.md). Ask the user to acknowledge it. Then implement it with ISAs linked to its sections (`isa new --spec docs/spec/…#S<n>`).
- **E4–E5**: check the outline with the user, write the spec, ack. Then `docs/plan/YYYY-MM-DD-<slug>.md` (same basename): ISA-sized steps, each one future ISA. Ack the plan. Then one ISA per step, created when the step starts (`isa new --plan …#P<n>`).

Writing rules and red flags: ISA skill, References/SpecDriven.md. In a git repo, commit the spec (and the plan) right after its ack, that file only.

No ISA before the ack: the ISA depends on the spec. An acknowledgement is the user's explicit go for exactly what it covers. Never acknowledge on the user's behalf, and never start code before it. If the build shows the spec is wrong, edit the spec and ask again; don't let the ISA drift from it. Specs, plans and the root `ISA.md` are committed in a git repo. Task ISAs live in `~/.isa` and are not.
<!-- isa:spec-driven:end -->
