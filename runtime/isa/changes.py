"""Did a shell command change project files? Standard library only.

The classifier can't see inside `python3 - <<EOF`, `node -e`, build scripts: those are
`unknown`. For them the engine takes a snapshot before the command and compares after:

    snapshot(root) → {"t": start time, "sig": signature of the dirty/untracked set, "paths": [...]}
    changed(before, root) → True when the set differs, or a listed path was modified after `t`

In a git work tree the set is `git status --porcelain` (ignored files — build output, caches —
are not project changes). Outside git it is every file under the project, walked with a cap and
without hidden or dependency/cache directories; the home directory itself is never walked.
"""
import hashlib
import os
import subprocess
import time

GIT_TIMEOUT = 5
WALK_CAP = 5000  # files looked at under one untracked directory, or in a non-git project


def _git_status(root):
    try:
        r = subprocess.run(["git", "-C", root, "status", "--porcelain=v1", "-z"], capture_output=True,
                           timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    paths, parts, i = [], r.stdout.split(b"\0"), 0
    while i < len(parts):
        entry = parts[i]
        if len(entry) > 3:
            paths.append(os.path.join(root, entry[3:].decode("utf-8", "replace")))
            if entry[:1] in (b"R", b"C"):  # rename/copy: the next field is the source path
                i += 1
        i += 1
    return r.stdout, paths


SKIP_DIRS = {"node_modules", "__pycache__", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache", ".cache"}


def _walk(root):
    """Outside git: every file under the project (hidden and dependency/cache dirs skipped), capped."""
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if not x.startswith(".") and x not in SKIP_DIRS]
        for name in files:
            out.append(os.path.join(d, name))
            if len(out) >= WALK_CAP:
                return out
    return out


def snapshot(root):
    t = time.time()
    if os.path.exists(os.path.join(root, ".git")):
        st = _git_status(root)
        if st is None:
            return None
        raw, paths = st
        return {"t": t, "sig": hashlib.sha256(raw).hexdigest(), "paths": paths}
    if root == os.path.realpath(os.path.expanduser("~")):
        return None  # never walk the whole home directory
    paths = _walk(root)
    return {"t": t, "sig": hashlib.sha256("\0".join(sorted(paths)).encode()).hexdigest(), "paths": paths}


def _modified_since(path, t):
    """The file, or for an untracked directory git lists as one entry, any file under it (bounded)."""
    try:
        if os.stat(path).st_mtime >= t:
            return True
    except OSError:
        return False
    if not os.path.isdir(path) or os.path.islink(path):
        return False
    seen = 0
    for d, dirs, files in os.walk(path):
        for name in files:
            seen += 1
            if seen > WALK_CAP:
                return False
            try:
                if os.lstat(os.path.join(d, name)).st_mtime >= t:
                    return True
            except OSError:
                pass
    return False


def changed(before, root):
    if not before:
        return False
    after = snapshot(root)
    if after is None:
        return False
    if after["sig"] != before["sig"]:
        return True
    return any(_modified_since(p, before["t"]) for p in after["paths"])
