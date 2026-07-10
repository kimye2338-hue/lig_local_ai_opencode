// OpenCodeLIG memory bridge.
// Best-effort, offline-safe plugin: injects cached AgentOps memory during
// compaction, and refreshes the durable recall file in the background.
// Never throws into the chat path and never blocks TUI startup on a sync child.

import { execFile } from "child_process"
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs"
import { join } from "path"

const MAX_RECALL_CHARS = 6000
const MAX_SUMMARY_CHARS = 1200
const STARTUP_REFRESH_COOLDOWN_MS = 60_000
const COMPACTION_REFRESH_COOLDOWN_MS = 60_000
const IDLE_REFRESH_COOLDOWN_MS = 60_000

let lastRefreshAt = 0

function baseDir(ctx) {
  const explicit = process.env.LIG_AGENTOPS_HOME || process.env.AGENTOPS_HOME
  if (explicit && explicit.trim()) return explicit
  return ctx?.directory || ctx?.worktree?.path || process.cwd()
}

function agentopsPath(base) {
  return join(base, "agent_ops", "agentops.py")
}

function stateDir(base) {
  const explicit = process.env.AGENTOPS_STATE_DIR
  if (explicit && explicit.trim()) return explicit
  return join(base, "agent_ops", "state")
}

function runAgentOpsAsync(base, args, onDone) {
  const script = agentopsPath(base)
  if (!existsSync(script)) {
    if (onDone) onDone("")
    return
  }
  const env = {
    ...process.env,
    PYTHONUTF8: process.env.PYTHONUTF8 || "1",
    PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
  }
  const runners = [
    ["python", [script, ...args]],
    ["py", ["-3.11", script, ...args]],
  ]
  const attempt = (index) => {
    if (index >= runners.length) {
      if (onDone) onDone("")
      return
    }
    const [exe, exeArgs] = runners[index]
    try {
      execFile(exe, exeArgs, {
        cwd: base,
        env,
        encoding: "utf-8",
        timeout: 10000,
        windowsHide: true,
      }, (error, stdout) => {
        if (error) {
          attempt(index + 1)
          return
        }
        if (onDone) onDone(String(stdout || "").trim())
      })
    } catch {
      attempt(index + 1)
    }
  }
  attempt(0)
}

function pinnedRecallBlockFromText(recalled) {
  if (!recalled) {
    return [
      "## OpenCodeLIG memory",
      "Pinned memory was unavailable. If this is a new session, run:",
      "`python agent_ops/agentops.py recall --pinned`",
    ].join("\n")
  }
  const body = recalled.length > MAX_RECALL_CHARS
    ? recalled.slice(0, MAX_RECALL_CHARS) + "\n...(memory truncated)"
    : recalled
  return [
    "## OpenCodeLIG pinned memory",
    "Use these durable user rules, project facts, recent lessons, and activity hints before answering.",
    body,
  ].join("\n")
}

function cachedRecallBlock(base) {
  try {
    // SESSION_RECALL.md is a plugin-owned durable cache. Agent instructions
    // rely on injected "pinned memory" text, not on this path directly.
    const cached = readFileSync(join(stateDir(base), "SESSION_RECALL.md"), "utf-8").trim()
    if (cached) return cached
  } catch {
    // fallback below
  }
  return fallbackStartupBlock()
}

function pushContext(output, block) {
  if (Array.isArray(output?.context)) {
    output.context.push(block)
  } else if (output) {
    output.prompt = (output.prompt ? output.prompt + "\n\n" : "") + block
  }
}

function writeStartupRecall(base, block) {
  try {
    const dir = stateDir(base)
    mkdirSync(dir, { recursive: true })
    writeFileSync(join(dir, "SESSION_RECALL.md"), block + "\n", "utf-8")
  } catch {
    // Fallback file is optional.
  }
}

function fallbackStartupBlock() {
  return [
    "## OpenCodeLIG memory",
    "Pinned memory refresh is running in the background.",
    "If immediate recall is needed, run: `python agent_ops/agentops.py recall --pinned`",
  ].join("\n")
}

function refreshStartupRecallAsync(base, cooldownMs = STARTUP_REFRESH_COOLDOWN_MS) {
  const now = Date.now()
  if (now - lastRefreshAt < cooldownMs) return
  lastRefreshAt = now
  setTimeout(() => {
    runAgentOpsAsync(base, ["recall", "--pinned"], (recalled) => {
      try {
        writeStartupRecall(base, pinnedRecallBlockFromText(recalled))
      } catch {
        // Background recall must never delay or break TUI startup.
      }
    })
  }, 1)
}

function compactSummary(input, output) {
  const candidates = [
    input?.summary,
    input?.message,
    input?.prompt,
    output?.summary,
    output?.prompt,
  ]
  for (const value of candidates) {
    if (typeof value === "string" && value.trim().length >= 30) {
      const oneLine = value.replace(/\s+/g, " ").trim()
      return oneLine.slice(0, MAX_SUMMARY_CHARS)
    }
  }
  return ""
}

function logCompactionActivity(base, input, output) {
  // Compaction summaries are session logs, not user rules: store them as a
  // low-priority activity (never `remember`, which is preference/high/user).
  // The fixed title lets add_activity's same-day/same-title cap dedupe to at
  // most one entry per day.
  const summary = compactSummary(input, output)
  if (!summary) return
  runAgentOpsAsync(base, ["log-activity", summary, "--title", "OpenCode TUI 세션 요약"])
}

export const MemoryInject = async (ctx) => {
  try {
    const base = baseDir(ctx)
    writeStartupRecall(base, fallbackStartupBlock())
    refreshStartupRecallAsync(base, STARTUP_REFRESH_COOLDOWN_MS)

    return {
      "experimental.session.compacting": async (input, output) => {
        try {
          pushContext(output, cachedRecallBlock(base))
          refreshStartupRecallAsync(base, COMPACTION_REFRESH_COOLDOWN_MS)
          logCompactionActivity(base, input, output)
        } catch {
          // Compaction hook is additive only.
        }
      },
      event: async ({ event }) => {
        const t = String((event && event.type) || "")
        const status = String(event?.properties?.status?.type || event?.status?.type || "")
        if (t === "session.idle" || t === "session.error" || (t === "session.status" && status === "idle")) {
          refreshStartupRecallAsync(base, IDLE_REFRESH_COOLDOWN_MS)
        }
      },
    }
  } catch {
    return {}
  }
}
