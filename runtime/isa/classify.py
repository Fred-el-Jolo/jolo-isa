"""What a tool call does: read, an `isa` command, a project write, unknown — or a guarded write.

    read      never gated (reading, searching, asking)
    isa-cmd   an `isa` command: the only writer of ISA entities, always allowed (it checks itself)
    write     a known project change: allowed in BUILD only
    unknown   can't tell (a script, a build tool): treated as a project change
    guarded   touches an ISA, a spec, a plan or anything under ~/.isa other than by reading or by `isa`:
              refused in every stage (FOUNDATION_2)

Paths decide first: ISA_HOME and `docs/YYYY-MM-DD-<slug>-0{1-spec,2-plan}.md` are guarded; temp dirs and the
agent's own memory folder are free; everything else belongs to the project.
"""
import os
import re
import shlex

from . import state

READ_TOOLS = {
    "Read", "Glob", "Grep", "LS", "WebFetch", "WebSearch", "TodoWrite", "TodoRead", "Task", "Agent",
    "ToolSearch", "Skill", "AskUserQuestion", "ExitPlanMode", "EnterPlanMode", "ListMcpResourcesTool",
    "ReadMcpResourceTool", "Monitor", "TaskStop", "BashOutput", "KillShell", "SendMessage", "ListAgents",
    "ScheduleWakeup", "SendFeedback", "ReportFindings", "EnterWorktree", "ExitWorktree",
    "read", "grep", "find", "ls",
}
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "write", "edit"}
SHELL_TOOLS = {"Bash", "bash", "PowerShell", "powershell"}
_READ_VERB = re.compile(r"(^|[_.-])(read|get|list|search|query|fetch|find|view|show|describe|lookup|"
                        r"guide|status|info|count|check|preview|download|export|authenticate)", re.I)
_WRITE_VERB = re.compile(r"(^|[_.-])(write|edit|create|update|delete|remove|send|post|push|set|put|"
                         r"move|rename|upload|insert|publish|merge|commit|deploy|batch|apply)", re.I)
DOC_REF = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+-0(?:1-spec|2-plan)\.md")


def tool_paths(tool_input):
    ti = tool_input or {}
    return [ti[k] for k in ("file_path", "notebook_path", "path") if isinstance(ti.get(k), str) and ti.get(k)]


def path_kind(path, cwd, temp_dirs=()):
    p = os.path.expanduser(path)
    if not os.path.isabs(p):
        p = os.path.join(cwd or os.getcwd(), p)
    if state.is_isa_path(p) or state.is_doc_path(p):
        return "guarded"
    rp = os.path.realpath(p)
    if is_agent_memory(rp):
        return "temp"
    root = state.project_root(cwd)
    if (rp + os.sep).startswith(root + os.sep) and root != os.path.realpath(os.path.expanduser("~")):
        return "project"
    if any((rp + os.sep).startswith(t + os.sep) for t in _temp_roots(temp_dirs)):
        return "temp"
    return "project"


def is_agent_memory(real_path):
    """~/.claude/projects/<project>/memory/… (the agent's notes; ISA_AGENT_MEMORY_ROOT overrides the parent)."""
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
    ti = tool_input or {}
    if tool in FILE_TOOLS:
        kinds = [path_kind(p, cwd, temp_dirs) for p in tool_paths(ti)]
        if "guarded" in kinds:
            return "guarded"
        return "read" if kinds and all(k == "temp" for k in kinds) else "write"
    if tool in SHELL_TOOLS:
        return bash(ti.get("command", ""), cwd, temp_dirs)
    if tool in READ_TOOLS:
        return "read"
    name = tool.split("__")[-1] if tool.startswith("mcp__") else tool
    if _WRITE_VERB.search(name):
        return "unknown"
    return "read" if _READ_VERB.search(name) else "unknown"


# ------------------------------------------------------------------ bash

READ_CMDS = {
    "ls", "cat", "head", "tail", "less", "more", "wc", "grep", "egrep", "fgrep", "rg", "ag", "fd", "tree",
    "stat", "file", "du", "df", "pwd", "which", "whereis", "type", "echo", "printf", "date", "whoami", "id",
    "uname", "printenv", "hostname", "ps", "jq", "yq", "sort", "uniq", "cut", "tr", "column", "diff", "cmp",
    "md5sum", "sha1sum", "sha256sum", "basename", "dirname", "realpath", "readlink", "test", "[", "true",
    "false", "nl", "od", "xxd", "hexdump", "strings", "bat", "batcat", "cal", "uptime", "free", "lsblk",
    "sleep", "seq", "expr", "comm", "paste", "fold", "fmt", "tac", "rev", "man", "tldr", "help", "awk",
    "gawk", "mawk", "eza", "exa", "cd", "pushd", "popd", "export", "unset", "set", "shopt", "wait",
    "sed", "find", "git", "gh", "command", "local", "declare", "read", "shasum", "lsof", "pgrep",
    "whatis", "apropos", "getconf", "locale", "tput", "stty", "ugrep", "zcat", "zgrep", "pdfinfo",
    "identify", "soxi", "ffprobe", "xmllint", "cloc", "tokei",
}
WRITE_CMDS = {
    "rm", "rmdir", "mv", "cp", "mkdir", "touch", "ln", "chmod", "chown", "chgrp", "tee", "dd", "truncate",
    "install", "rsync", "patch", "unzip", "shred", "sudo", "doas", "mkfifo", "mktemp", "npm", "pnpm", "yarn",
    "bun", "pip", "pip3", "uv", "cargo", "go", "make", "apt", "apt-get", "brew", "mise", "docker", "kubectl",
    "terraform", "wget", "scp", "systemctl", "crontab", "kill", "pkill", "killall",
}
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
ORDER = {"read": 0, "isa-cmd": 1, "unknown": 2, "write": 3, "guarded": 4}
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _tokens(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|<>()")
    lex.whitespace_split = True
    lex.commenters = "#"
    return list(lex)


def _worse(a, b):
    return a if ORDER[a] >= ORDER[b] else b


def _drop_heredoc_bodies(cmd):
    lines, out, pending = cmd.split("\n"), [], []
    for line in lines:
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending = [m.group(2) for m in _HEREDOC.finditer(line)]
    return "\n".join(out)


def _refs(raw, cwd):
    """Does the command's text (heredoc bodies and quotes included) name an ISA entity, or run inside ISA_HOME?"""
    h = os.path.realpath(state.home())
    if state.is_isa_path(cwd or os.getcwd()):
        return True
    return bool(h in raw or "~/.isa" in raw or "$ISA_HOME" in raw or "${ISA_HOME}" in raw or DOC_REF.search(raw))


def _segments(cmd):
    toks = _tokens(cmd.replace("\\\n", " ").replace("\n", " ; "))
    seg, out = [], []
    for t in toks + [";"]:
        if t in SEPARATORS or all(c in ";&|()" for c in t):
            if seg:
                out.append(seg)
            seg = []
        else:
            seg.append(t)
    return out


def bash(cmd, cwd, temp_dirs=()):
    if not cmd or not cmd.strip():
        return "read"
    raw = cmd
    cmd = _drop_heredoc_bodies(cmd)
    if ">(" in cmd:
        return "guarded" if _refs(raw, cwd) else "unknown"
    cmd = cmd.replace("<(", " ; ")
    subst = "$(" in _without_single_quoted(cmd) or "`" in _without_single_quoted(cmd)
    try:
        segs = _segments(re.sub(r"\$\([^)]*\)|`[^`]*`", "X", cmd) if subst else cmd)
    except ValueError:
        return "guarded" if _refs(raw, cwd) else "unknown"
    worst = "read"
    kinds = []
    for seg in segs:
        k = _segment(seg, cwd, temp_dirs)
        kinds.append(k)
        worst = _worse(worst, k)
    if subst and worst != "guarded":
        worst = _worse(worst, "unknown")
    # code that names an ISA entity in its text (a script, `python3 -c`, a heredoc fed to an interpreter) may write it
    # where no target is visible; a known command's targets were judged above, so a mere mention (a commit message,
    # an echo) is not a write
    if worst != "guarded" and (worst == "unknown" or subst) and _refs(raw, cwd):
        return "guarded"
    return worst


def _without_single_quoted(cmd):
    out, i, n, dq = [], 0, len(cmd), False
    while i < n:
        c = cmd[i]
        if c == "\\" and i + 1 < n:
            out.append(cmd[i:i + 2])
            i += 2
            continue
        if c == '"':
            dq = not dq
        elif c == "'" and not dq:
            j = cmd.find("'", i + 1)
            if j < 0:
                return cmd
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _segment(words, cwd, temp_dirs):
    kind, clean, i = "read", [], 0
    while i < len(words):
        w = words[i]
        if w in REDIRECTS or re.match(r"^\d*(>>?|>\|)$", w) or w in ("<", "<<", "<<<"):
            target = words[i + 1] if i + 1 < len(words) else ""
            if not (w in ("<", "<<", "<<<") or re.match(r"^&?\d+$", target) or target in SAFE_TARGETS):
                pk = path_kind(target, cwd, temp_dirs)
                kind = _worse(kind, "guarded" if pk == "guarded" else "write" if pk == "project" else "read")
            i += 2
            continue
        clean.append(w)
        i += 1
    return _worse(kind, _command(clean, cwd, temp_dirs))


def _command(words, cwd=None, temp_dirs=()):
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        words = words[1:]
    if not words:
        return "read"
    cmd, args = os.path.basename(words[0]), words[1:]
    if cmd in WRAPPERS:
        rest = [a for a in args if not a.startswith("-") and not re.match(r"^[A-Za-z_]\w*=|^\d+[smhd]?$", a)]
        return _command(rest, cwd, temp_dirs) if rest else "read"
    if cmd == "isa":
        return "isa-cmd"
    if args and all(a in ("--version", "-V", "--help", "-h", "version") for a in args):
        return "read"
    if cmd in PATH_CMDS:
        paths = [a for a in args if not a.startswith("-")]
        if cmd in ("chmod", "chown", "chgrp") and paths:
            paths = paths[1:]
        kinds = [path_kind(p, cwd, temp_dirs) for p in paths]
        if "guarded" in kinds:
            return "guarded"
        return "read" if paths and all(k == "temp" for k in kinds) else "write"
    if cmd in WRITE_CMDS:
        return "write"
    if cmd == "sed":
        if not any(a == "-i" or a.startswith("-i") or a.startswith("--in-place") for a in args):
            return "read"
        return "guarded" if any(path_kind(a, cwd, temp_dirs) == "guarded" for a in args if not a.startswith("-")) \
            else "write"
    if cmd == "find":
        return "write" if any(a in ("-delete", "-exec", "-execdir", "-ok", "-okdir") or a.startswith("-fprint")
                              or a == "-fls" for a in args) else "read"
    if cmd in ("awk", "gawk", "mawk"):
        return "unknown" if any("system(" in a or re.search(r"print[^;]*>", a) for a in args) else "read"
    if cmd == "git":
        return _git(args)
    if cmd == "gh":
        return _gh(args)
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
        return "write" if any(a in ("-d", "-D", "-m", "-M", "-c", "-C", "--delete", "--move", "-u",
                                    "--set-upstream-to") for a in rest) or [a for a in rest if not a.startswith("-")] \
            else "read"
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
