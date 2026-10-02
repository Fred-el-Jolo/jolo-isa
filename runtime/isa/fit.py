"""The gate's free, deterministic first pass (SPEC-v2 § 1.2), and a fit score for `isa fit`.

`prefilter(prompt)` → (verdict, reason) with verdict "yes" | "no" | "unsure". Rules, in order:
greeting/thanks → no · short prompt (≤ 4 words: "go", "ok do it", "fix these") → unsure, since it
usually authorises work proposed in the turn before, which only the judge (with that context) sees ·
question or explanation → unsure · explicit ISA mention → yes · work verb with an object → yes ·
anything else → unsure. Only `unsure` reaches the judge (judge.py); a false yes is the accepted cost.

`score(prompt)` → (level, reasons) is the older heuristic ("strong" | "maybe" | "none"), kept as a
detail line for `isa fit`. It decides nothing. fit.md states what the gate question protects.
"""
import re

SOCIAL = {"hi", "hello", "hey", "yo", "thanks", "thank", "you", "thx", "ty", "cheers", "cool", "nice", "great",
          "perfect", "awesome", "good", "looks", "look", "lgtm", "bye", "morning", "evening", "night", "very",
          "much", "a", "lot", "so", "all", "that", "works", "excellent", "wonderful", "merci", "bravo"}
WORK_VERB = re.compile(
    r"\b(fix|add|implement|refactor|write|rewrite|review|migrate|deploy|create|build|update|remove|delete|"
    r"rename|change|modify|install|configure|set up|port|convert|optimi[sz]e|improve|test|debug|audit|design|"
    r"plan|draft|document|upgrade|clean up|integrate|scaffold|generate|make|ship|publish|release|translate|"
    r"summari[sz]e|compare|investigate|research|analy[sz]e|assess|evaluate|benchmark|spec|prototype)\b",
    re.I)
QUESTION = re.compile(r"^\s*(what|why|how|when|where|which|who|whose|is|are|was|were|does|do|did|can|could|"
                      r"should|would|will|may|might)\b", re.I)
EXPLAIN = re.compile(r"\b(explain|describe|tell me about|remind me|meaning of|what('s| is| are| does))\b", re.I)
ISA_MENTION = re.compile(r"\bISA\b|\bideal state\b|\bISC\b", re.I)


def prefilter(prompt):
    text = (prompt or "").strip()
    words = re.findall(r"[\w'-]+", text.lower())
    if not text or text.startswith("/"):
        return "no", "empty prompt or slash command"
    if words and all(w in SOCIAL for w in words):
        return "no", "greeting or thanks"
    if len(words) <= 4:
        return "unsure", "short prompt: it may authorise work proposed earlier"
    if QUESTION.match(text) or text.rstrip().endswith("?") or EXPLAIN.search(text):
        return "unsure", "phrased as a question or an explanation request"
    if ISA_MENTION.search(text):
        return "yes", "explicit ISA mention"
    m = WORK_VERB.search(text)
    if m:
        return "yes", f"work request ({m.group(0).lower()} …)"
    return "unsure", "no work verb recognised"


# ------------------------------------------------------------------ detail score (isa fit)

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
