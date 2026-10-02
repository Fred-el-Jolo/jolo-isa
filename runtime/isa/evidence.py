"""Evidence: what `isa verify` proved, per ISA. Standard library only.

The model never writes its own evidence. `isa verify <ISA> [ISC-N…]` (commands.py) runs each ISC's
Test Strategy `tool:` command and appends one line per ISC to that ISA's ledger:

    ~/.isa/_state/evidence/<slug>-<hash>.jsonl
    {"v": 2, "t": epoch, "isc": "ISC-3", "kind": "verify|close|attest", "run": "green|red",
     "tool_sha": sha256(tool), "ok": exit == 0, "exit": 0, "secs": 1.2, "root": "/…", "cwd": "/…",
     "tail": "last lines of output", "evidence": "attest text"}

plus `strategy` rows (the Test Strategy as first verified). v1 rows (no `v`) read as green verify
rows. The hooks deny tool writes aimed at the ledger (engine.py).

An ISC is *mechanical* when its Test Strategy entry has a `tool:` and a type other than
SELF_ATTESTED; everything else (manual checks, screenshots, evals, ISCs with no entry — E1)
is self-attested and listed to the user at close. A mechanical ISC is *proven* when the latest
ledger line for it passed and was made with the probe as it reads now (same `tool_sha`), and
*fresh* when that pass is newer than a given time (the session's last project change).
"""
import hashlib
import json
import os

from . import lint, state

SELF_ATTESTED = lint.SELF_ATTESTED
TAIL_CHARS = 800


# ------------------------------------------------------------------ ledger

def ledger_dir():
    return os.path.join(state.home(), "_state", "evidence")  # created by `record`, never by a read


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
    os.makedirs(ledger_dir(), exist_ok=True)
    with open(ledger_path(isa_path), "a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def rows(isa_path):
    """Every ledger row of an ISA, in order (unparseable lines skipped)."""
    out = []
    try:
        with open(ledger_path(isa_path)) as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def latest(isa_path):
    """{isc: latest green probe row} — `isa verify` / `isa close` runs; red baselines and attestations
    are not proof of a probe passing."""
    out = {}
    for row in rows(isa_path):
        if "isc" in row and row.get("run", "green") == "green" and row.get("kind", "verify") in ("verify", "close"):
            out[row["isc"]] = row
    return out


def row_fingerprint(row):
    """The tree fingerprint a row was recorded against; None for a v1 row (no `v`)."""
    return row.get("fingerprint") if row.get("v") else None


def attested(isa_path):
    """{isc: latest attest row}."""
    return {r["isc"]: r for r in rows(isa_path) if r.get("kind") == "attest" and "isc" in r}


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


def unattested_ticks(isa_path, parsed):
    """[(isc, type)] self-attested ISCs ticked with no `isa verify --attest` row. Only for ISAs started
    under v2 (lint.is_v2): a v1 ISA's hand ticks predate the attest command (SPEC-v2 § 8)."""
    if not lint.is_v2(parsed["fm"]):
        return []
    att = attested(isa_path)
    return [(i, t) for i, t in self_attested_ticks(parsed) if i not in att]


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
