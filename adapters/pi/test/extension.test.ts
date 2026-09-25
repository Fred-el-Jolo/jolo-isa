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

test("stale ISA: exactly one continuation per prompt", () => {
  const { fire, notes } = harness("s-settle")
  fire("before_agent_start", { prompt: "do it" })
  const p = isaPath(); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, E1)
  fire("tool_result", { toolName: "write", input: { path: p }, content: [], isError: false })
  fire("tool_result", { toolName: "edit", input: { path: join(PROJ, "x.py") }, content: [], isError: false })
  const first = fire("agent_before_settle", {})
  assert.equal(first.continue, true)
  assert.match(first.entries[0].content, /changed after the ISA's last update/)
  assert.equal(fire("agent_before_settle", {}), undefined)
  assert.ok(notes.some((n) => /ending the turn anyway/.test(n)))
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
