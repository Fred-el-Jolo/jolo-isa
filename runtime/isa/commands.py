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
import hashlib
import json
import os
import re
import shlex
import subprocess
import time

from . import config, evidence, fingerprint, isafile, jev, lint, logs, problems, rules, specdoc, state

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
    `root` is absolute (spec 2026-10-06 § A.1)."""
    root = isafile.fm(text).get("root")
    if root:
        root = os.path.expanduser(str(root))
        if not os.path.isabs(root):
            return None, text, f"root `{root}` is relative — write the project's absolute path"
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
    opts, words, i = {"--tier": None, "--goal": None, "--spec": None, "--plan": None}, [], 0
    path_only = "--path-only" in args
    no_spec = "--no-spec" in args
    args = [a for a in args if a not in ("--path-only", "--no-spec")]
    while i < len(args):
        if args[i] in opts and i + 1 < len(args):
            opts[args[i]] = args[i + 1]
            i += 2
        else:
            words.append(args[i])
            i += 1
    slug = " ".join(words) or "task"
    path = state.new_isa_path(cwd, slug)
    if path_only:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        out(path)
        return 0
    if len([k for k in ("--spec", "--plan") if opts[k]]) + no_spec > 1:
        out("isa new: --spec, --plan and --no-spec exclude each other — pick one")
        return 2
    seeded, link = None, opts["--spec"] or opts["--plan"]
    if link:
        seeded, err = _seed(link, "--spec" if opts["--spec"] else "--plan", cwd)
        if err:
            out(f"isa new: {err}")
            return 1
    tier = (opts["--tier"] or (seeded or {}).get("tier") or "E3").upper()
    if tier not in lint.TIER_ARTICULATION:
        out(f"isa new: --tier must be E1..E5, got `{opts['--tier']}`")
        return 2
    root, err = root_for(cwd)
    if err:
        out(f"isa new: {err}")
        return 2
    prompts = project_prompts(state.project_key(cwd))
    goal, comment, source = None, None, prompts[-1] if prompts else None
    if seeded and opts["--goal"] is None and seeded["goal"]:
        goal = seeded["goal"]  # verbatim from the document: lint checks it against that file (§ B.5)
    elif opts["--goal"] is not None:
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
    stamp = isafile.now_iso()
    folder = os.path.basename(os.path.dirname(path))
    body, n = [], 0
    if seeded:
        stored = _link_text(seeded, link, root)
        body, n = _seed_body(seeded, stored, root)
    lines = ["---", 'task: ""', f"slug: {folder}", f"effort: {tier}", "phase: observe", f"progress: 0/{n}",
             f"started: {stamp}", f"updated: {stamp}", f"root: {isafile._yaml_value(root)}"]
    if seeded:
        lines.append(f"{'plan' if seeded['step'] else 'spec'}: {stored}")
    lines.append(f"stated_goal: {isafile._yaml_value(goal)}")
    if goal is not None:
        lines.append("stated_goal_source: " + ("spec" if seeded and opts["--goal"] is None else "prompt"))
    if comment:
        lines.append(comment)
    # SPEC-v2 § 11.2: no model call — the model lists the asks; lint checks each is a verbatim span
    lines += ["asks: []", "# asks: list each explicit ask of the prompt as a verbatim span (lint checks them)"]
    lines += ["---", ""]
    if no_spec:  # the user's "no spec" (spec 2026-10-06 § 5.4): the flow is E1's, the row records why
        body = ["## Decisions", "", f"- {time.strftime('%Y-%m-%d %H:%M')}: no-spec: the user's call", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    isafile.write_atomic(path, "\n".join(lines + body))
    if seeded:
        out(f"Seeded from {stored}: {n} draft criteria — rewrite each as an atomic, probe-able end state, add an "
            "`Anti:` ISC, and fill each Test Strategy entry (type, kind, check, threshold, tool), keeping its "
            "`anchors_to`.")
        if seeded["constraints"]:
            out(f"Constraints ({_rel(seeded['spec_path'], root)}):\n"
                + "\n".join(f"- {c}" for c in seeded["constraints"]))
    project_isa(state.doc_root(cwd), out)  # the project ISA, when it has none yet (spec 2026-10-06 § A.4)
    logs.note(isa=path)
    out(path)
    return 0


def _seed(link, flag, cwd):
    """→ (seed, None) for a link `isa new` may start from, or (None, why not): the document is the kind the flag
    names, it (and a plan's spec) reads as acked now, and a step's `after` steps are done (spec § 5.4, § 5.5)."""
    try:
        s = specdoc.seed(link, root=cwd)
    except ValueError as e:
        return None, str(e)
    if (flag == "--plan") != bool(s["step"]):
        return None, f"{link} is a {'plan' if s['step'] else 'spec'} — use {'--plan' if s['step'] else '--spec'}"
    for p in [s["path"]] + ([s["spec_path"]] if s["step"] else []):
        if specdoc.acked(p):
            continue
        with open(p, encoding="utf-8") as f:
            h = specdoc.acked_hash(f.read())
        if h:
            return None, (f"{_tilde(p)} changed since its ack (#{h} in its status line) — ask the user to "
                          "acknowledge it again")
        return None, f"{_tilde(p)} is not acknowledged yet — ask the user's ack first"
    if s["open_after"]:
        return None, f"{s['step']} comes after {', '.join(s['open_after'])}, still open — finish it first"
    return s, None


def _tilde(p):
    h = os.path.expanduser("~")
    return "~" + p[len(h):] if p == h or p.startswith(h + os.sep) else p


def _rel(path, root):
    rel = os.path.relpath(path, root)
    return path if rel.startswith("..") else rel


def _link_text(s, link, root):
    """The link as the ISA stores it: the document relative to the ISA's `root:` (absolute outside it)."""
    frag = str(link).partition("#")[2].strip()
    return _rel(s["path"], root) + (f"#{frag}" if frag else "")


def _seed_body(s, stored, root):
    """The scaffold of a linked ISA: pointer lines for the context the spec owns, the Goal, one draft criterion
    per seed (anchored in its Test Strategy entry), the step's Review focus lines (spec § B.5)."""
    sids = sorted({a.split(":")[0] for a, _ in s["criteria"] if ":" in a}, key=lambda x: int(x[1:]))
    if s["step"]:
        pointer = f"See {_rel(s['spec_path'], root)}" + (f"#{','.join(sids)}" if sids else "") + f" (step {stored})"
    else:
        pointer = f"See {stored}"
    seeds = s["criteria"] + [(s["step"], t) for t in s["review_focus"]]
    body = []
    for name in ("Problem", "Vision", "Out of Scope", "Constraints"):
        body += [f"## {name}", "", pointer, ""]
    body += ["## Goal", "", s["goal"] or "", "", "## Criteria", ""]
    body += [f"- [ ] ISC-{i}: {t}" for i, (_, t) in enumerate(seeds, 1)]
    body += ["", "## Test Strategy", "", "```yaml"]
    for i, (anchor, _) in enumerate(seeds, 1):
        body += [f"- isc: ISC-{i}", f"  anchors_to: \"{anchor}\""]
    body += ["```", ""]
    return body, len(seeds)


PROJECT_SKELETON = """---
kind: project
task: "{task}"
effort: E3
started: {stamp}
updated: {stamp}
---

## Problem

The living spec of `{name}`: the constraints and standing claims its code must keep satisfying. Task ISAs live in
`~/.isa/<project>/`, never committed; a criterion that must hold forever is promoted here (`promote: true`).
"""


def project_isa(root, out=print):
    """The project ISA at a doc root (`state.doc_root`, spec 2026-10-06 § A.4): created as a skeleton by the
    first `isa new` or the first spec written; an existing `ISA.md` of another kind is never touched."""
    path = os.path.join(root, "ISA.md")
    if os.path.exists(path):
        if state.frontmatter(path).get("kind") != "project":
            out(f"isa: {path} exists and is not a project ISA (no `kind: project`) — left untouched; this project "
                "gets no project ISA")
        return
    os.makedirs(root, exist_ok=True)
    name = os.path.basename(root)
    committed = " — commit it with the code" if state.repo_root(root) == os.path.realpath(root) else ""
    isafile.write_atomic(path, PROJECT_SKELETON.format(task=f"Living spec of {name}", stamp=isafile.now_iso(), name=name))
    out(f"isa: created the project ISA {path} (kind: project{committed})")


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
    """`promote: true` criteria of a task ISA with no line `(from <slug> ISC-N)` in the project ISA of the repo
    holding its `root:` (spec 2026-10-06 § A.4)."""
    want = [i for i, e in parsed["test_strategy"].items() if isinstance(e, dict) and e.get("promote") is True]
    if not want:
        return []
    proj = state.project_isa_of(path)
    try:
        ptext = _read(proj) if proj else ""
    except OSError:
        ptext = ""
    slug = os.path.basename(os.path.dirname(os.path.realpath(path)))
    return [f"{i}: `promote: true` but the project ISA has no line `(from {slug} {i})` — copy the claim into "
            f"{proj if proj else 'a project ISA (this ISA' + chr(39) + 's root is not in a git repo)'}"
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
    evidence.record(path, [{"v": 2, "t": time.time(), "kind": "asks", "asks": [str(a) for a in asks]}])


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

def close(path, cwd=None, timeout=600, out=print):
    cwd = cwd or os.getcwd()
    if state.is_project_isa(path):
        out("isa close: the project ISA never closes — `isa verify ISA.md` re-proves its standing claims")
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
    stale = _stale_docs(parsed["fm"], root)
    if stale:  # nothing is run or written for a spec or plan the user has not acknowledged as it is now
        out("isa close: not closed — the ISA file is unchanged:")
        for m in stale:
            out(f"  - {m}")
        return 1
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
    # the done marks, after the proof and before `complete`: a mark that can't be written leaves the ISA open
    try:
        written = done_marks(path, p, root)
    except (ValueError, OSError) as e:
        out(f"isa close: not closed — {e}; the ISA file is unchanged")
        return 1
    isafile.write_atomic(path, closing)
    # the close itself, also when no mechanical probe ran (all self-attested): Stop checks for it (problems.py)
    evidence.record(path, [{"v": 2, "t": time.time(), "kind": "closed", "probes": len(results)}])
    done = ("\nDone marks written (spec § B.6):\n" + "\n".join(f"  - {_rel(f, root)}: {ln}" for f, ln in written)
            if written else "")
    out(summary(path, closing, results, fps, marks, run_t) + done + jev_close_advice(path, closing, results, marks))
    return 0


def _doc_links(fm):
    return [(key, str(x)) for key in ("spec", "plan")
            for x in (fm.get(key) if isinstance(fm.get(key), list) else [fm.get(key)] if fm.get(key) else [])]


def _stale_docs(fm, root):
    """Why each spec or plan the ISA links to does not read as acknowledged as it is now (spec § 5.5 step 8)."""
    out = []
    for key, link in _doc_links(fm):
        try:
            files = specdoc.link_files(link, root=root)
        except ValueError as e:
            out.append(f"`{key}: {link}` — {e}")
            continue
        for f in files:
            text = _read(f)
            if specdoc.ack_holds(text):
                continue
            kind = specdoc.parse(text)["kind"]
            if specdoc.STATUS_ACKED.match(specdoc.status_line(text) or "") or \
                    specdoc.STATUS_DONE.match(specdoc.status_line(text) or ""):
                out.append(f"{_tilde(f)}: {kind} changed since its ack — ask the user to acknowledge it again")
            else:
                out.append(f"{_tilde(f)}: {kind} not acknowledged yet — ask the user's ack first")
    return out


def done_marks(path, p, root):
    """After a passing close (spec § B.6): tick each linked bullet whose anchored ISCs all passed (a waived or
    unticked one keeps it open), write the sections' `Done:` lines, and tick a linked plan step once every bullet
    it covers is ticked. → [(file, line written)]."""
    fm = p["fm"]
    slug = str(fm.get("slug") or os.path.basename(os.path.dirname(path)))
    date = time.strftime("%Y-%m-%d")
    by_tag = {}
    for i, e in p["test_strategy"].items():
        for t in re.split(r"[,\s]+", str(e.get("anchors_to") or "")):
            if t and i in p["leaves"]:
                by_tag.setdefault(t, []).append(i)
    proven = lambda s, a: bool(by_tag.get(f"{s}:{a}")) and all(  # noqa: E731
        i in p["counted"] and p["iscs"][i][0] for i in by_tag[f"{s}:{a}"])
    specs, steps = {}, {}
    for _key, link in _doc_links(fm):
        files, bullets = specdoc.link_files(link, root=root), specdoc.resolve(link, root=root)
        mine = specs.setdefault(files[-1], [])
        mine += [b for b in bullets if proven(*b) and b not in mine]
        if len(files) == 2:  # a plan link: `#P<n>`, in the plan files[0] over the spec files[-1]
            steps.setdefault(files[0], []).append((link.partition("#")[2].strip(), files[-1], bullets))
    written = []
    for f, bullets in specs.items():
        written += [(f, ln) for ln in specdoc.mark_done(f, bullets, slug, date)]
    for f, items in steps.items():
        ticked = []
        for pid, sp, bullets in items:
            secs = specdoc.parse(_read(sp))["sections"]
            if all(secs[s]["bullets"][a]["ticked"] for s, a in bullets):
                ticked.append(pid)
        written += [(f, ln) for ln in specdoc.mark_done(f, ticked, slug, date)]
    return written


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
