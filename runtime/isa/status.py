"""Read-only view of a session's bound ISA, for status lines. Standard library only.

    view(harness, session) → {"bound": None}
                           | {"bound": path, "task", "effort", "phase", "progress", "iteration",
                              "iscs": [{"id", "text", "done"}, …]}

`iscs` holds the leaf ISCs that count toward `progress` (no parents, tombstones or
waived ISCs), in file order — the same set `lint` computes `progress` over.
"""
import json
import os

from . import lint, logs, problems, state


def view(harness, session):
    st = state.read_session(harness, session)
    bound = st.get("bound")
    v = isa_view(bound) if bound and os.path.isfile(bound) else {"bound": None}
    v["mode"] = st.get("mode") or "off"
    v["mode_reason"] = st.get("mode_reason")
    v["blocked_no_isa"] = bool(st.get("blocked_no_isa"))
    v["gate"] = _last_gate(harness, session)
    return v


def _last_gate(harness, session):
    """The session's latest gate verdict from the debug log (logs.py, SPEC-v2 § 11.6), or None."""
    last = None
    for row in logs.recent():  # reads only: never creates the log folder
        if row.get("step") == "prompt" and row.get("harness") == harness and row.get("session") == session:
            if row.get("prefilter"):
                last = {"verdict": row["prefilter"], "source": "prefilter", "reason": row.get("reason"),
                        "ms": row.get("ms")}
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
