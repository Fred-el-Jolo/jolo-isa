"""`~/.isa/config.json` (`$ISA_HOME/config.json`): the user's system-wide ISA settings (SPEC-v2 § 11).

    {"ask_without_isa": true}    ask the user before a prompt goes on without an ISA (default: true)
    {"jev": true}                Jev judgments through jev-kit (default: true; false = no Jev call at all)
    {"jev_gate": 0.8}            Jev's Q1/Q2 line: at or above it, an ISA is required (SPEC-v2 § 12.2)
    {"jev_quiet": 0.3}           below it (and below jev_gate), a prompt goes on without an ISA silently —
                                 no question, the Continue pass granted (SPEC-v2 § 12.4, M11.2)
    {"jev_doubt": 0.5}           the advisory line: a red-exempt probe, a goal or an ask Jev rates below it
                                 is flagged (§ 11.2)

A missing file, unreadable JSON or a missing key means the default: a broken config never stops ISA,
and the parse error is noted in the debug log. Read on every use; nothing is cached across calls.
"""
import json
import os

from . import state

DEFAULTS = {"ask_without_isa": True, "jev": True, "jev_gate": 0.8, "jev_quiet": 0.3, "jev_doubt": 0.5}


def path():
    return os.path.join(state.home(), "config.json")


def load():
    """→ (settings, error or None)."""
    try:
        with open(path(), encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return dict(DEFAULTS), None
    except (OSError, ValueError) as e:
        return dict(DEFAULTS), f"{path()}: {e}"
    if not isinstance(data, dict):
        return dict(DEFAULTS), f"{path()}: not a JSON object"
    return {**DEFAULTS, **data}, None


def get(key):
    value = load()[0].get(key, DEFAULTS.get(key))
    return value if isinstance(value, type(DEFAULTS.get(key, value))) else DEFAULTS.get(key)


def number(key):
    """A threshold in [0, 1] → (value, error or None). Out of range or not a number → the default, and the
    error says why (callers note it in the debug log)."""
    settings, err = load()
    value = settings.get(key, DEFAULTS[key])
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        return DEFAULTS[key], f"{key}: {value!r} is not a number in [0, 1]; using {DEFAULTS[key]}"
    return float(value), err
