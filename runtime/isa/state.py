"""Where ISAs live and what each harness session has done. Standard library only.

Layout (spec 2026-10-06 § A.1): a git repo keeps only its project ISA, committed with it —

    <repo>/ISA.md                                            the project ISA (kind: project)

and everything else lives under ISA_HOME (default ~/.isa), never committed:

    ~/.isa/<project-key>/<YYYYMMDD-HHMMSS>_<slug>/ISA.md    a task ISA (in a repo or not)
    ~/.isa/_state/evidence/<slug>-<hash>.jsonl              its evidence ledger
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
    # a cwd inside an ISA folder belongs to that ISA's project, not to a project named after ~/.isa
    d, h_isa = os.path.realpath(cwd or os.getcwd()), os.path.realpath(home())
    if (d + os.sep).startswith(h_isa + os.sep):
        first = os.path.relpath(d, h_isa).split(os.sep)[0]
        if first not in (".", "_state"):
            return first
    root = project_root(cwd)
    h = os.path.realpath(os.path.expanduser("~"))
    if root == h:
        return "_home"
    rel = os.path.relpath(root, h) if (root + os.sep).startswith(h + os.sep) else "root" + root
    key = re.sub(r"[^A-Za-z0-9._-]+", "-", rel.replace(os.sep, "-")).strip("-")
    return key or "_root"


def _is_repo(d):
    return os.path.exists(os.path.join(d, ".git"))


def repo_root(cwd):
    """The git repo whose root holds cwd's project ISA, or None: no repo, or a repo rooted at
    $HOME or holding ISA_HOME (a dotfiles work tree — its `.isa/` would be ISA_HOME itself)."""
    root = project_root(cwd)
    if not _is_repo(root):
        return None
    ih = os.path.realpath(home())
    if root == os.path.realpath(os.path.expanduser("~")) or (ih + os.sep).startswith(root + os.sep) or ih == root:
        return None
    return root


def project_dir(cwd):
    """Where a new task ISA of cwd goes: always `ISA_HOME/<project-key>`, in a git repo too (spec 2026-10-06
    § A.1). A repo keeps only its project ISA, `<repo>/ISA.md`."""
    return os.path.join(home(), project_key(cwd))


def is_project_isa(path):
    """`<repo>/ISA.md`: the repo's living spec — never bound, never closed (spec 2026-10-06 § A.4)."""
    try:
        p = os.path.realpath(os.path.expanduser(path))
    except (TypeError, ValueError):
        return False
    d = os.path.dirname(p)
    return os.path.basename(p) == "ISA.md" and _is_repo(d) and repo_root(d) == d


def is_isa_path(path):
    """True for anything inside an ISA folder under ISA_HOME (the ISA itself, ephemeral slices, probes), and for
    a repo's project ISA."""
    try:
        p = os.path.realpath(os.path.expanduser(path))
    except (TypeError, ValueError):
        return False
    if is_project_isa(p):
        return True
    h = os.path.realpath(home())
    if not (p + os.sep).startswith(h + os.sep):
        return False
    rel = os.path.relpath(p, h).split(os.sep)
    return len(rel) >= 1 and rel[0] not in (".", "_state")  # _state is engine-owned; _home/_root are projects


def is_master_isa(path):
    return is_isa_path(path) and os.path.basename(path) == "ISA.md" and "_ephemeral" not in path


def is_task_isa(path):
    """A master ISA that can be bound to a session: every master ISA but a repo's project ISA."""
    return is_master_isa(path) and not is_project_isa(path)


def project_isa_of(isa_path):
    """The project ISA (`<repo>/ISA.md`) of the git repo holding the task ISA's `root:`, or None (no `root:`,
    a relative one, or a root outside any repo)."""
    root = frontmatter(isa_path).get("root")
    if not isinstance(root, str) or not root:
        return None
    root = os.path.expanduser(root)
    if not os.path.isabs(root):
        return None
    repo = repo_root(root)
    return os.path.join(repo, "ISA.md") if repo else None


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


def isa_home_key(isa_path):
    """The project folder an ISA was filed under (its real location, not a link)."""
    real = os.path.realpath(isa_path)
    return os.path.basename(os.path.dirname(os.path.dirname(real)))


def note_project(isa_path, key):
    """Record that the session bound to `isa_path` changed files in project `key`. The ISA stays filed in
    its home project; every other project gets a link `~/.isa/<key>/<slug>` → the ISA folder, so
    `isa ls` there lists it. Idempotent. → True when `key` was new for this ISA."""
    folder = os.path.dirname(os.path.realpath(isa_path))
    index = os.path.join(folder, ".projects.json")
    try:
        with open(index) as f:
            keys = json.load(f)
    except (OSError, ValueError):
        keys = []
    if key in keys:
        return False
    keys.append(key)
    tmp = index + ".tmp"
    with open(tmp, "w") as f:
        json.dump(keys, f)
    os.replace(tmp, index)
    if key != isa_home_key(isa_path):
        link = os.path.join(home(), key, os.path.basename(folder))
        if not os.path.lexists(link):
            os.makedirs(os.path.dirname(link), exist_ok=True)
            os.symlink(folder, link)
    return True


def projects_of(isa_path):
    try:
        with open(os.path.join(os.path.dirname(os.path.realpath(isa_path)), ".projects.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def is_scratch_dir(d):
    """A cwd that is no project at all: a non-git directory under a temp root (a scratchpad, /tmp/x)."""
    root = project_root(d)
    if os.path.exists(os.path.join(root, ".git")):
        return False
    real = os.path.realpath(root)
    for t in {"/tmp", "/var/tmp", "/dev/shm", os.environ.get("TMPDIR", "/tmp")}:
        t = os.path.realpath(t)
        if (real + os.sep).startswith(t + os.sep):
            return True
    return False


def list_isas(key=None, cwd=None, folder=None):
    """[(path, frontmatter)] for one project (a key under ISA_HOME, cwd's ISA folder, or a folder), newest first."""
    d = folder or (os.path.join(home(), key) if key else project_dir(cwd))
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


def log_prompt(harness, session_id, text, prompt_id=None, cwd=None, project=None, context=None):
    """One row per user prompt. `cwd`/`project` make "this project's prompts" a lookup (`isa new`), and
    `context` keeps the tail of the assistant message the prompt answers (a "go" means what it approves)."""
    row = {"t": time.time(), "id": prompt_id, "text": text, "cwd": cwd, "project": project, "context": context or ""}
    with open(os.path.join(state_dir("prompts"), f"{_safe(harness)}-{_safe(session_id)}.jsonl"), "a") as f:
        f.write(json.dumps(row) + "\n")


def prompts(harness, session_id):
    try:
        with open(os.path.join(state_dir("prompts"), f"{_safe(harness)}-{_safe(session_id)}.jsonl")) as f:
            return [json.loads(line)["text"] for line in f if line.strip()]
    except OSError:
        return []


def log_error(msg):
    with open(os.path.join(state_dir(), "errors.log"), "a") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + msg.replace("\n", "\n    ") + "\n")


# ------------------------------------------------------------------ transcript

CONTEXT_CHARS = 2000


def last_assistant_text(transcript_path, limit=CONTEXT_CHARS):
    """The tail of the last assistant text in a Claude Code transcript (JSONL); "" when unreadable."""
    if not transcript_path:
        return ""
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            f.seek(max(0, size - 1_000_000))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if not isinstance(m, dict) or m.get("type") != "assistant":
            continue
        content = (m.get("message") or {}).get("content")
        if isinstance(content, str):
            text = content
        else:
            text = "\n".join(c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")
        if text.strip():
            return text[-limit:]
    return ""
