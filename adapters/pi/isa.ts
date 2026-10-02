// ISA enforcement for pi — the same engine as the Claude Code hooks (`isa hook pi`).
//
// Every decision is made by the Python engine (runtime/isa/engine.py); this file only maps
// pi events to engine events and engine results back to pi. It fails OPEN: pi blocks a tool
// when a tool_call handler throws, so every handler catches its own errors and warns instead.
//
//   input               → engine "session_start" (first run / after compaction) + "prompt": the gate
//                          (SPEC-v2 § 12.4) on the raw text (`/skill:name …` not yet expanded), only
//                          when the agent is idle — a message typed while it runs (steer / followUp)
//                          belongs to the current run. When the gate is not settled as yes the engine
//                          answers `ask`: this extension asks the user right here, before the model sees
//                          anything ("Continue without ISA" / "Enable ISA"), and reports the pick
//                          (engine "ask_answer"). No UI → nobody is asked.
//   before_agent_start  → injects what `input` collected (ON block, the model's judge instruction)
//   tool_call           → engine "pre_tool"      → { block, reason }
//   tool_result         → engine "post_tool" / "tool_failed" → lint feedback appended to the result
//   session_compact     → engine "compacted"     → protocol + Goal re-injected on the next run
//   agent_before_settle → engine "stop" (with the last assistant text: when Jev was unavailable the model
//                          judged, and its `ISA judge (model): no|unsure — …` line makes the engine answer
//                          `ask`: the extension asks here, after the answer; Enable ISA continues the run
//                          with the ON block). One continuation per prompt, then a warning
//                          (completed runs only — never after an abort or an error)
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent"
import { spawnSync } from "node:child_process"
import { homedir } from "node:os"
import { join } from "node:path"

const ISA_BIN = process.env.ISA_BIN || join(homedir(), ".local", "share", "isa", "runtime", "bin", "isa")
// every engine call: no model, no network; the slowest step is a 5 s-capped `git status` on large repos
const TIMEOUT_MS = Number(process.env.ISA_HOOK_TIMEOUT_MS || 15000)
const CONTEXT_CHARS = 2000

type EngineResult = { context?: string; deny?: string; block?: string; warn?: string; ask?: string; options?: string[] }

export function callEngine(payload: Record<string, unknown>, timeoutMs: number = TIMEOUT_MS): EngineResult {
  const r = spawnSync("python3", [ISA_BIN, "hook", "pi"], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    timeout: timeoutMs,
  })
  if (r.error) throw r.error
  const out = (r.stdout || "").trim()
  if (!out) throw new Error(`isa hook pi: no output (exit ${r.status}) ${(r.stderr || "").slice(0, 300)}`)
  return JSON.parse(out) as EngineResult
}

export default function isaExtension(pi: ExtensionAPI, engine: typeof callEngine = callEngine) {
  let promptSeq = 0
  // prompt ids key the engine's "block once per prompt" memory, which outlives this process (resumed
  // sessions keep their state), so each process gets its own prefix
  const runId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
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
  // the tail of the last assistant message on the current branch ("" when there is none)
  const lastAssistantText = (ctx: ExtensionContext): string => {
    try {
      const entries = (ctx.sessionManager as any).getBranch?.() ?? []
      for (let i = entries.length - 1; i >= 0; i--) {
        const m = entries[i]?.type === "message" ? entries[i].message : undefined
        if (m?.role !== "assistant") continue
        const content = typeof m.content === "string" ? m.content
          : (m.content ?? []).filter((c: any) => c?.type === "text").map((c: any) => c.text).join("\n")
        if (content.trim()) return content.slice(-CONTEXT_CHARS)
      }
    } catch {
      // no context is fine: the engine then sees the prompt alone
    }
    return ""
  }
  const run = (ctx: ExtensionContext, event: string, extra: Record<string, unknown> = {}): EngineResult => {
    try {
      const payload = { event, session: sessionId(ctx), cwd: ctx.cwd, prompt_id: `pi-${runId}-${promptSeq}`, ...extra }
      const res = engine(payload)
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

  let pending: string[] | null = null // what the gate at `input` leaves for before_agent_start

  // session start (first run / after compaction) + the gate; → the text for the model
  const judge = async (ctx: ExtensionContext, prompt: string): Promise<string[]> => {
    promptSeq += 1
    const parts: string[] = []
    const sid = sessionId(ctx)
    if (startedFor !== sid || compacted) {
      const start = run(ctx, "session_start", { source: compacted ? "compact" : "startup" })
      if (start.context) parts.push(start.context)
      startedFor = sid
      compacted = false
    }
    const p = run(ctx, "prompt", { prompt, context: lastAssistantText(ctx), has_ui: Boolean(ctx.hasUI) })
    if (p.context) parts.push(p.context)
    if (p.ask && ctx.hasUI) {
      const res = run(ctx, "ask_answer", { choice: await select(ctx, p.ask, p.options) })
      if (res.context) parts.push(res.context)
    }
    return parts
  }
  const select = async (ctx: ExtensionContext, title: string, options?: string[]): Promise<string> => {
    try {
      return (await ctx.ui.select(title, options ?? ["Continue without ISA", "Enable ISA"])) ?? "Continue without ISA"
    } catch (e) {
      warn(ctx, `ISA: could not ask (${(e as Error).message}) — continuing without an ISA`)
      return "Continue without ISA"
    }
  }

  pi.on("input", async (event, ctx) => {
    // a message typed while the agent runs belongs to the current run: no judge, no question
    if (event.streamingBehavior) return { action: "continue" as const }
    pending = await judge(ctx, event.text)
    return { action: "continue" as const }
  })

  pi.on("before_agent_start", async (event, ctx) => {
    const parts = pending ?? (await judge(ctx, event.prompt)) // no `input` before this run: judge here
    pending = null
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
      // what the tool printed: `isa new` prints the ISA path the session is then bound to
      tool_output: (event.content ?? []).filter((c: any) => c?.type === "text").map((c: any) => c.text).join("\n"),
    })
    if (!res.context) return
    return { content: [...event.content, { type: "text" as const, text: `\n[ISA] ${res.context}` }] }
  })

  pi.on("agent_before_settle", async (event, ctx) => {
    // only a run that finished normally is checked: never restart one the user aborted or that errored
    if (event.outcome !== "completed" || event.context?.canContinue === false) return
    let res = run(ctx, "stop", { context: lastAssistantText(ctx), has_ui: Boolean(ctx.hasUI) })
    if (res.ask && ctx.hasUI) res = run(ctx, "ask_answer", { choice: await select(ctx, res.ask, res.options) })
    if (!res.block) return
    return {
      continue: true,
      entries: [{ type: "custom_message" as const, customType: "isa-stop", content: res.block, display: true }],
    }
  })
}
