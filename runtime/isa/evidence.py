"""Evidence: what `isa verify` proved, per ISA. Standard library only.

The model never writes its own evidence. `isa verify <ISA> [ISC-N…]` runs each ISC's
Test Strategy `tool:` command and appends one line per ISC to that ISA's ledger:

    ~/.isa/_state/evidence/<slug>-<hash>.jsonl
    {"t": epoch, "isc": "ISC-3", "tool_sha": sha256(tool), "ok": exit == 0, "exit": 0, "secs": 1.2,
     "cwd": "/…", "tail": "last lines of output"}

The hooks deny tool writes aimed at the ledger (engine.py).

An ISC is *mechanical* when its Test Strategy entry has a `tool:` and a type other than
SELF_ATTESTED; everything else (manual checks, screenshots, evals, ISCs with no entry — E1)
is self-attested and listed to the user at close. A mechanical ISC is *proven* when the latest
ledger line for it passed and was made with the probe as it reads now (same `tool_sha`), and
*fresh* when that pass is newer than a given time (the session's last project change).
"""
import hashlib
import json
import os
import subprocess
import time

from . import lint, state

SELF_ATTESTED = lint.SELF_ATTESTED
TAIL_CHARS = 800


# ------------------------------------------------------------------ ledger

def ledger_dir():
    return state.state_dir("evidence")


def ledger_path(isa_path):
    real = os.path.realpath(isa_path)
    slug = os.path.basename(os.path.dirname(real))[:60]
    return os.path.join(ledger_dir(), f"{slug}-{hashlib.sha256(real.encode()).hexdigest()[:12]}.jsonl")


def is_ledger_path(path):
    try:
        p = os.path.realpath(os.path.expanduser(path))
    except (TypeError, ValueError):
        return False
    d = os.path.realpath(os.path.join(state.home(), "_state", "evidence"))
    return p == d or p.startswith(d + os.sep)


def tool_sha(tool):
    return hashlib.sha256(str(tool).strip().encode()).hexdigest()


def record(isa_path, rows):
    with open(ledger_path(isa_path), "a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def latest(isa_path):
    """{isc: latest ledger row}."""
    out = {}
    try:
        with open(ledger_path(isa_path)) as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and "isc" in row:
                    out[row["isc"]] = row
    except OSError:
        pass
    return out


# ------------------------------------------------------------------ probes and proof

def probes(parsed):
    """{isc: {"type", "tool", "mechanical"}} for every counted leaf ISC."""
    out = {}
    for i in parsed["counted"]:
        e = parsed["test_strategy"].get(i) or {}
        tool = e.get("tool")
        typ = str(e.get("type", "")) if e else ""
        mech = bool(e) and isinstance(tool, str) and bool(tool.strip()) and typ not in SELF_ATTESTED
        out[i] = {"type": typ or "no probe", "tool": tool if mech else None, "mechanical": mech}
    return out


def ticked(parsed):
    return {i for i in parsed["counted"] if parsed["iscs"][i][0]}


def status(isa_path, parsed, isc, since=None, _rows=None, _pr=None):
    """'proven' | 'none' (never run) | 'failed' | 'changed' (probe edited since) | 'stale' (pass older
    than `since`) for one mechanical ISC."""
    row = (latest(isa_path) if _rows is None else _rows).get(isc)
    if not row:
        return "none"
    if row.get("tool_sha") != tool_sha((probes(parsed) if _pr is None else _pr)[isc]["tool"]):
        return "changed"
    if not row.get("ok"):
        return "failed"
    if since is not None and row.get("t", 0) <= since:
        return "stale"
    return "proven"


_WHY = {"none": "never run through `isa verify`", "failed": "its latest `isa verify` run failed",
        "changed": "its probe changed after the last run", "stale": "its pass is older than the last project change"}


def unproven(isa_path, parsed, iscs, since=None):
    """[(isc, reason)] for the mechanical ISCs among `iscs` that are not proven (fresh after `since`)."""
    pr, rows = probes(parsed), latest(isa_path)
    out = []
    for i in iscs:
        if i in pr and pr[i]["mechanical"]:
            s = status(isa_path, parsed, i, since, rows, pr)
            if s != "proven":
                out.append((i, _WHY[s]))
    return out


def unproven_ticks(isa_path, parsed, since=None):
    done = ticked(parsed)
    return unproven(isa_path, parsed, [i for i in parsed["counted"] if i in done], since)


def pending_ticks(isa_path, parsed, since):
    """Open mechanical ISCs whose probe passed after `since` and that may be ticked now: proven, not
    blocked by an unfinished Feature dependency (those wait; they must not freeze other work)."""
    pr, rows, done = probes(parsed), latest(isa_path), ticked(parsed)
    return [i for i in parsed["counted"] if i not in done and pr[i]["mechanical"]
            and status(isa_path, parsed, i, since, rows, pr) == "proven" and not blocked(parsed, [i])]


def self_attested_ticks(parsed):
    pr = probes(parsed)
    return [(i, pr[i]["type"]) for i in parsed["counted"] if i in ticked(parsed) and not pr[i]["mechanical"]]


def _members(parsed, feature):
    """The counted leaf ISCs a Feature covers (a listed parent stands for its leaves)."""
    counted = parsed["counted"]
    out = []
    for s in feature.get("satisfies") or []:
        out += [s] if s in counted else [c for c in counted if c.startswith(f"{s}.")]
    return out


def blocked(parsed, iscs, treat_open=()):
    """[(isc, feature, dependency, [open ISCs])] for each ISC among `iscs` whose Feature depends on a
    Feature that still has open ISCs. `treat_open` counts those ISCs as open (the state before an edit)."""
    feats = parsed.get("features") or []
    by_name = {f.get("name"): f for f in feats}
    done = ticked(parsed) - set(treat_open)
    out = []
    for i in iscs:
        for f in feats:
            if i not in _members(parsed, f):
                continue
            for d in f.get("depends_on") or []:
                if d in by_name:
                    open_ = [j for j in _members(parsed, by_name[d]) if j not in done and j != i]
                    if open_:
                        out.append((i, f.get("name"), d, open_))
    return out


def describe_blocked(rows):
    return "\n".join(f"  - {i} belongs to Feature `{f}`, which depends on `{d}` — still open in `{d}`: "
                     f"{', '.join(open_)}" for i, f, d, open_ in rows)


def describe(pairs):
    return "\n".join(f"  - {i}: {why}" for i, why in pairs)


# ------------------------------------------------------------------ isa verify

def run(isa_path, select=None, cwd=None, timeout=600, out=print):
    """Run the probes of `select` (default: every mechanical ISC), record them, report. → exit code."""
    try:
        text = open(isa_path, encoding="utf-8").read()
    except OSError as e:
        out(f"isa verify: cannot read {isa_path}: {e}")
        return 2
    parsed = lint.parse(text, isa_path)
    pr = probes(parsed)
    unknown = [i for i in (select or []) if i not in pr]
    if unknown:
        out(f"isa verify: not a counted leaf ISC of this ISA: {', '.join(unknown)}")
        return 2
    chosen = list(select) if select else [i for i in parsed["counted"] if pr[i]["mechanical"]]
    cwd = cwd or os.getcwd()
    results, rows, failed = {}, [], False
    for i in chosen:
        p = pr[i]
        if not p["mechanical"]:
            out(f"{i} SKIP  {p['type']} — self-attested, not run (listed to the user at close)")
            continue
        tool = p["tool"].strip()
        if tool not in results:  # ISCs sharing a probe run it once
            t0 = time.time()
            try:
                r = subprocess.run(tool, shell=True, executable="/bin/bash", cwd=cwd, capture_output=True,
                                   text=True, timeout=timeout)
                code, output = r.returncode, (r.stdout or "") + (r.stderr or "")
            except subprocess.TimeoutExpired as e:
                code = 124
                output = f"{e.stdout or ''}{e.stderr or ''}\n[timed out after {timeout}s]"
            results[tool] = (code, round(time.time() - t0, 2), output[-TAIL_CHARS:])
        code, secs, tail = results[tool]
        ok = code == 0
        failed |= not ok
        rows.append({"t": time.time(), "isc": i, "tool_sha": tool_sha(tool), "ok": ok, "exit": code,
                     "secs": secs, "cwd": cwd, "tail": tail})
        out(f"{i} {'PASS' if ok else 'FAIL'}  exit {code}  {secs}s  {tool}")
        if not ok:
            out("\n".join("    " + line for line in tail.rstrip().splitlines()[-15:]))
    if rows:
        record(isa_path, rows)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    waiting = blocked(parsed, [r["isc"] for r in rows if r["ok"] and r["isc"] not in ticked(parsed)])
    for i, f, d, open_ in waiting:
        out(f"{i} blocked — Feature `{f}` depends on `{d}` (still open: {', '.join(open_)}); "
            f"the pass is recorded, tick {i} once `{d}` is done")
    todo = [r["isc"] for r in rows if r["ok"] and r["isc"] not in ticked(parsed)
            and r["isc"] not in {w[0] for w in waiting}]
    if todo:
        out(f"\nPassed and not ticked yet — tick now; the hooks refuse other changes until you do: {', '.join(todo)}")
        out("Verification lines:")
        for r in rows:
            if r["isc"] in todo:
                out(f"- {r['isc']}: `isa verify` PASS {stamp} — `{pr[r['isc']]['tool'].strip()}`")
    if not rows and not failed:
        out("nothing to run: no mechanical ISC selected")
    return 1 if failed else 0
