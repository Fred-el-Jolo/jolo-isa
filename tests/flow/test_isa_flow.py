"""SPEC-v2 § 9: the whole flow, live. Two real Claude Code sessions run against this repo's runtime and
skill — one task that must end in a closed, proven ISA (YES), one question that must stay silent (NO).

Opt-in and paid (Sonnet 5.5, roughly $0.30–1 a run):

    ISA_FLOW_LIVE=1 python3 -m unittest tests.flow.test_isa_flow

Each session gets a sealed sandbox: a fresh git project copied from `fixture/`, a private ISA_HOME, the
repo's `isa` first on PATH, a generated `--settings` with the repo's hooks only (the user's
~/.claude/settings.json, skills, plugins and MCP servers are not loaded), `ISA_JUDGE=claude`.

Output: `tests/evals/results/flow/<stamp>/` (or `$ISA_FLOW_OUT/<stamp>/`) with `ISA.articulation.md`
(the ISA at the first project change), `ISA.final.md`, `timeline.md`, `verdict.md`, `verdict.json` and
both transcripts. When that folder sits in the `eval-results` worktree the run is committed there
(`ISA_FLOW_COMMIT=0` skips the commit).
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture")
RUNTIME_BIN = os.path.join(REPO, "runtime", "bin", "isa")
SKILL_DIR = os.path.join(REPO, "skill", "ISA")
LIVE = os.environ.get("ISA_FLOW_LIVE") == "1"
MODEL = os.environ.get("ISA_FLOW_MODEL", "claude-sonnet-5-5")
BUDGET = os.environ.get("ISA_FLOW_BUDGET_USD", "3")
TOOLS = ["Bash", "Read", "Edit", "Write", "Glob", "Grep"]
EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop"]

YES_PROMPT = ("Add two things to todo.py: a `done <id>` command that marks a task as completed, and a `--pending` "
              "flag on `list` that hides completed tasks. Completed tasks should show as `[x]` in the list output, "
              "pending ones as `[ ]`.")
NO_PROMPT = "what does `cmd_list` in todo.py print?"

# Copies the newest ISA.md to ISA.articulation.md the first time the model tries to change the project.
SNAPSHOT = r'''
import glob, json, os, shutil, sys
ev = json.load(sys.stdin)
dest = os.environ["ISA_FLOW_SNAPSHOT"]
if os.path.exists(dest):
    sys.exit(0)
inp = ev.get("tool_input") or {}
proj = os.path.realpath(os.environ["ISA_FLOW_PROJECT"])
target = inp.get("file_path") or inp.get("notebook_path") or ""
change = ev.get("tool_name") in ("Edit", "Write", "MultiEdit", "NotebookEdit") and \
    os.path.realpath(target).startswith(proj + os.sep)
cmd = inp.get("command") or "" if ev.get("tool_name") == "Bash" else ""
change = change or (cmd and "todo.py" in cmd and any(s in cmd for s in (">", "sed -i", "<<", "tee ", "patch")))
if change:
    isas = sorted(glob.glob(os.path.join(os.environ["ISA_HOME"], "*", "*", "ISA.md")), key=os.path.getmtime)
    if isas:
        shutil.copyfile(isas[-1], dest)
'''

ACCEPT = r'''
set -e
export TODO_FILE="$(mktemp -d)/t.json"
python3 todo.py add "buy milk" >/dev/null
python3 todo.py add "walk dog" >/dev/null
python3 todo.py done 1 >/dev/null
all=$(python3 todo.py list)
pending=$(python3 todo.py list --pending)
echo "$all" | grep -q '^1 \[x\] buy milk$'
echo "$all" | grep -q '^2 \[ \] walk dog$'
echo "$pending" | grep -q '^2 \[ \] walk dog$'
! echo "$pending" | grep -q 'buy milk'
'''


def _git(args, cwd, check=True):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=check)


class Sandbox:
    def __init__(self, name, out):
        self.root = tempfile.mkdtemp(prefix=f"isa-flow-{name}-")
        self.proj = os.path.join(self.root, "todo")
        self.isa_home = os.path.join(self.root, "isa-home")
        self.bin = os.path.join(self.root, "bin")
        self.out = out
        shutil.copytree(FIXTURE, self.proj)
        os.makedirs(self.isa_home)
        os.makedirs(self.bin)
        os.symlink(RUNTIME_BIN, os.path.join(self.bin, "isa"))
        _git(["init", "-q"], self.proj)
        _git(["add", "-A"], self.proj)
        _git(["-c", "user.name=flow", "-c", "user.email=flow@example.invalid", "commit", "-qm", "fixture"],
             self.proj)
        snap = os.path.join(self.root, "snapshot.py")
        with open(snap, "w") as f:
            f.write(SNAPSHOT)
        hook = f'python3 "{RUNTIME_BIN}" hook claude'
        hooks = {ev: [{"hooks": [{"type": "command", "command": hook, "timeout": 20 if ev == "UserPromptSubmit" else 15}]}]
                 for ev in EVENTS}
        hooks["PreToolUse"].append({"hooks": [{"type": "command", "command": f'python3 "{snap}"', "timeout": 10}]})
        self.settings = os.path.join(self.root, "settings.json")
        with open(self.settings, "w") as f:
            json.dump({"hooks": hooks, "permissions": {"allow": TOOLS, "defaultMode": "acceptEdits",
                                                       "additionalDirectories": [self.isa_home, SKILL_DIR]}}, f)

    def env(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("ISA_", "CLAUDE_CODE_", "CLAUDECODE"))}
        env.update(ISA_HOME=self.isa_home, ISA_SKILL_DIR=SKILL_DIR, ISA_JUDGE="claude",
                   ISA_FLOW_PROJECT=self.proj, ISA_FLOW_SNAPSHOT=os.path.join(self.out, "ISA.articulation.md"),
                   PATH=self.bin + os.pathsep + os.environ.get("PATH", ""), ENABLE_CLAUDEAI_MCP_SERVERS="false")
        return env

    def run(self, prompt):
        argv = ["claude", "-p", "--model", MODEL, "--output-format", "stream-json", "--verbose",
                "--include-hook-events", "--setting-sources", "project", "--settings", self.settings,
                "--no-session-persistence", "--disable-slash-commands", "--strict-mcp-config",
                "--permission-mode", "acceptEdits", "--tools", ",".join(TOOLS), "--allowedTools", ",".join(TOOLS),
                "--max-budget-usd", BUDGET, "--add-dir", self.isa_home, SKILL_DIR]
        t0 = time.time()
        r = subprocess.run(argv, input=prompt, cwd=self.proj, env=self.env(), capture_output=True, text=True,
                           timeout=int(os.environ.get("ISA_FLOW_TIMEOUT", "1800")))
        return Run(r.stdout, r.stderr, time.time() - t0, self)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Run:
    """A stream-json transcript, in order: tool calls (with results), hook events, the final result."""

    def __init__(self, stdout, stderr, secs, sb):
        self.raw, self.stderr, self.secs, self.sb = stdout, stderr, secs, sb
        self.items, self.calls, self.hooks = [], [], []
        self.final, self.cost, self.session, self.api_error = "", None, None, None
        by_id = {}
        for line in stdout.splitlines():
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if not isinstance(m, dict):
                continue
            t, sub = m.get("type"), str(m.get("subtype", ""))
            self.session = self.session or m.get("session_id")
            if t == "system" and "hook" in sub:
                code = m.get("exit_code")
                h = {"event": m.get("hook_event") or m.get("hook_event_name") or "", "name": m.get("hook_name") or "",
                     "sub": sub, "exit": int(code) if str(code).lstrip("-").isdigit() else code,
                     "text": " ".join(_unjson(m.get(k)) for k in ("output", "stdout", "stderr") if m.get(k))}
                self.hooks.append(h)
                self.items.append(("hook", h))
            elif t == "assistant":
                for c in (m.get("message") or {}).get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        e = {"name": c.get("name"), "input": c.get("input") or {}, "result": "", "error": False}
                        self.calls.append(e)
                        by_id[c.get("id")] = e
                        self.items.append(("call", e))
            elif t == "user":
                content = (m.get("message") or {}).get("content")
                for c in content if isinstance(content, list) else []:
                    if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in by_id:
                        e = by_id[c["tool_use_id"]]
                        rc = c.get("content")
                        e["result"] = rc if isinstance(rc, str) else " ".join(
                            x.get("text", "") for x in rc or [] if isinstance(x, dict))
                        e["error"] = bool(c.get("is_error"))
            elif t == "result":
                self.final = m.get("result") or ""
                self.api_error = m.get("api_error_status") or (m.get("terminal_reason") == "api_error" and self.final)
                self.cost = m.get("total_cost_usd")

    def hook_text(self, event):
        return "\n".join(h["text"] for h in self.hooks if event in (h["event"] + h["name"]))

    def bash(self, needle):
        return [c for c in self.calls if c["name"] == "Bash" and needle in (c["input"].get("command") or "")]

    def gate_rows(self):
        rows = []
        try:
            with open(os.path.join(self.sb.isa_home, "_state", "judge.jsonl")) as f:
                rows = [json.loads(line) for line in f if line.strip()]
        except OSError:
            pass
        return [r for r in rows if r.get("session") == self.session] or rows

    def session_state(self):
        for p in glob.glob(os.path.join(self.sb.isa_home, "_state", "sessions", "*.json")):
            with open(p) as f:
                return json.load(f)
        return {}

    def isas(self):
        return sorted(glob.glob(os.path.join(self.sb.isa_home, "*", "*", "ISA.md")))

    def ledger(self):
        rows = []
        for p in glob.glob(os.path.join(self.sb.isa_home, "_state", "evidence", "*.jsonl")):
            with open(p) as f:
                rows += [json.loads(line) for line in f if line.strip()]
        return sorted(rows, key=lambda r: r.get("t", 0))


def _unjson(text):
    """Hook output is JSON with \\u escapes: decode it so markers match the text the model saw."""
    try:
        return json.dumps(json.loads(text), ensure_ascii=False)
    except (TypeError, ValueError):
        return str(text)


def _fm(text):
    sys.path.insert(0, os.path.join(REPO, "runtime"))
    from isa import lint
    return lint.parse(text, "ISA.md")


def _stage(n, name, passed, evidence):
    return {"stage": n, "name": name, "passed": bool(passed), "evidence": evidence}


def judge_yes(run):
    st, s = run.session_state(), []
    gates = run.gate_rows()
    first = gates[0] if gates else {}
    s.append(_stage(1, "gate verdict yes, user line `ISA: ON`",
                    first.get("verdict") == "yes" and "ISA: ON" in run.hook_text("UserPromptSubmit"),
                    f"judge row: {first.get('verdict')} via {first.get('source')} in {first.get('ms')} ms — "
                    f"{first.get('reason')}"))
    with open(os.path.join(REPO, "runtime", "isa", "protocol.md")) as f:
        marker = f.readline().strip()
    s.append(_stage(2, "ON block injected", marker in run.hook_text("UserPromptSubmit"), f"marker {marker!r}"))
    reads = [c for c in run.calls if (c["name"] == "Read" and c["input"].get("file_path", "").endswith("ISA/SKILL.md"))
             or (c["name"] == "Bash" and "SKILL.md" in c["input"].get("command", ""))]
    s.append(_stage(3, "model read SKILL.md", reads, f"{len(reads)} read(s)"))

    isas = run.isas()
    path = isas[-1] if isas else None
    text = open(path).read() if path else ""
    p = _fm(text) if text else {"fm": {}, "iscs": {}}
    fm = p["fm"]
    news = run.bash("isa new")
    goal = str(fm.get("stated_goal") or "")
    ok4 = bool(news) and path and st.get("bound") == path and fm.get("root") and isinstance(fm.get("asks"), list) \
        and goal and goal in YES_PROMPT
    s.append(_stage(4, "`isa new` ran, session bound, root/asks/stated_goal set", ok4,
                    f"{len(news)} `isa new` call(s); bound={st.get('bound') == path}; root={fm.get('root')!r}; "
                    f"asks={fm.get('asks')!r}; stated_goal={goal!r}"))

    def changes_project(c):
        fp = c["input"].get("file_path") or ""
        return c["name"] in ("Edit", "Write", "MultiEdit") and os.path.realpath(fp).startswith(
            os.path.realpath(run.sb.proj) + os.sep)
    first_change = next((c for c in run.calls if changes_project(c)), None)
    snap = os.path.exists(os.path.join(run.sb.out, "ISA.articulation.md"))
    refused = first_change and first_change["error"] and "ISA" in first_change["result"]
    s.append(_stage(5, "ISA lint-clean before the first project change", first_change and snap and not refused,
                    f"first change: {first_change and first_change['name']} "
                    f"{first_change and first_change['input'].get('file_path')}; snapshot={snap}; "
                    f"refused={bool(refused)}: {(first_change or {}).get('result', '')[:200]!r}"))

    ledger = run.ledger()
    notes, ok6 = [], True
    for isc in sorted({r["isc"] for r in ledger if r.get("kind") == "verify" and r.get("ok") and r.get("isc")}):
        green = next(r for r in ledger if r.get("isc") == isc and r.get("kind") == "verify" and r.get("ok"))
        red = [r for r in ledger if r.get("isc") == isc and r.get("run") == "red" and not r.get("ok")
               and r.get("tool_sha") == green.get("tool_sha") and r.get("t", 0) < green["t"]
               and r.get("fingerprint") != green.get("fingerprint")]
        vline = next((ln for ln in text.splitlines() if ln.startswith(f"- {isc}:")), "")
        if red:
            moved = sorted(f for f in set(red[-1].get("files") or {}) | set(green.get("files") or {})
                           if (red[-1].get("files") or {}).get(f) != (green.get("files") or {}).get(f))
            notes.append(f"{isc}: red → green" + (f" (named files changed: {', '.join(moved)})" if moved else ""))
        elif "(no red baseline)" in vline:
            notes.append(f"{isc}: (no red baseline)")
        else:
            sys.path.insert(0, os.path.join(REPO, "runtime"))
            from isa import commands
            why = commands.red_exempt(p, isc)
            notes.append(f"{isc}: " + (f"red exempt ({why})" if why else "no red row and not marked"))
            ok6 = ok6 and bool(why)
    s.append(_stage(6, "red-then-green, or marked `(no red baseline)`", ok6, "; ".join(notes) or "no green rows"))

    own = [c for c in run.calls if "ISA ownership" in c["result"]]
    s.append(_stage(7, "model never wrote engine-owned fields", True,
                    f"{len(own)} ownership refusal(s){' — recovered' if own else ''}"))

    acc = subprocess.run(["bash", "-c", ACCEPT], cwd=run.sb.proj, capture_output=True, text=True)
    status = _git(["status", "--porcelain", "--untracked-files=all"], run.sb.proj).stdout.split("\n")
    changed = sorted(ln[3:] for ln in status if ln.strip() and "__pycache__" not in ln)
    allowed = all(f == "todo.py" or f.endswith(".json") or os.path.basename(f).startswith("test") for f in changed)
    s.append(_stage(8, "acceptance passes, only allowed files changed", acc.returncode == 0 and allowed,
                    f"acceptance exit {acc.returncode}; changed: {changed}"))

    closes = run.bash("isa close")
    close_rows = [r for r in ledger if r.get("kind") == "close"]
    last_t = close_rows[-1]["t"] - 1 if close_rows else 0
    last_close = [r for r in close_rows if r["t"] >= last_t]
    moved = [r for r in ledger if r.get("kind") == "changed" and r.get("t", 0) >= last_t]
    ticked = [i for i, v in p["iscs"].items() if v[0]]
    proven = [i for i in ticked if any(r.get("isc") == i and (r.get("ok") or r.get("kind") == "attest")
                                       for r in ledger)]
    ok9 = closes and fm.get("phase") == "complete" and last_close and all(r.get("ok") for r in last_close) \
        and not moved and len(proven) == len(ticked) and "complete" in run.final.lower()
    s.append(_stage(9, "`isa close` exit 0, complete, probes re-passed, tree unchanged, summary quoted", ok9,
                    f"{len(closes)} close call(s); phase={fm.get('phase')}; progress={fm.get('progress')}; "
                    f"last close: {sum(r.get('ok', False) for r in last_close)}/{len(last_close)} ok; "
                    f"tree moved by close: {bool(moved)}; ticks proven {len(proven)}/{len(ticked)}"))
    return s, path


def judge_no(run):
    gates = run.gate_rows()
    first = gates[0] if gates else {}
    ctx = [h for h in run.hooks if "UserPromptSubmit" in h["event"] + h["name"] and "additionalContext" in h["text"]]
    stops = [h for h in run.hooks if "Stop" in h["event"] + h["name"]]
    loud = [h for h in stops if h["exit"] not in (0, None) or "block" in h["text"] or "ISA" in h["text"]]
    return [
        _stage(1, "gate verdict no", first.get("verdict") == "no",
               f"judge row: {first.get('verdict')} via {first.get('source')} in {first.get('ms')} ms — "
               f"{first.get('reason')}"),
        _stage(2, "user line `ISA: OFF`", "ISA: OFF" in run.hook_text("UserPromptSubmit"), "UserPromptSubmit output"),
        _stage(3, "no ISA file", not run.isas(), f"{len(run.isas())} ISA file(s)"),
        _stage(4, "no context injected", not ctx, f"{len(ctx)} UserPromptSubmit context block(s)"),
        _stage(5, "Stop hook silent", not loud, f"{len(stops)} Stop hook event(s), {len(loud)} not silent"),
    ]


def timeline(run, title):
    out = [f"## {title}", "", f"session `{run.session}` · {run.secs:.0f} s · cost ${run.cost}", ""]
    for g in run.gate_rows():
        out.append(f"- **gate** {g.get('verdict')} via {g.get('source')} in {g.get('ms')} ms — {g.get('reason')}")
    for kind, x in run.items:
        if kind == "hook":
            text = " ".join(x["text"].split())[:220]
            if text or x["exit"] not in (0, None):
                out.append(f"- hook {x['event'] or x['name']} ({x['sub']}, exit {x['exit']}): {text}")
        else:
            inp = x["input"]
            what = inp.get("command") or inp.get("file_path") or inp.get("pattern") or json.dumps(inp)[:120]
            isa_edit = " **ISA edit**" if str(inp.get("file_path", "")).endswith("ISA.md") and x["name"] != "Read" else ""
            res = " ".join(x["result"].split())[:220]
            out.append(f"- **{x['name']}**{isa_edit} `{' '.join(str(what).split())[:200]}` → "
                       f"{'ERROR ' if x['error'] else ''}{res}")
    out += ["", "Final answer:", "", "> " + run.final.replace("\n", "\n> "), ""]
    return "\n".join(out)


def render(stamp, yes, no, yes_run, no_run):
    rows = lambda ss: "\n".join(f"| {x['stage']} | {x['name']} | {'PASS' if x['passed'] else 'FAIL'} | "
                                f"{x['evidence'].replace('|', '/')} |" for x in ss)
    gates = [g.get("ms") for r in (yes_run, no_run) for g in r.gate_rows()]
    return (f"# ISA flow run {stamp}\n\nModel {MODEL}; repo `{_git(['rev-parse', '--short', 'HEAD'], REPO).stdout.strip()}`"
            f" (+ working tree); gate times {gates} ms; cost ${yes_run.cost} + ${no_run.cost}.\n\n"
            f"## YES — task prompt\n\n> {YES_PROMPT}\n\n| # | stage | | evidence |\n|---|---|---|---|\n{rows(yes)}\n\n"
            f"## NO — question\n\n> {NO_PROMPT}\n\n| # | stage | | evidence |\n|---|---|---|---|\n{rows(no)}\n")


@unittest.skipUnless(LIVE, "live, paid run: set ISA_FLOW_LIVE=1")
class TestIsaFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = os.environ.get("ISA_FLOW_OUT") or os.path.join(REPO, "tests", "evals", "results", "flow")
        cls.out = os.path.join(base, stamp)
        os.makedirs(cls.out)
        yes_sb, no_sb = Sandbox("yes", cls.out), Sandbox("no", os.path.join(cls.out, ".no"))
        os.makedirs(no_sb.out)
        try:
            yes_run, no_run = yes_sb.run(YES_PROMPT), no_sb.run(NO_PROMPT)
            broken = [f"{n}: API error {r.api_error} — {r.final[:120]}" for n, r in (("yes", yes_run), ("no", no_run))
                      if r.api_error]
            if broken:  # a rate limit or outage says nothing about the ISA flow: no grading, no commit
                shutil.rmtree(cls.out, ignore_errors=True)
                raise RuntimeError("live run did not complete — " + "; ".join(broken))
            cls.yes, isa = judge_yes(yes_run)
            cls.no = judge_no(no_run)
            if isa:
                shutil.copyfile(isa, os.path.join(cls.out, "ISA.final.md"))
            for name, run in (("yes", yes_run), ("no", no_run)):
                with open(os.path.join(cls.out, f"transcript.{name}.jsonl"), "w") as f:
                    f.write(run.raw)
            with open(os.path.join(cls.out, "timeline.md"), "w") as f:
                f.write(f"# Timeline {stamp}\n\n" + timeline(yes_run, "YES session") + "\n" + timeline(no_run, "NO session"))
            report = render(stamp, cls.yes, cls.no, yes_run, no_run)
            with open(os.path.join(cls.out, "verdict.md"), "w") as f:
                f.write(report)
            gates = [g.get("ms") for r in (yes_run, no_run) for g in r.gate_rows()]
            with open(os.path.join(cls.out, "verdict.json"), "w") as f:
                json.dump({"stamp": stamp, "model": MODEL, "gate_ms": gates, "cost_usd": [yes_run.cost, no_run.cost],
                           "secs": [round(yes_run.secs), round(no_run.secs)], "yes": cls.yes, "no": cls.no}, f, indent=1)
            print("\n" + report, file=sys.stderr)
            for name, sb in (("yes", yes_sb), ("no", no_sb)):  # ledger, judge log, sessions: re-gradable later
                shutil.copytree(sb.isa_home, os.path.join(cls.out, f"isa-home.{name}"), symlinks=True)
        finally:
            shutil.rmtree(no_sb.out, ignore_errors=True)
            yes_sb.cleanup()
            no_sb.cleanup()
        cls.commit(stamp)

    @classmethod
    def commit(cls, stamp):
        if os.environ.get("ISA_FLOW_COMMIT") == "0":
            return
        top = _git(["rev-parse", "--show-toplevel"], cls.out, check=False).stdout.strip()
        branch = _git(["branch", "--show-current"], cls.out, check=False).stdout.strip()
        if not top or branch != "eval-results":
            return
        passed = sum(x["passed"] for x in cls.yes + cls.no)
        _git(["add", os.path.relpath(cls.out, top)], top)
        _git(["commit", "-qm", f"flow: {stamp} ({MODEL}; {passed}/{len(cls.yes) + len(cls.no)} stages passed)"], top)

    def test_yes_session(self):
        bad = [x for x in self.yes if not x["passed"]]
        self.assertFalse(bad, json.dumps(bad, indent=1))

    def test_no_session(self):
        bad = [x for x in self.no if not x["passed"]]
        self.assertFalse(bad, json.dumps(bad, indent=1))


if __name__ == "__main__":
    unittest.main()
