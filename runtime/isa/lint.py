"""The TASK ISA's rules, as a pure check of its text (and of its spec, from E2).

    errors(text, path, moment="draft"|"close") → [message]

draft: the shape — sections per tier, the criteria tree (depth, ids, one Anti), one probe per leaf and none on a
parent, the probe kinds, the spec link and the anchors. close: also every leaf proven, the Goal and Ask lines,
and (from E2) both acks holding.
"""
import os
import re

from . import classify, doc, isafile, spec, state

RED_KINDS = ("behaviour",)


def errors(text, path=None, moment="draft"):
    p = isafile.parse(text)
    fm, out = p["fm"], list(p["errors"])
    tier = isafile.tier(p)
    if tier == "E5":
        out.append("effort: E5 is gone — E4 has no depth limit")
    if tier not in isafile.DEPTH:
        out.append(f"effort: `{fm.get('effort')}` is not E1–E4")
        return out
    out += _sections(p, tier)
    out += _criteria(p, tier)
    out += _tests(p, tier)
    sp = _spec(p, path, tier, out)
    if moment == "close":
        out += close_errors(p, text, tier, sp)
    return out


def _sections(p, tier):
    out, secs = [], p["sections"]
    for h in secs:
        if h not in isafile.SECTIONS:
            out.append(f"`## {h}` is not an ISA section" + (" (Features are gone: the criteria tree is the breakdown)"
                                                            if h == "Features" else ""))
    if tier == "E1":
        out += [f"E1 has no `## {h}`" for h in isafile.E1_FORBIDDEN if h in secs]
        need = isafile.E1_REQUIRED
    else:
        need = isafile.CONTENT
    for h in need:
        if h not in secs:
            out.append(f"missing `## {h}`" + ("" if h in ("Criteria", "Test Strategy") else f" (`isa write <ISA> \"{h}\"`)"))
        elif not secs[h].strip():
            out.append(f"`## {h}` is empty")
    heads = [h for h in secs if h in isafile.SECTIONS]
    if heads != sorted(heads, key=isafile.SECTIONS.index):
        out.append("sections are out of order: " + ", ".join(isafile.SECTIONS))
    return out


def _criteria(p, tier):
    out, cap = [], isafile.DEPTH[tier]
    if not p["order"]:
        return ["no criteria (`isa write <ISA> Criteria`)"] if "Criteria" in p["sections"] else []
    for i in p["order"]:
        isc = p["iscs"][i]
        if isc["indent"] != 2 * (isc["level"] - 1):
            out.append(f"ISC-{i}: its indent doesn't match its id (two spaces per level)")
        if "." in i and i.rsplit(".", 1)[0] not in p["iscs"]:
            out.append(f"ISC-{i}: no parent ISC-{i.rsplit('.', 1)[0]}")
        if cap and isc["level"] > cap:
            out.append(f"ISC-{i} is nested {isc['level']} levels; {tier} allows {cap}")
    if not any(isafile.is_anti(p, i) for i in isafile.leaves(p)):
        out.append("no `Anti:` criterion (at least one, at every tier)")
    return out


def _tests(p, tier):
    if p["tests_error"]:
        return [p["tests_error"]]
    out, seen = [], set()
    leaves = isafile.leaves(p)
    for e in p["tests"]:
        i = str(e.get("isc", "")).replace("ISC-", "")
        if i not in p["iscs"]:
            out.append(f"Test Strategy: ISC-{i} is not a criterion")
            continue
        if p["iscs"][i]["children"]:
            out.append(f"Test Strategy: ISC-{i} is a parent — its children carry the probes")
            continue
        if p["iscs"][i]["dropped"]:
            out.append(f"Test Strategy: ISC-{i} is dropped")
            continue
        if i in seen:
            out.append(f"Test Strategy: ISC-{i} has two entries")
        seen.add(i)
        kind = e.get("kind")
        if kind not in isafile.KINDS:
            out.append(f"Test Strategy: ISC-{i} `kind` is one of {', '.join(isafile.KINDS)}")
        if kind != "manual" and not str(e.get("tool") or "").strip():
            out.append(f"Test Strategy: ISC-{i} has no `tool` (the probe's command)")
        elif kind != "manual" and classify.bash(str(e["tool"]), str(p["fm"].get("root") or "")) == "guarded":
            out.append(f"Test Strategy: ISC-{i}'s probe writes an ISA, a spec, a plan or ~/.isa (a probe never "
                       f"changes an ISA entity): `{e['tool']}`")
        if kind != "manual" and (kind not in RED_KINDS or isafile.is_anti(p, i)) and not e.get("fails-when"):
            out.append(f"Test Strategy: ISC-{i} needs `fails-when` (it can't be seen failing first)")
        if e.get("parallel") is not None:
            out.append(f"Test Strategy: ISC-{i} `parallel` is reserved for later")
        if tier != "E1" and not re.fullmatch(r"S\d+|Goal", str(e.get("anchors_to") or "")):
            out.append(f"Test Strategy: ISC-{i} `anchors_to` names a spec section (`S2`) or `Goal`")
    out += [f"ISC-{i} has no Test Strategy entry" for i in leaves if i not in seen]
    return out


def _spec(p, path, tier, out):
    if tier == "E1":
        if p["fm"].get("spec"):
            out.append("E1 has no spec")
        return None
    rel = p["fm"].get("spec")
    if not rel:
        out.append(f"{tier} needs its spec (`isa new --spec <spec>`)")
        return None
    root = str(p["fm"].get("root") or "")
    sp = rel if os.path.isabs(str(rel)) else os.path.join(root, str(rel))
    if not os.path.isfile(sp) and path:  # an example: its spec sits beside it
        sp = os.path.join(os.path.dirname(os.path.abspath(path)), str(rel))
    try:
        with open(sp, encoding="utf-8") as f:
            stext = f.read()
    except OSError:
        out.append(f"spec {rel} not found")
        return None
    secs = {re.match(r"S\d+", h).group(0) for h in spec.s_sections(stext)}
    anchors = {str(e.get("anchors_to")) for e in p["tests"]}
    for s in sorted(secs - anchors):
        out.append(f"spec section {s} has no criterion anchored to it")
    for a in sorted(x for x in anchors - secs if x.startswith("S")):
        out.append(f"anchors_to {a}: no such section in the spec")
    return {"path": sp, "text": stext}


def close_errors(p, text, tier, sp):
    out = []
    v = p["ver"]
    for i in isafile.leaves(p):
        if p["iscs"][i]["box"] != "x":
            out.append(f"ISC-{i} is not proven (`isa verify`, or `isa attest` for a manual one)")
    if not v["goal"] or not v["goal"].startswith("- Goal: yes"):
        out.append('no `- Goal: yes` line (`isa answer <ISA> goal "yes — <evidence>"`)')
    asks = p["fm"].get("asks") or []
    for n in range(1, len(asks) + 1):
        if n not in v["asks"]:
            out.append(f'no `- Ask {n}:` line (`isa answer <ISA> ask {n} "met — <evidence>"`)')
    if tier != "E1" and sp:
        if not spec.is_acked(sp["text"]):
            out.append("the spec is not acked as it is now")
        elif p["fm"].get("spec_hash") != spec.ack_hash(sp["text"]):
            out.append("the spec changed since this ISA was derived (`isa refine`)")
        if not isafile.acked(text):
            out.append("the ISA is not acked as it is now")
    return out


def main(argv, out=print):
    rc = 0
    moment = "draft"
    if argv[:1] == ["--close"]:
        moment, argv = "close", argv[1:]
    for path in argv:
        try:
            with open(os.path.expanduser(path), encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            out(f"{path}: cannot read ({e})")
            rc = 1
            continue
        errs = spec.lint(text) if state.is_doc_path(path) and path.endswith("-01-spec.md") else \
            errors(text, path, moment)
        out(f"{path}: {'ok' if not errs else f'{len(errs)} error(s)'}")
        for e in errs:
            out(f"  ERROR: {e}")
        rc = max(rc, 1 if errs else 0)
    return rc
