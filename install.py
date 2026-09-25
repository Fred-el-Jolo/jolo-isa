#!/usr/bin/env python3
"""Install (or remove) ISA enforcement for Claude Code and pi. Standard library only.

    python3 install.py              install / update
    python3 install.py --uninstall  remove hooks, extension, launcher, runtime (ISAs in ~/.isa are kept)
    python3 install.py --dry-run    show what would change

What it does:
  runtime   runtime/            → ~/.local/share/isa/runtime   (replaced wholesale)
  launcher  ~/.local/bin/isa    → symlink to runtime/bin/isa
  skill     skill/ISA/          → ~/.claude/skills/ISA         (replaced wholesale)
  claude    ~/.claude/settings.json: adds the ISA hook entries and permissions, keeps every other
            entry, backs the file up first (settings.json.isa-backup-<time>) — only when it changes
  pi        adapters/pi/isa.ts  → ~/.pi/agent/extensions/isa.ts (only when ~/.pi/agent exists)

Paths can be redirected for tests: --claude-settings, --pi-dir, --prefix, --skills-dir.
"""
import argparse
import json
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.abspath(__file__))
MARK = "isa hook claude"
H = os.path.expanduser("~")

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop"]
PERMS = ["Bash(isa:*)", "Read(~/.isa/**)", "Edit(~/.isa/**)", "Read(~/.claude/skills/ISA/**)"]  # Edit rules cover every file-editing tool
ISA_DIR = os.path.join(H, ".isa")


def hook_entry(cmd):
    return {"hooks": [{"type": "command", "command": cmd, "timeout": 15}]}


def merge_settings(settings, cmd):
    """Return a new settings dict with ISA hooks + permissions present exactly once, others untouched."""
    s = json.loads(json.dumps(settings))
    hooks = s.setdefault("hooks", {})
    for ev in EVENTS:
        groups = hooks.setdefault(ev, [])
        # drop stale ISA entries (e.g. an old install path), keep everyone else's
        for g in groups:
            g["hooks"] = [h for h in g.get("hooks", []) if MARK not in h.get("command", "") or h["command"] == cmd]
        groups[:] = [g for g in groups if g.get("hooks")]
        if not any(h.get("command") == cmd for g in groups for h in g.get("hooks", [])):
            groups.append(hook_entry(cmd))
    perms = s.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    for p in PERMS:
        if p not in allow:
            allow.append(p)
    dirs = perms.setdefault("additionalDirectories", [])
    if ISA_DIR not in dirs:
        dirs.append(ISA_DIR)
    return s


def strip_settings(settings):
    s = json.loads(json.dumps(settings))
    for ev, groups in list(s.get("hooks", {}).items()):
        for g in groups:
            g["hooks"] = [h for h in g.get("hooks", []) if MARK not in h.get("command", "")]
        s["hooks"][ev] = [g for g in groups if g.get("hooks")]
        if not s["hooks"][ev]:
            del s["hooks"][ev]
    perms = s.get("permissions", {})
    if "allow" in perms:
        perms["allow"] = [p for p in perms["allow"] if p not in PERMS]
    if "additionalDirectories" in perms:
        perms["additionalDirectories"] = [d for d in perms["additionalDirectories"] if d != ISA_DIR]
    return s


def write_json_if_changed(path, new, dry):
    try:
        with open(path) as f:
            old_text = f.read()
        old = json.loads(old_text)
    except FileNotFoundError:
        old_text, old = None, {}
    if new == old:
        print(f"  unchanged  {path}")
        return False
    if dry:
        print(f"  would update {path}")
        return True
    if old_text is not None:
        bak = f"{path}.isa-backup-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, bak)
        print(f"  backup     {bak}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".isa-tmp"
    with open(tmp, "w") as f:
        json.dump(new, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    print(f"  updated    {path}")
    return True


def copy_tree(src, dst, dry):
    if dry:
        print(f"  would copy {src} → {dst}")
        return
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test", "tests"))
    print(f"  copied     {dst}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prefix", default=os.path.join(H, ".local"))
    ap.add_argument("--claude-settings", default=os.path.join(H, ".claude", "settings.json"))
    ap.add_argument("--skills-dir", default=os.path.join(H, ".claude", "skills"))
    ap.add_argument("--pi-dir", default=os.path.join(H, ".pi", "agent"))
    ap.add_argument("--no-skill", action="store_true", help="leave the installed skill alone")
    a = ap.parse_args(argv)

    runtime = os.path.join(a.prefix, "share", "isa", "runtime")
    launcher = os.path.join(a.prefix, "bin", "isa")
    cmd = f"python3 {os.path.join(runtime, 'bin', 'isa')} hook claude"
    ext = os.path.join(a.pi_dir, "extensions", "isa.ts")

    try:
        with open(a.claude_settings) as f:
            settings = json.load(f)
    except FileNotFoundError:
        settings = {}

    if a.uninstall:
        print("Removing ISA enforcement (ISAs under ~/.isa are kept):")
        write_json_if_changed(a.claude_settings, strip_settings(settings), a.dry_run)
        for p in (ext, launcher):
            if os.path.lexists(p):
                print(f"  {'would remove' if a.dry_run else 'removed'}    {p}")
                if not a.dry_run:
                    os.remove(p)
        if os.path.isdir(os.path.dirname(runtime)):
            print(f"  {'would remove' if a.dry_run else 'removed'}    {os.path.dirname(runtime)}")
            if not a.dry_run:
                shutil.rmtree(os.path.dirname(runtime))
        return 0

    print("Installing ISA enforcement:")
    copy_tree(os.path.join(REPO, "runtime"), runtime, a.dry_run)
    if not a.dry_run:
        os.makedirs(os.path.dirname(launcher), exist_ok=True)
        target = os.path.join(runtime, "bin", "isa")
        if os.path.islink(launcher) and os.readlink(launcher) == target:
            print(f"  unchanged  {launcher}")
        else:
            if os.path.lexists(launcher):
                os.remove(launcher)
            os.symlink(target, launcher)
            print(f"  linked     {launcher} → {target}")
    if not a.no_skill:
        copy_tree(os.path.join(REPO, "skill", "ISA"), os.path.join(a.skills_dir, "ISA"), a.dry_run)
    write_json_if_changed(a.claude_settings, merge_settings(settings, cmd), a.dry_run)
    if os.path.isdir(a.pi_dir):
        src = os.path.join(REPO, "adapters", "pi", "isa.ts")
        same = os.path.isfile(ext) and open(ext).read() == open(src).read()
        if same:
            print(f"  unchanged  {ext}")
        elif a.dry_run:
            print(f"  would copy {src} → {ext}")
        else:
            os.makedirs(os.path.dirname(ext), exist_ok=True)
            shutil.copy2(src, ext)
            print(f"  copied     {ext}")
    else:
        print(f"  skipped pi (no {a.pi_dir})")
    os.makedirs(os.path.join(os.environ.get("ISA_HOME", os.path.join(H, ".isa"))), exist_ok=True)
    print("Done. New Claude Code and pi sessions are gated; running sessions pick it up on restart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
