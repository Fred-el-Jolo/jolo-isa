"""Specs and plans (spec 2026-10-06 § B.3–B.6): parse, lint and the ack hash.

A spec is `<doc root>/docs/spec/YYYY-MM-DD-<slug>.md`, a plan the same name under `docs/plan/`. Their shape
is the template of spec § B.3; the lint checks only what a script can decide (shape, coverage, size), the
user checks the rest at the ack.

Standard library only (frontmatter via `yamlish`). Entry points: `parse(text)`, `ack_hash(text)`,
`lint(path, moment)`; the ack records (§ B.4): `record_ack`, `ack_recorded`, `acked`.
"""
import hashlib
import json
import os
import re
import subprocess
import time

from . import state, yamlish

SECTION_RE = re.compile(r"^## (S\d+)\b(?:\s*[—–-]\s*(.*?))?\s*$")
BULLET_RE = re.compile(r"^- \[( |x|X)\] (A\d+):\s?(.*)$")
STEP_RE = re.compile(r"^- \[( |x|X)\] (P\d+) — (.*)$")
FOCUS_RE = re.compile(r"^- (.*?)\s*→\s*(P\d+)\s*$")
COVERS_RE = re.compile(r"(S\d+)(?::(A\d+(?:\s*,\s*A\d+)*))?")
STATUS_ACKED = re.compile(r"^status:\s*acked (\d{4}-\d{2}-\d{2}) #([0-9a-f]{8})(?:\s+#\s.*)?\s*$")
STATUS_RE = re.compile(r"^(draft|acked \d{4}-\d{2}-\d{2} #[0-9a-f]{8}|done \d{4}-\d{2}-\d{2})$")
EFFORT_RE = re.compile(r"^E[1-5]$")
# the marks `isa close` writes (§ B.6), which the ack hash leaves out
ISA_SUFFIX = re.compile(r"  \(\d{4}-\d{2}-\d{2}, ISA [^)]*\)\s*$")
STEP_DONE = re.compile(r" · Done: \d{4}-\d{2}-\d{2}\s*$")
# placeholders: TBD, TODO, a lone `…`, and the template's own `<…>` slots (several words, an ellipsis, or
# one of its single-word slots) — read outside inline code and fenced blocks
PLACEHOLDER = re.compile(r"\b(?:TBD|TODO)\b|(?<!\S)…(?!\S)|"
                         r"<(?:[^\s<>][^<>\n]*?[\s…][^<>\n]*|…|Title|slug|hash8|path|name)>")
INLINE_CODE = re.compile(r"(`+).+?\1")


def _norm(text):
    return text.replace("\r\n", "\n")


def _visible(text):
    """Text with HTML comments blanked (line numbers kept)."""
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def _split(text):
    """(frontmatter dict, frontmatter lines, body as [(line_no, line)] outside fences, error or None)."""
    lines = text.split("\n")
    fm, fm_lines, start, err = {}, [], 0, None
    if lines and lines[0] == "---" and "---" in lines[1:]:
        end = lines.index("---", 1)
        fm_lines, start = lines[1:end], end + 1
        try:
            fm = yamlish.load("\n".join(fm_lines)) or {}
            if not isinstance(fm, dict):
                fm, err = {}, "frontmatter: not a YAML mapping"
        except yamlish.YamlError as e:
            err = f"frontmatter: not valid YAML ({e})"
    else:
        err = "no YAML frontmatter (`---` block on the first line)"
    body, fence = [], False
    for i in range(start, len(lines)):
        if lines[i].startswith("```"):
            fence = not fence
            continue
        if not fence:
            body.append((i + 1, lines[i]))
    return fm, fm_lines, body, err


def _headings(body):
    """[(name, line_no, [(line_no, line)…])] for each `## ` heading; a `# ` heading ends a section."""
    out, cur = [], None
    for n, line in body:
        if line.startswith("## "):
            cur = (line[3:].strip(), n, [])
            out.append(cur)
        elif line.startswith("# "):
            cur = None
        elif cur is not None:
            cur[2].append((n, line))
    return out


def _covers(s):
    out = []
    for m in COVERS_RE.finditer(s):
        if m.group(2):
            out += [(m.group(1), a) for a in re.findall(r"A\d+", m.group(2))]
        else:
            out.append((m.group(1), None))
    return out


def _paths(s):
    return re.findall(r"`([^`]+)`", s) or ([s.strip()] if s.strip() else [])


def _steps(body):
    steps, dupes, cur, field = {}, [], None, None
    for n, line in body:
        m = STEP_RE.match(line)
        if m:
            pid, parts = m.group(2), [p.strip() for p in STEP_DONE.sub("", m.group(3)).split(" · ")]
            cur, field = {"line": n, "goal": parts[0], "tier": None, "covers": [], "after": [],
                          "files": None, "done_when": None, "ticked": m.group(1) != " "}, None
            for p in parts[1:]:
                if EFFORT_RE.match(p):
                    cur["tier"] = p
                elif p.startswith("covers"):
                    cur["covers"] = _covers(p[len("covers"):])
                elif p.startswith("after"):
                    cur["after"] = re.findall(r"P\d+", p)
            if pid in steps:
                dupes.append(pid)
            else:
                steps[pid] = cur
            continue
        if cur is None or not line.strip():
            continue
        if not line.startswith(" "):
            cur = None
            continue
        s = line.strip()
        if s.startswith("Files:"):
            cur["files"], field = _paths(s[len("Files:"):]), "files"
        elif s.startswith("Done when:"):
            rest = s[len("Done when:"):].strip()
            cur["done_when"], field = ([rest] if rest else []), "done"
        elif s.startswith("- ") and field == "files":
            cur["files"] += _paths(s[2:])
        elif s.startswith("- ") and field == "done":
            cur["done_when"].append(s[2:].strip())
        elif re.match(r"^[A-Z][\w ]*:", s):
            field = None
        elif field == "done" and cur["done_when"]:
            cur["done_when"][-1] += " " + s
    return steps, dupes


def _focus(body):
    out, inside = [], False
    for _, line in body:
        if line.strip() == "Review focus:":
            inside = True
            continue
        if not inside:
            continue
        if not line.strip() or STEP_RE.match(line):
            break
        if line.startswith("- "):
            m = FOCUS_RE.match(line)
            out.append((m.group(1), m.group(2)) if m else (line[2:].strip(), None))
        elif not line.startswith(" "):
            break
    return out


def _is_plan(fm, body):
    return bool(fm.get("spec")) and any(line.startswith("# Plan — ") for _, line in body)


def _parse(text):
    text = _visible(_norm(text))
    fm, fm_lines, body, err = _split(text)
    kind = "plan" if _is_plan(fm, body) else "spec"
    sections, s_dupes, a_dupes = {}, [], []
    for name, n, content in _headings(body):
        m = SECTION_RE.match("## " + name)
        if not m:
            continue
        sid, bullets = m.group(1), {}
        for bn, line in content:
            b = BULLET_RE.match(line)
            if not b:
                continue
            if b.group(2) in bullets:
                a_dupes.append((sid, b.group(2), bn))
                continue
            bullets[b.group(2)] = {"text": ISA_SUFFIX.sub("", b.group(3)).strip(), "ticked": b.group(1) != " ",
                                   "line": bn}
        if sid in sections:
            s_dupes.append(sid)
        else:
            sections[sid] = {"title": m.group(2) or "", "line": n, "bullets": bullets}
    steps, p_dupes = _steps(body) if kind == "plan" else ({}, [])
    return {"kind": kind, "fm": fm, "sections": sections, "steps": steps,
            "review_focus": _focus(body) if kind == "plan" else [],
            "_fm_lines": fm_lines, "_body": body, "_err": err,
            "_dupes": {"S": s_dupes, "A": a_dupes, "P": p_dupes}}


def parse(text):
    """{kind: "spec" | "plan", fm, sections: {S2: {title, line, bullets: {A1: {text, ticked, line}}}},
    steps: {P2: {line, goal, tier, covers: [(S, A | None)], after, files, done_when, ticked}},
    review_focus: [(text, step | None)]}. Lines are 1-based. `covers S2` reads as `("S2", None)`: every
    bullet of S2."""
    d = _parse(text)
    return {k: d[k] for k in ("kind", "fm", "sections", "steps", "review_focus")}


def ack_hash(text):
    """First 8 hex of the sha256 of the text without what `isa close` writes (§ B.4, § B.6): CRLF → LF,
    `status:` and `Done:` lines dropped, `[x]` / `[X]` read as `[ ]`, the `  (YYYY-MM-DD, ISA …)` suffix
    and a step's ` · Done: YYYY-MM-DD` dropped, trailing newlines normalised."""
    out = []
    for line in _norm(text).split("\n"):
        if line.startswith("status:") or line.startswith("Done:"):
            continue
        line = re.sub(r"^(\s*)- \[[xX]\] ", r"\1- [ ] ", line)
        out.append(STEP_DONE.sub("", ISA_SUFFIX.sub("", line)))
    norm = "\n".join(out).rstrip("\n") + "\n"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:8]


# ------------------------------------------------------------------ lint

def _placeholders(d):
    out = []
    for n, line in d["_body"]:
        m = PLACEHOLDER.search(INLINE_CODE.sub("", line))
        if m:
            out.append(f"placeholder `{m.group(0)}` on line {n}")
    for k, v in d["fm"].items():
        m = PLACEHOLDER.search(INLINE_CODE.sub("", v)) if isinstance(v, str) else None
        if m:
            out.append(f"placeholder `{m.group(0)}` in frontmatter `{k}`")
    return out


def _status(d):
    raw = next((ln.split(":", 1)[1] for ln in d["_fm_lines"] if ln.startswith("status:")), None)
    if raw is None:
        return ["frontmatter: `status` missing (draft | acked YYYY-MM-DD #<hash8> | done YYYY-MM-DD)"]
    val = re.sub(r"\s+#\s.*$", "", raw).strip()
    if not STATUS_RE.match(val):
        return [f"frontmatter: `status: {val}` is not draft | acked YYYY-MM-DD #<hash8> | done YYYY-MM-DD"]
    return []


def _text(lines):
    return [(n, ln) for n, ln in lines if ln.strip()]


def _spec_rules(d, moment):
    out, fm = [], d["fm"]
    effort = fm.get("effort")
    tier = None
    if effort is None:
        out.append("frontmatter: `effort` missing (E1–E5)")
    elif not EFFORT_RE.match(str(effort)):
        out.append(f"frontmatter: `effort: {effort}` is not E1–E5")
    else:
        tier = int(str(effort)[1])
    heads = _headings(d["_body"])
    by_name = {}
    for name, n, content in heads:
        by_name.setdefault(name.lower(), (n, content))
        if not _text(content) and "[DROPPED" not in name and not name.lower().startswith("open questions"):
            out.append(f"empty section `## {name}` (line {n})")
    goal = by_name.get("goal")
    if goal is None:
        out.append("no `## Goal` section")
    else:
        labels = {}
        cur = None
        for _, ln in goal[1]:
            s = ln.strip()
            if s in ("Said:", "Assumed:"):
                cur = s[:-1]
                labels[cur] = 0
            elif cur and ln.startswith("- "):
                labels[cur] += 1
            elif s and not ln.startswith(" "):
                cur = None
        for label in ("Said", "Assumed"):
            if label not in labels:
                out.append(f"Goal: no `{label}:` list (spec § B.10 rule 2)")
        if labels.get("Said") == 0:
            out.append("Goal: `Said:` lists nothing — what did the user ask for, in their words?")
        if labels.get("Assumed") == 0:
            out.append("warn: Goal: `Assumed:` lists nothing — the request was complete, or nobody looked hard")
    for sid in d["_dupes"]["S"]:
        out.append(f"{sid}: section id used twice")
    if not d["sections"]:
        out.append("no `S<n>` section (`## S1 — <a deliverable part>` with `Accepted when:` bullets)")
    for name, n, content in heads:
        m = SECTION_RE.match("## " + name)
        if not m or "[DROPPED" in name:
            continue
        sid = m.group(1)
        idx = next((i for i, (_, ln) in enumerate(content) if ln.strip() == "Accepted when:"), None)
        if idx is None:
            out.append(f"{sid}: no `Accepted when:` list (line {n})")
            continue
        found = 0
        for bn, ln in content[idx + 1:]:
            if BULLET_RE.match(ln):
                found += 1
            elif ln.startswith("- "):
                out.append(f"{sid}: line {bn} is not written `- [ ] A<n>: <outcome>`")
        if not found:
            out.append(f"{sid}: no `- [ ] A<n>:` bullet under `Accepted when:`")
    for sid, aid, bn in d["_dupes"]["A"]:
        out.append(f"{sid}: {aid} used twice (line {bn}) — bullet ids are unique in their section")
    oq = next((v for k, v in by_name.items() if k.startswith("open questions")), None)
    if moment == "ack" and oq:
        left = _open_left(oq[1])
        if left:
            out.append(f"Open questions: {len(left)} line(s) left — answer them before the ack")
    if tier and tier >= 3 and not ("approaches" in by_name and _text(by_name["approaches"][1])):
        out.append(f"E{tier}: no `## Approaches` section (2–3 options, the chosen one first, why)")
    if tier and tier >= 4:
        if not fm.get("plan"):
            out.append(f"E{tier}: no `plan:` in the frontmatter")
        dec = by_name.get("decisions")
        if not dec or not any("second-look:" in ln for _, ln in dec[1]):
            out.append(f"E{tier}: no `second-look:` line in `## Decisions`")
    if tier == 5 and not fm.get("interview"):
        out.append("E5: no `interview:` in the frontmatter (the date the Interview ran)")
    return out


def _open_left(content):
    return [ln for _, ln in _text(content) if ln.strip().rstrip(".").lower() != "none"]


def open_questions(text):
    """The lines left under the document's `## Open questions` (a lone `None` doesn't count)."""
    for name, _, content in _headings(_parse(text)["_body"]):
        if name.lower().startswith("open questions"):
            return _open_left(content)
    return []


def _doc_root(path):
    """The plan's git work-tree root, else the folder above `docs/plan/` (P6 brings `state.doc_root`)."""
    d = os.path.dirname(os.path.abspath(path))
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                           timeout=5)
        top = r.stdout.strip()
        if r.returncode == 0 and top and os.path.realpath(top) != os.path.realpath(os.path.expanduser("~")):
            return top
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.dirname(os.path.dirname(d))


def _plan_rules(d, path, text):
    out, steps = [], d["steps"]
    if not steps:
        out.append("no step (`- [ ] P1 — <goal> · E2 · covers S1:A1`)")
    for pid in d["_dupes"]["P"]:
        out.append(f"{pid}: step id used twice")
    for pid, st in steps.items():
        if not st["files"]:
            out.append(f"{pid}: no `Files:` line (line {st['line']})")
        if not st["done_when"]:
            out.append(f"{pid}: no `Done when:` (line {st['line']})")
        for a in st["after"]:
            if a not in steps:
                out.append(f"{pid}: after {a} — no such step")
    for txt, target in d["review_focus"]:
        if target is None:
            out.append(f'Review focus: "{txt}" names no owning step (end it with → P<n>)')
        elif target not in steps:
            out.append(f'Review focus: "{txt}" → {target} — no such step')
    rel = str(d["fm"].get("spec"))
    sp = os.path.expanduser(rel) if os.path.isabs(os.path.expanduser(rel)) else os.path.join(_doc_root(path), rel)
    try:
        with open(sp, encoding="utf-8") as f:
            spec_text = _norm(f.read())
    except (OSError, ValueError):
        out.append(f"spec: {rel} not found (looked for {sp})")
        return out
    spec = _parse(spec_text)
    covered = {c for st in steps.values() for c in st["covers"]}
    for pid, st in steps.items():
        for sid, aid in st["covers"]:
            sec = spec["sections"].get(sid)
            if sec is None:
                out.append(f"{pid}: covers {sid} — no such section in the spec")
            elif aid and aid not in sec["bullets"]:
                out.append(f"{pid}: covers {sid}:{aid} — no such bullet in the spec")
    for sid, sec in spec["sections"].items():
        if "[DROPPED" in sec["title"]:
            continue
        for aid, b in sec["bullets"].items():
            if not b["text"].startswith("[DROPPED") and (sid, aid) not in covered and (sid, None) not in covered:
                out.append(f"{sid}:{aid} is covered by no step")
    plan_bytes, spec_bytes = len(text.encode("utf-8")), len(spec_text.encode("utf-8"))
    if plan_bytes > 3 * spec_bytes:
        out.append(f"warn: the plan is {plan_bytes} bytes, over 3× its spec ({spec_bytes} bytes) — a plan longer "
                   "than the code it describes has written the code")
    code, fence = 0, False
    for line in text.split("\n"):
        if line.startswith("```"):
            fence = not fence
            code += len(line.encode("utf-8")) + 1
        elif fence:
            code += len(line.encode("utf-8")) + 1
    if code * 2 > plan_bytes:
        out.append(f"warn: code blocks are {100 * code // max(plan_bytes, 1)}% of the plan — the plan holds the "
                   "decisions, the step's ISA and the code hold the code")
    return out


def lint(path, moment="draft"):
    """Shape problems of a spec or plan (spec § B.3), as messages; a warning starts with `warn:`.
    `moment`: "draft", or "ack" (adds the rules that must hold before the ack question)."""
    if moment not in ("draft", "ack"):
        raise ValueError(f"moment must be 'draft' or 'ack', not {moment!r}")
    try:
        with open(path, encoding="utf-8") as f:
            text = _norm(f.read())
    except (OSError, ValueError) as e:  # ValueError: not UTF-8
        return [f"cannot read {path}: {e}"]
    d = _parse(text)
    out = [d["_err"]] if d["_err"] else []
    out += _status(d)
    out += _plan_rules(d, path, text) if d["kind"] == "plan" else _spec_rules(d, moment)
    out += _placeholders(d)
    return out


# ------------------------------------------------------------------ acks (§ B.4: a click, recorded)

def acks_path():
    """`~/.isa/_state/acks.jsonl`: one row per Acknowledge click. Written only by the hooks."""
    return os.path.join(state.home(), "_state", "acks.jsonl")


def status_line(text):
    """The frontmatter's raw `status:` line, or None."""
    lines = _norm(text).split("\n")
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return None
    return next((ln for ln in lines[1:lines.index("---", 1)] if ln.startswith("status:")), None)


def acked_hash(text):
    """The `#<hash8>` of a `status: acked YYYY-MM-DD #<hash8>` line, or None."""
    m = STATUS_ACKED.match(status_line(text) or "")
    return m.group(2) if m else None


def record_ack(path, harness, session):
    """Append the user's Acknowledge for the file as it is now; → its ack hash."""
    p = os.path.realpath(path)
    with open(p, encoding="utf-8") as f:
        h = ack_hash(f.read())
    with open(os.path.join(state.state_dir(), "acks.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"path": p, "hash": h, "t": time.time(), "harness": harness, "session": session}) + "\n")
    return h


def ack_recorded(path, h):
    """True when the user acknowledged this file with this hash on this machine."""
    p = os.path.realpath(path)
    try:
        with open(acks_path(), encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("path") == p and row.get("hash") == h:
                    return True
    except OSError:
        pass
    return False


def acked(path):
    """The file's `status: acked … #h` matches its content now (on any machine: no record needed to read)."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, ValueError):
        return False
    h = acked_hash(text)
    return bool(h) and h == ack_hash(text)
