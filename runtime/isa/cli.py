"""`isa` command line. Standard library only.

    isa ls [--all]               ISAs of the current project (or every project)
    isa new <slug> [--tier E3] [--goal "<verbatim span>"] [--path-only]
                                 create the task ISA (frontmatter: root, stated_goal, asks) and print
                                 its path — the hooks bind it to the session
    isa where                    project key and ISA folder for the current directory
    isa lint [--close] FILE…     recompute progress / nested parents / orphaned generated lines, then
                                 the mechanical gate check (same engine the hooks use)
    isa fit "<prompt>"           the gate's free pre-filter verdict (yes | no | unsure → judge) + fit score
    isa verify [--red] ISA [ISC-N…] [--attest "<evidence>"]
                                 run the probes (cwd = the ISA's root), record them, tick what passed and
                                 untick what regressed; --attest ticks a self-attested ISC; --red records
                                 the failing baseline before the change and ticks nothing
    isa close ISA                re-run every probe; close the ISA only when all pass and lint --close is clean
    isa status --session ID [--harness H] [--json]
                                 the session's bound ISA: tier, phase, progress, open ISCs (read-only)
    isa hook <harness>           hook entry point: event JSON on stdin, harness JSON on stdout
"""
import json
import os
import sys
import traceback

from . import commands, engine, fit, state, status


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd == "hook":
        return hook(args[0] if args else "claude")
    if cmd == "lint":
        return commands.lint_cmd(args)
    if cmd == "ls":
        return _ls(args)
    if cmd == "new":
        return commands.new(args)
    if cmd == "close":
        if len(args) != 1:
            print("usage: isa close ISA.md", file=sys.stderr)
            return 2
        return commands.close(os.path.expanduser(args[0]))
    if cmd == "fit":
        text = " ".join(args) if args else sys.stdin.read()
        verdict, why = fit.prefilter(text)
        level, reasons = fit.score(text)
        print(f"{verdict} — {why}" + (" (goes to the judge)" if verdict == "unsure" else "")
              + f"\n  fit score: {level}" + "".join(f"\n  - {r}" for r in reasons))
        return 0
    if cmd == "verify":
        return _verify(args)
    if cmd == "status":
        return _status(args)
    if cmd == "where":
        print(f"project key: {state.project_key(os.getcwd())}\nISA folder:  {state.project_dir(os.getcwd())}")
        return 0
    print(f"isa: unknown command `{cmd}` (see `isa --help`)", file=sys.stderr)
    return 2


def _ls(args):
    keys = sorted(k for k in os.listdir(state.home()) if k not in ("_state",) and not k.startswith(".")) \
        if "--all" in args and os.path.isdir(state.home()) else [state.project_key(os.getcwd())]
    n = 0
    for key in keys:
        rows = state.list_isas(key=key)
        if not rows:
            continue
        print(f"{key}/")
        for p, fm in rows:
            n += 1
            linked = os.path.islink(os.path.dirname(p))
            print(f"  {os.path.basename(os.path.dirname(p)):<52} {str(fm.get('effort', '?')):<3} "
                  f"{str(fm.get('phase', '?')):<9} {str(fm.get('progress', '?')):<7} {fm.get('task', '')}"
                  + (f"  (filed in {state.isa_home_key(p)})" if linked else ""))
    if not n:
        print(f"no ISAs under {state.project_dir(os.getcwd())}")
    return 0


def _verify(args):
    timeout, attest, red = 600, None, False
    args = list(args)
    for flag in ("--timeout", "--attest"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                print(f"isa verify: {flag} needs a value", file=sys.stderr)
                return 2
            val, args = args[i + 1], args[:i] + args[i + 2:]
            if flag == "--timeout":
                timeout = int(val)
            else:
                attest = val
    if "--red" in args:
        red, args = True, [a for a in args if a != "--red"]
    if not args:
        print('usage: isa verify [--red] ISA.md [ISC-N…] [--attest "<evidence>"] [--timeout SECONDS]',
              file=sys.stderr)
        return 2
    return commands.verify(os.path.expanduser(args[0]), args[1:], red=red, attest=attest, timeout=timeout)


def _status(args):
    opts, i = {"--harness": "claude", "--session": None}, 0
    while i < len(args):
        if args[i] in opts and i + 1 < len(args):
            opts[args[i]] = args[i + 1]
            i += 2
        else:
            i += 1
    if not opts["--session"]:
        print("isa status: --session ID is required", file=sys.stderr)
        return 2
    v = status.view(opts["--harness"], opts["--session"])
    print(json.dumps(v) if "--json" in args else status.line(v))
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
        "tool": d.get("tool_name"), "tool_input": d.get("tool_input"), "tool_use_id": d.get("tool_use_id"),
        "temp_dirs": [d["scratchpad_dir"]] if d.get("scratchpad_dir") else [],
        "retried": bool(d.get("stop_hook_active")), "transcript_path": d.get("transcript_path"),
        "tool_output": _tool_output(d.get("tool_response")), "_name": name,
    }


def _tool_output(resp):
    """The text a tool printed (Bash: stdout), as far as the hook input carries it."""
    if isinstance(resp, dict):
        return str(resp.get("stdout") or resp.get("output") or resp.get("content") or "")
    return "" if resp is None else str(resp)


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
