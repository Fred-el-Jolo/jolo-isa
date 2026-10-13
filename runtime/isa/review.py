"""The review of an E2–E4 ISA (`isa review`) and the trace the user reads before its ack (`isa show --trace`).

    isa review <ISA>                       the model's checklist on stdin, then Jev's check, into `## Review`
    isa review <ISA> --answer R<n> "<a>"   answer one flag: `keep: …`, `drop: …`, `fix: …` or `reopen: …`

The checklist is the model's reading of the spec and the ISA whole: seven lines, each a finding or `none`; the
seventh, `redundant`, names the criteria that are not needed, duplicated or malformed.
Jev then asks, in as few requests as the token budget allows (one, for any usual ISA):
    serves   per leaf      does it help solve the spec's Problem and reach its Goal?   flagged at no ≥ jev_serves
    covered  per section   do the criteria under ISC-k cover what Sk accepts?          flagged at no ≥ jev_covered
Every flag needs an answer before the ISA ack; Jev never blocks on its own. The review is bound to the criteria
it read (`reviewed: <hash8>`): a criterion changed after it needs a new review.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from . import commands, config, doc, isafile, jev, lint, spec
from .commands import Refused

DEADLINE = 10.0
LONGEST_BUDGET, REQUEST_BUDGET = 32000, 64000  # tokens: state + the longest question; state + all questions
PREFIXES = ("keep:", "drop:", "fix:", "reopen:")
QUESTIONS = ("Judge the criterion itself, never where it came from: Necessary? (what would go wrong, unnoticed, "
             "without it) Duplicate? (another criterion, or a test an existing probe already runs, proves the same) "
             "Malformed? (a vague claim, a probe that misses the claim, the wrong kind)")
ANSWERS = ("`keep: <what would go unnoticed without it>`, `drop: <duplicate of … / not needed because …>` (after "
           "`isa drop`), `fix: <what was malformed, and the change>` (after `isa write`), or `reopen: <the spec "
           "change>`")
SPEC_REASON = re.compile(r"\bS\d+\b|\bthe spec\b|accepted[ -]when", re.I)


# ------------------------------------------------------------------ the command

def cmd(args, stdin_text, out=print):
    args = list(args)
    answer = None
    if "--answer" in args:
        i = args.index("--answer")
        if len(args) < i + 3:
            raise Refused('usage: isa review <ISA> --answer R<n> "<keep: …|drop: …|fix: …|reopen: …>"')
        answer, args = (args[i + 1], " ".join(args[i + 2:])), args[:i]
    path, _ = commands._file(args, ("isa",))
    text = commands._read(path)
    commands._open_isa(text)
    p = isafile.parse(text)
    if isafile.tier(p) == "E1":
        raise Refused("an E1 ISA has no spec to review against: build it")
    sp = os.path.join(str(p["fm"].get("root")), str(p["fm"].get("spec") or ""))
    stext = commands._read(sp)
    if answer:
        return _answer(path, text, p, stext, sp, *answer, out=out)
    errs = lint.errors(text, path)
    if errs:
        raise Refused("the ISA doesn't lint yet, so it can't be reviewed:\n" + "\n".join(f"  - {e}" for e in errs[:12]))
    found = _checklist(stdin_text)
    missing = [k for k in isafile.CHECKLIST if k not in found]
    if missing:
        raise Refused("the checklist misses " + ", ".join(f"`{k}:`" for k in missing) + " — seven lines on stdin, "
                      "each a finding or `none`: " + ", ".join(f"{k}:" for k in isafile.CHECKLIST)
                      + " (`redundant:` the criteria not needed, duplicated or malformed)")
    if found["contradictions"].lower() != "none" and spec.is_acked(stext):
        raise Refused(f"a contradiction between sections is the spec's to fix: `isa reopen {commands._tilde(sp)}`, "
                      "fix it, ask the `Spec ack` again, then review")
    flags, jev_line = _jev_check(p, stext)
    lines = [f"Reviewed {isafile.now()} · criteria #{isafile.review_hash(text)} · {jev_line}"]
    lines += [f"- {k}: {found[k]}" for k in isafile.CHECKLIST]
    if flags:
        lines += ["", "Flags (each needs an answer before the ISA ack):"]
        lines += [f"- R{n}: {f['kind']} {f['about']} — no {f['no']:.2f} ≥ {f['threshold']:.2f} — {f['question']} — "
                  "answer: (open)" for n, f in enumerate(flags, 1)]
    new = doc.set_section(text, "Review", "\n".join(lines), isafile.SECTIONS)
    new = isafile.refresh(doc.fm_set(new, "reviewed", isafile.review_hash(text)))
    new = doc.fm_set(new, "flag_parts", " ".join(f"{f['about']}={isafile.subtree_hash(p, f['about'])}" for f in flags)
                     or None)
    commands._write(path, new)
    out(f"reviewed {commands._tilde(path)} — {jev_line}, {len(flags)} flag(s)")
    for ln in lines[len(isafile.CHECKLIST) + 1:]:
        if ln.startswith("- R"):
            out(ln)
    out(f"{QUESTIONS}. Answer each flag: {ANSWERS}. Then `isa show <ISA> --trace` for the user and the `ISA ack` "
        "question." if flags else "Next: `isa show <ISA> --trace` for the user, then the `ISA ack` question.")
    return 0


def _checklist(stdin_text):
    found = {}
    for ln in (stdin_text or "").split("\n"):
        m = re.match(rf"^\s*-?\s*({'|'.join(isafile.CHECKLIST)}):\s*(.+)$", ln)
        if m:
            found[m.group(1)] = m.group(2).strip()
    return found


def _answer(path, text, p, stext, sp, flag, answer, out):
    answer = answer.strip()
    if not answer.startswith(PREFIXES):
        raise Refused(f"an answer starts with `keep:`, `drop:`, `fix:` or `reopen:`. {QUESTIONS}. Answers: {ANSWERS}")
    if answer.startswith("reopen:") and spec.is_acked(stext):
        raise Refused(f"`reopen:` needs the spec reopened first: `isa reopen {commands._tilde(sp)}`")
    r = p["review"]
    if not r or flag not in [f["id"] for f in r["flags"]]:
        raise Refused(f"no flag {flag} in the review")
    about = next(f["about"] for f in r["flags"] if f["id"] == flag)
    t = commands._tilde(path)
    if answer.startswith("keep:") and SPEC_REASON.search(answer):
        raise Refused("`keep:` says what would go wrong, unnoticed, without the criterion — not where it came from "
                      "(a section, the spec, its Accepted-when lines). " + QUESTIONS)
    if answer.startswith("drop:"):
        if not about.startswith("ISC-"):
            raise Refused(f"{flag} is about a section's coverage: answer `keep:`, `fix:` or `reopen:`")
        if not p["iscs"].get(about[4:], {}).get("dropped"):
            raise Refused(f"`drop:` once it is dropped: `isa drop {t} {about} \"<why>\"`, then this answer")
    if answer.startswith("fix:"):
        before = dict(x.split("=", 1) for x in str(p["fm"].get("flag_parts") or "").split() if "=" in x)
        if before.get(about) == isafile.subtree_hash(p, about):
            raise Refused(f"`fix:` once {about} is changed: `isa write {t} …` first (a new review follows)")
    body = (p["sections"].get("Review") or "").split("\n")
    body = [re.sub(r" — answer: .*$", f" — answer: {answer}", ln) if ln.startswith(f"- {flag}: ") else ln
            for ln in body]
    commands._write(path, isafile.refresh(doc.set_section(text, "Review", "\n".join(body), isafile.SECTIONS)))
    out(f"answered {flag}")
    return 0


# ------------------------------------------------------------------ Jev's check

def _sections(stext):
    """[(k, title, accepted-when lines)] of the spec."""
    secs = doc.section_map(doc.split(stext)[2])
    out = []
    for h in spec.s_sections(stext):
        m = spec.S_HEAD.match(h)
        content = secs.get(h) or ""
        acc = content.split("Accepted when:", 1)[1] if "Accepted when:" in content else ""
        out.append((m.group(1), m.group(2), [ln[2:].strip() for ln in acc.split("\n") if ln.startswith("- ")]))
    return out


def _origin(p, i):
    e = isafile.entry(p, i) or {}
    if e.get("serves"):
        return f"common ground, serves {e['serves']}"
    o = str(e.get("anchors_to") or "")
    return ("context" if e.get("source") == "context" else o) or "none"


def _units(p, stext):
    """One unit per section (its leaves and its `covered` question), then one for ISC-0 and the rest."""
    secs = _sections(stext)
    ids = {k for k, _, _ in secs}
    units = []
    for k, title, acc in secs:
        crit = [i for i in p["order"] if (i == k or i.startswith(k + ".")) and not p["iscs"][i]["dropped"]]
        units.append({"sections": [{"id": f"S{k}", "title": title, "accepted_when": acc}], "criteria": crit,
                      "covered": [(k, title)]})
    rest = [i for i in p["order"] if i.split(".")[0] not in ids and not p["iscs"][i]["dropped"]]
    if rest:
        units.append({"sections": [], "criteria": rest, "covered": []})
    return units


def _questions(p, unit, titles):
    qs = {}
    for i in unit["criteria"]:
        if i not in isafile.leaves(p):
            continue
        top = i.split(".")[0]
        part = f", and deliver what section S{top} (\"{titles[top]}\") asks for" if top in titles else ""
        qs["serves_" + i.replace(".", "_")] = {"type": "noul", "instructions": (
            f"Does criterion ISC-{i} (\"{p['iscs'][i]['text']}\", see `criteria`) help solve the spec's stated "
            f"Problem and reach its Goal{part}? Answer yes when the Problem needs what it claims; no when it is "
            "unrelated to the Problem and the Goal, or only restates a detail no part of the spec asks for.")}
    for k, title in unit["covered"]:
        qs[f"covered_S{k}"] = {"type": "noul", "instructions": (
            f"Do the criteria under ISC-{k} in `criteria` together cover everything section S{k} (\"{title}\") asks for "
            "in its Accepted-when lines? Answer no when an Accepted-when outcome has no criterion that would prove it.")}
    return qs


def _state(p, stext, units):
    secs = doc.section_map(doc.split(stext)[2])
    crit = []
    for u in units:
        for i in u["criteria"]:
            e = isafile.entry(p, i) or {}
            crit.append({"id": f"ISC-{i}", "text": p["iscs"][i]["text"], "parent": f"ISC-{i.rsplit('.', 1)[0]}"
                         if "." in i else None, "origin": _origin(p, i), "why": e.get("why"), "probe": e.get("tool")})
    return {"problem": secs.get("Problem", ""), "goal": secs.get("Goal", "").split("\nSaid:")[0],
            "sections": [s for u in units for s in u["sections"]], "criteria": crit}


def _tokens(x):
    return len(json.dumps(x)) / 4


def _fits(state, qs):
    st = _tokens(state)
    longest = max([_tokens(q) for q in qs.values()] or [0])
    return st + longest <= LONGEST_BUDGET and st + _tokens(qs) <= REQUEST_BUDGET


def requests(p, stext):
    """[(state, questions)]: everything in one request when it fits, else consecutive units packed greedily."""
    units, titles = _units(p, stext), {k: t for k, t, _ in _sections(stext)}
    groups, cur = [], []
    for u in units:
        trial = cur + [u]
        qs = {k: v for g in trial for k, v in _questions(p, g, titles).items()}
        if cur and not _fits(_state(p, stext, trial), qs):
            groups.append(cur)
            cur = [u]
        else:
            cur = trial
    if cur:
        groups.append(cur)
    return [(_state(p, stext, g), {k: v for u in g for k, v in _questions(p, u, titles).items()}) for g in groups]


def _jev_check(p, stext):
    """→ (flags, the Jev line of `## Review`)."""
    reqs = [r for r in requests(p, stext) if r[1]]
    if not reqs or not jev.enabled():
        return [], isafile.UNAVAILABLE
    with ThreadPoolExecutor(max_workers=min(8, len(reqs))) as pool:
        results = list(pool.map(lambda r: jev.ask_adhoc(r[0], r[1], DEADLINE), reqs))
    if not all(r["served"] for r in results):
        return [], isafile.UNAVAILABLE
    serves, covered = config.number("jev_serves"), config.number("jev_covered")
    flags = []
    for (_, qs), res in zip(reqs, results):
        for qid, q in qs.items():
            kind, about = qid.split("_", 1)
            no = 1 - float(res["answers"][qid])
            threshold = serves if kind == "serves" else covered
            if no >= threshold:
                flags.append({"kind": kind, "about": "ISC-" + about.replace("_", ".") if kind == "serves" else about,
                              "no": no, "threshold": threshold, "question": q["instructions"]})
    n = sum(len(qs) for _, qs in reqs)
    return flags, f"Jev: {len(reqs)} request{'s' if len(reqs) > 1 else ''}, {n} questions"


# ------------------------------------------------------------------ the trace

def trace(path, text):
    p = isafile.parse(text)
    if isafile.tier(p) == "E1":
        raise Refused("`--trace` shows an ISA against its spec (E2–E4); an E1 ISA reads whole: `isa show <ISA>`")
    stext = commands._read(os.path.join(str(p["fm"].get("root")), str(p["fm"].get("spec") or "")))
    secs = _sections(stext)
    ids = {k for k, _, _ in secs}
    live = [i for i in p["order"] if not p["iscs"][i]["dropped"]]
    leaves = isafile.leaves(p)

    def item(i):
        e = isafile.entry(p, i) or {}
        tags = [f"serves {e['serves']}"] if e.get("serves") else []
        tags += [f"context: {e.get('why')}"] if e.get("source") == "context" else []
        tags += [f"why: {e.get('why')}"] if e.get("serves") and e.get("why") else []
        tags += [f"anchors {e.get('anchors_to')}"] if i.split(".")[0] not in ids | {"0"} and e.get("anchors_to") else []
        indent = "  " * (i.count(".") - (1 if i.split(".")[0] in ids | {"0"} else 0))
        rows = [f"{indent}- ISC-{i}: {p['iscs'][i]['text']}" + "".join(f" · {t}" for t in tags)]
        if i in leaves:
            rows.append(f"{indent}    probe: `{e.get('tool') or '(none yet)'}`")
        return rows

    out = [f"# Trace — {p['fm'].get('task', '')}", "", "## Common ground (ISC-0, built first)"]
    common = [i for i in live if i.startswith("0.")]
    out += [r for i in common for r in item(i)] or ["(none)"]
    for k, title, acc in secs:
        out += ["", f"## S{k} — {title}", "Accepted when:"] + [f"  - {a}" for a in acc]
        out += [r for i in live if i.startswith(k + ".") for r in item(i)] or ["(no criterion yet)"]
    out += ["", "## Antis and context (outside the spec's sections)"]
    out += [r for i in live if i.split(".")[0] not in ids | {"0"} for r in item(i)] or ["(none)"]
    r = p["review"]
    current = bool(r and r["hash"] == isafile.review_hash(text))
    out += ["", "## Review"] + ((p["sections"].get("Review") or "").split("\n") if current else
                                ["(missing: `isa review <ISA>`, the checklist on stdin)"])
    covered = sum(1 for k, _, _ in secs if any(i.startswith(k + ".") and i in leaves for i in live))
    context = sum(1 for i in leaves if (isafile.entry(p, i) or {}).get("source") == "context")
    status = ("review ✓ (Jev)" if r["jev"] else "review: model only") if current else "review: missing"
    out += ["", f"{covered}/{len(secs)} sections covered · {sum(1 for i in common if i in leaves)} common · "
                f"{context} context · {status}"]
    return "\n".join(out)
