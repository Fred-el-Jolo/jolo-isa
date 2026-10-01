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
const { default: isaExtension } = await import("../isa.ts")

const PROJ = mkdtempSync(join(homedir(), ".cache", "isa-pi-proj-"))
mkdirSync(join(PROJ, ".git"))
const E1 = readFileSync(join(ROOT, "skill/ISA/Examples/e1-minimal.md"), "utf8")

function harness(sessionId: string) {
  const handlers: Record<string, Function> = {}
  const notes: string[] = []
  const pi = { on: (name: string, fn: Function) => { handlers[name] = fn; return () => {} } }
  const ctx = {
    cwd: PROJ, hasUI: true, mode: "tui",
    ui: { notify: (m: string) => notes.push(m) },
    sessionManager: { getSessionId: () => sessionId },
  }
  isaExtension(pi as any)
  const fire = (name: string, event: Record<string, unknown> = {}) => handlers[name]?.(event, ctx)
  return { fire, notes }
}

function isaPath() {
  const key = execFileSync("python3", [process.env.ISA_BIN!, "where"], { cwd: PROJ, encoding: "utf8" }).split(/\s+/)[2]
  return join(process.env.ISA_HOME!, key, "20260101-000000_t", "ISA.md")
}

test("first run injects the protocol, later runs only the status", () => {
  const { fire } = harness("s-protocol")
  const first = fire("before_agent_start", { prompt: "hello" })
  assert.match(first.message.content, /\[ISA protocol/)
  assert.equal(first.message.display, false)
  const second = fire("before_agent_start", { prompt: "again" })
  assert.doesNotMatch(second.message.content, /\[ISA protocol/)
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

// a turn that leaves a real ISA problem (progress lies) after a project change
function problemTurn(fire: Function) {
  fire("before_agent_start", { prompt: "do it" })
  const p = isaPath(); mkdirSync(dirname(p), { recursive: true })
  writeFileSync(p, E1.replace("progress: 0/4", "progress: 4/4"))
  fire("tool_result", { toolName: "write", input: { path: p }, content: [], isError: false })
  fire("tool_result", { toolName: "edit", input: { path: join(PROJ, "x.py") }, content: [], isError: false })
}

test("real ISA problem: exactly one continuation per prompt", () => {
  const { fire, notes } = harness("s-settle")
  problemTurn(fire)
  const first = fire("agent_before_settle", DONE)
  assert.equal(first.continue, true)
  assert.match(first.entries[0].content, /progress `4\/4` but criteria say 0\/4/)
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
