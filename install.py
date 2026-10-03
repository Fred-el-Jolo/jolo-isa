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
  statusline (opt-in: --statusline; refreshed by every later install once wired)
            adapters/claude-statusline/ → ~/.local/share/isa/statusline (config.json kept), and the
            settings.json statusLine: an existing one (e.g. ccstatusline) is kept as `_isaInnerCommand`
            and shown above the ISA rows; --uninstall puts it back

Paths can be redirected for tests: --claude-settings, --pi-dir, --prefix, --skills-dir.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.abspath(__file__))
MARK = "isa hook claude"
H = os.path.expanduser("~")

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop"]
PERMS = ["Bash(isa:*)", "Read(~/.isa/**)", "Edit(~/.isa/**)", "Read(~/.claude/skills/ISA/**)"]  # Edit rules cover every file-editing tool
ISA_DIR = os.path.join(H, ".isa")


TIMEOUT = 15  # every ISA hook is a quick file / ledger check: no probe, no model call (SPEC-v2 § 11)


def hook_entry(cmd, ev=None):
    return {"hooks": [{"type": "command", "command": cmd, "timeout": TIMEOUT}]}


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
        for g in groups:  # an existing ISA entry keeps its place but gets the current timeout
            for h in g.get("hooks", []):
                if h.get("command") == cmd:
                    h["timeout"] = TIMEOUT
        if not any(h.get("command") == cmd for g in groups for h in g.get("hooks", [])):
            groups.append(hook_entry(cmd, ev))
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


def _q(s):
    return "'" + str(s).replace("'", "'\\''") + "'"


def _is_managed(sl):
    return bool(sl) and bool(sl.get("_isaManaged") or sl.get("_taskPlanManaged"))


def _inner_command(sl):
    """The statusLine command ours wraps: a managed entry remembers it, so re-running never nests."""
    if not sl:
        return None
    if _is_managed(sl):
        return sl.get("_isaInnerCommand", sl.get("_taskPlanInnerCommand"))
    return sl.get("command")


def merge_statusline(settings, node, sl_dir):
    """Wire the ISA statusLine, composing an existing one (e.g. ccstatusline) through
    statusline-wrapper.cjs: its command is kept in `_isaInnerCommand` and printed above the ISA rows."""
    s = json.loads(json.dumps(settings))
    post = s.get("hooks", {}).get("PostToolUse")
    if isinstance(post, list):  # the task-plan era's TodoWrite capture hook
        post[:] = [g for g in post if not (g.get("matcher") == "TodoWrite" and any(
            "harness.ts" in h.get("command", "") and "capture" in h.get("command", "") for h in g.get("hooks", [])))]
    cur = s.get("statusLine") or None
    inner = _inner_command(cur)
    harness = os.path.join(sl_dir, "harness.ts")
    if inner:
        cmd = " ".join(map(_q, (node, os.path.join(sl_dir, "scripts", "statusline-wrapper.cjs"), node, harness, inner)))
    else:
        cmd = f"{_q(node)} {_q(harness)} render"
    rest = {k: v for k, v in (cur or {}).items() if k not in ("_taskPlanManaged", "_taskPlanInnerCommand")}
    s["statusLine"] = {"type": "command", **rest, "command": cmd, "_isaManaged": True, "_isaInnerCommand": inner}
    return s


def strip_statusline(settings):
    """Put back the statusLine ours wrapped, or remove the one we added; leave any other alone."""
    s = json.loads(json.dumps(settings))
    cur = s.get("statusLine")
    if not _is_managed(cur):
        return s
    inner = _inner_command(cur)
    rest = {k: v for k, v in cur.items()
            if k not in ("_isaManaged", "_isaInnerCommand", "_taskPlanManaged", "_taskPlanInnerCommand")}
    if inner:
        s["statusLine"] = {**rest, "command": inner}
    else:
        del s["statusLine"]
    return s


def find_node():
    if shutil.which("mise"):
        try:
            p = subprocess.run(["mise", "which", "node"], capture_output=True, text=True, timeout=10)
            if p.returncode == 0 and p.stdout.strip():
                return p.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return shutil.which("node")


def install_statusline_files(dst, dry):
    """Copy adapters/claude-statusline (no tests) to dst, keeping the user's config.json."""
    cfg = os.path.join(dst, "config.json")
    saved = open(cfg).read() if os.path.isfile(cfg) else None
    copy_tree(os.path.join(REPO, "adapters", "claude-statusline"), dst, dry)
    if saved is not None and not dry:
        with open(cfg, "w") as f:
            f.write(saved)


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
    ap.add_argument("--statusline", action="store_true",
                    help="also wire the ISA statusLine (needs node >= 23.6), keeping an existing statusLine")
    a = ap.parse_args(argv)

    runtime = os.path.join(a.prefix, "share", "isa", "runtime")
    launcher = os.path.join(a.prefix, "bin", "isa")
    cmd = f"python3 {os.path.join(runtime, 'bin', 'isa')} hook claude"
    ext = os.path.join(a.pi_dir, "extensions", "isa.ts")
    sl_dir = os.path.join(a.prefix, "share", "isa", "statusline")

    try:
        with open(a.claude_settings) as f:
            settings = json.load(f)
    except FileNotFoundError:
        settings = {}

    if a.uninstall:
        print("Removing ISA enforcement (ISAs under ~/.isa are kept):")
        write_json_if_changed(a.claude_settings, strip_statusline(strip_settings(settings)), a.dry_run)
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
    new = merge_settings(settings, cmd)
    if a.statusline or _is_managed(settings.get("statusLine")):
        node = find_node()
        if node:
            install_statusline_files(sl_dir, a.dry_run)
            new = merge_statusline(new, node, sl_dir)
        else:
            print("  skipped statusline (no node binary: checked `mise which node` and PATH)")
    write_json_if_changed(a.claude_settings, new, a.dry_run)
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
