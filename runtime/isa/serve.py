"""`isa serve`: the session's spec or ISA rendered as HTML on a local web server, in the foreground until Ctrl+C.

Each request reads the file again (and the session again, so a spec followed by its ISA is followed too); the page
reloads itself when the file changes. Read only: the server writes nothing. The Markdown is the subset ISAs, specs
and plans use: headings, lists with checkboxes and `[n/m]` boxes, tables, fenced blocks, quotes, inline code,
emphasis and links. HTML comments are reader notes and are left out.
"""
import html
import http.server
import json
import os
import re
import sys

from . import doc, state, status

INLINE_CODE = re.compile(r"`([^`]+)`")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![\w*])[*_](?![\s*_])(.+?)(?<![\s*_])[*_](?![\w*])")
LIST = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
BOX = re.compile(r"^\[( |x|X|\d+/\d+)\]\s+")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)\s*([\w+-]*)")
ROW_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def inline(text):
    """One line of Markdown → HTML: code spans first (their text stays literal), then links and emphasis."""
    parts, out = INLINE_CODE.split(text), []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(f"<code>{html.escape(part)}</code>")
            continue
        s = html.escape(part, quote=False)
        s = LINK.sub(lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', s)
        s = BOLD.sub(r"<strong>\1</strong>", s)
        out.append(ITALIC.sub(r"<em>\1</em>", s))
    return "".join(out)


def _box(text):
    """A list item's leading `[ ]`, `[x]` or `[n/m]` → (css class, mark html, rest of the text)."""
    m = BOX.match(text)
    if not m:
        return "", "", text
    b, rest = m.group(1), text[m.end():]
    if b in (" ", "x", "X"):
        done = b != " "
        return ("done" if done else "open"), f'<span class="box">{"✓" if done else ""}</span>', rest
    n, total = (int(x) for x in b.split("/"))
    return ("done" if n == total else "open"), f'<span class="count">{n}/{total}</span>', rest


def _cells(line):
    line = line.strip()
    return [c.strip() for c in line.strip("|").split("|")]


def _table(rows):
    head, body = rows[0], rows[2:]
    out = ["<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in _cells(head)) + "</tr></thead><tbody>"]
    out += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in _cells(r)) + "</tr>" for r in body]
    return "\n".join(out + ["</tbody></table>"])


def _list(items):
    """[(indent, text)] → nested <ul>s; a deeper indent opens a sub-list in the item above it."""
    out, stack = [], []
    for indent, text in items:
        while stack and indent < stack[-1]:
            out.append("</li></ul>")
            stack.pop()
        if stack and indent == stack[-1]:
            out.append("</li>")
        else:
            out.append("<ul>")
            stack.append(indent)
        cls, mark, rest = _box(text)
        out.append(f'<li class="{cls}">{mark}<span>{inline(rest)}</span>' if cls else f"<li>{inline(rest)}")
    out += ["</li></ul>"] * len(stack)
    return "".join(out)


def body_html(body):
    """The Markdown body (no frontmatter) → HTML."""
    lines, out, i = doc.norm(body).split("\n"), [], 0
    para = []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        fence = FENCE.match(line)
        if fence:
            flush()
            j, code = i + 1, []
            while j < len(lines) and not lines[j].strip().startswith(fence.group(1)):
                code.append(lines[j])
                j += 1
            lang = f' class="lang-{fence.group(2)}"' if fence.group(2) else ""
            out.append(f"<pre><code{lang}>{html.escape(chr(10).join(code))}</code></pre>")
            i = j + 1
            continue
        if line.lstrip().startswith("<!--"):
            flush()
            while i < len(lines) and "-->" not in lines[i]:
                i += 1
            i += 1
            continue
        line = doc.COMMENT.sub("", line)
        if not line.strip():
            flush()
            i += 1
            continue
        h = HEADING.match(line)
        if h:
            flush()
            n = len(h.group(1))
            slug = re.sub(r"[^\w]+", "-", h.group(2).lower()).strip("-")
            out.append(f'<h{n} id="{slug}">{inline(h.group(2))}</h{n}>')
            i += 1
            continue
        if re.fullmatch(r"\s*([-*_])(\s*\1){2,}\s*", line):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < len(lines) and ROW_SEP.match(lines[i + 1]):
            flush()
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            out.append(_table(lines[i:j]))
            i = j
            continue
        if line.lstrip().startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + body_html("\n".join(quote)) + "</blockquote>")
            continue
        if LIST.match(line):
            flush()
            items = []
            while i < len(lines):
                m = LIST.match(lines[i])
                if m:
                    items.append([len(m.group(1).expandtabs(4)), m.group(2)])
                elif lines[i].strip() and lines[i][:1].isspace() and items:
                    items[-1][1] += " " + lines[i].strip()  # a continuation line of the item above
                else:
                    break
                i += 1
            out.append(_list(items))
            continue
        para.append(line.strip())
        i += 1
    flush()
    return "\n".join(out)


def page(path):
    """The whole HTML page of one spec, ISA or plan."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm, _, body = doc.split(text)
    title = fm.get("task") or doc.title(body) or os.path.basename(path)
    h1 = "" if doc.title(body) else f"<h1>{html.escape(str(title))}</h1>"
    meta = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(doc.fm_value(v))}</td></tr>"
                   for k, v in fm.items())
    return PAGE.format(title=html.escape(str(title)), h1=h1, path=html.escape(path), mtime=_mtime(path),
                       meta=f'<table class="meta">{meta}</table>' if meta else "", body=body_html(body))


def _mtime(path):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return 0


def _handler(resolve):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = resolve()
            route = self.path.split("?", 1)[0]
            if route == "/":
                if path:
                    self._send(200, "text/html; charset=utf-8", page(path))
                else:
                    self._send(404, "text/html; charset=utf-8", "<p>No spec or ISA bound to this session.</p>")
            elif route == "/version":
                self._send(200, "application/json", json.dumps({"path": path, "mtime": _mtime(path) if path else 0}))
            else:
                self._send(404, "text/plain; charset=utf-8", "not found")

        def _send(self, code, ctype, text):
            data = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # quiet: the terminal shows only the address
            pass

    return Handler


def _opt(args, name, default):
    if name in args and args.index(name) + 1 < len(args):
        return args[args.index(name) + 1]
    return default


def serve_cmd(args, harness=None, sid=None):
    """`isa serve [spec|isa|<file>] [--host H] [--port N]`: serve the file at the root until Ctrl+C."""
    host, port = _opt(args, "--host", "127.0.0.1"), _opt(args, "--port", "8765")
    if not port.isdigit():
        print("isa serve: --port takes a number", file=sys.stderr)
        return 2
    values = {_opt(args, o, None) for o in ("--host", "--port", "--session", "--harness")}
    files = [a for a in args if not a.startswith("-") and a not in values and a not in ("spec", "isa")]
    if files:
        fixed = os.path.abspath(files[0])
        if not os.path.isfile(fixed):
            print(f"isa serve: no file {files[0]}", file=sys.stderr)
            return 1
        resolve = lambda: fixed
    else:
        which = next((a for a in args if a in ("spec", "isa")), None)
        if not sid:
            harness, sid = status._session_of_project(os.getcwd())
        if not sid:
            print("isa serve: no session of this project (pass --session ID or a file)", file=sys.stderr)
            return 1
        resolve = lambda: status.target(state.read_session(harness or "claude", sid), which)
        if not resolve():
            print(f"isa serve: no {which or 'spec or ISA'} bound to session {sid}", file=sys.stderr)
            return 1
    try:
        server = http.server.ThreadingHTTPServer((host, int(port)), _handler(resolve))
    except OSError as e:
        print(f"isa serve: cannot listen on {host}:{port}: {e.strerror}", file=sys.stderr)
        return 1
    shown = f"[{host}]" if ":" in host else host
    print(f"isa serve: {resolve()}\n  http://{shown}:{server.server_address[1]}/  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nisa serve: stopped")
    finally:
        server.server_close()
    return 0


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg: #fbfaf7; --fg: #1f2328; --muted: #6a6f76; --line: #e3e0d8; --code: #f1eee7; --accent: #2f6f4f;
  --open: #9a6700; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #16181b; --fg: #e4e2dd; --muted: #9a9da3; --line: #2c2f34;
  --code: #202327; --accent: #6cc196; --open: #d6a64a; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 860px; margin: 0 auto; padding: 32px 16px 64px; }}
.path {{ color: var(--muted); font-size: 13px; word-break: break-all; }}
h1 {{ font-size: 28px; line-height: 1.25; margin: 8px 0 16px; }}
h2 {{ font-size: 20px; margin: 36px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--line); }}
h3, h4 {{ font-size: 17px; margin: 24px 0 8px; }}
a {{ color: var(--accent); }}
code, pre {{ font: 13.5px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
code {{ background: var(--code); padding: 1px 5px; border-radius: 4px; }}
pre {{ background: var(--code); padding: 12px 14px; border-radius: 8px; overflow-x: auto; }}
pre code {{ background: none; padding: 0; }}
table {{ border-collapse: collapse; margin: 12px 0; display: block; overflow-x: auto; }}
th, td {{ border: 1px solid var(--line); padding: 5px 10px; text-align: left; vertical-align: top; }}
table.meta {{ font-size: 13.5px; }}
table.meta th {{ color: var(--muted); font-weight: 500; }}
ul {{ padding-left: 22px; }}
li {{ margin: 3px 0; }}
li.done, li.open {{ list-style: none; margin-left: -22px; }}
li.done > ul, li.open > ul {{ margin-left: 22px; }}
li.done > span:not(.box):not(.count) {{ color: var(--muted); }}
.box {{ display: inline-block; width: 15px; height: 15px; border: 1.5px solid var(--open); border-radius: 3px;
  margin-right: 8px; vertical-align: -2px; font-size: 11px; line-height: 12px; text-align: center; }}
li.done > .box {{ border-color: var(--accent); background: var(--accent); color: var(--bg); }}
.count {{ font: 12px ui-monospace, monospace; color: var(--open); border: 1px solid currentColor; border-radius: 9px;
  padding: 0 6px; margin-right: 8px; }}
li.done > .count {{ color: var(--accent); }}
blockquote {{ margin: 12px 0; padding: 2px 14px; border-left: 3px solid var(--line); color: var(--muted); }}
hr {{ border: 0; border-top: 1px solid var(--line); margin: 24px 0; }}
</style></head>
<body><main>
<div class="path">{path}</div>
{h1}
{meta}
{body}
</main>
<script>
let seen = {mtime};
setInterval(async () => {{
  try {{
    const v = await (await fetch("/version", {{cache: "no-store"}})).json();
    if (v.mtime !== seen) location.reload();
  }} catch (e) {{}}
}}, 1000);
</script>
</body></html>
"""
