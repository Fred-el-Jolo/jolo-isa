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

Result (dict, all keys optional):
    context     text for the model
    deny        pre_tool: reason the call is refused
    block       stop: reason the turn must continue
    warn        text for the user (not the model)
"""
import hashlib
import json
import os
import re
import time

from . import changes, classify, evidence, fit, lint, state

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
    r = lint.lint(isa_path, moment, prompts=prompts)
    return [m for lvl, m in r.items if lvl == "ERROR"], [m for lvl, m in r.items if lvl == "WARN"]


def _status_line(isa_path):
    fm = state.frontmatter(isa_path)
    return (f"ISA bound: {_tilde(isa_path)} — {fm.get('effort', '?')}, phase {fm.get('phase', '?')}, "
            f"progress {fm.get('progress', '?')}")


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
    fn = {
        "session_start": _session_start, "prompt": _prompt, "pre_tool": _pre_tool,
        "post_tool": _post_tool, "tool_failed": _tool_failed, "stop": _stop, "compacted": _compacted,
    }.get(ev.get("event"))
    return fn(ev) if fn else {}


def _session_start(ev):
    cwd = ev.get("cwd")
    with state.session(ev["harness"], ev["session"]) as st:
        bound = _bound(st)
        compact = ev.get("source") == "compact" or st.get("compacted")
        st["compacted"] = False
    parts = [protocol(cwd)]
    if bound:
        parts.append(_status_line(bound))
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
    state.log_prompt(ev["harness"], ev["session"], ev.get("prompt", ""), ev.get("prompt_id"))
    st = state.read_session(ev["harness"], ev["session"])
    bound = _bound(st)
    level, reasons = fit.score(ev.get("prompt", ""))
    # an open bound ISA means the prompt most likely continues it: no fit advice then
    open_bound = bound and state.frontmatter(bound).get("phase") != "complete"
    note = "" if open_bound else fit.advice(level, reasons, bound=bound)
    if bound:
        text = _status_line(bound) + ". A new task gets a new ISA; continuing work keeps this one."
    else:
        text = ("No ISA bound in this session yet: the first file change or other mutation will be "
                f"refused until one exists under {_tilde(state.project_dir(ev.get('cwd')))}/.")
    return {"context": text + ("\n" + note if note else "")}


def _pre_tool(ev):
    kind, _isa = classify.classify(ev.get("tool", ""), ev.get("tool_input"), ev.get("cwd"), ev.get("temp_dirs", ()))
    if _targets_ledger(ev, kind):
        return {"deny": "ISA evidence gate: the evidence ledger (~/.isa/_state/evidence/) is written only by "
                        "`isa verify`. Run the probe through `isa verify <ISA> ISC-N` instead."}
    st = state.read_session(ev["harness"], ev["session"])
    refused = _tick_gate(ev, st)
    if refused:
        return {"deny": refused}
    if kind == "read":
        return {}
    bound = _bound(st)
    cwd = ev.get("cwd")
    if not bound:
        listing = _project_listing(cwd)
        return {"deny": (
            f"ISA gate: this {kind} call is refused because no ISA is bound to this session yet. "
            f"Write the ISA first — e.g. {_tilde(state.new_isa_path(cwd, 'your-task'))} "
            f"(read {_tilde(skill_dir())}/SKILL.md and the closest example first; E1 = `## Goal` + `## Criteria` "
            "with ≥1 `Anti:` ISC). Writing it binds it to this session; then retry this call."
            + ("\n" + listing if listing else ""))}
    errors, _ = _lint(bound, "articulation", ev["harness"], ev["session"])
    if errors:
        return {"deny": f"ISA gate: {_tilde(bound)} does not pass the articulation gate yet, so building is refused. "
                        f"Fix the ISA, then retry:\n{_fmt(errors)}"}
    parsed = _parsed(bound)
    pending = evidence.pending_ticks(bound, parsed, st.get("last_mutation", 0.0)) if parsed else []
    if pending:
        return {"deny": f"ISA evidence gate: {', '.join(pending)} passed `isa verify` but "
                        f"{'is' if len(pending) == 1 else 'are'} not ticked in {_tilde(bound)}. Tick "
                        f"{'it' if len(pending) == 1 else 'them'} (with the Verification line `isa verify` printed) "
                        "before moving on to the next change."}
    if ev.get("tool") in classify.SHELL_TOOLS and kind == "unknown":
        snap = changes.snapshot(state.project_root(cwd))
        if snap:
            with state.session(ev["harness"], ev["session"]) as s:
                snaps = s.setdefault("shell_snaps", {})
                snaps[_call_key(ev)] = snap
                for k in list(snaps)[:-20]:
                    snaps.pop(k, None)
    return {}


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


def _tick_gate(ev, st):
    """Refusal text when a file-tool call would tick a mechanical ISC that has no passing `isa verify`
    run newer than the session's last project change; None otherwise."""
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
            continue  # can't tell beforehand; the post-edit check and Stop still catch it
        before = evidence.ticked(lint.parse(current, path)) if current else set()
        after = lint.parse(new, path)
        newly = [i for i in after["counted"] if i in evidence.ticked(after) and i not in before]
        order = evidence.blocked(after, newly, treat_open=newly)
        if order:
            return ("ISA order gate: this edit ticks ISCs whose Feature depends on unfinished Features — "
                    f"finish (verify and tick) the dependency first, in an earlier edit:\n{evidence.describe_blocked(order)}")
        bad = evidence.unproven(path, after, newly, since=st.get("last_mutation", 0.0))
        if bad:
            ids = " ".join(i for i, _ in bad)
            return (f"ISA evidence gate: this edit ticks ISCs that are not proven — an ISC is ticked only after "
                    f"its probe passes through `isa verify`, after the last project change:\n{evidence.describe(bad)}\n"
                    f"Run `isa verify {_tilde(path)} {ids}`, then tick what passed.")
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


def _post_tool(ev):
    tool, ti, cwd = ev.get("tool", ""), ev.get("tool_input") or {}, ev.get("cwd")
    kind, isa_paths = classify.classify(tool, ti, cwd, ev.get("temp_dirs", ()))
    masters = [p for p in isa_paths if state.is_master_isa(os.path.join(cwd or "", os.path.expanduser(p)))]
    now = time.time()
    out = []
    with state.session(ev["harness"], ev["session"]) as st:
        # the bound ISA changed on disk without a file-tool path naming it (a shell edit: heredoc,
        # `sed -i`, a script): that call was an ISA edit, not a project change
        shell_edit = not masters and _isa_touched(st)
        if masters:
            path = os.path.realpath(os.path.join(cwd or "", os.path.expanduser(masters[-1])))
            if st.get("bound") != path:
                if st.get("bound"):
                    out.append(f"ISA binding switched to {_tilde(path)} (was {_tilde(st['bound'])}).")
                st["bound"] = path
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
        bound = _bound(st)
        last_mutation = st["last_mutation"]
    if (masters or shell_edit) and bound:
        errors, warns = _lint(bound, "auto", ev["harness"], ev["session"])
        if errors:
            out.append(f"ISA lint — {len(errors)} error(s) in {_tilde(bound)}:\n{_fmt(errors)}")
        else:
            out.append(_status_line(bound) + " — lint ok" + (f" ({len(warns)} warning(s))" if warns else "") + ".")
    if bound and (masters or shell_edit or _is_verify(ev)):
        parsed = _parsed(bound)
        if parsed and (masters or shell_edit):
            bad = evidence.unproven_ticks(bound, parsed)
            if bad:
                out.append("ISA evidence — ticked without a passing `isa verify` run (verify or untick):\n"
                           + evidence.describe(bad))
            order = evidence.blocked(parsed, sorted(evidence.ticked(parsed)))
            if order:
                out.append("ISA order — ticked out of dependency order (untick until the dependency is done):\n"
                           + evidence.describe_blocked(order))
        pending = evidence.pending_ticks(bound, parsed, last_mutation) if parsed else []
        if pending:
            out.append(f"Passed `isa verify`, not ticked yet: {', '.join(pending)} — tick now, with their "
                       "Verification lines; other changes are refused until you do.")
    return {"context": "\n".join(out)} if out else {}


def _tool_failed(ev):
    if ev.get("tool") in classify.SHELL_TOOLS:
        kind, _ = classify.classify(ev.get("tool", ""), ev.get("tool_input"), ev.get("cwd"), ev.get("temp_dirs", ()))
        if kind == "unknown":  # a script that failed halfway may still have written files
            with state.session(ev["harness"], ev["session"]) as st:
                if _script_changed(ev, st):
                    _count_change(st, time.time(), [])
    st = state.read_session(ev["harness"], ev["session"])
    if _bound(st) and ev.get("tool") in classify.SHELL_TOOLS:
        return {"context": "A command failed. If it was an ISC probe, that ISC stays unticked — fold what the "
                           "failure taught you into the ISA (split, tighten, or add an ISC; log a Decision)."}
    return {}


def _evidence_problems(bound, last_mutation, closing):
    parsed = _parsed(bound)
    if not parsed:
        return []
    out = []
    bad = evidence.unproven_ticks(bound, parsed)
    if bad:
        out.append("ticked without a passing `isa verify` run — verify or untick:\n" + evidence.describe(bad))
    order = evidence.blocked(parsed, sorted(evidence.ticked(parsed)))
    if order:
        out.append("ticked out of dependency order — untick until the dependency is done:\n"
                   + evidence.describe_blocked(order))
    pending = evidence.pending_ticks(bound, parsed, last_mutation)
    if pending:
        out.append(f"`isa verify` passed for {', '.join(pending)} but the ISA does not tick "
                   f"{'it' if len(pending) == 1 else 'them'} — tick with the Verification lines, keep `progress` true")
    if closing:
        seen = {i for i, _ in bad}
        stale = [x for x in evidence.unproven_ticks(bound, parsed, since=last_mutation) if x[0] not in seen]
        if stale:
            out.append(f"closing needs every probe re-proven after the last project change — run "
                       f"`isa verify {_tilde(bound)}`:\n" + evidence.describe(stale))
    return out


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
        bound = _bound(st)
        if _isa_touched(st):  # edited by a call whose PostToolUse never ran (e.g. a failed command)
            st["last_isa_edit"] = time.time()
        problems = []
        if st["mutations"] and not bound:
            problems.append("project files were changed but no ISA is bound to this session — write one now "
                            "that records what was done and how it was verified")
        if bound:
            if st["last_mutation"] > st["last_isa_edit"]:
                problems.append("project files changed after the ISA's last update — tick what is verified "
                                "(with `## Verification` lines), add what you learned, and set `phase` / "
                                "`progress` to the truth before stopping")
            errors, _ = _lint(bound, "auto", ev["harness"], ev["session"])
            closing = state.frontmatter(bound).get("phase") == "complete"
            if errors:
                what = "the close gate (`phase: complete`)" if closing else "lint"
                problems.append(f"{_tilde(bound)} fails {what}:\n{_fmt(errors)}")
            problems += _evidence_problems(bound, st["last_mutation"], closing)
        if not problems:
            return _attested_notice(st, bound)
        already = st["stop_blocks"].get(pid, 0) >= 1 or ev.get("retried")
        st["stop_blocks"][pid] = st["stop_blocks"].get(pid, 0) + 1
        if len(st["stop_blocks"]) > 50:
            for k in sorted(st["stop_blocks"])[:-50]:
                st["stop_blocks"].pop(k, None)
    text = "ISA check before ending the turn:\n" + "\n".join(f"- {p}" for p in problems)
    if already:
        return {"warn": "ISA still not true after one retry — ending the turn anyway.\n" + text}
    return {"block": text}
