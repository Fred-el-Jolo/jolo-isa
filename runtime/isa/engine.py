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

ISA mode (SPEC-v2 § 1, § 12): every session is OFF until the gate says yes for a prompt, the user picks
Enable ISA, a write is attempted, an unknown command changes project files, or an ISA is bound; then it
is ON for good. The gate (§ 12.2) asks Jev first — Q1 "is this work?" with no ISA bound or a finished
one, Q2 "continuation or new task?" with an open one — and, when Jev is unavailable, leaves Q1 to the
running model, whose answer carries `ISA judge (model): yes|no|unsure — <reason>` (Stop reads it as a
string). Whatever is not settled as yes goes to the user (§ 12.4). OFF sessions get nothing else from
this engine. `ISA_MODE=on|off` (the user's override) wins, and no judge runs under it.
Every event leaves one row in the debug log (logs.py).
"""
import hashlib
import json
import os
import re
import time

from . import changes, classify, config, evidence, isafile, jev, lint, logs, problems, rules, skills, specdoc, state

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
    """Lint with the verbatim-goal check. A goal verified once (in any session) stays verified, in a local
    digest file beside the ISA."""
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
        label = evidence.pause_label(p)
        rows.append(f"  - {_tilde(p)} — {fm.get('task', '?')} (phase {fm.get('phase', '?')}, {fm.get('progress', '?')}"
                    + (f", {label}" if label else "") + ")")
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

_NOTE = {}


def note(**fields):
    """Extra fields for this event's debug log row."""
    _NOTE.update(fields)


def handle(ev):
    _NOTE.clear()
    t0 = time.time()
    res = _handle(ev)
    _log_event(ev, res, t0)
    return res


def _log_event(ev, res, t0):
    try:
        project = state.project_key(ev.get("cwd")) if ev.get("cwd") else None
    except Exception:  # noqa: BLE001
        project = None
    decision = [k for k in ("deny", "block", "warn", "context") if res.get(k)] or ["none"]
    row = {"step": ev.get("event"), "harness": ev.get("harness"), "session": ev.get("session"),
           "prompt_id": ev.get("prompt_id"), "project": project, "ms": int((time.time() - t0) * 1000),
           "decision": "+".join(decision)}
    if ev.get("tool"):
        row["tool"] = ev.get("tool")
    for k in ("deny", "block", "warn"):
        if res.get(k):
            row[k] = str(res[k]).splitlines()[0][:200]
    row.update(_NOTE)
    logs.write(row)


def _handle(ev):
    if _mode_env() == "off":
        note(mode="off", mode_source="ISA_MODE=off")
        return {}
    fn = {
        "session_start": _session_start, "prompt": _prompt, "pre_tool": _pre_tool,
        "post_tool": _post_tool, "tool_failed": _tool_failed, "stop": _stop, "compacted": _compacted,
        "ask_answer": _ask_answer,
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


# The model's Q1 verdict when Jev is unavailable (SPEC-v2 § 12.5), anywhere in its last message
JUDGE_LINE = re.compile(r"ISA judge \(model\):\s*(yes|no|unsure)\b[ \t]*[—–-]*[ \t]*([^\n]*)", re.I)

# Asking the user whenever the gate does not say yes (SPEC-v2 § 12.4, config `ask_without_isa`)
ASK_TITLE = "ISA is not enabled for this prompt"
ASK_CONTINUE = "Continue without ISA"
ASK_ENABLE = "Enable ISA"


def _question(label):
    return f"{ASK_TITLE} ({label}). Continue?"


def _ask_text(label):
    """The instruction to ask with AskUserQuestion (Claude Code: only the model can ask)."""
    return (f"Before you answer, ask the user with AskUserQuestion — question: \"{_question(label)}\", options in "
            f"this order: \"{ASK_CONTINUE} (Recommended)\" and \"{ASK_ENABLE}\". If they pick {ASK_ENABLE}, write the "
            f"ISA (read {_tilde(skill_dir())}/SKILL.md, then `isa new <slug>`) and do the work under it.")


def _q1_text():
    """Q1, as the `isa-gate` preset asks it: one text for Jev and for the model."""
    try:
        with open(os.path.join(jev.PRESETS, "isa-gate.json"), encoding="utf-8") as f:
            return json.load(f)["questions"]["work"]["instructions"]
    except (OSError, ValueError, KeyError):
        return "Does the user's message ask for a deliverable that could be done wrong in ways the reply alone would not reveal?"


def _judge_text(ask, why):
    """Q1 left to the running model (Jev unavailable)."""
    if ask == "model":
        below = ("no or unsure → before you go on without an ISA, ask the user with AskUserQuestion — question: "
                 f"\"{_question('model: <your verdict> — <your reason>')}\", options in this order: "
                 f"\"{ASK_CONTINUE} (Recommended)\" and \"{ASK_ENABLE}\"; if they pick {ASK_ENABLE}, write the ISA "
                 "and do the work under it.")
    elif ask == "extension":
        below = "no or unsure → just answer; the user is asked when you finish."
    else:
        below = "no or unsure → answer without an ISA."
    return (f"[ISA gate — Jev unavailable ({why}): you judge this prompt]\n{_q1_text()}\n"
            "Answer that question in one line of your reply (anywhere in it): "
            "`ISA judge (model): yes|no|unsure — <one-line reason>`.\n"
            f"yes → write the ISA before the work: read {_tilde(skill_dir())}/SKILL.md, then `isa new <slug>`.\n"
            f"{below}\nThe turn can't end without the line (or an ISA).")


def _assistant_text(ev):
    return ev.get("context") or state.last_assistant_text(ev.get("transcript_path"))


def _judge_line(ev):
    """→ (verdict, reason) from `ISA judge (model): …` in the last assistant message, or (None, "")."""
    m = JUDGE_LINE.search(_assistant_text(ev) or "")
    return (m.group(1).lower(), m.group(2).strip()[:200]) if m else (None, "")


def _headless():
    """A Claude Code run nobody attends (`claude -p`): there is no one to ask."""
    return os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0" or \
        os.environ.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk")


def _ask_mode(ev):
    """→ (mode, why-not): "model" (Claude Code: the model asks with AskUserQuestion), "extension" (pi: the
    adapter asks with its own dialog), or None with the reason no one is asked."""
    settings, err = config.load()
    if err:
        note(config_error=err)
    if not settings.get("ask_without_isa", True):
        return None, "config"
    if ev.get("harness") == "pi":
        return ("extension", None) if ev.get("has_ui") else (None, "no-ui")
    return (None, "no-ui") if _headless() else ("model", None)


def _ask_choice(ev):
    """The user's pick in our AskUserQuestion: enable | continue | unknown."""
    resp = ev.get("tool_response")
    for src in ((ev.get("tool_input") or {}).get("answers"), resp.get("answers") if isinstance(resp, dict) else None):
        if isinstance(src, dict):
            for q, a in src.items():
                if ASK_TITLE in str(q):
                    return "enable" if ASK_ENABLE.lower() in str(a).lower() else "continue"
    m = re.search(re.escape(ASK_TITLE) + r'[^"]*"\s*=\s*"([^"]*)"', str(ev.get("tool_output") or ""))
    if m:
        return "enable" if ASK_ENABLE.lower() in m.group(1).lower() else "continue"
    return "unknown"


def _is_our_question(ev):
    qs = (ev.get("tool_input") or {}).get("questions") or []
    return any(ASK_TITLE in str((q or {}).get("question", "")) for q in qs if isinstance(q, dict))


def _record_choice(ev, choice):
    """Store the user's answer for this prompt; `enable` switches the session ON (ON rules then apply)."""
    with state.session(ev["harness"], ev["session"]) as st:
        if not st.get("gate"):  # only an answer to the hook's own question for this prompt counts
            note(asked=True, choice=choice, ignored="no gate question for this prompt")
            return {}
        st["ask_answer"] = {"pid": str(ev.get("prompt_id")), "choice": choice}
        note(asked=True, choice=choice)
        if choice != "enable":
            st["pass"] = st["gate"].get("pid")  # the Continue pass: no ISA gate for the rest of this prompt
            return {"context": _continue_text(st["gate"], choice)}
        _switch_on(st, "user", "the user chose to enable ISA")
        st["needs_isa_since"] = ev.get("prompt_id")
    return {"warn": "ISA: ON — you chose to enable it",
            "context": f"The user chose {ASK_ENABLE}: write the ISA and do the work under it.\n\n" + _on_block(ev.get("cwd"))}


def _continue_text(gate, choice):
    """What the model reads after a Continue pick (or a failed question): the gate's outcome and the pass.
    Without it the model only holds the pre-ask line and older ON blocks, and hedges with a judge line."""
    judge = f"Jev {gate['score']:.2f}" if isinstance(gate.get("score"), (int, float)) else "the model's own verdict"
    picked = f"the user chose {ASK_CONTINUE}" if choice == "continue" else "the question could not reach the user"
    return (f"[ISA gate — {judge}: not settled as work; {picked}]\n"
            "The Continue pass holds for the rest of this prompt: answer and make changes with no ISA, write no "
            "`ISA judge (model):` line, and ignore any earlier ISA protocol for this prompt. This supersedes any "
            "line saying this prompt needs a new ISA (or a reopen). The next prompt is judged again.")


def _ask_answer(ev):
    """pi: the adapter asked with its own dialog and reports the pick."""
    choice = "enable" if ASK_ENABLE.lower() in str(ev.get("choice") or "").lower() else "continue"
    res = _record_choice(ev, choice)
    if choice != "enable":  # never `block`: at settle that would restart a run the user let end
        return res
    # asked at `input`: the context goes before the model; asked at settle: the run continues with it
    return {"context": res["context"], "block": res["context"], "warn": res["warn"]} if res else {}


# The spec / plan ack (spec 2026-10-06 § B.4, § 5.6 questions 3–5): a click on exactly ACK_YES, recorded
ACK_HEADER_SPEC = "Spec ack"
ACK_HEADER_PLAN = "Plan ack"
ACK_YES = "Acknowledge"
ACK_NO = "Request changes"
ACK_HEADERS = {ACK_HEADER_SPEC: "spec", ACK_HEADER_PLAN: "plan"}
DOC_PATH = re.compile(r"[^\s\"'`(]*docs/(?:spec|plan)/[^\s\"'`?)]+\.md")
STATUS_ACKED_TEXT = re.compile(r"status:\s*acked")


def _doc_kind(path):
    return "plan" if os.path.basename(os.path.dirname(path)) == "plan" else "spec"


def _doc_title(path):
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, ValueError):
        return ""
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), "")
    return title[len("Plan — "):] if title.startswith("Plan — ") else title


def _doc_summary(path):
    """Title and Goal of a spec or plan, for Q2 (the `isa-continuation` preset's `isa` field)."""
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, ValueError):
        return f"{_doc_kind(path)} {path}"
    lines = text.splitlines()
    goal = next((ln[len("Goal:"):].strip() for ln in lines if ln.startswith("Goal:")), "")
    if not goal and "## Goal" in lines:
        goal = next((ln.strip() for ln in lines[lines.index("## Goal") + 1:] if ln.strip()), "")
    return f"{_doc_kind(path)} {_tilde(path)} (no ISA yet): {_doc_title(path)}\nGoal: {goal}"


def _bind_doc(st, ev, out):
    """A file-tool write of a spec or plan binds it to the session (spec § B.7); the ISA binding is untouched."""
    if ev.get("tool") not in classify.FILE_TOOLS:
        return
    for p in classify.tool_paths(ev.get("tool_input")):
        full = os.path.realpath(p if os.path.isabs(os.path.expanduser(p)) else os.path.join(ev.get("cwd") or "", p))
        if not state.is_spec_path(full):
            continue
        kind = _doc_kind(full)
        if st.get("doc", {}).get("path") != full:
            out.append(f"{kind.capitalize()} {_tilde(full)} bound to this session. Its ack: once `isa lint` on it is "
                       f"clean, ask with AskUserQuestion — header `{ACK_HEADER_SPEC if kind == 'spec' else ACK_HEADER_PLAN}`, "
                       f"question naming the file, options exactly `{ACK_YES}` and `{ACK_NO}`.")
        st["doc"] = {"path": full, "kind": kind}


def _ack_questions(ev):
    qs = (ev.get("tool_input") or {}).get("questions") or []
    return [q for q in qs if isinstance(q, dict) and q.get("header") in ACK_HEADERS]


def _ack_path(q, ev, st):
    """The document an ack question is about: the spec/plan path it names, else the session's bound doc."""
    cwd = ev.get("cwd") or ""
    for m in DOC_PATH.findall(str(q.get("question", ""))):
        full = os.path.realpath(os.path.join(cwd, os.path.expanduser(m)))
        if state.is_spec_path(full):
            return full
    doc = (st or {}).get("doc") or {}
    return doc.get("path")


def _ack_question_refusal(ev, st):
    """PreToolUse: the ack question is asked only in its exact shape, about a document that lints clean."""
    if ev.get("tool") != "AskUserQuestion":
        return None
    for q in _ack_questions(ev):
        header = q.get("header")
        if (ev.get("tool_input") or {}).get("answers"):
            return "ISA ack: the ack question carries `answers` — only the user answers it. Ask it without them."
        labels = [str((o or {}).get("label", "")) for o in q.get("options") or [] if isinstance(o, dict)]
        if sorted(labels) != sorted([ACK_YES, ACK_NO]) or q.get("multiSelect"):
            return (f"ISA ack: the `{header}` question takes exactly two options, `{ACK_YES}` and `{ACK_NO}` "
                    "(no other label, no \"(Recommended)\", no multiSelect).")
        path = _ack_path(q, ev, st)
        if not path or not os.path.isfile(path):
            return (f"ISA ack: the `{header}` question must name the document, e.g. \"Acknowledge "
                    "docs/spec/YYYY-MM-DD-<slug>.md?\" — no such spec or plan here.")
        if ACK_HEADERS[header] != _doc_kind(path):
            want = ACK_HEADER_SPEC if _doc_kind(path) == "spec" else ACK_HEADER_PLAN
            return f"ISA ack: {_tilde(path)} is a {_doc_kind(path)} — ask with header `{want}`."
        errors = [m for m in specdoc.lint(path, "ack") if not m.startswith("warn:")]
        if errors:
            return (f"ISA ack: {_tilde(path)} does not pass `isa lint --moment ack` yet, so the user can't be asked "
                    f"to acknowledge it. Fix it, then ask:\n{_fmt(errors)}")
    return None


def _ack_answer(ev, question):
    resp = ev.get("tool_response")
    for src in ((ev.get("tool_input") or {}).get("answers"), resp.get("answers") if isinstance(resp, dict) else None):
        if isinstance(src, dict) and question in src:
            return str(src[question])
    m = re.search(re.escape(f'"{question}"') + r'\s*=\s*"([^"]*)"', str(ev.get("tool_output") or ""))
    return m.group(1) if m else None


def _ack_text(path, h):
    """What the model does after the click: the status line, then (in a git repo) commit that file alone."""
    kind, title = _doc_kind(path), _doc_title(path)
    line = f"status: acked {time.strftime('%Y-%m-%d')} #{h}"
    repo = state.repo_root(os.path.dirname(path))
    if repo and path.startswith(repo + os.sep):
        rel = os.path.relpath(path, repo)
        msg = f"{'Spec' if kind == 'spec' else 'Plan'}: {title} (acked)"
        commit = (f" Then commit that file alone: `git -C {repo} add -- {rel} && git -C {repo} commit -m \"{msg}\" "
                  f"-- {rel}` (code commits stay the user's call).")
    else:
        commit = " The project is outside any repository: no commit."
    return (f"The user acknowledged {_tilde(path)} (#{h}). Set its frontmatter line to exactly `{line}` with Edit, "
            f"changing nothing else in that edit.{commit} The ack is the go for what the {kind} covers.")


def _record_ack(ev):
    """PostToolUse of an ack question: exactly ACK_YES records the ack; anything else records nothing."""
    st = state.read_session(ev["harness"], ev["session"])
    out = []
    for q in _ack_questions(ev):
        path = _ack_path(q, ev, st)
        answer = _ack_answer(ev, str(q.get("question", "")))
        if not path or not os.path.isfile(path):
            continue
        if answer is None or answer.strip() != ACK_YES:
            note(ack="declined")
            out.append(f"{answer!r} is not an acknowledgement — {_tilde(path)} stays unacknowledged. Revise it "
                       "with the user's notes, then ask again.")
            continue
        errors = [m for m in specdoc.lint(path, "ack") if not m.startswith("warn:")]
        if errors:
            out.append(f"Not recorded: {_tilde(path)} does not pass the ack lint:\n{_fmt(errors)}")
            continue
        h = specdoc.record_ack(path, ev["harness"], ev["session"])
        note(ack="recorded")
        out.append(_ack_text(path, h))
    return {"context": "\n".join(out)} if out else {}


def _status_refusal(ev):
    """A `status: acked … #h` line is written only after the user's click (spec § B.4): with Edit/Write, when
    an ack with that hash is recorded and the written file still has that hash."""
    tool, ti, cwd = ev.get("tool", ""), ev.get("tool_input") or {}, ev.get("cwd") or ""
    if tool in classify.SHELL_TOOLS:
        if _shell_status_write(str(ti.get("command", "")), cwd):
            return ("ISA ack: `status: acked` is written with Edit, after the user picked Acknowledge — not from a "
                    "shell command. (A command that only reads the spec: run it apart from the text naming the "
                    "status line.)")
        return None
    if tool not in classify.FILE_TOOLS:
        return None
    for p in classify.tool_paths(ti):
        path = os.path.realpath(os.path.join(cwd, os.path.expanduser(p)))
        if not state.is_spec_path(path):
            continue
        try:
            current = open(path, encoding="utf-8").read()
        except (OSError, ValueError):
            current = ""
        new = _proposed(tool, ti, current)
        if new is None or specdoc.status_line(new) == specdoc.status_line(current):
            continue
        h = specdoc.acked_hash(new)
        if not h:
            continue
        if not specdoc.ack_recorded(path, h):
            header = ACK_HEADER_SPEC if _doc_kind(path) == "spec" else ACK_HEADER_PLAN
            return (f"ISA ack: no recorded ack of {_tilde(path)} with hash #{h}. Only the user acknowledges: ask with "
                    f"AskUserQuestion (header `{header}`, options `{ACK_YES}` / `{ACK_NO}`); the status line comes "
                    "after their click.")
        if specdoc.ack_hash(new) != h:
            return (f"ISA ack: after this write {_tilde(path)} would no longer match what the user acknowledged "
                    f"(#{h}). Write the status line alone; any other change needs a new ack.")
    return None


def _shell_status_write(cmd, cwd):
    """A shell command that names `status: acked` and may write it into a spec: a segment naming the spec
    that writes or runs a script (`sed -i`, `perl -pi`, `> spec`), or a script whose heredoc names it.
    Segments that only read the spec (`grep`, `cat`, `isa lint`) or never name it (`git commit -m …`) don't count."""
    if not STATUS_ACKED_TEXT.search(cmd):
        return False
    specs = {m for m in DOC_PATH.findall(cmd) if state.is_spec_path(os.path.join(cwd, os.path.expanduser(m)))}
    if not specs:
        return False
    try:
        toks = classify._tokens(classify._drop_heredoc_bodies(cmd).replace("\\\n", " ").replace("\n", " ; "))
    except ValueError:
        return True  # can't read the command: treat it as a write
    segs, seg = [], []
    for t in toks + [";"]:
        if t in classify.SEPARATORS or all(c in ";&|()" for c in t):
            segs.append(seg)
            seg = []
        else:
            seg.append(t)
    seen, scripts = set(), False
    for words in filter(None, segs):
        named = {s for s in specs if any(s in w for w in words)}
        seen |= named
        kind, _ = classify._segment(words, cwd, ())
        if named and kind not in ("read", "isa-cmd"):
            return True
        scripts = scripts or kind == "unknown"
    return scripts and bool(specs - seen)  # named only inside a heredoc body that a script reads


def _targets_acks(ev):
    """A write aimed at the ack records (`acks.jsonl`): only the hooks append there."""
    tool, ti, cwd = ev.get("tool", ""), ev.get("tool_input") or {}, ev.get("cwd") or ""
    acks = os.path.realpath(specdoc.acks_path())
    if tool in classify.FILE_TOOLS:
        paths = [os.path.join(cwd, os.path.expanduser(p)) for p in classify.tool_paths(ti)]
    elif tool in classify.SHELL_TOOLS:
        paths = classify.write_targets(str(ti.get("command", "")), cwd)
    else:
        return False
    return any(os.path.realpath(p) == acks for p in paths)


def _on_block(cwd):
    listing = _project_listing(cwd)
    return protocol(cwd) + ("\n" + listing if listing else "")


def _assistant_context(ev):
    if ev.get("context"):
        return str(ev["context"])[-state.CONTEXT_CHARS:]
    return state.last_assistant_text(ev.get("transcript_path"))


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
    if not bound:  # nothing bound, or a bound path that no longer exists (it reads as nothing bound)
        return True
    if _new_task_pending(st, bound):
        return True
    phase = state.frontmatter(bound).get("phase")
    if st.get("needs_isa_since") and phase == "complete":
        return True
    if _scaffold(bound):
        return "scaffold" if st.get("bound_prompt") == pid else True
    return False


def _new_task_pending(st, bound):
    """Q2 said "new task" while `bound` was open: a new ISA must be bound (editing this one won't do)."""
    q2 = st.get("q2") or {}
    return bool(bound) and q2.get("outcome") == "new" and q2.get("old") == bound  # a doc's Q2 has no `old`


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


# A prompt made only of system notification blocks (a background task finished): not the user's prompt
NOTIFICATION = re.compile(r"\A(?:\s*<task-notification>.*?</task-notification>)+\s*\Z", re.S)


def _prompt(ev):
    if NOTIFICATION.match(str(ev.get("prompt") or "")):
        # no judge, nothing injected, and nothing the user's last answer set is touched (the Continue pass, the
        # gate record, the turn start); not written to the prompt log either — it holds the user's words
        note(notification=True)
        return {}
    cwd, pid, prompt = ev.get("cwd"), ev.get("prompt_id"), ev.get("prompt", "")
    context = _assistant_context(ev)
    state.log_prompt(ev["harness"], ev["session"], prompt, pid, cwd=cwd, project=state.project_key(cwd),
                     context=context)
    with state.session(ev["harness"], ev["session"]) as st:
        st["prompt_started"] = time.time()  # Stop only checks turns where something happened after this
        st.pop("gate", None)
        st.pop("pass", None)  # the Continue pass lasts until the next prompt (SPEC-v2 § 12.4, M11.1)
        mode = _mode(st)
        doc = (st.get("doc") or {}).get("path")
        forced = mode == "on" and _switch_on(st, "override" if _mode_env() == "on" else "binding",
                                             "ISA_MODE=on" if _mode_env() == "on" else "open ISA bound (v1 session)")
        bound = _bound(st)
    complete = bool(bound) and state.frontmatter(bound).get("phase") == "complete"
    note(mode_before=mode)
    if forced and _mode_env() == "on":
        return {"context": _on_block(cwd)}
    # no judge (§ 12.2): an empty prompt, ON with no ISA yet (one is required already), or ISA_MODE=on
    if not str(prompt or "").strip():
        return {}
    if mode == "on" and not bound and doc and os.path.isfile(doc) and _mode_env() != "on":
        return _q2(ev, None, prompt, context, doc=doc)  # the bound spec or plan is the task (spec § B.7)
    if mode == "on" and not bound:
        return {"context": "ISA: ON — no ISA bound yet: write it before the work (`isa new <slug> --goal \"…\"`)."}
    if _mode_env() == "on":
        return {"context": _status_line(bound) + (". A new task gets a new ISA (or a reopen of this finished one)."
                                                  if complete else ". A new task gets a new ISA; continuing work keeps this one.")}
    if mode == "on" and not complete:
        return _q2(ev, bound, prompt, context)
    return _q1(ev, mode, bound, prompt, context)


def _gate_line():
    line, err = config.number("jev_gate")
    if err:
        note(config_error=err)
    return line


def _with_outage(ev, res, out):
    outage = _jev_outage(ev, res)
    if outage:
        out["warn"] = (out.get("warn", "") + "\n" + outage).strip()
    return out


def _unavailable(res):
    """What the user reads for a Jev call that was not served: credit, budget, or jev-kit's reason."""
    return jev.kind(res) if jev.kind(res) in ("credit", "budget") else res.get("reason") or "error"


def _q1(ev, mode, bound, prompt, context):
    """Q1 — is this work? (no ISA bound, or the bound one is complete)."""
    line = _gate_line()
    res = jev.ask("isa-gate", {"prompt": prompt, "context": context or "",
                               "skill": skills.describe(prompt, ev.get("harness"), ev.get("cwd"))},
                  jev.HOOK_DEADLINE, harness=ev.get("harness"), session=ev.get("session"), prompt_id=ev.get("prompt_id"))
    note(question="q1", judge="jev" if res["served"] else "model")
    if not res["served"]:
        note(jev_reason=res["reason"])
        return _with_outage(ev, res, _q1_model(ev, mode, bound, _unavailable(res)))
    score = res["answer"]
    note(score=score)
    label = f"Jev {score:.2f}"
    if score >= line:
        out = _q1_yes(ev, mode, bound, label)
    elif score < _quiet_line(line):
        out = _q1_quiet(ev, mode, bound, score, _quiet_line(line))
    else:
        out = _q1_ask(ev, mode, bound, score)
    return _with_outage(ev, res, out)


def _quiet_line(gate):
    """`jev_quiet`: below it Jev's "not work" is clear enough not to ask (M11.2). Must sit below the gate."""
    quiet, err = config.number("jev_quiet")
    if quiet >= gate:
        quiet, err = config.DEFAULTS["jev_quiet"], f"jev_quiet: {quiet} is not below jev_gate {gate}; using 0.3"
    if err:
        note(config_error=err)
    return quiet


def _q1_quiet(ev, mode, bound, score, quiet):
    """Clearly not work: no question; the prompt goes on with the Continue pass."""
    _not_settled(ev, mode, "jev", score, ask=False)
    with state.session(ev["harness"], ev["session"]) as st:
        st["pass"] = str(ev.get("prompt_id"))
    note(outcome="quiet")
    out = {"warn": f"ISA gate — Jev {score:.2f} → continue without ISA (below {quiet:.2f})"}
    if mode == "on" and bound:
        out["context"] = f"{_status_line(bound)}. This prompt was read as no new work (Jev {score:.2f})."
    return out


def _q1_yes(ev, mode, bound, label):
    cwd, pid = ev.get("cwd"), ev.get("prompt_id")
    with state.session(ev["harness"], ev["session"]) as st:
        if mode == "on":  # a finished ISA is bound
            st["needs_isa_since"] = pid
            note(outcome="new_isa")
            return {"warn": f"ISA gate — {label} → new task: new ISA, or reopen the finished one",
                    "context": f"{_status_line(bound)}. This prompt is a new task: new ISA, or reopen the finished "
                               "one (`phase: learn`, `iteration`, `resumed_at`, a `refined:` Decision)."}
        _switch_on(st, "jev", f"Jev reads this as work ({label})")
        st["needs_isa_since"] = pid  # this prompt is work: an ISA is required (read by Stop, § 13.4b)
        note(outcome="on", mode_after="on")
    out = {"warn": f"ISA gate — {label} → ON", "context": _on_block(cwd)}
    return out


def _not_settled(ev, mode, judge, score=None, ask=True):
    """Record that this prompt was not settled as work; → the ask mode (or None and why not)."""
    ask, why_not = _ask_mode(ev) if ask else (None, "quiet")
    with state.session(ev["harness"], ev["session"]) as st:
        st.pop("needs_isa_since", None)
        st["gate"] = {"pid": str(ev.get("prompt_id")), "judge": judge, "ask": ask, "score": score}
        if mode != "on":
            st.update(mode="off", mode_source=judge, mode_reason="not settled as work")
    note(ask=ask or why_not)
    return ask, why_not


def _q1_ask(ev, mode, bound, score):
    """Jev answered below the line: the user decides (§ 12.4)."""
    label, qlabel = f"Jev {score:.2f}", f"Jev: {score:.2f}"
    ask, why_not = _not_settled(ev, mode, "jev", score)
    pre = f"{_status_line(bound)}. If this prompt is a new task, it needs a new ISA (or a reopen).\n" \
        if mode == "on" and bound else ""
    if ask == "model":
        note(outcome="ask")
        return {"warn": f"ISA gate — {label} → asking you",
                "context": pre + f"[ISA gate — {label}: not settled as work]\n" + _ask_text(qlabel)}
    if ask == "extension":
        note(outcome="ask")
        out = {"warn": f"ISA gate — {label} → asking you", "ask": _question(qlabel),
               "options": [ASK_CONTINUE, ASK_ENABLE]}
        return dict(out, context=pre.strip()) if pre else out
    note(outcome="continue")
    with state.session(ev["harness"], ev["session"]) as st:
        st["pass"] = str(ev.get("prompt_id"))  # nobody to ask: the prompt goes on, as after a Continue
    why = "nobody to ask" if why_not == "no-ui" else "asking is off"
    out = {"warn": f"ISA gate — {label} → continue without ISA ({why})"}
    return dict(out, context=pre.strip()) if pre else out


def _q1_model(ev, mode, bound, why):
    """Jev unavailable: the running model answers Q1 with its judge line (§ 12.5)."""
    ask, _ = _not_settled(ev, mode, "model")
    note(outcome="model")
    pre = f"{_status_line(bound)}.\n" if mode == "on" and bound else ""
    return {"warn": f"ISA gate — Jev unavailable ({why}) → the model judges", "context": pre + _judge_text(ask, why)}


def _isa_summary(path):
    fm = state.frontmatter(path)
    return f"task: {fm.get('task', '')}\nGoal: {_goal_section(path)}"


def _q2(ev, bound, prompt, context, doc=None):
    """Q2 — continuation or new task? (an open ISA is bound, or else a spec or plan). Never asks the user."""
    if doc:
        return _q2_doc(ev, doc, prompt, context)
    line = _gate_line()
    res = jev.ask("isa-continuation", {"isa": _isa_summary(bound), "prompt": prompt, "context": context or ""},
                  jev.HOOK_DEADLINE, harness=ev.get("harness"), session=ev.get("session"), prompt_id=ev.get("prompt_id"))
    status = _status_line(bound)
    pid = str(ev.get("prompt_id"))
    note(question="q2", judge="jev" if res["served"] else "none")
    with state.session(ev["harness"], ev["session"]) as st:
        if not res["served"]:
            note(jev_reason=res["reason"], outcome="continuation")
            st["q2"] = {"pid": pid, "outcome": "unavailable", "old": bound}
            out = {"warn": "ISA gate — Jev unavailable → continuation (the model may start a new ISA)",
                   "context": status + ". A new task gets a new ISA (`isa new <slug>`); continuing work keeps this one."}
            return _with_outage(ev, res, out)
        new = res["answers"].get("new_task")
        resumes = res["answers"].get("resumes")
        new = float(new) if isinstance(new, (int, float)) else 0.0
        note(score=new)
        if new >= line:
            label = "paused" if isinstance(resumes, (int, float)) and resumes >= 0.5 else "superseded"
            st["q2"] = {"pid": pid, "outcome": "new", "old": bound, "label": label}
            note(outcome="new_task", resumes=resumes)
            out = {"warn": f"ISA gate — Jev {new:.2f} → new task: new ISA (open one {label})",
                   "context": f"{status}. This prompt starts a new task (Jev {new:.2f}): write a new ISA for it "
                              f"(`isa new <slug> --goal \"…\"`); the open one is then marked {label} and stays "
                              "resumable. The turn can't end before the new ISA is bound."}
        else:
            st["q2"] = {"pid": pid, "outcome": "continuation", "old": bound}
            note(outcome="continuation")
            out = {"warn": f"ISA gate — Jev {new:.2f} → continuation",
                   "context": status + ". This prompt continues it; a different task gets a new ISA."}
    return _with_outage(ev, res, out)


def _q2_doc(ev, doc, prompt, context):
    """Q2 against the bound spec or plan (no ISA bound yet). The outcome is recorded with `doc`, never `old`:
    no ISA is paused for it."""
    line = _gate_line()
    res = jev.ask("isa-continuation", {"isa": _doc_summary(doc), "prompt": prompt, "context": context or ""},
                  jev.HOOK_DEADLINE, harness=ev.get("harness"), session=ev.get("session"), prompt_id=ev.get("prompt_id"))
    kind, pid = _doc_kind(doc), str(ev.get("prompt_id"))
    bound_line = f"{kind.capitalize()} {_tilde(doc)} is bound (no ISA yet)"
    note(question="q2", judge="jev" if res["served"] else "none", doc=True)
    with state.session(ev["harness"], ev["session"]) as st:
        if not res["served"]:
            note(jev_reason=res["reason"], outcome="continuation")
            st["q2"] = {"pid": pid, "outcome": "unavailable", "doc": doc}
            return _with_outage(ev, res, {
                "warn": "ISA gate — Jev unavailable → continuation of the bound " + kind,
                "context": bound_line + ". A different task gets its own spec, or an E1 ISA."})
        new = res["answers"].get("new_task")
        new = float(new) if isinstance(new, (int, float)) else 0.0
        note(score=new)
        if new >= line:
            st["q2"] = {"pid": pid, "outcome": "new", "doc": doc}
            note(outcome="new_task")
            out = {"warn": f"ISA gate — Jev {new:.2f} → new task (not the bound {kind})",
                   "context": f"{bound_line}. This prompt starts a new task (Jev {new:.2f}), not about it: write a "
                              "new spec for it, or an E1 ISA (`isa new <slug> --tier E1`)."}
        else:
            st["q2"] = {"pid": pid, "outcome": "continuation", "doc": doc}
            note(outcome="continuation")
            out = {"warn": f"ISA gate — Jev {new:.2f} → continuation of the bound {kind}",
                   "context": f"{bound_line}. This prompt continues it."}
    return _with_outage(ev, res, out)


def _jev_outage(ev, res):
    """The user's line for a Jev call that was not served — once per session and kind of problem."""
    kind = jev.kind(res)
    if not kind:
        return ""
    with state.session(ev["harness"], ev["session"]) as st:
        warned = st.setdefault("jev_warned", [])
        if kind in warned:
            return ""
        warned.append(kind)
    return jev.message(res)


def _pre_tool(ev):
    kind, _isa = classify.classify(ev.get("tool", ""), ev.get("tool_input"), ev.get("cwd"), ev.get("temp_dirs", ()))
    if _targets_ledger(ev, kind):
        return {"deny": "ISA evidence gate: the evidence ledger (~/.isa/_state/evidence/) is written only by "
                        "`isa verify`. Run the probe through `isa verify <ISA> ISC-N` instead."}
    if _targets_acks(ev):
        return {"deny": "ISA ack: acks.jsonl (~/.isa/_state/acks.jsonl) holds the user's Acknowledge clicks and is "
                        "written only by the hooks."}
    if kind == "isa-cmd":
        return {}  # `isa new|lint|verify|close`: how the model writes the engine-owned state — never gated
    if kind == "isa-shell-edit":
        return {"deny": "ISA ownership: edit an ISA.md with Write/Edit, not a shell command — the hooks check "
                        "Write/Edit against the engine-owned fields (ticks, generated Verification lines, "
                        "progress, root, phase: complete); `isa verify` / `isa close` write those."}
    st = state.read_session(ev["harness"], ev["session"])
    refused = _ownership_refusal(ev) or _status_refusal(ev) or _ack_question_refusal(ev, st)
    if refused:
        return {"deny": refused}
    _note_creating(ev)
    if kind == "read":
        return {}
    if st.get("pass"):  # the user chose Continue for this prompt: no ISA gate until the next prompt
        note(**{"pass": True})
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


def _note_creating(ev):
    """A file-tool write about to create an ISA.md: binding it is allowed even while another ISA is bound
    (SPEC-v2 § 12.7). Recorded here because PostToolUse can no longer tell the file was new."""
    if ev.get("tool") not in classify.FILE_TOOLS:
        return
    cwd = ev.get("cwd") or ""
    new = [os.path.realpath(os.path.join(cwd, os.path.expanduser(p))) for p in classify.tool_paths(ev.get("tool_input"))]
    new = [p for p in new if state.is_master_isa(p) and not os.path.exists(p)]
    if new:
        with state.session(ev["harness"], ev["session"]) as s:
            s["creating"] = (s.get("creating", []) + new)[-10:]


def _snapshot_unknown(ev, kind, cwd):
    """Before an `unknown` shell command: snapshot the project so post_tool can tell whether it changed files,
    and the evidence ledger, which no tool may write (SPEC-v2 § 12.9)."""
    if ev.get("tool") not in classify.SHELL_TOOLS or kind != "unknown":
        return
    snap = None if state.is_scratch_dir(cwd) else changes.snapshot(state.project_root(cwd))
    ledger = None if _runs_isa_cmd(ev) else _ledger_state(state.read_session(ev["harness"], ev["session"]))
    if snap or ledger:
        with state.session(ev["harness"], ev["session"]) as s:
            for name, value in (("shell_snaps", snap), ("ledger_snaps", ledger)):
                if value:
                    snaps = s.setdefault(name, {})
                    snaps[_call_key(ev)] = value
                    for k in list(snaps)[:-20]:
                        snaps.pop(k, None)


def _runs_isa_cmd(ev):
    """`… && isa verify …`: an `isa` command inside a longer command writes the ledger legitimately."""
    return bool(re.search(r"(^|[\s;&|(/])isa\s+(new|lint|verify|close)\b", str((ev.get("tool_input") or {}).get("command", ""))))


def _ledger_state(st):
    """{"bound": sha256 of the bound ISA's ledger, "files": {name: mtime} of the evidence folder}."""
    files = {}
    try:
        for name in os.listdir(evidence.ledger_dir()):
            files[name] = os.path.getmtime(os.path.join(evidence.ledger_dir(), name))
    except OSError:
        pass
    bound, digest = _bound(st), None
    if bound:
        try:
            with open(evidence.ledger_path(bound), "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            digest = ""
    return {"bound": bound, "sha": digest, "files": files}


def _ledger_check(ev, st, out):
    """After an `unknown` shell command: report a ledger it changed; the bound ISA's own ledger also gets a
    `ledger-changed` blocked key, so `isa close` refuses until a full `isa verify` re-proves everything."""
    before = st.get("ledger_snaps", {}).pop(_call_key(ev), None)
    if not before:
        return ""
    now = _ledger_state(st)
    if before.get("bound") and before["bound"] == now["bound"] and before["sha"] != now["sha"]:
        problems.record_ledger_changed(before["bound"])
        out.append(f"ISA evidence ledger changed by this command — only `isa` commands write it. `isa close "
                   f"{_tilde(before['bound'])}` refuses until a full `isa verify` (no ISC list) re-proves everything.")
        return "ISA: the evidence ledger changed under a shell command — the ISA can't close until it is re-proven"
    changed = sorted(n for n in set(before["files"]) | set(now["files"])
                     if before["files"].get(n) != now["files"].get(n))
    if changed:
        out.append("ISA evidence ledger changed by this command (" + ", ".join(changed[:5]) + ") — only `isa` "
                   "commands write it.")
        return "ISA: an evidence ledger changed under a shell command"
    return ""


# ------------------------------------------------------------------ evidence

def _parsed(path, text=None):
    try:
        return lint.parse(open(path, encoding="utf-8").read() if text is None else text, path)
    except OSError:
        return None


def _targets_ledger(ev, kind):
    """A write aimed at the evidence ledger: a file-tool write there, or a shell redirect / `rm` / `mv` / `cp` …
    whose resolved target is inside it. Merely naming the folder (`grep … evidence/`) is fine."""
    tool, ti, cwd = ev.get("tool", ""), ev.get("tool_input") or {}, ev.get("cwd") or ""
    if tool in classify.FILE_TOOLS:
        return any(evidence.is_ledger_path(os.path.join(cwd, os.path.expanduser(p))) for p in classify.tool_paths(ti))
    if tool in classify.SHELL_TOOLS:  # a path the command visibly writes; a script is caught after it ran
        return any(evidence.is_ledger_path(p) for p in classify.write_targets(str(ti.get("command", "")), cwd))
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
        if classify.path_kind(full, ev.get("cwd"), ev.get("temp_dirs", ())) in ("project", "spec"):
            return os.path.dirname(os.path.realpath(os.path.expanduser(full)))
    return None


def _changed_projects(ev, kind):
    """Project keys a counted change landed in: by file path for file tools, by cwd for shell commands."""
    if ev.get("tool") in classify.FILE_TOOLS:
        base = _target_base(ev)
        return [state.project_key(base)] if base else []
    return [state.project_key(ev.get("cwd"))]


def _spec_project_isa(ev, out):
    """The first spec or plan written creates the project ISA at its doc root (spec 2026-10-06 § A.4)."""
    if ev.get("tool") not in classify.FILE_TOOLS:
        return
    for p in classify.tool_paths(ev.get("tool_input")):
        full = p if os.path.isabs(os.path.expanduser(p)) else os.path.join(ev.get("cwd") or "", p)
        if state.is_spec_path(full):
            from . import commands  # only here: hooks stay light
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(os.path.expanduser(full)))))
            commands.project_isa(root, out.append)


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
        old = st.get("bound")
        if old:
            out.append(f"ISA binding switched to {_tilde(path)} (was {_tilde(old)}).")
            _mark_left(st, old, path, out)
        if evidence.pause_label(path):  # a paused / superseded ISA bound again (SPEC-v2 § 12.7)
            evidence.record(path, [{"v": 2, "t": time.time(), "kind": "resumed"}])
            out.append(f"Resumed {_tilde(path)} (it was {evidence.pause_label(path) or 'paused'}).")
        st["bound"] = path
        st["bound_prompt"] = ev.get("prompt_id")  # the scaffold exit holds on this prompt only
        hist = st.setdefault("bound_history", [])  # waivers quote prompts of every session an ISA was bound to
        if path not in hist:
            hist.append(path)
    if state.frontmatter(path).get("phase") != "complete":
        st.pop("needs_isa_since", None)
        st.pop("blocked_no_isa", None)
    return "ISA: ON — an ISA was bound" if _switch_on(st, "binding", "an ISA was bound") else ""


def _mark_left(st, old, path, out):
    """A new ISA bound in place of an open one after Q2 said "new task" (or could not be asked): the old one
    is marked paused or superseded in its ledger — hooks never edit the ISA (SPEC-v2 § 12.7)."""
    q2 = st.pop("q2", None) or {}
    if q2.get("old") != old or q2.get("outcome") not in ("new", "unavailable"):
        return
    if not os.path.isfile(old) or state.frontmatter(old).get("phase") == "complete":
        return
    label = q2.get("label") or "paused"  # no Q2 answer (Jev unavailable): the reversible label
    evidence.record(old, [{"v": 2, "t": time.time(), "kind": label, "by": os.path.basename(os.path.dirname(path))}])
    out.append(f"The open ISA {_tilde(old)} is now marked {label}; it stays resumable (`isa ls` lists it).")


def _may_bind(st, path, ev):
    """The binding rule (SPEC-v2 § 12.7): a Write/Edit of an ISA.md binds it only when no open ISA is bound,
    when it is the bound one, or when the write creates the file."""
    cur = _bound(st)
    if not cur or cur == path or state.frontmatter(cur).get("phase") == "complete":
        return True
    creating = st.get("creating", [])
    if path in creating:
        creating.remove(path)
        return True
    resp = ev.get("tool_response")
    return isinstance(resp, dict) and resp.get("type") == "create"


def _project_feedback(path):
    """An edit of the repo's project ISA: content only, never bound."""
    if not os.path.isfile(path):
        return {}
    return {"context": f"Project ISA {_tilde(path)} edited (not bound to this session)."}


def _printed_isa(output):
    """The ISA.md path `isa new` printed (the last one in the output), or None."""
    for m in reversed(re.findall(r"(?<!\S)(/\S+/ISA\.md)\b", str(output or ""))):
        if state.is_task_isa(m) and os.path.isfile(m):
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
    if ev.get("tool") == "AskUserQuestion" and _is_our_question(ev):
        return _record_choice(ev, _ask_choice(ev))
    if ev.get("tool") == "AskUserQuestion" and _ack_questions(ev):
        return _record_ack(ev)
    tool, ti, cwd = ev.get("tool", ""), ev.get("tool_input") or {}, ev.get("cwd")
    kind, isa_paths = classify.classify(tool, ti, cwd, ev.get("temp_dirs", ()))
    if kind == "isa-cmd":
        return _post_isa_cmd(ev)
    full = [os.path.join(cwd or "", os.path.expanduser(p)) for p in isa_paths]
    masters = [p for p, f in zip(isa_paths, full) if state.is_task_isa(f)]  # the project ISA never binds (§ 13.2)
    project_edits = [f for f in full if state.is_project_isa(f)]
    if project_edits and not masters:
        return _project_feedback(project_edits[-1])
    now = time.time()
    out, touched, warn = [], [], ""
    with state.session(ev["harness"], ev["session"]) as st:
        was_off = _mode(st) == "off"
        # the bound ISA changed on disk without a file-tool path naming it (a shell edit: heredoc,
        # `sed -i`, a script): that call was an ISA edit, not a project change
        shell_edit = not masters and _isa_touched(st)
        other = None  # an ISA edited without binding it (another open ISA is bound)
        if masters:
            path = os.path.realpath(os.path.join(cwd or "", os.path.expanduser(masters[-1])))
            if _may_bind(st, path, ev):
                warn = _bind(st, path, ev, out)
            else:
                other = path
                out.append(f"Edited {_tilde(path)} — the session stays bound to {_tilde(_bound(st))} (editing "
                           "another ISA changes its content, not the binding).")
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
            _spec_project_isa(ev, out)
            _bind_doc(st, ev, out)
            if was_off and not st.get("pass") and _switch_on(st, "change", "a command changed project files"):
                warn = "ISA: ON — a command changed project files; the turn needs an ISA before it ends"
        if kind == "unknown" and tool in classify.SHELL_TOOLS:
            warn = _ledger_check(ev, st, out) or warn
        bound = _bound(st)
    if other:
        errors, _ = _lint(other, "auto", ev["harness"], ev["session"])
        if errors:
            out.append(f"ISA lint — {len(errors)} error(s) in {_tilde(other)}:\n{_fmt(errors)}")
        masters = []  # the bound ISA did not change: no bound-ISA feedback below
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
    if ev.get("tool") == "AskUserQuestion" and _is_our_question(ev):
        _record_choice(ev, "unavailable")  # the tool can't reach the user here: the default (continue) stands
        return {}
    if ev.get("tool") in classify.SHELL_TOOLS:
        kind, _ = classify.classify(ev.get("tool", ""), ev.get("tool_input"), ev.get("cwd"), ev.get("temp_dirs", ()))
        if kind == "unknown":  # a script that failed halfway may still have written files
            with state.session(ev["harness"], ev["session"]) as st:
                if _script_changed(ev, st):
                    _count_change(st, time.time(), [])
                ledger_out = []
                ledger_warn = _ledger_check(ev, st, ledger_out)
            if ledger_warn:
                return {"warn": ledger_warn, "context": "\n".join(ledger_out)}
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


JUDGE_MISSING = ("Jev was unavailable, so this prompt is yours to judge: put the line "
                 "`ISA judge (model): yes|no|unsure — <one-line reason>` in your answer (yes → write the ISA first: "
                 "`isa new <slug>`), or write the ISA.")


def _ask_missing(label):
    return (f"This prompt is not settled as work and the user was not asked. Ask them with AskUserQuestion "
            f"(question \"{_question(label)}\", options \"{ASK_CONTINUE} (Recommended)\" and \"{ASK_ENABLE}\"), "
            "then follow their choice.")


def _refuse_once(st, pid, ev, block, warn):
    already = st["stop_blocks"].get(pid, 0) >= 1 or ev.get("retried")
    st["stop_blocks"][pid] = st["stop_blocks"].get(pid, 0) + 1
    if not already:
        return {"block": "ISA check before ending the turn:\n- " + block}
    st.pop("gate", None)
    return {"warn": warn}


def _stop_gate(ev, st, gate, pid):
    """Stop for a prompt the gate did not settle as yes (SPEC-v2 § 12.4, § 12.5). → a result, or None when the
    ON rules apply now (the model judged `yes`)."""
    ans = st.get("ask_answer") if (st.get("ask_answer") or {}).get("pid") == str(ev.get("prompt_id")) else None
    ask = gate.get("ask")
    verdict, reason = _judge_line(ev) if gate.get("judge") == "model" else (None, "")
    note(judge=gate.get("judge"), model_verdict=verdict, model_reason=reason, asked=bool(ans),
         choice=ans and ans["choice"], ask=ask)
    if ans:  # the user chose (Enable switched the session ON, and the ON rules took over before this)
        st.pop("gate", None)
        return {}
    if verdict == "yes":  # work: the ON rules apply — an ISA, or after a finished one a new ISA or a reopen
        st.pop("gate", None)
        st["needs_isa_since"] = ev.get("prompt_id")
        _switch_on(st, "model", f"the model judged this work: {reason}"[:200])
        return None
    if gate.get("judge") == "model" and not verdict:
        return _refuse_once(st, pid, ev, JUDGE_MISSING,
                            "ISA: the agent neither judged this prompt nor wrote an ISA — ending the turn anyway.")
    if not ask:  # nobody to ask, or asking is off
        st.pop("gate", None)
        return {}
    label = f"model: {verdict} — {reason}" if verdict else f"Jev: {gate.get('score', 0):.2f}" \
        if gate.get("score") is not None else "Jev: below the line"
    if ask == "extension":  # pi asks with its own dialog, then reports the pick (`ask_answer`)
        return {"ask": _question(label), "options": [ASK_CONTINUE, ASK_ENABLE]}
    return _refuse_once(st, pid, ev, _ask_missing(label),
                        "ISA: the agent went on without an ISA and did not ask you — ending the turn anyway.")


def _stop(ev):
    pid = str(ev.get("prompt_id") or "_")
    with state.session(ev["harness"], ev["session"]) as st:
        gate = st.get("gate") if (st.get("gate") or {}).get("pid") == str(ev.get("prompt_id")) else None
        mode = _mode(st)
        bound = _bound(st)
        bound_now = bool(bound) and st.get("bound_prompt") == ev.get("prompt_id")
        if gate:
            open_isa = bool(bound) and state.frontmatter(bound).get("phase") != "complete"
            switched = mode == "on" and not bound and st.get("mode_since", 0) >= st.get("prompt_started", 0)
            if bound_now or open_isa or switched:
                st.pop("gate", None)  # the model took the ISA path (or a change turned it ON): ON rules
                gate = None
        if gate:
            res = _stop_gate(ev, st, gate, pid)
            if res is not None:
                return res
            mode = _mode(st)
        if mode != "on":
            return {}  # OFF: the prompt was not settled as work, and the user (or nobody to ask) let it go on
        bound = _bound(st)
        if _isa_touched(st):  # edited by a call whose PostToolUse never ran (e.g. a failed command)
            st["last_isa_edit"] = time.time()
        need = _needs_isa(st, bound, ev.get("prompt_id"))
        new_task = bool(bound) and _new_task_pending(st, bound)
        if need == "scaffold":
            return {}  # the clarify-first scaffold, on the prompt that created it
        started = st.get("prompt_started", 0.0)
        if need is not True and started and st["last_mutation"] < started and st["last_isa_edit"] < started:
            return {}  # nothing happened this turn: nothing to check
    items = []
    if need is True:  # checked even on a turn that changed nothing: a review is work too
        items.append({"code": "no-isa", "isc": None, "line": NO_ISA})
        bound = None if not bound or new_task or _scaffold(bound) \
            or state.frontmatter(bound).get("phase") == "complete" else bound
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
