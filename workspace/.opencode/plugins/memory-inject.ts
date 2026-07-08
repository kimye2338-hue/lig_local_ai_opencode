// OpenCodeLIG memory bridge.
// Best-effort, offline-safe plugin: injects pinned AgentOps memory during
// compaction, and leaves a local session recall file at startup for fallback
// commands/agent instructions. Never throws into the chat path.

import { execFileSync } from "child_process"
import { existsSync, mkdirSync, writeFileSync } from "fs"
import { join } from "path"

const MAX_RECALL_CHARS = 6000
const MAX_SUMMARY_CHARS = 1200

function baseDir(ctx) {
  const explicit = process.env.AGENTOPS_HOME
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

function runAgentOps(base, args) {
  const script = agentopsPath(base)
  if (!existsSync(script)) return ""
  const env = {
    ...process.env,
    PYTHONUTF8: process.env.PYTHONUTF8 || "1",
    PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
  }
  const runners = [
    ["python", [script, ...args]],
    ["py", ["-3.11", script, ...args]],
  ]
  for (const [exe, exeArgs] of runners) {
    try {
      return String(execFileSync(exe, exeArgs, {
        cwd: base,
        env,
        encoding: "utf-8",
        stdio: ["ignore", "pipe", "ignore"],
        timeout: 10000,
      }) || "").trim()
    } catch {
      // Try the next runner. Memory is helpful context, not a hard dependency.
    }
  }
  return ""
}

function pinnedRecallBlock(base) {
  const recalled = runAgentOps(base, ["recall", "--pinned"])
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
  runAgentOps(base, ["log-activity", summary, "--title", "OpenCode TUI 세션 요약"])
}

export const MemoryInject = async (ctx) => {
  const base = baseDir(ctx)
  const startupBlock = pinnedRecallBlock(base)
  writeStartupRecall(base, startupBlock)

  return {
    "experimental.session.compacting": async (input, output) => {
      const freshBlock = pinnedRecallBlock(base)
      pushContext(output, freshBlock)
      logCompactionActivity(base, input, output)
    },
    event: async ({ event }) => {
      const t = String((event && event.type) || "")
      if (t === "session.idle" || t === "session.error") {
        writeStartupRecall(base, pinnedRecallBlock(base))
      }
    },
  }
}
