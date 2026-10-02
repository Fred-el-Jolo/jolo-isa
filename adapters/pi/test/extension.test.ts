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
process.env.ISA_JUDGE = "heuristic" // no test ever calls a model
delete process.env.ISA_MODE
const { default: isaExtension } = await import("../isa.ts")

const PROJ = mkdtempSync(join(homedir(), ".cache", "isa-pi-proj-"))
mkdirSync(join(PROJ, ".git"))
const E1 = readFileSync(join(ROOT, "skill/ISA/Examples/e1-minimal.md"), "utf8")

function harness(sessionId: string, engine?: Function, branch: unknown[] = []) {
  const handlers: Record<string, Function> = {}
  const notes: string[] = []
  const pi = { on: (name: string, fn: Function) => { handlers[name] = fn; return () => {} } }
  const ctx = {
    cwd: PROJ, hasUI: true, mode: "tui",
    ui: { notify: (m: string) => notes.push(m) },
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

test("an OFF prompt injects nothing; a task prompt injects the ON block once", () => {
  const { fire, notes } = harness("s-protocol")
  assert.equal(fire("before_agent_start", { prompt: "hello" }), undefined)
  assert.ok(notes.some((n) => /^ISA: OFF/.test(n)))
  const on = fire("before_agent_start", { prompt: "Fix the bug in dates.py so the tests pass" })
  assert.match(on.message.content, /\[ISA: ON/)
  assert.equal(on.message.display, false)
  assert.ok(notes.some((n) => /^ISA: ON/.test(n)))
  const again = fire("before_agent_start", { prompt: "and add a test for it too please" })
  assert.doesNotMatch(again.message.content, /\[ISA: ON/)
})

test("the prompt call gets its own timeout and the previous assistant message", () => {
  const calls: { payload: Record<string, unknown>; timeout?: number }[] = []
  const stub = (payload: Record<string, unknown>, timeout?: number) => { calls.push({ payload, timeout }); return {} }
  const branch = [
    { type: "message", message: { role: "user", content: [{ type: "text", text: "review it?" }] } },
    { type: "message", message: { role: "assistant", content: [{ type: "text", text: "x".repeat(3000) + "I propose a review." }] } },
    { type: "custom", customType: "isa" },
  ]
  const { fire } = harness("s-stub", stub, branch)
  fire("before_agent_start", { prompt: "go" })
  fire("tool_call", { toolName: "read", input: { path: "x" } })
  const prompt = calls.find((c) => c.payload.event === "prompt")!
  assert.equal(prompt.timeout, 20000)
  assert.equal((prompt.payload.context as string).length, 2000)
  assert.match(prompt.payload.context as string, /I propose a review\.$/)
  for (const c of calls.filter((c) => c.payload.event !== "prompt")) assert.equal(c.timeout, undefined)
})

test("mutating tool is blocked until an ISA is bound", () => {
  const { fire } = harness("s-gate")
  fire("before_agent_start", { prompt: "edit x" })
  const blocked = fire("tool_call", { toolName: "write", input: { path: join(PROJ, "x.py"), content: "x" } })
  assert.equal(blocked.block, true)
  assert.match(blocked.reason, /no ISA is bound/)
  assert.equal(fire("tool_call", { toolName: "read", input: { path: join(PROJ, "x.py") } }), undefined)
  const p = isaPath(); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, E1)
  const res = fire("tool_result", { toolName: "write", input: { path: p }, content: [{ type: "text", text: "ok" }], isError: false })
  assert.match(res.content.at(-1).text, /lint ok/)
  assert.equal(fire("tool_call", { toolName: "write", input: { path: join(PROJ, "x.py"), content: "x" } }), undefined)
})

const DONE = { outcome: "completed", context: { canContinue: true } }

// a turn that leaves a real ISA problem (a lint error: no Anti ISC) after a project change
function problemTurn(fire: Function) {
  fire("before_agent_start", { prompt: "do it" })
  const p = isaPath(); mkdirSync(dirname(p), { recursive: true })
  writeFileSync(p, E1.replace("ISC-4: Anti:", "ISC-4:"))
  fire("tool_result", { toolName: "write", input: { path: p }, content: [], isError: false })
  fire("tool_result", { toolName: "edit", input: { path: join(PROJ, "x.py") }, content: [], isError: false })
}

test("real ISA problem: exactly one continuation per prompt", () => {
  const { fire, notes } = harness("s-settle")
  problemTurn(fire)
  const first = fire("agent_before_settle", DONE)
  assert.equal(first.continue, true)
  assert.match(first.entries[0].content, /no `Anti:` ISC/)
  assert.equal(fire("agent_before_settle", DONE), undefined)
  assert.ok(notes.some((n) => /ending the turn anyway/.test(n)))
})

test("a run the user aborted is never continued", () => {
  const { fire } = harness("s-aborted")
  problemTurn(fire)
  assert.equal(fire("agent_before_settle", { outcome: "aborted", context: { canContinue: true } }), undefined)
})

test("a run that ended in an error outcome is never continued", () => {
  const { fire } = harness("s-error")
  problemTurn(fire)
  assert.equal(fire("agent_before_settle", { outcome: "error", context: { canContinue: true } }), undefined)
  assert.equal(fire("agent_before_settle", { outcome: "completed", context: { canContinue: false } }), undefined)
})

test("a resumed session (new pi process) still blocks its first turn", () => {
  const first = harness("s-resume")  // pi process 1
  problemTurn(first.fire)
  assert.equal(first.fire("agent_before_settle", DONE).continue, true)
  const again = harness("s-resume")  // pi process 2, same session id, prompt counter restarts
  problemTurn(again.fire)
  assert.equal(again.fire("agent_before_settle", DONE).continue, true)
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
