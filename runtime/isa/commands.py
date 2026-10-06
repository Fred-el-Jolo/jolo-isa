"""`isa new`, `isa verify`, `isa close` (SPEC-v2 § 3.2): the commands that write an ISA's engine-owned
state. Standard library only.

    new(args)     scaffold a task ISA (frontmatter only: task, slug, effort, phase, progress, started,
                  updated, root, stated_goal, asks) and print its path; the hooks bind it
    verify(...)   run probes (cwd = the ISA's `root`), record ledger rows, tick what passed, untick what
                  regressed, write the generated Verification lines; `--attest` ticks a self-attested ISC;
                  `--red` records the failing baseline and never ticks
    close(path)   re-run every probe; close only when everything passes and `lint --close` is clean

Every command recomputes `progress`, syncs nested parents and drops orphaned generated lines first
(isafile.normalize), and refuses to run probes before the ISA passes articulation lint.
"""
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import time

from . import config, crypt, evidence, fingerprint, isafile, jev, lint, logs, problems, quotes, rules, state

TAIL = evidence.TAIL_CHARS
VAGUE = {"make", "this", "that", "good", "better", "thing", "things", "stuff", "please", "just", "with", "from",
         "into", "some", "it's", "they", "them", "then", "than", "have", "would", "could", "should"}


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def articulation_errors(path, text):
    norm = isafile.normalize(text)
    r = lint.lint(path, "articulation", text=norm)
    return [m for lvl, m in r.items if lvl == "ERROR"] + rules.check(path, lint.parse(norm, path))[0]


# ------------------------------------------------------------------ root

def _enclosing_isa(cwd):
    """The ISA.md of the ISA folder `cwd` is in (or under), or None."""
    d, h = os.path.realpath(cwd), os.path.realpath(state.home())
    while (d + os.sep).startswith(h + os.sep):
        if os.path.isfile(os.path.join(d, "ISA.md")):
            return os.path.join(d, "ISA.md")
        d = os.path.dirname(d)
    return None


def _inside_isa_home(cwd):
    d, h = os.path.realpath(cwd), os.path.realpath(state.home())
    return (d + os.sep).startswith(h + os.sep)


def root_for(cwd):
    """(root, error): the project root for a new ISA run from `cwd`. Inside an ISA folder it is that ISA's
    own `root:` — never the ISA folder itself, which has no git root and would make probes run there."""
    if _inside_isa_home(cwd):
        enclosing = _enclosing_isa(cwd)
        root = state.frontmatter(enclosing).get("root") if enclosing else None
        if not root:
            return None, "no root: run it from the project (this directory is inside the ISA home)"
        return os.path.expanduser(str(root)), None
    return state.project_root(cwd), None


def resolve_root(text, cwd, path=None):
    """(root, text, error) for an existing ISA: its `root:`, or — a v1 ISA — cwd's project root, written in.
    A relative `root` (a repo ISA, § 13.3) is relative to the repo the ISA lives in."""
    root = isafile.fm(text).get("root")
    if root:
        root = os.path.expanduser(str(root))
        if not os.path.isabs(root):
            repo = state.isa_repo(path) if path else None
            if not repo:
                return None, text, f"root `{root}` is relative, but this ISA is not inside a repo's .isa/"
            root = os.path.normpath(os.path.join(repo, root))
        return (root, text, None) if os.path.isdir(root) else (None, text, f"root `{root}` is not a directory")
    if _inside_isa_home(cwd):
        return None, text, "no root: run it from the project (an ISA without `root:` takes the project of the cwd)"
    root = state.project_root(cwd)
    return root, isafile.fm_set(text, "root", root), None


# ------------------------------------------------------------------ new

def _content_words(s):
    return [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", s) if w.lower() not in VAGUE]


def min_content(s):
    """Scaffold's fail-closed rule: ≥ 6 tokens and some propositional content."""
    return len(re.findall(r"\S+", s or "")) >= 6 and len(_content_words(s)) >= 2


def project_prompts(key):
    rows = []
    d = state.state_dir("prompts")
    for f in sorted(os.listdir(d)):
        if not f.endswith(".jsonl"):
            continue
        try:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict) and row.get("project") == key:
                        rows.append(row)
        except OSError:
            continue
    return sorted(rows, key=lambda r: r.get("t", 0))


def new(args, cwd=None, out=print):
    cwd = cwd or os.getcwd()
    opts, words, i = {"--tier": None, "--goal": None}, [], 0
    path_only = "--path-only" in args
    args = [a for a in args if a != "--path-only"]
    while i < len(args):
        if args[i] in opts and i + 1 < len(args):
            opts[args[i]] = args[i + 1]
            i += 2
        else:
            words.append(args[i])
            i += 1
    slug = " ".join(words) or "task"
    path = state.new_isa_path(cwd, slug)
    repo = None if path_only else state.repo_root(cwd)
    if repo and not path.startswith(os.path.join(repo, ".isa") + os.sep):
        repo = None
    if repo and not crypt.key():  # Option A (SPEC-v2 § 13.7): a repo ISA's prompts need the key
        out(f"isa new: {crypt.NO_KEY}")
        return 2
    if path_only:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        out(path)
        return 0
    tier = (opts["--tier"] or "E3").upper()
    if tier not in lint.TIER_ARTICULATION:
        out(f"isa new: --tier must be E1..E5, got `{opts['--tier']}`")
        return 2
    root, err = root_for(cwd)
    if err:
        out(f"isa new: {err}")
        return 2
    prompts = project_prompts(state.project_key(cwd))
    goal, comment, source = None, None, prompts[-1] if prompts else None
    if opts["--goal"] is not None:
        span = opts["--goal"]
        if not min_content(span):
            out("isa new: --goal fails the minimum-content rule (≥ 6 words with real content) — pick a longer "
                "verbatim span of the prompt, or leave --goal out (stated_goal: null)")
            return 1
        holding = [r for r in prompts if span in (r.get("text") or "")]
        if not holding:
            out("isa new: --goal is not a verbatim span of any logged prompt of this project — copy it "
                "byte-for-byte from the user's prompt")
            return 1
        goal, source = span, holding[-1]
    elif prompts:
        latest = prompts[-1].get("text") or ""
        if len(latest) <= 300 and "```" not in latest and "<pasted" not in latest and min_content(latest):
            goal = latest
    if goal is None:
        comment = ("# stated_goal: copy a verbatim span of the user's prompt (≥ 6 words), or leave it null "
                   "and log the candidate in Decisions")
    repo = state.isa_repo(path)
    if repo:  # a repo ISA: `root` is repo-relative, so the committed ISA works on every machine (§ 13.3)
        rr = os.path.realpath(repo)
        rel = os.path.relpath(os.path.realpath(root), rr)
        root = "." if rel == "." else rel if not rel.startswith("..") else root
    stamp = isafile.now_iso()
    folder = os.path.basename(os.path.dirname(path))
    lines = ["---", 'task: ""', f"slug: {folder}", f"effort: {tier}", "phase: observe", "progress: 0/0",
             f"started: {stamp}", f"updated: {stamp}", f"root: {isafile._yaml_value(root)}",
             f"stated_goal: {isafile._yaml_value(goal)}"]
    if goal is not None:
        lines.append("stated_goal_source: prompt")
    if comment:
        lines.append(comment)
    # SPEC-v2 § 11.2: no model call — the model lists the asks; lint checks each is a verbatim span
    lines += ["asks: []", "# asks: list each explicit ask of the prompt as a verbatim span (lint checks them)"]
    lines += ["---", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    isafile.write_atomic(path, "\n".join(lines))
    if repo:
        crypt.setup_repo(repo, out)
        project_isa(repo, out)
    logs.note(isa=path)
    out(path)
    return 0


PROJECT_SKELETON = """---
kind: project
task: "{task}"
effort: E3
started: {stamp}
updated: {stamp}
---

## Problem

The living spec of `{name}`: the constraints and standing claims its code must keep satisfying. Task ISAs live in
`.isa/`; a criterion that must hold forever is promoted here (`promote: true`).
"""


def project_isa(repo, out=print):
    """The repo's project ISA (SPEC-v2 § 13.2): created as a skeleton on the first `isa new`; an existing
    root `ISA.md` of another kind is never touched."""
    path = os.path.join(repo, "ISA.md")
    if os.path.exists(path):
        if state.frontmatter(path).get("kind") != "project":
            out(f"isa new: {path} exists and is not a project ISA (no `kind: project`) — left untouched; this repo "
                "gets no project ISA")
        return
    name = os.path.basename(repo)
    isafile.write_atomic(path, PROJECT_SKELETON.format(task=f"Living spec of {name}", stamp=isafile.now_iso(), name=name))
    out(f"isa: created the project ISA {path} (kind: project — commit it with the code)")


STANDING = re.compile(r"^\s*- (ISC-P\d+): (.*)$", re.M)
PROJECT_FORBIDDEN = ("phase", "progress", "root", "stated_goal", "asks")


def lint_project(path, text):
    """The project ISA's rules (SPEC-v2 § 13.2, § 13.5) → [error]."""
    p = lint.parse(text, path)
    fm, errs = p["fm"], []
    if fm.get("kind") != "project":
        errs.append("frontmatter: a repo's root ISA.md must say `kind: project`")
    if not str(fm.get("task") or "").strip():
        errs.append("frontmatter: `task:` (the repo's one-line purpose) is empty")
    errs += [f"frontmatter: `{k}:` belongs to task ISAs, not the project ISA" for k in PROJECT_FORBIDDEN if k in fm]
    errs += [f"the project ISA never quotes the user (it is committed unencrypted): {line}"
             for line in crypt.lint_project(text) if not line.startswith("frontmatter")]
    if re.search(r"^\s*- \[[ xX]\] ISC-", p["content"].get("Criteria", ""), re.M):
        errs.append("Criteria: standing claims have no checkbox — write `- ISC-P<n>: <claim>` (re-proved, never ticked)")
    claims = STANDING.findall(p["content"].get("Criteria", ""))
    seen = set()
    for i, _ in claims:
        if i in seen:
            errs.append(f"Criteria: {i} appears twice")
        seen.add(i)
        e = p["test_strategy"].get(i)
        if not e or not str(e.get("tool") or "").strip():
            errs.append(f"Test Strategy: standing claim {i} has no entry with a `tool:` — it must be re-provable")
    return errs


def verify_project(path, timeout=600, out=print):
    """`isa verify ISA.md`: re-prove every standing claim from the repo root; record locally (never committed)."""
    text = _read(path)
    errs = lint_project(path, text)
    if errs:
        out("isa verify: the project ISA does not lint clean:")
        for e in errs:
            out(f"  - {e}")
        return 1
    p = lint.parse(text, path)
    repo = os.path.dirname(os.path.realpath(path))
    claims = [i for i, _ in STANDING.findall(p["content"].get("Criteria", ""))]
    if not claims:
        out("isa verify: the project ISA has no standing claims yet")
        return 0
    failed, rows = 0, []
    for i in claims:
        e = p["test_strategy"][i]
        cwd = _probe_cwd(repo, e)
        t0 = time.time()
        try:
            r = subprocess.run(str(e["tool"]).strip(), shell=True, executable="/bin/bash", cwd=cwd,
                               capture_output=True, text=True, timeout=timeout, env=probe_env())
            code = r.returncode
        except subprocess.TimeoutExpired:
            code = 124
        secs = round(time.time() - t0, 2)
        failed += code != 0
        out(f"{i} {'PASS' if code == 0 else 'FAIL'}  exit {code}  {secs}s  {str(e['tool']).strip()}")
        rows.append({"t": time.time(), "isc": i, "ok": code == 0, "exit": code, "secs": secs,
                     "tool_sha": evidence.tool_sha(e["tool"])})
    d = state.state_dir("project")
    with open(os.path.join(d, state.project_key(repo) + ".jsonl"), "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    out(f"\nproject ISA: {len(claims) - failed}/{len(claims)} standing claim(s) hold")
    return 1 if failed else 0


def promote_issues(path, parsed):
    """`promote: true` criteria of a task ISA with no line `(from <slug> ISC-N)` in the project ISA (§ 13.2)."""
    want = [i for i, e in parsed["test_strategy"].items() if isinstance(e, dict) and e.get("promote") is True]
    if not want:
        return []
    repo = state.isa_repo(path)
    proj = os.path.join(repo, "ISA.md") if repo else None
    try:
        ptext = _read(proj) if proj else ""
    except OSError:
        ptext = ""
    slug = os.path.basename(os.path.dirname(os.path.realpath(path)))
    return [f"{i}: `promote: true` but the project ISA has no line `(from {slug} {i})` — copy the claim into "
            f"{'the repo' + chr(39) + 's ISA.md' if proj else 'a project ISA (this ISA is not in a repo)'}"
            for i in want if f"(from {slug} {i})" not in ptext]


# ------------------------------------------------------------------ running probes

def _probe_root(root, entry):
    """The project a probe runs in: the entry's own `root:` (a path relative to $HOME, for an ISA spanning
    several projects), else the ISA's `root`."""
    own = entry.get("root") if isinstance(entry, dict) else None
    if not own:
        return root
    own = os.path.expanduser(str(own))
    return os.path.realpath(own if os.path.isabs(own) else os.path.join(os.path.expanduser("~"), own))


def _probe_cwd(root, entry):
    base = _probe_root(root, entry)
    sub = entry.get("cwd") if isinstance(entry, dict) else None
    return os.path.normpath(os.path.join(base, os.path.expanduser(str(sub)))) if sub else base


def _batch(path, parsed, chosen, root, timeout, out):
    """Run a probe batch between two fingerprints of every root it touches.
    → (results, fp_after {root: fp}, changed {root: [paths]})."""
    roots = sorted({_probe_root(root, parsed["test_strategy"].get(i)) for i in chosen})
    before = {r: fingerprint.of(r) for r in roots}
    results = _run_probes(parsed, chosen, root, timeout)
    after = {r: fingerprint.of(r) for r in roots}
    changed = {}
    for r in roots:
        if before[r] != after[r] and fingerprint.UNCOMPUTABLE not in (before[r], after[r]):
            paths = fingerprint.changed_paths(r, before[r], after[r])
            changed[r] = paths
            out(f"probe changed the tree in {r}: {', '.join(paths) or '(files changed)'} — a probe must only "
                "observe; this run is recorded as a project change and `isa close` refuses a batch like it")
            evidence.record(path, [{"v": 2, "t": time.time(), "kind": "changed", "root": r, "paths": paths,
                                    "before": before[r], "after": after[r]}])
    return results, after, changed


def probe_env():
    """The caller's environment minus its ISA_* switches (ISA_HOME stays): a probe sees the same
    settings whoever runs `isa verify` — a model with ISA_ADVICE=off set, or a hook-free shell."""
    return {k: v for k, v in os.environ.items() if not k.startswith("ISA_") or k == "ISA_HOME"}


def _run_probes(parsed, chosen, root, timeout):
    """{isc: (code, secs, tail, tool, cwd, root)} — identical probes in the same cwd run once."""
    pr, cache, res = evidence.probes(parsed), {}, {}
    for i in chosen:
        tool = pr[i]["tool"].strip()
        cwd = _probe_cwd(root, parsed["test_strategy"].get(i))
        if (tool, cwd) not in cache:
            t0 = time.time()
            try:
                r = subprocess.run(tool, shell=True, executable="/bin/bash", cwd=cwd, capture_output=True,
                                   text=True, timeout=timeout, env=probe_env())
                code, output = r.returncode, (r.stdout or "") + (r.stderr or "")
            except subprocess.TimeoutExpired as e:
                code, output = 124, f"{e.stdout or ''}{e.stderr or ''}\n[timed out after {timeout}s]"
            except OSError as e:
                code, output = 127, f"cannot run in {cwd}: {e}"
            cache[(tool, cwd)] = (code, round(time.time() - t0, 2), output[-TAIL:])
        res[i] = cache[(tool, cwd)] + (tool, cwd, _probe_root(root, parsed["test_strategy"].get(i)))
    return res


def _record(path, rows):
    """Append rows; → their ledger ids."""
    return evidence.record(path, rows)


def _ref(path, rid):
    return f"(ledger: {rid})"


def _last_pass(path, isc, before):
    t = None
    for row in evidence.rows(path):
        if row.get("isc") == isc and row.get("ok") and row.get("run", "green") == "green" \
                and row.get("kind", "verify") in ("verify", "close") and row.get("t", 0) < before:
            t = row["t"]
    return t


def _asks_snapshot(path, parsed):
    """The asks in force at the first `isa verify` (SPEC-v2 § 11.2): removing one later needs a
    `refined:` row (rules.py)."""
    if any(r.get("kind") == "asks" for r in evidence.rows(path)):
        return
    asks = parsed["fm"].get("asks") if isinstance(parsed["fm"].get("asks"), list) else []
    k = crypt.key() if state.isa_repo(path) else None  # a committed ledger never holds the words (§ 13.5)
    evidence.record(path, [{"v": 2, "t": time.time(), "kind": "asks",
                            "asks": [crypt.tag(str(a), k) if k else str(a) for a in asks]}])


def _strategy_snapshot(path, parsed):
    if any(r.get("kind") == "strategy" for r in evidence.rows(path)):
        return
    entries = {i: {"type": e.get("type"), "kind": e.get("kind"), "tool_sha": evidence.tool_sha(e.get("tool"))
                   if e.get("tool") else None} for i, e in parsed["test_strategy"].items()}
    evidence.record(path, [{"v": 2, "t": time.time(), "kind": "strategy", "entries": entries}])


# ------------------------------------------------------------------ red-then-green (SPEC-v2 § 4.6)

RED_KINDS = lint.RED_KINDS
NO_RED = " (no red baseline)"


def named_files(tool, cwd, root):
    """{path relative to root: sha256} for every token of `tool` that names an existing file under root —
    hashed one by one, so the close can say which named file moved between the red and the green run."""
    try:
        toks = shlex.split(tool)
    except ValueError:
        toks = tool.split()
    out = {}
    for t in toks:
        t = t.strip("'\"")
        if not t or t.startswith("-") or len(t) > 300:
            continue
        p = os.path.realpath(os.path.join(cwd, os.path.expanduser(t)))
        if not os.path.isfile(p) or not (p + os.sep).startswith(os.path.realpath(root) + os.sep):
            continue
        try:
            with open(p, "rb") as f:
                out[os.path.relpath(p, root)] = "sha256:" + hashlib.sha256(f.read()).hexdigest()
        except OSError:
            continue
    return out


def red_exempt(parsed, isc):
    """None when `isc` needs a red baseline, else why it doesn't."""
    if str(parsed["fm"].get("effort", "E3")) == "E1":
        return "E1"
    e = parsed["test_strategy"].get(isc) or {}
    if not str(e.get("kind") or "").strip() and not parsed["iscs"].get(isc, (False, ""))[1].lstrip().startswith("Anti:"):
        return "kind unset"
    return lint.red_exempt_why(parsed["iscs"].get(isc, (False, ""))[1], e)


def red_baseline(path, isc, tool_sha, fp, before):
    """The latest failed red row of `isc` older than `before`, made with the same probe text and against a
    different tree (fingerprint) — the probe as written now, seen failing on other code. None if none."""
    best = None
    for r in evidence.rows(path):
        if r.get("isc") != isc or r.get("run") != "red" or r.get("ok") or r.get("t", 0) >= before:
            continue
        rfp = evidence.row_fingerprint(r)
        if r.get("tool_sha") != tool_sha or not rfp or rfp == fingerprint.UNCOMPUTABLE or rfp == fp:
            continue
        best = r
    return best


def _marks(path, parsed, results, fps, run_t):
    """{isc: " (no red baseline)"} for passing ISCs that need a baseline and have none."""
    marks = {}
    for i, (code, _secs, _tail, tool, _cwd, root) in results.items():
        if code == 0 and red_exempt(parsed, i) is None and \
                not red_baseline(path, i, evidence.tool_sha(tool), fps.get(root), run_t):
            marks[i] = NO_RED
    return marks


def _apply(path, text, results, line_nos, stamp, run_t, marks=None):
    """Tick what passed (in Feature order), untick what regressed; → (text, ticked, unticked, waiting)."""
    marks = marks or {}
    ticked, unticked = [], []
    pending = {i: r for i, r in results.items() if r[0] == 0}
    for i, (code, secs, _tail, tool, _cwd, _root) in results.items():
        p = lint.parse(text, path)
        if code != 0 and p["iscs"].get(i, (False,))[0]:
            prev = _last_pass(path, i, run_t)
            was = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(prev)) if prev else "earlier"
            text = isafile.untick(text, i)
            text = isafile.set_verification(
                text, i, f"- {i}: regressed (passed at {was}) — FAIL {stamp} — exit {code} — `{tool}`")
            unticked.append(i)
    progressed = True
    while pending and progressed:  # a dependency ticked in this run unblocks its dependents in the same run
        progressed = False
        for i in list(pending):
            p = lint.parse(text, path)
            if evidence.blocked(p, [i]):
                continue
            code, secs, _tail, tool, _cwd, _root = pending.pop(i)
            if not p["iscs"][i][0]:
                ticked.append(i)
            text = isafile.tick(text, i)
            text = isafile.set_verification(
                text, i, f"- {i}: verified {stamp} — exit 0 in {secs}s — `{tool}`{marks.get(i, '')} "
                         f"{_ref(path, line_nos[i])}")
            progressed = True
    waiting = sorted(pending)
    return text, ticked, unticked, waiting


def _finish_text(text, stamp):
    text = isafile.normalize(text)
    return isafile.fm_set(text, "updated", stamp)


# ------------------------------------------------------------------ verify

def verify(path, select=(), red=False, attest=None, cwd=None, timeout=600, out=print):
    cwd = cwd or os.getcwd()
    if state.is_project_isa(path):
        return verify_project(path, timeout, out)
    refused = _no_key(path)
    if refused:
        out(f"isa verify: {refused}")
        return 2
    try:
        text = _read(path)
    except OSError as e:
        out(f"isa verify: cannot read {path}: {e}")
        return 2
    errs = articulation_errors(path, text)
    if errs:
        out("isa verify: the ISA does not pass articulation lint yet — probes run only after it does "
            f"(`isa lint {path}`):")
        for e in errs[:12]:
            out(f"  - {e}")
        return 1
    root, text, err = resolve_root(text, cwd, path)
    if err:
        out(f"isa verify: {err}")
        return 2
    parsed = lint.parse(text, path)
    pr = evidence.probes(parsed)
    unknown = [i for i in select if i not in pr]
    if unknown:
        out(f"isa verify: not a counted leaf ISC of this ISA: {', '.join(unknown)}")
        return 2
    _strategy_snapshot(path, parsed)
    _asks_snapshot(path, parsed)
    stamp, run_t = isafile.now_iso(), time.time()
    if attest is not None:
        return _attest(path, text, parsed, pr, list(select), attest, stamp, out)
    chosen = list(select) or [i for i in parsed["counted"] if pr[i]["mechanical"]]
    for i in [i for i in chosen if not pr[i]["mechanical"]]:
        out(f"{i} SKIP  {pr[i]['type']} — self-attested: tick it with `isa verify {path} {i} --attest \"<evidence>\"`")
    mech = [i for i in chosen if pr[i]["mechanical"]]
    if not mech:
        out("nothing to run: no mechanical ISC selected")
        if text != _read(path):  # a v1 ISA just got its root
            isafile.write_atomic(path, _finish_text(text, stamp))
        _unblock(path, out)
        return 0
    results, fps, _changed = _batch(path, parsed, mech, root, timeout, out)
    rows = [{"v": 2, "t": time.time(), "isc": i, "kind": "verify", "run": "red" if red else "green",
             "tool_sha": evidence.tool_sha(tool), "ok": code == 0, "exit": code, "secs": secs, "root": r,
             "cwd": c, "fingerprint": fps.get(r), "files": named_files(tool, c, r), "tail": tail}
            for i, (code, secs, tail, tool, c, r) in results.items()]
    marks = {} if red else _marks(path, parsed, results, fps, run_t)
    line_nos = dict(zip(results, _record(path, rows)))
    logs.note(isa=path, red=bool(red), passed=sorted(i for i, r in results.items() if r[0] == 0),
              failed=sorted(i for i, r in results.items() if r[0] != 0))
    for i, (code, secs, tail, tool, c, _r) in results.items():
        if red:
            out(f"{i} {'FAIL (red, as expected)' if code else 'PASS — already green before the change: is the probe testing anything?'}"
                f"  exit {code}  {secs}s  {tool}")
        else:
            out(f"{i} {'PASS' if code == 0 else 'FAIL'}  exit {code}  {secs}s  {tool}")
            if code:
                out("\n".join("    " + line for line in tail.rstrip().splitlines()[-15:]))
    if red:
        if text != _read(path):
            isafile.write_atomic(path, _finish_text(text, stamp))
        _unblock(path, out)
        return 0
    text, ticked, unticked, waiting = _apply(path, text, results, line_nos, stamp, run_t, marks)
    for i in sorted(set(marks) & set(ticked)):
        out(f"{i}: ticked{NO_RED} — {_why_no_red(path, parsed, i, results[i][3], run_t)}")
    for i in waiting:
        b = evidence.blocked(lint.parse(text, path), [i])
        f, d, open_ = (b[0][1], b[0][2], b[0][3]) if b else ("?", "?", [])
        out(f"{i} passed but waits — Feature `{f}` depends on `{d}` (still open: {', '.join(open_)}); "
            f"it is ticked by the run after `{d}` is done")
    text = _finish_text(text, stamp)
    isafile.write_atomic(path, text)
    out(f"\nISA updated: ticked {', '.join(ticked) or '—'}, unticked {', '.join(unticked) or '—'}, "
        f"progress {isafile.progress_of(text)} — re-read the ISA before editing it.")
    _unblock(path, out, full=not select and not any(r[0] for r in results.values()))
    jev_probe_advice(path, parsed, [i for i in mech if results.get(i, (1,))[0] == 0], out)
    return 1 if any(r[0] for r in results.values()) else 0


def _unblock(path, out, full=False):
    """Clear the `blocked` items (SPEC-v2 § 4.5) this run shows fixed; report the ones still open."""
    before = problems.open_items(path)
    still = problems.reevaluate(path, full=full)
    if len(still) < len(before):
        out(f"cleared {len(before) - len(still)} blocked item(s) recorded by an earlier turn")
    if still:
        out("still blocked (from an earlier turn; `isa close` refuses until fixed):\n" + problems.describe(still))


def _attest(path, text, parsed, pr, select, evidence_text, stamp, out):
    if len(select) != 1 or not str(evidence_text).strip():
        out("usage: isa verify ISA.md ISC-N --attest \"<evidence>\"  (exactly one ISC, non-empty evidence)")
        return 2
    i = select[0]
    if pr[i]["mechanical"]:
        out(f"isa verify: {i} has a runnable probe — run `isa verify {path} {i}`; --attest is for "
            "manual / screenshot / eval criteria only")
        return 1
    entry = parsed["test_strategy"].get(i) or {}
    if str(entry.get("risk", "")).strip().lower().startswith("high"):
        out(f"isa verify: {i} is `risk: high` — it needs a mechanical probe, or the user waives it")
        return 1
    b = evidence.blocked(parsed, [i])
    if b:
        out(f"isa verify: {i} waits for Feature `{b[0][2]}` (still open: {', '.join(b[0][3])})")
        return 1
    row = {"v": 2, "t": time.time(), "isc": i, "kind": "attest", "ok": True,
           "tool_sha": evidence.tool_sha(entry.get("tool")) if entry.get("tool") else None,
           "evidence": str(evidence_text).strip()}
    [n] = _record(path, [row])
    text = isafile.tick(text, i)
    text = isafile.set_verification(text, i, f"- {i}: attested {stamp} — {row['evidence']} {_ref(path, n)}")
    text = _finish_text(text, stamp)
    isafile.write_atomic(path, text)
    out(f"{i} ATTESTED — listed to the user at close as not machine-verified\n"
        f"ISA updated: ticked {i}, progress {isafile.progress_of(text)} — re-read the ISA before editing it.")
    _unblock(path, out)
    return 0


# ------------------------------------------------------------------ close

def _no_key(path):
    """Option A (§ 13.7): a repo task ISA is verified and closed only with the key (keyed HMACs, readable quotes).
    The first command in a clone also registers the filter (and re-checks out what it can now decrypt)."""
    repo = state.isa_repo(path)
    if not repo:
        return None
    crypt.ensure_filter(repo)
    k = crypt.key()
    if not k:
        return crypt.NO_KEY
    try:
        other = crypt.unreadable(_read(path), k)
    except OSError:
        return None
    return (f"this ISA holds values encrypted under key {', '.join(other)}, not your key {crypt.keyid(k)} — "
            "`isa key import FILE` with that key") if other else None


def close(path, cwd=None, timeout=600, out=print):
    cwd = cwd or os.getcwd()
    if state.is_project_isa(path):
        out("isa close: the project ISA never closes — `isa verify ISA.md` re-proves its standing claims")
        return 2
    refused = _no_key(path)
    if refused:
        out(f"isa close: {refused}")
        return 2
    try:
        original = _read(path)
    except OSError as e:
        out(f"isa close: cannot read {path}: {e}")
        return 2
    errs = articulation_errors(path, original)
    if errs:
        out("isa close: the ISA does not pass articulation lint — fix it first:")
        for e in errs[:12]:
            out(f"  - {e}")
        return 1
    root, text, err = resolve_root(original, cwd, path)
    if err:
        out(f"isa close: {err}")
        return 2
    parsed = lint.parse(text, path)
    pr = evidence.probes(parsed)
    _strategy_snapshot(path, parsed)
    stamp, run_t = isafile.now_iso(), time.time()
    mech = [i for i in parsed["counted"] if pr[i]["mechanical"]]
    results, fps, changed = _batch(path, parsed, mech, root, timeout, out) if mech else ({}, {}, {})
    rows = [{"v": 2, "t": time.time(), "isc": i, "kind": "close", "run": "green",
             "tool_sha": evidence.tool_sha(tool), "ok": code == 0, "exit": code, "secs": secs, "root": r,
             "cwd": c, "fingerprint": fps.get(r), "files": named_files(tool, c, r), "tail": tail}
            for i, (code, secs, tail, tool, c, r) in results.items()]
    marks = _marks(path, parsed, results, fps, run_t)
    line_nos = dict(zip(results, _record(path, rows))) if rows else {}
    logs.note(isa=path, passed=sorted(i for i, r in results.items() if r[0] == 0),
              failed=sorted(i for i, r in results.items() if r[0] != 0))
    text, _ticked, _unticked, waiting = _apply(path, text, results, line_nos, stamp, run_t, marks)
    text = _finish_text(text, stamp)
    issues = [f"{i}: probe fails now (exit {results[i][0]}) — `{results[i][3]}`" for i in results if results[i][0]]
    issues += [f"a probe changed the tree in {r}: {', '.join(ps) or '(files changed)'} — the run must leave "
               "the tree unchanged to prove it" for r, ps in changed.items()]
    issues += [f"{i}: passed but waits for its Feature's dependency" for i in waiting]
    p = lint.parse(text, path)
    issues += [f"{i}: ticked without an `isa verify --attest` row" for i, _ in evidence.unattested_ticks(path, p)]
    issues += promote_issues(path, p)
    closing = isafile.fm_set(text, "phase", "complete")
    r = lint.lint(path, "close", text=closing)
    issues += [m for lvl, m in r.items if lvl == "ERROR"]
    # items blocked by an earlier turn: re-evaluated on what this close would write (its own probe rows are in
    # the ledger already); what a successful close itself resolves doesn't block it
    still = [k for k in problems.reevaluate(path, text=closing) if k[0] not in problems.CLOSE_RESOLVES]
    issues += [f"still blocked from an earlier turn: {line.strip()[2:]}"
               for line in problems.describe(still).splitlines()] if still else []
    if issues:
        out(f"isa close: not closed — {len(issues)} problem(s); the ISA file is unchanged:")
        for m in issues:
            out(f"  - {m}")
        return 1
    isafile.write_atomic(path, closing)
    # the close itself, also when no mechanical probe ran (all self-attested): Stop checks for it (problems.py)
    evidence.record(path, [{"v": 2, "t": time.time(), "kind": "closed", "probes": len(results)}])
    out(summary(path, closing, results, fps, marks, run_t) + jev_close_advice(path, closing, results, marks))
    return 0


def _why_no_red(path, parsed, i, tool, before):
    reds = [r for r in evidence.rows(path) if r.get("isc") == i and r.get("run") == "red" and r.get("t", 0) < before]
    if not reds:
        return "no `isa verify --red` run of it before the change"
    if all(r.get("ok") for r in reds):
        return "its red run passed: the probe was never seen failing — it can't fail, so it proves nothing"
    if not any(r.get("tool_sha") == evidence.tool_sha(tool) for r in reds if not r.get("ok")):
        return "the probe was edited after its failing red run"
    return "its failing red run saw the same tree (nothing changed between red and green)"


def _changed_since_red(path, isc, before):
    """Named files whose hash differs between the red baseline and the latest green row."""
    rows = evidence.rows(path)
    reds = [r for r in rows if r.get("isc") == isc and r.get("run") == "red" and not r.get("ok")]
    greens = [r for r in rows if r.get("isc") == isc and r.get("run", "green") == "green" and r.get("ok")
              and r.get("kind") in ("verify", "close")]
    if not reds or not greens:
        return []
    a, b = reds[-1].get("files") or {}, greens[-1].get("files") or {}
    return sorted(f for f in set(a) | set(b) if a.get(f) != b.get(f))


def summary(path, text, results, fps=None, marks=None, run_t=None):
    p = lint.parse(text, path)
    pr = evidence.probes(p)
    ver = p["content"].get("Verification", "")
    lines = [f"isa close: {path} — complete, progress {isafile.progress_of(text)}"]
    proven = [i for i in p["counted"] if pr[i]["mechanical"]]
    if proven:
        lines.append("Proven (every probe re-run by this close):")
        lines += [f"  - {i}: exit 0 in {results[i][1]}s — `{results[i][3]}`" for i in proven if i in results]
    fw = lambda i: str((p["test_strategy"].get(i) or {}).get("fails-when") or "").strip()  # noqa: E731
    no_red = sorted(marks or {})
    if no_red:
        lines.append("No red baseline (never seen failing — weigh them like the self-attested ones):")
        lines += [f"  - {i}: {_why_no_red(path, p, i, results[i][3], run_t or time.time())}"
                  + (f" — fails when: {fw(i)}" if fw(i) else "") for i in no_red]
    never = [i for i in proven if i not in (marks or {}) and red_exempt(p, i)]
    if never:
        lines.append("Never seen failing by design (red-exempt) — what each probe would see if the claim were false:")
        lines += [f"  - {i} ({red_exempt(p, i)}): {fw(i) or '(no fails-when written)'}" for i in never]
    exempt = [(i, red_exempt(p, i)) for i in proven if str(red_exempt(p, i) or "").lower().startswith("exempt")]
    if exempt:
        lines.append("Red run exempted by the ISA: " + "; ".join(f"{i} ({why})" for i, why in exempt))
    moved = [(i, _changed_since_red(path, i, run_t or time.time())) for i in proven if i not in (marks or {})]
    moved = [(i, fs) for i, fs in moved if fs]
    if moved:
        lines.append("Changed since red (named files that moved between the red and the green run — is the test "
                     "itself among them?):")
        lines += [f"  - {i}: {', '.join(fs)}" for i, fs in moved]
    attested = [i for i in p["counted"] if not pr[i]["mechanical"]]
    if attested:
        lines.append("Self-attested (not machine-verified — check them):")
        for i in attested:
            m = re.search(rf"^- {re.escape(i)}: attested \S+ — (.*?)(?: \(ledger: [^)]*\))?$", ver, re.M)
            lines.append(f"  - {i} ({pr[i]['type']}): {m.group(1) if m else p['iscs'][i][1]}")
    w = sorted(isafile.waived(p))
    if w:
        lines.append("Waived by the user: " + ", ".join(w))
    moved = sorted({x for r in evidence.rows(path) if r.get("kind") == "changed" for x in r.get("paths") or ["(files)"]})
    if moved:
        lines.append("Changed by probe (at some run of this ISA): " + ", ".join(moved))
    unc = sorted({r for r, fp in (fps or {}).items() if fp == fingerprint.UNCOMPUTABLE})
    if unc:
        lines.append("Fingerprint uncomputable (tree changes by probes not detectable): " + ", ".join(unc))
    goal = re.findall(r"^- Goal: (yes|no)\b.*$", ver, re.M)
    if goal:
        lines.append(re.findall(r"^- Goal: .*$", ver, re.M)[-1])
    return "\n".join(lines)


# ------------------------------------------------------------------ lint

def lint_cmd(args, out=print):
    """`isa lint [--close | --moment M] FILE…`: an ISA under the ISA home gets its engine-owned fields
    recomputed on disk first (isafile.normalize); other files (examples) are only read."""
    moment = "auto"
    if args[:1] == ["--close"]:
        moment, args = "close", args[1:]
    elif args[:1] == ["--moment"] and len(args) > 1:
        moment, args = args[1], args[2:]
    total = 0
    for p in args:
        try:
            text = _read(p)
        except OSError as e:
            out(f"{p}: cannot read ({e})")
            total += 1
            continue
        if state.isa_repo(p) and crypt.ensure_filter(state.isa_repo(p)):
            text = _read(p)  # the clone's first command: the filter decrypted it
        if state.is_project_isa(p):
            errs = lint_project(p, text)
            total += len(errs)
            out(f"{p}: {'ok' if not errs else f'{len(errs)} error(s)'} (project ISA)")
            for e in errs:
                out(f"  ERROR: {e}")
            continue
        norm = isafile.normalize(text)
        if norm != text and state.is_master_isa(p):
            isafile.write_atomic(p, norm)
        r = lint.lint(p, moment, text=norm)
        if state.is_master_isa(p):
            parsed = lint.parse(norm, p)
            errs, warns = rules.check(p, parsed)
            for m in errs:
                r.err(m)
            for m in warns:
                r.warn(m)
            for i in parsed["counted"]:
                reds = [x for x in evidence.rows(p) if x.get("isc") == i and x.get("run") == "red"]
                if reds and reds[-1].get("ok"):
                    r.warn(f"{i}: its probe passed its red run (before the change) — a probe that can't fail "
                           "proves nothing; tighten it, or mark the entry `red: exempt — <why>`")
            _unblock(p, out)
        total += r.errors
        out(f"{p}: {'ok' if not r.errors else f'{r.errors} error(s)'}")
        for level, msg in r.items:
            out(f"  {level}: {msg}")
    return 1 if total else 0

# ------------------------------------------------------------------ Jev advice (SPEC-v2 § 11.2, never blocking)

def _doubt():
    return config.number("jev_doubt")[0]


def _jev_line(results, out):
    """At most one `Jev:` line per command for calls that were not served (the ON block asks the model
    to relay it); timeouts and Jev being switched off say nothing."""
    msg = next((jev.message(r) for r in results if jev.message(r)), None)
    if msg:
        out("Jev: " + msg)


def jev_probe_advice(path, parsed, passed, out=print):
    """First `isa verify` of a probe that can't be seen failing first (red-exempt): ask Jev once per
    (ISC, probe text) whether it would fail if the claim were false; warn below _doubt()."""
    if not jev.enabled():
        return
    pr = evidence.probes(parsed)
    cache = {(r.get("isc"), r.get("tool_sha")): r for r in evidence.rows(path)
             if r.get("kind") == "advice" and r.get("question") == "isa-probe"}
    exempt = [(i, red_exempt(parsed, i)) for i in passed if red_exempt(parsed, i)]
    sha = {i: evidence.tool_sha(pr[i]["tool"]) for i, _ in exempt}
    todo = [(i, why) for i, why in exempt if (i, sha[i]) not in cache]
    if todo:
        payloads = [("isa-probe", {"isc": i, "claim": parsed["iscs"][i][1], "probe": pr[i]["tool"].strip(),
                                   "why_exempt": why, "fails_when": str((parsed["test_strategy"].get(i) or {})
                                                                        .get("fails-when") or "(not written)")})
                    for i, why in todo]
        results = jev.ask_many(payloads, jev.CMD_DEADLINE, cmd="verify", isa=path)
        rows = [{"v": 2, "t": time.time(), "kind": "advice", "question": "isa-probe", "isc": i,
                 "tool_sha": sha[i], "answer": r["answer"]} for (i, _), r in zip(todo, results) if r["served"]]
        if rows:
            evidence.record(path, rows)
            cache.update({(r["isc"], r["tool_sha"]): r for r in rows})
        _jev_line(results, out)
    for i, _ in exempt:
        row = cache.get((i, sha[i]))
        if row and row.get("answer") is not None and row["answer"] < _doubt():
            out(f"Jev doubts {i}'s probe would fail if the claim were false ({row['answer']:g}) — advisory: "
                "tighten it, or say why it holds in Decisions")


CLAIM_MAX = 30


def _claim_items(path, p, results, marks):
    """The weak ticks a close asks Jev about (future/JEV.md #1): self-attested ones (evidence: the attest
    text) and ones never seen failing (evidence: the probe, its exit code and its output). A red-then-green
    tick is left alone."""
    pr = evidence.probes(p)
    attested = evidence.attested(path)
    items = []
    for i in p["counted"]:
        if not p["iscs"][i][0]:
            continue
        ts = p["test_strategy"].get(i) or {}
        if not pr[i]["mechanical"]:
            ev = str((attested.get(i) or {}).get("evidence") or "(no attest text)")
        elif i in (marks or {}) and i in results:
            code, _secs, tail, tool = results[i][:4]
            ev = f"command: {tool}\nexit {code}\noutput (last lines):\n{(tail or '').strip()[-1500:] or '(none)'}"
        else:
            continue
        items.append(("isa-claim", {"isc": i, "claim": p["iscs"][i][1], "threshold": str(ts.get("threshold") or ""),
                                    "how": str(ts.get("check") or ts.get("type") or ""), "evidence": ev}))
    return items[:CLAIM_MAX]


def jev_close_advice(path, text, results=None, marks=None):
    """`isa close`: Jev on the goal, on each ask line, and on each weak tick's evidence — shown, recorded,
    never blocking."""
    if not jev.enabled():
        return ""
    p = lint.parse(text, path)
    ver = p["content"].get("Verification", "")
    evidence_text = "\n".join(f"- [{'x' if p['iscs'][i][0] else ' '}] {i}: {p['iscs'][i][1]}" for i in p["iscs"]) \
        + "\n\n" + ver
    asks = p["fm"].get("asks") if isinstance(p["fm"].get("asks"), list) else []
    items = [("isa-goal", {"stated_goal": str(p["fm"].get("stated_goal") or ""),
                           "goal": p["content"].get("Goal", "").strip(), "evidence": evidence_text})]
    for n, a in enumerate(asks, 1):
        m = re.search(rf"^- Ask {n}: (.*)$", ver, re.M)
        items.append(("isa-ask", {"ask": str(a), "line": m.group(1) if m else "(no line)", "evidence": evidence_text}))
    items += _claim_items(path, p, results or {}, marks)
    results = jev.ask_many(items, jev.CMD_DEADLINE, cmd="close", isa=path)
    lines = []
    for n, ((preset, payload), r) in enumerate(zip(items, results)):
        label = "goal delivered" if preset == "isa-goal" else f"{payload['isc']} evidence supports the claim" \
            if preset == "isa-claim" else f"Ask {n} (\"{payload['ask'][:60]}\") met"
        if r["served"]:
            flag = " — check it" if r["answer"] < _doubt() else ""
            lines.append(f"  - {label}: {r['answer']:g}{flag}")
        else:
            lines.append(f"  - {label}: not judged (Jev unavailable: {r['reason']})")
    evidence.record(path, [{"v": 2, "t": time.time(), "kind": "advice", "question": preset, "served": r["served"],
                            "answer": r["answer"], "reason": None if r["served"] else r["reason"],
                            **({"isc": payload["isc"]} if preset == "isa-claim" else {})}
                           for (preset, payload), r in zip(items, results)])
    msgs = []
    _jev_line(results, msgs.append)
    return "\nJev (advisory — never blocks the close):\n" + "\n".join(lines) + ("\n" + "\n".join(msgs) if msgs else "")


# ------------------------------------------------------------------ migrate (SPEC-v2 § 13.9)

OLD_REF = re.compile(r"\(ledger: [^)#]*#L(\d+)\)")


def _migratable():
    """[(old ISA path, repo)] for every ISA under ISA_HOME whose `root` lies inside a git repo."""
    out, home = [], state.home()
    if not os.path.isdir(home):
        return out
    for key in sorted(os.listdir(home)):
        d = os.path.join(home, key)
        if key == "_state" or not os.path.isdir(d) or os.path.islink(d):
            continue
        for slug in sorted(os.listdir(d)):
            folder = os.path.join(d, slug)
            p = os.path.join(folder, "ISA.md")
            if os.path.islink(folder) or not os.path.isfile(p):
                continue
            root = state.frontmatter(p).get("root")
            if not root:
                continue
            root = os.path.expanduser(str(root))
            repo = state.repo_root(root) if os.path.isabs(root) and os.path.isdir(root) else None
            if repo:
                out.append((p, repo))
    return out


def migrate(args, out=print):
    dry = "--dry-run" in args
    todo = _migratable()
    if not todo:
        out("isa migrate: nothing to move (no ISA under the ISA home has a `root` inside a git repo)")
        return 0
    k = crypt.key()
    if not k and not dry:
        out(f"isa migrate: {crypt.NO_KEY}")
        return 2
    moved, repos = {}, set()
    for old, repo in todo:
        slug = os.path.basename(os.path.dirname(old))
        new = os.path.join(repo, ".isa", slug, "ISA.md")
        if os.path.exists(os.path.dirname(new)):
            out(f"skip  {old} — {os.path.dirname(new)} exists")
            continue
        out(f"{'would move' if dry else 'move'}  {os.path.dirname(old)} → {os.path.dirname(new)}")
        if dry:
            continue
        old_ledger = evidence.ledger_path(old)
        old_rows = []
        try:
            with open(old_ledger) as f:
                for line in f:
                    try:
                        old_rows.append(json.loads(line))
                    except ValueError:
                        old_rows.append(None)
        except OSError:
            pass
        text = _read(old)
        words = quotes.spans(text)
        prompts = [r.get("text") or "" for r in project_prompts(state.project_key(repo))]
        os.makedirs(os.path.join(repo, ".isa"), exist_ok=True)
        shutil.move(os.path.dirname(old), os.path.dirname(new))
        for junk in (".stated_goal.sha256", ".projects.json"):
            with contextlib.suppress(OSError):
                os.remove(os.path.join(os.path.dirname(new), junk))
        ids, new_rows = {}, []
        for n, row in enumerate(old_rows, 1):
            if not isinstance(row, dict):
                continue
            row = {kk: vv for kk, vv in row.items() if kk != "id"}
            for kk in ("root", "cwd"):
                if isinstance(row.get(kk), str) and os.path.isabs(row[kk]):
                    row[kk] = evidence._rel(row[kk], repo)
            for kk in evidence.REDACTED:
                if isinstance(row.get(kk), str):
                    row[kk] = quotes.redact(row[kk], words)
            if row.get("kind") == "asks":
                row["asks"] = [a if str(a).startswith("hmac:") else crypt.tag(str(a), k) for a in row.get("asks") or []]
            row.setdefault("machine", evidence.MACHINE)
            row["id"] = evidence.row_id(row)
            ids[n] = row["id"]
            new_rows.append(row)
        with open(evidence.ledger_path(new), "w") as f:
            for row in new_rows:
                f.write(json.dumps(row) + "\n")
        with contextlib.suppress(OSError):
            os.remove(old_ledger)
        text = OLD_REF.sub(lambda m: f"(ledger: {ids.get(int(m.group(1)), '?')})", text)
        rel = os.path.relpath(os.path.realpath(os.path.expanduser(str(state.frontmatter(new).get("root")))),
                              os.path.realpath(repo))
        text = isafile.fm_set(text, "root", "." if rel == "." else rel)
        isafile.write_atomic(new, text)
        verified = [w for w in words if any(w in p for p in prompts)]
        if verified:
            rules.mark_verified(new, verified)
        moved[os.path.realpath(old)] = os.path.realpath(new)
        repos.add(repo)
    if dry:
        return 0
    for repo in sorted(repos):
        crypt.setup_repo(repo, out)
        project_isa(repo, out)
    _rebind(moved)
    _drop_links(moved)
    out(f"isa migrate: {len(moved)} ISA(s) moved into {len(repos)} repo(s); nothing committed")
    return 0


def _rebind(moved):
    d = os.path.join(state.home(), "_state", "sessions")
    for name in os.listdir(d) if os.path.isdir(d) else []:
        p = os.path.join(d, name)
        try:
            with open(p) as f:
                st = json.load(f)
        except (OSError, ValueError):
            continue
        changed = False
        if st.get("bound") in moved:
            st["bound"], changed = moved[st["bound"]], True
        hist = [moved.get(h, h) for h in st.get("bound_history") or []]
        if hist != (st.get("bound_history") or []):
            st["bound_history"], changed = hist, True
        if changed:
            with open(p + ".tmp", "w") as f:
                json.dump(st, f)
            os.replace(p + ".tmp", p)


def _drop_links(moved):
    """Links `note_project` made in other projects' folders to a moved ISA folder (§ 13.1: they go away)."""
    home = state.home()
    olds = {os.path.dirname(o) for o in moved}
    for key in os.listdir(home):
        d = os.path.join(home, key)
        if not os.path.isdir(d) or key == "_state":
            continue
        for slug in os.listdir(d):
            p = os.path.join(d, slug)
            if os.path.islink(p) and os.readlink(p) in olds:
                os.remove(p)


# ------------------------------------------------------------------ migrate --home (spec 2026-10-06 § A.5)

HOME_COMMIT = 'git rm -r --cached .isa && git add .gitattributes && git commit -m "Move task ISAs out of git"'
ENC_VALUE = re.compile(r'"?' + crypt.TOKEN.pattern + r'"?')


def _plain(text, k):
    """`text` with every `enc:v1:` value opened by the key; one it can't open (no key, another key) → `""`.
    → (text, how many were blanked)."""
    if "enc:v1:" not in text:
        return text, 0
    text = crypt.smudge(text, k)
    return ENC_VALUE.subn('""', text)


def _home_rows(lines, repo, tags):
    """Ledger rows of a repo ISA as a home ledger holds them: `root` / `cwd` absolute, the `asks` snapshot
    verbatim (`tags`: hmac tag → ask). Row ids are kept, so every `(ledger: <id>)` line still resolves."""
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        for kk in ("root", "cwd"):
            if isinstance(row.get(kk), str) and not os.path.isabs(row[kk]):
                row[kk] = os.path.normpath(os.path.join(repo, row[kk]))
        if row.get("kind") == "asks":
            row["asks"] = [tags.get(a, a) for a in row.get("asks") or []]
        out.append(json.dumps(row))
    return out


def _drop_attributes(repo, dry, out):
    path = os.path.join(repo, ".gitattributes")
    try:
        with open(path) as f:
            have = f.read().splitlines()
    except OSError:
        return
    keep = [x for x in have if x.strip() not in crypt.ATTRIBUTES]
    if len(keep) == len(have):
        return
    empty = not any(x.strip() for x in keep)
    out(f".gitattributes: drop the {len(have) - len(keep)} `.isa` line(s)" + (", then the empty file" if empty else ""))
    if dry:
        return
    if empty:
        os.remove(path)
    else:
        isafile.write_atomic(path, "\n".join(keep) + "\n")


def migrate_home(args, out=print):
    """`isa migrate --home [--dry-run]`, run inside a repo: move every `<repo>/.isa/<slug>/` to
    `ISA_HOME/<project-key>/<slug>/`, its `evidence.jsonl` to the home ledger, `root:` absolute, values still
    encrypted on disk opened with the key (or blanked), sessions rebound, the `.isa` git filter removed.
    Commits nothing; prints the commit for the user. → 0, 1 when a slug was skipped, 2 outside a repo."""
    dry = "--dry-run" in args
    repo = state.repo_root(os.getcwd())
    if not repo:
        out("isa migrate --home: not inside a git repo (run it at the repo whose .isa/ should move home)")
        return 2
    src_dir, dest_dir = os.path.join(repo, ".isa"), os.path.join(state.home(), state.project_key(repo))
    slugs = sorted(s for s in (os.listdir(src_dir) if os.path.isdir(src_dir) else [])
                   if os.path.isdir(os.path.join(src_dir, s)) and not os.path.islink(os.path.join(src_dir, s)))
    if dry:
        out("isa migrate --home (dry run: nothing is changed)")
    k = crypt.key()
    moved, skipped = {}, []
    for slug in slugs:
        src, dest = os.path.join(src_dir, slug), os.path.join(dest_dir, slug)
        if os.path.lexists(dest):
            skipped.append(slug)
            out(f"skip  {slug} — {dest} exists; it stays in {src_dir}/")
            continue
        out(f"move  {src} → {dest}")
        old_isa = os.path.join(src, "ISA.md")
        texts = {}
        for d, _, files in os.walk(src):
            for n in files:
                p = os.path.join(d, n)
                if n.endswith(".md"):
                    text, blanked = _plain(_read(p), k)
                    texts[os.path.relpath(p, src)] = text
                    if blanked:
                        out(f"  {slug}/{os.path.relpath(p, src)}: {blanked} encrypted value(s) "
                            f"{'blanked' if not dry else 'would be blanked'} to \"\" "
                            f"({'no key' if not k else 'not under your key'})")
        if dry:
            continue
        real_old = os.path.realpath(old_isa)
        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(src, dest)
        new_isa = os.path.join(dest, "ISA.md")
        for rel, text in texts.items():
            if rel == "ISA.md":
                root = isafile.fm(text).get("root")
                if isinstance(root, str) and root and not os.path.isabs(os.path.expanduser(root)):
                    text = isafile.fm_set(text, "root", os.path.normpath(os.path.join(repo, root)))
            isafile.write_atomic(os.path.join(dest, rel), text)
        ledger = os.path.join(dest, "evidence.jsonl")
        if os.path.isfile(ledger):
            asks = isafile.fm(texts.get("ISA.md", "")).get("asks")
            tags = {crypt.tag(str(a), k): str(a) for a in asks} if k and isinstance(asks, list) else {}
            with open(ledger) as f:
                rows = _home_rows(f, repo, tags)
            target = evidence.ledger_path(new_isa)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "a") as f:
                f.writelines(r + "\n" for r in rows)
            os.remove(ledger)
        moved[real_old] = os.path.realpath(new_isa)
    _drop_attributes(repo, dry, out)
    r = crypt._git(repo, "config", "--local", "--get-regexp", r"^filter\.isa\.")
    if r is not None and r.returncode == 0 and r.stdout.strip():
        out("git config: remove the filter.isa section")
        if not dry:
            crypt._git(repo, "config", "--local", "--remove-section", "filter.isa")
    if not dry:
        _rebind(moved)
    out(f"isa migrate --home: {len(moved) if not dry else len(slugs) - len(skipped)} ISA folder(s) "
        f"{'would move' if dry else 'moved'} to {dest_dir}/, {len(skipped)} skipped; nothing committed")
    if skipped:
        out(f"  skipped (already at home): {', '.join(skipped)} — move or delete them by hand before committing")
    out("Commit the removal from git yourself:")
    out(HOME_COMMIT)
    return 1 if skipped else 0
