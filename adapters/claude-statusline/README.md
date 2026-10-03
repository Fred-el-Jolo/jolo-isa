# ISA statusline

Shows the ISA bound to the current Claude Code session in the
statusLine: tier, phase, progress, and the ISCs still open. Nothing to keep
in sync. The ISA hooks already bind one `ISA.md` per session, and this
only reads it.

```
●●●●●○○○○○○○○○○ 5/15  E3 · build · Rebuild progress-outline as the ISA status line
○ ISC-6 Wide layout shows progress bar, tier, phase and task on row 1.
○ ISC-7 Wide layout lists up to two open ISCs, the last with `+N` for the rest.  +8
```

Compact (under 70 columns, or `mode: "compact"`):

```
5/15 build ISC-6 Wide layout shows progress bar, tier, phas…
```

With `phase: complete` the open rows become `✔ complete`. With every ISC
ticked but the ISA not closed yet, they read `✔ all ISCs verified`. If no
ISA is bound, it prints nothing.

## How it works

```
Claude Code statusLine ──stdin {session_id}──► harness.ts render
                                                   │
                                  isa status --json --session <id>   (runtime/isa/status.py)
                                                   │  reads ~/.isa/_state/sessions/claude-<id>.json → bound ISA.md
                                                   ▼
                                  { task, effort, phase, progress, iteration, iscs[] }
                                                   │
                                             renderer.ts ──► stdout
```

- **The runtime owns the data.** `isa status` finds the bound ISA through the
  engine's own session state and parses it with the same helpers `isa lint`
  uses (`collect_iscs`, `leaf_iscs`). The ISC list is exactly the set
  `progress` counts: leaves only, with no dropped or waived ISCs.
- **This adapter only renders it.** It has no hook and no state file, and it
  never writes anything. Any failure prints nothing and exits 0.
- **Open ISCs, not a "current" one.** An ISA has no in-progress marker, so
  the phase says what is happening and the rows list what's still open, in
  file order.
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
| `color` | `true` | `NO_COLOR` in the environment always wins. Without color, glyphs fall back to `[x]`/`[ ]` and the bar to `#`/`-` |
| `isaBin` | `$ISA_BIN`, then `~/.local/bin/isa` | the `isa` launcher |

## Tests

```bash
node --test 'test/*.test.ts'
```
