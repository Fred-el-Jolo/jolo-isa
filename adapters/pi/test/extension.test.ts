// node --test adapters/pi/test/extension.test.ts   (Node ≥ 22.18 strips the types)
// Drives the extension through a mock `pi` against the real engine in a throwaway ISA_HOME.
import { test } from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs"
import { tmpdir, homedir } from "node:os"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { execFileSync } from "node:child_process"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..")
process.env.ISA_BIN = join(ROOT, "runtime", "bin", "isa")
process.env.ISA_HOME = mkdtempSync(join(tmpdir(), "isa-pi-"))
process.env.ISA_SKILL_DIR = join(ROOT, "skill", "ISA")
process.env.ISA_JEV_BIN = join(process.env.ISA_HOME, "no-jev-here") // no test reaches the real `jev`
delete process.env.ISA_MODE
const { default: isaExtension } = await import("../isa.ts")

const PROJ = mkdtempSync(join(homedir(), ".cache", "isa-pi-proj-"))
mkdirSync(join(PROJ, ".git"))
const E1 = readFileSync(join(ROOT, "skill/ISA/Examples/e1-minimal.md"), "utf8")

// a fake `jev` (SPEC-v2 § 12): answers every question of a preset with FAKE_JEV_P
const FAKE_JEV = join(process.env.ISA_HOME!, "fake-jev")
writeFileSync(FAKE_JEV, `#!/usr/bin/env python3
import json, os, sys
sys.stdin.read()
preset = sys.argv[2]
d = os.environ["JEV_KIT_PRESETS"].split(":")[0]
qs = json.load(open(os.path.join(d, preset + ".json")))["questions"]
p = float(os.environ.get("FAKE_JEV_P", "0.31"))
print(json.dumps({"ok": True, "answers": {q: {"type": "noul", "answer": p} for q in qs}}))
`, { mode: 0o755 })

async function withJev(p: string | null, fn: () => Promise<void>) {
  const saved = process.env.ISA_JEV_BIN
  if (p !== null) { process.env.ISA_JEV_BIN = FAKE_JEV; process.env.FAKE_JEV_P = p }
  try { await fn() } finally { process.env.ISA_JEV_BIN = saved; delete process.env.FAKE_JEV_P }
}
function harness(sessionId: string, engine?: Function, branch: unknown[] = [], ui: Record<string, Function> = {},
                 hasUI = true) {
  const handlers: Record<string, Function> = {}
  const notes: string[] = []
  const pi = { on: (name: string, fn: Function) => { handlers[name] = fn; return () => {} } }
  const ctx = {
    cwd: PROJ, hasUI, mode: "tui",
    ui: { notify: (m: string) => notes.push(m), ...ui },
    sessionManager: { getSessionId: () => sessionId, getBranch: () => branch },
  }
  if (engine) isaExtension(pi as any, engine as any)
  else isaExtension(pi as any)
  const fire = (name: string, event: Record<string, unknown> = {}) => handlers[name]?.(event, ctx)
  return { fire, notes }
}

function isaPath() {
  const key = execFileSync("python3", [process.env.ISA_BIN!, "where"], { cwd: PROJ, encoding: "utf8" }).split(/\s+/)[2]
  return join(process.env.ISA_HOME!, key, "20260101-000000_t", "ISA.md")
}

test("the gate: Jev below the line asks; a Jev yes injects the ON block once", async () => {
  await withJev("0.5", async () => {
    const select = async (_t: string, options: string[]) => options[0]
    const { fire, notes } = harness("s-protocol", undefined, [], { select })
    await fire("input", { text: "hello", source: "interactive" })
    assert.equal(await fire("before_agent_start", { prompt: "hello" }), undefined)
    assert.ok(notes.some((n) => /^ISA gate — Jev 0\.50 → asking you/.test(n)))
    process.env.FAKE_JEV_P = "0.93"
    await fire("input", { text: "Fix the bug in dates.py so the tests pass", source: "interactive" })
    const on = await fire("before_agent_start", { prompt: "Fix the bug in dates.py so the tests pass" })
    assert.match(on.message.content, /\[ISA: ON/)
    assert.equal(on.message.display, false)
    assert.ok(notes.some((n) => /^ISA gate — Jev 0\.93 → ON/.test(n)))
    await fire("input", { text: "and add a test for it too please", source: "interactive" })
    const again = await fire("before_agent_start", { prompt: "and add a test for it too please" })
    assert.doesNotMatch(again.message.content, /\[ISA: ON/)
  })
})

test("prompt and stop carry the last assistant message; every call has the same limit", async () => {
  const calls: { payload: Record<string, unknown>; timeout?: number }[] = []
  const stub = (payload: Record<string, unknown>, timeout?: number) => { calls.push({ payload, timeout }); return {} }
  const branch = [
    { type: "message", message: { role: "user", content: [{ type: "text", text: "review it?" }] } },
    { type: "message", message: { role: "assistant", content: [{ type: "text", text: "x".repeat(3000) + "I propose a review." }] } },
    { type: "custom", customType: "isa" },
  ]
  const { fire } = harness("s-stub", stub, branch)
  await fire("before_agent_start", { prompt: "go" })
  fire("tool_call", { toolName: "read", input: { path: "x" } })
  await fire("agent_before_settle", { outcome: "completed", context: { canContinue: true } })
  const prompt = calls.find((c) => c.payload.event === "prompt")!
  assert.equal((prompt.payload.context as string).length, 2000)
  assert.match(prompt.payload.context as string, /I propose a review\.$/)
  const stop = calls.find((c) => c.payload.event === "stop")!
  assert.match(stop.payload.context as string, /I propose a review\.$/)
  for (const c of calls) assert.equal(c.timeout, undefined) // callEngine's default: ISA_HOOK_TIMEOUT_MS (15 s)
})

test("mutating tool is blocked until an ISA is bound", async () => {
  const { fire } = harness("s-gate")
  await fire("before_agent_start", { prompt: "edit x" }) // Jev unavailable: the model judges, the session is still OFF
  const blocked = fire("tool_call", { toolName: "write", input: { path: join(PROJ, "x.py"), content: "x" } })
  assert.equal(blocked.block, true)
  assert.match(blocked.reason, /needs an ISA first/) // the write itself switches the session ON
  assert.equal(fire("tool_call", { toolName: "read", input: { path: join(PROJ, "x.py") } }), undefined)
  const p = isaPath(); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, E1)
  const res = fire("tool_result", { toolName: "write", input: { path: p }, content: [{ type: "text", text: "ok" }], isError: false })
  assert.match(res.content.at(-1).text, /lint ok/)
  assert.equal(fire("tool_call", { toolName: "write", input: { path: join(PROJ, "x.py"), content: "x" } }), undefined)
})

const DONE = { outcome: "completed", context: { canContinue: true } }

// a turn that leaves a real ISA problem (a lint error: no Anti ISC) after a project change
async function problemTurn(fire: Function) {
  await fire("before_agent_start", { prompt: "do it" })
  const p = isaPath(); mkdirSync(dirname(p), { recursive: true })
  writeFileSync(p, E1.replace("ISC-4: Anti:", "ISC-4:"))
  fire("tool_result", { toolName: "write", input: { path: p }, content: [], isError: false })
  fire("tool_result", { toolName: "edit", input: { path: join(PROJ, "x.py") }, content: [], isError: false })
}

test("real ISA problem: exactly one continuation per prompt", async () => {
  const { fire, notes } = harness("s-settle")
  await problemTurn(fire)
  const first = await fire("agent_before_settle", DONE)
  assert.equal(first.continue, true)
  assert.match(first.entries[0].content, /no `Anti:` ISC/)
  assert.equal(await fire("agent_before_settle", DONE), undefined)
  assert.ok(notes.some((n) => /ending the turn anyway/.test(n)))
})

test("a run the user aborted is never continued", async () => {
  const { fire } = harness("s-aborted")
  await problemTurn(fire)
  assert.equal(await fire("agent_before_settle", { outcome: "aborted", context: { canContinue: true } }), undefined)
})

test("a run that ended in an error outcome is never continued", async () => {
  const { fire } = harness("s-error")
  await problemTurn(fire)
  assert.equal(await fire("agent_before_settle", { outcome: "error", context: { canContinue: true } }), undefined)
  assert.equal(await fire("agent_before_settle", { outcome: "completed", context: { canContinue: false } }), undefined)
})

test("a resumed session (new pi process) still blocks its first turn", async () => {
  const first = harness("s-resume")  // pi process 1
  await problemTurn(first.fire)
  assert.equal((await first.fire("agent_before_settle", DONE)).continue, true)
  const again = harness("s-resume")  // pi process 2, same session id, prompt counter restarts
  await problemTurn(again.fire)
  assert.equal((await again.fire("agent_before_settle", DONE)).continue, true)
})

test("engine failure fails open with a warning", () => {
  process.env.ISA_FAULT_INJECT = "1"
  try {
    const { fire, notes } = harness("s-fault")
    assert.equal(fire("tool_call", { toolName: "write", input: { path: join(PROJ, "y.py") } }), undefined)
    assert.ok(notes.some((n) => /ISA hook error/.test(n)))
  } finally {
    delete process.env.ISA_FAULT_INJECT
  }
})

test.after(() => {
  rmSync(PROJ, { recursive: true, force: true })
  rmSync(process.env.ISA_HOME!, { recursive: true, force: true })
})

const JUDGED_BRANCH = [
  { type: "message", message: { role: "user", content: [{ type: "text", text: "what does cmd_list print?" }] } },
  { type: "message", message: { role: "assistant", content: [{ type: "text", text: "ISA judge (model): no — a question about the code.\n\nIt prints each task." }] } },
]

test("the model's `no` asks the user, after it answered; Continue ends the turn", async () => {
  const asked: { title: string; options: string[] }[] = []
  const select = async (title: string, options: string[]) => { asked.push({ title, options }); return options[0] }
  const { fire } = harness("s-ask-continue", undefined, JUDGED_BRANCH, { select })
  const p = await fire("before_agent_start", { prompt: "what does cmd_list in todo.py print?" })
  assert.match(p.message.content, /ISA judge \(model\)/)
  assert.doesNotMatch(p.message.content, /AskUserQuestion/) // pi: the extension asks, not the model
  const res = await fire("agent_before_settle", { outcome: "completed", context: { canContinue: true } })
  assert.equal(asked.length, 1)
  assert.equal(asked[0].title, "ISA is not enabled for this prompt (model: no — a question about the code.). Continue?")
  assert.deepEqual(asked[0].options, ["Continue without ISA", "Enable ISA"])
  assert.equal(res, undefined)
})

test("the model's `no` asks the user; Enable ISA continues the run with the ON block", async () => {
  const select = async (_t: string, options: string[]) => options[1]
  const { fire } = harness("s-ask-enable", undefined, JUDGED_BRANCH, { select })
  await fire("before_agent_start", { prompt: "what does cmd_list in todo.py print?" })
  const res = await fire("agent_before_settle", { outcome: "completed", context: { canContinue: true } })
  assert.equal(res.continue, true)
  assert.match(res.entries[0].content, /The user chose Enable ISA/)
  assert.match(res.entries[0].content, /\[ISA: ON/)
})

test("no UI: nobody asks the user, the model's `no` stands", async () => {
  let called = 0
  const select = async () => { called += 1; return "Enable ISA" }
  const { fire } = harness("s-ask-noui", undefined, JUDGED_BRANCH, { select }, false)
  await fire("before_agent_start", { prompt: "what does cmd_list in todo.py print?" })
  const res = await fire("agent_before_settle", { outcome: "completed", context: { canContinue: true } })
  assert.equal(called, 0)
  assert.equal(res, undefined)
})

const QUESTION = "what does cmd_list in todo.py print?"

test("M11: below the line, pi asks at input before the model; Continue injects nothing", async () => {
  await withJev("0.31", async () => {
    const asked: string[] = []
    const select = async (title: string, options: string[]) => { asked.push(title); return options[0] }
    const { fire } = harness("s-m11-continue", undefined, [], { select })
    const r = await fire("input", { text: QUESTION, source: "interactive" })
    assert.deepEqual(r, { action: "continue" })
    assert.deepEqual(asked, ["ISA is not enabled for this prompt (Jev: 0.31). Continue?"])
    assert.equal(await fire("before_agent_start", { prompt: QUESTION }), undefined)
    assert.equal(await fire("agent_before_settle", DONE), undefined)
  })
})

test("M11: Enable ISA at input puts the ON block before the model", async () => {
  await withJev("0.31", async () => {
    const select = async (_t: string, options: string[]) => options[1]
    const { fire } = harness("s-m11-enable", undefined, [], { select })
    await fire("input", { text: QUESTION, source: "interactive" })
    const p = await fire("before_agent_start", { prompt: QUESTION })
    assert.match(p.message.content, /\[ISA: ON/)
  })
})

test("M11: a Jev yes at input turns ON without asking", async () => {
  await withJev("0.93", async () => {
    let called = 0
    const select = async () => { called += 1; return "Continue without ISA" }
    const { fire } = harness("s-m11-yes", undefined, [], { select })
    await fire("input", { text: "please check the flag files today", source: "interactive" })
    assert.equal(called, 0)
    assert.match((await fire("before_agent_start", { prompt: "please check the flag files today" })).message.content, /\[ISA: ON/)
  })
})

test("M11: a message typed while the agent runs is not judged", async () => {
  const calls: Record<string, unknown>[] = []
  const stub = (payload: Record<string, unknown>) => { calls.push(payload); return {} }
  const { fire } = harness("s-m11-steer", stub)
  await fire("input", { text: "also do y", source: "interactive", streamingBehavior: "steer" })
  await fire("input", { text: "and z", source: "interactive", streamingBehavior: "followUp" })
  assert.equal(calls.filter((c) => c.event === "prompt").length, 0)
})

test("M11: a slash prompt reaches the engine raw, at input", async () => {
  const calls: Record<string, unknown>[] = []
  const stub = (payload: Record<string, unknown>) => { calls.push(payload); return {} }
  const { fire } = harness("s-m11-slash", stub)
  await fire("input", { text: "/skill:demo-review utils.py", source: "interactive" })
  await fire("before_agent_start", { prompt: "expanded skill text …" })
  const prompts = calls.filter((c) => c.event === "prompt")
  assert.equal(prompts.length, 1)
  assert.equal(prompts[0].prompt, "/skill:demo-review utils.py")
})

test("M11: Jev unavailable → the model judges; pi asks at settle after its `no`", async () => {
  await withJev(null, async () => {
    const asked: string[] = []
    const select = async (title: string, options: string[]) => { asked.push(title); return options[0] }
    const branch = [{ type: "message", message: { role: "assistant", content: [{ type: "text",
      text: "ISA judge (model): no — a question about the code.\n\nIt prints each task." }] } }]
    const { fire } = harness("s-m11-model", undefined, branch, { select })
    await fire("input", { text: QUESTION, source: "interactive" })
    assert.deepEqual(asked, [])
    assert.match((await fire("before_agent_start", { prompt: QUESTION })).message.content, /ISA judge \(model\)/)
    assert.equal(await fire("agent_before_settle", DONE), undefined)
    assert.deepEqual(asked, ["ISA is not enabled for this prompt (model: no — a question about the code.). Continue?"])
  })
})

test("M11.1: Continue at input lets the prompt's changes through", async () => {
  await withJev("0.2", async () => {
    const select = async (_t: string, options: string[]) => options[0]
    const { fire } = harness("s-m111-pass", undefined, [], { select })
    await fire("input", { text: "commit and push", source: "interactive" })
    await fire("before_agent_start", { prompt: "commit and push" })
    assert.equal(fire("tool_call", { toolName: "write", input: { path: join(PROJ, "z.py"), content: "x" } }), undefined)
  })
})

test("M11.2: below jev_quiet, pi asks nothing at input (quiet)", async () => {
  await withJev("0.1", async () => {
    let called = 0
    const select = async (_t: string, options: string[]) => { called += 1; return options[0] }
    const { fire, notes } = harness("s-m112-quiet", undefined, [], { select })
    await fire("input", { text: "commit and push", source: "interactive" })
    assert.equal(called, 0)
    assert.ok(notes.some((n) => /continue without ISA \(below 0\.30\)/.test(n)))
  })
})
