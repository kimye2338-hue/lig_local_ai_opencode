// OpenCodeLIG session autosave.
// Writes useful chat/session snippets directly into the Obsidian vault on each
// event, so closing the terminal window does not lose the visible session trail.
// Best-effort and offline-safe: failure must never affect the chat path.

import { appendFileSync, existsSync, mkdirSync, writeFileSync } from "fs"
import { join } from "path"

const MAX_TEXT_CHARS = 1600
const MAX_EVENT_CHARS = 2400
const MIN_USEFUL_CHARS = 8

let lastSignature = ""
let lastWriteMs = 0

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
    .replace(/(?i:api[_-]?key\s*[=:]\s*)[^\s,;]+/g, "$1<hidden>")
    .replace(/(?i:password\s*[=:]\s*)[^\s,;]+/g, "$1<hidden>")
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
    const priority = ["role", "text", "content", "message", "summary", "prompt", "title"]
    for (const key of priority) {
      if (key in value) collectText(value[key], out, depth + 1)
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

function writeEvent(event: any): void {
  try {
    ensureSessionFile()
    const type = String(event?.type || "event")
    const text = usefulText(event)
    if (!text && type !== "session.idle" && type !== "session.error") return

    const now = Date.now()
    const signature = `${type}:${text.slice(0, 400)}`
    if (signature === lastSignature && now - lastWriteMs < 3000) return
    lastSignature = signature
    lastWriteMs = now

    const heading = `\n## ${timeStamp()} ${type}\n`
    const body = text ? `${text}\n` : "(상태 이벤트)\n"
    appendFileSync(sessionFile(), heading + body, "utf-8")
  } catch {
    // Autosave must never interrupt the user's session.
  }
}

export const SessionAutosave = async (_ctx: any) => {
  try {
    ensureSessionFile()
    appendFileSync(sessionFile(), `\n## ${timeStamp()} session.start\nOpenCode 세션 시작\n`, "utf-8")
  } catch {
    // optional
  }
  return {
    event: async ({ event }: any) => {
      writeEvent(event)
    },
    "experimental.session.compacting": async (input: any, output: any) => {
      writeEvent({ type: "session.compacting", input, output })
    },
  }
}
