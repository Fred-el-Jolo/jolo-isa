# Future B — "ISA status" status line

> **Status: built for Claude Code.** The data side is `isa status --session <id> [--harness H] --json` (`runtime/isa/status.py`): it follows option 2 below through the engine's own session binding, and lists the leaf ISCs `progress` counts (via `lint.collect_iscs` / `lint.leaf_iscs`, so the two never disagree). The renderer is a separate Node statusLine client in `~/dev/progress-outline`. A pi display (`ctx.ui`) can consume the same JSON later. The LifeOS status line is deliberately **not** carried over.

```json
{"bound": "/…/ISA.md", "task": "…", "effort": "E3", "phase": "build", "progress": "3/15",
 "iteration": null, "iscs": [{"id": "ISC-1", "text": "…", "done": true}, …]}
```

With nothing bound (or the file gone) it prints `{"bound": null}` and exits 0.

## What the ISA already exposes (the data contract)

The ISA frontmatter is the whole interface — the status line only reads it, never writes it:

| Field | Example | Use |
|-------|---------|-----|
| `task` | `"Add SHA-256 verify to backup CLI"` | label |
| `phase` | `execute` | `observe\|think\|plan\|build\|execute\|verify\|learn\|complete` |
| `progress` | `7/18` | progress bar / fraction — counted over leaf ISCs, excluding dropped and waived (IsaFormat § Field Rules) |
| `effort` | `E3` | tier badge |
| `iteration` | `2` | reopened marker (absent on first run) |
| `updated` | ISO-8601 | staleness hint |
| `current_state` / `ideal_state` | one-liners | optional journey text |

The skill keeps `phase` and `progress` true on every edit (see `skill/ISA/SKILL.md` § Lifecycle rules), so a reader can trust them.

## How LifeOS found the active ISA (for reference, not to copy)

LifeOS mirrored every ISA write into a registry (`MEMORY/STATE/work.json`, via `ISASync.hook.ts` on PostToolUse Write/Edit) keyed by slug and session UUID, and a dashboard read that registry. That's heavy. Simpler options for the status line:

1. Most recently modified `~/.claude/isa/*/ISA.md` whose `phase` ≠ `complete`.
2. A tiny PostToolUse hook that writes `{session_id → isa_path}` to a state file when an `ISA.md` is written; the status line reads that for the current session (Claude Code passes `session_id` to the status line command).

Option 2 is correct with multiple concurrent sessions; option 1 is zero-hook.
