"""The tree fingerprint of a probe root (SPEC-v2 § 4.2). Standard library only.

    of(root)                       → "git:<tree id>" | "walk:<sha256>" | "uncomputable"
    changed_paths(root, a, b)      → [paths under root that differ between two git fingerprints]

Git work tree: the content of every tracked and untracked non-ignored file under `root`, as a tree id —
`git add -A` into a temporary copy of the index, then `git write-tree --prefix=<root>/`. The real index
is never touched; a commit that changes no file changes nothing; gitignored files never count.
`ISA_HOME` is excluded when it lies inside `root`.

Anywhere else: a walk of (path, size, mtime_ns), hidden and dependency/cache directories skipped,
capped at WALK_CAP files / WALK_SECONDS — past the cap, or for the home directory itself, the answer is
"uncomputable". This one is not a content hash: a `touch` changes it.

Only `isa verify` / `isa close` call this; hooks never do (a large tree can take a moment).
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import time

from . import changes, state

GIT_TIMEOUT = 60
WALK_CAP = 5000
WALK_SECONDS = 2.0
UNCOMPUTABLE = "uncomputable"


def _git(args, cwd, env=None):
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=GIT_TIMEOUT)


def _git_top(root):
    try:
        r = _git(["rev-parse", "--show-toplevel"], root)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def _inside(path, root):
    return path == root or (path + os.sep).startswith(root + os.sep)


def of(root):
    root = os.path.realpath(os.path.expanduser(root))
    if not os.path.isdir(root):
        return UNCOMPUTABLE
    top = _git_top(root)
    try:
        return _git_fp(root, top) if top else _walk_fp(root)
    except (OSError, subprocess.TimeoutExpired):
        return UNCOMPUTABLE


def _git_fp(root, top):
    idx = _git(["rev-parse", "--git-path", "index"], top).stdout.strip()
    idx = idx if os.path.isabs(idx) else os.path.join(top, idx)
    rel = os.path.relpath(root, top)
    home = os.path.realpath(state.home())
    with tempfile.TemporaryDirectory(prefix="isa-fp-") as d:
        tmp = os.path.join(d, "index")
        if os.path.isfile(idx):
            shutil.copy2(idx, tmp)
        env = dict(os.environ, GIT_INDEX_FILE=tmp)
        spec = ["--", "." if rel == "." else rel, *changes.ISA_FILES]  # the repo's project ISA never counts
        if _inside(home, root):
            spec.append(f":(exclude){os.path.relpath(home, top)}")
        if _git(["add", "-A", *spec], top, env).returncode != 0:
            return UNCOMPUTABLE
        w = _git(["write-tree"] + ([] if rel == "." else [f"--prefix={rel}/"]), top, env)
        if w.returncode != 0 or not w.stdout.strip():
            return UNCOMPUTABLE
        return "git:" + w.stdout.strip()


def _walk_fp(root):
    if root == os.path.realpath(os.path.expanduser("~")):
        return UNCOMPUTABLE  # never walk the whole home directory
    home = os.path.realpath(state.home())
    h, n, t0 = hashlib.sha256(), 0, time.time()
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in changes.SKIP_DIRS
                         and not _inside(os.path.realpath(os.path.join(d, x)), home))
        for name in sorted(files):
            p = os.path.join(d, name)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            h.update(f"{os.path.relpath(p, root)}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
            n += 1
            if n > WALK_CAP or time.time() - t0 > WALK_SECONDS:
                return UNCOMPUTABLE
    return "walk:" + h.hexdigest()


def changed_paths(root, before, after):
    """Paths (relative to root) that differ between two git fingerprints; [] when unknown."""
    if not (before or "").startswith("git:") or not (after or "").startswith("git:") or before == after:
        return []
    top = _git_top(os.path.realpath(root))
    if not top:
        return []
    try:
        r = _git(["diff-tree", "-r", "--name-only", before[4:], after[4:]], top)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line for line in r.stdout.splitlines() if line.strip()] if r.returncode == 0 else []
