"""The hooks' decisions, harness-neutral (FOUNDATION_1 and FOUNDATION_2).

Events: session_start, prompt (the gate), pre_tool, post_tool, tool_failed, stop, compacted, ask_answer (pi).
The gate judges each prompt once — Jev, else the running model — and whatever is not a yes goes to the user.
While ON, the lifecycle decides what a project change needs:

    E1     TRIAGE → ISA DRAFT → BUILD → CLOSED
    E2–E4  TRIAGE → SPEC DRAFT → SPEC ACKED → ISA DRAFT → ISA ACKED (BUILD) → CLOSED

and in every mode, ISAs, specs, plans and ~/.isa change only through `isa` commands.
"""
import json
import os
import re
import time

from . import classify, config, doc, isafile, jev, lint, logs, skills, spec, state

HERE = os.path.dirname(os.path.abspath(__file__))
_NOTE = {}

ASK_TITLE = "ISA is not enabled for this prompt"
ASK_CONTINUE, ASK_ENABLE = "Continue without ISA", "Enable ISA"
ACK_YES, ACK_NO = "Acknowledge", "Request changes"
ACK_HEADERS = {"Spec ack": "spec", "ISA ack": "isa"}
JUDGE_LINE = re.compile(r"ISA judge \(model\):\s*(yes|no|unsure)\b[ \t]*[—–-]*[ \t]*([^\n]*)", re.I)
NOTIFICATION = re.compile(r"\A(?:\s*<task-notification>.*?</task-notification>)+\s*\Z", re.S)
GUARD = ("ISA: ISAs, specs, plans and everything under ~/.isa are written only by `isa` commands — "
         "`isa write <file> <section>` (text on stdin), `isa write <ISA> ISC-N \"<text>\"` / `--probe \"<command>\"`, "
         "`isa drop`, `isa decide`, `isa answer`, `isa ack`, `isa reopen`, `isa refine`. Reading is free "
         "(`isa show <file>`, cat, grep).")


def note(**fields):
    _NOTE.update(fields)


def handle(ev):
    _NOTE.clear()
    t0 = time.time()
    res = _handle(ev)
    if logs.on():
        row = {"step": ev.get("event"), "harness": ev.get("harness"), "session": ev.get("session"),
               "prompt_id": ev.get("prompt_id"), "ms": int((time.time() - t0) * 1000),
               "decision": "+".join(k for k in ("deny", "block", "warn", "context", "ask") if res.get(k)) or "none"}
        if ev.get("tool"):
            row["tool"] = ev["tool"]
        row.update(_NOTE)
        logs.write(row)
    return res


def _handle(ev):
    if _mode_env() == "off":
        return {}
    fn = {"session_start": _session_start, "prompt": _prompt, "pre_tool": _pre_tool, "post_tool": _post_tool,
          "stop": _stop, "compacted": _compacted, "ask_answer": _ask_answer}.get(ev.get("event"))
    return fn(ev) if fn else {}


# ------------------------------------------------------------------ mode, texts

def _mode_env():
    m = (os.environ.get("ISA_MODE") or "auto").strip().lower()
    return m if m in ("on", "off") else "auto"


def _mode(st):
    return "on" if _mode_env() == "on" else st.get("mode") or "off"


def _tilde(p):
    h = os.path.expanduser("~")
    return "~" + p[len(h):] if p and p.startswith(h + os.sep) else p


def skill_dir():
    return os.environ.get("ISA_SKILL_DIR") or os.path.expanduser("~/.claude/skills/ISA")


def protocol():
    with open(os.path.join(HERE, "protocol.md"), encoding="utf-8") as f:
        return f.read().replace("{skill}", _tilde(skill_dir())).strip()


def _question(label):
    return f"{ASK_TITLE} ({label}). Continue?"


def _ask_text(label):
    return (f"Before you answer, ask the user with AskUserQuestion — question: \"{_question(label)}\", options in this "
            f"order: \"{ASK_CONTINUE} (Recommended)\" and \"{ASK_ENABLE}\". If they pick {ASK_ENABLE}, follow the ISA "
            "lifecycle for this prompt.")


def q1_text():
    try:
        with open(os.path.join(jev.PRESETS, "isa-gate.json"), encoding="utf-8") as f:
            return json.load(f)["questions"]["work"]["instructions"]
    except (OSError, ValueError, KeyError):
        return "Does this message ask for work with several dependent steps?"


def _judge_text(ask, why):
    below = {"model": f"no or unsure → ask the user with AskUserQuestion — question: \"{_question('model: <verdict>')}\", "
                      f"options \"{ASK_CONTINUE} (Recommended)\" and \"{ASK_ENABLE}\".",
             "extension": "no or unsure → just answer; the user is asked when you finish."}.get(ask, "no or unsure → answer.")
    return (f"[ISA gate — Jev unavailable ({why}): you judge this prompt]\n{q1_text()}\n"
            "Answer it in one line of your reply: `ISA judge (model): yes|no|unsure — <one-line reason>`.\n"
            "yes → follow the ISA lifecycle (it starts with `isa new <slug> --tier E1` or `isa spec new <slug> --tier E2`).\n"
            f"{below}\nThe turn can't end without the line.")


def _headless():
    return os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0" or \
        os.environ.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk")


def _ask_mode(ev):
    if not config.get("ask_without_isa"):
        return None
    if ev.get("harness") == "pi":
        return "extension" if ev.get("has_ui") else None
    return None if _headless() else "model"


# ------------------------------------------------------------------ the lifecycle

def _exists(p):
    return bool(p) and os.path.isfile(p)


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _finished(sp):
    """A spec whose plan exists: its work is closed, it is never open again."""
    return _exists(sp) and os.path.exists(spec.plan_path(sp))


def stage(st):
    """→ (name, what to do next)."""
    isa, sp = st.get("bound"), st.get("doc")
    if _exists(isa):
        text = _read(isa)
        p = isafile.parse(text)
        t = _tilde(isa)
        if p["fm"].get("phase") == "complete":
            return "CLOSED", ("the bound ISA is closed: new work starts its own ISA (`isa new <slug> --tier E1`) or "
                              "spec (`isa spec new <slug> --tier E2`)")
        if isafile.tier(p) != "E1":
            spath = os.path.join(str(p["fm"].get("root")), str(p["fm"].get("spec") or ""))
            stext = _read(spath) if _exists(spath) else ""
            if not spec.is_acked(stext):
                return "SPEC DRAFT", (f"its spec {_tilde(spath)} is reopened: edit it with `isa write`, show the user "
                                      "`isa diff`, then ask the `Spec ack` question")
            if p["fm"].get("spec_hash") != spec.ack_hash(stext):
                return "ISA REFINE", f"the spec changed since this ISA was derived: `isa refine {t}`, then the ISA ack"
        errs = lint.errors(text, isa)
        if errs:
            return "ISA DRAFT", (f"finish the ISA with `isa write` ({len(errs)} to do: `isa lint {t}`)"
                                 + ("" if isafile.tier(p) == "E1" else f", then `isa review {t}`, `isa show {t} "
                                    "--trace` for the user, and the `ISA ack` question"))
        if isafile.tier(p) != "E1" and not isafile.acked(text):
            rerr = isafile.review_errors(text)
            review = f"{rerr[0].replace('<ISA>', t)}; then " if rerr else ""
            if p["fm"].get("acked"):
                return "ISA DRAFT", (f"the ISA changed since its ack: {review}show the user `isa diff {t}` and "
                                     f"`isa show {t} --trace`, then ask the `ISA ack` question")
            if rerr:
                return "ISA DRAFT", (f"review it before the ack — {review}`isa show {t} --trace` for the user and the "
                                     "`ISA ack` question")
            return "ISA DRAFT", (f"show the user the ISA (`isa show {t} --trace`), then ask the `ISA ack` question "
                                 "(header `ISA ack`, options `Acknowledge` / `Request changes`)")
        return "BUILD", ""
    if _exists(sp) and not _finished(sp):
        if spec.is_acked(_read(sp)):
            return "SPEC ACKED", f"the ack is the go: `isa new --spec {_tilde(sp)}`"
        return "SPEC DRAFT", (f"finish the spec with `isa write {_tilde(sp)} <part>`, `isa lint` it, then ask the "
                              "`Spec ack` question")
    return "TRIAGE", ("nothing is bound yet: E1 work starts with `isa new <slug> --tier E1`, E2–E4 work with "
                      "`isa spec new <slug> --tier E2`")


def _status_line(st):
    isa = st.get("bound")
    if _exists(isa):
        fm = state.frontmatter(isa)
        return f"ISA bound: {_tilde(isa)} — {fm.get('effort')}, {fm.get('phase')}, progress {fm.get('progress')}"
    if _exists(st.get("doc")) and not _finished(st.get("doc")):
        return f"Spec bound: {_tilde(st['doc'])}"
    return "Nothing bound"


# ------------------------------------------------------------------ session start, prompt (the gate)

def _session_start(ev):
    st = state.read_session(ev["harness"], ev["session"])
    if _mode(st) != "on":
        return {}
    name, todo = stage(st)
    return {"context": protocol() + f"\n\n{_status_line(st)}. Stage: {name}" + (f" — {todo}" if todo else "")}


def _compacted(ev):
    return _session_start(ev)


def _assistant_text(ev):
    return ev.get("context") or state.last_assistant_text(ev.get("transcript_path"))


def _prompt(ev):
    prompt = str(ev.get("prompt") or "")
    if NOTIFICATION.match(prompt):
        return {}
    pid = str(ev.get("prompt_id"))
    with state.session(ev["harness"], ev["session"]) as st:
        state.keep_prompt(st, prompt, pid)
        for k in ("gate", "pass", "ask_answer", "q2"):
            st.pop(k, None)
        st["prompt"] = pid
        if _mode_env() == "on" and st.get("mode") != "on":
            st["mode"] = "on"
            return {"context": protocol()}
        mode = _mode(st)
        bound_open = _exists(st.get("bound")) and state.frontmatter(st["bound"]).get("phase") != "complete"
        doc_open = not st.get("bound") and _exists(st.get("doc")) and not _finished(st.get("doc"))
    if not prompt.strip() or _mode_env() == "on":
        return {"context": _status_line(st) + f". Stage: {stage(st)[0]}"} if _mode_env() == "on" else {}
    if mode == "on" and (bound_open or doc_open):
        return _q2(ev, st, prompt)
    return _q1(ev, prompt)


def _q1(ev, prompt):
    res = jev.ask("isa-gate", {"prompt": prompt, "context": _assistant_text(ev) or "",
                               "skill": skills.describe(prompt, ev.get("harness"), ev.get("cwd"))},
                  jev.HOOK_DEADLINE, harness=ev.get("harness"), session=ev.get("session"), prompt_id=ev.get("prompt_id"))
    note(question="q1", judge="jev" if res["served"] else "model")
    pid = str(ev.get("prompt_id"))
    ask = _ask_mode(ev)
    if not res["served"]:
        why = jev.kind(res) if jev.kind(res) in ("credit", "budget") else res.get("reason") or "error"
        with state.session(ev["harness"], ev["session"]) as st:
            st["gate"] = {"pid": pid, "judge": "model", "ask": ask}
        out = {"warn": f"ISA gate — Jev unavailable ({why}) → the model judges", "context": _judge_text(ask, why)}
        msg = jev.message(res) if jev.kind(res) else ""
        if msg:
            out["warn"] += "\n" + msg
        return out
    score = res["answer"]
    note(score=score)
    gate, quiet = config.number("jev_gate"), config.number("jev_quiet")
    with state.session(ev["harness"], ev["session"]) as st:
        if score >= gate:
            st["mode"] = "on"
            if _exists(st.get("bound")) and state.frontmatter(st["bound"]).get("phase") == "complete":
                st.pop("bound")
                st.pop("doc", None)  # the closed ISA's spec goes with it
            if _finished(st.get("doc")):
                st.pop("doc")
            return {"warn": f"ISA gate — Jev {score:.2f} → ON", "context": protocol()}
        if score < quiet or not ask:
            st["pass"] = pid
            why = "below the quiet line" if score < quiet else "nobody to ask"
            return {"warn": f"ISA gate — Jev {score:.2f} → continue without ISA ({why})"}
        st["gate"] = {"pid": pid, "judge": "jev", "ask": ask, "score": score}
    label = f"Jev: {score:.2f}"
    if ask == "extension":
        return {"warn": f"ISA gate — Jev {score:.2f} → asking you", "ask": _question(label),
                "options": [ASK_CONTINUE, ASK_ENABLE]}
    return {"warn": f"ISA gate — Jev {score:.2f} → asking you",
            "context": f"[ISA gate — Jev {score:.2f}: not settled as work]\n" + _ask_text(label)}


def _q2(ev, st, prompt):
    bound = st.get("bound")
    about = (f"task: {state.frontmatter(bound).get('task', '')}" if _exists(bound) else
             f"spec: {doc.title(doc.split(_read(st['doc']))[2])}")
    res = jev.ask("isa-continuation", {"isa": about, "prompt": prompt, "context": _assistant_text(ev) or ""},
                  jev.HOOK_DEADLINE, harness=ev.get("harness"), session=ev.get("session"), prompt_id=ev.get("prompt_id"))
    note(question="q2", judge="jev" if res["served"] else "none")
    new = res["answers"].get("new_task") if res["served"] else None
    if isinstance(new, (int, float)) and new >= config.number("jev_gate"):
        with state.session(ev["harness"], ev["session"]) as s:
            s["q2"] = {"pid": str(ev.get("prompt_id")), "bound": bound, "doc": s.get("doc")}
        return {"warn": f"ISA gate — Jev {new:.2f} → new task",
                "context": f"{_status_line(st)}. This prompt starts a new task: it gets its own ISA or spec. The turn "
                           "can't end before it is bound."}
    label = f"Jev {new:.2f} → continuation" if isinstance(new, (int, float)) else "Jev unavailable → continuation"
    return {"warn": f"ISA gate — {label}", "context": f"{_status_line(st)}. Stage: {stage(st)[0]}. This prompt "
                                                     "continues it; a different task gets its own ISA or spec."}


# ------------------------------------------------------------------ PreToolUse

def _ack_target(q, ev, st):
    """The file an ack question names: a spec path in its text, else the bound spec / ISA."""
    kind = ACK_HEADERS.get(str(q.get("header", "")).strip())
    if kind == "isa":
        return st.get("bound") if _exists(st.get("bound")) else None
    m = re.search(r"[^\s\"'`(]*docs/\d{4}-\d{2}-\d{2}-[a-z0-9-]+-01-spec\.md", str(q.get("question", "")))
    if m:
        p = os.path.expanduser(m.group(0))
        return os.path.realpath(p if os.path.isabs(p) else os.path.join(ev.get("cwd") or os.getcwd(), p))
    return st.get("doc") if _exists(st.get("doc")) else None


def _ack_questions(ev):
    qs = (ev.get("tool_input") or {}).get("questions") or []
    return [q for q in qs if isinstance(q, dict) and str(q.get("header", "")).strip() in ACK_HEADERS]


def _pre_tool(ev):
    tool = ev.get("tool", "")
    st = state.read_session(ev["harness"], ev["session"])
    if tool == "AskUserQuestion":
        ti = ev.get("tool_input") or {}
        gate_q = any(isinstance(q, dict) and ASK_TITLE in str(q.get("question", "")) for q in ti.get("questions") or [])
        if ti.get("answers") and (gate_q or _ack_questions(ev)):
            return {"deny": "ISA: the answer to this question is the user's own click — ask it without `answers` "
                            "and let the user pick"}
        for q in _ack_questions(ev):
            path = _ack_target(q, ev, st)
            if not path:
                return {"deny": f"ISA ack: no {ACK_HEADERS[q['header'].strip()]} to acknowledge is bound"}
            text = _read(path)
            errs = spec.lint(text) if spec.kind_of(path) == "spec" else lint.errors(text, path)
            if errs:
                return {"deny": f"ISA ack: {_tilde(path)} doesn't lint yet, so the user can't be asked:\n"
                                + "\n".join(f"  - {e}" for e in errs[:12])}
            rerr = isafile.review_errors(text) if spec.kind_of(path) != "spec" else []
            if rerr:
                return {"deny": f"ISA ack: {_tilde(path)} isn't reviewed for the ack yet — "
                                + rerr[0].replace("<ISA>", _tilde(path))}
        return {}
    kind = classify.classify(tool, ev.get("tool_input"), ev.get("cwd"), ev.get("temp_dirs", ()))
    note(kind=kind)
    if kind == "guarded":
        return {"deny": GUARD}
    if kind not in ("write", "unknown") or _mode(st) != "on" or st.get("pass") == str(ev.get("prompt_id")):
        return {}
    name, todo = stage(st)
    if name == "BUILD":
        return {}
    return {"deny": f"ISA: {name} — this change waits: {todo}."}


# ------------------------------------------------------------------ PostToolUse

def _choice(ev):
    """The user's pick in the gate's own AskUserQuestion: enable | continue | None."""
    resp = ev.get("tool_response")
    for src in ((ev.get("tool_input") or {}).get("answers"), resp.get("answers") if isinstance(resp, dict) else None):
        if isinstance(src, dict):
            for q, a in src.items():
                if ASK_TITLE in str(q):
                    return "enable" if ASK_ENABLE.lower() in str(a).lower() else "continue"
    m = re.search(re.escape(ASK_TITLE) + r'[^"]*"\s*=\s*"([^"]*)"', str(ev.get("tool_output") or ""))
    return ("enable" if ASK_ENABLE.lower() in m.group(1).lower() else "continue") if m else None


def _answer(ev, question):
    resp = ev.get("tool_response")
    for src in ((ev.get("tool_input") or {}).get("answers"), resp.get("answers") if isinstance(resp, dict) else None):
        if isinstance(src, dict) and question in src:
            return str(src[question])
    m = re.search(re.escape(f'"{question}"') + r'\s*=\s*"([^"]*)"', str(ev.get("tool_output") or ""))
    return m.group(1) if m else None


def _record_choice(ev, choice):
    with state.session(ev["harness"], ev["session"]) as st:
        if not st.get("gate"):
            return {}
        st["ask_answer"] = {"pid": str(ev.get("prompt_id")), "choice": choice}
        note(choice=choice)
        if choice == "enable":
            st["mode"] = "on"
            return {"warn": "ISA: ON — you chose to enable it",
                    "context": f"The user chose {ASK_ENABLE}: follow the ISA lifecycle.\n\n" + protocol()}
        st["pass"] = st["gate"]["pid"]
    return {"context": "[ISA gate — not settled as work; the user chose Continue without ISA]\nThe Continue pass "
                       "holds for the rest of this prompt: answer and make changes with no ISA, and write no "
                       "`ISA judge (model):` line. The next prompt is judged again."}


def _record_ack(ev, path, answer):
    if (answer or "").strip() != ACK_YES:
        return f"{answer!r} is not an acknowledgement: revise {_tilde(path)} with the user's notes, then ask again."
    h = spec.record_click(path, ev["harness"], ev["session"])
    note(ack="recorded")
    return f"The user acknowledged {_tilde(path)} (#{h}): run `isa ack {_tilde(path)}`."


def _post_tool(ev):
    tool = ev.get("tool", "")
    if tool == "AskUserQuestion":
        st = state.read_session(ev["harness"], ev["session"])
        out = []
        for q in _ack_questions(ev):
            path = _ack_target(q, ev, st)
            if path:
                out.append(_record_ack(ev, path, _answer(ev, str(q.get("question", "")))))
        with state.session(ev["harness"], ev["session"]) as s:
            if out:
                s["ack_asked"] = str(ev.get("prompt_id"))
        choice = _choice(ev)
        res = _record_choice(ev, choice) if choice else {}
        if out:
            res = dict(res, context="\n".join(([res["context"]] if res.get("context") else []) + out))
        return res
    if tool in classify.SHELL_TOOLS and classify.bash((ev.get("tool_input") or {}).get("command", ""),
                                                      ev.get("cwd")) == "isa-cmd":
        return _bind(ev, str(ev.get("tool_output") or ""))
    return {}


def _bind(ev, output):
    isa = next((ln.split(": ", 1)[1].strip() for ln in output.splitlines() if ln.startswith("ISA: ")), None)
    sp = next((ln.split(": ", 1)[1].strip() for ln in output.splitlines() if ln.startswith("Spec: ")), None)
    if not (isa or sp):
        return {}
    with state.session(ev["harness"], ev["session"]) as st:
        if isa and _exists(isa):
            fm = state.frontmatter(isa)
            st["bound"] = isa
            st["doc"] = os.path.join(str(fm.get("root")), str(fm["spec"])) if fm.get("spec") else None
        elif sp and _exists(sp):
            st["bound"], st["doc"] = None, sp
        else:
            return {}
        st["mode"] = "on"
        st.pop("q2", None)
        name, todo = stage(st)
    note(bound=isa or sp)
    return {"context": f"{_status_line(st)}. Stage: {name}" + (f" — {todo}" if todo else "")}


# ------------------------------------------------------------------ Stop

def _refuse_once(pid, ev, text):
    with state.session(ev["harness"], ev["session"]) as st:
        n = (st.setdefault("stop_blocks", {})).get(pid, 0)
        st["stop_blocks"] = {pid: n + 1}
    if n or ev.get("retried"):
        return {"warn": "ISA: the turn ends with this open — " + text.splitlines()[0]}
    return {"block": "ISA check before ending the turn:\n- " + text}


def _stop(ev):
    pid = str(ev.get("prompt_id"))
    st = state.read_session(ev["harness"], ev["session"])
    gate = st.get("gate") if (st.get("gate") or {}).get("pid") == pid else None
    answered = (st.get("ask_answer") or {}).get("pid") == pid
    if gate and not answered:
        if gate["judge"] == "model":
            m = JUDGE_LINE.search(_assistant_text(ev) or "")
            if not m:
                return _refuse_once(pid, ev, "Jev was unavailable, so this prompt is yours to judge: put "
                                             "`ISA judge (model): yes|no|unsure — <reason>` in your answer.")
            if m.group(1).lower() == "yes":
                with state.session(ev["harness"], ev["session"]) as s:
                    s["mode"] = "on"
                st["mode"] = "on"
            elif gate.get("ask") == "model":
                return _refuse_once(pid, ev, "you judged this prompt not ISA work, so the user decides: "
                                    + _ask_text("model: " + m.group(1).lower()))
        elif gate.get("ask") == "model":
            return _refuse_once(pid, ev, "this prompt is not settled as work and the user was not asked. "
                                + _ask_text(f"Jev: {gate.get('score', 0):.2f}"))
        elif gate.get("ask") == "extension":
            return {"ask": _question(f"Jev: {gate.get('score', 0):.2f}"), "options": [ASK_CONTINUE, ASK_ENABLE]}
    if _mode(st) != "on" or st.get("pass") == pid:
        return {}
    q2 = st.get("q2") or {}
    if q2.get("pid") == pid and st.get("bound") == q2.get("bound") and st.get("doc") == q2.get("doc"):
        return _refuse_once(pid, ev, "this prompt is a new task: start its own ISA (`isa new <slug> --tier E1`) or "
                                     "spec (`isa spec new <slug> --tier E2`).")
    name, todo = stage(st)
    asked = st.get("ack_asked") == pid
    if name in ("BUILD", "CLOSED"):
        return {}
    if name == "SPEC DRAFT" and _exists(st.get("doc")) and \
            (doc.section_map(doc.split(_read(st["doc"]))[2]).get("Open questions") or "").strip():
        return {}  # the turn may end on the spec's open questions
    if name in ("SPEC DRAFT", "ISA DRAFT") and asked:
        return {}
    if ev.get("harness") == "pi" and ev.get("has_ui"):
        ask = _pi_ack(st, name)
        if ask:
            return ask
    return _refuse_once(pid, ev, f"{name}: {todo}.")


# ------------------------------------------------------------------ pi

def _pi_ack(st, name):
    path = st.get("doc") if name == "SPEC DRAFT" else st.get("bound") if name == "ISA DRAFT" else None
    if not _exists(path):
        return None
    text = _read(path)
    if spec.lint(text) if spec.kind_of(path) == "spec" else lint.errors(text, path) + isafile.review_errors(text):
        return None
    what = _tilde(path) if spec.kind_of(path) == "spec" else f"the ISA {state.frontmatter(path).get('task', '')}"
    return {"ask": f"Acknowledge {what}?", "options": [ACK_YES, ACK_NO], "ask_kind": "ack", "ask_path": path}


def _ask_answer(ev):
    if ev.get("ask_kind") == "ack":
        path = ev.get("ask_path")
        if not _exists(path):
            return {}
        msg = _record_ack(ev, path, ev.get("choice"))
        return {"context": msg, "block": msg}
    choice = "enable" if ASK_ENABLE.lower() in str(ev.get("choice") or "").lower() else "continue"
    res = _record_choice(ev, choice)
    if choice == "enable" and res:
        return {"context": res["context"], "block": res["context"], "warn": res["warn"]}
    return res
