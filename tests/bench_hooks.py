#!/usr/bin/env python3
"""ISC-25: wall time of hook invocations (PreToolUse with a big bound ISA, Stop, PostToolUse)."""
import json, os, subprocess, sys, tempfile, time, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISA = os.path.join(ROOT, "runtime", "bin", "isa")
tmp = tempfile.mkdtemp()
env = dict(os.environ, ISA_HOME=tmp)
big = open(os.path.join(ROOT, "skill/ISA/Examples/e5-enterprise.md")).read()
key = subprocess.run([sys.executable, ISA, "where"], cwd=ROOT, env=env, text=True, capture_output=True).stdout.split()[2]
p = os.path.join(tmp, key, "20260101-000000_big", "ISA.md"); os.makedirs(os.path.dirname(p)); open(p, "w").write(big)
def run(d):
    d.update(session_id="bench", cwd=ROOT, prompt_id="p")
    t = time.perf_counter()
    subprocess.run([sys.executable, ISA, "hook", "claude"], input=json.dumps(d), text=True, capture_output=True, env=env)
    return (time.perf_counter() - t) * 1000
run({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": p}})
res = {}
for name, d in [("PreToolUse(Edit, bound 900-line ISA)", {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {"file_path": os.path.join(ROOT, "x.py")}}),
                ("PreToolUse(Read)", {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "x"}}),
                ("PostToolUse(ISA edit)", {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": p}}),
                ("Stop", {"hook_event_name": "Stop"}),
                ("SessionStart", {"hook_event_name": "SessionStart", "source": "startup"})]:
    ts = [run(dict(d)) for _ in range(50 if name.startswith("PreToolUse(Edit") else 10)]
    res[name] = max(ts)
    print(f"{name:<40} median {sorted(ts)[len(ts)//2]:6.1f} ms   max {max(ts):6.1f} ms")
shutil.rmtree(tmp)
sys.exit(0 if max(res.values()) < 300 else 1)
