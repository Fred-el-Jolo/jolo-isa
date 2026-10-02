"""The ISA problems Stop refuses a turn for, as stable (code, isc) keys — and the `blocked` escalation
(SPEC-v2 § 4.5). Standard library only.

    current(isa_path, text=None, lint_errors=None) → [item]   item = {"code", "isc", "line"}
    render(items) → [problem text]                             grouped, for the Stop message
    record_blocked(isa_path, items)                           a turn ended with these still open
    open_items(isa_path) → [(code, isc)]                      replay of blocked / unblocked rows
    reevaluate(isa_path, text=None) → [(code, isc)]           unblock what no longer holds; → still open

Codes: no-isa (session state only — an ISA-less problem has no ledger), lint-error, tick-unproven,
tick-order, tick-unattested, unclosed, complete-without-close. A blocked item is matched by its key,
never by its wording, so rewording a message never strands an item.
"""
import os
import time

from . import evidence, isafile, lint

HEADS = {
    "tick-unproven": "ticked without a passing `isa verify` run — verify or untick:",
    "tick-order": "ticked out of dependency order — untick until the dependency is done:",
    "tick-unattested": "ticked without `isa verify --attest` (self-attested criteria are ticked by that command; "
                       "untick these):",
}
SHORT = {
    "no-isa": "a turn ended without an ISA",
    "lint-error": "the ISA fails lint",
    "tick-unproven": "ticked without a passing `isa verify` run",
    "tick-order": "ticked out of dependency order",
    "tick-unattested": "ticked without `isa verify --attest`",
    "unclosed": "every criterion is ticked but the ISA is still open",
    "complete-without-close": "`phase: complete` was not written by `isa close`",
}
CLOSE_RESOLVES = {"unclosed", "complete-without-close"}  # what a successful `isa close` itself fixes


def tilde(p):
    h = os.path.expanduser("~")
    return "~" + p[len(h):] if p == h or p.startswith(h + os.sep) else p


def _item(code, isc, line):
    return {"code": code, "isc": isc, "line": line}


def lint_item(isa_path, errors, closing, fmt):
    what = "the close gate (`phase: complete`)" if closing else "lint"
    return _item("lint-error", None, f"{tilde(isa_path)} fails {what}:\n{fmt(errors)}")


def evidence_items(isa_path, parsed, closing):
    items = []
    for i, why in evidence.unproven_ticks(isa_path, parsed):
        items.append(_item("tick-unproven", i, f"  - {i}: {why}"))
    for i, f, d, open_ in evidence.blocked(parsed, sorted(evidence.ticked(parsed))):
        items.append(_item("tick-order", i, f"  - {i} belongs to Feature `{f}`, which depends on `{d}` — "
                                            f"still open in `{d}`: {', '.join(open_)}"))
    for i, t in evidence.unattested_ticks(isa_path, parsed):
        items.append(_item("tick-unattested", i, f"  - {i}: {t}"))
    # freshness is the close's job (`isa close` re-runs every probe, SPEC-v2 § 4.2): no timestamps here
    if closing and lint.is_v2(parsed["fm"]) and not any(r.get("kind") in ("close", "closed") for r in evidence.rows(isa_path)):
        items.append(_item("complete-without-close", None,
                           f"`phase: complete` was not written by `isa close` — run `isa close {tilde(isa_path)}` "
                           "(it re-runs every probe and closes only when all pass)"))
    return items


def unclosed_item(isa_path, parsed):
    if not parsed["counted"] or not all(i in evidence.ticked(parsed) for i in parsed["counted"]):
        return []
    phase = parsed["fm"].get("phase", "?")
    return [_item("unclosed", None,
                  f"every criterion of {tilde(isa_path)} is ticked but `phase` is still `{phase}` — close it: write "
                  f"the `- Goal: yes|no — …` line, then run `isa close {tilde(isa_path)}` (it re-runs every probe "
                  "and sets `phase: complete`); or add the criterion that is still missing")]


def _fmt(errors, limit=12):
    more = f"\n  … and {len(errors) - limit} more (run `isa lint <path>`)" if len(errors) > limit else ""
    return "\n".join(f"  - {e}" for e in errors[:limit]) + more


def current(isa_path, text=None, lint_errors=None):
    """The problems an ISA has right now (no session: no `no-isa`, no stated_goal-vs-prompt check unless
    `lint_errors` are passed in by a caller that has the session)."""
    try:
        text = isafile.normalize(open(isa_path, encoding="utf-8").read() if text is None else text)
    except OSError:
        return []
    parsed = lint.parse(text, isa_path)
    closing = parsed["fm"].get("phase") == "complete"
    if lint_errors is None:
        r = lint.lint(isa_path, "auto", text=text)
        lint_errors = [m for lvl, m in r.items if lvl == "ERROR"]
    items = [lint_item(isa_path, lint_errors, closing, _fmt)] if lint_errors else []
    items += evidence_items(isa_path, parsed, closing)
    if not closing and not lint_errors:
        items += unclosed_item(isa_path, parsed)
    return items


def render(items):
    groups = {}
    for it in items:
        groups.setdefault(it["code"], []).append(it)
    out = []
    for code, its in groups.items():
        if code in HEADS:
            out.append(HEADS[code] + "\n" + "\n".join(it["line"] for it in its))
        else:
            out += [it["line"] for it in its]
    return out


# ------------------------------------------------------------------ the ledger side

def record_blocked(isa_path, items):
    keys = [{"code": it["code"], "isc": it["isc"]} for it in items if it["code"] != "no-isa"]
    if keys:
        evidence.record(isa_path, [{"v": 2, "t": time.time(), "kind": "blocked", "items": keys}])


def open_items(isa_path):
    """[(code, isc)] still open: every `blocked` key not cleared by a later `unblocked` row."""
    open_ = {}
    for row in evidence.rows(isa_path):
        if row.get("kind") == "blocked":
            for k in row.get("items") or []:
                open_[(k.get("code"), k.get("isc"))] = True
        elif row.get("kind") == "unblocked":
            for k in row.get("items") or []:
                open_.pop((k.get("code"), k.get("isc")), None)
    return list(open_)


def reevaluate(isa_path, text=None):
    """Append an `unblocked` row for every open key that no longer holds; → the keys still open."""
    keys = open_items(isa_path)
    if not keys:
        return []
    now = {(it["code"], it["isc"]) for it in current(isa_path, text=text)}
    resolved = [k for k in keys if k not in now]
    if resolved:
        evidence.record(isa_path, [{"v": 2, "t": time.time(), "kind": "unblocked",
                                    "items": [{"code": c, "isc": i} for c, i in resolved]}])
    return [k for k in keys if k in now]


def describe(keys):
    return "\n".join(f"  - {(isc + ': ') if isc else ''}{SHORT.get(code, code)}" for code, isc in keys)
