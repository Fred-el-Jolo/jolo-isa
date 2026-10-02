"""Engine writes to an ISA.md (SPEC-v2 § 3.1): ticks, generated Verification lines, `progress`,
nested parents, frontmatter fields. Standard library only.

The model owns the content; these functions only touch the engine-owned parts and leave every other
byte as it was. All of them take and return text; `write_atomic` puts it on disk (temp file + rename).

    normalize(text)  tick/untick nested parents from their leaves, drop orphaned generated Verification
                     lines, recompute `progress` — what lint, verify and close run before they check
                     anything, so an engine-owned field the model's edit made stale never blocks it
"""
import json
import os
import re
import tempfile
import time

from . import lint

GENERATED = re.compile(r"^- (ISC-\d+(?:\.\d+)*): (verified|attested|regressed)\b")
LEGACY = re.compile(r"^- (ISC-\d+(?:\.\d+)*): `isa verify` (PASS|FAIL)\b")  # the lines v1 `isa verify` printed
FM_BLOCK = re.compile(r"\A---\n(.*?\n)---\n", re.S)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ------------------------------------------------------------------ frontmatter

def _yaml_value(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_yaml_value(x) for x in v) + "]"
    s = str(v)
    if re.fullmatch(r"[A-Za-z0-9_./~+-][A-Za-z0-9_./~+:-]*", s) and ": " not in s and s not in ("null", "true", "false"):
        return s
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid YAML double-quoted scalar


def fm_set(text, key, value):
    """`key: value` in the frontmatter: replaced in place, or added before the closing `---`."""
    m = FM_BLOCK.match(text)
    if not m:
        return text
    block = m.group(1)
    line = f"{key}: {_yaml_value(value)}"
    pat = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    block = pat.sub(lambda _: line, block, count=1) if pat.search(block) else block + line + "\n"
    return "---\n" + block + "---\n" + text[m.end():]


def fm(text):
    return lint.parse(text)["fm"]


# ------------------------------------------------------------------ criteria

def _set_box(text, isc, checked):
    pat = re.compile(rf"^(\s*- \[)( |x|X)(\] {re.escape(isc)}:)", re.M)
    return pat.sub(lambda m: m.group(1) + ("x" if checked else " ") + m.group(3), text, count=1)


def tick(text, isc):
    return _set_box(text, isc, True)


def untick(text, isc):
    return _set_box(text, isc, False)


def waived(p):
    return set(re.findall(r"waived: (ISC-\d+(?:\.\d+)*)", p["content"].get("Decisions", "")))


def sync_parents(text):
    """A nested parent is ticked exactly when every non-dropped leaf under it is ticked or waived."""
    p = lint.parse(text)
    parents = [i for i in p["iscs"] if any(j.startswith(i + ".") for j in p["iscs"])]
    for parent in sorted(parents, key=lambda i: -i.count(".")):  # deepest first
        leaves = [j for j in p["leaves"] if j.startswith(parent + ".")]
        if not leaves:
            continue
        done = all(p["iscs"][j][0] or j in waived(p) for j in leaves)
        if done != p["iscs"][parent][0]:
            text = _set_box(text, parent, done)
            p = lint.parse(text)
    return text


def progress_of(text):
    p = lint.parse(text)
    done = sum(1 for i in p["counted"] if p["iscs"][i][0])
    return f"{done}/{len(p['counted'])}"


# ------------------------------------------------------------------ verification lines

def _section_span(text, name):
    """(start, end) of a `## name` section's body (after its heading line); fenced blocks ignored."""
    pos, start, in_fence = 0, None, False
    for line in text.splitlines(keepends=True):
        if line.startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            if start is not None:
                return start, pos
            if line[3:].strip() == name:
                start = pos + len(line)
        pos += len(line)
    return (start, len(text)) if start is not None else None


def set_verification(text, isc, line):
    """Replace the generated (or v1 `isa verify`) line of `isc` with `line`, or add it after the last ISC
    line of `## Verification` (the section is created at the end of the file when missing)."""
    span = _section_span(text, "Verification")
    if span is None:
        return text.rstrip("\n") + "\n\n## Verification\n\n" + line + "\n"
    s, e = span
    body = text[s:e].splitlines(keepends=True)
    for k, b in enumerate(body):
        m = GENERATED.match(b) or LEGACY.match(b)
        if m and m.group(1) == isc:
            body[k] = line + "\n"
            return text[:s] + "".join(body) + text[e:]
    last = max((k for k, b in enumerate(body) if b.startswith("- ISC-")), default=None)
    if last is not None:
        body.insert(last + 1, line + "\n")
    else:  # no ISC line yet: first item of the section, keeping a blank line around non-list text
        lead = 0
        while lead < len(body) and not body[lead].strip():
            lead += 1
        ins = ([] if lead else ["\n"]) + [line + "\n"]
        if lead < len(body) and not body[lead].startswith("- "):
            ins.append("\n")
        body[lead:lead] = ins
    return text[:s] + "".join(body) + text[e:]


def generated_lines(text):
    """{isc: line} for the engine-generated Verification lines (v1 `isa verify` lines included)."""
    span = _section_span(text, "Verification")
    out = {}
    if span:
        for b in text[span[0]:span[1]].splitlines():
            m = GENERATED.match(b) or LEGACY.match(b)
            if m:
                out[m.group(1)] = b
    return out


def drop_orphans(text):
    """Remove generated lines whose ISC is gone (dropped, renumbered, waived) or — for verified/attested
    lines — no longer ticked. A `regressed` line stays while its ISC is open: it says why."""
    span = _section_span(text, "Verification")
    if not span:
        return text
    p = lint.parse(text)
    s, e = span
    keep = []
    for b in text[s:e].splitlines(keepends=True):
        m = GENERATED.match(b) or LEGACY.match(b)
        if m:
            i = m.group(1)
            gone = i not in p["counted"]
            stale = m.group(2) in ("verified", "attested", "PASS") and not gone and not p["iscs"][i][0]
            if gone or stale:
                continue
        keep.append(b)
    body = "".join(keep)
    if not body.strip():  # only orphans were there: drop the section (sections never appear empty)
        head = text.rfind("## Verification", 0, s)
        return text[:head].rstrip("\n") + "\n" + text[e:]
    return text[:s] + body + text[e:]


def normalize(text):
    text = sync_parents(text)
    text = drop_orphans(text)
    if FM_BLOCK.match(text):
        text = fm_set(text, "progress", progress_of(text))
    return text


# ------------------------------------------------------------------ disk

def write_atomic(path, text):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".ISA.md.", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
