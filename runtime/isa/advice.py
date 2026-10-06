"""Jev's advice at `isa verify` and `isa close`: printed, never blocking, never written into the ISA.

    probe(p, isc, entry)   the first run of a probe that can't be seen failing first: would it fail if the claim
                           were false? A score below `jev_doubt` prints a warning.
    close(p)               the goal, each ask, and each weak tick (attested, or never seen failing): lines under
                           "Jev (advisory — never blocks the close)"; below `jev_doubt` flagged "check it".
A call that is not served prints one `Jev:` line when the cause is the user's to fix (credit, budget).
"""
from . import config, isafile, jev


def _outage(results):
    for r in results:
        if jev.kind(r) in ("credit", "budget"):
            return ["Jev: " + jev.message(r)]
    return []


def probe(p, isc, entry):
    if not jev.enabled() or (p["ver"]["iscs"].get(isc) or {}).get("result"):
        return []
    kind = entry.get("kind")
    if kind == "behaviour" and not isafile.is_anti(p, isc):
        return []
    why = "an Anti criterion" if isafile.is_anti(p, isc) else f"kind `{kind}` has no red run"
    r = jev.ask("isa-probe", {"isc": f"ISC-{isc}", "claim": p["iscs"][isc]["text"], "why_exempt": why,
                              "probe": str(entry.get("tool")), "fails_when": str(entry.get("fails-when") or "")},
                jev.CMD_DEADLINE)
    if r["served"] and r["answer"] < config.number("jev_doubt"):
        return [f"Jev doubts ISC-{isc}'s probe would fail if the claim were false ({r['answer']:.2f}) — tighten it, "
                "or say why it holds (`isa decide`)"]
    return _outage([r])


def _evidence(p):
    lines = []
    for i in isafile.leaves(p):
        res = (p["ver"]["iscs"].get(i) or {}).get("result") or ""
        lines.append(f"ISC-{i}: {p['iscs'][i]['text']} — {res.split(': ', 1)[-1]}")
    return "\n".join(lines)


def close(p):
    if not jev.enabled():
        return []
    ev, items, labels = _evidence(p), [], []
    items.append(("isa-goal", {"stated_goal": str(p["fm"].get("stated_goal") or ""),
                               "goal": p["sections"].get("Goal", ""), "evidence": ev}))
    labels.append("goal delivered")
    for n, a in enumerate(p["fm"].get("asks") or [], 1):
        items.append(("isa-ask", {"ask": str(a), "line": p["ver"]["asks"].get(n, ""), "evidence": ev}))
        labels.append(f"Ask {n} met")
    for i in isafile.leaves(p)[:30]:
        res = (p["ver"]["iscs"].get(i) or {}).get("result") or ""
        if "attested" in res or "(no red baseline)" in res:
            e = isafile.entry(p, i) or {}
            items.append(("isa-claim", {"isc": f"ISC-{i}", "claim": p["iscs"][i]["text"], "threshold": "exit 0",
                                        "how": str(e.get("tool") or "attested"), "evidence": res}))
            labels.append(f"ISC-{i} evidence")
    results = jev.ask_many(items, jev.CMD_DEADLINE)
    doubt = config.number("jev_doubt")
    lines = [f"  - {lab}: {r['answer']:.2f}" + (" — check it" if r["answer"] < doubt else "")
             for lab, r in zip(labels, results) if r["served"]]
    return (["Jev (advisory — never blocks the close):"] + lines if lines else []) + _outage(results)
