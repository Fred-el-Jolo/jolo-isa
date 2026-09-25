// ISA enforcement for pi — the same engine as the Claude Code hooks (`isa hook pi`).
//
// Every decision is made by the Python engine (runtime/isa/engine.py); this file only maps
// pi events to engine events and engine results back to pi. It fails OPEN: pi blocks a tool
// when a tool_call handler throws, so every handler catches its own errors and warns instead.
//
//   before_agent_start  → engine "session_start" (first run / after compaction) + "prompt"
//   tool_call           → engine "pre_tool"      → { block, reason }
//   tool_result         → engine "post_tool" / "tool_failed" → lint feedback appended to the result
//   session_compact     → engine "compacted"     → protocol + Goal re-injected on the next run
//   agent_before_settle → engine "stop"          → one continuation per prompt, then a warning
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent"
import { spawnSync } from "node:child_process"
import { homedir } from "node:os"
import { join } from "node:path"

const ISA_BIN = process.env.ISA_BIN || join(homedir(), ".local", "share", "isa", "runtime", "bin", "isa")
const TIMEOUT_MS = Number(process.env.ISA_HOOK_TIMEOUT_MS || 5000)

type EngineResult = { context?: string; deny?: string; block?: string; warn?: string }

export function callEngine(payload: Record<string, unknown>): EngineResult {
  const r = spawnSync("python3", [ISA_BIN, "hook", "pi"], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    timeout: TIMEOUT_MS,
  })
  if (r.error) throw r.error
  const out = (r.stdout || "").trim()
  if (!out) throw new Error(`isa hook pi: no output (exit ${r.status}) ${(r.stderr || "").slice(0, 300)}`)
  return JSON.parse(out) as EngineResult
}

export default function isaExtension(pi: ExtensionAPI, engine: typeof callEngine = callEngine) {
  let promptSeq = 0
  let startedFor = "" // session id whose protocol has been injected
  let compacted = false

  const sessionId = (ctx: ExtensionContext) => {
    try {
      return ctx.sessionManager.getSessionId() || "unknown"
    } catch {
      return "unknown"
    }
  }
  const warn = (ctx: ExtensionContext | undefined, msg: string) => {
    try {
      if (ctx?.hasUI) ctx.ui.notify(msg, "warning")
      else console.error(msg)
    } catch {
      console.error(msg)
    }
  }
  const run = (ctx: ExtensionContext, event: string, extra: Record<string, unknown> = {}): EngineResult => {
    try {
      const res = engine({ event, session: sessionId(ctx), cwd: ctx.cwd, prompt_id: `pi-${promptSeq}`, ...extra })
      if (res.warn) warn(ctx, res.warn)
      return res
    } catch (e) {
      warn(ctx, `ISA hook error (not enforced for this event): ${(e as Error).message}`)
      return {}
    }
  }

  pi.on("session_compact", (_event, ctx) => {
    compacted = true
    run(ctx, "compacted")
  })

  pi.on("before_agent_start", (event, ctx) => {
    promptSeq += 1
    const parts: string[] = []
    const sid = sessionId(ctx)
    if (startedFor !== sid || compacted) {
      const start = run(ctx, "session_start", { source: compacted ? "compact" : "startup" })
      if (start.context) parts.push(start.context)
      startedFor = sid
      compacted = false
    }
    const p = run(ctx, "prompt", { prompt: event.prompt })
    if (p.context) parts.push(p.context)
    if (!parts.length) return
    return { message: { customType: "isa", content: parts.join("\n\n"), display: false } }
  })

  pi.on("tool_call", (event, ctx) => {
    const res = run(ctx, "pre_tool", { tool: event.toolName, tool_input: event.input })
    if (res.deny) return { block: true, reason: res.deny }
  })

  pi.on("tool_result", (event, ctx) => {
    const res = run(ctx, event.isError ? "tool_failed" : "post_tool", {
      tool: (event as { toolName?: string }).toolName,
      tool_input: event.input,
    })
    if (!res.context) return
    return { content: [...event.content, { type: "text" as const, text: `\n[ISA] ${res.context}` }] }
  })

  pi.on("agent_before_settle", (_event, ctx) => {
    const res = run(ctx, "stop")
    if (!res.block) return
    return {
      continue: true,
      entries: [{ type: "custom_message" as const, customType: "isa-stop", content: res.block, display: true }],
    }
  })
}
