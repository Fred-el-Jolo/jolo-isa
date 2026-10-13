# ISA statusline

Shows the ISA bound to the current Claude Code session in the statusLine,
on one row: the tier first, then progress, the lifecycle stage, the current
ISC and the task. Nothing to keep in sync. The ISA hooks already bind one
`ISA.md` per session, and this only reads it.

```
E3 - ●●●●●○○○○○○○○○○ 5/15 · BUILD · ISC-3.4.2 · Rebuild progress-outline as the ISA status line
```

Compact (under 70 columns, or `mode: "compact"`):

```
E3 - 5/15 BUILD ISC-3.4.2
```

- **The stage**, not the ISA's phase, without the `ISA ` prefix: DRAFT,
  REFINE, BUILD, CLOSED.
- **The current ISC** is the first open leaf in file order, by id only:
  titles never fit. With every ISC ticked but the ISA not closed, it reads
  `all verified`; once CLOSED, there is none.
- **Only a spec bound** (SPEC DRAFT, SPEC ACKED):
  `E3 - SPEC DRAFT · 2026-10-13-foo-01-spec.md`.
- **Nothing bound** prints nothing.

The row is cut with `…` at the terminal width; the task is dropped when
fewer than four columns are left for it.

## Opening the file: `isa open`

To read or edit the spec or the ISA the line is about (before an ack, say),
run `isa open` in a terminal in the project. It opens the session's spec
during SPEC DRAFT and SPEC ACKED, and its ISA after that; `isa open spec` or
`isa open isa` picks one, and `--print` prints the path instead. The editor
is `$ISA_EDITOR`, `$VISUAL`, `$EDITOR`, else nvim. Your edit to an acked file
needs a new ack, like any other change. The model never runs `isa open`: it
is refused from a tool call. The session is `--session ID`, else the one in
the environment, else this project's most recent one.

## How it works

```
Claude Code statusLine ──stdin {session_id}──► harness.ts render
                                                   │
                                  isa status --json --session <id>   (runtime/isa/status.py)
                                                   │  reads ~/.isa/_state/sessions/claude-<id>.json → bound ISA.md or spec
                                                   ▼
                                  { stage, spec, task, effort, progress, iscs[] }
                                                   │
                                             renderer.ts ──► stdout
```

- **The runtime owns the data.** `isa status` finds the bound ISA through the
  engine's own session state and parses it with the same helpers `isa lint`
  uses (`isafile.parse`, `isafile.leaves`, `isafile.progress`). The ISC list is exactly the set
  `progress` counts: leaves only, with no dropped or waived ISCs.
- **This adapter only renders it.** It has no hook and no state file, and it
  never writes anything. Any failure prints nothing and exits 0.
- **The current ISC is the first open one.** An ISA has no in-progress
  marker, so the stage says what is happening and the first open leaf, in
  file order, is what comes next.
- Takes about 35 ms per refresh (one Python start), so there is no cache.

| File | Role |
|------|------|
| `harness.ts` | statusLine entry point (`node harness.ts render`) |
| `isa.ts` | finds the `isa` launcher, calls `isa status --json` |
| `renderer.ts` | pure `renderStatusLine(view, columns, mode, color)` |
| `types.ts` | `IsaView`, which mirrors the `isa status` JSON |
| `scripts/statusline-wrapper.cjs` | runs the other statusLine first, then the ISA rows below it |

## Install

From the repo root:

```bash
python3 install.py --statusline   # copies this folder to ~/.local/share/isa/statusline and wires settings.json
python3 install.py --uninstall    # restores the previous statusLine (and removes everything else ISA)
```

`install.py` is the only writer of `~/.claude/settings.json` (backed up first). An
existing statusLine command (e.g. `ccstatusline`) is kept: it is remembered in
`_isaInnerCommand`, run by `scripts/statusline-wrapper.cjs`, and printed above
the ISA rows; re-running never nests wrappers, and `--uninstall` puts it back.
Once wired, every later `python3 install.py` refreshes the copy. A statusLine
wired by the old standalone `progress-outline` repo (`_isaManaged`, or the
task-plan era's `_taskPlanManaged` and its `TodoWrite` capture hook) migrates
in place with its inner command.

Needs node ≥ 23.6 (native TypeScript), found through `mise which node`, else PATH.
Tests: `node --test adapters/claude-statusline/test/renderer.test.ts`; the
install mechanism is covered by `tests.test_install.TestStatusline`.

## Configuration

`config.json` next to the installed `harness.ts` (`~/.local/share/isa/statusline/config.json`, optional; kept across reinstalls):

| Option | Default | Description |
|--------|---------|-------------|
| `mode` | `auto` | `auto` picks compact/wide from `$COLUMNS` (under 70 → compact); `compact`/`wide` pin it |
| `color` | `true` | `NO_COLOR` in the environment always wins. Without color, the bar falls back to `#`/`-` |
| `isaBin` | `$ISA_BIN`, then `~/.local/bin/isa` | the `isa` launcher |

## Tests

```bash
node --test 'test/*.test.ts'
```
