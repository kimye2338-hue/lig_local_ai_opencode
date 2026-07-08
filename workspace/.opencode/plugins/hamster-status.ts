// Hamster status bridge — reflects OpenCode chat/tool activity in the desktop pet.
// The hamster overlay reads %LIG_STATE_DIR%\current_status.json (status/message).
// agent_ops runtime writes it during work/agent/tool runs, but plain OpenCode chat
// does not — so the pet used to stay "대기 중" while the model was answering.
// This plugin writes that file on chat/tool events so the pet shows "작업 중"
// during generation and "대기 중" when the session goes idle.
// No external imports (offline / 망분리 safe). Best-effort: never throws.

import { writeFileSync, mkdirSync } from "fs"
import { join } from "path"

function stateDir(): string {
  const explicit = process.env.LIG_STATE_DIR
  if (explicit && explicit.trim()) return explicit
  const home = process.env.USERPROFILE || process.env.HOME || "."
  return join(home, "OpenCodeLIG_USERDATA", "state")
}

let lastWrite = 0
let lastStatus = ""

function write(status: string, message: string, force = false): void {
  try {
    // 스트리밍 이벤트가 초당 수십 번 올 수 있으므로 같은 상태는 800ms로 스로틀.
    const now = new Date().getTime()
    if (!force && status === lastStatus && now - lastWrite < 800) return
    lastWrite = now
    lastStatus = status
    const dir = stateDir()
    mkdirSync(dir, { recursive: true })
    writeFileSync(
      join(dir, "current_status.json"),
      JSON.stringify({ status, message, task: "chat", source: "opencode-chat" }),
      "utf-8",
    )
  } catch {
    // 상태 표시는 부가 기능 — 실패해도 채팅에 영향 주지 않는다.
  }
}

export const HamsterStatus = async (_ctx: any) => ({
  "tool.execute.before": async () => {
    write("working", "도구 실행 중...")
  },
  "tool.execute.after": async () => {
    write("working", "작업 중...", true)
  },
  event: async ({ event }: any) => {
    const t: string = (event && event.type) || ""
    if (t === "session.idle" || t === "session.error") {
      write("idle", "대기 중입니다. 작업이 시작되면 알려드릴게요.", true)
    } else if (t.indexOf("message") >= 0 || t.indexOf("part") >= 0) {
      write("working", "모델이 응답 중...")
    }
  },
})
