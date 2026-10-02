"""The gate's judge (SPEC-v2 § 1.2 and § 7). Standard library only.

    gate(prompt, context="", harness="claude", backend=None)
        → {"verdict": "yes"|"no", "reason": str, "source": "prefilter"|"judge"|"heuristic"|"error",
           "ms": int, "backend": str}

The free pre-filter (fit.prefilter) answers obvious prompts; only `unsure` reaches a backend:

    ISA_JUDGE   auto (default) | claude[:model] | pi[:provider/model] | api[:model] | heuristic
                auto = the harness's own CLI when it is on PATH, else heuristic; never api (a key in the
                environment is not consent to bill it from every session)

Failure policy: a backend that times out (ISA_JUDGE_TIMEOUT, default 12 s), exits non-zero or answers
something that isn't a verdict gives verdict yes, source error — if the gate can't decide, the session
is ON. A named CLI that isn't installed falls back to the heuristic (unsure → yes).
Advisory calls (`isa lint`'s probe_adequacy, `isa close`'s goal_met / asks_met) run in commands, not
hooks: they get ISA_ADVICE_TIMEOUT (default 60 s), and a failure there is only a note.

Every backend runs the judge isolated from the user's setup, and with ISA_JUDGE_CHILD=1 so the judge's
own session runs no ISA hook (engine.handle returns {} for it).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

from . import fit

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TIMEOUT = 12.0
DEFAULT_ADVICE_TIMEOUT = 60.0  # advisory calls run in `isa lint` / `isa close`, never in a hook
CONTEXT_CHARS = 2000
API_URL = "https://api.anthropic.com"
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "reason"],
          "properties": {"verdict": {"type": "string", "enum": ["yes", "no"]}, "reason": {"type": "string"}}}
ASKS_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["asks"],
               "properties": {"asks": {"type": "array", "items": {"type": "string"}}}}


class JudgeError(Exception):
    pass


def timeout():
    try:
        return float(os.environ.get("ISA_JUDGE_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        return DEFAULT_TIMEOUT


def advice_timeout():
    try:
        return float(os.environ.get("ISA_ADVICE_TIMEOUT") or DEFAULT_ADVICE_TIMEOUT)
    except ValueError:
        return DEFAULT_ADVICE_TIMEOUT


def backend_for(harness):
    want = (os.environ.get("ISA_JUDGE") or "auto").strip()
    if want and want != "auto":
        return want
    cli = "pi" if harness == "pi" else "claude"
    return cli if shutil.which(cli) else "heuristic"


def render(name, **values):
    with open(os.path.join(HERE, f"{name}.md"), encoding="utf-8") as f:
        text = f.read()
    for k, v in values.items():
        text = text.replace("{" + k + "}", v if v else "(none)")
    return text


def _child_env():
    env = dict(os.environ)
    env.update(ISA_JUDGE_CHILD="1", ENABLE_CLAUDEAI_MCP_SERVERS="false")
    return env


def _ask_claude(model, text, limit, schema=SCHEMA):
    argv = ["claude", "-p", "--model", model or DEFAULT_CLAUDE_MODEL, "--output-format", "json",
            "--json-schema", json.dumps(schema), "--tools", "", "--setting-sources", "project",
            "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"]
    with tempfile.TemporaryDirectory(prefix="isa-judge-") as d:
        r = subprocess.run(argv, input=text, cwd=d, env=_child_env(), capture_output=True, text=True,
                           timeout=limit)
    if r.returncode != 0:
        raise JudgeError(f"claude exited {r.returncode}")
    try:
        out = json.loads(r.stdout)
    except ValueError:
        return r.stdout
    if isinstance(out, dict):
        if isinstance(out.get("structured_output"), dict):
            return json.dumps(out["structured_output"])
        return str(out.get("result") or "")
    return r.stdout


def _ask_pi(model, text, limit, schema=None):
    model = model or os.environ.get("ISA_JUDGE_PI_MODEL")
    argv = ["pi", "-p", "--mode", "json", "--no-session", "--no-extensions", "--no-skills", "--no-context-files",
            "--no-tools"] + (["--model", model] if model else []) + ["--", text]
    with tempfile.TemporaryDirectory(prefix="isa-judge-") as d:
        r = subprocess.run(argv, cwd=d, env=_child_env(), capture_output=True, text=True, timeout=limit,
                           stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise JudgeError(f"pi exited {r.returncode}")
    answer = ""
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        msg = ev.get("message") if isinstance(ev, dict) and ev.get("type") == "message_end" else None
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            answer = "".join(c.get("text", "") for c in msg.get("content") or []
                             if isinstance(c, dict) and c.get("type") == "text") or answer
    return answer


def _ask_api(model, text, limit, schema=None):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise JudgeError("ANTHROPIC_API_KEY is not set")
    url = (os.environ.get("ANTHROPIC_BASE_URL") or API_URL).rstrip("/") + "/v1/messages"
    body = {"model": model or DEFAULT_CLAUDE_MODEL, "max_tokens": 300,
            "system": "Answer with one JSON object and nothing else.",
            "messages": [{"role": "user", "content": text}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=limit) as resp:
            out = json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise JudgeError(f"api: {e}")
    return "".join(c.get("text", "") for c in out.get("content") or [] if isinstance(c, dict))


ASK = {"claude": _ask_claude, "pi": _ask_pi, "api": _ask_api}


def parse_verdict(text):
    """{"verdict", "reason"} from a backend's answer; JudgeError when it isn't a yes/no verdict."""
    candidates = [text] + re.findall(r"\{[^{}]*\}", text or "")
    for c in candidates:
        try:
            d = json.loads(c)
        except (ValueError, TypeError):
            continue
        if isinstance(d, dict) and str(d.get("verdict", "")).strip().lower() in ("yes", "no"):
            return {"verdict": str(d["verdict"]).strip().lower(), "reason": str(d.get("reason") or "").strip()}
    raise JudgeError("answer is not a yes/no verdict")


def ask(question, backend, **values):
    """Render `question`'s template and return the backend's parsed verdict (JudgeError on failure)."""
    name, _, model = backend.partition(":")
    if name not in ASK:
        raise JudgeError(f"unknown backend `{name}`")
    try:
        return parse_verdict(ASK[name](model, render(question, **values), timeout()))
    except subprocess.TimeoutExpired:
        raise JudgeError(f"{name} timed out after {timeout():g}s")
    except OSError as e:
        raise JudgeError(f"{name}: {e}")


def gate(prompt, context="", harness="claude", backend=None):
    t0 = time.time()

    def done(verdict, reason, source, spec):
        return {"verdict": verdict, "reason": reason, "source": source, "ms": int((time.time() - t0) * 1000),
                "backend": spec}

    pre, why = fit.prefilter(prompt)
    if pre != "unsure":
        return done(pre, why, "prefilter", "prefilter")
    spec = backend or backend_for(harness)
    name = spec.partition(":")[0]
    if name == "heuristic":
        return done("yes", f"{why}; no judge configured, so ON", "heuristic", spec)
    if name in ("claude", "pi") and not shutil.which(name):
        v = done("yes", f"{why}; `{name}` is not installed, so ON", "heuristic", spec)
        v["note"] = f"ISA judge `{name}` not found on PATH — the gate uses the heuristic pre-filter"
        return v
    try:
        d = ask("gate", spec, prompt=prompt, context=context or "")
    except JudgeError as e:
        return done("yes", f"judge unavailable ({e})", "error", spec)
    return done(d["verdict"], d["reason"] or "judged", "judge", spec)


ADEQ_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdicts"],
               "properties": {"verdicts": {"type": "array", "items": {
                   "type": "object", "required": ["isc", "verdict", "reason"],
                   "properties": {"isc": {"type": "string"}, "verdict": {"type": "string", "enum": ["yes", "no"]},
                                  "reason": {"type": "string"}}}}}}


def structured(template, schema, key, harness=None, backend=None, advisory=False, **values):
    """Ask a template whose answer is a JSON object holding `key`. → (object or None, status) with status
    ok | off (ISA_ADVICE=off, advisory calls only) | none (no judge available) | error."""
    if advisory and (os.environ.get("ISA_ADVICE") or "on").strip().lower() in ("off", "0", "no", "false"):
        return None, "off"
    spec = backend or backend_for(harness or os.environ.get("ISA_HARNESS") or "claude")
    name, _, model = spec.partition(":")
    if name not in ASK or (name in ("claude", "pi") and not shutil.which(name)):
        return None, "none"
    try:
        text = ASK[name](model, render(template, **values), advice_timeout() if advisory else timeout(), schema=schema)
    except (subprocess.TimeoutExpired, OSError, JudgeError):
        return None, "error"
    for c in [text] + re.findall(r"\{.*\}", text or "", re.S):
        try:
            d = json.loads(c)
        except (ValueError, TypeError):
            continue
        if isinstance(d, dict) and key in d:
            return d, "ok"
    return None, "error"


def extract_asks(prompt, context="", harness=None, backend=None):
    """The explicit asks of a prompt as verbatim spans (template judge/asks_extract.md), or None when no
    judge is available or it fails — the caller then leaves `asks:` for the model to write."""
    d, _ = structured("judge/asks_extract", ASKS_SCHEMA, "asks", harness=harness, backend=backend,
                      prompt=prompt, context=context or "")
    if not d or not isinstance(d.get("asks"), list):
        return None
    return [str(a).strip() for a in d["asks"] if str(a).strip()]


# ------------------------------------------------------------------ context

def last_assistant_text(transcript_path, limit=CONTEXT_CHARS):
    """The tail of the last assistant text in a Claude Code transcript (JSONL); "" when unreadable."""
    if not transcript_path:
        return ""
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            f.seek(max(0, size - 1_000_000))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if not isinstance(m, dict) or m.get("type") != "assistant":
            continue
        content = (m.get("message") or {}).get("content")
        if isinstance(content, str):
            text = content
        else:
            text = "\n".join(c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")
        if text.strip():
            return text[-limit:]
    return ""
