"""Specs and plans (spec 2026-10-06 § B.3–B.6): parse, lint and the ack hash.

A spec is `<doc root>/docs/spec/YYYY-MM-DD-<slug>.md`, a plan the same name under `docs/plan/`. Their shape
is the template of spec § B.3; the lint checks only what a script can decide (shape, coverage, size), the
user checks the rest at the ack.

Standard library only (frontmatter via `yamlish`). Entry points: `parse(text)`, `ack_hash(text)`,
`lint(path, moment)`; the ack records (§ B.4): `record_ack`, `ack_recorded`, `acked`, `ack_holds`; the ISA links
(§ B.5, plan P10): `resolve(link)`, `seed(link)`, `link_files(link)`; the done marks (§ B.6, plan P11):
`mark_done(path, bullets, slug, date)`.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import time

from . import state, yamlish

SECTION_RE = re.compile(r"^## (S\d+)\b(?:\s*[—–-]\s*(.*?))?\s*$")
BULLET_RE = re.compile(r"^- \[( |x|X)\] (A\d+):\s?(.*)$")
STEP_RE = re.compile(r"^- \[( |x|X)\] (P\d+) — (.*)$")
FOCUS_RE = re.compile(r"^- (.*?)\s*→\s*(P\d+)\s*$")
COVERS_RE = re.compile(r"(S\d+)(?::(A\d+(?:\s*,\s*A\d+)*))?")
STATUS_ACKED = re.compile(r"^status:\s*acked (\d{4}-\d{2}-\d{2}) #([0-9a-f]{8})(?:\s+#\s.*)?\s*$")
# `isa close` keeps the ack hash on the done line, so a done document still reads as unchanged or edited
STATUS_DONE = re.compile(r"^status:\s*done (\d{4}-\d{2}-\d{2}) #([0-9a-f]{8})(?:\s+#\s.*)?\s*$")
STATUS_RE = re.compile(r"^(draft|acked \d{4}-\d{2}-\d{2} #[0-9a-f]{8}|done \d{4}-\d{2}-\d{2}(?: #[0-9a-f]{8})?)$")
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
        return ["frontmatter: `status` missing (draft | acked YYYY-MM-DD #<hash8> | done YYYY-MM-DD [#<hash8>])"]
    val = re.sub(r"\s+#\s.*$", "", raw).strip()
    if not STATUS_RE.match(val):
        return [f"frontmatter: `status: {val}` is not draft | acked YYYY-MM-DD #<hash8> | done YYYY-MM-DD [#<hash8>]"]
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
    sp = _spec_of(path, d["fm"])
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


def _spec_of(plan_path, fm):
    """The spec a plan names in its frontmatter (`spec:`, relative to the plan's doc root)."""
    rel = os.path.expanduser(str(fm.get("spec") or ""))
    return rel if os.path.isabs(rel) else os.path.join(_doc_root(plan_path), rel)


# ------------------------------------------------------------------ ISA links (§ B.5, § 5.4, § 5.5; plan P10)

def _link_parts(link, root=None):
    """`<path>#<fragment>` → (real path, fragment); a relative path is read from `root` (default: the cwd)."""
    path, _, frag = str(link).partition("#")
    path = os.path.expanduser(path.strip())
    if not os.path.isabs(path):
        path = os.path.join(root or os.getcwd(), path)
    return os.path.realpath(path), frag.strip()


def _read_doc(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, ValueError):
        raise ValueError(f"{what} {path} not found") from None


def _bullets(spec, covers, where):
    out = []
    for sid, aid in covers:
        sec = spec["sections"].get(sid)
        if sec is None:
            raise ValueError(f"{where}: no section {sid}")
        if aid and aid not in sec["bullets"]:
            raise ValueError(f"{where}: no bullet {sid}:{aid}")
        if not aid and "[DROPPED" in sec["title"]:
            continue
        for a in [aid] if aid else list(sec["bullets"]):
            if not sec["bullets"][a]["text"].startswith("[DROPPED") and (sid, a) not in out:
                out.append((sid, a))
    return out


def _link(link, root=None):
    """→ {path, doc, step, bullets, spec_path, spec} for a spec link (`#S1`, `#S1,S2`, `#S2:A1,A2`, none: every
    section) or a plan link (`#P<n>`: the bullets the step covers, in the plan's spec)."""
    path, frag = _link_parts(link, root)
    d = _parse(_read_doc(path, "link:"))
    if d["kind"] == "plan":
        if not re.fullmatch(r"P\d+", frag):
            raise ValueError(f"{link}: a plan link names one step, `#P<n>`")
        step = d["steps"].get(frag)
        if step is None:
            raise ValueError(f"{link}: no step {frag} in the plan")
        sp = os.path.realpath(_spec_of(path, d["fm"]))
        spec = _parse(_read_doc(sp, f"{link}: the plan's spec"))
        return {"path": path, "doc": d, "step": frag, "bullets": _bullets(spec, step["covers"], f"{link} → {sp}"),
                "spec_path": sp, "spec": spec}
    covers = _covers(frag) if frag else [(sid, None) for sid in d["sections"]]
    if frag and not covers:
        raise ValueError(f"{link}: `#{frag}` names no section (`#S1`, `#S1,S2`, `#S2:A1,A2`)")
    return {"path": path, "doc": d, "step": None, "bullets": _bullets(d, covers, link), "spec_path": path, "spec": d}


def resolve(link, root=None):
    """The `(S, A)` bullets a link names, dropped ones left out; ValueError for a missing file, section, bullet
    or step."""
    return _link(link, root)["bullets"]


def link_files(link, root=None):
    """The files a link reads: the spec, or the plan and its spec."""
    k = _link(link, root)
    return [k["path"]] + ([k["spec_path"]] if k["step"] else [])


def _section_lines(d, name):
    for heading, _, content in _headings(d["_body"]):
        if heading.lower() == name:
            return [ln for _, ln in _text(content)]
    return []


def _goal_line(d):
    for ln in _section_lines(d, "goal"):
        if ln.strip() not in ("Said:", "Assumed:") and not ln.startswith("- ") and not ln.startswith(" "):
            return ln.strip()
    return None


def seed(link, root=None):
    """What `isa new --spec / --plan` scaffolds from (§ 5.4 step 5, § 5.5 step 5): `goal` (the spec's Goal line,
    or the step line), `criteria` [(anchor, text)] (each linked bullet as `S2:A1`; for a step also its "Done
    when" lines, anchored `P<n>`), `tier` (`effort:`, or the step's), the spec's `constraints`, and the
    `review_focus` lines the step owns. Also `path`, `spec_path`, `step` and `open_after` (a step's `after`
    steps not ticked yet)."""
    k = _link(link, root)
    spec = k["spec"]
    criteria = [(f"{s}:{a}", spec["sections"][s]["bullets"][a]["text"]) for s, a in k["bullets"]]
    if k["step"]:
        st = k["doc"]["steps"][k["step"]]
        goal, tier = st["goal"], st["tier"]
        criteria += [(k["step"], t) for t in st["done_when"] or []]
        focus = [t for t, owner in k["doc"]["review_focus"] if owner == k["step"]]
        open_after = [a for a in st["after"] if not k["doc"]["steps"].get(a, {}).get("ticked")]
    else:
        goal, focus, open_after = _goal_line(spec), [], []
        tier = str(spec["fm"].get("effort") or "").strip().upper() or None
    constraints = [ln[2:].strip() if ln.startswith("- ") else ln.strip() for ln in _section_lines(spec, "constraints")]
    return {"goal": goal, "criteria": criteria, "tier": tier, "constraints": constraints, "review_focus": focus,
            "path": k["path"], "spec_path": k["spec_path"], "step": k["step"], "open_after": open_after}


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


def ack_holds(text):
    """The text reads as unchanged since its ack: an `acked` status line, or the `done` line `isa close` wrote in
    its place (which keeps the hash), whose hash matches the text now."""
    line = status_line(text) or ""
    m = STATUS_ACKED.match(line) or STATUS_DONE.match(line)
    return bool(m) and m.group(2) == ack_hash(text)


# ------------------------------------------------------------------ done marks (§ B.6: written by `isa close`)

SUFFIX_SLUG = re.compile(r"  \(\d{4}-\d{2}-\d{2}, ISA ([^)]*)\)\s*$")


@contextlib.contextmanager
def doc_lock(path):
    """Exclusive `flock` on `<path>.lock`, which the holder removes before letting go — no lock file stays in the
    project. A waiter that wakes on a lock file removed meanwhile opens the new one and waits again."""
    lock = os.path.realpath(path) + ".lock"
    while True:
        fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            if os.stat(lock).st_ino == os.fstat(fd).st_ino:
                break
        except FileNotFoundError:
            pass
        except BaseException:
            os.close(fd)
            raise
        os.close(fd)
    try:
        yield
    finally:
        try:
            os.unlink(lock)
        except OSError:
            pass
        os.close(fd)


def _write_doc(path, text):
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", dir=os.path.dirname(path))
    try:
        os.chmod(tmp, stat.S_IMODE(os.stat(path).st_mode))
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _live(sec):
    """A section's bullets that count: dropped ones (and every bullet of a dropped section) left out."""
    if "[DROPPED" in sec["title"]:
        return []
    return [b for b in sec["bullets"].values() if not b["text"].startswith("[DROPPED")]


def _section_end(d, sec, n_lines):
    return min((n for n, ln in d["_body"] if n > sec["line"] and (ln.startswith("## ") or ln.startswith("# "))),
               default=n_lines + 1)


def _done_lines(lines, sids, date):
    """Write, replace or remove the `Done:` line of each section in `sids`, on the bullets as `lines` hold them."""
    d = _parse("\n".join(lines))
    for sid in sorted(set(sids), key=lambda s: -d["sections"][s]["line"]):
        sec = d["sections"][sid]
        end = _section_end(d, sec, len(lines))
        old = [n for n, ln in d["_body"] if sec["line"] < n < end and ln.startswith("Done:")]
        live = _live(sec)
        new = None
        if live and all(b["ticked"] for b in live):
            slugs = []
            for b in live:
                m = SUFFIX_SLUG.search(lines[b["line"] - 1])
                if m and m.group(1) not in slugs:
                    slugs.append(m.group(1))
            new = f"Done: {date} — {len(live)}/{len(live)} accepted (ISAs {', '.join(slugs)})"
        for n in reversed(old[1:] if new else old):
            del lines[n - 1]
        if new and old:
            lines[old[0] - 1] = new
        elif new:
            lines.insert(sec["line"], new)
    return lines


def _all_done(d):
    if d["kind"] == "plan":
        return bool(d["steps"]) and all(s["ticked"] for s in d["steps"].values())
    live = [b for sec in d["sections"].values() for b in _live(sec)]
    return bool(live) and all(b["ticked"] for b in live)


def mark_done(path, bullets, slug, date):
    """Write the done marks of spec § B.6 into a spec or a plan, under `<path>.lock`, on the file as it is now
    (re-read under the lock, so a close running next to this one loses no tick). For a spec, `bullets` are
    `(S, A)` pairs: each is ticked with `  (<date>, ISA <slug>)` (a bullet ticked already keeps its suffix), and
    each of their sections whose live bullets are now all ticked gets its one `Done: <date> — <n>/<n> accepted
    (ISAs <slugs>)` line, the slugs read back from the bullets. For a plan, `bullets` are step ids, ticked with
    ` · Done: <date>`. Once every live bullet (every step) is ticked — never on an empty set — the status becomes
    `status: done <date> #<hash8>`, keeping the ack hash. Raises ValueError, writing nothing, when the file
    changed since its ack or names no such bullet or step. Writes atomically; → the lines it wrote."""
    path = os.path.realpath(path)
    with doc_lock(path):
        with open(path, encoding="utf-8", newline="") as f:
            raw = f.read()
        text = _norm(raw)
        d = _parse(text)
        if not ack_holds(text):
            raise ValueError(f"{path}: {d['kind']} changed since its ack — ask the user to acknowledge it again")
        old = text.split("\n")
        lines = list(old)
        if d["kind"] == "plan":
            for pid in bullets:
                st = d["steps"].get(pid)
                if st is None:
                    raise ValueError(f"{path}: no step {pid}")
                if not st["ticked"]:
                    line = re.sub(r"^- \[ \] ", "- [x] ", lines[st["line"] - 1].rstrip())
                    lines[st["line"] - 1] = line if STEP_DONE.search(line) else f"{line} · Done: {date}"
        else:
            sids = []
            for sid, aid in bullets:
                b = d["sections"].get(sid, {}).get("bullets", {}).get(aid)
                if b is None:
                    raise ValueError(f"{path}: no bullet {sid}:{aid}")
                if b["text"].startswith("[DROPPED"):
                    continue
                line = lines[b["line"] - 1].rstrip()
                if not b["ticked"]:
                    line = re.sub(r"^- \[ \] ", "- [x] ", ISA_SUFFIX.sub("", line)) + f"  ({date}, ISA {slug})"
                elif not ISA_SUFFIX.search(line):
                    line += f"  ({date}, ISA {slug})"
                lines[b["line"] - 1] = line
                sids.append(sid)
            lines = _done_lines(lines, sids, date)
        if _all_done(_parse("\n".join(lines))) and STATUS_ACKED.match(status_line(text) or ""):
            i = old.index(status_line(text))
            lines[i] = f"status: done {date} #{acked_hash(text)}"
        if lines == old:
            return []
        before = set(old)
        changed = [ln for ln in lines if ln not in before]
        new = "\n".join(lines)
        _write_doc(path, new.replace("\n", "\r\n") if "\r\n" in raw else new)
        return changed
