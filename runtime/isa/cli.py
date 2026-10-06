"""`isa` command line. Standard library only.

    isa ls [--all]               ISAs of the current project (or every project)
    isa new <slug> [--tier E3] [--goal "<verbatim span>"] [--path-only]
                                 create the task ISA (frontmatter: root, stated_goal, asks) and print
                                 its path — the hooks bind it to the session
    isa where                    project key and ISA folder for the current directory
    isa lint [--close] FILE…     recompute progress / nested parents / orphaned generated lines, then
                                 the mechanical gate check (same engine the hooks use); a spec or plan
                                 (docs/spec/*.md, docs/plan/*.md) gets the spec lint instead
                                 (`--moment ack`: also the rules that must hold before the ack)
    isa verify [--red] ISA [ISC-N…] [--attest "<evidence>"]
                                 run the probes (cwd = the ISA's root), record them, tick what passed and
                                 untick what regressed; --attest ticks a self-attested ISC; --red records
                                 the failing baseline before the change and ticks nothing
    isa close ISA                re-run every probe; close the ISA only when all pass and lint --close is clean
    isa status --session ID [--harness H] [--json]
                                 the session's bound ISA: tier, phase, progress, open ISCs (read-only)
    isa current [--session ID] [--harness H] [--json]
                                 the session's bound ISA for a skill: path, task, tier, phase, progress,
                                 open criteria. The session defaults to $CLAUDE_CODE_SESSION_ID (Claude
                                 Code) or $PI_SESSION_ID (pi); exit 1 when no ISA is bound
    isa purge-logs [--days N] [--dry-run]
                                 delete debug log day files (~/.isa/_state/logs) older than N days (7);
                                 never touches the evidence ledger, sessions, prompts or ISAs
    isa hook <harness>           hook entry point: event JSON on stdin, harness JSON on stdout
"""
import json
import os
import sys
import time
import traceback

from . import commands, engine, evidence, logs, specdoc, state, status


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd in LOGGED:
        t0 = time.time()
        logs.take_note()
        rc = 2
        try:
            rc = _dispatch(cmd, args)
            return rc
        finally:
            row = {"step": "cmd", "cmd": cmd, "exit": rc, "ms": int((time.time() - t0) * 1000), "cwd": os.getcwd()}
            isa = next((os.path.expanduser(a) for a in args if a.endswith("ISA.md")), None)
            if isa:
                row["isa"] = isa
            row.update(logs.take_note())
            if cmd != "purge-logs" or os.path.isdir(logs.log_dir()):  # a purge never creates the folder
                logs.write(row)
    return _dispatch(cmd, args)


LOGGED = {"new", "lint", "verify", "close", "purge-logs"}


def _dispatch(cmd, args):
    if cmd == "hook":
        return hook(args[0] if args else "claude")
    if cmd == "lint":
        return _lint(args)
    if cmd == "ls":
        return _ls(args)
    if cmd == "new":
        return commands.new(args)
    if cmd == "close":
        if len(args) != 1:
            print("usage: isa close ISA.md", file=sys.stderr)
            return 2
        return commands.close(os.path.expanduser(args[0]))
    if cmd == "verify":
        return _verify(args)
    if cmd == "status":
        return _status(args)
    if cmd == "current":
        return _current(args)
    if cmd == "purge-logs":
        return logs.purge_cmd(args)
    if cmd == "where":
        print(f"project key: {state.project_key(os.getcwd())}\nISA folder:  {state.project_dir(os.getcwd())}")
        return 0
    print(f"isa: unknown command `{cmd}` (see `isa --help`)", file=sys.stderr)
    return 2


def _spec_doc(p):
    """A spec or plan: a `.md` directly under a `docs/spec/` or `docs/plan/` folder (until P6's
    `state.is_spec_path`)."""
    d = os.path.dirname(os.path.abspath(os.path.expanduser(p)))
    return p.endswith(".md") and os.path.basename(d) in ("spec", "plan") \
        and os.path.basename(os.path.dirname(d)) == "docs"


def _lint(args):
    """`isa lint`: specs and plans go to `specdoc.lint`, every other file to the ISA lint, unchanged."""
    flags, files = [], list(args)
    if files[:1] == ["--close"]:
        flags, files = files[:1], files[1:]
    elif files[:1] == ["--moment"] and len(files) > 1:
        flags, files = files[:2], files[2:]
    if not any(_spec_doc(p) for p in files):
        return commands.lint_cmd(args)
    moment = "ack" if flags == ["--moment", "ack"] else "draft"
    rc = 0
    for p in files:
        if not _spec_doc(p):
            rc = max(rc, commands.lint_cmd(flags + [p]))
            continue
        try:
            with open(os.path.expanduser(p), encoding="utf-8") as f:
                kind = specdoc.parse(f.read())["kind"]
        except (OSError, ValueError) as e:  # ValueError: not UTF-8
            print(f"{p}: cannot read ({e})")
            rc = 1
            continue
        items = specdoc.lint(os.path.expanduser(p), moment)
        errs = [m for m in items if not m.startswith("warn:")]
        print(f"{p}: {'ok' if not errs else f'{len(errs)} error(s)'} ({kind})")
        for m in items:
            print(f"  WARN: {m[len('warn:'):].strip()}" if m.startswith("warn:") else f"  ERROR: {m}")
        rc = max(rc, 1 if errs else 0)
    return rc


def _ls(args):
    """The current project's ISAs (ISA_HOME/<key>); `--all` adds every ISA_HOME folder."""
    here = state.project_dir(os.getcwd())
    folders = [(state.project_key(os.getcwd()), here)]
    if "--all" in args and os.path.isdir(state.home()):
        folders += [(k, os.path.join(state.home(), k)) for k in sorted(os.listdir(state.home()))
                    if k not in ("_state",) and not k.startswith(".") and os.path.join(state.home(), k) != here]
    n = 0
    for key, folder in folders:
        rows = state.list_isas(folder=folder)
        if not rows:
            continue
        print(f"{key}/")
        for p, fm in rows:
            n += 1
            linked = os.path.islink(os.path.dirname(p))
            label = evidence.pause_label(p) if fm.get("phase") != "complete" else None
            print(f"  {os.path.basename(os.path.dirname(p)):<52} {str(fm.get('effort', '?')):<3} "
                  f"{str(label or fm.get('phase', '?')):<10} {str(fm.get('progress', '?')):<7} {fm.get('task', '')}"
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


def _current(args):
    opts, i = {"--harness": None, "--session": None}, 0
    while i < len(args):
        if args[i] in opts and i + 1 < len(args):
            opts[args[i]] = args[i + 1]
            i += 2
        else:
            i += 1
    sid, harness = opts["--session"], opts["--harness"]
    if not sid:
        for var, h in (("CLAUDE_CODE_SESSION_ID", "claude"), ("PI_SESSION_ID", "pi")):
            if os.environ.get(var):
                sid, harness = os.environ[var], harness or h
                break
    if not sid:
        print("isa current: no session — pass --session ID, or run it from a Claude Code or pi shell "
              "($CLAUDE_CODE_SESSION_ID / $PI_SESSION_ID)", file=sys.stderr)
        return 2
    v = status.current(harness or "claude", sid)
    if "--json" in args:
        print(json.dumps(v))
    elif v["path"]:
        print(f"{v['path']}\n{v['tier']} {v['phase']} {v['progress']}" + (f" ({v['label']})" if v["label"] else "")
              + f" — {v['task']}" + "".join(f"\n  open {o['id']}: {o['text']}" for o in v["open"]))
    else:
        print(f"no ISA bound to session {sid}")
    return 0 if v["path"] else 1


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
        "tool_output": _tool_output(d.get("tool_response")), "tool_response": d.get("tool_response"), "_name": name,
        # Stop: the final answer, when the harness passes it (the transcript is read otherwise)
        "context": d.get("last_assistant_message") if name == "Stop" else None,
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
