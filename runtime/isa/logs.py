"""Debug logs: one JSONL file per day under ~/.isa/_state/logs/ (SPEC-v2 § 11.6), and their purge.

`write(row)` appends one row (`t` added) to today's file. It never raises: a log must not block or
fail a hook. `recent(days=2)` reads the last days' rows (for `isa status`); reading creates nothing.

`isa purge-logs [--days N] [--dry-run]` deletes the day files (`YYYY-MM-DD.jsonl`) whose date is more
than N days before today (default 7). The age comes from the file name, never the mtime. Nothing else
under ~/.isa is touched: the evidence ledger, sessions, prompt logs and ISAs are state, not logs.
Not scheduled by anything; run it by hand (or add a timer later).
"""
import datetime
import json
import os
import re
import time

from . import state

DEFAULT_DAYS = 7
DAY_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")


def log_dir():
    return os.path.join(state.home(), "_state", "logs")


_NOTE = {}


def note(**fields):
    """Extra fields for the current command's debug log row (cli.py writes it when the command ends)."""
    _NOTE.update(fields)


def take_note():
    out = dict(_NOTE)
    _NOTE.clear()
    return out


def write(row):
    try:
        d = log_dir()
        os.makedirs(d, exist_ok=True)
        line = json.dumps({"t": round(time.time(), 3), **row}, default=str, ensure_ascii=False)
        with open(os.path.join(d, time.strftime("%Y-%m-%d") + ".jsonl"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001 — never let a log write change what a hook decides
        pass


def recent(days=2):
    """Rows of the last `days` day files, oldest first."""
    today = datetime.date.today()
    out = []
    for n in range(days - 1, -1, -1):
        path = os.path.join(log_dir(), (today - datetime.timedelta(days=n)).isoformat() + ".jsonl")
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            continue
    return out


def expired(days, today=None):
    """Day files older than `days` days, oldest first, as (path, date)."""
    today = today or datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    try:
        names = os.listdir(log_dir())
    except OSError:
        return []
    out = []
    for name in names:
        m = DAY_FILE.match(name)
        if not m:
            continue
        try:
            day = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if day < cutoff:
            out.append((os.path.join(log_dir(), name), day))
    return sorted(out, key=lambda x: x[1])


def purge_cmd(args, out=print):
    days, dry = DEFAULT_DAYS, False
    it = iter(args)
    for a in it:
        if a == "--dry-run":
            dry = True
        elif a == "--days":
            try:
                days = int(next(it))
                if days < 0:
                    raise ValueError
            except (StopIteration, ValueError):
                out("usage: isa purge-logs [--days N] [--dry-run]   (N: a whole number of days, default 7)")
                return 2
        else:
            out(f"isa purge-logs: unknown option `{a}`")
            return 2
    files = expired(days)
    for path, _day in files:
        out(("would delete " if dry else "deleted ") + path)
        if not dry:
            try:
                os.remove(path)
            except OSError as e:
                out(f"  cannot delete: {e}")
    out(f"isa purge-logs: {'would delete' if dry else 'deleted'} {len(files)} log file(s) older than {days} day(s) "
        f"in {log_dir()}")
    return 0
