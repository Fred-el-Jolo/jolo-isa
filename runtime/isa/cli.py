"""`isa` command line. Standard library only.

    isa ls [--all]               ISAs of the current project (or every project)
    isa new <slug>               create a fresh ISA folder for this project, print the ISA.md path
    isa where                    project key and ISA folder for the current directory
    isa lint [--moment M] FILE…  mechanical gate check (same engine the hooks use)
    isa hook <harness>           hook entry point: event JSON on stdin, harness JSON on stdout
"""
import json
import os
import sys
import traceback

from . import engine, lint, state


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd == "hook":
        return hook(args[0] if args else "claude")
    if cmd == "lint":
        return lint.main(args)
    if cmd == "ls":
        return _ls(args)
    if cmd == "new":
        p = state.new_isa_path(os.getcwd(), " ".join(args) or "task")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        print(p)
        return 0
    if cmd == "where":
        print(f"project key: {state.project_key(os.getcwd())}\nISA folder:  {state.project_dir(os.getcwd())}")
        return 0
    print(f"isa: unknown command `{cmd}` (see `isa --help`)", file=sys.stderr)
    return 2


def _ls(args):
    keys = sorted(k for k in os.listdir(state.home()) if not k.startswith("_")) \
        if "--all" in args and os.path.isdir(state.home()) else [state.project_key(os.getcwd())]
    n = 0
    for key in keys:
        rows = state.list_isas(key=key)
        if not rows:
            continue
        print(f"{key}/")
        for p, fm in rows:
            n += 1
            print(f"  {os.path.basename(os.path.dirname(p)):<52} {str(fm.get('effort', '?')):<3} "
                  f"{str(fm.get('phase', '?')):<9} {str(fm.get('progress', '?')):<7} {fm.get('task', '')}")
    if not n:
        print(f"no ISAs under {state.project_dir(os.getcwd())}")
    return 0


# ------------------------------------------------------------------ hook adapters

def hook(harness):
    raw = sys.stdin.read()
    try:
        if os.environ.get("ISA_FAULT_INJECT"):
            raise RuntimeError("injected fault (ISA_FAULT_INJECT)")
        data = json.loads(raw or "{}")
        adapter = ADAPTERS[harness]
        ev = adapter["in"](data)
        res = engine.handle(ev) if ev else {}
        return adapter["out"](ev or {}, res)
    except Exception as e:  # fail open, loudly: a gate bug must never stop all work
        where = "~/.isa/_state/errors.log"
        try:
            state.log_error(f"{harness}: {e!r}\n{traceback.format_exc()}\ninput: {raw[:2000]}")
        except Exception:
            where = "stderr"
            print(traceback.format_exc(), file=sys.stderr)
        msg = f"ISA hook error (not enforced for this event): {e}. Details: {where}"
        print(json.dumps({"systemMessage": msg} if harness == "claude" else {"warn": msg}))
        return 0


# Claude Code ---------------------------------------------------------

_CLAUDE_EVENTS = {
    "SessionStart": "session_start", "UserPromptSubmit": "prompt", "PreToolUse": "pre_tool",
    "PostToolUse": "post_tool", "PostToolUseFailure": "tool_failed", "Stop": "stop",
    "PreCompact": "compacted", "PostCompact": "compacted",
}


def _claude_in(d):
    name = d.get("hook_event_name")
    ev = _CLAUDE_EVENTS.get(name)
    if not ev:
        return None
    return {
        "harness": "claude", "session": d.get("session_id"), "event": ev, "cwd": d.get("cwd"),
        "prompt_id": d.get("prompt_id"), "source": d.get("source"), "prompt": d.get("prompt"),
        "tool": d.get("tool_name"), "tool_input": d.get("tool_input"),
        "temp_dirs": [d["scratchpad_dir"]] if d.get("scratchpad_dir") else [],
        "retried": bool(d.get("stop_hook_active")), "_name": name,
    }


def _claude_out(ev, res):
    name = ev.get("_name")
    out = {}
    if res.get("warn"):
        out["systemMessage"] = res["warn"]
    if res.get("block") and name == "Stop":
        # exit code 2: Claude Code keeps the turn going and feeds stderr to the model
        if out:
            print(json.dumps(out))
        print(res["block"], file=sys.stderr)
        return 2
    if res.get("deny") and name == "PreToolUse":
        out["hookSpecificOutput"] = {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": res["deny"]}
    elif res.get("context") and name in ("SessionStart", "UserPromptSubmit", "PostToolUse", "PostToolUseFailure"):
        out["hookSpecificOutput"] = {"hookEventName": name, "additionalContext": res["context"]}
    if out:
        print(json.dumps(out))
    return 0


# pi (the extension already speaks the neutral shape) ------------------

def _pi_in(d):
    d = dict(d)
    d["harness"] = "pi"
    return d if d.get("event") else None


def _pi_out(ev, res):
    print(json.dumps(res))
    return 0


ADAPTERS = {
    "claude": {"in": _claude_in, "out": _claude_out},
    "pi": {"in": _pi_in, "out": _pi_out},
}
