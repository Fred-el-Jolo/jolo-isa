"""`~/.isa/config.json` (`$ISA_HOME/config.json`): the user's ISA settings.

    {"ask_without_isa": true}   ask the user whenever the gate does not say yes (default: true)
    {"jev": true}               Jev judges the gate (default: true; false = no Jev call at all)
    {"jev_gate": 0.8}           at or above it, the prompt is ISA work
    {"jev_quiet": 0.3}          below it, the prompt goes on without an ISA and without a question
    {"jev_doubt": 0.5}          the advisory line: a probe, goal or ask Jev rates below it is flagged
    {"debug": false}            DEBUG: write the debug log (`ISA_DEBUG=1` overrides)

A missing file, unreadable JSON or a missing key means the default: a broken config never stops ISA.
"""
import json
import os

DEFAULTS = {"ask_without_isa": True, "jev": True, "jev_gate": 0.8, "jev_quiet": 0.3, "jev_doubt": 0.5,
            "debug": False}


def path():
    return os.path.join(os.path.expanduser(os.environ.get("ISA_HOME", "~/.isa")), "config.json")


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
    """A threshold in [0, 1]; out of range or not a number → the default."""
    value = load()[0].get(key, DEFAULTS[key])
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        return DEFAULTS[key]
    return float(value)
