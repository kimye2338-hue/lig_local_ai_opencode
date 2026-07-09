// Hamster status bridge — reflects OpenCode chat/tool activity in the desktop pet.
// The hamster overlay reads %LIG_STATE_DIR%\current_status.json (status/message).
// agent_ops runtime writes it during work/agent/tool runs, but plain OpenCode chat
// does not — so the pet used to stay "대기 중" while the model was answering.
// This plugin writes that file on chat/tool events so the pet shows "작업 중"
// during generation and "대기 중" when the session goes idle.
// No external imports (offline / 망분리 safe). Best-effort: never throws.

import { appendFileSync, renameSync, writeFileSync, mkdirSync, statSync, truncateSync } from "fs"
import { join } from "path"

const ENABLE_EVENT_LOG = process.env.LIG_DIAG_EVENTS === "1"
const EVENT_LOG_MAX_BYTES = 1024 * 1024
const seenEventTypes = new Set<string>()

function stateDir(): string {
  const explicit = process.env.LIG_STATE_DIR
  if (explicit && explicit.trim()) return explicit
  const home = process.env.USERPROFILE || process.env.HOME || "."
  return join(home, "OpenCodeLIG_USERDATA", "state")
}

let lastWrite = 0
let lastStatus = ""

function writeAtomic(path: string, body: string): void {
  const tmp = `${path}.${process.pid}.${Date.now()}.tmp`
  writeFileSync(tmp, body, "utf-8")
  renameSync(tmp, path)
}

function write(status: string, message: string, force = false): void {
  try {
    // 스트리밍 이벤트가 초당 수십 번 올 수 있으므로 같은 상태는 800ms로 스로틀.
    const now = new Date().getTime()
    if (!force && status === lastStatus && now - lastWrite < 800) return
    lastWrite = now
    lastStatus = status
    const dir = stateDir()
    mkdirSync(dir, { recursive: true })
    writeAtomic(join(dir, "current_status.json"), JSON.stringify({
      status,
      message,
      task: "chat",
      source: "opencode-chat",
      updated_at: new Date().toISOString(),
    }))
  } catch {
    // 상태 표시는 부가 기능 — 실패해도 채팅에 영향 주지 않는다.
  }
}

function eventLogPath(): string {
  const home = process.env.USERPROFILE || process.env.HOME || "."
  const diag = process.env.LIG_DIAG_DIR || join(home, "OpenCodeLIG_USERDATA", "diagnostics")
  return join(diag, "opencode-event-types.log")
}

function logEventType(type: string, marker = ""): void {
  if (!ENABLE_EVENT_LOG) return
  try {
    const home = process.env.USERPROFILE || process.env.HOME || "."
    const diag = process.env.LIG_DIAG_DIR || join(home, "OpenCodeLIG_USERDATA", "diagnostics")
    const path = eventLogPath()
    const key = `${type} ${marker}`.trim()
    if (seenEventTypes.has(key)) return
    seenEventTypes.add(key)
    mkdirSync(diag, { recursive: true })
    try {
      if (statSync(path).size > EVENT_LOG_MAX_BYTES) truncateSync(path, 0)
    } catch {
      // first write
    }
    appendFileSync(path, `${new Date().toISOString()} ${type}${marker ? " " + marker : ""}\n`, "utf-8")
  } catch {
    // 진단 로그는 부가 기능이다.
  }
}

function statusFromSessionStatus(event: any): string {
  return String(event?.properties?.status?.type || event?.status?.type || "")
}

function taskToolName(event: any): string {
  return String(
    event?.properties?.taskName ||
    event?.properties?.task?.name ||
    event?.properties?.name ||
    event?.properties?.tool ||
    "task"
  )
}

function isTaskToolCall(type: string, event: any): boolean {
  return type === "session.next.tool.called" && event?.properties?.tool === "task"
}

function isTaskToolSuccess(type: string, event: any): boolean {
  return type === "session.next.tool.success" && event?.properties?.tool === "task"
}

function isTaskToolFailure(type: string, event: any): boolean {
  return type === "session.next.tool.failed" && event?.properties?.tool === "task"
}

export const HamsterStatus = async (_ctx: any) => {
  // Binary grep on the patched opencode.exe showed these session events exist:
  // session.next.*, session.status, session.idle, experimental.session.compacting.
  // Older guessed task/subagent event families were not present, so this bridge
  // only trusts structured tool/status fields that are actually emitted.
  // OpenCode 시작 시 지난 세션의 완료/작업 상태가 남아 "완료"로 뜨지 않도록 대기중으로 초기화.
  // (햄스터는 상태 파일 중 가장 최근 것을 표시하므로, 시작 시 최신 idle 을 써서 이전 상태를 덮는다.)
  write("idle", "대기 중입니다. 작업이 시작되면 알려드릴게요.", true)
  return {
    "tool.execute.before": async () => {
      write("working", "도구 실행 중...")
    },
    "tool.execute.after": async () => {
      write("working", "작업 중...", true)
    },
    event: async ({ event }: any) => {
      const t: string = (event && event.type) || ""
      if (t) logEventType(t, isTaskToolCall(t, event) ? "task_tool_called" : "")
      const status = statusFromSessionStatus(event)
      if (isTaskToolCall(t, event)) {
        write("working", `멀티에이전트 ${taskToolName(event)} 작업 중...`, true)
      } else if (isTaskToolSuccess(t, event)) {
        write("done", `멀티에이전트 ${taskToolName(event)} 작업 완료`, true)
      } else if (isTaskToolFailure(t, event)) {
        write("error", `멀티에이전트 ${taskToolName(event)} 작업 중 오류가 발생했습니다.`, true)
      } else if (t === "session.status" && status === "idle") {
        write("idle", "대기 중입니다. 작업이 시작되면 알려드릴게요.", true)
      } else if (t === "session.status" && status === "busy") {
        write("working", "OpenCode가 작업 중입니다.")
      } else if (t === "session.status" && status === "retry") {
        write("working", "모델 응답을 재시도 중입니다.", true)
      } else if (t === "experimental.session.compacting") {
        write("working", "세션 정리 중...", true)
      } else if (t === "session.idle") {
        write("idle", "대기 중입니다. 작업이 시작되면 알려드릴게요.", true)
      } else if (t === "session.error" || t === "session.next.step.failed" || t === "session.next.tool.failed") {
        write("error", "작업 중 오류가 발생했습니다.", true)
      } else if (t === "session.next.step.ended") {
        write("done", "작업이 끝났습니다.", true)
      } else if (
        t === "session.next.prompted" ||
        t === "session.next.prompt.admitted" ||
        t === "session.next.step.started" ||
        t === "session.next.text.started" ||
        t === "session.next.text.delta" ||
        t === "session.next.text.ended" ||
        t === "session.next.reasoning.started" ||
        t === "session.next.reasoning.delta" ||
        t === "session.next.reasoning.ended"
      ) {
        write("working", "모델이 응답 중...")
      } else if (
        t === "session.next.tool.input.started" ||
        t === "session.next.tool.input.delta" ||
        t === "session.next.tool.input.ended" ||
        t === "session.next.tool.called" ||
        t === "session.next.tool.progress" ||
        t === "session.next.tool.success" ||
        t === "session.next.shell.started" ||
        t === "session.next.shell.ended"
      ) {
        write("working", "도구 실행 중...")
      }
    },
  }
}
