"""A view of a session, for status lines and skills (`isa status`, `isa current`), and `isa open`: the user's editor
on its spec or ISA. `status` and `current` never write; `open` lets the user edit the file.

    view(harness, session) → {"bound": path | None, "mode" (off | on | disabled), "stage", "spec", "task", "effort", "phase",
                              "progress", "iscs": [{"id", "text", "done", "level"}, …]}

`iscs` lists the leaf criteria that count toward `progress`, in file order. With only a spec bound, `effort` is the
spec's tier.
"""
import glob
import os
import shlex
import subprocess
import sys

from . import engine, isafile, state


def view(harness, session):
    st = state.read_session(harness, session)
    bound = st.get("bound") if st.get("bound") and os.path.isfile(st["bound"]) else None
    v = {"bound": bound, "mode": "disabled" if engine.disabled(st) else engine._mode(st), "stage": engine.stage(st)[0],
         "spec": st.get("doc")}
    if bound:
        with open(bound, encoding="utf-8") as f:
            p = isafile.parse(f.read())
        fm = p["fm"]
        v.update(task=fm.get("task"), effort=fm.get("effort"), phase=fm.get("phase"), progress=isafile.progress(p),
                 iscs=[{"id": f"ISC-{i}", "text": p["iscs"][i]["text"], "done": p["iscs"][i]["box"] == "x",
                        "level": p["iscs"][i]["level"]} for i in isafile.leaves(p)])
    elif v["spec"] and os.path.isfile(v["spec"]):
        v["effort"] = state.frontmatter(v["spec"]).get("effort")
    return v


def line(v):
    head = f"ISA {str(v.get('mode', 'off')).upper()} — {v.get('stage')}"
    if not v.get("bound"):
        return head + (f" — spec {v['spec']}" if v.get("spec") else " — no ISA bound to this session")
    open_ = [i["id"] for i in v.get("iscs") or [] if not i["done"]]
    return (f"{head} — {v.get('effort', '?')} {v.get('phase', '?')} {v.get('progress', '?')} — {v.get('task', '')}"
            + (f"\nopen: {', '.join(open_)}" if open_ else ""))


# ------------------------------------------------------------------ isa open

def _session_of_project(cwd):
    """(harness, id) of this project's most recently active session: its ISA or its spec belongs here."""
    pdir, root = state.project_dir(cwd) + os.sep, state.project_root(cwd) + os.sep
    files = glob.glob(os.path.join(state.home(), "_state", "sessions", "*-*.json"))
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        harness, _, sid = os.path.basename(f)[:-len(".json")].partition("-")
        st = state.read_session(harness, sid)
        if str(st.get("bound") or "").startswith(pdir) or str(st.get("doc") or "").startswith(root):
            return harness, sid
    return None, None


def target(st, which=None):
    """The file `isa open` opens: `spec` or `isa`, else the one the stage is about."""
    bound = st.get("bound") if st.get("bound") and os.path.isfile(st["bound"]) else None
    doc = st.get("doc") if st.get("doc") and os.path.isfile(st["doc"]) else None
    if which is None:
        which = "spec" if engine.stage(st)[0].startswith("SPEC ") or not bound else "isa"
    return doc if which == "spec" else bound


def editor():
    """$ISA_EDITOR, $VISUAL, $EDITOR, else nvim, for writing: the user may edit the file by hand (a model never runs
    `isa open`: the classifier refuses it from a tool call). An edit to an acked file needs a new ack."""
    return shlex.split(os.environ.get("ISA_EDITOR") or os.environ.get("VISUAL") or os.environ.get("EDITOR") or "nvim")


def open_cmd(args, harness=None, sid=None):
    """`isa open [spec|isa] [--print]`: the session's spec or ISA in the editor (or its path)."""
    which = next((a for a in args if a in ("spec", "isa")), None)
    if not sid:
        harness, sid = _session_of_project(os.getcwd())
    if not sid:
        print("isa open: no session of this project (pass --session ID)", file=sys.stderr)
        return 1
    path = target(state.read_session(harness or "claude", sid), which)
    if not path:
        print(f"isa open: no {which or 'spec or ISA'} bound to session {sid}", file=sys.stderr)
        return 1
    if "--print" in args:
        print(path)
        return 0
    return subprocess.call(editor() + [path])
