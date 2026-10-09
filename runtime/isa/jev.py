"""Jev judgments through the user's jev-kit CLI (SPEC-v2 § 11): on by default, bounded, add-only.

    ask(preset, payload, deadline, **ctx) → {"served", "answer", "answers", "reason", "detail", "ms"}
    ask_many([(preset, payload), …], deadline, **ctx) → the same, in order, run in parallel
    ask_adhoc(state, {id: question}, deadline, **ctx) → the same, one `jev ask` request of many questions

The engine runs `jev run <preset> --consumer isa` (`ISA_JEV_BIN`, default `jev`) with this folder's
presets first on `JEV_KIT_PRESETS`, the payload as JSON on stdin, and kills the call at its own
deadline (1.5 s in hooks, 3 s in commands) — whatever jev-kit's breaker thinks. jev-kit never answers
in Jev's place: not served is a non-zero exit with `{"ok": false, "unavailable": {reason, detail}}`.
This module never retries and never decides anything itself; callers apply the answer add-only.
`"jev": false` in ~/.isa/config.json, or no `jev` CLI, means no call at all.
Every call writes a `jev` row to the debug log. `message(result)` is the one line the user sees when a
call was not served (credit, budget, anything else).
"""
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from . import config, logs

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = os.path.join(HERE, "jev")
HOOK_DEADLINE = 1.5
CMD_DEADLINE = 3.0
# the lines Jev's answers are read against are `jev_gate` and `jev_doubt` in ~/.isa/config.json (config.py)
CREDIT = re.compile(r"credit|balance|insufficient|payment|billing|quota|\b402\b", re.I)


def binary():
    """The `jev` CLI to run, or None when Jev is switched off or not installed."""
    if not config.get("jev"):
        return None
    name = os.environ.get("ISA_JEV_BIN") or "jev"
    return shutil.which(name) if os.sep not in name else (name if os.access(name, os.X_OK) else None)


def enabled():
    return binary() is not None


def ask(preset, payload, deadline, **ctx):
    return _call(["run", preset], payload, deadline, {"preset": preset}, **ctx)


def ask_adhoc(state, questions, deadline, **ctx):
    """One request of many questions over one state (`jev ask`): the review's per-leaf and per-section checks.
    Served only when every question came back."""
    res = _call(["ask"], {"state": state, "questions": questions}, deadline,
                {"preset": "adhoc", "questions": len(questions)}, **ctx)
    if res["served"] and set(questions) - set(res["answers"]):
        res.update(served=False, reason="garbled", detail="answers missing for some questions")
    return res


def _call(argv, payload, deadline, row_fields, **ctx):
    exe = binary()
    if not exe:
        return {"served": False, "reason": "off", "detail": "", "answer": None, "answers": {}, "ms": 0}
    env = dict(os.environ, JEV_KIT_PRESETS=PRESETS + (os.pathsep + os.environ["JEV_KIT_PRESETS"]
                                                       if os.environ.get("JEV_KIT_PRESETS") else ""))
    t0 = time.time()
    res = {"served": False, "reason": "error", "detail": "", "answer": None, "answers": {}}
    try:
        r = subprocess.run([exe, *argv, "--consumer", "isa"], input=json.dumps(payload), text=True,
                           capture_output=True, timeout=deadline, env=env)
        res.update(_parse(r.returncode, r.stdout, r.stderr))
    except subprocess.TimeoutExpired:
        res.update(reason="timeout", detail=f"no answer within {deadline:g} s")
    except OSError as e:
        res.update(reason="error", detail=str(e))
    res["ms"] = int((time.time() - t0) * 1000)
    row = {"step": "jev", **row_fields, "served": res["served"], "answer": res["answer"], "ms": res["ms"]}
    if not res["served"]:
        row.update(reason=res["reason"], detail=res["detail"][:200])
    row.update({k: v for k, v in ctx.items() if v is not None})
    logs.write(row)
    return res


def _parse(code, out, err):
    try:
        data = json.loads(out.strip().splitlines()[-1]) if out.strip() else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return {"served": False, "reason": "garbled" if code == 0 else "error",
                "detail": (out or err or f"exit {code}").strip()[:200]}
    if code == 0 and data.get("ok") and isinstance(data.get("answers"), dict):
        answers = {k: v.get("answer") for k, v in data["answers"].items() if isinstance(v, dict)}
        first = next(iter(answers.values()), None)
        if not isinstance(first, (int, float)):
            return {"served": False, "reason": "garbled", "detail": out.strip()[:200]}
        return {"served": True, "answer": float(first), "answers": answers}
    un = data.get("unavailable") if isinstance(data.get("unavailable"), dict) else {}
    reason = "budget" if code == 5 else str(un.get("reason") or ("auth" if code == 3 else "error"))
    return {"served": False, "reason": reason, "detail": str(un.get("detail") or err or "").strip()}


def ask_many(items, deadline, **ctx):
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(items))) as pool:
        # the debug row names the criterion a per-ISC question was about (probe adequacy, claim check)
        futures = [pool.submit(ask, preset, payload, deadline, **ctx,
                               **({"isc": payload["isc"]} if isinstance(payload, dict) and "isc" in payload else {}))
                   for preset, payload in items]
        return [f.result() for f in futures]


def kind(res):
    """credit | budget | other | None (served, switched off, or a deadline miss — not worth a message)."""
    if res.get("served") or res.get("reason") in ("off", "timeout"):
        return None
    if res.get("reason") == "budget":
        return "budget"
    if CREDIT.search(res.get("detail") or ""):
        return "credit"
    return "other"


def message(res):
    k = kind(res)
    detail = (res.get("detail") or "").strip()
    if k == "credit":
        return (f"Jev credit looks exhausted ({detail}). ISA keeps working on its baseline checks. To fix: top up "
                "TypeSafe credits, then run `jev reset`; or stop the attempts with `jev disable` (every jev-kit "
                'consumer) or `"jev": false` in ~/.isa/config.json (ISA only).')
    if k == "budget":
        return (f'Jev\'s daily budget for consumer "isa" is used up ({detail}). ISA keeps working on its baseline '
                "checks; raise the budget in ~/.config/jev-kit/config.json or wait for the window to roll.")
    if k == "other":
        return (f"Jev unavailable ({res.get('reason')}: {detail}). ISA keeps working on its baseline checks; "
                "`jev status` shows the breaker.")
    return None
