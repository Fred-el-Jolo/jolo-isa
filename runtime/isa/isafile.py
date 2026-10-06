"""The TASK ISA: its sections, its criteria tree, its probes, its Verification lines.

Criteria are a tree: `- [ ] ISC-3: …` at the top, `  - [ ] ISC-3.1: …` one level down (two spaces per level),
ids following the nesting. A leaf has one probe (its `## Test Strategy` entry) and a box `[ ]` / `[x]`; a parent
has no probe and shows its children as `[done/total]`, then `[x]` once every child is done. A dropped ISC stays as
a tombstone, `[DROPPED — <why>]`, and its id is never used again.

Verification holds only lines the `isa` commands write:
    - ISC-1.2: red 2026-10-07 01:02 exit 1 — `cmd`          the failing run before the build
    - ISC-1.2: verified 2026-10-07 01:05 exit 0 — `cmd`     the passing run (`(no red baseline)` when none failed)
    - ISC-1.2: failed 2026-10-07 01:05 exit 2 — `cmd`       the last run failed
    - ISC-1.2: attested 2026-10-07 01:05 — <evidence>       a manual leaf, ticked on the user-visible evidence
    - Goal: yes — <evidence>
    - Ask 1: met — <evidence>
"""
import re
import time

from . import doc, yamlish

SECTIONS = ["Problem", "Vision", "Out of Scope", "Principles", "Constraints", "Goal", "Criteria", "Test Strategy",
            "Decisions", "Verification"]
CONTENT = SECTIONS[:8]  # what the ack covers, and what `isa write` writes as a block
E1_REQUIRED = ["Problem", "Goal", "Criteria", "Test Strategy"]
E1_FORBIDDEN = ["Vision", "Out of Scope", "Constraints"]
DEPTH = {"E1": 1, "E2": 2, "E3": 3, "E4": None}
KINDS = ("behaviour", "regression", "doc", "config", "file", "manual")
ISC_LINE = re.compile(r"^(?P<ind> *)- \[(?P<box>[ xX]|\d+/\d+)\] ISC-(?P<id>\d+(?:\.\d+)*): ?(?P<text>.*)$")
VER_LINE = re.compile(r"^- ISC-(?P<id>\d+(?:\.\d+)*): (?P<what>red|verified|failed|attested) (?P<rest>.*)$")
RUN = re.compile(r"^(?P<when>\S+ \S+) exit (?P<code>-?\d+) — `(?P<cmd>.*)`(?P<note>.*)$")
DROPPED = "[DROPPED"


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ------------------------------------------------------------------ parse

def parse(text):
    fm, _, body = doc.split(text)
    secs = doc.section_map(body)
    iscs, order, errors = {}, [], []
    for n, ln in enumerate((secs.get("Criteria") or "").split("\n"), 1):
        if not ln.strip():
            continue
        m = ISC_LINE.match(ln)
        if not m:
            errors.append(f"Criteria line {n} is not `- [ ] ISC-N: <claim>`: {ln.strip()[:60]}")
            continue
        i = m.group("id")
        if i in iscs:
            errors.append(f"ISC-{i} is used twice")
            continue
        level = i.count(".") + 1
        iscs[i] = {"id": i, "level": level, "indent": len(m.group("ind")), "box": m.group("box").lower(),
                   "text": m.group("text").strip(), "dropped": m.group("text").strip().startswith(DROPPED)}
        order.append(i)
    for i in order:
        iscs[i]["children"] = [j for j in order if j.rsplit(".", 1)[0] == i and "." in j]
    tests, tests_error = _tests(secs.get("Test Strategy") or "")
    return {"fm": fm, "body": body, "sections": secs, "iscs": iscs, "order": order, "errors": errors,
            "tests": tests, "tests_error": tests_error, "ver": _ver(secs.get("Verification") or "")}


def _tests(content):
    m = re.search(r"```ya?ml\n(.*?)```", content, re.S)
    raw = m.group(1) if m else content
    if not raw.strip():
        return [], None
    try:
        data = yamlish.load(raw)
    except yamlish.YamlError as e:
        return [], f"Test Strategy: the YAML does not parse ({e})"
    if not isinstance(data, list) or not all(isinstance(e, dict) for e in data):
        return [], "Test Strategy: not a YAML list of entries (`- isc: ISC-N`)"
    return data, None


def _ver(content):
    out = {"iscs": {}, "goal": None, "asks": {}}
    for ln in content.split("\n"):
        m = VER_LINE.match(ln)
        if m:
            slot = "red" if m.group("what") == "red" else "result"
            out["iscs"].setdefault(m.group("id"), {})[slot] = ln
        elif ln.startswith("- Goal: "):
            out["goal"] = ln
        else:
            a = re.match(r"^- Ask (\d+): ", ln)
            if a:
                out["asks"][int(a.group(1))] = ln
    return out


def leaves(p):
    """Non-dropped ISCs without children."""
    return [i for i in p["order"] if not p["iscs"][i]["children"] and not p["iscs"][i]["dropped"]]


def entry(p, isc):
    return next((e for e in p["tests"] if str(e.get("isc", "")).replace("ISC-", "") == isc), None)


def is_anti(p, isc):
    return p["iscs"][isc]["text"].startswith("Anti:")


def tier(p):
    return str(p["fm"].get("effort") or "").upper()


# ------------------------------------------------------------------ render

def render_criteria(p):
    """The Criteria lines with every parent's box recomputed from its children."""
    done = {}

    def complete(i):
        if i in done:
            return done[i]
        isc = p["iscs"][i]
        kids = [k for k in isc["children"] if not p["iscs"][k]["dropped"]]
        done[i] = all(complete(k) for k in kids) if kids else isc["box"] == "x"
        return done[i]

    lines = []
    for i in p["order"]:
        isc = p["iscs"][i]
        kids = [k for k in isc["children"] if not p["iscs"][k]["dropped"]]
        if isc["dropped"]:
            box = " "
        elif kids:
            n = sum(complete(k) for k in kids)
            box = "x" if n == len(kids) else f"{n}/{len(kids)}"
        else:
            box = isc["box"] if isc["box"] in ("x", " ") else " "
        lines.append("  " * (isc["level"] - 1) + f"- [{box}] ISC-{i}: {isc['text']}")
    return "\n".join(lines)


def progress(p):
    ls = leaves(p)
    return f"{sum(p['iscs'][i]['box'] == 'x' for i in ls)}/{len(ls)}"


def render_tests(entries):
    keys = ("isc", "anchors_to", "kind", "tool", "fails-when")
    out = []
    for e in entries:
        ordered = [k for k in keys if k in e] + [k for k in e if k not in keys]
        for n, k in enumerate(ordered):
            v = e[k]
            if k == "isc":
                v = "ISC-" + str(v).replace("ISC-", "")
            out.append(("- " if n == 0 else "  ") + f"{k}: {doc.fm_value(v)}")
    return "```yaml\n" + "\n".join(out) + "\n```" if out else ""


def render_ver(p):
    v = p["ver"]
    lines = []
    for i in p["order"]:
        slot = v["iscs"].get(i) or {}
        lines += [slot[k] for k in ("red", "result") if slot.get(k)]
    lines += [v["goal"]] if v["goal"] else []
    lines += [v["asks"][n] for n in sorted(v["asks"])]
    return "\n".join(lines)


def refresh(text):
    """Recompute parent boxes, `progress` and `updated`; the Verification section in its fixed order."""
    p = parse(text)
    if p["order"]:
        text = doc.set_section(text, "Criteria", render_criteria(p), SECTIONS)
    p = parse(text)
    text = doc.fm_set(text, "progress", progress(p))
    text = doc.fm_set(text, "updated", stamp())
    ver = render_ver(p)
    if ver:
        text = doc.set_section(text, "Verification", ver, SECTIONS)
    return text


def set_box(text, isc, ticked):
    p = parse(text)
    p["iscs"][isc]["box"] = "x" if ticked else " "
    return refresh(doc.set_section(text, "Criteria", render_criteria(p), SECTIONS))


def set_ver(text, isc=None, slot=None, line=None, goal=None, ask=None):
    p = parse(text)
    if isc:
        p["ver"]["iscs"].setdefault(isc, {})[slot] = line
    if goal:
        p["ver"]["goal"] = goal
    if ask:
        p["ver"]["asks"][ask[0]] = ask[1]
    return doc.set_section(text, "Verification", render_ver(p), SECTIONS)


# ------------------------------------------------------------------ acks and diffs

def _neutral(content):
    return re.sub(r"^(\s*)- \[(?:[ xX]|\d+/\d+)\] ", r"\1- [ ] ", content, flags=re.M)


def ack_hash(text):
    """What the user acks: the content sections, ticks ignored, and the tier."""
    fm, _, body = doc.split(text)
    parts = [f"effort: {fm.get('effort')}"]
    for s in CONTENT:
        raw = doc.raw_section(body, s)
        if raw is not None:
            parts.append(f"## {s}\n{_neutral(raw).strip()}")
    return doc.h8("\n".join(parts))


def parts(text):
    """{label: hash} of each content section, Criteria and Test Strategy split per ISC: what `isa diff` compares."""
    p = parse(text)
    out = {}
    for s in CONTENT[:6]:
        raw = doc.raw_section(p["body"], s)
        if raw is not None:
            out[s] = doc.h8(raw)
    for i in p["order"]:
        e = entry(p, i)
        out[f"ISC-{i}"] = doc.h8(p["iscs"][i]["text"] + "\n" + (repr(sorted(e.items())) if e else ""))
    return out


def acked(text):
    """True when the ISA's `acked:` line holds its content's hash now."""
    m = re.match(r"^\S+ #([0-9a-f]{8})$", str(doc.split(text)[0].get("acked") or ""))
    return bool(m) and m.group(1) == ack_hash(text)
