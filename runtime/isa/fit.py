"""Does this prompt describe work an ISA would structure? Deterministic stand-in for a Jev judgment.

`score(prompt)` → (level, reasons) with level "strong" | "maybe" | "none". The statement it checks
against is fit.md. It never gates anything: the verdict is context for the model. Replace
`score` with a model judgment (Future D, JEV.md) without changing callers.
"""
import re

# work whose outcome someone relies on and whose parts could be skipped
OUTCOME_VERBS = re.compile(
    r"\b(review|audit|assess|evaluat\w*|analy[sz]\w*|investigat\w*|diagnos\w*|root[- ]cause|debug\w*|"
    r"compar\w*|benchmark\w*|research\w*|survey|inventor(y|ies)|map (out|the)|plan\w*|design\w*|spec(ify|s)?|"
    r"propos\w*|recommend\w*|strateg\w*|migrat\w*|refactor\w*|rethink|re-?think|overhaul|harden\w*|triage|"
    r"check (if|whether|that|all|every|each)|figure out|find (all|every|out why)|verify|validate)\b", re.I)
COVERAGE = re.compile(r"\b(all|every|each|complete(ly)?|thorough(ly)?|exhaustive(ly)?|end[- ]to[- ]end|"
                      r"whole|entire|full)\b", re.I)
DONE_LANG = re.compile(r"\b(make sure|ensure|so that|until|definition of done|acceptance|must|should (be|not))\b",
                       re.I)
QUESTION_START = re.compile(r"^\s*(what|who|when|where|which|why|is|are|was|were|does|do|did|can|could|"
                            r"should|how (do|does|can|much|many|long))\b", re.I)
EXPLAIN = re.compile(r"\b(explain|what('s| is| are| does)|meaning of|define|definition of(?! done)|tell me about|"
                     r"remind me)\b", re.I)
SMALL_TALK = re.compile(r"^\s*(ok(ay)?|thanks?|thank you|yes|no|yep|nope|sure|cool|great|nice|lgtm|go|continue|"
                        r"proceed|stop|hi|hello)\b[\s.!]*$", re.I)


def score(prompt):
    text = (prompt or "").strip()
    words = re.findall(r"\w[\w'-]*", text)
    n = len(words)
    if not text or SMALL_TALK.match(text) or text.startswith("/"):
        return "none", []
    pts, reasons = 0, []
    verbs = sorted({m.group(0).lower() for m in OUTCOME_VERBS.finditer(text)})
    if verbs:
        pts += 3 + (1 if len(verbs) >= 2 else 0)
        reasons.append("outcome work: " + ", ".join(verbs[:4]))
    if COVERAGE.search(text):
        pts += 1
        reasons.append("asks for coverage (" + COVERAGE.search(text).group(0).lower() + ")")
    if DONE_LANG.search(text):
        pts += 1
        reasons.append("states a done condition (" + DONE_LANG.search(text).group(0).lower() + ")")
    parts = len(re.findall(r"^\s*(?:[-*•]|\d+[.)])\s+", text, re.M))
    sentences = len([s for s in re.split(r"[.!?\n]+", text) if len(s.split()) >= 3])
    if parts >= 2 or sentences >= 4:
        pts += 1
        reasons.append(f"several parts ({parts} list items, {sentences} sentences)" if parts >= 2
                       else f"several parts ({sentences} sentences)")
    if n >= 120:
        pts += 2
        reasons.append(f"long brief ({n} words)")
    elif n >= 40:
        pts += 1
        reasons.append(f"substantial brief ({n} words)")
    if n <= 20 and QUESTION_START.match(text) and not verbs:
        pts -= 2
    if EXPLAIN.search(text) and not verbs:
        pts -= 1
    if n <= 8:
        pts -= 2
    level = "strong" if pts >= 4 else "maybe" if pts >= 2 else "none"
    return level, (reasons if level != "none" else [])


def advice(level, reasons, bound=None):
    """One short paragraph for the model; empty when the prompt doesn't fit."""
    if level == "none":
        return ""
    why = "; ".join(reasons)
    head = f"ISA fit: {level} ({why})."
    if bound:
        return head + " An ISA is bound — if this is a new task, give it its own ISA."
    if level == "strong":
        return (head + " Even if this stays read-only, structure it with an ISA before starting: Goal = the "
                "conclusion to reach, ISCs = the questions the answer must settle (one per part, plus an `Anti:` "
                "for the lazy answer), Verification = evidence per ISC. See fit.md in the ISA runtime.")
    return head + " Consider an ISA if the answer has several parts that could each be skipped."
