"""Rules that need more than the ISA file (SPEC-v2 § 6.4, § 6.5, § 3.1 asks): the ledger and the prompt
log. `lint.lint` stays a pure file check (examples, tools/lint_isa.py); these run on top of it in
`isa lint`, `isa verify` / `isa close` (articulation precondition) and the hook-side lint.

    check(isa_path, parsed) → (errors, warnings)

- downgrade (§ 6.4): an entry weaker than the Test Strategy snapshot taken by the first `isa verify`
  (mechanical → self-attested `type`, a `kind:` with a weaker minimum, a `tool:` removed), or a
  self-attested entry whose ISC has a failing probe run, needs `refined: ISC-N probe downgraded — <why>`;
- waiver (§ 6.5): `waived: ISC-N — "<verbatim user words>"`, the quote found in a prompt of a session
  the ISA was bound to;
- asks (§ 3.1, § 11.2): each ask is a verbatim span of a prompt of the ISA's sessions (the model writes
  them); an ask in the snapshot taken by the first `isa verify` may be removed only with a `refined:` row.

Errors for ISAs started under v2, warnings for older ones (spec § 8).
"""
import json
import os
import re

from . import crypt, evidence, lint, state

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


# ------------------------------------------------------------------ quotes checked on another machine (§ 13.4)

def _repo_key(isa_path):
    return crypt.key() if state.isa_repo(isa_path) else None


def verified_tags(isa_path):
    return {t for r in evidence.rows(isa_path) if r.get("kind") == "quote-verified" for t in r.get("tags") or []}


def mark_verified(isa_path, spans):
    """A repo ISA's quotes found in this machine's prompt log: recorded as keyed HMACs, so lint accepts them on a
    machine whose prompt log doesn't hold them. Never the words themselves."""
    k = _repo_key(isa_path)
    if not k:
        return
    have = verified_tags(isa_path)
    new = sorted({crypt.tag(s, k) for s in spans if s} - have)
    if new:
        import time
        evidence.record(isa_path, [{"v": 2, "t": time.time(), "kind": "quote-verified", "tags": new}])


def quote_ok(isa_path, span, prompts):
    """Is `span` the user's words — in a logged prompt here, or verified earlier (a `quote-verified` tag)?"""
    k = _repo_key(isa_path)
    if k and crypt.tag(span, k) in verified_tags(isa_path):
        return True
    if any(span in p for p in prompts):
        mark_verified(isa_path, [span])
        return True
    return False


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
        if not quote_ok(isa_path, q.group(1).replace('\\"', '"'), prompts):
            out.append(f"Decisions: the quote in `waived: {m.group(1)}` is not in any prompt of this ISA's sessions "
                       "— copy the user's words byte-for-byte")
    return out


def _asks(isa_path, parsed):
    out = []
    snapshot = next((r.get("asks") or [] for r in evidence.rows(isa_path) if r.get("kind") == "asks"), [])
    now = parsed["fm"].get("asks") if isinstance(parsed["fm"].get("asks"), list) else []
    k = _repo_key(isa_path)
    # a repo ISA's snapshot holds keyed HMACs, never the words (§ 13.5)
    present = set(now) | ({crypt.tag(str(a), k) for a in now} if k else set())
    gone = [a for a in snapshot if a not in present]
    if gone and not re.search(r"refined:.*\bask", parsed["content"].get("Decisions", ""), re.I):
        shown = "an ask" if str(gone[0]).startswith("hmac:") else f"\"{str(gone[0])[:60]}\""
        out.append(f"frontmatter: ask removed from `asks:` without a `refined:` Decisions row: {shown}")
    if now:
        prompts = [p for stem in sessions_of(isa_path) for p in _session_prompts(stem)]
        verified = verified_tags(isa_path) if k else set()
        if prompts or verified:  # no logged prompt and nothing verified: nothing to check against
            for a in now:
                if not quote_ok(isa_path, str(a), prompts):
                    out.append(f"frontmatter: ask \"{str(a)[:60]}\" is not a verbatim span of a prompt of this ISA's "
                               "sessions — copy the user's words byte-for-byte")
    return out


def _loose_quotes(isa_path, parsed):
    """A repo ISA quoting ≥ 6 words of a logged prompt outside the quoting forms of § 13.5 would push them to git
    in plain text → a warning (the model should use `user: "…"`)."""
    if not state.isa_repo(isa_path):
        return []
    prompts = [p for stem in sessions_of(isa_path) for p in _session_prompts(stem)]
    shingles = set()
    for p in prompts:
        w = p.split()
        shingles.update(" ".join(w[i:i + 6]) for i in range(max(0, len(w) - 5)))
    if not shingles:
        return []
    from . import quotes
    out = []
    for sec in ("Decisions", "Changelog", "Verification"):
        for line in parsed["content"].get(sec, "").splitlines():
            bare = line
            for a, b in reversed(quotes.body_forms(line)):
                bare = bare[:a] + bare[b:]
            w = bare.split()
            if any(" ".join(w[i:i + 6]) in shingles for i in range(max(0, len(w) - 5))):
                out.append(f"{sec}: a line quotes the user's prompt outside the quoting forms — write it as "
                           f"`user: \"<words>\"` so it is encrypted in git, or in your own words: {line.strip()[:70]}")
    return out


def check(isa_path, parsed):
    found = _downgrades(isa_path, parsed) + _waivers(isa_path, parsed) + _asks(isa_path, parsed)
    errs, warns = (found, []) if lint.is_v2(parsed["fm"]) else ([], found)
    return errs, warns + _loose_quotes(isa_path, parsed)
