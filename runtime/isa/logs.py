"""The debug log: one JSONL file per day under ~/.isa/_state/logs/, written only with DEBUG on.

`write(row)` appends one row when DEBUG is on, and does nothing (opens nothing) when it is off; it never
raises. `isa log [--session ID] [--prompt ID] [--days N]` prints rows; `isa purge-logs [--days N]
[--dry-run]` deletes day files older than N days (7), by the date in their name.
"""
import datetime
import json
import os
import re
import time

from . import state

DEFAULT_DAYS = 7
DAY_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")
_ON = None


def on():
    global _ON
    if _ON is None:
        _ON = state.debug()
    return _ON


def log_dir():
    return os.path.join(state.home(), "_state", "logs")


def write(row):
    if not on():
        return
    try:
        os.makedirs(log_dir(), exist_ok=True)
        line = json.dumps({"t": round(time.time(), 3), **row}, default=str, ensure_ascii=False)
        with open(os.path.join(log_dir(), time.strftime("%Y-%m-%d") + ".jsonl"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001 — a log never changes what a hook decides
        pass


def recent(days=2):
    today = datetime.date.today()
    out = []
    for n in range(days - 1, -1, -1):
        p = os.path.join(log_dir(), (today - datetime.timedelta(days=n)).isoformat() + ".jsonl")
        try:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            continue
    return out


def _opt(args, name, default=None):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default


def log_cmd(args, out=print):
    if not os.path.isdir(log_dir()):
        out("isa log: no debug log — turn DEBUG on (`ISA_DEBUG=1`, or \"debug\": true in ~/.isa/config.json)")
        return 1
    sid, pid = _opt(args, "--session"), _opt(args, "--prompt")
    rows = [r for r in recent(int(_opt(args, "--days", "2"))) if (not sid or r.get("session") == sid)
            and (not pid or r.get("prompt_id") == pid)]
    for r in rows:
        out(json.dumps(r, ensure_ascii=False))
    return 0


def purge_cmd(args, out=print):
    days, dry = int(_opt(args, "--days", DEFAULT_DAYS)), "--dry-run" in args
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    try:
        names = sorted(os.listdir(log_dir()))
    except OSError:
        names = []
    n = 0
    for name in names:
        m = DAY_FILE.match(name)
        if m and datetime.date.fromisoformat(m.group(1)) < cutoff:
            n += 1
            if not dry:
                os.remove(os.path.join(log_dir(), name))
            out(f"{'would delete' if dry else 'deleted'} {name}")
    out(f"isa purge-logs: {n} day file(s) older than {days} days{' (dry run)' if dry else ''}")
    return 0
