"""`isa` — the only way to create, read, change or delete an ISA entity. Standard library only.

Start
    isa spec new <slug> --tier E2|E3|E4          a draft spec at docs/YYYY-MM-DD-<slug>-01-spec.md (binds it)
    isa new <slug> --tier E1 [--goal G] [--ask A]…   an E1 TASK ISA (binds it)
    isa new --spec <spec> [--goal G] [--ask A]…      the TASK ISA of an acked spec (binds it; an open one is reused)
Write
    isa write <file> <section>                   a section, text on stdin (Criteria and Test Strategy: once)
    isa write <ISA> ISC-N "<text>"               change or add one criterion
    isa write <ISA> ISC-N --probe "<command>" [--kind K] [--fails-when F] [--anchors S2]
    isa write <ISA> task|asks                    the task line; the asks (one per line, verbatim)
    isa drop <ISA> ISC-N "<why>"                 a tombstone; the id is never reused
    isa decide <ISA> "<text>"                    one Decisions row
Acks
    isa ack <file>                               write the user's recorded click (spec: then commit it)
    isa reopen <spec>                            an acked spec back to draft
    isa diff <file>                              what changed since its last ack
    isa refine <ISA>                             follow a re-acked spec (progress kept; the ISA is acked again)
Proof
    isa verify <ISA> [--red] [ISC-N…]            run the probes; red: the failing baseline before the build
    isa attest <ISA> ISC-N "<evidence>"          a manual leaf
    isa answer <ISA> goal "yes — <evidence>"     the Goal line; `ask N "met — <evidence>"` an Ask line
    isa close <ISA>                              re-prove all, write the plan (E2+), commit the work and the plan
Read
    isa show <file> [--to <section>]   isa lint <file>…   isa ls [--all]   isa where
    isa status --session ID [--json]   isa current [--json]   isa log [--session ID] [--prompt ID]
    isa purge-logs [--days N] [--dry-run]        delete old debug log days
    isa hook <claude|pi>                         the hook entry point (event JSON on stdin)
"""
import json
import os
import sys
import time
import traceback

from . import commands, engine, lint, logs, state, status


def _stdin():
    return "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()


COMMANDS = {
    "spec": lambda a: commands.spec_cmd(a),
    "new": lambda a: commands.new(a),
    "write": lambda a: commands.write(a, _stdin() if _needs_stdin(a) else ""),
    "drop": lambda a: commands.drop(a),
    "decide": lambda a: commands.decide(a),
    "show": lambda a: commands.show(a),
    "lint": lambda a: lint.main(a),
    "ack": lambda a: commands.ack(a),
    "reopen": lambda a: commands.reopen(a),
    "diff": lambda a: commands.diff_cmd(a),
    "refine": lambda a: commands.refine(a),
    "verify": lambda a: commands.verify(a),
    "attest": lambda a: commands.attest(a),
    "answer": lambda a: commands.answer(a),
    "close": lambda a: commands.close(a),
    "ls": lambda a: commands.ls(a),
    "status": lambda a: _status(a),
    "current": lambda a: _current(a),
    "where": lambda a: commands.where(a),
    "log": lambda a: logs.log_cmd(a),
    "purge-logs": lambda a: logs.purge_cmd(a),
    "hook": lambda a: hook(a[0] if a else "claude"),
}


def _needs_stdin(args):
    """`isa write <file> <part>` with no inline text and no --probe: the text comes on stdin."""
    rest = [a for a in args[2:] if a not in ("--kind", "--fails-when", "--anchors")]
    return len(args) >= 2 and not rest and "--probe" not in args


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, args = argv[0], argv[1:]
    fn = COMMANDS.get(cmd)
    if not fn:
        print(f"isa: unknown command `{cmd}` (see `isa --help`)", file=sys.stderr)
        return 2
    t0 = time.time()
    rc = 2
    try:
        rc = fn(args)
        return rc
    except commands.Refused as e:
        print(f"isa {cmd}: {e}", file=sys.stderr)
        rc = 1
        return rc
    finally:
        if cmd not in ("hook", "log") and logs.on():
            logs.write({"step": "cmd", "cmd": cmd, "exit": rc, "ms": int((time.time() - t0) * 1000), "cwd": os.getcwd()})


def _opts(args, names):
    out = {n: None for n in names}
    for n in names:
        if n in args and args.index(n) + 1 < len(args):
            out[n] = args[args.index(n) + 1]
    return out


def _status(args):
    o = _opts(args, ("--session", "--harness"))
    if not o["--session"]:
        print("isa status: --session ID is required", file=sys.stderr)
        return 2
    v = status.view(o["--harness"] or "claude", o["--session"])
    print(json.dumps(v) if "--json" in args else status.line(v))
    return 0


def _current(args):
    o = _opts(args, ("--session", "--harness"))
    sid, harness = o["--session"], o["--harness"]
    if not sid:
        for var, h in (("CLAUDE_CODE_SESSION_ID", "claude"), ("PI_SESSION_ID", "pi")):
            if os.environ.get(var):
                sid, harness = os.environ[var], harness or h
                break
    if not sid:
        print("isa current: no session (pass --session ID)", file=sys.stderr)
        return 2
    v = status.view(harness or "claude", sid)
    print(json.dumps(v) if "--json" in args else status.line(v))
    return 0 if v.get("bound") else 1


# ------------------------------------------------------------------ hook adapters

def hook(harness):
    raw = sys.stdin.read()
    try:
        data = json.loads(raw or "{}")
        ev = ADAPTERS[harness]["in"](data)
        res = engine.handle(ev) if ev else {}
        return ADAPTERS[harness]["out"](ev or {}, res)
    except Exception as e:  # fail open, loudly: a gate bug must never stop all work
        if logs.on():
            logs.write({"step": "error", "harness": harness, "error": repr(e), "trace": traceback.format_exc()})
        msg = f"ISA hook error (not enforced for this event): {e!r}"
        print(json.dumps({"systemMessage": msg} if harness == "claude" else {"warn": msg}))
        return 0


_CLAUDE_EVENTS = {
    "SessionStart": "session_start", "UserPromptSubmit": "prompt", "PreToolUse": "pre_tool",
    "PostToolUse": "post_tool", "PostToolUseFailure": "tool_failed", "Stop": "stop",
    "PreCompact": "compacted", "PostCompact": "compacted",
}


def _tool_output(resp):
    if isinstance(resp, dict):
        return str(resp.get("stdout") or resp.get("output") or resp.get("content") or "")
    return "" if resp is None else str(resp)


def _claude_in(d):
    name = d.get("hook_event_name")
    ev = _CLAUDE_EVENTS.get(name)
    if not ev:
        return None
    return {"harness": "claude", "session": d.get("session_id"), "event": ev, "cwd": d.get("cwd"),
            "prompt_id": d.get("prompt_id"), "source": d.get("source"), "prompt": d.get("prompt"),
            "tool": d.get("tool_name"), "tool_input": d.get("tool_input"),
            "temp_dirs": [d["scratchpad_dir"]] if d.get("scratchpad_dir") else [],
            "retried": bool(d.get("stop_hook_active")), "transcript_path": d.get("transcript_path"),
            "tool_output": _tool_output(d.get("tool_response")), "tool_response": d.get("tool_response"),
            "_name": name, "context": d.get("last_assistant_message") if name == "Stop" else None}


def _claude_out(ev, res):
    name, out = ev.get("_name"), {}
    if res.get("warn"):
        out["systemMessage"] = res["warn"]
    if res.get("block") and name == "Stop":
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


def _pi_in(d):
    d = dict(d)
    d["harness"] = "pi"
    return d if d.get("event") else None


def _pi_out(ev, res):
    print(json.dumps(res))
    return 0


ADAPTERS = {"claude": {"in": _claude_in, "out": _claude_out}, "pi": {"in": _pi_in, "out": _pi_out}}
