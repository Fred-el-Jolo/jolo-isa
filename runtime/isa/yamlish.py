"""The YAML subset ISA files use, read with the standard library only.

Supported: block mappings, block lists of scalars or mappings, flow lists of
scalars (`[a, b]`), plain / single- / double-quoted scalars, `|` `|-` `>` `>-`
block scalars, comments, and int / float / bool / null plain scalars.
Not supported (raises YamlError): anchors, tags, flow mappings, multi-document
streams, complex keys. That is enough for frontmatter, `## Test Strategy` and
`## Features`; anything fancier is a format error in an ISA anyway.
"""
import re

__all__ = ["load", "YamlError"]


class YamlError(ValueError):
    pass


_INT = re.compile(r"^[-+]?(0|[1-9][0-9_]*)$")
_FLOAT = re.compile(r"^[-+]?(\.[0-9]+|[0-9][0-9_]*(\.[0-9]*)?)([eE][-+]?[0-9]+)?$")
_KEY = re.compile(r"^([^\s'\"#\[\]{},&*!|>%@`][^:#]*?|'[^']*'|\"[^\"]*\")\s*:(\s+|$)")


def _strip_comment(s):
    """Drop a trailing ` # comment` that sits outside quotes."""
    out, q = [], None
    for i, c in enumerate(s):
        if q:
            if c == q:
                if q == "'" and i + 1 < len(s) and s[i + 1] == "'":
                    pass
                else:
                    q = None
        elif c in "'\"" and (i == 0 or s[i - 1] in " \t[,"):
            q = c
        elif c == "#" and (i == 0 or s[i - 1] in " \t"):
            return "".join(out).rstrip()
        out.append(c)
    return "".join(out).rstrip()


def _scalar(tok, line_no):
    tok = tok.strip()
    if tok == "":
        return None
    if tok[0] == "'":
        if len(tok) < 2 or tok[-1] != "'":
            raise YamlError(f"line {line_no}: unterminated single-quoted string")
        return tok[1:-1].replace("''", "'")
    if tok[0] == '"':
        if len(tok) < 2 or tok[-1] != '"':
            raise YamlError(f"line {line_no}: unterminated double-quoted string")
        body = tok[1:-1]
        esc = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/", "0": "\0", "r": "\r"}
        out, i = [], 0
        while i < len(body):
            c = body[i]
            if c == "\\" and i + 1 < len(body):
                n = body[i + 1]
                if n in esc:
                    out.append(esc[n]); i += 2; continue
                if n == "u" and i + 5 < len(body):
                    out.append(chr(int(body[i + 2:i + 6], 16))); i += 6; continue
                if n == "x" and i + 3 < len(body):
                    out.append(chr(int(body[i + 2:i + 4], 16))); i += 4; continue
                raise YamlError(f"line {line_no}: unknown escape \\{n}")
            out.append(c); i += 1
        return "".join(out)
    if tok[0] in "&*!{%@`":
        raise YamlError(f"line {line_no}: unsupported YAML construct `{tok[:20]}`")
    if tok[0] in "|>":
        raise YamlError(f"line {line_no}: block scalar indicator in an unexpected place")
    if tok[0] == "[":
        return _flow_list(tok, line_no)
    if ": " in tok or tok.endswith(":"):
        raise YamlError(f"line {line_no}: mapping values are not allowed here: `{tok[:40]}`")
    low = tok.lower()
    if low in ("null", "~"):
        return None
    if low in ("true", "false"):
        return low == "true"
    if _INT.match(tok):
        return int(tok.replace("_", ""))
    if _FLOAT.match(tok) and any(ch.isdigit() for ch in tok):
        return float(tok.replace("_", ""))
    return tok


def _flow_list(tok, line_no):
    if not tok.endswith("]"):
        raise YamlError(f"line {line_no}: unterminated flow list")
    inner = tok[1:-1].strip()
    if not inner:
        return []
    items, cur, q = [], [], None
    for c in inner:
        if q:
            cur.append(c)
            if c == q:
                q = None
        elif c in "'\"":
            q = c; cur.append(c)
        elif c == ",":
            items.append("".join(cur)); cur = []
        elif c in "[]{}":
            raise YamlError(f"line {line_no}: nested flow collections are not supported")
        else:
            cur.append(c)
    items.append("".join(cur))
    return [_scalar(x, line_no) for x in items if x.strip() != "" or len(items) == 1]


class _Parser:
    def __init__(self, text):
        self.lines = []
        for n, raw in enumerate(text.split("\n"), 1):
            if "\t" in raw[: len(raw) - len(raw.lstrip())]:
                raise YamlError(f"line {n}: tab in indentation")
            self.lines.append((n, raw))
        self.i = 0

    # -- helpers
    def _skip_blank(self):
        while self.i < len(self.lines):
            s = self.lines[self.i][1].strip()
            if s == "" or s.startswith("#"):
                self.i += 1
            else:
                return

    def _peek(self):
        self._skip_blank()
        if self.i >= len(self.lines):
            return None
        n, raw = self.lines[self.i]
        return n, len(raw) - len(raw.lstrip(" ")), raw.strip()

    # -- grammar
    def parse(self):
        p = self._peek()
        if p is None:
            return None
        n, ind, content = p
        val = self._node(ind)
        if self._peek() is not None:
            n, _, content = self._peek()
            raise YamlError(f"line {n}: unexpected content `{content[:40]}`")
        return val

    def _node(self, ind):
        n, cur, content = self._peek()
        if content.startswith("- ") or content == "-":
            return self._list(cur)
        if _KEY.match(content):
            return self._map(cur)
        self.i += 1
        return _scalar(_strip_comment(content), n)

    def _list(self, ind):
        out = []
        while True:
            p = self._peek()
            if p is None:
                return out
            n, cur, content = p
            if cur < ind:
                return out
            if cur > ind:
                raise YamlError(f"line {n}: bad indentation in list")
            if not (content.startswith("- ") or content == "-"):
                return out
            rest = content[1:].lstrip(" ")
            item_ind = cur + (len(content) - len(rest))
            if rest == "" or rest.startswith("#"):
                self.i += 1
                p2 = self._peek()
                out.append(self._node(p2[1]) if p2 and p2[1] > cur else None)
            elif _KEY.match(rest):
                # mapping starting on the dash line: rewrite the line as its own block
                raw_n, _ = self.lines[self.i]
                self.lines[self.i] = (raw_n, " " * item_ind + rest)
                out.append(self._map(item_ind))
            else:
                self.i += 1
                out.append(self._inline_value(rest, n, cur))
        return out

    def _map(self, ind):
        out = {}
        while True:
            p = self._peek()
            if p is None:
                return out
            n, cur, content = p
            if cur < ind:
                return out
            if cur > ind:
                raise YamlError(f"line {n}: bad indentation in mapping")
            m = _KEY.match(content)
            if not m:
                if content.startswith("- "):
                    return out
                raise YamlError(f"line {n}: expected `key: value`, got `{content[:40]}`")
            key = _scalar(m.group(1), n)
            if key in out:
                raise YamlError(f"line {n}: duplicate key `{key}`")
            rest = content[m.end():]
            self.i += 1
            stripped = _strip_comment(rest)
            if stripped == "":
                p2 = self._peek()
                if p2 and (p2[1] > cur or (p2[1] == cur and p2[2].startswith("- "))):
                    out[key] = self._node(p2[1])
                else:
                    out[key] = None
            else:
                out[key] = self._inline_value(stripped, n, cur)
        return out

    def _inline_value(self, tok, n, parent_ind):
        tok = _strip_comment(tok)
        if tok[:1] in "|>" and re.match(r"^[|>][-+]?$", tok):
            return self._block_scalar(tok, parent_ind)
        return _scalar(tok, n)

    def _block_scalar(self, indicator, parent_ind):
        folded, chomp = indicator[0] == ">", indicator[1:2]
        body, block_ind = [], None
        while self.i < len(self.lines):
            n, raw = self.lines[self.i]
            if raw.strip() == "":
                body.append(""); self.i += 1; continue
            ind = len(raw) - len(raw.lstrip(" "))
            if block_ind is None:
                if ind <= parent_ind:
                    break
                block_ind = ind
            if ind < block_ind:
                break
            body.append(raw[block_ind:]); self.i += 1
        while body and body[-1] == "":
            body.pop()
            if chomp == "+":
                break
        if folded:
            text, prev_blank = "", True
            for ln in body:
                if ln == "":
                    text += "\n"; prev_blank = True
                else:
                    text += ("" if prev_blank or text.endswith("\n") else " ") + ln
                    prev_blank = False
        else:
            text = "\n".join(body)
        return text + ("" if chomp == "-" or not body else "\n")


def load(text):
    """Parse `text` as the ISA YAML subset. Raises YamlError on anything else."""
    return _Parser(text).parse()
