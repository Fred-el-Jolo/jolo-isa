"""`~/.isa/config.json` (`$ISA_HOME/config.json`): the user's system-wide ISA settings (SPEC-v2 § 11).

    {"ask_without_isa": true}    ask the user before a prompt goes on without an ISA (default: true)
    {"jev": true}                Jev judgments through jev-kit (default: true; false = no Jev call at all)

A missing file, unreadable JSON or a missing key means the default: a broken config never stops ISA,
and the parse error is noted in the debug log. Read on every use; nothing is cached across calls.
"""
import json
import os

from . import state

DEFAULTS = {"ask_without_isa": True, "jev": True}


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
