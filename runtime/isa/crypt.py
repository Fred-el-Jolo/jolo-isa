"""Encrypting the user's verbatim words in a repo's committed ISAs (SPEC-v2 § 13.5–13.8). Stdlib + `openssl`.

Files on disk stay plain; a git clean/smudge filter (`isa crypt clean|smudge|process`) encrypts on the
way into git and decrypts on the way out. Only the quoting forms of quotes.py are touched, in place,
byte for byte: `smudge(clean(text)) == text`.

    key() → bytes | None              ISA_KEY (base64) or $ISA_HOME/key
    keyid(key) → 8 hex
    encrypt(raw, key) → "enc:v1:<keyid>:<b64url(iv ‖ ct ‖ tag)>"     deterministic (SIV-like)
    decrypt(token, key) → raw | None   None: another key, or a tag that doesn't verify
    clean(text, key) / smudge(text, key) → text
    tag(text, key) → "hmac:v1:<keyid>:<hex>"   a keyed fingerprint (asks snapshot, quote-verified rows)

The raw text encrypted is the value exactly as written in the file (quotes and escapes included), so
decrypting restores the very bytes. The key is never put on a command line.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
import subprocess
import sys
import tempfile

from . import lint, quotes, state

TOKEN = re.compile(r"enc:v1:([0-9a-f]{8}):([A-Za-z0-9_-]+)")
FM_BLOCK = re.compile(r"\A---\n(.*?\n)---\n", re.S)


# ------------------------------------------------------------------ the key

def key_path():
    return os.path.join(state.home(), "key")


def key():
    raw = os.environ.get("ISA_KEY")
    if not raw:
        try:
            with open(key_path()) as f:
                raw = f.read()
        except OSError:
            return None
    try:
        k = base64.b64decode(raw.strip(), validate=True)
    except ValueError:
        return None
    return k if len(k) == 32 else None


def keyid(k):
    return hashlib.sha256(k).hexdigest()[:8]


def new_key():
    return secrets.token_bytes(32)


def save_key(k):
    os.makedirs(state.home(), exist_ok=True)
    tmp = key_path() + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(base64.b64encode(k).decode() + "\n")
    os.replace(tmp, key_path())


def _sub(k, label):
    return hmac.new(k, label.encode(), hashlib.sha256).digest()


def tag(text, k):
    return f"hmac:v1:{keyid(k)}:{hmac.new(_sub(k, 'tag'), text.encode(), hashlib.sha256).hexdigest()[:32]}"


# ------------------------------------------------------------------ the cipher

def _openssl(data, k_enc, iv, decrypt=False):
    with tempfile.NamedTemporaryFile("w", delete=False, prefix="isa-k-") as f:
        os.chmod(f.name, 0o600)
        f.write(k_enc.hex())
        kfile = f.name
    try:
        r = subprocess.run(["openssl", "enc", "-aes-256-ctr", *(["-d"] if decrypt else []), "-pass", f"file:{kfile}",
                            "-pbkdf2", "-iter", "1", "-md", "sha256", "-nosalt", "-iv", iv.hex()],
                           input=data, capture_output=True, timeout=10)
    finally:
        os.unlink(kfile)
    if r.returncode != 0:
        raise RuntimeError("openssl failed: " + r.stderr.decode(errors="replace").strip()[:200])
    return r.stdout


def encrypt(raw, k):
    data = raw.encode()
    iv = hmac.new(_sub(k, "iv"), data, hashlib.sha256).digest()[:16]
    ct = _openssl(data, _sub(k, "enc"), iv)
    mac = hmac.new(_sub(k, "mac"), iv + ct, hashlib.sha256).digest()[:16]
    return f"enc:v1:{keyid(k)}:" + base64.urlsafe_b64encode(iv + ct + mac).decode().rstrip("=")


def decrypt(token, k):
    m = TOKEN.fullmatch(token)
    if not m or m.group(1) != keyid(k):
        return None
    blob = base64.urlsafe_b64decode(m.group(2) + "=" * (-len(m.group(2)) % 4))
    iv, ct, mac = blob[:16], blob[16:-16], blob[-16:]
    if not hmac.compare_digest(mac, hmac.new(_sub(k, "mac"), iv + ct, hashlib.sha256).digest()[:16]):
        return None
    return _openssl(ct, _sub(k, "enc"), iv, decrypt=True).decode()


# ------------------------------------------------------------------ where the user's words are (raw)

def _flow_items(s):
    """(start, end) of each element of a YAML flow list body `"a", 'b', c` — quotes kept in the range."""
    out, i, n = [], 0, len(s)
    while i < n:
        while i < n and s[i] in " ,":
            i += 1
        if i >= n:
            break
        start = i
        if s[i] in "\"'":
            q, i = s[i], i + 1
            while i < n and s[i] != q:
                i += 2 if s[i] == "\\" and q == '"' else 1
            i += 1
        else:
            while i < n and s[i] != ",":
                i += 1
        end = i
        while end > start and s[end - 1] == " ":
            end -= 1
        out.append((start, end))
    return out


def _unquote(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        inner = raw[1:-1]
        return inner.replace('\\"', '"').replace("\\\\", "\\") if raw[0] == '"' else inner.replace("''", "'")
    return raw


def ranges(text):
    """[(start, end)] of every raw span to encrypt: frontmatter `stated_goal` and `asks` values, the Goal's
    opening quote of the `stated_goal`, `anchors_to:` values equal to one of those spans, and the quoted
    span of every body form (quotes.py). Ranges are absolute offsets into `text`, non-overlapping."""
    out, words = [], set()
    m = FM_BLOCK.match(text)
    fm_end = m.end() if m else 0
    if m:
        off = m.start(1)
        lines = m.group(1).split("\n")
        pos, in_asks = off, False
        for line in lines:
            mm = re.match(r"(stated_goal|asks):[ \t]*(.*)$", line)
            if mm:
                in_asks = mm.group(1) == "asks" and not mm.group(2).strip()
                val_start = pos + mm.start(2)
                val = mm.group(2).rstrip()
                if mm.group(1) == "stated_goal" and val and val not in ("null", "~"):
                    out.append((val_start, val_start + len(val)))
                    words.add(_unquote(val))
                elif mm.group(1) == "asks" and val.startswith("[") and val.endswith("]"):
                    for a, b in _flow_items(val[1:-1]):
                        out.append((val_start + 1 + a, val_start + 1 + b))
                        words.add(_unquote(val[1 + a:1 + b]))
            elif in_asks and re.match(r"\s+-\s+\S", line):
                im = re.match(r"(\s+-\s+)(.*?)\s*$", line)
                out.append((pos + im.end(1), pos + im.end(2)))
                words.add(_unquote(im.group(2)))
            elif not line.startswith((" ", "\t")):
                in_asks = False
            pos += len(line) + 1
    goal = next((w for w in [_unquote(v) for v in re.findall(r"^stated_goal:[ \t]*(.+)$", m.group(1), re.M)]
                 if w not in ("null", "~", "")), None) if m else None
    body = text[fm_end:]
    if goal and not goal.startswith("enc:v1:"):
        gm = re.search(r"^## Goal\n+(.*)$", body, re.M)
        if gm and goal in gm.group(1):
            s = fm_end + gm.start(1) + gm.group(1).index(goal)
            out.append((s, s + len(goal)))
    words = {w for w in words if w and not w.startswith("enc:v1:")}
    pos = fm_end
    for line in body.split("\n"):
        for a, b in quotes.body_forms(line):
            out.append((pos + a, pos + b))
        am = re.match(r"(\s*(?:-\s+)?anchors_to:[ \t]*)(.+?)\s*$", line)
        if am and _unquote(am.group(2)) in words:
            out.append((pos + am.end(1), pos + am.end(1) + len(am.group(2))))
        pos += len(line) + 1
    out = sorted(set(out))
    merged = []
    for a, b in out:
        if merged and a < merged[-1][1]:
            continue
        merged.append((a, b))
    return merged


def _token_raw(raw):
    """The token inside a value written as `"enc:v1:…"` (or bare), or None."""
    m = TOKEN.fullmatch(raw.strip().strip('"'))
    return m.group(0) if m else None


def clean(text, k):
    """Every plain span → an `enc:v1:` token. A whole YAML value (frontmatter, `anchors_to:`, a bare Goal
    literal) becomes `"<token>"`; a span inside a body quote becomes `<token>` between the quotes it had.
    The encrypted text carries a one-letter flag (V: whole value, Q: inside quotes) so `smudge` restores
    the exact bytes. Spans already encrypted pass through. Raises KeyError when a span needs a key."""
    out, last = [], 0
    for a, b in ranges(text):
        raw = text[a:b]
        if _token_raw(raw):
            continue
        if k is None:
            raise KeyError("no key")
        inside = a > 0 and text[a - 1] == '"' and b < len(text) and text[b] == '"'
        tok = encrypt(("Q" if inside else "V") + raw, k)
        out.append(text[last:a] + (tok if inside else f'"{tok}"'))
        last = b
    return "".join(out) + text[last:]


def smudge(text, k):
    """Every `enc:v1:` token this key can open → the exact bytes it replaced. Others stay as they are."""
    if k is None:
        return text
    out, last = [], 0
    for m in TOKEN.finditer(text):
        raw = decrypt(m.group(0), k)
        if raw is None or raw[:1] not in ("V", "Q"):
            continue
        a, b = m.start(), m.end()
        if raw[0] == "V" and a > 0 and text[a - 1] == '"' and b < len(text) and text[b] == '"':
            a, b = a - 1, b + 1  # the quotes `clean` added around a whole value
        out.append(text[last:a] + raw[1:])
        last = b
    return "".join(out) + text[last:]


def plain_spans(text):
    """The spans of `text` that are not encrypted yet (a commit without a key must refuse these)."""
    return [text[a:b] for a, b in ranges(text) if not _token_raw(text[a:b])]


# ------------------------------------------------------------------ git filter driver

NO_KEY = ("no key for this repo's ISA prompts — run `isa key import FILE` (the key exported on another machine) or "
          "`isa key new` (a new key; prompts encrypted under another key stay unreadable). Both are safe to type "
          "as `! isa key …` inside Claude Code.")


def filter_cmd(argv):
    """`isa crypt clean|smudge [PATH]`: stdin → stdout. `isa crypt process`: git's long-running protocol."""
    mode = argv[0] if argv else ""
    if mode == "process":
        return _process()
    data = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
    try:
        out = clean(data, key()) if mode == "clean" else smudge(data, key()) if mode == "smudge" else None
    except KeyError:
        print(f"isa crypt: {NO_KEY}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"isa crypt: {e}", file=sys.stderr)
        return 1
    if out is None:
        print("usage: isa crypt clean|smudge|process [PATH]", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(out.encode("utf-8", "surrogateescape"))
    return 0


def _pkt_read(f):
    head = f.read(4)
    if not head:
        return None
    n = int(head, 16)
    return b"" if n == 0 else f.read(n - 4)


def _pkt_write(f, data):
    f.write(b"%04x" % (len(data) + 4) + data)


def _flush(f):
    f.write(b"0000")
    f.flush()


def _pkt_text(f):
    lines = []
    while True:
        p = _pkt_read(f)
        if p is None:
            return None
        if p == b"":
            return lines
        lines.append(p.decode().rstrip("\n"))


def _process():
    inp, out = sys.stdin.buffer, sys.stdout.buffer
    hello = _pkt_text(inp)
    if not hello or "git-filter-client" not in hello:
        return 1
    _pkt_write(out, b"git-filter-server\n")
    _pkt_write(out, b"version=2\n")
    _flush(out)
    _pkt_text(inp)  # capabilities offered
    _pkt_write(out, b"capability=clean\n")
    _pkt_write(out, b"capability=smudge\n")
    _flush(out)
    k = key()
    while True:
        meta = _pkt_text(inp)
        if meta is None:
            return 0
        cmd = next((x.split("=", 1)[1] for x in meta if x.startswith("command=")), "")
        chunks = []
        while True:
            p = _pkt_read(inp)
            if not p:
                break
            chunks.append(p)
        text = b"".join(chunks).decode("utf-8", "surrogateescape")
        try:
            res = clean(text, k) if cmd == "clean" else smudge(text, k)
            status = b"success"
        except (KeyError, RuntimeError) as e:
            print(f"isa crypt: {NO_KEY if isinstance(e, KeyError) else e}", file=sys.stderr)
            res, status = None, b"error"
        _pkt_write(out, b"status=" + status + b"\n")
        _flush(out)
        if res is not None:
            data = res.encode("utf-8", "surrogateescape")
            for i in range(0, len(data), 65516):
                _pkt_write(out, data[i:i + 65516])
            _flush(out)
            _flush(out)  # keep status=success


# ------------------------------------------------------------------ repo setup

ATTRIBUTES = [".isa/**/*.md filter=isa", ".isa/**/evidence.jsonl merge=union"]


def launcher():
    return os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "isa"))


def _git(repo, *args):
    try:
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None


def setup_repo(repo, out=print):
    """First touch of a repo (SPEC-v2 § 13.1, § 13.6): `.gitattributes` lines, the filter in the clone's
    local git config, a warning when `.isa/` is ignored, then re-checkout of unmodified encrypted files."""
    path = os.path.join(repo, ".gitattributes")
    try:
        with open(path) as f:
            have = f.read()
    except OSError:
        have = ""
    missing = [a for a in ATTRIBUTES if a not in have.splitlines()]
    if missing:
        with open(path, "a") as f:
            f.write(("" if not have or have.endswith("\n") else "\n") + "\n".join(missing) + "\n")
    r = _git(repo, "rev-parse", "--is-inside-work-tree")
    if not r or r.returncode != 0:
        return  # not a usable git repo (a bare `.git` folder): nothing to register
    exe = launcher()
    want = {"filter.isa.clean": f"{exe} crypt clean %f", "filter.isa.smudge": f"{exe} crypt smudge %f",
            "filter.isa.process": f"{exe} crypt process", "filter.isa.required": "true"}
    fresh = False
    for k_, v in want.items():
        cur = _git(repo, "config", "--local", "--get", k_)
        if not cur or cur.stdout.strip() != v:
            _git(repo, "config", "--local", k_, v)
            fresh = True
    ig = _git(repo, "check-ignore", "-q", ".isa/x/ISA.md")
    if ig and ig.returncode == 0:
        out("isa: warning — `.isa/` is gitignored in this repo, so its ISAs will never be committed")
    if fresh:
        ls = _git(repo, "ls-files", "-z", "--", ".isa")
        for rel in (ls.stdout.split("\0") if ls and ls.returncode == 0 else []):
            p = os.path.join(repo, rel)
            if not rel.endswith(".md") or not os.path.isfile(p):
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    if "enc:v1:" not in f.read():
                        continue
            except OSError:
                continue
            d = _git(repo, "diff", "--quiet", "--", rel)
            if d and d.returncode == 0:  # unmodified: git won't rewrite it, so remove it and check it out again
                os.remove(p)
                _git(repo, "checkout", "--", rel)


def ensure_filter(repo):
    """Register the filter in a clone that lacks it (a fresh clone: § 13.6). → True when it did."""
    r = _git(repo, "config", "--local", "--get", "filter.isa.process")
    if r is not None and r.returncode == 0 and r.stdout.strip():
        return False
    if not os.path.exists(os.path.join(repo, ".gitattributes")):
        return False
    setup_repo(repo, out=lambda *_: None)
    return True


def unreadable(text, k):
    """Key ids of `enc:v1:` values this key can't open (another key, or none)."""
    ids = {m.group(1) for m in TOKEN.finditer(text)}
    return sorted(ids - ({keyid(k)} if k else set()))


def lint_project(text):
    """Quoting forms are refused in a project ISA (§ 13.5): → their offending lines."""
    bad = []
    for line in text.splitlines():
        if quotes.body_forms(line):
            bad.append(line.strip()[:80])
    fm = lint.parse(text)["fm"]
    if fm.get("stated_goal") or fm.get("asks"):
        bad.append("frontmatter `stated_goal` / `asks`")
    return bad
