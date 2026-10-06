"""Markdown files with YAML frontmatter and `## ` sections: the shared layer of ISAs, specs and plans.

A section runs from its `## ` heading to the next `## ` heading outside a fenced block. HTML comments are
reader notes: they are blanked outside fenced blocks only, so a probe's command keeps its text.
"""
import hashlib
import re

from . import yamlish

FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def norm(text):
    return text.replace("\r\n", "\n")


def split(text):
    """→ (frontmatter dict, frontmatter text, body). A missing or broken frontmatter gives ({}, "", text)."""
    text = norm(text)
    m = FM.match(text)
    if not m:
        return {}, "", text
    try:
        fm = yamlish.load(m.group(1)) or {}
    except yamlish.YamlError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), m.group(1), text[m.end():]


def fm_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(fm_value(x) for x in v) + "]"
    if v is None:
        return "null"
    s = str(v)
    if s == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]|^\s|\s$|^[-?]", s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def fm_set(text, key, value):
    """Set (value not None) or remove (None) one frontmatter key; keeps every other line as written."""
    text = norm(text)
    m = FM.match(text)
    lines = m.group(1).split("\n") if m else []
    body = text[m.end():] if m else text
    out, done = [], False
    for ln in lines:
        if re.match(rf"^{re.escape(key)}:(\s|$)", ln):
            if value is not None and not done:
                out.append(f"{key}: {fm_value(value)}")
            done = True
        else:
            out.append(ln)
    if not done and value is not None:
        out.append(f"{key}: {fm_value(value)}")
    return "---\n" + "\n".join(out) + "\n---\n" + body


def _blank_comments(body):
    """Comments blanked outside fences, line count kept."""
    out, fence, buf = [], False, []
    for ln in body.split("\n"):
        if ln.startswith("```"):
            if not fence and buf:
                out.append(COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), "\n".join(buf)))
                buf = []
            fence = not fence
            out.append(ln)
        elif fence:
            out.append(ln)
        else:
            buf.append(ln)
    if buf:
        out.append(COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), "\n".join(buf)))
    return "\n".join(out)


def sections(body):
    """[(heading, start_line, end_line)] over `body` lines (end exclusive), headings outside fences."""
    lines = body.split("\n")
    heads, fence = [], False
    for i, ln in enumerate(lines):
        if ln.startswith("```"):
            fence = not fence
        elif not fence and ln.startswith("## "):
            heads.append((ln[3:].strip(), i))
    return [(h, i, heads[n + 1][1] if n + 1 < len(heads) else len(lines)) for n, (h, i) in enumerate(heads)]


def section_map(body):
    """{heading: content text (comments blanked outside fences, stripped)} for each `## ` section."""
    clean = _blank_comments(body).split("\n")
    return {h: "\n".join(clean[s + 1:e]).strip() for h, s, e in sections(body)}


def raw_section(body, heading):
    lines = body.split("\n")
    for h, s, e in sections(body):
        if h == heading:
            return "\n".join(lines[s + 1:e]).strip("\n")
    return None


def set_section(text, heading, content, order=None):
    """Replace the section `heading` with `content`, or insert it: before the first section that comes after it
    in `order` (a list of headings, or a function heading → sort key), else at the end."""
    text = norm(text)
    m = FM.match(text)
    head, body = (text[:m.end()], text[m.end():]) if m else ("", text)
    lines = body.split("\n")
    block = [f"## {heading}", ""] + (content.strip("\n").split("\n") if content.strip() else []) + [""]
    secs = sections(body)
    for h, s, e in secs:
        if h == heading:
            lines[s:e] = block
            return head + "\n".join(lines).rstrip("\n") + "\n"
    key = (lambda h: order.index(h) if h in order else len(order)) if isinstance(order, list) else order
    at = len(lines)
    if key:
        mine = key(heading)
        for h, s, _ in secs:
            if key(h) > mine:
                at = s
                break
    while at == len(lines) and lines and not lines[-1].strip():
        lines.pop()
        at = len(lines)
    if at == len(lines):
        lines += [""] + block
    else:
        lines[at:at] = block
    return head + "\n".join(lines).rstrip("\n") + "\n"


def remove_section(text, heading):
    text = norm(text)
    m = FM.match(text)
    head, body = (text[:m.end()], text[m.end():]) if m else ("", text)
    lines = body.split("\n")
    for h, s, e in sections(body):
        if h == heading:
            del lines[s:e]
            break
    return head + "\n".join(lines).rstrip("\n") + "\n"


def title(body):
    for ln in body.split("\n"):
        if ln.startswith("# "):
            return ln[2:].strip()
    return ""


def h8(text):
    return hashlib.sha256(norm(text).rstrip("\n").encode("utf-8")).hexdigest()[:8]
