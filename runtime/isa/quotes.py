"""The user's verbatim words in an ISA (SPEC-v2 § 13.5): where they may appear, and where they are.

An ISA holds the user's words only in these forms — and exactly these are encrypted in git
(crypt.py) and redacted from the ledger (evidence.py):

    frontmatter `stated_goal`                      the value
    frontmatter `asks`                             each entry
    `## Goal`                                      the opening quote of the `stated_goal` literal
    `waived: ISC-N — "<words>"`                    a waiver's quote (§ 6.5)
    `stated_goal null — candidate: "<literal>"`    Scaffold's rejected candidate
    `user: "<words>"`                              every other quote of the user

In the body forms the quoted span runs to the next `"` not preceded by a backslash; one form per line.

    spans(text) → [str]          the verbatim spans present (unescaped), longest first
    body_forms(line) → [(start, end)]   character ranges of the quoted spans of the body forms on one line
"""
import re

from . import lint

# the opening `"` of each body form; the span runs to the next unescaped `"`
BODY_FORM = re.compile(r'(?:\bwaived: ISC-\d+(?:\.\d+)* — |\bstated_goal null — candidate: |\buser: )"')


def _close(line, start):
    """Index of the closing `"` of a span starting at `start`, or -1."""
    i = start
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == '"':
            return i
        i += 1
    return -1


def body_forms(line):
    out = []
    for m in BODY_FORM.finditer(line):
        start = m.end()
        end = _close(line, start)
        if end > start:
            out.append((start, end))
    return out


def unescape(s):
    return s.replace('\\"', '"')


def spans(text):
    """Every verbatim user span the ISA holds, longest first (so a redaction never splits a longer one)."""
    p = lint.parse(text)
    fm = p["fm"]
    found = []
    if isinstance(fm.get("stated_goal"), str) and fm["stated_goal"].strip():
        found.append(fm["stated_goal"])
    if isinstance(fm.get("asks"), list):
        found += [str(a) for a in fm["asks"] if str(a).strip()]
    for line in text.splitlines():
        found += [unescape(line[a:b]) for a, b in body_forms(line)]
    uniq = {s for s in found if s and not s.startswith("enc:v1:")}
    return sorted(uniq, key=len, reverse=True)


def redact(value, words, mark="[user words]"):
    """`value` with every span in `words` replaced by `mark`."""
    if not isinstance(value, str) or not value:
        return value
    for w in words:
        if w and w in value:
            value = value.replace(w, mark)
    return value
