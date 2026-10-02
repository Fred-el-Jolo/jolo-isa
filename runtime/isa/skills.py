"""Slash commands that invoke a skill (SPEC-v2 § 12.6): the gate judges them with the skill's description.

    describe(prompt, harness, cwd) → "/<name>: <description>" | ""

Claude Code sends the raw `/<name> …`; pi's `input` event sends `/skill:<name> …`. The name is looked up
in the project's and the user's skill folders; an unknown name (a built-in command, a plugin skill) gives
"" and the prompt is judged alone.
"""
import os
import re

from . import state

SLASH = re.compile(r"^\s*/(?:skill:)?([A-Za-z0-9][\w.-]*)(?=\s|$)")
DIRS = {
    "claude": [".claude/skills", "~/.claude/skills"],
    "pi": [".pi/skills", "~/.pi/agent/skills", ".agents/skills", "~/.agents/skills"],
}


def describe(prompt, harness, cwd):
    m = SLASH.match(prompt or "")
    if not m:
        return ""
    name = m.group(1)
    roots = []
    for d in DIRS.get(harness, DIRS["claude"]):
        if d.startswith("~"):
            roots.append(os.path.expanduser(d))
        else:
            for base in (cwd, state.project_root(cwd) if cwd else None):
                if base and os.path.join(base, d) not in roots:
                    roots.append(os.path.join(base, d))
    for r in roots:
        path = os.path.join(r, name, "SKILL.md")
        if os.path.isfile(path):
            desc = state.frontmatter(path).get("description")
            return f"/{name}: {desc}" if isinstance(desc, str) and desc.strip() else f"/{name}"
    return ""
