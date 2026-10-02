"""Harness-neutral decisions. Adapters translate their events into `handle(event)` calls.

Event (dict):
    harness     "claude" | "pi" | …
    session     session id
    event       session_start | prompt | pre_tool | post_tool | tool_failed | stop | compacted
    cwd         working directory
    prompt_id   id of the current user prompt (stop: one block per prompt)
    source      session_start only: startup | resume | clear | compact | …
    prompt      prompt only: raw user text
    tool, tool_input      pre_tool / post_tool / tool_failed
    temp_dirs   extra directories treated as scratch (e.g. Claude's scratchpad_dir)
    retried     stop only: the harness says a stop hook already forced this continuation
    transcript_path  prompt only (Claude Code): where the previous assistant message is read from
    context     prompt only (pi): the tail of the previous assistant message

Result (dict, all keys optional):
    context     text for the model
    deny        pre_tool: reason the call is refused
    block       stop: reason the turn must continue
    warn        text for the user (not the model)

ISA mode (SPEC-v2 § 1): every session is OFF until the gate (judge.py) answers yes for a prompt, a
write is attempted, an unknown command changes project files, or an ISA is bound; then it is ON for
good. OFF sessions get nothing from this engine. `ISA_MODE=on|off` (the user's override) wins.
"""
import hashlib
import json
import os
import re
import time

from . import changes, classify, evidence, isafile, judge, lint, problems, rules, state

HERE = os.path.dirname(os.path.abspath(__file__))
STALE_NUDGE_EVERY = 5
MAX_LISTED = 6


def skill_dir():
    return os.path.expanduser(os.environ.get("ISA_SKILL_DIR", "~/.claude/skills/ISA"))


def protocol(cwd):
    text = open(os.path.join(HERE, "protocol.md"), encoding="utf-8").read()
    return text.replace("{project_dir}", _tilde(state.project_dir(cwd))).replace("{skill_dir}", _tilde(skill_dir()))


def _tilde(p):
    h = os.path.expanduser("~")
    return "~" + p[len(h):] if p == h or p.startswith(h + os.sep) else p


# ------------------------------------------------------------------ helpers

def _goal_ok_file(isa_path):
    return os.path.join(os.path.dirname(isa_path), ".stated_goal.sha256")


def _lint(isa_path, moment, harness, session):
    """Lint with the verbatim-goal check. A goal verified once (in any session) stays verified."""
    fm = state.frontmatter(isa_path)
    goal = fm.get("stated_goal") if isinstance(fm.get("stated_goal"), str) else None
    prompts = None
    if goal:
        digest = hashlib.sha256(goal.encode()).hexdigest()
        try:
            verified = open(_goal_ok_file(isa_path)).read().strip() == digest
        except OSError:
            verified = False
        if not verified:
            prompts = state.prompts(harness, session)
            if any(goal in p for p in prompts):
                with open(_goal_ok_file(isa_path), "w") as f:
                    f.write(digest + "\n")
                prompts = None
    try:
        text = isafile.normalize(open(isa_path, encoding="utf-8").read())
    except OSError:
        return ["cannot read the ISA"], []
    # hook-side: lint what the commands would leave (progress, nested parents, orphaned generated lines
    # recomputed) without writing it — hooks never write the ISA (SPEC-v2 § 0.3, § 3.1)
    r = lint.lint(isa_path, moment, text=text, prompts=prompts)
    errs, warns = rules.check(isa_path, lint.parse(text, isa_path))  # ledger- and prompt-aware rules
    return [m for lvl, m in r.items if lvl == "ERROR"] + errs, [m for lvl, m in r.items if lvl == "WARN"] + warns


def _status_line(isa_path):
    fm = state.frontmatter(isa_path)
    try:  # computed from the criteria: the frontmatter value may lag until the next `isa` command
        progress = isafile.progress_of(open(isa_path, encoding="utf-8").read())
    except OSError:
        progress = fm.get("progress", "?")
    return (f"ISA bound: {_tilde(isa_path)} — {fm.get('effort', '?')}, phase {fm.get('phase', '?')}, "
            f"progress {progress}")


def _open_iscs(isa_path, limit=40):
    try:
        text = open(isa_path, encoding="utf-8").read()
    except OSError:
        return []
    return [m.group(0).strip() for m in re.finditer(r"^\s*- \[ \] ISC-[\d.]+:.*$", text, re.M)][:limit]


def _goal_section(isa_path):
    try:
        text = open(isa_path, encoding="utf-8").read()
    except OSError:
        return ""
    m = re.search(r"^## Goal\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def _project_listing(cwd, exclude=None):
    rows = []
    for p, fm in state.list_isas(cwd=cwd):
        if p == exclude or fm.get("phase") == "complete":
            continue
        rows.append(f"  - {_tilde(p)} — {fm.get('task', '?')} (phase {fm.get('phase', '?')}, {fm.get('progress', '?')})")
        if len(rows) >= MAX_LISTED:
            break
    return ("Open ISAs in this project (edit one to continue it):\n" + "\n".join(rows)) if rows else ""


def _bound(st):
    p = st.get("bound")
    return p if p and os.path.isfile(p) else None


def _isa_touched(st):
    """True when the bound ISA's mtime moved since the engine last looked; records the new mtime.
    The first look (no baseline yet, e.g. state written by an older engine) only records."""
    p = _bound(st)
    try:
        m = os.path.getmtime(p) if p else None
    except OSError:
        m = None
    seen = st.get("isa_mtime")
    st["isa_mtime"] = m
    return m is not None and seen is not None and m != seen


def _fmt(errors, limit=12):
    more = f"\n  … and {len(errors) - limit} more (run `isa lint <path>`)" if len(errors) > limit else ""
    return "\n".join(f"  - {e}" for e in errors[:limit]) + more


# ------------------------------------------------------------------ events

def handle(ev):
    if os.environ.get("ISA_JUDGE_CHILD"):
        return {}  # the judge's own session: no ISA hook at all (judge.py)
    if _mode_env() == "off":
        if ev.get("event") == "prompt":
            _log_judge(ev, {"verdict": "no", "reason": "ISA_MODE=off", "source": "override", "ms": 0,
                            "backend": "override"})
        return {}
    fn = {
        "session_start": _session_start, "prompt": _prompt, "pre_tool": _pre_tool,
        "post_tool": _post_tool, "tool_failed": _tool_failed, "stop": _stop, "compacted": _compacted,
    }.get(ev.get("event"))
    return fn(ev) if fn else {}


# ------------------------------------------------------------------ mode

NO_ISA = ("No ISA yet. Write it now (`isa new <slug> --goal \"<span>\"`, then Goal, Criteria, Test Strategy). "
          "If you are asking the user to clarify before you can define done, run `isa new`, write the Goal and "
          "your questions under Decisions, and set `context_sufficient: false` — that is enough to end the turn.")


def _mode_env():
    m = (os.environ.get("ISA_MODE") or "auto").strip().lower()
    return m if m in ("on", "off") else "auto"


def _mode(st):
    """on | off. A session file without `mode` (v1, or nothing decided yet) is ON exactly when an open
    ISA is bound to it."""
    if _mode_env() != "auto":
        return _mode_env()
    if st.get("mode") in ("on", "off"):
        return st["mode"]
    b = _bound(st)
    return "on" if b and state.frontmatter(b).get("phase") != "complete" else "off"


def _switch_on(st, source, reason):
    """Record the OFF → ON transition (ON is sticky). → True when this call switched it."""
    if st.get("mode") == "on":
        return False
    st.update(mode="on", mode_source=source, mode_reason=reason, mode_since=time.time())
    return True


def _log_judge(ev, v):
    row = {"t": time.time(), "harness": ev.get("harness"), "session": ev.get("session"),
           "prompt_id": ev.get("prompt_id"), "source": v["source"], "verdict": v["verdict"],
           "reason": v["reason"], "ms": v["ms"], "backend": v.get("backend")}
    with open(os.path.join(state.state_dir(), "judge.jsonl"), "a") as f:
        f.write(json.dumps(row) + "\n")


def _on_block(cwd):
    listing = _project_listing(cwd)
    return protocol(cwd) + ("\n" + listing if listing else "")


def _assistant_context(ev):
    if ev.get("context"):
        return str(ev["context"])[-judge.CONTEXT_CHARS:]
    return judge.last_assistant_text(ev.get("transcript_path"))


def _scaffold(path):
    """The clarify-first shape: observe, context_sufficient: false, a Goal, a question in Decisions,
    no Criteria yet."""
    p = _parsed(path)
    if not p:
        return False
    fm, c = p["fm"], p["content"]
    return (fm.get("phase") == "observe" and fm.get("context_sufficient") is False and bool(c.get("Goal", "").strip())
            and not p["iscs"] and any(line.rstrip().endswith("?") for line in c.get("Decisions", "").splitlines()))


def _needs_isa(st, bound, pid):
    """True when an ON turn may not end yet for lack of an ISA; "scaffold" when the clarify-first
    scaffold may end it (only on the prompt that created it); False otherwise."""
    if not bound:
        return True
    phase = state.frontmatter(bound).get("phase")
    if st.get("needs_isa_since") and phase == "complete":
        return True
    if _scaffold(bound):
        return "scaffold" if st.get("bound_prompt") == pid else True
    return False


def _session_start(ev):
    cwd = ev.get("cwd")
    with state.session(ev["harness"], ev["session"]) as st:
        bound = _bound(st)
        compact = ev.get("source") == "compact" or st.get("compacted")
        st["compacted"] = False
        mode = _mode(st)
        no_isa_blocked = st.get("blocked_no_isa")
    if mode != "on":
        return {}  # OFF or undecided: nothing from the ISA system reaches the model
    parts = [protocol(cwd)]
    if no_isa_blocked:
        parts.append("Blocked from an earlier turn: it ended without an ISA — write it now (`isa new …`).")
    if bound:
        parts.append(_status_line(bound))
        still = problems.open_items(bound)
        if still:
            parts.append("Still blocked from an earlier turn (fix them; `isa verify` / `isa lint` clear what holds "
                         "no more, and `isa close` refuses until then):\n" + problems.describe(still))
        if compact:
            parts.append("Goal (re-injected after compaction):\n" + _goal_section(bound))
            iscs = _open_iscs(bound)
            if iscs:
                parts.append("Open ISCs:\n" + "\n".join(iscs))
    listing = _project_listing(cwd, exclude=bound)
    if listing:
        parts.append(listing)
    return {"context": "\n\n".join(parts)}


def _compacted(ev):
    with state.session(ev["harness"], ev["session"]) as st:
        st["compacted"] = True
    return {}


def _prompt(ev):
    cwd, pid, prompt = ev.get("cwd"), ev.get("prompt_id"), ev.get("prompt", "")
    context = _assistant_context(ev)
    state.log_prompt(ev["harness"], ev["session"], prompt, pid, cwd=cwd, project=state.project_key(cwd),
                     context=context)
    with state.session(ev["harness"], ev["session"]) as st:
        st["prompt_started"] = time.time()  # Stop only checks turns where something happened after this
        mode = _mode(st)
        forced = mode == "on" and _switch_on(st, "override" if _mode_env() == "on" else "binding",
                                             "ISA_MODE=on" if _mode_env() == "on" else "open ISA bound (v1 session)")
        bound = _bound(st)
    complete = bool(bound) and state.frontmatter(bound).get("phase") == "complete"
    if mode == "on":
        if forced and _mode_env() == "on":
            return {"context": _on_block(cwd)}
        if not complete:
            if bound:
                return {"context": _status_line(bound) + ". A new task gets a new ISA; continuing work keeps this one."}
            return {"context": "ISA: ON — no ISA bound yet: write it before the work (`isa new <slug> --goal \"…\"`)."}
    # OFF, or ON with only a finished ISA bound: judge this prompt
    v = judge.gate(prompt, context=context, harness=ev.get("harness"))
    _log_judge(ev, v)
    with state.session(ev["harness"], ev["session"]) as st:
        note = ""
        if v.get("note") and not st.get("judge_note_shown"):
            st["judge_note_shown"] = True
            note = "\n" + v["note"]
        if mode == "on":  # a finished ISA is bound
            if v["verdict"] == "yes":
                st["needs_isa_since"] = pid
                return {"context": f"{_status_line(bound)}. This prompt is a new task: new ISA, or reopen the "
                                   "finished one (`phase: learn`, `iteration`, `resumed_at`, a `refined:` Decision)."}
            st.pop("needs_isa_since", None)
            return {"context": _status_line(bound) + "."}
        if v["verdict"] == "no":
            st.update(mode="off", mode_source=v["source"], mode_reason=v["reason"])
            return {"warn": f"ISA: OFF — {v['reason']}{note}"}
        _switch_on(st, v["source"], v["reason"])
    return {"warn": f"ISA: ON — {v['reason']}{note}", "context": _on_block(cwd)}


def _pre_tool(ev):
    kind, _isa = classify.classify(ev.get("tool", ""), ev.get("tool_input"), ev.get("cwd"), ev.get("temp_dirs", ()))
    if _targets_ledger(ev, kind):
        return {"deny": "ISA evidence gate: the evidence ledger (~/.isa/_state/evidence/) is written only by "
                        "`isa verify`. Run the probe through `isa verify <ISA> ISC-N` instead."}
    if kind == "isa-cmd":
        return {}  # `isa new|lint|verify|close`: how the model writes the engine-owned state — never gated
    if kind == "isa-shell-edit":
        return {"deny": "ISA ownership: edit an ISA.md with Write/Edit, not a shell command — the hooks check "
                        "Write/Edit against the engine-owned fields (ticks, generated Verification lines, "
                        "progress, root, phase: complete); `isa verify` / `isa close` write those."}
    st = state.read_session(ev["harness"], ev["session"])
    refused = _ownership_refusal(ev)
    if refused:
        return {"deny": refused}
    if kind == "read":
        return {}
    cwd = ev.get("cwd")
    if _mode(st) == "off":
        if kind == "write":  # the gate said no, but a change is evidence: ON, and this change waits for its ISA
            with state.session(ev["harness"], ev["session"]) as s:
                _switch_on(s, "write", "a change was attempted")
            return {"deny": "ISA: ON — this change needs an ISA first.\n\n" + _on_block(_target_base(ev) or cwd),
                    "warn": "ISA: ON — a change was attempted"}
        # unknown: it runs; only a change it actually makes switches the session ON (post_tool)
        _snapshot_unknown(ev, kind, cwd)
        return {}
    bound = _bound(st)
    if not bound:
        base = _target_base(ev) or cwd  # file the ISA where the change lands, not where the session started
        listing = _project_listing(base)
        return {"deny": (
            f"ISA gate: this {kind} call is refused because no ISA is bound to this session yet. "
            f"Write the ISA first — e.g. {_tilde(state.new_isa_path(base, 'your-task'))} "
            f"(read {_tilde(skill_dir())}/SKILL.md and the closest example first; E1 = `## Goal` + `## Criteria` "
            "with ≥1 `Anti:` ISC). Writing it binds it to this session; then retry this call."
            + ("\n" + listing if listing else ""))}
    if state.frontmatter(bound).get("phase") == "complete":
        # a finished ISA is not a current task: never re-gate it against today's rules
        return {"deny": (
            f"ISA gate: the bound ISA {_tilde(bound)} is complete, so this {kind} call has no open task. "
            f"For new work write a new ISA — e.g. {_tilde(state.new_isa_path(cwd, 'your-task'))}. To continue "
            "the finished work instead, reopen it: set `phase: learn`, increment `iteration`, add `resumed_at` "
            "and a `refined: reopened after complete — <why>` Decision. Then retry this call.")}
    errors, _ = _lint(bound, "articulation", ev["harness"], ev["session"])
    if errors:
        return {"deny": f"ISA gate: {_tilde(bound)} does not pass the articulation gate yet, so building is refused. "
                        f"Fix the ISA, then retry:\n{_fmt(errors)}"}
    _snapshot_unknown(ev, kind, cwd)
    return {}


def _snapshot_unknown(ev, kind, cwd):
    """Before an `unknown` shell command: snapshot the project so post_tool can tell whether it changed files."""
    if ev.get("tool") in classify.SHELL_TOOLS and kind == "unknown" and not state.is_scratch_dir(cwd):
        snap = changes.snapshot(state.project_root(cwd))
        if snap:
            with state.session(ev["harness"], ev["session"]) as s:
                snaps = s.setdefault("shell_snaps", {})
                snaps[_call_key(ev)] = snap
                for k in list(snaps)[:-20]:
                    snaps.pop(k, None)


# ------------------------------------------------------------------ evidence

def _parsed(path, text=None):
    try:
        return lint.parse(open(path, encoding="utf-8").read() if text is None else text, path)
    except OSError:
        return None


def _targets_ledger(ev, kind):
    """A write aimed at the evidence ledger: any file-tool write there, or a non-read shell command naming it."""
    tool, ti, cwd = ev.get("tool", ""), ev.get("tool_input") or {}, ev.get("cwd") or ""
    if tool in classify.FILE_TOOLS:
        return any(evidence.is_ledger_path(os.path.join(cwd, os.path.expanduser(p))) for p in classify.tool_paths(ti))
    if tool in classify.SHELL_TOOLS and kind != "read":
        return bool(re.search(r"_state[/\\]+evidence", str(ti.get("command", ""))))
    return False


def _proposed(tool, ti, current):
    """The text a file-tool call would leave in the file, or None when it can't be worked out."""
    if tool in ("Write", "write"):
        return ti.get("content") if isinstance(ti.get("content"), str) else None
    if tool == "Edit":
        edits = [(ti.get("old_string"), ti.get("new_string"), ti.get("replace_all"))]
    elif tool == "MultiEdit":
        edits = [(e.get("old_string"), e.get("new_string"), e.get("replace_all"))
                 for e in ti.get("edits") or [] if isinstance(e, dict)]
    elif tool == "edit":  # pi: {path, edits: [{oldText, newText}]} (sometimes a JSON string or one object)
        raw = ti.get("edits")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                return None
        if isinstance(raw, dict):
            raw = [raw]
        if raw is None and "oldText" in ti:
            raw = [ti]
        edits = [(e.get("oldText"), e.get("newText"), False) for e in raw or [] if isinstance(e, dict)]
    else:
        return None
    text = current
    for old, new, every in edits:
        if not isinstance(old, str) or not isinstance(new, str) or old not in text:
            return None
        text = text.replace(old, new) if every else text.replace(old, new, 1)
    return text


def _ownership_refusal(ev):
    """Refusal text when a model Write/Edit of an ISA.md would touch an engine-owned field (SPEC-v2 § 3.1):
    tick a box, add or change a generated Verification line, set `phase: complete`, change `root`, or
    write a `progress` that is neither the old value nor the right one. None otherwise."""
    tool, ti, cwd = ev.get("tool", ""), ev.get("tool_input") or {}, ev.get("cwd") or ""
    if tool not in classify.FILE_TOOLS:
        return None
    for p in classify.tool_paths(ti):
        path = os.path.realpath(os.path.join(cwd, os.path.expanduser(p)))
        if not state.is_master_isa(path):
            continue
        try:
            current = open(path, encoding="utf-8").read()
        except OSError:
            current = ""
        new = _proposed(tool, ti, current)
        if new is None:
            continue  # can't tell beforehand; the post-edit lint and Stop still catch it
        why = _ownership_diff(path, current, new)
        if why:
            return f"ISA ownership: {why}"
    return None


def _ownership_diff(path, old, new):
    po = lint.parse(old, path) if old else None
    pn = lint.parse(new, path)
    before = {i for i, (c, _, _) in po["iscs"].items() if c} if po else set()
    newly = [i for i, (c, _, _) in pn["iscs"].items() if c and i not in before]
    if newly:
        ids = " ".join(newly)
        return (f"this edit ticks {', '.join(newly)} — ticks are written by `isa verify`, which runs the probe "
                f"and ticks what passes: `isa verify {_tilde(path)} {ids}` (self-attested criteria: "
                f"`isa verify {_tilde(path)} ISC-N --attest \"<evidence>\"`). Unticking is allowed.")
    go, gn = isafile.generated_lines(old) if old else {}, isafile.generated_lines(new)
    changed = sorted(i for i in gn if go.get(i) != gn[i])
    if changed:
        return (f"this edit adds or changes the generated Verification line of {', '.join(changed)} — those "
                "lines (`verified` / `attested` / `regressed`) are written by `isa verify` from the ledger. "
                "`[DEFERRED-VERIFY]`, `- Goal:` and `- Ask N:` lines are yours.")
    fo, fn = (po["fm"] if po else {}), pn["fm"]
    if fn.get("phase") == "complete" and fo.get("phase") != "complete":
        return f"`phase: complete` is written by `isa close {_tilde(path)}`, which re-runs every probe first."
    if po and str(fo.get("root")) != str(fn.get("root")):
        keep = f"keep the line `root: {fo.get('root')}`" if fo.get("root") else "leave `root:` out"
        return (f"`root:` is engine-owned (written by `isa new`, used as every probe's cwd) — {keep} "
                "in your edit.")
    if "progress" in fn and str(fn["progress"]) != str(fo.get("progress")) \
            and str(fn["progress"]) != isafile.progress_of(new):
        return (f"`progress: {fn['progress']}` is not what the criteria say ({isafile.progress_of(new)}) — "
                "leave `progress` to the engine: `isa lint`, `isa verify` and `isa close` recompute it.")
    return None


def _call_key(ev):
    """Pairs a tool call's Pre and Post hooks: the harness's call id, else a hash of the command."""
    if ev.get("tool_use_id"):
        return str(ev["tool_use_id"])
    return hashlib.sha256(str((ev.get("tool_input") or {}).get("command", "")).encode()).hexdigest()[:16]


def _script_changed(ev, st):
    """An `unknown` shell command (a heredoc script, `node -e`, a build) changed project files."""
    snap = st.get("shell_snaps", {}).pop(_call_key(ev), None)
    return bool(snap) and changes.changed(snap, state.project_root(ev.get("cwd")))


def _target_base(ev):
    """Directory of the first project file a file tool is about to change (None for shell / other tools)."""
    if ev.get("tool") not in classify.FILE_TOOLS:
        return None
    for p in classify.tool_paths(ev.get("tool_input")):
        full = p if os.path.isabs(os.path.expanduser(p)) else os.path.join(ev.get("cwd") or "", p)
        if classify.path_kind(full, ev.get("cwd"), ev.get("temp_dirs", ())) == "project":
            return os.path.dirname(os.path.realpath(os.path.expanduser(full)))
    return None


def _changed_projects(ev, kind):
    """Project keys a counted change landed in: by file path for file tools, by cwd for shell commands."""
    if ev.get("tool") in classify.FILE_TOOLS:
        base = _target_base(ev)
        return [state.project_key(base)] if base else []
    return [state.project_key(ev.get("cwd"))]


def _count_change(st, now, out):
    st["last_mutation"] = now
    st["mutations"] += 1
    st["since_isa"] += 1
    if st["since_isa"] % STALE_NUDGE_EVERY == 0 and _bound(st):
        out.append(f"{st['since_isa']} changes since the ISA was last updated — fold what you learned "
                   "into it now (tick verified ISCs with evidence, add/split ISCs, keep progress true).")


def _is_verify(ev):
    return ev.get("tool") in classify.SHELL_TOOLS and \
        bool(re.search(r"(^|[\s;&|(/])isa\s+verify\b", str((ev.get("tool_input") or {}).get("command", ""))))


def _bind(st, path, ev, out):
    """Bind `path` to the session (a Write/Edit of it, or `isa new` printing it). → the user line, or ""."""
    if st.get("bound") != path:
        if st.get("bound"):
            out.append(f"ISA binding switched to {_tilde(path)} (was {_tilde(st['bound'])}).")
        st["bound"] = path
        st["bound_prompt"] = ev.get("prompt_id")  # the scaffold exit holds on this prompt only
        hist = st.setdefault("bound_history", [])  # waivers quote prompts of every session an ISA was bound to
        if path not in hist:
            hist.append(path)
    if state.frontmatter(path).get("phase") != "complete":
        st.pop("needs_isa_since", None)
        st.pop("blocked_no_isa", None)
    return "ISA: ON — an ISA was bound" if _switch_on(st, "binding", "an ISA was bound") else ""


def _printed_isa(output):
    """The ISA.md path `isa new` printed (the last one in the output), or None."""
    for m in reversed(re.findall(r"(?<!\S)(/\S+/ISA\.md)\b", str(output or ""))):
        if state.is_master_isa(m) and os.path.isfile(m):
            return os.path.realpath(m)
    return None


def _post_isa_cmd(ev):
    """After `isa new|lint|verify|close`: the engine may have written the bound ISA — refresh its mtime
    baseline so that is never taken for a model shell edit; `isa new` binds the path it printed."""
    command = str((ev.get("tool_input") or {}).get("command", ""))
    out, warn, bound = [], "", None
    with state.session(ev["harness"], ev["session"]) as st:
        if re.search(r"(^|[\s;&|(/])isa\s+new\b", command) and "--path-only" not in command:
            path = _printed_isa(ev.get("tool_output"))
            if path:
                warn = _bind(st, path, ev, out)
                st["last_isa_edit"] = time.time()
                st["since_isa"] = 0
                bound = path
        _isa_touched(st)
    if bound:
        errors, _ = _lint(bound, "auto", ev["harness"], ev["session"])
        goal = [e for e in errors if "stated_goal" in e]
        out.append(f"ISA bound: {_tilde(bound)} — now write Problem/Goal/Criteria/Test Strategy with Write/Edit, "
                   "then `isa lint` it." + (f"\n{_fmt(goal)}" if goal else ""))
    res = {"context": "\n".join(out)} if out else {}
    if warn:
        res["warn"] = warn
    return res


def _post_tool(ev):
    tool, ti, cwd = ev.get("tool", ""), ev.get("tool_input") or {}, ev.get("cwd")
    kind, isa_paths = classify.classify(tool, ti, cwd, ev.get("temp_dirs", ()))
    if kind == "isa-cmd":
        return _post_isa_cmd(ev)
    masters = [p for p in isa_paths if state.is_master_isa(os.path.join(cwd or "", os.path.expanduser(p)))]
    now = time.time()
    out, touched, warn = [], [], ""
    with state.session(ev["harness"], ev["session"]) as st:
        was_off = _mode(st) == "off"
        # the bound ISA changed on disk without a file-tool path naming it (a shell edit: heredoc,
        # `sed -i`, a script): that call was an ISA edit, not a project change
        shell_edit = not masters and _isa_touched(st)
        if masters:
            path = os.path.realpath(os.path.join(cwd or "", os.path.expanduser(masters[-1])))
            warn = _bind(st, path, ev, out)
            st["last_isa_edit"] = now
            st["since_isa"] = 0
            _isa_touched(st)  # baseline mtime for the next shell-edit check
        elif shell_edit:
            st["last_isa_edit"] = now
            st["since_isa"] = 0
            if kind == "unknown" and tool in classify.SHELL_TOOLS and _script_changed(ev, st):
                _count_change(st, now, out)  # one script edited the ISA and project files
        elif isa_paths:
            st["last_isa_edit"] = now  # ephemeral slice or probe file inside the ISA folder
        elif kind == "write" or (kind == "unknown" and tool in classify.SHELL_TOOLS and _script_changed(ev, st)):
            _count_change(st, now, out)
            touched = _changed_projects(ev, kind)
            if was_off and _switch_on(st, "change", "a command changed project files"):
                warn = "ISA: ON — a command changed project files; the turn needs an ISA before it ends"
        bound = _bound(st)
    if bound:
        for key in touched:
            if state.note_project(bound, key) and key != state.isa_home_key(bound):
                out.append(f"This ISA now also covers project `{key}` (changed files there); "
                           f"`isa ls` in that project lists it.")
    if (masters or shell_edit) and bound:
        errors, warns = _lint(bound, "auto", ev["harness"], ev["session"])
        if errors:
            out.append(f"ISA lint — {len(errors)} error(s) in {_tilde(bound)}:\n{_fmt(errors)}")
        else:
            out.append(_status_line(bound) + " — lint ok" + (f" ({len(warns)} warning(s))" if warns else "") + ".")
    if bound and (masters or shell_edit):
        parsed = _parsed(bound)
        if parsed:
            bad = evidence.unproven_ticks(bound, parsed)
            if bad:
                out.append("ISA evidence — ticked without a passing `isa verify` run (only `isa verify` ticks; "
                           "untick these):\n" + evidence.describe(bad))
            order = evidence.blocked(parsed, sorted(evidence.ticked(parsed)))
            if order:
                out.append("ISA order — ticked out of dependency order (untick until the dependency is done):\n"
                           + evidence.describe_blocked(order))
    res = {"context": "\n".join(out)} if out else {}
    if warn:
        res["warn"] = warn
    return res


def _tool_failed(ev):
    if ev.get("tool") in classify.SHELL_TOOLS:
        kind, _ = classify.classify(ev.get("tool", ""), ev.get("tool_input"), ev.get("cwd"), ev.get("temp_dirs", ()))
        if kind == "unknown":  # a script that failed halfway may still have written files
            with state.session(ev["harness"], ev["session"]) as st:
                if _script_changed(ev, st):
                    _count_change(st, time.time(), [])
    st = state.read_session(ev["harness"], ev["session"])
    if _bound(st) and _is_verify(ev):
        return {"context": "A probe failed. Claim wrong or code wrong? If the claim, update the ISA now (split, "
                           "tighten, or add an ISC; log a Decision); if the code, fix it and run `isa verify` again."}
    if _bound(st) and ev.get("tool") in classify.SHELL_TOOLS:
        return {"context": "A command failed — fold what the failure taught you into the ISA (split, tighten, "
                           "or add an ISC; log a Decision)."}
    return {}


def _attested_notice(st, bound):
    """On a clean close, tell the user (once per ISA content) which ticks no machine checked."""
    if not bound or state.frontmatter(bound).get("phase") != "complete":
        return {}
    try:
        with open(bound, "rb") as f:
            key = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return {}
    if st.get("attested_warned") == key:
        return {}
    st["attested_warned"] = key
    parsed = _parsed(bound)
    items = evidence.self_attested_ticks(parsed) if parsed else []
    if not items:
        return {}
    rows = "\n".join(f"  - {i} ({typ}): {parsed['iscs'][i][1]}" for i, typ in items)
    return {"warn": f"ISA closed: {_tilde(bound)}. Not machine-verified — the agent attested these itself; "
                    f"check them:\n{rows}"}


def _stop(ev):
    pid = str(ev.get("prompt_id") or "_")
    with state.session(ev["harness"], ev["session"]) as st:
        if _mode(st) != "on":
            return {}  # OFF: the gate said this is no task
        bound = _bound(st)
        if _isa_touched(st):  # edited by a call whose PostToolUse never ran (e.g. a failed command)
            st["last_isa_edit"] = time.time()
        need = _needs_isa(st, bound, ev.get("prompt_id"))
        if need == "scaffold":
            return {}  # the clarify-first scaffold, on the prompt that created it
        started = st.get("prompt_started", 0.0)
        if need is not True and started and st["last_mutation"] < started and st["last_isa_edit"] < started:
            return {}  # nothing happened this turn: nothing to check
    items = []
    if need is True:  # checked even on a turn that changed nothing: a review is work too
        items.append({"code": "no-isa", "isc": None, "line": NO_ISA})
        bound = None if not bound or _scaffold(bound) or state.frontmatter(bound).get("phase") == "complete" \
            else bound
    if bound:  # reads the ISA, the ledger and session state only — never runs a probe
        errors, _ = _lint(bound, "auto", ev["harness"], ev["session"])
        items += problems.current(bound, lint_errors=errors)
    with state.session(ev["harness"], ev["session"]) as st:
        if not items:
            return _attested_notice(st, bound)
        already = st["stop_blocks"].get(pid, 0) >= 1 or ev.get("retried")
        st["stop_blocks"][pid] = st["stop_blocks"].get(pid, 0) + 1
        if len(st["stop_blocks"]) > 50:
            for k in sorted(st["stop_blocks"])[:-50]:
                st["stop_blocks"].pop(k, None)
        if already and any(it["code"] == "no-isa" for it in items):
            st["blocked_no_isa"] = pid  # an ISA-less problem has no ledger: it lives in the session
    text = "ISA check before ending the turn:\n" + "\n".join(f"- {p}" for p in problems.render(items))
    if already:
        if bound:  # escalate: the open problems outlive the turn (SPEC-v2 § 4.5) — in the ledger, never the ISA
            problems.record_blocked(bound, items)
        return {"warn": "ISA still not true after one retry — ending the turn anyway; these stay recorded as "
                        "blocked (shown at the next start, `isa close` refuses until they are fixed).\n" + text}
    return {"block": text}
