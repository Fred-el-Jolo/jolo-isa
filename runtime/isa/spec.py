"""SPEC and PLAN: `<cwd>/docs/YYYY-MM-DD-<slug>-01-spec.md` and its `-02-plan.md`, and the ack clicks.

A spec is what is wanted, in the user's words, from E2:

    ---
    status: draft | acked YYYY-MM-DD #<hash8>
    effort: E2 | E3 | E4
    ---
    # <title>
    ## Problem / ## Goal (a sentence, then Said: and Assumed: lists) / ## Out of scope / ## Constraints
    ## Approaches                         (from E3)
    ## S1 — <part>  …  Accepted when:  - <observable outcome>   (no checkbox, no id, no done mark)
    ## Decisions / ## Open questions      (empty at the ack)

The plan is written by `isa close` (from E2): the record of the work, copied from the closed ISA.
An ack is the user's click on Acknowledge, recorded in `~/.isa/<project>/acks.jsonl` with the file's hash and the
hash of each of its parts (what `isa diff` compares); `isa ack` then writes it into the file.
"""
import json
import os
import re
import time

from . import doc, isafile, state

FIXED = ["Problem", "Goal", "Out of scope", "Constraints", "Approaches"]
TAIL = ["Decisions", "Open questions"]
S_HEAD = re.compile(r"^S(\d+)\s+[—–-]\s+(.+)$")
STATUS = re.compile(r"^(draft|acked (\d{4}-\d{2}-\d{2}) #([0-9a-f]{8}))$")
PLACEHOLDER = re.compile(r"\b(?:TBD|TODO)\b")
PLAN_SECTIONS = isafile.CONTENT + ["Decisions", "Review", "Verification"]


def _key(h):
    m = S_HEAD.match(h)
    if m:
        return (1, int(m.group(1)))
    if h in FIXED:
        return (0, FIXED.index(h))
    return (2, TAIL.index(h) if h in TAIL else 9)


def template(title, effort):
    heads = FIXED[:4] + (["Approaches"] if effort in ("E3", "E4") else []) + TAIL
    return (f"---\nstatus: draft\neffort: {effort}\n---\n\n# {title}\n\n" + "".join(f"## {h}\n\n" for h in heads)
            ).rstrip("\n") + "\n"


def set_section(text, name, content):
    if name.lower() == "title":
        fm, _, body = doc.split(text)
        if doc.title(body):
            return re.sub(r"(?m)^# .*$", "# " + content.strip(), doc.norm(text), count=1)
        m = doc.FM.match(doc.norm(text))
        return doc.norm(text)[:m.end()] + f"\n# {content.strip()}\n" + doc.norm(text)[m.end():]
    return doc.set_section(text, canonical(name), content, _key)


def canonical(name):
    for h in FIXED + TAIL:
        if name.strip().lower() == h.lower():
            return h
    m = S_HEAD.match(name.strip())
    if m:
        return f"S{m.group(1)} — {m.group(2).strip()}"
    return name.strip()


def status(text):
    return str(doc.split(text)[0].get("status") or "")


def ack_hash(text):
    """The hash of the spec without its `status:` line."""
    t = re.sub(r"(?m)^status:.*\n", "", doc.norm(text), count=1)
    return doc.h8(t)


def is_acked(text):
    m = STATUS.match(status(text))
    return bool(m and m.group(3)) and m.group(3) == ack_hash(text)


def parts(text):
    """{label: hash} of the title and of each section."""
    _, _, body = doc.split(text)
    out = {"Title": doc.h8(doc.title(body))}
    for h, _, _ in doc.sections(body):
        out[h] = doc.h8(doc.raw_section(body, h) or "")
    return out


def s_sections(text):
    return [h for h, _, _ in doc.sections(doc.split(text)[2]) if S_HEAD.match(h)]


def lint(text):
    fm, _, body = doc.split(text)
    secs = doc.section_map(body)
    errs = []
    if not STATUS.match(str(fm.get("status") or "")):
        errs.append("frontmatter: `status` is `draft` or `acked YYYY-MM-DD #<hash8>`")
    if str(fm.get("effort") or "") not in ("E2", "E3", "E4"):
        errs.append("frontmatter: `effort` is E2, E3 or E4 (E1 has no spec)")
    if not doc.title(body):
        errs.append("no title (`isa write <spec> Title`)")
    for h in FIXED[:4] + (["Approaches"] if fm.get("effort") in ("E3", "E4") else []):
        if not secs.get(h):
            errs.append(f"`## {h}` is empty (`isa write <spec> \"{h}\"`)")
    goal = secs.get("Goal") or ""
    said = re.search(r"(?ms)^Said:\n((?:- .*\n?)+)", goal + "\n")
    if not said:
        errs.append("Goal: no `Said:` list (the user's words)")
    if not re.search(r"(?m)^Assumed:$", goal):
        errs.append("Goal: no `Assumed:` list (what was filled in)")
    s = s_sections(text)
    if not s:
        errs.append("no `## S1 — <part>` section")
    for h in s:
        content = secs.get(h) or ""
        m = re.search(r"(?ms)^Accepted when:\n(.*)", content)
        lines = [ln for ln in (m.group(1).split("\n") if m else []) if ln.strip()]
        if not lines:
            errs.append(f"{h}: no `Accepted when:` lines")
        for ln in lines:
            if re.match(r"^- \[[ xX]\]", ln) or re.match(r"^- A\d+:", ln) or re.search(r"\(\d{4}-\d{2}-\d{2}, ISA ", ln):
                errs.append(f"{h}: an Accepted when line has a checkbox, an id or a done mark: {ln.strip()[:60]}")
        if re.search(r"(?m)^Done:", content):
            errs.append(f"{h}: a `Done:` line (a spec has no done marks)")
    if (secs.get("Open questions") or "").strip():
        errs.append("Open questions: answer them and empty the section before the ack")
    for h, content in secs.items():
        for ln in re.sub(r"`[^`]*`", "", content).split("\n"):
            m = PLACEHOLDER.search(ln)
            if m:
                errs.append(f"`## {h}`: placeholder `{m.group(0)}`")
                break
    return errs


# ------------------------------------------------------------------ acks

def doc_root(path, text=None):
    """The project folder a spec, a plan or an ISA belongs to: the spec's `<cwd>` (above `docs/`), the ISA's root."""
    if state.is_doc_path(path):
        return os.path.dirname(os.path.dirname(os.path.abspath(path)))
    if text is None:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    return str(doc.split(text)[0].get("root") or os.path.dirname(path))


def kind_of(path):
    return "spec" if state.is_doc_path(path) and path.endswith("-01-spec.md") else "isa"


def hash_of(path, text):
    return ack_hash(text) if kind_of(path) == "spec" else isafile.ack_hash(text)


def parts_of(path, text):
    return parts(text) if kind_of(path) == "spec" else isafile.parts(text)


def record_click(path, harness, session):
    """The user clicked Acknowledge for this file as it is now: one row, with the hash of each part."""
    p = os.path.realpath(path)
    with open(p, encoding="utf-8") as f:
        text = f.read()
    acks = state.acks_path(doc_root(p, text))
    os.makedirs(os.path.dirname(acks), exist_ok=True)
    row = {"file": p, "kind": kind_of(p), "hash": hash_of(p, text), "parts": parts_of(p, text), "t": time.time(),
           "harness": harness, "session": session}
    with state.lock(acks):
        with open(acks, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    return row["hash"]


def clicks(path, text=None):
    p = os.path.realpath(path)
    acks = state.acks_path(doc_root(p, text))
    out = []
    try:
        with open(acks, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("file") == p:
                    out.append(row)
    except OSError:
        pass
    return out


def clicked(path, h, text=None):
    return any(r.get("hash") == h for r in clicks(path, text))


def diff(path, text, title):
    """`<title> — changed since its ack:` and one line per part added (+), removed (-) or changed (~)."""
    rows = clicks(path, text)
    if not rows:
        return [f"{title} — never acked: the user reads it whole"]
    old, new = rows[-1].get("parts") or {}, parts_of(path, text)
    lines = [f"{title} — changed since its ack:"]
    for k in new:
        if k not in old:
            lines.append(f"  + {k}")
        elif old[k] != new[k]:
            lines.append(f"  ~ {k}")
    lines += [f"  - {k}" for k in old if k not in new]
    return lines if len(lines) > 1 else [f"{title} — unchanged since its ack"]


# ------------------------------------------------------------------ plan

def plan_path(spec_path):
    return spec_path.replace("-01-spec.md", "-02-plan.md")


def render_plan(isa_text, title, spec_name, slug):
    """The PLAN: the closed ISA's content, Decisions, and Verification without its run lines."""
    p = isafile.parse(isa_text)
    out = [f"---\nspec: {spec_name}\nisa: {slug}\nclosed: {time.strftime('%Y-%m-%d')}\n---\n\n# Plan — {title}\n"]
    for s in PLAN_SECTIONS:
        if s == "Verification":
            v = p["ver"]
            content = "\n".join(([v["goal"]] if v["goal"] else []) + [v["asks"][n] for n in sorted(v["asks"])])
        else:
            content = doc.raw_section(p["body"], s)
        if content is not None and content.strip():
            out.append(f"## {s}\n\n{content.strip()}\n")
    return "\n".join(out)
