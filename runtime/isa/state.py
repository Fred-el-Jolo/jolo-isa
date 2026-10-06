"""Where ISA things live, and what each harness session holds. Standard library only.

    ~/.isa/<project>/<YYYYMMDD-HHMMSS>_<slug>/ISA.md   a TASK ISA
    ~/.isa/<project>/acks.jsonl                         the user's ack clicks for that project
    ~/.isa/_state/sessions/<harness>-<session>.json     one session: mode, bound ISA or spec, the last prompts
    ~/.isa/_state/logs/YYYY-MM-DD.jsonl                 debug rows, only with DEBUG on
    ~/.isa/config.json                                  the user's settings

`<project>` is the git work-tree root (else the directory) relative to $HOME, "/" → "-":
/home/me/dev/app → "dev-app". `ISA_HOME` overrides ~/.isa.
"""
import contextlib
import fcntl
import json
import os
import re
import time

from . import yamlish

PROMPTS_KEPT = 20


def home():
    return os.path.expanduser(os.environ.get("ISA_HOME", "~/.isa"))


def debug():
    """DEBUG: `ISA_DEBUG=1`, or `"debug": true` in config.json. Off by default."""
    v = os.environ.get("ISA_DEBUG")
    if v is not None:
        return v.strip().lower() not in ("", "0", "false", "no", "off")
    from . import config
    return bool(config.get("debug"))


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


def is_repo(d):
    return os.path.exists(os.path.join(project_root(d), ".git"))


def project_key(cwd):
    root = project_root(cwd)
    h = os.path.realpath(os.path.expanduser("~"))
    if root == h:
        return "_home"
    rel = os.path.relpath(root, h) if (root + os.sep).startswith(h + os.sep) else "root" + root
    return re.sub(r"[^A-Za-z0-9._-]+", "-", rel.replace(os.sep, "-")).strip("-") or "_root"


def project_dir(cwd):
    return os.path.join(home(), project_key(cwd))


def acks_path(cwd):
    return os.path.join(project_dir(cwd), "acks.jsonl")


def new_isa_path(cwd, slug):
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:48] or "task"
    return os.path.join(project_dir(cwd), time.strftime("%Y%m%d-%H%M%S") + "_" + slug, "ISA.md")


def is_isa_path(path):
    """Anything under ISA_HOME: the ISAs, the acks, the state. Written only by `isa` commands."""
    try:
        p = os.path.realpath(os.path.expanduser(path))
    except (TypeError, ValueError):
        return False
    h = os.path.realpath(home())
    return p == h or (p + os.sep).startswith(h + os.sep)


DOC_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+-0(1-spec|2-plan)\.md$")


def is_doc_path(path):
    """`<dir>/docs/YYYY-MM-DD-<slug>-01-spec.md` or `…-02-plan.md`: a SPEC or a PLAN."""
    p = os.path.expanduser(str(path or ""))
    return bool(DOC_NAME.match(os.path.basename(p))) and os.path.basename(os.path.dirname(os.path.abspath(p))) == "docs"


_FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def frontmatter(path):
    try:
        with open(path, encoding="utf-8") as f:
            m = _FM.match(f.read())
        fm = yamlish.load(m.group(1)) if m else {}
    except (OSError, ValueError, yamlish.YamlError):
        return {}
    return fm if isinstance(fm, dict) else {}


def list_isas(folder):
    """[(path, frontmatter)] of a project folder, newest first."""
    out = []
    if os.path.isdir(folder):
        for slug in sorted(os.listdir(folder), reverse=True):
            p = os.path.join(folder, slug, "ISA.md")
            if os.path.isfile(p):
                out.append((p, frontmatter(p)))
    return out


# ---------------------------------------------------------------- locks and atomic writes

@contextlib.contextmanager
def lock(path):
    """Exclusive flock on `<path>.lock`, removed by its holder before release: no lock file stays behind. A
    waiter woken on a removed lock file retries on the new one."""
    name = os.path.realpath(path) + ".lock"
    os.makedirs(os.path.dirname(name), exist_ok=True)
    while True:
        fd = os.open(name, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            if os.stat(name).st_ino == os.fstat(fd).st_ino:
                break
        except FileNotFoundError:
            pass
        except BaseException:
            os.close(fd)
            raise
        os.close(fd)
    try:
        yield
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass
        os.close(fd)


def write_atomic(path, text):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".{os.path.basename(path)}.{os.getpid()}.tmp")
    try:
        mode = os.stat(path).st_mode & 0o777
    except OSError:
        mode = None
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, path)


# ---------------------------------------------------------------- sessions

def _safe(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(s or "unknown"))[:120]


def session_file(harness, session_id):
    return os.path.join(home(), "_state", "sessions", f"{_safe(harness)}-{_safe(session_id)}.json")


@contextlib.contextmanager
def session(harness, session_id):
    """Locked read-modify-write of one session's state."""
    path = session_file(harness, session_id)
    with lock(path):
        try:
            with open(path, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            st = {}
        yield st
        write_atomic(path, json.dumps(st, indent=1))


def read_session(harness, session_id):
    try:
        with open(session_file(harness, session_id), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def keep_prompt(st, text, pid):
    """The last PROMPTS_KEPT prompts, inside the session: what `stated_goal` and `asks` are checked against."""
    st["prompts"] = (st.get("prompts") or [])[-(PROMPTS_KEPT - 1):] + [{"id": pid, "text": text}]


def session_prompts(harness=None, session_id=None):
    """The prompts of a session; with no session given, the one in the environment (Claude Code, pi)."""
    if not session_id:
        for var, h in (("CLAUDE_CODE_SESSION_ID", "claude"), ("PI_SESSION_ID", "pi")):
            if os.environ.get(var):
                harness, session_id = h, os.environ[var]
                break
    if not session_id:
        return None
    return [p.get("text", "") for p in read_session(harness or "claude", session_id).get("prompts") or []]


# ---------------------------------------------------------------- transcript

def last_assistant_text(transcript_path, limit=2000):
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
        text = content if isinstance(content, str) else "\n".join(
            c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")
        if text.strip():
            return text[-limit:]
    return ""
