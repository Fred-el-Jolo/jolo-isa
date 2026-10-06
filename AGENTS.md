# ISA skill — standalone export

This folder is a port of the **ISA (Ideal State Artifact) skill** out of LifeOS, the personal AI setup it was built in, so it runs on a fresh Claude Code (and pi) install with none of LifeOS present. Working here means refining the export.

## Objective

ISA makes multi-step work state what done means before it starts, and prove it as it goes. It rests on three foundations, defined once in `skill/ISA/References/Foundations.md`:

- **FOUNDATION_0 — the entities:** TASK, TASK ISA, Tier, ISC, Probe, SPEC, PLAN, Ack, Session, Gate, Lifecycle. Nothing else.
- **FOUNDATION_1 — the decision tree:** no ISA → nothing; E1 → ISA → build; E2–E4 → spec → ack → ISA → ack → build. Nothing bypasses it.
- **FOUNDATION_2 — `isa` commands are the only writers** of ISAs, specs, plans and `~/.isa`. A Write, an Edit or a script on them is refused.

A skill loads only when the model decides to, so hooks enforce it in every session: Claude Code hooks (user scope) and a pi extension call one engine. Design and acceptance: `docs/spec/2026-10-06-gate-close-issues.md`.

## Layout

```
├── AGENTS.md / CLAUDE.md           ← this file (CLAUDE.md includes it)
├── skill/ISA/                      ← installed to ~/.claude/skills/ISA/
│   ├── SKILL.md                    ← writing a good ISA; the lifecycle in short
│   ├── References/
│   │   ├── Foundations.md          ← the entities, the lifecycle, one command per action (wins on contradiction)
│   │   └── SpecDriven.md           ← writing a spec: template, rules, red flags, the ack and reopen
│   └── Examples/                   ← one ISA per tier (E1–E4), their specs in specs/; all lint ok
├── skill/global-rules.md           ← the block install.py puts in ~/.claude/CLAUDE.md and ~/.pi/agent/AGENTS.md
├── runtime/                        ← the engine, installed to ~/.local/share/isa/runtime (Python stdlib only)
│   ├── bin/isa                     ← CLI launcher, linked to ~/.local/bin/isa
│   └── isa/
│       ├── cli.py                  ← `isa <command>` (COMMANDS) and the hook adapters (Claude Code, pi)
│       ├── commands.py             ← every writing command: spec new, new, write, drop, decide, ack, reopen, refine, verify, attest, answer, close
│       ├── engine.py               ← the hooks: the gate, the lifecycle stages, the perimeter, Stop
│       ├── isafile.py              ← the TASK ISA: sections, the criteria tree, probes, Verification lines, the ack hash
│       ├── spec.py                 ← SPEC and PLAN: template, lint, hash, the ack clicks, `isa diff`, the plan render
│       ├── lint.py                 ← the ISA rules per tier (draft and close)
│       ├── doc.py                  ← frontmatter and `## ` sections (comments blanked outside fences only)
│       ├── classify.py             ← read / isa-cmd / write / unknown / guarded, for tool calls and Bash
│       ├── gitops.py               ← the commits: the spec after its ack, the work and the plan after a close
│       ├── advice.py               ← Jev's advice at verify and close (printed, never blocking)
│       ├── state.py, config.py, logs.py, status.py, skills.py, jev.py, jev/, yamlish.py
│       └── protocol.md             ← the ON block injected when a session turns ON
├── adapters/pi/isa.ts              ← pi extension → `isa hook pi` (installed to ~/.pi/agent/extensions/)
├── adapters/claude-statusline/     ← Claude Code statusLine (Node): renders `isa status --json`; opt-in
├── install.py                      ← install / --uninstall / --dry-run for both harnesses
├── tests/                          ← test_foundations (the foundations end to end), test_install, test_bash_classifier, test_yamlish
├── tools/lint_isa.py               ← lints the examples with the runtime's rules
├── future/                         ← design notes for the future tasks (memory, status line, Jev)
└── docs/spec/                      ← this repo's own specs
```

## Install

```bash
python3 install.py --dry-run    # see what changes
python3 install.py              # install / update (idempotent)
python3 install.py --statusline # also wire the ISA statusLine (keeps an existing one)
python3 install.py --uninstall  # remove everything except ~/.isa (and restore the previous statusLine)
```

Needs `python3` (standard library only) and, for pi, the pi agent at `~/.pi/agent`. The installer does the following:

- copies the runtime and the skill, and links `~/.local/bin/isa`;
- merges the hook entries and permissions into `~/.claude/settings.json`, keeping every other entry and backing the file up first;
- copies the pi extension;
- writes the rule block of `skill/global-rules.md` into `~/.claude/CLAUDE.md` and `~/.pi/agent/AGENTS.md`, between markers, leaving your text around it untouched;
- moves a `~/.isa` from before the foundations aside, once (`~/.isa.legacy-<time>/`).

## How it is enforced

One engine (`runtime/isa/engine.py`), two thin adapters. Every decision is deterministic code except the gate, which asks Jev (`jev` CLI, jev-kit) under a 1.5 s deadline.

- **The gate.** Each prompt is judged once:
  - with no ISA or spec open, "is this a TASK?" (preset `isa-gate`): several dependent steps where a mistake could pass unnoticed, versus a quick exchange or a 1–3 step action that fails visibly. Jev ≥ `jev_gate` (0.8) turns the session ON; below `jev_quiet` (0.3) the prompt goes on; anything in between goes to the user (*Continue without ISA* / *Enable ISA*), and Stop refuses a turn that skips that question, even if an ISA was bound meanwhile;
  - with an ISA or spec open, "continuation or new task?" (`isa-continuation`);
  - with Jev unavailable, the model judges with `ISA judge (model): yes|no|unsure — <reason>`;
  - Continue grants a pass for the rest of that prompt.
- **The lifecycle.** While ON, the stage comes from the bound ISA or spec and its acks: TRIAGE, SPEC DRAFT, SPEC ACKED, ISA DRAFT, ISA REFINE, BUILD, CLOSED. A project change (`write` or `unknown`) goes through in BUILD only, and the refusal names the stage and the next command.
- **The perimeter (FOUNDATION_2).** In every mode, a `guarded` call is refused: any Write or Edit of an ISA, a spec, a plan or anything under `~/.isa`, and any shell command that writes to them or runs a script on them. Reading is free.
- **Stop** refuses once per prompt when the turn ends with the stage asking for something:
  - nothing bound while ON;
  - a spec draft that was neither asked for its ack nor has open questions;
  - an ISA not acked;
  - a spec reopened;
  - a new task not bound.
  The second time, the turn ends with a warning.
- **The commands own the state.** `isa verify` runs probes from the ISA's root and writes run lines into the ISA's Verification. `isa close` re-proves everything, writes the plan (E2+) and commits. `isa ack` writes an ack only on the user's recorded click. No hook writes an ISA; no hook runs a probe.
- **Failure policy:** a hook that crashes fails open with a visible message (and a debug row with DEBUG on). pi's extension catches its own errors, since pi blocks a tool when a handler throws.
- **`ISA_MODE=off|on`** is the user's override (off: every hook silent; on: ON from the first prompt, no judge).

**State.** `~/.isa` holds:

- `<project>/<YYYYMMDD-HHMMSS>_<slug>/ISA.md`, one folder per TASK ISA;
- `<project>/acks.jsonl`, the user's clicks;
- `config.json`;
- `_state/sessions/<harness>-<id>.json` (mode, the bound ISA or spec, the last 20 prompts for the verbatim checks).

With DEBUG on (`ISA_DEBUG=1`, or `"debug": true` in config.json), the hooks and commands also write `_state/logs/YYYY-MM-DD.jsonl`, read with `isa log` and pruned with `isa purge-logs`. With DEBUG off nothing else is written, and the text the model gets is the same. Specs and plans live in `<cwd>/docs/` and are committed in a git repo; TASK ISAs never are.

## Issues

- **The new engine is installed after the foundations ISA closes.** The build ran under the old engine, whose `isa close` it needs. Right after the close: `python3 install.py`. That moves the old `~/.isa` aside to `~/.isa.legacy-<time>/`, for the user to delete. It also leaves `~/.isa.after-move-20261007` (what the hooks wrote during the 2026-10-07 test incident, logged in the foundations ISA), to delete.
- **The old live-flow results worktree** (`tests/evals/results`, branch `eval-results`) has no test left that writes to it: `git worktree remove tests/evals/results` once it is no longer wanted.
- **This repo's spec lives in the old layout**, `docs/spec/2026-10-06-gate-close-issues.md`, which the new engine doesn't read as a spec. The next spec here starts at `docs/YYYY-MM-DD-<slug>-01-spec.md`.
- **A new task mid-session leaves the open ISA open:** Q2 asks for a new ISA but no longer labels the old one paused. `isa ls` shows it as open.

## Future tasks

- **Parallel children (subagents).** `parallel: true` on a child is reserved and refused for now. Later, a parallel child runs alongside its parallel siblings while the others keep their order.
- **Memory (Future A).** Learn from closed plans and offer the learnings when a new ISA is written, with the user approving each item. It includes the `[arch]` tag: a Decision row marked as a convention other tasks must follow. See `future/MEMORY.md`.
- **The status line (Future B).** The renderer is built (`adapters/claude-statusline/`). Showing the criteria tree's levels, and a pi display, are open. See `future/STATUSLINE.md`.
- **Jev judgments (Future D)** in place of more of the model's self-grading. See `future/JEV.md`.

## Working rules for this folder

- What installs: `skill/ISA/`, `skill/global-rules.md` (the block), `runtime/`, `adapters/pi/isa.ts`, and with `--statusline`, `adapters/claude-statusline/`.
- Before installing, run:
  - `python3 -m unittest tests.test_foundations tests.test_install tests.test_bash_classifier`;
  - `node --test adapters/pi/test/extension.test.ts adapters/claude-statusline/test/renderer.test.ts`;
  - with PyYAML on `PYTHONPATH`, also `tests/test_yamlish.py`.
  No test calls a model or the real `jev`, and no installer test touches the real `~/.isa`, `~/.claude/CLAUDE.md` or `~/.pi/agent/AGENTS.md` (every `install.py` call passes temp paths).
- Tests prove the foundations first. A test of a removed path is deleted, not rewritten.
- Keep `runtime/` standard-library only (`python3 tests/check_stdlib.py runtime/`), and every file under 50 KB.
- Keep the examples linting: `python3 tools/lint_isa.py skill/ISA/Examples/*.md skill/ISA/Examples/specs/*.md`.
- Keep it free of LifeOS: no `LIFEOS/` paths, no `localhost:31337`, no personal data. Check with `rg -n -i 'lifeos|31337|MEMORY/WORK|\btelos\b|\bpulse\b' skill/` (zero hits). Provenance lives only in this file.
- When `SKILL.md` and `Foundations.md` disagree, `Foundations.md` wins; fix both on purpose.

## Source provenance

Exported 2026-09-22 from a LifeOS 7.1.1 install (skill `ISA` v1.0.13, `IsaFormat.md` v1.5.19, Algorithm v8.4.0). Rebuilt on the three foundations on 2026-10-07: the project ISA, ephemeral slices, hierarchies, Features, plan steps, done marks, the evidence ledger and the five workflows were removed. The history is in git.
