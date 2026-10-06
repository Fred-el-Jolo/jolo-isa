"""Read-only view of a session, for status lines and skills (`isa status`, `isa current`).

    view(harness, session) → {"bound": path | None, "mode", "stage", "spec", "task", "effort", "phase",
                              "progress", "iscs": [{"id", "text", "done", "level"}, …]}

`iscs` lists the leaf criteria that count toward `progress`, in file order.
"""
import os

from . import engine, isafile, state


def view(harness, session):
    st = state.read_session(harness, session)
    bound = st.get("bound") if st.get("bound") and os.path.isfile(st["bound"]) else None
    v = {"bound": bound, "mode": engine._mode(st), "stage": engine.stage(st)[0], "spec": st.get("doc")}
    if bound:
        with open(bound, encoding="utf-8") as f:
            p = isafile.parse(f.read())
        fm = p["fm"]
        v.update(task=fm.get("task"), effort=fm.get("effort"), phase=fm.get("phase"), progress=isafile.progress(p),
                 iscs=[{"id": f"ISC-{i}", "text": p["iscs"][i]["text"], "done": p["iscs"][i]["box"] == "x",
                        "level": p["iscs"][i]["level"]} for i in isafile.leaves(p)])
    return v


def line(v):
    head = f"ISA {str(v.get('mode', 'off')).upper()} — {v.get('stage')}"
    if not v.get("bound"):
        return head + (f" — spec {v['spec']}" if v.get("spec") else " — no ISA bound to this session")
    open_ = [i["id"] for i in v.get("iscs") or [] if not i["done"]]
    return (f"{head} — {v.get('effort', '?')} {v.get('phase', '?')} {v.get('progress', '?')} — {v.get('task', '')}"
            + (f"\nopen: {', '.join(open_)}" if open_ else ""))
