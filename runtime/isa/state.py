"""Where ISAs live and what each harness session has done. Standard library only.

Layout (ISA_HOME defaults to ~/.isa):

    ~/.isa/<project-key>/<YYYYMMDD-HHMMSS>_<slug>/ISA.md    one task ISA
    ~/.isa/_state/sessions/<harness>-<session>.json         binding + counters
    ~/.isa/_state/prompts/<harness>-<session>.jsonl         raw user prompts
    ~/.isa/_state/errors.log                                hook failures

The project key is the git work-tree root (or the directory itself) as a path
relative to $HOME with "/" turned into "-": /home/me/dev/app → "dev-app".
"""
import contextlib
import fcntl
import json
import os
import re
import time

from . import yamlish


def home():
    return os.path.expanduser(os.environ.get("ISA_HOME", "~/.isa"))


def state_dir(*parts):
    d = os.path.join(home(), "_state", *parts)
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------- projects

def project_root(cwd):
    d = os.path.realpath(cwd or os.getcwd())
    probe = d
    while True:
        if os.path.exists(os.path.join(probe, ".git")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return d
        probe = parent


def project_key(cwd):
    root = project_root(cwd)
    h = os.path.realpath(os.path.expanduser("~"))
    if root == h:
        return "_home"
    rel = os.path.relpath(root, h) if (root + os.sep).startswith(h + os.sep) else "root" + root
    key = re.sub(r"[^A-Za-z0-9._-]+", "-", rel.replace(os.sep, "-")).strip("-")
    return key or "_root"


def project_dir(cwd):
    return os.path.join(home(), project_key(cwd))


def is_isa_path(path):
    """True for anything inside an ISA folder (the ISA itself, ephemeral slices, probes)."""
    try:
        p = os.path.realpath(os.path.expanduser(path))
    except (TypeError, ValueError):
        return False
    h = os.path.realpath(home())
    if not (p + os.sep).startswith(h + os.sep):
        return False
    rel = os.path.relpath(p, h).split(os.sep)
    return len(rel) >= 1 and rel[0] != "." and not rel[0].startswith("_")


def is_master_isa(path):
    return is_isa_path(path) and os.path.basename(path) == "ISA.md" and "_ephemeral" not in path


def new_isa_path(cwd, slug="task"):
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:48] or "task"
    return os.path.join(project_dir(cwd), time.strftime("%Y%m%d-%H%M%S") + "_" + slug, "ISA.md")


_FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def frontmatter(path):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return {}
    m = _FM.match(text)
    if not m:
        return {}
    try:
        fm = yamlish.load(m.group(1))
    except yamlish.YamlError:
        return {}
    return fm if isinstance(fm, dict) else {}


def list_isas(key=None, cwd=None):
    """[(path, frontmatter)] for one project, newest first."""
    d = os.path.join(home(), key) if key else project_dir(cwd)
    out = []
    if os.path.isdir(d):
        for slug in sorted(os.listdir(d), reverse=True):
            p = os.path.join(d, slug, "ISA.md")
            if os.path.isfile(p):
                out.append((p, frontmatter(p)))
    return out


# ---------------------------------------------------------------- sessions

def _safe(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(s or "unknown"))[:120]


def _session_file(harness, session):
    return os.path.join(state_dir("sessions"), f"{_safe(harness)}-{_safe(session)}.json")


@contextlib.contextmanager
def session(harness, session_id):
    """Locked read-modify-write of one session's state (parallel tool calls race otherwise)."""
    path = _session_file(harness, session_id)
    with open(path + ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            st = json.load(open(path))
        except (OSError, ValueError):
            st = {}
        st.setdefault("bound", None)
        st.setdefault("last_isa_edit", 0.0)
        st.setdefault("last_mutation", 0.0)
        st.setdefault("mutations", 0)
        st.setdefault("since_isa", 0)
        st.setdefault("stop_blocks", {})
        st.setdefault("compacted", False)
        yield st
        st["touched"] = time.time()
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f, indent=1)
        os.replace(tmp, path)


def read_session(harness, session_id):
    try:
        return json.load(open(_session_file(harness, session_id)))
    except (OSError, ValueError):
        return {}


def log_prompt(harness, session_id, text, prompt_id=None):
    with open(os.path.join(state_dir("prompts"), f"{_safe(harness)}-{_safe(session_id)}.jsonl"), "a") as f:
        f.write(json.dumps({"t": time.time(), "id": prompt_id, "text": text}) + "\n")


def prompts(harness, session_id):
    try:
        with open(os.path.join(state_dir("prompts"), f"{_safe(harness)}-{_safe(session_id)}.jsonl")) as f:
            return [json.loads(line)["text"] for line in f if line.strip()]
    except OSError:
        return []


def log_error(msg):
    with open(os.path.join(state_dir(), "errors.log"), "a") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + msg.replace("\n", "\n    ") + "\n")
