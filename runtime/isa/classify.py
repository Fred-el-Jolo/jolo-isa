"""Is a tool call a read or a mutation? Harness-neutral, standard library only.

Three answers:
    "read"     never gated (reading, searching, asking, planning)
    "write"    a known mutation — gated, and counts toward "ISA is stale"
    "unknown"  can't tell — gated before an ISA exists (fail closed), not counted as stale

Paths decide first: anything inside an ISA folder is "isa" (always allowed, and an
edit of an ISA.md binds it); anything under a temp dir is "temp" (allowed, not counted).
"""
import os
import re
import shlex

from . import state

# ------------------------------------------------------------------ tools

READ_TOOLS = {
    # Claude Code
    "Read", "Glob", "Grep", "LS", "WebFetch", "WebSearch", "TodoWrite", "TodoRead", "Task", "Agent",
    "ToolSearch", "Skill", "AskUserQuestion", "ExitPlanMode", "EnterPlanMode", "ListMcpResourcesTool",
    "ReadMcpResourceTool", "Monitor", "TaskStop", "BashOutput", "KillShell", "SendMessage", "ListAgents",
    "ScheduleWakeup", "SendFeedback", "ReportFindings", "EnterWorktree", "ExitWorktree",
    # pi
    "read", "grep", "find", "ls",
}
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "write", "edit"}
SHELL_TOOLS = {"Bash", "bash", "PowerShell", "powershell"}
_READ_VERB = re.compile(r"(^|[_.-])(read|get|list|search|query|fetch|find|view|show|describe|lookup|"
                        r"guide|status|info|count|check|preview|download|export|authenticate)", re.I)
_WRITE_VERB = re.compile(r"(^|[_.-])(write|edit|create|update|delete|remove|send|post|push|set|put|"
                         r"move|rename|upload|insert|publish|merge|commit|deploy|batch|apply)", re.I)


def tool_paths(tool_input):
    ti = tool_input or {}
    out = []
    for k in ("file_path", "notebook_path", "path"):
        v = ti.get(k)
        if isinstance(v, str) and v:
            out.append(v)
    return out


def path_kind(path, cwd, temp_dirs=()):
    p = os.path.expanduser(path)
    if not os.path.isabs(p):
        p = os.path.join(cwd or os.getcwd(), p)
    if state.is_isa_path(p):
        return "isa"
    rp = os.path.realpath(p)
    if is_agent_memory(rp):
        return "temp"  # the agent's own memory notes: agent state, not project work
    root = state.project_root(cwd)
    if (rp + os.sep).startswith(root + os.sep) and root != os.path.realpath(os.path.expanduser("~")):
        return "project"  # a project that lives under /tmp is still a project
    for t in _temp_roots(temp_dirs):
        if (rp + os.sep).startswith(t + os.sep):
            return "temp"
    return "project"


def is_agent_memory(real_path):
    """~/.claude/projects/<project>/memory/… (Claude Code's per-project memory). Override the parent
    with ISA_AGENT_MEMORY_ROOT (tests)."""
    base = os.path.realpath(os.path.expanduser(os.environ.get("ISA_AGENT_MEMORY_ROOT", "~/.claude/projects")))
    if not (real_path + os.sep).startswith(base + os.sep):
        return False
    rel = os.path.relpath(real_path, base).split(os.sep)
    return len(rel) >= 2 and rel[1] == "memory"


def _temp_roots(extra=()):
    roots = {"/tmp", "/var/tmp", "/dev/shm", os.environ.get("TMPDIR", "/tmp")}
    roots.update(e for e in extra if e)
    return [os.path.realpath(r) for r in roots if r]


def classify(tool, tool_input, cwd, temp_dirs=()):
    """→ (kind, isa_paths) where kind is read|write|unknown and isa_paths lists ISA files touched."""
    ti = tool_input or {}
    if tool in FILE_TOOLS:
        kinds = [(p, path_kind(p, cwd, temp_dirs)) for p in tool_paths(ti)]
        isa = [p for p, k in kinds if k == "isa"]
        if kinds and all(k in ("isa", "temp") for _, k in kinds):
            return "read", isa
        return "write", isa
    if tool in SHELL_TOOLS:
        return bash(ti.get("command", ""), cwd, temp_dirs)
    if tool in READ_TOOLS:
        return "read", []
    name = tool.split("__")[-1] if tool.startswith("mcp__") else tool
    if _WRITE_VERB.search(name):
        return "unknown", []
    if _READ_VERB.search(name):
        return "read", []
    return "unknown", []


# ------------------------------------------------------------------ bash

READ_CMDS = {
    "ls", "cat", "head", "tail", "less", "more", "wc", "grep", "egrep", "fgrep", "rg", "ag", "fd", "tree",
    "stat", "file", "du", "df", "pwd", "which", "whereis", "type", "echo", "printf", "date", "whoami", "id",
    "uname", "printenv", "hostname", "ps", "jq", "yq", "sort", "uniq", "cut", "tr", "column", "diff", "cmp",
    "md5sum", "sha1sum", "sha256sum", "basename", "dirname", "realpath", "readlink", "test", "[", "true",
    "false", "nl", "od", "xxd", "hexdump", "strings", "bat", "batcat", "cal", "uptime", "free", "lsblk",
    "sleep", "seq", "expr", "comm", "paste", "fold", "fmt", "tac", "rev", "man", "tldr", "help", "awk",
    "gawk", "mawk", "eza", "exa", "cd", "pushd", "popd", "export", "unset", "set", "shopt", "wait",
    "isa", "sed", "find", "git", "gh", "command", "local", "declare", "read", "shasum", "lsof", "pgrep",
    "whatis", "apropos", "getconf", "locale", "tput", "stty", "ugrep", "zcat", "zgrep", "pdfinfo",
    "identify", "soxi", "ffprobe", "xmllint", "cloc", "tokei",
}
WRITE_CMDS = {
    "rm", "rmdir", "mv", "cp", "mkdir", "touch", "ln", "chmod", "chown", "chgrp", "tee", "dd", "truncate",
    "install", "rsync", "patch", "unzip", "shred", "sudo", "doas", "mkfifo", "mktemp", "npm", "pnpm", "yarn",
    "bun", "pip", "pip3", "uv", "cargo", "go", "make", "apt", "apt-get", "brew", "mise", "docker", "kubectl",
    "terraform", "wget", "scp", "systemctl", "crontab", "kill", "pkill", "killall",
}
# file commands judged by their path arguments: all in temp dirs / ~/.isa → not a project mutation
PATH_CMDS = {"rm", "rmdir", "mv", "cp", "mkdir", "touch", "ln", "chmod", "chown", "chgrp", "tee",
             "truncate", "install", "rsync", "mktemp"}
WRAPPERS = {"time", "nice", "nohup", "env", "timeout", "xargs", "stdbuf", "ionice", "caffeinate", "exec"}
GIT_READ = {"status", "log", "diff", "show", "blame", "rev-parse", "ls-files", "ls-tree", "describe",
            "shortlog", "grep", "reflog", "cat-file", "rev-list", "name-rev", "whatchanged", "count-objects",
            "for-each-ref", "show-ref", "check-ignore", "var", "help", "version", "merge-base"}
GIT_WRITE = {"add", "commit", "push", "reset", "checkout", "switch", "merge", "rebase", "cherry-pick",
             "revert", "rm", "mv", "restore", "clean", "am", "apply", "pull", "init", "clone", "gc", "prune"}
GH_READ_VERBS = {"view", "list", "status", "diff", "checks", "search", "browse"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "|&", ";;", "{", "}"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>", ">&"}
SAFE_TARGETS = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"}


def _tokens(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|<>()")
    lex.whitespace_split = True
    lex.commenters = "#"
    return list(lex)


def bash(cmd, cwd, temp_dirs=()):
    if not cmd or not cmd.strip():
        return "read", []
    cmd = _drop_heredoc_bodies(cmd)
    if ">(" in cmd:
        return "unknown", []
    cmd = cmd.replace("<(", " ; ")  # process substitution: judge the inner command on its own
    if "$(" in cmd or "`" in cmd:
        # command substitution can hide anything; judge the visible parts, never better than unknown
        visible = re.sub(r"\$\([^)]*\)|`[^`]*`", "X", cmd)
        k, isa = bash(visible, cwd, temp_dirs) if visible != cmd else ("unknown", [])
        return ("write" if k == "write" else "unknown"), isa
    try:
        toks = _tokens(cmd.replace("\\\n", " ").replace("\n", " ; "))
    except ValueError:
        return "unknown", []
    worst, isa = "read", []
    seg = []
    for t in toks + [";"]:
        if t in SEPARATORS or all(c in ";&|()" for c in t):
            if seg:
                k, i = _segment(seg, cwd, temp_dirs)
                isa += i
                worst = _worse(worst, k)
            seg = []
        else:
            seg.append(t)
    return worst, isa


_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _drop_heredoc_bodies(cmd):
    """Keep `cat <<EOF > f` but drop the lines up to the delimiter — they are data, not commands."""
    lines, out, pending = cmd.split("\n"), [], []
    for line in lines:
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending = [m.group(2) for m in _HEREDOC.finditer(line)]
    return "\n".join(out)


def _worse(a, b):
    order = {"read": 0, "unknown": 1, "write": 2}
    return a if order[a] >= order[b] else b


def _segment(words, cwd, temp_dirs):
    kind, isa = "read", []
    # redirections anywhere in the segment
    clean, i = [], 0
    while i < len(words):
        w = words[i]
        if w in REDIRECTS or re.match(r"^\d*(>>?|>\|)$", w) or w in ("<", "<<", "<<<"):
            target = words[i + 1] if i + 1 < len(words) else ""
            if w in ("<", "<<", "<<<") or re.match(r"^&?\d+$", target) or target in SAFE_TARGETS:
                pass
            else:
                pk = path_kind(target, cwd, temp_dirs)
                if pk == "isa":
                    isa.append(target)
                elif pk == "project":
                    kind = "write"
            i += 2
            continue
        if re.match(r"^\d$", w) and i + 1 < len(words) and words[i + 1] in REDIRECTS | {">", ">>"}:
            i += 1
            continue
        clean.append(w)
        i += 1
    return _worse(kind, _command(clean, cwd, temp_dirs, isa)), isa


def _command(words, cwd=None, temp_dirs=(), isa=None):
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        words = words[1:]
    if not words:
        return "read"
    cmd = os.path.basename(words[0])
    args = words[1:]
    if cmd in WRAPPERS:
        rest = [a for a in args if not a.startswith("-") and not re.match(r"^[A-Za-z_]\w*=|^\d+[smhd]?$", a)]
        return _command(rest, cwd, temp_dirs, isa) if rest else "read"
    if args and all(a in ("--version", "-V", "--help", "-h", "version") for a in args):
        return "read"
    if cmd in PATH_CMDS:
        paths = [a for a in args if not a.startswith("-")]
        if cmd in ("chmod", "chown", "chgrp") and paths:
            paths = paths[1:]  # mode / owner
        kinds = [path_kind(p, cwd, temp_dirs) for p in paths]
        if paths and all(k in ("temp", "isa") for k in kinds):
            if isa is not None:
                isa += [p for p, k in zip(paths, kinds) if k == "isa"]
            return "read"
        return "write"
    if cmd in WRITE_CMDS:
        return "write"
    if cmd == "sed":
        return "write" if any(a == "-i" or a.startswith("-i") or a.startswith("--in-place") for a in args) else "read"
    if cmd == "find":
        return "write" if any(a in ("-delete", "-exec", "-execdir", "-ok", "-okdir") or a.startswith("-fprint")
                              or a == "-fls" for a in args) else "read"
    if cmd in ("awk", "gawk", "mawk"):
        return "unknown" if any("system(" in a or re.search(r"print[^;]*>", a) for a in args) else "read"
    if cmd == "git":
        return _git(args)
    if cmd == "gh":
        return _gh(args)
    if cmd == "isa":
        return "read"
    if cmd in READ_CMDS:
        return "read"
    if cmd in ("curl", "http", "https"):
        if any(a in ("-o", "-O", "--output", "--remote-name", "-T", "--upload-file") for a in args):
            return "write"
        if any(a in ("-X", "--request", "-d", "--data", "--data-raw", "-F", "--form") for a in args):
            return "unknown"
        return "read"
    if cmd == "tar":
        flags = "".join(a for a in args[:2] if not a.startswith("--"))
        return "write" if "x" in flags or "c" in flags else "read"
    return "unknown"


def _git(args):
    while args and args[0].startswith("-"):
        args = args[2:] if args[0] in ("-C", "-c", "--git-dir", "--work-tree") else args[1:]
    if not args:
        return "read"
    sub, rest = args[0], args[1:]
    if sub in GIT_READ:
        return "read"
    if sub in GIT_WRITE:
        return "write"
    if sub == "branch":
        return "write" if any(a in ("-d", "-D", "-m", "-M", "-c", "-C", "--delete", "--move", "-u", "--set-upstream-to")
                              for a in rest) or [a for a in rest if not a.startswith("-")] else "read"
    if sub == "tag":
        return "read" if not rest or rest[0] in ("-l", "--list", "-n") else "write"
    if sub == "stash":
        return "read" if rest[:1] in (["list"], ["show"]) else "write"
    if sub == "remote":
        return "read" if not rest or rest[0] in ("-v", "show", "get-url") else "write"
    if sub == "config":
        return "read" if any(a in ("--get", "--get-all", "--list", "-l", "--get-regexp") for a in rest) else "write"
    if sub == "worktree":
        return "read" if rest[:1] == ["list"] else "write"
    if sub == "fetch":
        return "unknown"
    return "unknown"


def _gh(args):
    words = [a for a in args if not a.startswith("-")]
    if len(words) >= 2 and words[1] in GH_READ_VERBS:
        return "read"
    if words[:1] == ["api"]:
        method = next((args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-X", "--method")), "GET")
        has_fields = any(a in ("-f", "-F", "--field", "--raw-field", "--input") for a in args)
        return "read" if method.upper() == "GET" and not has_fields else "unknown"
    if words[:1] in (["auth"], ["status"], ["search"], ["browse"]):
        return "read"
    return "unknown"
