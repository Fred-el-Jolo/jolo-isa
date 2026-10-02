"""A tiny todo list stored in a JSON file (TODO_FILE, default ./todo.json).

    python3 todo.py add "buy milk"
    python3 todo.py list
"""
import argparse
import json
import os
import sys


def path():
    return os.environ.get("TODO_FILE", "todo.json")


def load():
    try:
        with open(path()) as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save(tasks):
    with open(path(), "w") as f:
        json.dump(tasks, f, indent=1)


def cmd_add(args):
    tasks = load()
    next_id = max((t["id"] for t in tasks), default=0) + 1
    tasks.append({"id": next_id, "text": args.text})
    save(tasks)
    print(f"added {next_id}")


def cmd_list(args):
    for t in load():
        print(f"{t['id']} [ ] {t['text']}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="todo")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("text")
    a.set_defaults(func=cmd_add)
    ls = sub.add_parser("list")
    ls.set_defaults(func=cmd_list)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
