"""The commits of the lifecycle: the spec after its ack, the work and the plan after a passing close.

`snapshot(root)` is taken by `isa new`: the files already changed then are the user's, never committed by the
close. `changed_since(root, base_dirty)` is what the task changed. Outside git every call is a no-op.
"""
import os
import subprocess


def _git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def repo(root):
    r = _git(root, "rev-parse", "--show-toplevel")
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def dirty(root):
    """Paths (relative to the repo root) with uncommitted changes, untracked files included."""
    r = _git(root, "status", "--porcelain", "--untracked-files=all", "-z")
    out, items = [], r.stdout.split("\0") if r.returncode == 0 else []
    i = 0
    while i < len(items):
        it = items[i]
        if len(it) > 3:
            out.append(it[3:])
            if it[0] in "RC":
                i += 1
                if it[0] == "R" and i < len(items) and items[i]:
                    out.append(items[i])  # a rename's old path: its deletion belongs to the same commit
        i += 1
    return sorted(set(out))


def snapshot(root):
    """→ {"base_dirty": [paths]} for the ISA's frontmatter, or {} outside git."""
    return {"base_dirty": dirty(root)} if repo(root) else {}


def changed_since(root, base_dirty, exclude=()):
    top = repo(root)
    if not top:
        return []
    skip = set(base_dirty or []) | {os.path.relpath(os.path.realpath(p), top) for p in exclude}
    return [p for p in dirty(root) if p not in skip]


def commit(root, paths, message):
    """Commit exactly these paths. → (short sha, None); (None, None) outside git or with nothing to commit;
    (None, git's first error line) when the commit fails (a pre-commit hook, signing, identity)."""
    top = repo(root)
    if not top or not paths:
        return None, None
    rel = [os.path.relpath(os.path.realpath(os.path.join(top, p)), top) if not os.path.isabs(p)
           else os.path.relpath(os.path.realpath(p), top) for p in paths]
    here = [p for p in rel if os.path.lexists(os.path.join(top, p))]
    gone = [p for p in rel if p not in here]  # a deletion (a rename's old path): `git add` would refuse the pathspec
    if here:
        _git(top, "add", "-A", "--", *here)
    if gone:
        _git(top, "rm", "--cached", "-q", "--ignore-unmatch", "--", *gone)
    if _git(top, "diff", "--cached", "--quiet", "--", *rel).returncode == 0:
        return None, None
    r = _git(top, "commit", "-q", "-m", message, "--", *rel)
    if r.returncode != 0:
        lines = [ln.strip() for ln in (r.stderr + "\n" + r.stdout).splitlines() if ln.strip()]
        return None, lines[0] if lines else f"git commit exited {r.returncode}"
    return _git(top, "rev-parse", "--short", "HEAD").stdout.strip(), None
