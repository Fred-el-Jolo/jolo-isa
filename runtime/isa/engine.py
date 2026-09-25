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
import os
import re
import time

from . import classify, lint, state

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
    if bound:
        return {"context": _status_line(bound) + ". A new task gets a new ISA; continuing work keeps this one."}
    return {"context": "No ISA bound in this session yet: the first file change or other mutation will be "
                       f"refused until one exists under {_tilde(state.project_dir(ev.get('cwd')))}/."}


def _pre_tool(ev):
    kind, _isa = classify.classify(ev.get("tool", ""), ev.get("tool_input"), ev.get("cwd"), ev.get("temp_dirs", ()))
    if kind == "read":
        return {}
    st = state.read_session(ev["harness"], ev["session"])
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
    return {}


def _post_tool(ev):
    tool, ti, cwd = ev.get("tool", ""), ev.get("tool_input") or {}, ev.get("cwd")
    kind, isa_paths = classify.classify(tool, ti, cwd, ev.get("temp_dirs", ()))
    masters = [p for p in isa_paths if state.is_master_isa(os.path.join(cwd or "", os.path.expanduser(p)))]
    now = time.time()
    out = []
    with state.session(ev["harness"], ev["session"]) as st:
        if masters:
            path = os.path.realpath(os.path.join(cwd or "", os.path.expanduser(masters[-1])))
            if st.get("bound") != path:
                if st.get("bound"):
                    out.append(f"ISA binding switched to {_tilde(path)} (was {_tilde(st['bound'])}).")
                st["bound"] = path
            st["last_isa_edit"] = now
            st["since_isa"] = 0
        elif isa_paths:
            st["last_isa_edit"] = now  # ephemeral slice or probe file inside the ISA folder
        elif kind == "write":
            st["last_mutation"] = now
            st["mutations"] += 1
            st["since_isa"] += 1
            if st["since_isa"] % STALE_NUDGE_EVERY == 0 and _bound(st):
                out.append(f"{st['since_isa']} changes since the ISA was last updated — fold what you learned "
                           "into it now (tick verified ISCs with evidence, add/split ISCs, keep progress true).")
        bound = _bound(st)
    if masters and bound:
        errors, warns = _lint(bound, "auto", ev["harness"], ev["session"])
        if errors:
            out.append(f"ISA lint — {len(errors)} error(s) in {_tilde(bound)}:\n{_fmt(errors)}")
        else:
            out.append(_status_line(bound) + " — lint ok" + (f" ({len(warns)} warning(s))" if warns else "") + ".")
    return {"context": "\n".join(out)} if out else {}


def _tool_failed(ev):
    st = state.read_session(ev["harness"], ev["session"])
    if _bound(st) and ev.get("tool") in classify.SHELL_TOOLS:
        return {"context": "A command failed. If it was an ISC probe, that ISC stays unticked — fold what the "
                           "failure taught you into the ISA (split, tighten, or add an ISC; log a Decision)."}
    return {}


def _stop(ev):
    pid = str(ev.get("prompt_id") or "_")
    with state.session(ev["harness"], ev["session"]) as st:
        bound = _bound(st)
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
            if errors:
                fm = state.frontmatter(bound)
                what = "the close gate (`phase: complete`)" if fm.get("phase") == "complete" else "lint"
                problems.append(f"{_tilde(bound)} fails {what}:\n{_fmt(errors)}")
        if not problems:
            return {}
        already = st["stop_blocks"].get(pid, 0) >= 1 or ev.get("retried")
        st["stop_blocks"][pid] = st["stop_blocks"].get(pid, 0) + 1
        if len(st["stop_blocks"]) > 50:
            for k in sorted(st["stop_blocks"])[:-50]:
                st["stop_blocks"].pop(k, None)
    text = "ISA check before ending the turn:\n" + "\n".join(f"- {p}" for p in problems)
    if already:
        return {"warn": "ISA still not true after one retry — ending the turn anyway.\n" + text}
    return {"block": text}
