"""Mechanical check of ISA files against skill/ISA/References/IsaFormat.md.

Covers only what a script can decide: frontmatter, section order, the tier
gate's section list, anti-criteria, Test Strategy / Features shape and
coverage, `progress`, and the close rules. Judgment calls (atomicity, the
Splitting Test, whether the Goal line is honest) stay with CheckCompleteness.

Standard library only (YAML via `yamlish`). Entry points: `lint(path, moment)`
returns a Report; `main(argv)` is the `isa lint` command.
"""
import re
import sys

from . import yamlish

SECTIONS = [
    "Problem", "Vision", "Out of Scope", "Principles", "Constraints",
    "Dependencies", "Goal", "Criteria", "Bridge Criteria", "Test Strategy",
    "Features", "Decisions", "Changelog", "Verification",
]
CRITERIA_ALIASES = {"ISC Criteria": "Criteria", "IDEAL STATE CRITERIA": "Criteria"}
RECORD = {"Decisions", "Changelog", "Verification"}
ELEVEN = ["Problem", "Vision", "Out of Scope", "Principles", "Constraints",
          "Goal", "Criteria", "Test Strategy", "Features"]  # + Dependencies/Bridge when linked
TIER_ARTICULATION = {
    "E1": ["Goal", "Criteria"],
    "E2": ["Problem", "Goal", "Criteria", "Test Strategy"],
    "E3": ["Problem", "Vision", "Out of Scope", "Constraints", "Goal",
           "Criteria", "Features", "Test Strategy"],
    "E4": ELEVEN,
    "E5": ELEVEN,
}
CORE = ["task", "slug", "effort", "phase", "progress", "started", "updated"]
PHASES = {"observe", "think", "plan", "build", "execute", "verify", "learn", "complete"}
TS_KEYS = {"isc", "anchors_to", "type", "check", "threshold", "tool",
           "property", "generator", "runs", "cwd", "risk", "root", "kind", "red", "class"}
FEATURE_KEYS = {"name", "description", "satisfies", "depends_on", "parallelizable"}
# Test Strategy types a machine can't run: their ticks are self-attested (evidence.py)
SELF_ATTESTED = {"manual", "screenshot", "eval"}
# a probe that still holds a placeholder can't be run as written: `<session-id>`, `…`
PLACEHOLDER = re.compile(r"<[A-Za-z_][\w -]*>|…")

# ISAs started before this date follow the v1 rules where SPEC-v2 § 8 softens a new rule for them
V2_SINCE = "2026-10-02"

# SPEC-v2 § 6.1: an entry's `kind:` sets the minimum probe type
KINDS = {"behaviour", "behavior", "http", "visual", "file", "config", "schema", "doc", "decision", "regression"}
KIND_REFUSES = {  # kind → (refused types, grep-only refused)
    "behaviour": ({"manual", "screenshot", "eval"}, True), "behavior": ({"manual", "screenshot", "eval"}, True),
    "http": ({"manual", "screenshot", "eval"}, True), "visual": (set(), True), "file": (set(), False),
    "config": ({"manual"}, False), "schema": ({"manual"}, True), "doc": (set(), False),
    "decision": (set(), False), "regression": ({"manual", "screenshot", "eval"}, False),
}
GREP_ONLY = {"grep", "egrep", "fgrep", "rg", "test", "[", "cat", "head", "tail", "wc"}
# SPEC-v2 § 6.2: these words in an ISC or its probe force a `risk:` declaration (they also match ordinary code)
RISK_WORDS = re.compile(r"\b(secret|token|credential|password|auth|login|permission|payment|billing|money|invoice|"
                        r"deploy|prod|production|publish|release|push)\b", re.I)
SHAPE_ROWS = {
    "finding": re.compile(r"finding: .+ — (adopted|rebutted|deferred) \(.+\)"),
    "repro-bypass": re.compile(r"repro-bypass: (pure-additive|non-isolable|repro would cause damage) — \S"),
}

ISC_RE = re.compile(r"^\s*- \[( |x|X)\] (ISC-\d+(?:\.\d+)*): ?(.*)$")
SLUG_RE = re.compile(r"^\d{8}-\d{6}_[a-z0-9-]+$")


class Report:
    def __init__(self, path):
        self.path, self.items = path, []

    def err(self, msg):
        self.items.append(("ERROR", msg))

    def warn(self, msg):
        self.items.append(("WARN", msg))

    @property
    def errors(self):
        return sum(1 for level, _ in self.items if level == "ERROR")


def split_frontmatter(text, r):
    if not text.startswith("---\n"):
        r.err("file does not start with '---' — frontmatter must be the first line "
              "(move any leading comment below it)")
        m = re.search(r"^---\n(.*?)\n---\n", text, re.S | re.M)
    else:
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        r.err("no YAML frontmatter found")
        return {}, text
    try:
        fm = yamlish.load(m.group(1)) or {}
    except yamlish.YamlError as e:
        r.err(f"frontmatter is not valid YAML: {e}")
        fm = {}
    return fm, text[m.end():]


def strip_comments_and_fences(body):
    """Body with HTML comments removed; fenced blocks kept (headings inside fences are ignored later)."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.S)


def sections(body):
    out, cur, in_fence = [], None, False
    for line in body.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            name = line[3:].strip()
            name = CRITERIA_ALIASES.get(name, name)
            cur = [name, []]
            out.append(cur)
        elif cur is not None:
            cur[1].append(line)
    return [(n, "\n".join(ls)) for n, ls in out]


def collect_iscs(content):
    """({id: (checked, text, section)} in file order, [duplicate ids]) from Criteria + Bridge Criteria."""
    iscs, dupes = {}, []
    for sec in ("Criteria", "Bridge Criteria"):
        for line in content.get(sec, "").splitlines():
            m = ISC_RE.match(line)
            if m:
                iid = m.group(2)
                if iid in iscs:
                    dupes.append(iid)
                iscs[iid] = (m.group(1).lower() == "x", m.group(3), sec)
    return iscs, dupes


def leaf_iscs(iscs, decisions):
    """(parents, leaves, counted): leaves drop parents and `[DROPPED` tombstones; counted also
    drops ISCs waived in Decisions — the set `progress` is computed over."""
    dropped = {i for i, (_, t, _) in iscs.items() if t.startswith("[DROPPED")}
    parents = {i for i in iscs if any(j.startswith(i + ".") for j in iscs)}
    leaves = [i for i in iscs if i not in parents and i not in dropped]
    waived = set(re.findall(r"waived: (ISC-\d+(?:\.\d+)*)", decisions))
    return parents, leaves, [i for i in leaves if i not in waived]


def parse(text, path="<text>"):
    """The parts of an ISA other modules read (status, evidence), parsed exactly as `lint` does.
    Never raises on a malformed file: missing parts come back empty."""
    r = Report(path)
    fm, body = split_frontmatter(text, r)
    content = dict(sections(strip_comments_and_fences(body)))
    iscs, _ = collect_iscs(content)
    parents, leaves, counted = leaf_iscs(iscs, content.get("Decisions", ""))
    ts = yaml_block(content["Test Strategy"], r, "Test Strategy") if "Test Strategy" in content else []
    feats = yaml_block(content["Features"], r, "Features") if "Features" in content else []
    return {"fm": fm, "content": content, "iscs": iscs, "leaves": leaves, "counted": counted,
            "test_strategy": {e["isc"]: e for e in ts if isinstance(e, dict) and "isc" in e},
            "features": [f for f in feats if isinstance(f, dict)]}


def grep_only(tool):
    """Every command of the probe only reads text (grep, test -f, cat …): it can't run the code it claims
    about. A pipeline or `&&` chain counts only when all of its commands are such readers."""
    tool = str(tool or "")
    # a command substitution runs its own commands: `test "$(./app --help | wc -l)" -le 12` runs the app;
    # unwrap them innermost first, so a nested `$(… $(cat ids) …)` is judged level by level
    while True:
        subs = re.findall(r"\$\(([^()]*)\)|`([^`]*)`", tool)
        if not subs:
            break
        if any(not grep_only(a or b) for a, b in subs):
            return False
        tool = re.sub(r"\$\([^()]*\)|`[^`]*`", "X", tool)
    segs = [s.strip() for s in re.split(r"\|\||&&|\||;", tool) if s.strip()]
    if not segs:
        return False
    for seg in segs:
        words = seg.split()
        while words and re.match(r"^[A-Za-z_]\w*=", words[0]):
            words = words[1:]
        if words and words[0] in ("!", "cd"):
            if words[0] == "cd":
                continue
            words = words[1:]
        if not words or words[0].split("/")[-1] not in GREP_ONLY:
            return False
    return True


def is_v2(fm):
    """Started on or after V2_SINCE (SPEC-v2 § 8: older open ISAs get warnings, not errors, for new rules)."""
    return str(fm.get("started") or "")[:10] >= V2_SINCE


def dependency_cycle(features):
    """The first `depends_on` cycle among Features, as [A, B, …, A], or None."""
    deps = {f.get("name"): [d for d in f.get("depends_on") or []] for f in features if isinstance(f, dict)}
    state = {}

    def visit(n, path):
        if state.get(n) == "done" or n not in deps:
            return None
        if state.get(n) == "open":
            return path[path.index(n):] + [n]
        state[n] = "open"
        for d in deps[n]:
            found = visit(d, path + [n])
            if found:
                return found
        state[n] = "done"
        return None

    for n in deps:
        found = visit(n, [])
        if found:
            return found
    return None


def yaml_block(text, r, section):
    m = re.search(r"```ya?ml\n(.*?)```", text, re.S)
    if not m:
        r.err(f"{section}: no fenced ```yaml list")
        return []
    try:
        data = yamlish.load(m.group(1))
    except yamlish.YamlError as e:
        r.err(f"{section}: YAML does not parse: {e}")
        return []
    if not isinstance(data, list):
        r.err(f"{section}: YAML is not a list")
        return []
    return data


def lint(path, moment="auto", text=None, prompts=None):
    """Lint one ISA. `prompts`, when given, is the list of raw user prompts the
    harness logged; a `stated_goal` found in none of them is an error."""
    r = Report(path)
    if text is None:
        text = open(path, encoding="utf-8").read()
    fm, body = split_frontmatter(text, r)
    body = strip_comments_and_fences(body)

    # --- frontmatter
    for k in CORE:
        if k not in fm:
            r.err(f"frontmatter: missing `{k}`")
    tier = str(fm.get("effort", ""))
    if tier not in TIER_ARTICULATION:
        r.err(f"frontmatter: effort `{tier}` is not E1..E5")
        tier = "E3"
    phase = fm.get("phase")
    if phase not in PHASES:
        r.err(f"frontmatter: phase `{phase}` not in {sorted(PHASES)}")
    if "slug" in fm and not SLUG_RE.match(str(fm["slug"])):
        r.err(f"frontmatter: slug `{fm['slug']}` is not YYYYMMDD-HHMMSS_kebab")
    if len(str(fm.get("task", ""))) > 60:
        r.warn(f"frontmatter: task is {len(str(fm['task']))} chars (max 60)")
    goal = fm.get("stated_goal")
    if prompts is not None and isinstance(goal, str) and goal.strip():
        if not any(goal in p for p in prompts):
            r.err("frontmatter: stated_goal is not a verbatim substring of any logged user prompt "
                  "— copy it byte-for-byte from the prompt, or set it to null and log the candidate in Decisions")
    if tier != "E1" and "context_sufficient" not in fm:  # rule 6: the ambiguity check left its outcome
        _sev(r, fm)("frontmatter: `context_sufficient` not set — record the ambiguity check's outcome (true, or false "
                    "when a reasoned default was accepted via `proceed`)")
    if moment == "auto":
        moment = "close" if phase == "complete" else "articulation"
    linked = bool(fm.get("parent") or fm.get("children"))

    # --- sections: order, duplicates, empties, tier gate
    secs = sections(body)
    names = [n for n, _ in secs]
    for n in names:
        if n not in SECTIONS:
            r.err(f"sections: unknown section `## {n}`")
    known = [n for n in names if n in SECTIONS]
    if len(set(known)) != len(known):
        r.err("sections: a section appears twice")
    idx = [SECTIONS.index(n) for n in known]
    if idx != sorted(idx):
        r.err(f"sections: out of locked order: {known}")
    content = {n: t for n, t in secs}
    for n, t in secs:
        if not t.strip():
            r.err(f"sections: `## {n}` is empty (omit it instead)")
    required = list(TIER_ARTICULATION[tier])
    if tier in ("E4", "E5") and linked:
        required += ["Dependencies", "Bridge Criteria"]
    for n in required:
        if n not in content:
            r.err(f"gate {tier}/{moment}: missing `## {n}`")
    if moment == "articulation":
        # Record sections are allowed early only when they hold real entries — never required.
        pass
    else:
        rec = ["Verification"] + (["Decisions", "Changelog"] if tier in ("E4", "E5") else [])
        for n in rec:
            if n == "Changelog" and n not in content and \
                    "no belief refuted this run" in content.get("Decisions", ""):
                continue
            if n not in content:
                r.err(f"gate {tier}/close: missing `## {n}`")
        if tier == "E5" and not fm.get("interview_ran"):
            r.err("gate E5/close: `interview_ran` not set")

    # --- criteria
    iscs, dupes = collect_iscs(content)
    for iid in dupes:
        r.err(f"criteria: duplicate id {iid}")
    if not iscs:
        r.err("criteria: no `- [ ] ISC-N:` lines")
    parents, leaves, counted = leaf_iscs(iscs, content.get("Decisions", ""))
    m_checked = sum(1 for i in counted if iscs[i][0])
    expect = f"{m_checked}/{len(counted)}"
    if str(fm.get("progress", "")).strip() != expect:
        r.err(f"frontmatter: progress `{fm.get('progress')}` but criteria say {expect}")
    if not any(t.startswith("Anti:") for _, t, _ in iscs.values()):
        r.err("criteria: no `Anti:` ISC (≥1 required at every tier)")
    for i in leaves:
        t = iscs[i][1]
        if "(probe:" in t and tier != "E1":  # E1 has no Test Strategy; inline is its only home
            r.warn(f"criteria: {i} carries its probe inline — move it to Test Strategy")
        words = len(re.sub(r"^(Anti|Antecedent|Bridge):\s*", "", t).split())
        if words > 20:
            r.warn(f"criteria: {i} is {words} words (target 8–12) — split?")
    for p in parents:
        kids = [j for j in leaves if j.startswith(p + ".")]
        if iscs[p][0] and not all(iscs[k][0] for k in kids):
            r.err(f"criteria: parent {p} ticked while a leaf is open")

    # --- test strategy
    if "Test Strategy" in content:
        entries = yaml_block(content["Test Strategy"], r, "Test Strategy")
        covered = set()
        for e in entries:
            if not isinstance(e, dict) or "isc" not in e:
                r.err(f"Test Strategy: entry without `isc`: {e}")
                continue
            covered.add(e["isc"])
            extra = set(e) - TS_KEYS
            if extra:
                r.err(f"Test Strategy: {e['isc']} unknown keys {sorted(extra)}")
            if e["isc"] not in iscs:
                r.err(f"Test Strategy: {e['isc']} is not an ISC in Criteria")
            need = ["type", "tool"] + (["property", "generator", "runs"] if e.get("type") == "property"
                                       else ["check", "threshold"])
            for k in need:
                if k not in e:
                    r.err(f"Test Strategy: {e['isc']} missing `{k}`")
            tool = e.get("tool")
            if e.get("type") not in SELF_ATTESTED and isinstance(tool, str) and PLACEHOLDER.search(tool):
                r.err(f"Test Strategy: {e['isc']} `tool:` holds a placeholder "
                      f"(`{PLACEHOLDER.search(tool).group(0)}`) — write the exact command `isa verify` will run")
            _v2_entry_rules(r, e, fm, tier, iscs, content)
            if isinstance(tool, str) and re.match(r"\s*cd\s+/", tool):
                r.warn(f"Test Strategy: {e['isc']} starts with `cd /…` — probes run from the ISA's `root:`; "
                       "use `cwd:` (relative to root) or `root:` (another project) instead")
            if fm.get("stated_goal") and "anchors_to" not in e:
                r.err(f"Test Strategy: {e['isc']} missing `anchors_to` (stated_goal is set)")
            if iscs.get(e["isc"], (None, ""))[1].startswith("Bridge:") and \
                    not str(e.get("anchors_to", "")).startswith("cross:"):
                r.err(f"Test Strategy: bridge {e['isc']} needs `anchors_to: cross: <slug>`")
        missing = [i for i in leaves if i not in covered]
        if missing:
            r.err(f"Test Strategy: no entry for leaf ISCs {missing}")

    # --- features
    if "Features" in content:
        feats = yaml_block(content["Features"], r, "Features")
        names = {f.get("name") for f in feats if isinstance(f, dict)}
        for f in feats:
            if not isinstance(f, dict):
                r.err(f"Features: entry is not a mapping: {f}")
                continue
            miss = FEATURE_KEYS - set(f)
            if miss:
                r.err(f"Features: `{f.get('name')}` missing {sorted(miss)}")
            for s in f.get("satisfies") or []:
                if s not in iscs:
                    r.err(f"Features: `{f.get('name')}` satisfies unknown {s}")
            for d in f.get("depends_on") or []:
                if d not in names:
                    r.err(f"Features: `{f.get('name')}` depends on unknown Feature `{d}`")
        cycle = dependency_cycle(feats)
        if cycle:
            r.err(f"Features: dependency cycle {' → '.join(cycle)} — no ISC in it could ever be ticked")

    # --- changelog: four parts per entry
    if "Changelog" in content:
        for entry in re.split(r"\n(?=- )", content["Changelog"].strip()):
            if not entry.startswith("- "):
                continue
            for part in ("conjectured:", "refuted by:", "learned:", "criterion now:"):
                if part not in entry:
                    r.err(f"Changelog: entry missing `{part}`: {entry.splitlines()[0][:60]}")
                    break

    # --- shape rows (any moment): `finding:` and `repro-bypass:` rows must be well formed
    for line in content.get("Decisions", "").splitlines():
        for key, pat in SHAPE_ROWS.items():
            if f"{key}:" in line and not pat.search(line):
                r.err(f"Decisions: malformed `{key}:` row — expected "
                      + ("`finding: <text> — adopted (<diff/ISC>) | rebutted (<reason>) | deferred (<task>)`"
                         if key == "finding" else
                         "`repro-bypass: pure-additive | non-isolable | repro would cause damage — <why>`")
                      + f": {line.strip()[:80]}")

    # --- ticks vs evidence (any moment, once Verification exists)
    ver = content.get("Verification", "")
    if ver:
        for i in leaves:
            has = re.search(rf"^- {re.escape(i)}:", ver, re.M)
            deferred = re.search(rf"^- {re.escape(i)}: \[DEFERRED-VERIFY\]", ver, re.M)
            if iscs[i][0] and not has:
                r.warn(f"verification: {i} is ticked but has no evidence line")
            if has and not deferred and not iscs[i][0]:
                r.warn(f"verification: {i} has evidence but is not ticked")

    # --- close rules
    if moment == "close":
        for i in counted:
            if not iscs[i][0]:
                r.err(f"close: leaf {i} still open and not waived")
            elif not re.search(rf"^- {re.escape(i)}:", ver, re.M):
                r.err(f"close: {i} has no Verification entry")
        _close_shape_rules(r, fm, tier, content, ver)
        goal_lines = re.findall(r"^- Goal: (yes|no)\b", ver, re.M)
        if not goal_lines:
            r.err("close: no `- Goal: yes|no — …` line in Verification")
        elif goal_lines[-1] != "yes":
            r.err("close: latest Goal line is `no`")
        if phase != "complete":
            r.warn("close checked but phase is not `complete`")
    return r


def _sev(r, fm, strict=True):
    """Error for ISAs started under v2, warning for older ones (SPEC-v2 § 8)."""
    return r.err if strict and is_v2(fm) else r.warn


def _v2_entry_rules(r, e, fm, tier, iscs, content):
    i = e["isc"]
    kind = str(e.get("kind") or "").strip().lower()
    typ = str(e.get("type") or "").strip().lower()
    say = _sev(r, fm, strict=tier != "E1")
    if not kind:
        say(f"Test Strategy: {i} missing `kind:` (one of {', '.join(sorted(KINDS - {'behavior'}))}) — it sets "
            "which probe types can prove the ISC")
    elif kind not in KINDS:
        say(f"Test Strategy: {i} `kind: {kind}` is not one of {', '.join(sorted(KINDS - {'behavior'}))}")
    else:
        refused, no_grep = KIND_REFUSES[kind]
        if typ in refused:
            say(f"Test Strategy: {i} `kind: {kind}` can't be proven by a `{typ}` probe — run the thing it claims")
        elif no_grep and typ not in SELF_ATTESTED and grep_only(e.get("tool")):
            say(f"Test Strategy: {i} `kind: {kind}` can't be proven by a grep-only probe (it reads text, it doesn't "
                "run the code) — run it")
    risk = str(e.get("risk") or "").strip()
    text = iscs.get(i, (False, ""))[1] + " " + str(e.get("tool") or "")
    if not risk and RISK_WORDS.search(text):
        _sev(r, fm, strict=tier not in ("E1", "E2"))(
            f"Test Strategy: {i} mentions `{RISK_WORDS.search(text).group(0)}` — declare `risk: high` or "
            "`risk: low — <why>`")
    elif risk:
        low = risk.lower()
        if low.startswith("low"):
            if not re.match(r"low\s*[—-]+\s*\S", risk, re.I):
                _sev(r, fm)(f"Test Strategy: {i} `risk: low` needs its reason: `risk: low — <why>`")
        elif low != "high":
            _sev(r, fm)(f"Test Strategy: {i} `risk:` must be `high` or `low — <why>`, got `{risk}`")
        elif typ in SELF_ATTESTED and i not in set(re.findall(r"waived: (ISC-\d+(?:\.\d+)*)",
                                                              content.get("Decisions", ""))):
            r.err(f"Test Strategy: {i} is `risk: high` — a `{typ}` probe can't prove it: write a mechanical probe, "
                  "or the user waives the ISC")


def _close_shape_rules(r, fm, tier, content, ver):
    dec = content.get("Decisions", "")
    asks = fm.get("asks") if isinstance(fm.get("asks"), list) else []
    for n, ask in enumerate(asks, 1):
        m = re.search(rf"^- Ask {n}: (\S+)(.*)$", ver, re.M)
        if not m:
            r.err(f"close: ask {n} (\"{str(ask)[:60]}\") has no `- Ask {n}: met | skipped — <why> | surfaced` line")
        elif m.group(1).rstrip("—-,:") not in ("met", "skipped", "surfaced"):
            r.err(f"close: `- Ask {n}:` must say met, skipped — <why>, or surfaced (got `{m.group(1)}`)")
        elif m.group(1).startswith("skipped") and not re.search(r"—\s*\S", m.group(2)):
            r.err(f"close: `- Ask {n}: skipped` needs its reason (`— <why>`)")
    risky = re.search(r"^\s*risk:\s*high\b", content.get("Test Strategy", ""), re.M | re.I)
    if (risky or tier in ("E4", "E5")) and "second-look:" not in dec:
        _sev(r, fm)("close: no `second-look: <who/what reviewed, where its findings are> | skipped — <why>` row in "
                    "Decisions (" + ("a `risk: high` ISC" if risky else f"tier {tier}") + ")")
    for cls in sorted(set(re.findall(r"^\s*class:\s*(.+?)\s*$", content.get("Test Strategy", ""), re.M))):
        if not re.search(rf"class-sweep: {re.escape(cls)} — ", dec):
            r.err(f"close: `class: {cls}` needs a `class-sweep: {cls} — N siblings via <probe>; M fixed, K "
                  "tombstoned` row in Decisions")


def main(argv):
    moment = "auto"
    if argv[:1] == ["--moment"]:
        moment, argv = argv[1], argv[2:]
    elif argv[:1] == ["--close"]:
        moment, argv = "close", argv[1:]
    total = 0
    for p in argv:
        r = lint(p, moment)
        total += r.errors
        status = "ok" if not r.errors else f"{r.errors} error(s)"
        print(f"{p}: {status}")
        for level, msg in r.items:
            print(f"  {level}: {msg}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
