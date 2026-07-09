// OpenCodeLIG session autosave.
// Writes useful chat/session snippets directly into the Obsidian vault on each
// event, so closing the terminal window does not lose the visible session trail.
// Best-effort and offline-safe: failure must never affect the chat path.

import { appendFileSync, existsSync, mkdirSync, writeFileSync } from "fs"
import { execFileSync } from "child_process"
import { join } from "path"

const MAX_TEXT_CHARS = 1600
const MAX_EVENT_CHARS = 2400
const MIN_USEFUL_CHARS = 8
const FLUSH_INTERVAL_MS = 60000
const FLUSH_MIN_CHARS = 80

let lastSignature = ""
let lastWriteMs = 0
let lastFlushMs = 0
let sessionBuffer: string[] = []

function userdataDir(): string {
  const explicit = process.env.OPENCODE_USERDATA
  if (explicit && explicit.trim()) return explicit
  const home = process.env.USERPROFILE || process.env.HOME || "."
  return join(home, "OpenCodeLIG_USERDATA")
}

function wikiSessionsDir(): string {
  return join(userdataDir(), "memory", "wiki", "sessions")
}

function dayStamp(date = new Date()): string {
  return date.toISOString().slice(0, 10)
}

function timeStamp(date = new Date()): string {
  return date.toTimeString().slice(0, 8)
}

function sessionFile(): string {
  return join(wikiSessionsDir(), `${dayStamp()}-opencode-session.md`)
}

function ensureSessionFile(): void {
  const dir = wikiSessionsDir()
  mkdirSync(dir, { recursive: true })
  const path = sessionFile()
  if (!existsSync(path)) {
    writeFileSync(path, [
      "# OpenCode session autosave",
      "",
      "이 파일은 OpenCodeLIG가 대화/작업 이벤트를 자동 저장한 기록입니다.",
      "터미널 창을 닫아도 이미 기록된 내용은 이 Obsidian vault 노트에 남습니다.",
      "",
    ].join("\n"), "utf-8")
  }
}

function compact(value: string): string {
  return value.replace(/\s+/g, " ").trim()
}

function redact(value: string): string {
  return value
    .replace(/Bearer\s+[A-Za-z0-9._\-+/=]+/g, "Bearer <hidden>")
    .replace(/(api[_-]?key\s*[=:]\s*)[^\s,;]+/gi, "$1<hidden>")
    .replace(/(password\s*[=:]\s*)[^\s,;]+/gi, "$1<hidden>")
}

function collectText(value: any, out: string[], depth = 0): void {
  if (out.length >= 12 || depth > 5 || value == null) return
  if (typeof value === "string") {
    const text = compact(value)
    if (text.length >= MIN_USEFUL_CHARS) out.push(text.slice(0, MAX_TEXT_CHARS))
    return
  }
  if (Array.isArray(value)) {
    for (const item of value) collectText(item, out, depth + 1)
    return
  }
  if (typeof value === "object") {
    const priority = [
      "properties",
      "role",
      "text",
      "delta",
      "content",
      "message",
      "summary",
      "prompt",
      "title",
      "input",
      "output",
      "command",
      "tool",
      "error",
      "result",
    ]
    for (const key of priority) {
      if (key in value) collectText(value[key], out, depth + 1)
    }
    for (const [key, child] of Object.entries(value)) {
      if (!priority.includes(key)) collectText(child, out, depth + 1)
    }
  }
}

function usefulText(event: any): string {
  const parts: string[] = []
  collectText(event, parts)
  const unique: string[] = []
  for (const p of parts) {
    if (!unique.includes(p)) unique.push(p)
  }
  return redact(unique.join("\n\n")).slice(0, MAX_EVENT_CHARS)
}

function baseDir(ctx?: any): string {
  const explicit = process.env.LIG_AGENTOPS_HOME || process.env.AGENTOPS_HOME
  if (explicit && explicit.trim()) return explicit
  return ctx?.directory || ctx?.worktree?.path || process.cwd()
}

function agentopsPath(base: string): string {
  return join(base, "agent_ops", "agentops.py")
}

function activityTitle(date = new Date()): string {
  const bucket = Math.floor(date.getMinutes() / 10) * 10
  return `OpenCode session autosave ${dayStamp(date)} ${String(date.getHours()).padStart(2, "0")}:${String(bucket).padStart(2, "0")}`
}

function runAgentOps(base: string, args: string[]): void {
  const script = agentopsPath(base)
  if (!existsSync(script)) return
  const env = {
    ...process.env,
    PYTHONUTF8: process.env.PYTHONUTF8 || "1",
    PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
  }
  const runners: Array<[string, string[]]> = [
    ["py", ["-3.11", script, ...args]],
    ["python", [script, ...args]],
  ]
  for (const [exe, exeArgs] of runners) {
    try {
      execFileSync(exe, exeArgs, {
        cwd: base,
        env,
        encoding: "utf-8",
        stdio: ["ignore", "ignore", "ignore"],
        timeout: 8000,
      })
      return
    } catch {
      // try next runner
    }
  }
}

function rememberSessionActivity(base: string, force = false): void {
  try {
    const now = Date.now()
    const body = compact(sessionBuffer.join("\n"))
    if (body.length < FLUSH_MIN_CHARS && !force) return
    if (!force && now - lastFlushMs < FLUSH_INTERVAL_MS) return
    lastFlushMs = now
    sessionBuffer = []
    if (!body) return
    runAgentOps(base, ["log-activity", body.slice(0, MAX_EVENT_CHARS), "--title", activityTitle()])
  } catch {
    // Memory promotion is best-effort; raw Obsidian autosave is already written.
  }
}

function writeEvent(event: any, base: string): void {
  try {
    ensureSessionFile()
    const type = String(event?.type || "event")
    const text = usefulText(event)
    const statusType = String(event?.properties?.status?.type || event?.status?.type || "")
    const shouldFlush = (
      type === "session.idle" ||
      type === "session.error" ||
      type === "session.status" && statusType === "idle" ||
      type === "session.next.step.ended" ||
      type === "session.next.step.failed" ||
      type === "session.compacting"
    )
    if (!text && !shouldFlush) return

    const now = Date.now()
    const signature = `${type}:${text.slice(0, 400)}`
    if (signature === lastSignature && now - lastWriteMs < 3000) return
    lastSignature = signature
    lastWriteMs = now

    const heading = `\n## ${timeStamp()} ${type}\n`
    const body = text ? `${text}\n` : "(상태 이벤트)\n"
    appendFileSync(sessionFile(), heading + body, "utf-8")
    if (text) sessionBuffer.push(`[${type}] ${text}`)
    rememberSessionActivity(base, shouldFlush)
  } catch {
    // Autosave must never interrupt the user's session.
  }
}

export const SessionAutosave = async (ctx: any) => {
  const base = baseDir(ctx)
  try {
    ensureSessionFile()
    appendFileSync(sessionFile(), `\n## ${timeStamp()} session.start\nOpenCode 세션 시작\n`, "utf-8")
  } catch {
    // optional
  }
  return {
    event: async ({ event }: any) => {
      writeEvent(event, base)
    },
    "experimental.session.compacting": async (input: any, output: any) => {
      writeEvent({ type: "session.compacting", input, output }, base)
    },
  }
}
