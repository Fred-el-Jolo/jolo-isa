"""Read-only view of a session's bound ISA, for status lines. Standard library only.

    view(harness, session) → {"bound": None}
                           | {"bound": path, "task", "effort", "phase", "progress", "iteration",
                              "iscs": [{"id", "text", "done"}, …]}

`iscs` holds the leaf ISCs that count toward `progress` (no parents, tombstones or
waived ISCs), in file order — the same set `lint` computes `progress` over.
"""
import json
import os

from . import evidence, lint, logs, problems, state


def view(harness, session):
    st = state.read_session(harness, session)
    bound = st.get("bound")
    v = isa_view(bound) if bound and os.path.isfile(bound) else {"bound": None}
    v["mode"] = st.get("mode") or "off"
    v["mode_reason"] = st.get("mode_reason")
    v["blocked_no_isa"] = bool(st.get("blocked_no_isa"))
    v["gate"] = _last_gate(harness, session)
    v["jev"] = _last_jev(harness, session)
    v["label"] = evidence.pause_label(bound) if v.get("bound") else None
    return v


def current(harness, session):
    """`isa current`: the session's bound ISA for a skill — path, task, tier, phase, progress, label and
    the open criteria; {"path": None} when nothing is bound."""
    v = view(harness, session)
    if not v.get("bound"):
        return {"path": None, "session": session, "harness": harness}
    return {"path": v["bound"], "session": session, "harness": harness, "task": v.get("task"),
            "tier": v.get("effort"), "phase": v.get("phase"), "progress": v.get("progress"), "label": v.get("label"),
            "open": [{"id": i["id"], "text": i["text"]} for i in v["iscs"] if not i["done"]]}


def _last_jev(harness, session):
    """The session's latest Jev call from the debug log: served, answer, or why not (credit, budget…)."""
    last = None
    for row in logs.recent():
        if row.get("step") == "jev" and row.get("harness") == harness and row.get("session") == session:
            last = {k: row.get(k) for k in ("preset", "served", "answer", "reason", "detail", "ms")}
    return last


def _last_gate(harness, session):
    """The session's latest gate verdict from the debug log (logs.py, SPEC-v2 § 11.6, § 12.5), or None."""
    last = None
    for row in logs.recent():  # reads only: never creates the log folder
        if row.get("step") == "prompt" and row.get("harness") == harness and row.get("session") == session:
            if row.get("question"):  # SPEC-v2 § 12.5: who judged, which question, the score, the outcome
                last = {"judge": row.get("judge"), "question": row["question"], "score": row.get("score"),
                        "outcome": row.get("outcome"), "reason": row.get("jev_reason"), "ms": row.get("ms")}
            elif row.get("mode_source"):
                last = {"verdict": row.get("mode"), "source": "override", "reason": row["mode_source"],
                        "ms": row.get("ms")}
    return last


def isa_view(path):
    p = lint.parse(open(path, encoding="utf-8").read(), path)
    fm, iscs, counted = p["fm"], p["iscs"], p["counted"]
    return {
        "bound": path,
        "task": fm.get("task"),
        "effort": fm.get("effort"),
        "phase": fm.get("phase"),
        # counted from the criteria: the frontmatter `progress` may lag until the next `isa` command
        "progress": f"{sum(1 for i in counted if iscs[i][0])}/{len(counted)}",
        "iteration": fm.get("iteration"),
        "iscs": [{"id": i, "text": iscs[i][1], "done": iscs[i][0]} for i in counted],
        "blocked": [{"code": c, "isc": i} for c, i in problems.open_items(path)],
    }


def line(v):
    """One human-readable line (`isa status` without --json)."""
    mode = f"ISA {str(v.get('mode', 'off')).upper()}" + (f" ({v['mode_reason']})" if v.get("mode_reason") else "")
    if not v.get("bound"):
        return mode + " — no ISA bound to this session" + (" (blocked: a turn ended without an ISA)"
                                                            if v.get("blocked_no_isa") else "")
    open_ = [i["id"] for i in v["iscs"] if not i["done"]]
    blocked = [(b["isc"] + " " if b["isc"] else "") + b["code"] for b in v.get("blocked") or []]
    return (f"{mode} — {v.get('effort', '?')} {v.get('phase', '?')} {v.get('progress', '?')} — {v.get('task', '')}"
            + (f"\nopen: {', '.join(open_)}" if open_ else "")
            + (f"\nblocked: {', '.join(blocked)}" if blocked else ""))
