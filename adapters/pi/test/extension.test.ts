// node --test adapters/pi/test/extension.test.ts   (Node ≥ 22.18 strips the types)
// The pi adapter maps pi events to engine events and engine results back to pi — nothing else. These tests drive
// it through a mock `pi` against a fake engine (the decisions are tested in Python, tests/test_foundations.py),
// plus one call to the real engine: a guarded write is refused.
import { test } from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..")
process.env.ISA_BIN = join(ROOT, "runtime", "bin", "isa")
process.env.ISA_HOME = mkdtempSync(join(tmpdir(), "isa-pi-"))
process.env.ISA_JEV_BIN = join(process.env.ISA_HOME, "no-jev-here")
delete process.env.ISA_MODE
const { default: isaExtension, callEngine } = await import("../isa.ts")

type Result = Record<string, unknown>

function harness(answers: Record<string, Result | (() => Result)>, ui: Record<string, Function> = {}, hasUI = true) {
  const handlers: Record<string, Function> = {}
  const notes: string[] = []
  const calls: Record<string, unknown>[] = []
  const engine = (payload: Record<string, unknown>) => {
    calls.push(payload)
    const a = answers[payload.event as string]
    return (typeof a === "function" ? a() : a) ?? {}
  }
  const pi = { on: (name: string, fn: Function) => { handlers[name] = fn; return () => {} } }
  const ctx = {
    cwd: "/tmp/proj", hasUI, mode: "tui",
    ui: { notify: (m: string) => notes.push(m), ...ui },
    sessionManager: { getSessionId: () => "s1", getBranch: () => [] },
  }
  isaExtension(pi as any, engine as any)
  const fire = (name: string, event: Record<string, unknown> = {}) => handlers[name]?.(event, ctx)
  return { fire, notes, calls }
}

test("input: session start once, then the gate; its context reaches the model at before_agent_start", async () => {
  const h = harness({ session_start: { context: "PROTOCOL" }, prompt: { context: "GATE", warn: "ISA gate — Jev 0.93 → ON" } })
  await h.fire("input", { text: "build it", source: "interactive" })
  const res = await h.fire("before_agent_start", { prompt: "build it" })
  assert.equal(res.message.content, "PROTOCOL\n\nGATE")
  assert.equal(res.message.display, false)
  assert.deepEqual(h.calls.map((c) => c.event), ["session_start", "prompt"])
  assert.ok(h.notes.includes("ISA gate — Jev 0.93 → ON"))
  await h.fire("input", { text: "more", source: "interactive" })
  assert.deepEqual(h.calls.map((c) => c.event), ["session_start", "prompt", "prompt"])
})

test("the gate's question: asked with select, the pick reported as ask_answer", async () => {
  const picks: string[] = []
  const select = async (_t: string, options: string[]) => { picks.push(options.join("|")); return options[1] }
  const h = harness({ prompt: { ask: "ISA is not enabled for this prompt (Jev: 0.50). Continue?",
                                options: ["Continue without ISA", "Enable ISA"] },
                      ask_answer: { context: "ENABLED" } }, { select })
  await h.fire("input", { text: "rename it", source: "interactive" })
  const res = await h.fire("before_agent_start", { prompt: "rename it" })
  assert.deepEqual(picks, ["Continue without ISA|Enable ISA"])
  const ans = h.calls.find((c) => c.event === "ask_answer")!
  assert.equal(ans.choice, "Enable ISA")
  assert.match(res.message.content, /ENABLED/)
})

test("a message typed while the agent runs is not judged", async () => {
  const h = harness({ prompt: { context: "GATE" } })
  await h.fire("input", { text: "also this", source: "interactive", streamingBehavior: "steer" })
  assert.equal(h.calls.length, 0)
})

test("tool_call: a deny blocks the tool with its reason", async () => {
  const h = harness({ pre_tool: { deny: "ISA: written only by `isa` commands" } })
  const res = await h.fire("tool_call", { toolName: "write", input: { path: "x" } })
  assert.deepEqual(res, { block: true, reason: "ISA: written only by `isa` commands" })
  assert.equal(h.calls[0].tool, "write")
})

test("tool_result: the tool's text goes to the engine, its context is appended", async () => {
  const h = harness({ post_tool: { context: "ISA bound" } })
  const res = await h.fire("tool_result", { toolName: "bash", input: { command: "isa new x --tier E1" },
                                            content: [{ type: "text", text: "ISA: /h/x/ISA.md" }] })
  assert.equal(h.calls[0].tool_output, "ISA: /h/x/ISA.md")
  assert.equal(res.content.at(-1).text, "\n[ISA] ISA bound")
})

test("agent_before_settle: a block continues the run once; an aborted run is never checked", async () => {
  const h = harness({ stop: { block: "ISA check: TRIAGE" } })
  const res = await h.fire("agent_before_settle", { outcome: "completed" })
  assert.equal(res.continue, true)
  assert.equal(res.entries[0].content, "ISA check: TRIAGE")
  await h.fire("agent_before_settle", { outcome: "aborted" })
  assert.equal(h.calls.filter((c) => c.event === "stop").length, 1)
})

test("the ack question: Esc is never an ack; the pick goes back with its kind and path", async () => {
  const h = harness({ stop: { ask: "Acknowledge docs/x-01-spec.md?", options: ["Acknowledge", "Request changes"],
                              ask_kind: "ack", ask_path: "/p/docs/x-01-spec.md" },
                      ask_answer: { block: "revise it" } }, { select: async () => undefined })
  const res = await h.fire("agent_before_settle", { outcome: "completed" })
  const ans = h.calls.find((c) => c.event === "ask_answer")!
  assert.deepEqual([ans.choice, ans.ask_kind, ans.ask_path], ["Request changes", "ack", "/p/docs/x-01-spec.md"])
  assert.equal(res.continue, true)
})

test("an engine failure fails open: a warning, no block", async () => {
  const h = harness({ pre_tool: () => { throw new Error("boom") } })
  const res = await h.fire("tool_call", { toolName: "write", input: { path: "x" } })
  assert.equal(res, undefined)
  assert.ok(h.notes.some((n) => /ISA hook error/.test(n) && /boom/.test(n)))
})

test("the real engine refuses a write onto an ISA file", () => {
  const isa = join(process.env.ISA_HOME!, "dev-x", "20260101-000000_t", "ISA.md")
  const res = callEngine({ event: "pre_tool", session: "s1", cwd: tmpdir(), prompt_id: "p1", tool: "write",
                           tool_input: { path: isa, content: "x" } })
  assert.match(String(res.deny), /written only by `isa` commands/)
  rmSync(process.env.ISA_HOME!, { recursive: true, force: true })
})
