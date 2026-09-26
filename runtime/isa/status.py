"""Read-only view of a session's bound ISA, for status lines. Standard library only.

    view(harness, session) → {"bound": None}
                           | {"bound": path, "task", "effort", "phase", "progress", "iteration",
                              "iscs": [{"id", "text", "done"}, …]}

`iscs` holds the leaf ISCs that count toward `progress` (no parents, tombstones or
waived ISCs), in file order — the same set `lint` computes `progress` over.
"""
import os

from . import lint, state


def view(harness, session):
    bound = state.read_session(harness, session).get("bound")
    if not bound or not os.path.isfile(bound):
        return {"bound": None}
    return isa_view(bound)


def isa_view(path):
    p = lint.parse(open(path, encoding="utf-8").read(), path)
    fm, iscs, counted = p["fm"], p["iscs"], p["counted"]
    return {
        "bound": path,
        "task": fm.get("task"),
        "effort": fm.get("effort"),
        "phase": fm.get("phase"),
        "progress": fm.get("progress"),
        "iteration": fm.get("iteration"),
        "iscs": [{"id": i, "text": iscs[i][1], "done": iscs[i][0]} for i in counted],
    }


def line(v):
    """One human-readable line (`isa status` without --json)."""
    if not v.get("bound"):
        return "no ISA bound to this session"
    open_ = [i["id"] for i in v["iscs"] if not i["done"]]
    return (f"{v.get('effort', '?')} {v.get('phase', '?')} {v.get('progress', '?')} — {v.get('task', '')}"
            + (f"\nopen: {', '.join(open_)}" if open_ else ""))
