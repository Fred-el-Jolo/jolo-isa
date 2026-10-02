"""Rules that need more than the ISA file (SPEC-v2 § 6.4, § 6.5, § 3.1 asks): the ledger and the prompt
log. `lint.lint` stays a pure file check (examples, tools/lint_isa.py); these run on top of it in
`isa lint`, `isa verify` / `isa close` (articulation precondition) and the hook-side lint.

    check(isa_path, parsed) → (errors, warnings)

- downgrade (§ 6.4): an entry weaker than the Test Strategy snapshot taken by the first `isa verify`
  (mechanical → self-attested `type`, a `kind:` with a weaker minimum, a `tool:` removed), or a
  self-attested entry whose ISC has a failing probe run, needs `refined: ISC-N probe downgraded — <why>`;
- waiver (§ 6.5): `waived: ISC-N — "<verbatim user words>"`, the quote found in a prompt of a session
  the ISA was bound to;
- asks (§ 3.1): an ask `isa new` extracted may be removed from `asks:` only with a `refined:` row.

Errors for ISAs started under v2, warnings for older ones (spec § 8).
"""
import json
import os
import re

from . import evidence, lint, state

KIND_STRENGTH = {"behaviour": 3, "behavior": 3, "http": 3, "schema": 3, "regression": 2, "config": 2,
                 "visual": 1, "file": 1, "doc": 0, "decision": 0}


def _mechanical(entry):
    return bool(entry) and bool(str(entry.get("tool") or "").strip()) and \
        str(entry.get("type") or "") not in lint.SELF_ATTESTED


def _downgrades(isa_path, parsed):
    rows = evidence.rows(isa_path)
    snap = next((r.get("entries") or {} for r in rows if r.get("kind") == "strategy"), {})
    failed = {r["isc"] for r in rows if r.get("isc") and r.get("kind") in ("verify", "close")
              and r.get("run", "green") == "green" and not r.get("ok")}
    out = []
    for i, e in parsed["test_strategy"].items():
        was = snap.get(i)
        why = None
        if was:
            was_mech = bool(was.get("tool_sha")) and str(was.get("type") or "") not in lint.SELF_ATTESTED
            if was_mech and not _mechanical(e):
                why = f"was a runnable `{was.get('type')}` probe, now `{e.get('type')}`" + \
                      ("" if str(e.get("tool") or "").strip() else " with no `tool:`")
            elif KIND_STRENGTH.get(str(e.get("kind") or "").lower(), 3) < \
                    KIND_STRENGTH.get(str(was.get("kind") or "").lower(), 0):
                why = f"`kind:` weakened from `{was.get('kind')}` to `{e.get('kind')}`"
        if why is None and i in failed and not _mechanical(e):
            why = "its probe failed, and it is now self-attested"
        if why and not re.search(rf"refined: {re.escape(i)} probe downgraded — \S", parsed["content"].get("Decisions", "")):
            out.append(f"Test Strategy: {i} probe downgraded ({why}) — needs a Decisions row "
                       f"`refined: {i} probe downgraded — <why>`")
    return out


def sessions_of(isa_path):
    """(harness, session) of every session the ISA was bound to (now or earlier)."""
    real = os.path.realpath(isa_path)
    d = os.path.join(state.home(), "_state", "sessions")
    out = []
    try:
        names = os.listdir(d)
    except OSError:
        return out
    for f in names:
        if not f.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, f)) as fh:
                st = json.load(fh)
        except (OSError, ValueError):
            continue
        if st.get("bound") == real or real in (st.get("bound_history") or []):
            out.append(f[:-len(".json")])
    return out


def _session_prompts(stem):
    try:
        with open(os.path.join(state.home(), "_state", "prompts", stem + ".jsonl"), encoding="utf-8") as f:
            return [json.loads(line).get("text") or "" for line in f if line.strip()]
    except (OSError, ValueError):
        return []


def _waivers(isa_path, parsed):
    out = []
    prompts = None
    for line in parsed["content"].get("Decisions", "").splitlines():
        m = re.search(r"waived: (ISC-\d+(?:\.\d+)*)(.*)$", line)
        if not m:
            continue
        q = re.search(r"[\"“](.+?)[\"”]", m.group(2))
        if not q:
            out.append(f"Decisions: `waived: {m.group(1)}` must quote the user: "
                       f"`waived: {m.group(1)} — \"<verbatim user words>\"` (only the user can waive)")
            continue
        if prompts is None:
            prompts = [p for stem in sessions_of(isa_path) for p in _session_prompts(stem)]
        if not any(q.group(1) in p for p in prompts):
            out.append(f"Decisions: the quote in `waived: {m.group(1)}` is not in any prompt of this ISA's sessions "
                       "— copy the user's words byte-for-byte")
    return out


def _asks(isa_path, parsed):
    extracted = next((r.get("asks") or [] for r in evidence.rows(isa_path) if r.get("kind") == "asks"), [])
    now = parsed["fm"].get("asks") if isinstance(parsed["fm"].get("asks"), list) else []
    gone = [a for a in extracted if a not in now]
    if gone and not re.search(r"refined:.*\bask", parsed["content"].get("Decisions", ""), re.I):
        return [f"frontmatter: ask removed from `asks:` without a `refined:` Decisions row: \"{gone[0][:60]}\""]
    return []


def check(isa_path, parsed):
    found = _downgrades(isa_path, parsed) + _waivers(isa_path, parsed) + _asks(isa_path, parsed)
    return (found, []) if lint.is_v2(parsed["fm"]) else ([], found)
