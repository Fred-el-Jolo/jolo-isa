"""The `isa` commands: the only writers of ISAs, specs, plans and acks (FOUNDATION_2).

Every command prints what it did and the next step. A path line `ISA: <path>` or `Spec: <path>` binds that file to
the session (the PostToolUse hook reads it).
"""
import os
import re
import subprocess
import time

from . import advice, classify, doc, gitops, isafile, lint, spec, state

TIERS = ("E1", "E2", "E3", "E4")
CLOSED = "this ISA is closed; new work gets a new ISA"


class Refused(Exception):
    pass


def _open_isa(text):
    """Every command that writes a TASK ISA refuses a closed one."""
    if isafile.parse(text)["fm"].get("phase") == "complete":
        raise Refused(CLOSED)


def _in_build(p, text, path):
    """No probe runs before BUILD: from E2, the spec acked and unchanged since the ISA was derived, the ISA acked."""
    if isafile.tier(p) == "E1":
        return
    t = _tilde(path)
    sp = os.path.join(str(p["fm"].get("root")), str(p["fm"].get("spec") or ""))
    stext = _read(sp)
    if not spec.is_acked(stext):
        raise Refused(f"no probe runs before BUILD: its spec {_tilde(sp)} is reopened — `isa diff` for the user, the "
                      f"`Spec ack` question, then `isa ack {_tilde(sp)}`")
    if p["fm"].get("spec_hash") != spec.ack_hash(stext):
        raise Refused(f"no probe runs before BUILD: the spec changed since this ISA was derived — `isa refine {t}`, "
                      "then the `ISA ack` question")
    if not isafile.acked(text):
        raise Refused(f"no probe runs before BUILD: the ISA is not acked as it is now — `isa review {t}`, "
                      f"`isa show {t} --trace` for the user, then the `ISA ack` question")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise Refused(f"cannot read {path}: {e.strerror}") from None


def _write(path, text):
    with state.lock(path):
        state.write_atomic(path, text)


def _opt(args, name, many=False):
    """Pull `--name value` options out of args (in place)."""
    vals = []
    while name in args:
        i = args.index(name)
        if i + 1 >= len(args):
            raise Refused(f"{name} needs a value")
        vals.append(args[i + 1])
        del args[i:i + 2]
    return vals if many else (vals[-1] if vals else None)


def _flag(args, name):
    if name in args:
        args.remove(name)
        return True
    return False


def _tilde(p):
    h = os.path.expanduser("~")
    return "~" + p[len(h):] if p.startswith(h + os.sep) else p


def _kind(path):
    if state.is_doc_path(path):
        return "spec" if path.endswith("-01-spec.md") else "plan"
    if os.path.basename(path) == "ISA.md" and state.is_isa_path(path):
        return "isa"
    raise Refused(f"{path} is neither a TASK ISA (~/.isa/…/ISA.md) nor a spec (docs/YYYY-MM-DD-<slug>-01-spec.md)")


def _file(args, want=None):
    if not args:
        raise Refused("which file? (the ISA or the spec, as the first argument)")
    path = os.path.realpath(os.path.expanduser(args.pop(0)))
    kind = _kind(path)
    if want and kind not in want:
        raise Refused(f"{_tilde(path)} is a {kind}; this command takes {' or '.join(want)}")
    if not os.path.isfile(path):
        raise Refused(f"{_tilde(path)} does not exist")
    return path, kind


def _lint_note(path, text, moment="draft"):
    errs = spec.lint(text) if _kind(path) == "spec" else lint.errors(text, path, moment)
    if not errs:
        return "lint: ok"
    return f"lint: {len(errs)} to do:\n" + "\n".join(f"  - {e}" for e in errs[:12]) + (
        f"\n  … and {len(errs) - 12} more (`isa lint {_tilde(path)}`)" if len(errs) > 12 else "")


def _verbatim(span, what):
    prompts = state.session_prompts()
    if prompts is not None and prompts and not any(span in p for p in prompts):
        raise Refused(f"{what} \"{span[:60]}\" is not a verbatim span of a prompt of this session — copy the "
                      "user's words byte for byte")


# ------------------------------------------------------------------ start

def spec_cmd(args, out=print):
    if args[:1] != ["new"]:
        raise Refused("usage: isa spec new <slug> --tier E2|E3|E4")
    args = args[1:]
    tier = (_opt(args, "--tier") or "").upper()
    if tier not in TIERS[1:]:
        raise Refused("a spec is E2, E3 or E4 (`--tier E2`); E1 work has no spec: `isa new <slug> --tier E1`")
    if not args:
        raise Refused("usage: isa spec new <slug> --tier E2|E3|E4")
    slug = re.sub(r"[^a-z0-9]+", "-", args[0].lower()).strip("-")
    path = os.path.join(os.getcwd(), "docs", f"{time.strftime('%Y-%m-%d')}-{slug}-01-spec.md")
    if os.path.exists(path):
        raise Refused(f"{_tilde(path)} exists already")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _write(path, spec.template(slug.replace("-", " ").capitalize(), tier))
    heads = ["Title", "Problem", "Goal", "Out of scope", "Constraints"] + (["Approaches"] if tier != "E2" else [])
    out(f"Spec: {path}")
    out(f"Write each part with `isa write {_tilde(path)} <part>` (the text on stdin): {', '.join(heads)}, then "
        "one `S1 — <part>` per deliverable part (a description, then `Accepted when:` and `- <outcome>` lines). "
        "Ask the user's open questions; then `isa lint`, then the `Spec ack` question.")
    return 0


def new(args, out=print):
    args = list(args)
    goal, asks = _opt(args, "--goal"), _opt(args, "--ask", many=True)
    spec_arg, tier = _opt(args, "--spec"), (_opt(args, "--tier") or "").upper()
    for a in ([goal] if goal else []) + asks:
        _verbatim(a, "--goal" if a == goal else "--ask")
    if spec_arg:
        return _new_from_spec(os.path.realpath(os.path.expanduser(spec_arg)), goal, asks, out)
    if tier != "E1" or not args:
        raise Refused("E1 work: `isa new <slug> --tier E1`. E2–E4 work starts from its acked spec: "
                      "`isa spec new <slug> --tier E2`, then `isa new --spec <spec>`")
    root = state.project_root(os.getcwd())
    path = state.new_isa_path(root, args[0])
    fm = _fm(args[0], "E1", root, goal, asks, {"slug": os.path.basename(os.path.dirname(path))})
    _write(path, _skeleton(fm, isafile.E1_REQUIRED))
    out(f"ISA: {path}")
    out(f"Write it: `isa write {_tilde(path)} <section>` for Problem, Goal, Criteria (one level, at least one "
        "`Anti:`), Test Strategy; then `isa lint`, `isa verify --red`, the build, `isa verify`, `isa close`.")
    return 0


def _fm(slug, tier, root, goal, asks, extra=None):
    fm = {"task": slug.replace("-", " "), "slug": None, "effort": tier, "phase": "draft", "progress": "0/0",
          "started": isafile.stamp(), "updated": isafile.stamp(), "root": root}
    fm.update(extra or {})
    fm.update(gitops.snapshot(root))
    if goal:
        fm["stated_goal"] = goal
    if asks:
        fm["asks"] = asks
    return fm


def _skeleton(fm, heads, seeds=None):
    text = "---\n" + "\n".join(f"{k}: {doc.fm_value(v)}" for k, v in fm.items() if v is not None) + "\n---\n"
    for h in heads:
        text += f"\n## {h}\n\n" + (seeds or {}).get(h, "").strip() + ("\n" if (seeds or {}).get(h) else "")
    return re.sub(r"\n{3,}", "\n\n", text)


def _new_from_spec(sp, goal, asks, out):
    if not (state.is_doc_path(sp) and sp.endswith("-01-spec.md")) or not os.path.isfile(sp):
        raise Refused(f"{_tilde(sp)} is not a spec (docs/YYYY-MM-DD-<slug>-01-spec.md)")
    stext = _read(sp)
    if os.path.exists(spec.plan_path(sp)):
        raise Refused(f"{_tilde(sp)} is finished: its plan {_tilde(spec.plan_path(sp))} exists")
    if not spec.is_acked(stext):
        raise Refused(f"{_tilde(sp)} is not acked as it is now — finish it and ask the user's `Spec ack` first")
    root = spec.doc_root(sp)
    rel = os.path.relpath(sp, root)
    for p, fm in state.list_isas(state.project_dir(root)):
        if fm.get("spec") == rel and fm.get("phase") != "complete":
            out(f"ISA: {p}")
            out(f"(the open ISA of this spec — bound again; `isa show {_tilde(p)}`)")
            return 0
    sfm, _, sbody = doc.split(stext)
    secs = doc.section_map(sbody)
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-|-01-spec\.md$", "", os.path.basename(sp))
    path = state.new_isa_path(root, slug)
    goal_text = (secs.get("Goal") or "").split("\nSaid:")[0].strip()
    parents = [spec.S_HEAD.match(h) for h in spec.s_sections(stext)]
    seeds = {"Problem": secs.get("Problem", ""), "Out of Scope": secs.get("Out of scope", ""),
             "Constraints": secs.get("Constraints", ""), "Goal": goal_text,
             "Criteria": "\n".join(f"- [ ] ISC-{m.group(1)}: {m.group(2).strip()}" for m in parents)}
    fm = _fm(slug, str(sfm.get("effort")), root, goal, asks,
             {"task": doc.title(sbody) or slug, "slug": os.path.basename(os.path.dirname(path)), "spec": rel,
              "spec_hash": spec.ack_hash(stext)})
    _write(path, _skeleton(fm, isafile.CONTENT, seeds))
    out(f"ISA: {path}")
    out("Seeded from the spec: Problem, Out of Scope, Constraints, Goal, and one parent per section (ISC-k for Sk). "
        f"Write Vision and Principles, then the criteria one at a time (up to "
        f"{isafile.DEPTH.get(fm['effort']) or 'any number of'} levels):\n"
        "  - under its section: `isa write <ISA> ISC-k.n \"<claim>\" --probe \"<command>\"` (anchored to Sk unasked);\n"
        "  - common ground two sections share: `ISC-0` first (`isa write <ISA> ISC-0 \"Common ground\" --before "
        "ISC-1`), its leaves with `--serves S2+S3 --why \"…\"`; a section's prerequisites as its first children "
        "(`--before ISC-k.1`);\n"
        "  - Antis outside the sections: `--anchors Goal` or `--anchors Constraints`; anything the spec doesn't "
        "state: `--source context --why \"…\"`.\n"
        "Then `isa lint`, `isa review <ISA>` (the six-line checklist on stdin), `isa show <ISA> --trace` for the "
        "user, and the `ISA ack` question.")
    for h in spec.s_sections(stext):
        out(f"  {h}: " + " | ".join(ln[2:] for ln in (secs.get(h) or "").split("Accepted when:")[-1].split("\n")
                                     if ln.startswith("- ")))
    return 0


# ------------------------------------------------------------------ write

def write(args, stdin_text, out=print):
    args = list(args)
    stdin_text = stdin_text or ""
    probe, kind_, fails, anchors = (_opt(args, "--probe"), _opt(args, "--kind"), _opt(args, "--fails-when"),
                                    _opt(args, "--anchors"))
    origin = {"before": _opt(args, "--before"), "serves": _opt(args, "--serves"), "source": _opt(args, "--source"),
              "why": _opt(args, "--why")}
    path, kind = _file(args, ("spec", "isa"))
    if not args:
        raise Refused("which part? `isa write <file> <section>` (text on stdin), or `isa write <ISA> ISC-N …`")
    part = args.pop(0)
    text = _read(path)
    if kind == "spec":
        if spec.status(text) != "draft":
            raise Refused(f"{_tilde(path)} is acked — `isa reopen {_tilde(path)}` first (the user acks it again)")
        new = spec.set_section(text, part, (stdin_text if not args else " ".join(args)) + "\n")
        _write(path, new)
        out(f"wrote {spec.canonical(part)} in {_tilde(path)}\n{_lint_note(path, new)}")
        return 0
    _open_isa(text)
    if re.fullmatch(r"ISC-\d+(\.\d+)*", part):
        new = _write_isc(text, part[4:], " ".join(args) if args else (stdin_text.strip() if not probe else ""),
                         probe, kind_, fails, anchors, **origin)
    elif part.lower() in ("task", "asks"):
        value = " ".join(args) if args else stdin_text.strip()
        if part.lower() == "asks":
            value = [ln.strip() for ln in value.split("\n") if ln.strip()]
            for a in value:
                _verbatim(a, "ask")
        new = doc.fm_set(text, part.lower(), value)
    else:
        new = _write_section(text, part, stdin_text if not args else " ".join(args))
    new = isafile.refresh(new)
    _write(path, new)
    out(f"wrote {part} in {_tilde(path)}\n{_lint_note(path, new)}")
    return 0


def _section_name(part):
    for h in isafile.SECTIONS:
        if part.strip().lower() == h.lower():
            return h
    raise Refused(f"`{part}` is not an ISA section ({', '.join(isafile.CONTENT)}), `task`, `asks` or `ISC-N`")


def _write_section(text, part, content):
    h = _section_name(part)
    if h == "Decisions":
        raise Refused('Decisions grow one row at a time: `isa decide <ISA> "<text>"`')
    if h == "Verification":
        raise Refused("Verification is written by `isa verify`, `isa attest` and `isa answer`")
    if h == "Review":
        raise Refused("`## Review` is written by `isa review <ISA>` (the checklist on stdin)")
    p = isafile.parse(text)
    tier = isafile.tier(p)
    if tier == "E1" and h in isafile.E1_FORBIDDEN:
        raise Refused(f"E1 has no `## {h}`")
    if h in ("Criteria", "Test Strategy") and (p["sections"].get(h) or "").strip():
        raise Refused(f"`## {h}` is written once as a block; change one criterion with `isa write <ISA> ISC-N "
                      '"<text>"`, its probe with `isa write <ISA> ISC-N --probe "<command>"`, or drop it with '
                      '`isa drop <ISA> ISC-N "<why>"`')
    if h == "Criteria":
        q = isafile.parse(doc.set_section(text, h, content, isafile.SECTIONS))
        if q["errors"]:
            raise Refused("Criteria: " + "; ".join(q["errors"][:5]))
        for i in q["order"]:
            q["iscs"][i]["box"] = " "
        content = isafile.render_criteria(q)
    if h == "Test Strategy":
        q = isafile.parse(doc.set_section(text, h, content, isafile.SECTIONS))
        if q["tests_error"]:
            raise Refused(q["tests_error"])
        content = isafile.render_tests(q["tests"])
    return doc.set_section(text, h, content, isafile.SECTIONS)


def _section_ids(p):
    """The `S<k>` numbers of the ISA's spec ({} for E1, or when the spec can't be read)."""
    sp = os.path.join(str(p["fm"].get("root")), str(p["fm"].get("spec") or ""))
    if not p["fm"].get("spec") or not os.path.isfile(sp):
        return set()
    with open(sp, encoding="utf-8") as f:
        return {spec.S_HEAD.match(h).group(1) for h in spec.s_sections(f.read())}


def _write_isc(text, isc, words, probe, kind_, fails, anchors, before=None, serves=None, source=None, why=None):
    p = isafile.parse(text)
    cap = isafile.DEPTH.get(isafile.tier(p))
    existing = p["iscs"].get(isc)
    if existing and existing["dropped"]:
        raise Refused(f"ISC-{isc} is dropped; ids are never reused — take a new one")
    if before and existing:
        raise Refused(f"ISC-{isc} exists; `--before` places a new criterion (moving one is out of scope)")
    up = isc.rsplit(".", 1)[0] if "." in isc else None
    if words:
        if existing:
            if words != existing["text"]:
                existing.update(text=words, box=" ")
        else:
            if up and up not in p["iscs"]:
                raise Refused(f"ISC-{isc}: no ISC-{up} above it")
            level = isc.count(".") + 1
            if cap and level > cap:
                raise Refused(f"ISC-{isc} would be nested {level} levels; {isafile.tier(p)} allows {cap}")
            p["iscs"][isc] = {"id": isc, "level": level, "indent": 2 * (level - 1), "box": " ", "text": words,
                              "dropped": False, "children": []}
            at = len(p["order"])
            if before:
                t = before.replace("ISC-", "")
                if t not in p["iscs"] or (t.rsplit(".", 1)[0] if "." in t else None) != up:
                    raise Refused(f"ISC-{isc} --before {before}: not a sibling (`--before` names a criterion with the "
                                  "same parent)")
                at = p["order"].index(t)
            elif up:
                fam = [n for n, j in enumerate(p["order"]) if j == up or j.startswith(up + ".")]
                at = fam[-1] + 1
            if up:
                kids = p["iscs"][up]["children"]
                kids.insert(kids.index(before.replace("ISC-", "")) if before else len(kids), isc)
            p["order"].insert(at, isc)
            top = isc.split(".")[0]
            if up and top != "0" and not anchors and top in _section_ids(p):
                anchors = f"S{top}"  # a leaf under its section's parent comes from that section
        text = doc.set_section(text, "Criteria", isafile.render_criteria(p), isafile.SECTIONS)
    elif before:
        raise Refused(f"`--before` places a new criterion: `isa write <ISA> ISC-{isc} \"<claim>\" --before {before}`")
    if probe is not None or kind_ or fails or anchors or serves or source or why:
        if isc not in p["iscs"]:
            raise Refused(f"ISC-{isc} is not a criterion yet: `isa write <ISA> ISC-{isc} \"<claim>\"` first")
        if p["iscs"][isc]["children"]:
            raise Refused(f"ISC-{isc} is a parent — its children carry the probes")
        if probe is not None and classify.bash(probe, str(p["fm"].get("root") or "")) == "guarded":
            raise Refused(f"ISC-{isc}: the probe `{probe}` writes an ISA, a spec, a plan or ~/.isa — a probe checks "
                          "the work and never changes an ISA entity")
        q = isafile.parse(text)
        entries = [dict(e) for e in q["tests"]]
        e = isafile.entry(q, isc)
        if e is None:
            e = {"isc": f"ISC-{isc}", "kind": "behaviour"}
            entries.append(e)
        else:
            e = next(x for x in entries if str(x.get("isc", "")).replace("ISC-", "") == isc)
        changed = probe is not None and probe != e.get("tool")
        for k, v in (("tool", probe), ("kind", kind_), ("fails-when", fails), ("anchors_to", anchors),
                     ("serves", serves), ("source", source), ("why", why)):
            if v is not None:
                e[k] = v
        order = {i: n for n, i in enumerate(q["order"])}
        entries.sort(key=lambda x: order.get(str(x.get("isc", "")).replace("ISC-", ""), 10 ** 6))
        text = doc.set_section(text, "Test Strategy", isafile.render_tests(entries), isafile.SECTIONS)
        if changed:
            text = isafile.set_box(text, isc, False)
    return text


def drop(args, out=print):
    args = list(args)
    path, _ = _file(args, ("isa",))
    if len(args) < 2 or not re.fullmatch(r"ISC-\d+(\.\d+)*", args[0]):
        raise Refused('usage: isa drop <ISA> ISC-N "<why>"')
    isc, why = args[0][4:], " ".join(args[1:])
    text = _read(path)
    _open_isa(text)
    p = isafile.parse(text)
    if isc not in p["iscs"]:
        raise Refused(f"ISC-{isc} is not a criterion")
    for i in p["order"]:
        if i == isc or i.startswith(isc + "."):
            p["iscs"][i].update(text=f"[DROPPED — {why}]", dropped=True, box=" ")
    text = doc.set_section(text, "Criteria", isafile.render_criteria(p), isafile.SECTIONS)
    keep = [e for e in p["tests"] if not re.fullmatch(rf"(ISC-)?{re.escape(isc)}(\.\d+)*", str(e.get("isc", "")))]
    text = doc.set_section(text, "Test Strategy", isafile.render_tests(keep), isafile.SECTIONS)
    text = isafile.refresh(text)
    _write(path, text)
    out(f"dropped ISC-{isc} (a tombstone keeps the id)\n{_lint_note(path, text)}")
    return 0


def decide(args, out=print):
    args = list(args)
    path, _ = _file(args, ("isa",))
    if not args:
        raise Refused('usage: isa decide <ISA> "<text>"')
    text = _read(path)
    _open_isa(text)
    rows = (isafile.parse(text)["sections"].get("Decisions") or "").strip()
    rows = (rows + "\n" if rows else "") + f"- {isafile.now()}: {' '.join(args)}"
    text = isafile.refresh(doc.set_section(text, "Decisions", rows, isafile.SECTIONS))
    _write(path, text)
    out("decision recorded")
    return 0


# ------------------------------------------------------------------ read

def show(args, out=print):
    args = list(args)
    to, traced = _opt(args, "--to"), _flag(args, "--trace")
    path, kind = _file(args, ("spec", "isa", "plan"))
    text = _read(path)
    if traced:
        if kind != "isa":
            raise Refused("`--trace` shows a TASK ISA against its spec")
        from . import review
        out(review.trace(path, text))
        return 0
    if not to:
        out(text.rstrip("\n"))
        return 0
    _, _, body = doc.split(text)
    lines, kept = body.split("\n"), []
    for h, s, e in doc.sections(body):
        kept += lines[s:e]
        if h.lower() == to.lower():
            break
    else:
        raise Refused(f"no `## {to}` in {_tilde(path)}")
    out((doc.title(body) and f"# {doc.title(body)}\n") or "")
    out("\n".join(kept).rstrip("\n"))
    return 0


def diff_cmd(args, out=print):
    args = list(args)
    path, kind = _file(args, ("spec", "isa"))
    text = _read(path)
    title = doc.title(doc.split(text)[2]) if kind == "spec" else f"ISA {doc.split(text)[0].get('task', '')}"
    out("\n".join(spec.diff(path, text, title)))
    return 0


# ------------------------------------------------------------------ acks

def ack(args, out=print):
    args = list(args)
    path, kind = _file(args, ("spec", "isa"))
    text = _read(path)
    if kind == "isa":
        _open_isa(text)
    h = spec.hash_of(path, text)
    if kind == "isa" and isafile.tier(isafile.parse(text)) == "E1":
        raise Refused("an E1 ISA has no ack: build it")
    errs = spec.lint(text) if kind == "spec" else lint.errors(text, path) + isafile.review_errors(text)
    if errs:
        raise Refused("it isn't ready for the ack:\n" + "\n".join(f"  - {e}" for e in errs[:12]))
    if not spec.clicked(path, h, text):
        q = "Spec ack" if kind == "spec" else "ISA ack"
        raise Refused(f"no click: ask the user with AskUserQuestion (header `{q}`, options `Acknowledge` / "
                      f"`Request changes`). `isa ack` records only the user's own click on the file as it is now")
    if kind == "spec":
        text = doc.fm_set(text, "status", f"acked {time.strftime('%Y-%m-%d')} #{h}")
        _write(path, text)
        sha, err = gitops.commit(spec.doc_root(path), [path], f"Spec: {doc.title(doc.split(text)[2])} (acked)")
        out(f"acked {_tilde(path)} (#{h})" + (f", committed {sha}" if sha else ""))
        if err:
            out(f"Not committed: the spec — {err}")
        out("The ack is the go: `isa new --spec " + _tilde(path) + "` (or `isa refine <ISA>` for its open ISA).")
    else:
        text = doc.fm_set(text, "acked", f"{time.strftime('%Y-%m-%d')} #{h}")
        text = doc.fm_set(text, "phase", "build")
        _write(path, text)
        out(f"acked the ISA (#{h}): BUILD — `isa verify --red`, the work, `isa verify`, `isa close`")
    return 0


def reopen(args, out=print):
    args = list(args)
    path, _ = _file(args, ("spec",))
    text = _read(path)
    if not spec.status(text).startswith("acked"):
        raise Refused(f"{_tilde(path)} is a draft already")
    _write(path, doc.fm_set(text, "status", "draft"))
    out(f"reopened {_tilde(path)}: edit it with `isa write`, then `isa diff` for the user and the `Spec ack` question")
    return 0


def refine(args, out=print):
    args = list(args)
    path, _ = _file(args, ("isa",))
    text = _read(path)
    _open_isa(text)
    p = isafile.parse(text)
    sp = os.path.join(str(p["fm"].get("root")), str(p["fm"].get("spec") or ""))
    if not p["fm"].get("spec") or not os.path.isfile(sp):
        raise Refused("this ISA has no spec to follow")
    stext = _read(sp)
    if not spec.is_acked(stext):
        raise Refused("its spec is not acked yet: the user acks it first")
    if p["fm"].get("spec_hash") == spec.ack_hash(stext):
        raise Refused("its spec is unchanged since this ISA was derived")
    text = doc.fm_set(doc.fm_set(text, "spec_hash", spec.ack_hash(stext)), "acked", None)
    text = doc.fm_set(text, "phase", "draft")
    _write(path, isafile.refresh(text))
    out("\n".join(spec.diff(sp, stext, doc.title(doc.split(stext)[2]))))
    out("Progress is kept. Update the criteria this changes (`isa write <ISA> ISC-N`, `isa drop`), then the "
        "`ISA ack` question.")
    return 0


# ------------------------------------------------------------------ proof

def _env():
    return {k: v for k, v in os.environ.items() if not k.startswith("ISA_") or k == "ISA_HOME"}


def _run(cmd, root, timeout=600):
    t0 = time.time()
    try:
        r = subprocess.run(["bash", "-c", cmd], cwd=root, env=_env(), capture_output=True, text=True, timeout=timeout)
        code = r.returncode
    except subprocess.TimeoutExpired:
        code = 124
    return code, round(time.time() - t0, 2)


def _probe_set(p, select):
    leaves = isafile.leaves(p)
    if select:
        bad = [s for s in select if s[4:] not in leaves]
        if bad:
            raise Refused(f"not leaf criteria: {', '.join(bad)}")
        leaves = [s[4:] for s in select]
    return [(i, isafile.entry(p, i)) for i in leaves if (isafile.entry(p, i) or {}).get("kind") != "manual"]


def _red_failed(p, isc, cmd):
    m = isafile.RUN.match(((p["ver"]["iscs"].get(isc) or {}).get("red") or "").split(" red ", 1)[-1])
    return bool(m) and m.group("code") != "0" and m.group("cmd") == cmd


def _proved(text, p, results, red):
    for isc, (code, cmd) in results.items():
        when = isafile.now()
        if red:
            text = isafile.set_ver(text, isc, "red", f"- ISC-{isc}: red {when} exit {code} — `{cmd}`")
            continue
        if code == 0:
            kind = (isafile.entry(p, isc) or {}).get("kind")
            note = " (no red baseline)" if kind == "behaviour" and not _red_failed(p, isc, cmd) else ""
            text = isafile.set_ver(text, isc, "result", f"- ISC-{isc}: verified {when} exit 0 — `{cmd}`{note}")
        else:
            text = isafile.set_ver(text, isc, "result", f"- ISC-{isc}: failed {when} exit {code} — `{cmd}`")
        text = isafile.set_box(text, isc, code == 0)
    return text


def verify(args, out=print):
    args = list(args)
    red = _flag(args, "--red")
    timeout = _opt(args, "--timeout")
    if timeout is not None and not timeout.isdigit():
        raise Refused("--timeout takes whole seconds")
    timeout = int(timeout or 600)
    path, _ = _file(args, ("isa",))
    text = _read(path)
    _open_isa(text)
    errs = lint.errors(text, path)
    if errs:
        raise Refused("the ISA doesn't lint yet, so no probe runs:\n" + "\n".join(f"  - {e}" for e in errs[:12]))
    p = isafile.parse(text)
    _in_build(p, text, path)
    root = str(p["fm"].get("root"))
    results, failed, advice_lines = {}, [], []
    for isc, e in _probe_set(p, args):
        code, secs = _run(str(e["tool"]), root, timeout)
        results[isc] = (code, str(e["tool"]))
        word = ("FAIL (red, as expected)" if code else "PASS at red — this probe can't be seen failing") if red \
            else ("PASS" if code == 0 else "FAIL")
        out(f"ISC-{isc} {word}  exit {code}  {secs}s  {e['tool']}")
        if code and not red:
            failed.append(isc)
        if code == 0 and not red:
            advice_lines += advice.probe(p, isc, e)
    for line in advice_lines:
        out(line)
    text = isafile.refresh(_proved(text, p, results, red))
    _write(path, text)
    out(f"progress {isafile.progress(isafile.parse(text))}" + (f" — failed: {', '.join('ISC-' + i for i in failed)}. "
                                                              "Claim wrong or code wrong?" if failed else ""))
    return 1 if failed else 0


def attest(args, out=print):
    args = list(args)
    path, _ = _file(args, ("isa",))
    if len(args) < 2:
        raise Refused('usage: isa attest <ISA> ISC-N "<evidence>"')
    isc, evidence = args[0][4:], " ".join(args[1:])
    text = _read(path)
    _open_isa(text)
    p = isafile.parse(text)
    if isc not in isafile.leaves(p) or (isafile.entry(p, isc) or {}).get("kind") != "manual":
        raise Refused(f"ISC-{isc} is not a manual leaf: its probe is a command — `isa verify`")
    text = isafile.set_ver(text, isc, "result", f"- ISC-{isc}: attested {isafile.now()} — {evidence}")
    text = isafile.refresh(isafile.set_box(text, isc, True))
    _write(path, text)
    out(f"ISC-{isc} attested — listed to the user at close as not machine-verified")
    return 0


def answer(args, out=print):
    args = list(args)
    path, _ = _file(args, ("isa",))
    text = _read(path)
    _open_isa(text)
    if args[:1] == ["goal"] and len(args) >= 2:
        line = " ".join(args[1:])
        if not re.match(r"^(yes|no)\b", line):
            raise Refused('the goal answer starts with `yes` or `no`: isa answer <ISA> goal "yes — <evidence>"')
        text = isafile.set_ver(text, goal=f"- Goal: {line}")
    elif args[:1] == ["ask"] and len(args) >= 3 and args[1].isdigit():
        n = int(args[1])
        if n < 1 or n > len(isafile.parse(text)["fm"].get("asks") or []):
            raise Refused(f"there is no ask {n} in `asks:`")
        text = isafile.set_ver(text, ask=(n, f"- Ask {n}: {' '.join(args[2:])}"))
    else:
        raise Refused('usage: isa answer <ISA> goal "yes — <evidence>" | isa answer <ISA> ask N "met — <evidence>"')
    _write(path, isafile.refresh(text))
    out("answered")
    return 0


def close(args, out=print):
    args = list(args)
    path, _ = _file(args, ("isa",))
    text = _read(path)
    _open_isa(text)
    errs = lint.errors(text, path)
    if errs:
        raise Refused("not closed — the ISA doesn't lint:\n" + "\n".join(f"  - {e}" for e in errs[:12]))
    p = isafile.parse(text)
    root = str(p["fm"].get("root"))
    results = {}
    for isc, e in _probe_set(p, []):
        results[isc] = (_run(str(e["tool"]), root)[0], str(e["tool"]))
    bad = [f"ISC-{i}: exit {c} — `{cmd}`" for i, (c, cmd) in results.items() if c]
    if bad:
        raise Refused("not closed — nothing written; these probes fail now:\n" + "\n".join(f"  - {b}" for b in bad))
    closing = isafile.refresh(_proved(text, p, results, False))
    errs = lint.errors(closing, path, "close")
    if errs:
        raise Refused("not closed — nothing written:\n" + "\n".join(f"  - {e}" for e in errs))
    closing = doc.fm_set(closing, "phase", "complete")
    q = isafile.parse(closing)
    plan, sp = None, None
    if isafile.tier(q) != "E1":
        sp = os.path.join(root, str(q["fm"]["spec"]))
        plan = spec.plan_path(sp)
        _write(plan, spec.render_plan(closing, doc.title(doc.split(_read(sp))[2]), os.path.basename(sp),
                                      q["fm"].get("slug") or os.path.basename(os.path.dirname(path))))
    _write(path, closing)
    work = gitops.changed_since(root, q["fm"].get("base_dirty"), exclude=[x for x in (sp, plan) if x])
    sha, werr = gitops.commit(root, work, str(q["fm"].get("task") or "ISA task"))
    psha, perr = gitops.commit(root, [plan], f"Plan: {q['fm'].get('task')}") if plan else (None, None)
    out(_summary(path, closing, results, plan, sha, psha))
    for what, err in (("the work", werr), ("the plan", perr)):
        if err:
            out(f"Not committed: {what} — {err}")
    for line in advice.close(isafile.parse(closing)):
        out(line)
    return 0


def _summary(path, text, results, plan, sha, psha):
    p = isafile.parse(text)
    lines = [f"isa close: {_tilde(path)} — complete, progress {isafile.progress(p)}", "Proven (every probe re-run):"]
    lines += [f"  - ISC-{i}: exit 0 — `{cmd}`" for i, (_, cmd) in results.items()]
    nored = [i for i in results if "(no red baseline)" in ((p["ver"]["iscs"].get(i) or {}).get("result") or "")]
    if nored:
        lines.append("No red baseline (never seen failing): " + ", ".join(f"ISC-{i}" for i in nored))
    att = [i for i in isafile.leaves(p) if "attested" in ((p["ver"]["iscs"].get(i) or {}).get("result") or "")]
    if att:
        lines.append("Self-attested (check them): " + ", ".join(f"ISC-{i}" for i in att))
    dropped = [f"ISC-{i}" for i in p["order"] if p["iscs"][i]["dropped"]]
    if dropped:
        lines.append("Dropped: " + ", ".join(dropped))
    lines += [p["ver"]["goal"]] if p["ver"]["goal"] else []
    lines += [p["ver"]["asks"][n] for n in sorted(p["ver"]["asks"])]
    if plan:
        lines.append(f"Plan written: {_tilde(plan)}")
    if sha or psha:
        lines.append("Committed: " + ", ".join(x for x in (sha and f"the work {sha}", psha and f"the plan {psha}") if x))
    return "\n".join(lines)


# ------------------------------------------------------------------ listing

def ls(args, out=print):
    folders = [state.project_dir(os.getcwd())]
    if "--all" in args and os.path.isdir(state.home()):
        folders += [os.path.join(state.home(), k) for k in sorted(os.listdir(state.home()))
                    if not k.startswith(("_", ".")) and os.path.join(state.home(), k) != folders[0]]
    n = 0
    for folder in folders:
        rows = state.list_isas(folder)
        if rows:
            out(os.path.basename(folder) + "/")
        for p, fm in rows:
            n += 1
            out(f"  {os.path.basename(os.path.dirname(p)):<48} {str(fm.get('effort', '?')):<3} "
                f"{str(fm.get('phase', '?')):<9} {str(fm.get('progress', '?')):<7} {fm.get('task', '')}")
    if not n:
        out(f"no ISAs under {_tilde(folders[0])}")
    return 0


def where(args, out=print):
    out(f"project key: {state.project_key(os.getcwd())}\nISA folder:  {state.project_dir(os.getcwd())}")
    return 0
