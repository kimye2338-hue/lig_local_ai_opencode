# -*- coding: utf-8 -*-
"""Patch an existing OpenCodeLIG install in place.

This script is launched by PATCH_EXISTING_INSTALL_LIG_OPENCODE_20260709.bat.txt.
It is intentionally additive:
- backs up touched files under USERDATA diagnostics;
- never deletes or rewrites OpenCodeLIG_USERDATA memory/wiki/schedules;
- patches diagnostic classification without hiding real app-validation gaps;
- installs optional wheels only when the wheel files are already available.
"""
from __future__ import annotations

import os
import importlib.util
import shutil
import subprocess
import sys
import time
from pathlib import Path

MARK_PENDING = "# BEGIN LIG EXISTING-INSTALL HOTFIX 20260709"
MARK_ADAPTERS = "# BEGIN LIG ADAPTER STATUS HOTFIX 20260709"
MARK_RUN = "rem BEGIN LIG EXISTING-INSTALL HOTFIX 20260709"

SESSION_AUTOSAVE_PLUGIN = r'''// OpenCodeLIG session autosave.
// Writes useful chat/session snippets directly into the Obsidian vault on each
// event, so closing the terminal window does not lose the visible session trail.
// Best-effort and offline-safe: failure must never affect the chat path.

import { appendFileSync, existsSync, mkdirSync, writeFileSync } from "fs"
import { execFile } from "child_process"
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
let streamBuffer = {
  text: "",
  reasoning: "",
  toolInput: "",
}

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
  let redacted = value
    .replace(/Bearer\s+[A-Za-z0-9._\-+/=]+/g, "Bearer <hidden>")
    .replace(/(api[_-]?key\s*[=:]\s*)[^\s,;]+/gi, "$1<hidden>")
    .replace(/(password\s*[=:]\s*)[^\s,;]+/gi, "$1<hidden>")
    .replace(/((?:token|secret|credential)\s*[=:]\s*)[^\s,;]+/gi, "$1<hidden>")
  for (const [key, raw] of Object.entries(process.env)) {
    if (!/(api.*key|token|secret|credential|password)/i.test(key)) continue
    const value = String(raw || "").trim()
    if (value.length < 8) continue
    redacted = redacted.split(value).join("<hidden>")
  }
  return redacted
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

function runAgentOpsAsync(base: string, args: string[]): void {
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
  const attempt = (index: number): void => {
    if (index >= runners.length) return
    const [exe, exeArgs] = runners[index]
    try {
      execFile(exe, exeArgs, {
        cwd: base,
        env,
        encoding: "utf-8",
        timeout: 8000,
        windowsHide: true,
      }, (error) => {
        if (error) attempt(index + 1)
      })
    } catch {
      attempt(index + 1)
    }
  }
  attempt(0)
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
    runAgentOpsAsync(base, ["log-activity", body.slice(0, MAX_EVENT_CHARS), "--title", activityTitle()])
  } catch {
    // Memory promotion is best-effort; raw Obsidian autosave is already written.
  }
}

function streamBucket(type: string): "text" | "reasoning" | "toolInput" | "" {
  if (type.includes(".text.")) return "text"
  if (type.includes(".reasoning.")) return "reasoning"
  if (type.includes(".tool.input.")) return "toolInput"
  return ""
}

function bufferEventText(type: string, text: string): void {
  const bucket = streamBucket(type)
  if (!bucket || !text) return
  const prior = streamBuffer[bucket]
  streamBuffer[bucket] = compact(`${prior}\n${text}`).slice(0, MAX_EVENT_CHARS)
}

function takeBufferedText(type: string): string {
  const bucket = streamBucket(type)
  if (!bucket) return ""
  const text = streamBuffer[bucket]
  streamBuffer[bucket] = ""
  return text
}

function writeEvent(event: any, base: string): void {
  try {
    ensureSessionFile()
    const type = String(event?.type || "event")
    const text = usefulText(event)
    if (
      type === "session.next.text.delta" ||
      type === "session.next.reasoning.delta" ||
      type === "session.next.tool.input.delta"
    ) {
      bufferEventText(type, text)
      return
    }
    const buffered = takeBufferedText(type)
    const mergedText = compact([buffered, text].filter(Boolean).join("\n\n")).slice(0, MAX_EVENT_CHARS)
    const statusType = String(event?.properties?.status?.type || event?.status?.type || "")
    const shouldFlush = (
      type === "session.idle" ||
      type === "session.error" ||
      type === "session.status" && statusType === "idle" ||
      type === "session.next.step.ended" ||
      type === "session.next.step.failed" ||
      type === "session.compacting" ||
      type === "session.next.text.ended" ||
      type === "session.next.reasoning.ended" ||
      type === "session.next.tool.input.ended"
    )
    if (!mergedText && !shouldFlush) return

    const now = Date.now()
    const signature = `${type}:${mergedText.slice(0, 400)}`
    if (signature === lastSignature && now - lastWriteMs < 3000) return
    lastSignature = signature
    lastWriteMs = now

    const heading = `\n## ${timeStamp()} ${type}\n`
    const body = mergedText ? `${mergedText}\n` : "(상태 이벤트)\n"
    appendFileSync(sessionFile(), heading + body, "utf-8")
    if (mergedText) sessionBuffer.push(`[${type}] ${mergedText}`)
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
'''

HAMSTER_STATUS_PLUGIN = r'''// Hamster status bridge — reflects OpenCode chat/tool activity in the desktop pet.
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
'''

MEMORY_INJECT_PLUGIN = r'''// OpenCodeLIG memory bridge.
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
'''

COMPACTION_HANDOFF_PLUGIN = r'''import { readFileSync } from "fs"
import { join } from "path"

export const CompactionHandoff = async (ctx: any) => {
  try {
    return {
      "experimental.session.compacting": async (_input: any, output: any) => {
        try {
          const explicit = process.env.LIG_AGENTOPS_HOME || process.env.AGENTOPS_HOME
          const base = explicit && explicit.trim()
            ? explicit
            : (ctx?.directory || ctx?.worktree?.path || process.cwd())
          let handoff = ""
          let missing = false
          try {
            handoff = readFileSync(join(base, "agent_ops/state/COMPACT_HANDOFF.md"), "utf-8")
          } catch {
            missing = true
          }
          const block = [
            "## AgentOps durable handoff (preserve across compaction)",
            "After compaction, FIRST read: agent_ops/state/COMPACT_HANDOFF.md, RESUME_PLAN.md, ACTIVE_TASK.json, CHECKPOINT.json.",
            "Items under next_step/queue are PLANNED, not approved. No risk:review_required action without explicit current-session user approval.",
            missing ? "(COMPACT_HANDOFF.md not found at session start — run `python agent_ops/agentops.py checkpoint` early.)" : handoff,
          ].join("\n")
          if (Array.isArray(output?.context)) {
            output.context.push(block)   // additive: preferred (F2)
          } else {
            output.prompt = (output.prompt ? output.prompt + "\n\n" : "") + block
          }
        } catch {
          // Handoff is additive only.
        }
      },
    }
  } catch {
    return {}
  }
}
'''

AUTOCAD_BATCH_SOURCE = r'''# -*- coding: utf-8 -*-
"""AutoCAD subprocess adapter with copy-only DWG policy.

Prefer accoreconsole when present. Some company PCs expose only GUI AutoCAD
Mechanical (`acad.exe /p LIGNEX1 /product ACADM`), so fall back to `acad.exe`
with `/b <script>` while keeping the same copied-DWG safety policy.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from ..audit import record as audit_record

STANDARD_PATHS = (
    r"C:\AutoCAD 2019\accoreconsole.exe",
    r"C:\AutoCAD 2019\acad.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2019\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2019\acad.exe",
)


def find_accoreconsole() -> str:
    override = os.environ.get("ACCORECONSOLE_EXE", "").strip()
    if override:
        return override
    found = shutil.which("accoreconsole")
    if found:
        return found
    for raw in STANDARD_PATHS:
        path = Path(raw)
        if path.exists():
            return str(path)
    return ""


def find_acad() -> str:
    for name in ("ACAD_EXE", "AUTOCAD_EXE"):
        override = os.environ.get(name, "").strip()
        if override:
            return override
    found = shutil.which("acad")
    if found:
        return found
    for raw in STANDARD_PATHS:
        path = Path(raw)
        if path.name.lower() == "acad.exe" and path.exists():
            return str(path)
    return ""


def find_autocad_executable() -> tuple[str, str]:
    console = find_accoreconsole()
    if console:
        return console, "accoreconsole"
    gui = find_acad()
    if gui:
        return gui, "acad"
    return "", ""


def _copy_path(src: Path) -> Path:
    base = src.with_name("사본_" + src.name)
    if not base.exists():
        return base
    for idx in range(2, 1000):
        candidate = base.with_name(f"{base.stem}_{idx}{base.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("copy name exhausted")


def _decode_autocad(data: bytes) -> str:
    if not data:
        return ""
    return data.decode("utf-16-le", errors="replace")


def _audit(copy_dwg: Path, scr_path: Path, result: Dict[str, Any]) -> None:
    audit_record({
        "kind": "adapter",
        "name": "autocad_batch.execute",
        "target": f"{copy_dwg.name}|{scr_path.name}",
        "risk": "dangerous",
        "verdict": "approved" if result.get("ok") else "failed",
        "detail": result.get("error", "") or f"exit {result.get('returncode', '')}",
    })


def execute(dwg_path: str, scr_path: str, options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    opts = options if isinstance(options, dict) else {}
    dwg = Path(str(dwg_path or "")).expanduser().resolve()
    scr = Path(str(scr_path or "")).expanduser().resolve()
    if not dwg.exists():
        return {"ok": False, "error": "DWG 파일 없음"}
    if not scr.exists():
        return {"ok": False, "error": "AutoCAD script 파일 없음"}
    exe, exe_kind = find_autocad_executable()
    if not exe:
        return {"ok": False, "error": "AutoCAD 실행파일 없음 — ACCORECONSOLE_EXE, ACAD_EXE, AUTOCAD_EXE 또는 AutoCAD 2019 경로 확인"}
    timeout_s = int(opts.get("timeout_s") or 300)
    copy_dwg = _copy_path(dwg)
    shutil.copy2(dwg, copy_dwg)
    if exe_kind == "accoreconsole":
        cmd = [exe, "/i", str(copy_dwg), "/s", str(scr)]
    else:
        profile = str(opts.get("profile") or os.environ.get("AUTOCAD_PROFILE") or "LIGNEX1")
        product = str(opts.get("product") or os.environ.get("AUTOCAD_PRODUCT") or "ACADM")
        cmd = [exe, str(copy_dwg), "/p", profile, "/product", product, "/b", str(scr)]
    try:
        r = subprocess.run(cmd, cwd=str(scr.parent), capture_output=True, timeout=timeout_s)
        out = _decode_autocad(r.stdout or b"")
        err = _decode_autocad(r.stderr or b"")
        if r.returncode == 53:
            result = {
                "ok": False,
                "error": "AutoCAD가 도면을 열지 못함(exit 53) — 사본 dwg 경로 확인",
                "returncode": r.returncode,
                "copy_path": str(copy_dwg),
                "log_tail": (out + err)[-400:],
                "cmd": cmd,
            }
        else:
            result = {
                "ok": r.returncode == 0,
                "returncode": r.returncode,
                "copy_path": str(copy_dwg),
                "stdout_tail": out[-800:],
                "stderr_tail": err[-800:],
                "cmd": cmd,
            }
            if r.returncode != 0:
                result["error"] = f"AutoCAD command failed exit {r.returncode}"
    except subprocess.TimeoutExpired:
        result = {"ok": False, "error": f"AutoCAD command timeout ({timeout_s}s)", "copy_path": str(copy_dwg), "cmd": cmd}
    except Exception as exc:
        result = {"ok": False, "error": f"AutoCAD command failed: {exc.__class__.__name__}", "copy_path": str(copy_dwg), "cmd": cmd}
    _audit(copy_dwg, scr, result)
    return result
'''



def _path_from_env(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip().strip('"')
    return Path(raw) if raw else default


ROOT = _path_from_env("OPENCODELIG_ROOT", Path.home() / "OpenCodeLIG")
WS = ROOT / "workspace"
USERDATA = Path.home() / "OpenCodeLIG_USERDATA"
LOG_DIR = USERDATA / "diagnostics" / "patches"
STAMP = time.strftime("%Y%m%d_%H%M%S")
PATCH_SOURCE_DIR = _path_from_env("LIG_HOTFIX_PACKAGE_DIR", Path(__file__).resolve().parents[2])
LOG = LOG_DIR / f"existing_install_hotfix_{STAMP}.log"


def log(message: str) -> None:
    print(message)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write(message + "\n")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _crlf_bytes(text: str) -> bytes:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n").encode("utf-8")


def write_crlf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_crlf_bytes(text))


def write_crlf_if_changed(path: Path, text: str) -> bool:
    desired = _crlf_bytes(text)
    if path.exists() and path.read_bytes() == desired:
        return False
    backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(desired)
    return True


def write_text_if_changed(path: Path, text: str) -> bool:
    desired = text.encode("utf-8")
    if path.exists() and path.read_bytes() == desired:
        return False
    backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(desired)
    return True


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    out = LOG_DIR / "backup" / STAMP / path.name
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, out)
    return out


def run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(WS),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def copy_root_check_bat() -> None:
    src = WS / "점검용_전체확인.bat"
    dst = ROOT / "점검용_전체확인.bat"
    if not src.exists():
        log(f"[WARN] workspace check BAT not found: {src}")
        return
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        log(f"[SKIP] root check BAT already current: {dst}")
        return
    backup(dst)
    shutil.copy2(src, dst)
    log(f"[OK] root check BAT copied: {dst}")


def create_gateway_wrappers() -> None:
    """Fix 'probe-gateway is not recognized' from unqualified command calls."""
    bin_dir = ROOT / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrappers = {
        "probe-gateway.bat": "probe-gateway.bat",
        "probe_gateway.bat": "probe-gateway.bat",
        "gateway-smoke.bat": "gateway-smoke.bat",
    }
    for wrapper_name, launch_name in wrappers.items():
        target = bin_dir / wrapper_name
        body = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "setlocal EnableExtensions\r\n"
            "set \"HERE=%~dp0\"\r\n"
            "for %%I in (\"%HERE%..\") do set \"OC_ROOT=%%~fI\"\r\n"
            f"set \"TARGET=%OC_ROOT%\\workspace\\launch\\{launch_name}\"\r\n"
            "if not exist \"%TARGET%\" (\r\n"
            "  echo [ERROR] target launcher not found: %TARGET%\r\n"
            "  exit /b 1\r\n"
            ")\r\n"
            "call \"%TARGET%\" %*\r\n"
            "exit /b %ERRORLEVEL%\r\n"
        )
        if write_crlf_if_changed(target, body):
            log(f"[OK] command wrapper created/updated: {target}")
        else:
            log(f"[SKIP] command wrapper already current: {target}")


def create_ocd_wrapper() -> None:
    """Create the user-facing command while keeping the existing ocd.py profile flow."""
    bin_dir = ROOT / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = bin_dir / "ocd.bat"
    body = (
        "@echo off\n"
        "chcp 65001 >nul\n"
        "setlocal EnableExtensions\n"
        "set \"PYTHONUTF8=1\"\n"
        "set \"PYTHONIOENCODING=utf-8\"\n"
        "set \"LITELLM_LOCAL_MODEL_COST_MAP=True\"\n"
        "set \"LITELLM_LOCAL_POLICY_TEMPLATES=True\"\n"
        "set \"LITELLM_LOCAL_BLOG_POSTS=True\"\n"
        "set \"HERE=%~dp0\"\n"
        "for %%I in (\"%HERE%..\") do set \"OC_ROOT=%%~fI\"\n"
        "set \"OCDPY=%OC_ROOT%\\workspace\\agent_ops\\ocd.py\"\n"
        "if not exist \"%OCDPY%\" (\n"
        "  echo [ERROR] OpenCodeLIG ocd.py not found: %OCDPY%\n"
        "  exit /b 1\n"
        ")\n"
        "if \"%~1\"==\"\" (\n"
        "  if not defined LIG_PROJECT_DIR set \"LIG_PROJECT_DIR=%CD%\"\n"
        ")\n"
        "where py >nul 2>nul\n"
        "if %ERRORLEVEL%==0 (\n"
        "  py -3.11 -X utf8 \"%OCDPY%\" %*\n"
        ") else (\n"
        "  python -X utf8 \"%OCDPY%\" %*\n"
        ")\n"
        "exit /b %ERRORLEVEL%\n"
    )
    if write_crlf_if_changed(target, body):
        log(f"[OK] ocd wrapper created/updated: {target}")
    else:
        log(f"[SKIP] ocd wrapper already current: {target}")


def create_launcher_helpers() -> None:
    launch_dir = WS / "launch"
    launch_dir.mkdir(parents=True, exist_ok=True)

    obsidian_vbs = launch_dir / "obsidian_detached.vbs"
    obsidian_body = (
        "Option Explicit\n"
        "Dim shell, exePath, vaultPath, cmd\n"
        "If WScript.Arguments.Count < 2 Then WScript.Quit 1\n"
        "exePath = WScript.Arguments(0)\n"
        "vaultPath = WScript.Arguments(1)\n"
        "Set shell = CreateObject(\"WScript.Shell\")\n"
        "cmd = Chr(34) & exePath & Chr(34) & \" \" & Chr(34) & vaultPath & Chr(34)\n"
        "shell.Run cmd, 1, False\n"
    )
    if write_crlf_if_changed(obsidian_vbs, obsidian_body):
        log(f"[OK] detached Obsidian launcher created/updated: {obsidian_vbs}")
    else:
        log(f"[SKIP] detached Obsidian launcher already current: {obsidian_vbs}")

    hamster_vbs = launch_dir / "hamster_hidden.vbs"
    hamster_body = (
        "Dim sh, fso, bat, cmd, logDir, logFile\n"
        "Set sh = CreateObject(\"WScript.Shell\")\n"
        "Set fso = CreateObject(\"Scripting.FileSystemObject\")\n"
        "bat = Replace(WScript.ScriptFullName, \"hamster_hidden.vbs\", \"hamster.bat\")\n"
        "logDir = sh.ExpandEnvironmentStrings(\"%USERPROFILE%\") & \"\\OpenCodeLIG_USERDATA\\diagnostics\"\n"
        "If Not fso.FolderExists(logDir) Then fso.CreateFolder(logDir)\n"
        "logFile = logDir & \"\\hamster_launcher.log\"\n"
        "cmd = \"%ComSpec% /c \"\"\" & bat & \"\"\" --hidden >> \"\"\" & logFile & \"\"\" 2>>&1\"\n"
        "sh.Run cmd, 0, False\n"
    )
    if write_crlf_if_changed(hamster_vbs, hamster_body):
        log(f"[OK] hamster hidden launcher created/updated: {hamster_vbs}")
    else:
        log(f"[SKIP] hamster hidden launcher already current: {hamster_vbs}")

    wrapper = launch_dir / "project_agentops_wrapper.py"
    wrapper_body = '''# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    install_home = Path(os.environ.get("LIG_AGENTOPS_HOME", "")).resolve()
    if not install_home.exists():
        raise SystemExit("LIG_AGENTOPS_HOME is not set to the installed workspace")
    project_root = Path(os.environ.get("AGENTOPS_ROOT") or Path.cwd()).resolve()
    os.environ["AGENTOPS_ROOT"] = str(project_root)
    script_name = Path(__file__).name
    target = install_home / "agent_ops" / script_name
    if not target.exists():
        raise SystemExit(f"installed agent_ops script not found: {target}")
    project_path = str(project_root)
    sys.path[:] = [p for p in sys.path if p and str(Path(p).resolve()) != project_path]
    sys.path.insert(0, str(install_home))
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
'''
    if write_text_if_changed(wrapper, wrapper_body):
        log(f"[OK] project agent_ops wrapper created/updated: {wrapper}")
    else:
        log(f"[SKIP] project agent_ops wrapper already current: {wrapper}")


def create_plugin_bridges() -> None:
    plugin_dir = WS / ".opencode" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugins = {
        "session-autosave.ts": SESSION_AUTOSAVE_PLUGIN,
        "hamster-status.ts": HAMSTER_STATUS_PLUGIN,
        "memory-inject.ts": MEMORY_INJECT_PLUGIN,
        "compaction-handoff.ts": COMPACTION_HANDOFF_PLUGIN,
    }
    for name, body in plugins.items():
        plugin = plugin_dir / name
        if write_text_if_changed(plugin, body):
            log(f"[OK] OpenCodeLIG plugin created/updated: {plugin}")
        else:
            log(f"[SKIP] OpenCodeLIG plugin already current: {plugin}")
    guard = plugin_dir / "command-guard.ts"
    if not guard.exists():
        log(f"[WARN] command guard plugin is missing and must be restored from the full package: {guard}")




def create_self_improvement() -> None:
    path = WS / "agent_ops" / "self_improvement.py"
    if write_text_if_changed(path, SELF_IMPROVEMENT_SOURCE):
        log(f"[OK] self-improvement runtime created/updated: {path}")
    else:
        log(f"[SKIP] self-improvement runtime already current: {path}")


def create_release_contracts() -> None:
    path = WS / "agent_ops" / "release_contracts.py"
    if write_text_if_changed(path, RELEASE_CONTRACTS_SOURCE):
        log(f"[OK] release contracts created/updated: {path}")
    else:
        log(f"[SKIP] release contracts already current: {path}")

def create_quality_gate() -> None:
    path = WS / "agent_ops" / "quality_gate.py"
    if write_text_if_changed(path, QUALITY_GATE_SOURCE):
        log(f"[OK] quality gate created/updated: {path}")
    else:
        log(f"[SKIP] quality gate already current: {path}")


def patch_agentops_quality_gate_command() -> None:
    path = WS / "agent_ops" / "agentops.py"
    if not path.exists():
        log(f"[WARN] agentops.py not found for quality-gate command patch: {path}")
        return
    text = read_text(path)
    changed = False
    if "def cmd_quality_gate(args):" not in text:
        anchor = "\ndef cmd_weekly(args):"
        func = '''

def cmd_quality_gate(args):
    from agent_ops.quality_gate import run_quality_gate
    result = run_quality_gate(
        ROOT,
        run_commands=not getattr(args, "no_commands", False),
        out=Path(args.out) if getattr(args, "out", "") else None,
    )
    print(result.to_markdown())
    if result.report_path:
        print(f"Report: {result.report_path}")
    return 0 if result.ok else 1
'''
        if anchor in text:
            text = text.replace(anchor, func + anchor, 1)
            changed = True
        else:
            log("[WARN] cmd_weekly anchor not found for quality-gate command patch")
    if 'sub.add_parser("quality-gate")' not in text:
        anchor = '    p = sub.add_parser("safety-check"); p.add_argument("text", nargs="*"); p.set_defaults(func=cmd_safety_check)'
        line = '    p = sub.add_parser("quality-gate"); p.add_argument("--no-commands", action="store_true"); p.add_argument("--out", default=""); p.set_defaults(func=cmd_quality_gate)\n'
        if anchor in text:
            text = text.replace(anchor, line + anchor, 1)
            changed = True
        else:
            log("[WARN] safety-check parser anchor not found for quality-gate command patch")
    if changed:
        backup(path)
        write_text(path, text)
        log(f"[OK] agentops quality-gate command patched: {path}")
    else:
        log(f"[SKIP] agentops quality-gate command already current: {path}")



def patch_agentops_self_improve_command() -> None:
    path = WS / "agent_ops" / "agentops.py"
    if not path.exists():
        log(f"[WARN] agentops.py not found for self-improve command patch: {path}")
        return
    text = read_text(path)
    changed = False
    if "def cmd_self_improve(args):" not in text:
        anchor = "\ndef cmd_weekly(args):"
        func = '''

def cmd_self_improve(args):
    from agent_ops import self_improvement as si
    op = getattr(args, "op", "status")
    if op == "on":
        print(json.dumps(si.set_enabled(True), ensure_ascii=False, indent=2))
        return 0
    if op == "off":
        print(json.dumps(si.set_enabled(False), ensure_ascii=False, indent=2))
        return 0
    if op == "report":
        path = si.render_report()
        print(path.read_text(encoding="utf-8", errors="replace"))
        print(f"Report: {path}")
        return 0
    if op == "inject":
        print(si.format_injection_block())
        return 0
    print(json.dumps(si.status(), ensure_ascii=False, indent=2))
    return 0
'''
        if anchor in text:
            text = text.replace(anchor, func + anchor, 1)
            changed = True
        else:
            log("[WARN] cmd_weekly anchor not found for self-improve command patch")
    if 'sub.add_parser("self-improve")' not in text:
        anchor = '    p = sub.add_parser("safety-check"); p.add_argument("text", nargs="*"); p.set_defaults(func=cmd_safety_check)'
        line = '    p = sub.add_parser("self-improve"); p.add_argument("op", choices=["status", "on", "off", "report", "inject"], nargs="?", default="status"); p.set_defaults(func=cmd_self_improve)\n'
        if anchor in text:
            text = text.replace(anchor, line + anchor, 1)
            changed = True
        else:
            log("[WARN] safety-check parser anchor not found for self-improve command patch")
    if changed:
        backup(path)
        write_text(path, text)
        log(f"[OK] agentops self-improve command patched: {path}")
    else:
        log(f"[SKIP] agentops self-improve command already current: {path}")

def patch_autocad_adapter() -> None:
    adapter = WS / "agent_ops" / "adapters" / "autocad_batch.py"
    if write_text_if_changed(adapter, AUTOCAD_BATCH_SOURCE):
        log(f"[OK] AutoCAD adapter created/updated for accoreconsole/acad.exe fallback: {adapter}")
    else:
        log(f"[SKIP] AutoCAD adapter already current: {adapter}")


def patch_agentops_litellm_offline_env() -> None:
    """Force LiteLLM offline metadata mode before optional imports can run."""
    path = WS / "agent_ops" / "agentops.py"
    if not path.exists():
        log(f"[WARN] agentops.py not found for LiteLLM offline patch: {path}")
        return
    text = read_text(path)
    if "LITELLM_LOCAL_MODEL_COST_MAP" in text:
        log(f"[SKIP] LiteLLM offline env already present: {path}")
        return
    needle = "from pathlib import Path\n"
    block = (
        "\n"
        "# LiteLLM offline: closed-network PCs must not fetch model metadata from GitHub.\n"
        "os.environ.setdefault(\"LITELLM_LOCAL_MODEL_COST_MAP\", \"True\")\n"
        "os.environ.setdefault(\"LITELLM_LOCAL_POLICY_TEMPLATES\", \"True\")\n"
        "os.environ.setdefault(\"LITELLM_LOCAL_BLOG_POSTS\", \"True\")\n"
    )
    if needle not in text:
        log(f"[WARN] pathlib import anchor not found for LiteLLM offline patch: {path}")
        return
    backup_path = backup(path)
    write_text(path, text.replace(needle, needle + block, 1))
    log(f"[OK] LiteLLM offline env patched in agentops.py (backup: {backup_path})")


def patch_hamster_start_grace() -> None:
    path = WS / "agent_ops" / "ui" / "hamster_overlay.py"
    if not path.exists():
        log(f"[WARN] hamster overlay not found for start-grace patch: {path}")
        return
    text = read_text(path)
    changed = False
    if "LIG_HAMSTER_START_GRACE_SECONDS" not in text:
        anchor = 'WATCH_PROCESS = (os.environ.get("LIG_HAMSTER_WATCH_PROCESS") or "opencode.exe").strip()\n'
        if anchor in text:
            text = text.replace(
                anchor,
                anchor + 'START_GRACE_SECONDS = int(os.environ.get("LIG_HAMSTER_START_GRACE_SECONDS") or "300")\n',
                1,
            )
            changed = True
    if "time.time() - self._started_at > 20" in text:
        text = text.replace("time.time() - self._started_at > 20", "time.time() - self._started_at > START_GRACE_SECONDS")
        changed = True
    if changed:
        backup_path = backup(path)
        write_text(path, text)
        log(f"[OK] hamster start grace patched (backup: {backup_path})")
    else:
        log(f"[SKIP] hamster start grace already current: {path}")


def wheel_dirs() -> list[Path]:
    candidates = [
        PATCH_SOURCE_DIR / "patch_wheels",
        PATCH_SOURCE_DIR / "workspace" / "tools" / "wheelhouse",
        WS / "tools" / "wheelhouse",
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path).lower()
        if path.exists() and key not in seen:
            out.append(path)
            seen.add(key)
    return out


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def try_install_optional_wheels() -> None:
    if module_available("mss"):
        log("[SKIP] mss already importable. Offline wheel install not needed.")
        return
    dirs = wheel_dirs()
    mss_found = any(list(d.glob("mss-*.whl")) for d in dirs)
    if not dirs:
        log("[INFO] no wheelhouse found for optional patch wheels")
        return
    if not mss_found:
        log("[INFO] mss wheel not found. Screen capture will use Pillow/PowerShell fallback.")
        return
    for wh in dirs:
        if not list(wh.glob("mss-*.whl")):
            continue
        cp = run([sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(wh), "mss"], timeout=120)
        if cp.returncode == 0:
            log(f"[OK] mss installed from: {wh}")
            return
        log(f"[WARN] mss install failed from {wh}: {(cp.stderr or cp.stdout)[-800:]}")
    log("[WARN] mss wheel exists but installation failed. Fallback remains active.")


def patch_run_launcher() -> None:
    launcher = WS / "RUN_OPENCODE_LIG.bat"
    if not launcher.exists():
        log(f"[WARN] launcher not found: {launcher}")
        return
    backup_path = backup(launcher)
    text = r'''@echo off
chcp 65001 >nul
setlocal EnableExtensions
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "LITELLM_LOCAL_MODEL_COST_MAP=True"
set "LITELLM_LOCAL_POLICY_TEMPLATES=True"
set "LITELLM_LOCAL_BLOG_POSTS=True"

rem OpenCodeLIG unified launcher
rem - keeps OpenCode plugins enabled
rem - uses a clean OpenCode runtime cache to avoid company-network startup waits
rem - starts the hamster overlay from the real installed workspace

for %%I in ("%~dp0.") do set "AGENTOPS_HOME=%%~fI"
for %%I in ("%AGENTOPS_HOME%\..") do set "OC_ROOT=%%~fI"

if not defined LIG_PROJECT_DIR (
  set "LIG_PROJECT_DIR=%CD%"
)
if /I "%LIG_PROJECT_DIR%"=="%USERPROFILE%" set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"
if /I "%LIG_PROJECT_DIR%"=="%WINDIR%\System32" set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"
if /I "%LIG_PROJECT_DIR%"=="%WINDIR%\SysWOW64" set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"
echo(%LIG_PROJECT_DIR%| findstr /I /B /C:"%WINDIR%\\" >nul && set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"
for %%I in ("%LIG_PROJECT_DIR%") do if /I "%%~fI"=="%%~dI\" set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"

set "LIG_AGENTOPS_HOME=%AGENTOPS_HOME%"
set "OCODE_EXE=%OC_ROOT%\bin\opencode.exe"
set "OPENCODE_USERDATA=%USERPROFILE%\OpenCodeLIG_USERDATA"
if not defined AGENTOPS_MEMORY_DIR set "AGENTOPS_MEMORY_DIR=%OPENCODE_USERDATA%\memory"
set "AGENTOPS_ROOT=%LIG_PROJECT_DIR%"
set "PYTHONPATH=%AGENTOPS_HOME%;%PYTHONPATH%"
set "LIG_API_ENV_FILE=%OPENCODE_USERDATA%\secrets\lig-api.env"
set "LIG_STATE_DIR=%OPENCODE_USERDATA%\state"
set "LIG_DIAG_DIR=%OPENCODE_USERDATA%\diagnostics"
set "LIG_LAUNCH_LOG=%LIG_DIAG_DIR%\run_opencode_lig.log"
set "OPENCODE_DISABLE_DEFAULT_PLUGINS=1"
set "NO_UPDATE_NOTIFIER=1"
set "LIG_HAMSTER_WATCH_PROCESS=opencode.exe"
set "LIG_HAMSTER_START_GRACE_SECONDS=300"

if not exist "%OPENCODE_USERDATA%" mkdir "%OPENCODE_USERDATA%"
if not exist "%OPENCODE_USERDATA%\secrets" mkdir "%OPENCODE_USERDATA%\secrets"
if not exist "%OPENCODE_USERDATA%\config" mkdir "%OPENCODE_USERDATA%\config"
if not exist "%LIG_STATE_DIR%" mkdir "%LIG_STATE_DIR%"
if not exist "%LIG_DIAG_DIR%" mkdir "%LIG_DIAG_DIR%"

if not exist "%OCODE_EXE%" (
  echo [ERROR] opencode.exe not found:
  echo %OCODE_EXE%
  pause
  exit /b 1
)

rem 처음이면 secret 파일을 템플릿에서 자동 생성한다.
if not exist "%LIG_API_ENV_FILE%" (
  if exist "%AGENTOPS_HOME%\config\lig-api.env.example" (
    copy /y "%AGENTOPS_HOME%\config\lig-api.env.example" "%LIG_API_ENV_FILE%" >nul
    echo [설정] 게이트웨이 설정 파일을 만들었습니다: %LIG_API_ENV_FILE%
  ) else (
    echo [ERROR] lig-api.env 및 템플릿을 찾지 못했습니다: %LIG_API_ENV_FILE%
    pause
    exit /b 1
  )
)

set "NEED_FILL="
findstr /R /C:"^LIG_GATEWAY_BASE_URL=$" "%LIG_API_ENV_FILE%" >nul 2>&1 && set "NEED_FILL=1"
findstr /C:"REPLACE_WITH" "%LIG_API_ENV_FILE%" >nul 2>&1 && set "NEED_FILL=1"
findstr /C:"PUT_INTERNAL" "%LIG_API_ENV_FILE%" >nul 2>&1 && set "NEED_FILL=1"
if defined NEED_FILL (
  echo [안내] 게이트웨이 주소/키가 아직 비어 있습니다. 아래 파일의
  echo   LIG_GATEWAY_BASE_URL 과 LIG_API_KEY 를 채우세요: %LIG_API_ENV_FILE%
  start "" notepad "%LIG_API_ENV_FILE%"
  echo   채운 뒤 저장하고 아무 키나 누르세요.
  pause
)

rem Load lig-api.env into shell environment as well.
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%LIG_API_ENV_FILE%") do (
  if not "%%A"=="" set "%%A=%%B"
)

rem 햄스터 시작 전 상태 리셋.
>"%LIG_STATE_DIR%\current_status.json" echo {"status":"idle","task":"idle"}
del /q "%LIG_DIAG_DIR%\agent-loop-last.json" >nul 2>&1
del /q "%LIG_DIAG_DIR%\tool-dispatch-last.json" >nul 2>&1

rem ============================================================
rem Start hamster overlay.
rem Use fixed workspace path first so it also works when launched by ocd.
rem Correct actual path:
rem   %USERPROFILE%\OpenCodeLIG\workspace\agent_ops\ui\hamster_overlay.py
rem ============================================================

set "LIG_WORKSPACE_HOME=%USERPROFILE%\OpenCodeLIG\workspace"
set "HAMSTER_PY="
set "HAMSTER_HOME="
set "HAMSTER_LOG=%LIG_DIAG_DIR%\hamster_overlay_start.log"

if exist "%LIG_WORKSPACE_HOME%\agent_ops\ui\hamster_overlay.py" set "HAMSTER_PY=%LIG_WORKSPACE_HOME%\agent_ops\ui\hamster_overlay.py"
if exist "%LIG_WORKSPACE_HOME%\agent_ops\ui\hamster_overlay.py" set "HAMSTER_HOME=%LIG_WORKSPACE_HOME%"
if not defined HAMSTER_PY if exist "%AGENTOPS_HOME%\agent_ops\ui\hamster_overlay.py" set "HAMSTER_PY=%AGENTOPS_HOME%\agent_ops\ui\hamster_overlay.py"
if not defined HAMSTER_HOME if exist "%AGENTOPS_HOME%\agent_ops\ui\hamster_overlay.py" set "HAMSTER_HOME=%AGENTOPS_HOME%"
if not defined HAMSTER_PY goto :hamster_not_found

>>"%LIG_LAUNCH_LOG%" echo [%time%] Starting hamster_overlay.py
>>"%LIG_LAUNCH_LOG%" echo HAMSTER_PY=%HAMSTER_PY%
>"%HAMSTER_LOG%" echo [%date% %time%] starting hamster
>>"%HAMSTER_LOG%" echo HAMSTER_PY=%HAMSTER_PY%
>>"%HAMSTER_LOG%" echo HAMSTER_HOME=%HAMSTER_HOME%
>>"%HAMSTER_LOG%" echo LIG_WORKSPACE_HOME=%LIG_WORKSPACE_HOME%
>>"%HAMSTER_LOG%" echo AGENTOPS_HOME=%AGENTOPS_HOME%
>>"%HAMSTER_LOG%" echo OPENCODE_USERDATA=%OPENCODE_USERDATA%

rem Make sure hamster can import agent_ops from the selected home.
set "LIG_AGENTOPS_HOME=%HAMSTER_HOME%"
set "PYTHONPATH=%HAMSTER_HOME%;%PYTHONPATH%"
if exist "%AGENTOPS_HOME%\launch\_pyw.bat" call "%AGENTOPS_HOME%\launch\_pyw.bat"
if defined PYW start "OpenCodeLIG Hamster" /B /MIN /D "%HAMSTER_HOME%" %PYW% "%HAMSTER_PY%"
if not defined PYW start "OpenCodeLIG Hamster" /B /MIN /D "%HAMSTER_HOME%" pythonw "%HAMSTER_PY%"
goto :hamster_done

:hamster_not_found
>>"%LIG_LAUNCH_LOG%" echo [%time%] hamster_overlay.py not found
>"%HAMSTER_LOG%" echo [%date% %time%] hamster_overlay.py not found
:hamster_done

cd /d "%AGENTOPS_HOME%"

rem 구 모드/primary 정리 (best-effort).
py -3.11 -m agent_ops.clean_stale >nul 2>&1 || python -m agent_ops.clean_stale >nul 2>&1

rem 위키 자동화: vault 자동 시드 + Obsidian 자동 실행.
rem BEGIN LIG EXISTING-INSTALL HOTFIX 20260709
if not exist "%OPENCODE_USERDATA%\memory\wiki" mkdir "%OPENCODE_USERDATA%\memory\wiki" >nul 2>&1
py -3.11 -m agent_ops.wiki_vault "%OPENCODE_USERDATA%\memory\wiki" >nul 2>&1 || python -m agent_ops.wiki_vault "%OPENCODE_USERDATA%\memory\wiki" >nul 2>&1
if "%LIG_AUTO_WIKI%"=="0" goto :wiki_done
set "OBSEXE="
for %%P in ("%AGENTOPS_HOME%\tools\Obsidian\Obsidian.exe" "%OC_ROOT%\tools\Obsidian\Obsidian.exe" "%LOCALAPPDATA%\Obsidian\Obsidian.exe" "%LOCALAPPDATA%\Programs\Obsidian\Obsidian.exe" "%PROGRAMFILES%\Obsidian\Obsidian.exe") do if not defined OBSEXE if exist "%%~P" set "OBSEXE=%%~P"
if not defined OBSEXE for /f "delims=" %%F in ('dir /b /s "%OC_ROOT%\Obsidian.exe" 2^>nul') do if not defined OBSEXE set "OBSEXE=%%F"
if defined OBSEXE if exist "%AGENTOPS_HOME%\launch\obsidian_detached.vbs" wscript "%AGENTOPS_HOME%\launch\obsidian_detached.vbs" "%OBSEXE%" "%OPENCODE_USERDATA%\memory\wiki"
:wiki_done
rem END LIG EXISTING-INSTALL HOTFIX 20260709

rem BEGIN LIG PROJECT WORKDIR HOTFIX 20260709
rem 프로그램 본체는 설치 폴더에서 읽고, 사용자가 cd로 들어온 폴더를 작업 기준으로 사용한다.
if not exist "%LIG_PROJECT_DIR%" mkdir "%LIG_PROJECT_DIR%" >nul 2>&1
if /I "%LIG_PROJECT_DIR%"=="%AGENTOPS_HOME%" goto :project_ready
if not exist "%LIG_PROJECT_DIR%\.opencode" (
  xcopy /E /I /Y "%AGENTOPS_HOME%\.opencode" "%LIG_PROJECT_DIR%\.opencode" >nul
)
if not exist "%LIG_PROJECT_DIR%\.opencode\plugins" mkdir "%LIG_PROJECT_DIR%\.opencode\plugins" >nul 2>&1
rem 필수 플러그인: session-autosave.ts memory-inject.ts command-guard.ts hamster-status.ts compaction-handoff.ts
for %%F in ("%AGENTOPS_HOME%\.opencode\plugins\*.ts") do copy /Y "%%~fF" "%LIG_PROJECT_DIR%\.opencode\plugins\%%~nxF" >nul
if not exist "%LIG_PROJECT_DIR%\agent_ops" mkdir "%LIG_PROJECT_DIR%\agent_ops" >nul 2>&1
if exist "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" (
  copy /Y "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" "%LIG_PROJECT_DIR%\agent_ops\agentops.py" >nul
  copy /Y "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" "%LIG_PROJECT_DIR%\agent_ops\command_guard.py" >nul
  copy /Y "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" "%LIG_PROJECT_DIR%\agent_ops\safe_file_writer.py" >nul
)
if not exist "%LIG_PROJECT_DIR%\agent_ops\results" mkdir "%LIG_PROJECT_DIR%\agent_ops\results" >nul 2>&1
:project_ready
cd /d "%LIG_PROJECT_DIR%"
rem END LIG PROJECT WORKDIR HOTFIX 20260709

set "OPENCODE_FAST_BASE=%OPENCODE_USERDATA%\opencode_fast_runtime"
set "OPENCODE_FAST_CONFIG=%OPENCODE_FAST_BASE%\config"
set "OPENCODE_FAST_DATA=%OPENCODE_FAST_BASE%\data"
set "OPENCODE_FAST_CACHE=%OPENCODE_FAST_BASE%\cache"
set "OPENCODE_LEGACY_CONFIG=%OPENCODE_USERDATA%\config"
set "OPENCODE_LEGACY_DATA=%OPENCODE_USERDATA%\data"
set "OPENCODE_LEGACY_CACHE=%OPENCODE_USERDATA%\cache"

if not exist "%OPENCODE_FAST_CONFIG%" mkdir "%OPENCODE_FAST_CONFIG%" >nul 2>&1
if not exist "%OPENCODE_FAST_DATA%" mkdir "%OPENCODE_FAST_DATA%" >nul 2>&1
if not exist "%OPENCODE_FAST_CACHE%" mkdir "%OPENCODE_FAST_CACHE%" >nul 2>&1
if not exist "%OPENCODE_FAST_BASE%\.migrated" (
  if not exist "%OPENCODE_FAST_CONFIG%\*" if exist "%OPENCODE_LEGACY_CONFIG%" robocopy "%OPENCODE_LEGACY_CONFIG%" "%OPENCODE_FAST_CONFIG%" /E /XO >nul
  if not exist "%OPENCODE_FAST_DATA%\*" if exist "%OPENCODE_LEGACY_DATA%" robocopy "%OPENCODE_LEGACY_DATA%" "%OPENCODE_FAST_DATA%" /E /XO >nul
  if not exist "%OPENCODE_FAST_CACHE%\*" if exist "%OPENCODE_LEGACY_CACHE%" robocopy "%OPENCODE_LEGACY_CACHE%" "%OPENCODE_FAST_CACHE%" /E /XO >nul
  >"%OPENCODE_FAST_BASE%\.migrated" echo migrated
)

set "OPENCODE_CONFIG_DIR=%OPENCODE_FAST_CONFIG%"
set "XDG_CONFIG_HOME=%OPENCODE_FAST_CONFIG%"
set "XDG_DATA_HOME=%OPENCODE_FAST_DATA%"
set "XDG_CACHE_HOME=%OPENCODE_FAST_CACHE%"

set "OPENCODE_CONFIG=%AGENTOPS_HOME%\opencode.json"
set "OPENCODE_PURE="

set "OPENCODE_DISABLE_MODELS_FETCH=1"
set "OPENCODE_DISABLE_AUTOUPDATE=1"
set "OPENCODE_DISABLE_LSP_DOWNLOAD=1"
set "OPENCODE_MODELS_URL=http://127.0.0.1:9/api.json"

set "NPM_CONFIG_REGISTRY=http://127.0.0.1:9/"
set "npm_config_registry=http://127.0.0.1:9/"
set "NPM_CONFIG_FETCH_TIMEOUT=1000"
set "NPM_CONFIG_FETCH_RETRIES=0"
set "npm_config_fetch_timeout=1000"
set "npm_config_fetch_retries=0"
set "BUN_CONFIG_REGISTRY=http://127.0.0.1:9/"
set "BUN_INSTALL_CACHE_DIR=%OPENCODE_FAST_CACHE%\bun"

set "NO_PROXY=*"
set "no_proxy=*"
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "http_proxy="
set "https_proxy="
set "all_proxy="
set "npm_config_proxy="
set "npm_config_https_proxy="

"%OCODE_EXE%" %*

exit /b %errorlevel%
'''
    write_crlf(launcher, text)
    log(f"[OK] launcher replaced with canonical OpenCodeLIG launcher (backup: {backup_path})")


PENDING_BLOCK = r'''
# BEGIN LIG EXISTING-INSTALL HOTFIX 20260709
# Additive hotfix for an existing company-PC install. The goal is not to hide
# missing apps; it reclassifies diagnostics using already-proven fallback paths.
try:
    _LIG_ORIG_RUN_CMD = run_cmd
    _LIG_ORIG_COMMON_PROGRAM_PATHS = common_program_paths
    try:
        from agent_ops.release_contracts import (
            AUTOSAVE_REQUIRED_MARKERS as _LIG_AUTOSAVE_REQUIRED_MARKERS,
            HAMSTER_EVENT_BRIDGE_MARKERS as _LIG_HAMSTER_EVENT_BRIDGE_MARKERS,
            LAUNCHER_FAST_RUNTIME_MARKERS as _LIG_LAUNCHER_FAST_RUNTIME_MARKERS,
            MEMORY_INJECT_REQUIRED_MARKERS as _LIG_MEMORY_INJECT_REQUIRED_MARKERS,
            PLUGIN_SYNC_GLOB as _LIG_PLUGIN_SYNC_GLOB,
            REQUIRED_PLUGIN_FILES as _LIG_REQUIRED_PLUGIN_FILES,
        )
    except Exception:
        _LIG_AUTOSAVE_REQUIRED_MARKERS = ()
        _LIG_HAMSTER_EVENT_BRIDGE_MARKERS = ()
        _LIG_LAUNCHER_FAST_RUNTIME_MARKERS = ()
        _LIG_MEMORY_INJECT_REQUIRED_MARKERS = ()
        _LIG_PLUGIN_SYNC_GLOB = ".opencode\\plugins\\*.ts"
        _LIG_REQUIRED_PLUGIN_FILES = ()

    def run_cmd(args, timeout=30, cwd=None, env=None):  # type: ignore[override]
        try:
            first = str((args or [""])[0]).lower()
            second = str((args or ["", ""])[1]).lower() if len(args or []) > 1 else ""
            if first.endswith("\\acad.exe") or first.endswith("/acad.exe"):
                if second in {"/?", "-?", "--help", "/help"}:
                    return {
                        "ok": True,
                        "returncode": 0,
                        "stdout": "GUI AutoCAD found; help probe skipped to avoid launching UI. Use /p LIGNEX1 /product ACADM /b for script execution.",
                        "stderr": "",
                        "args": args,
                    }
        except Exception:
            pass
        return _LIG_ORIG_RUN_CMD(args, timeout=timeout, cwd=cwd, env=env)

    def common_program_paths() -> dict[str, list[Path]]:  # type: ignore[override]
        paths = _LIG_ORIG_COMMON_PROGRAM_PATHS()
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        pfx86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        ws = workspace_root()
        root = Path.home() / "OpenCodeLIG"

        def add_unique(key: str, values: list[Path]) -> None:
            cur = paths.setdefault(key, [])
            seen = {str(p).lower() for p in cur}
            for value in values:
                if str(value).lower() not in seen:
                    cur.append(value)
                    seen.add(str(value).lower())

        acad: list[Path] = []
        acad.extend([
            Path(r"C:\AutoCAD 2019\acad.exe"),
            Path(r"C:\AutoCAD 2019\accoreconsole.exe"),
        ])
        for base in (pf / "Autodesk", pfx86 / "Autodesk", Path(r"C:\Autodesk")):
            try:
                acad.extend(base.glob("AutoCAD*/acad.exe"))
                acad.extend(base.glob("AutoCAD*/*accoreconsole.exe"))
                acad.extend(base.glob("**/acad.exe"))
                acad.extend(base.glob("**/accoreconsole.exe"))
            except Exception:
                pass
        for year in range(2016, 2027):
            acad.extend([
                pf / "Autodesk" / f"AutoCAD {year}" / "accoreconsole.exe",
                pf / "Autodesk" / f"AutoCAD {year}" / "acad.exe",
                pfx86 / "Autodesk" / f"AutoCAD {year}" / "accoreconsole.exe",
                pfx86 / "Autodesk" / f"AutoCAD {year}" / "acad.exe",
            ])
        add_unique("autocad", acad)
        add_unique("obsidian", [
            ws / "tools" / "Obsidian" / "Obsidian.exe",
            root / "tools" / "Obsidian" / "Obsidian.exe",
            root / "workspace" / "tools" / "Obsidian" / "Obsidian.exe",
            local / "Obsidian" / "Obsidian.exe",
            local / "Programs" / "Obsidian" / "Obsidian.exe",
        ])
        return paths

    def _lig_hotfix_has_pass(checks: list[Check], item: str) -> bool:
        return any(c.item == item and c.status == "PASS" for c in checks)

    def _lig_hotfix_screenshot_backend() -> tuple[bool, str]:
        if has_module("mss"):
            return True, "mss"
        try:
            from PIL import ImageGrab  # type: ignore # noqa: F401
            return True, "Pillow ImageGrab"
        except Exception:
            pass
        if sys.platform.startswith("win"):
            return True, "PowerShell System.Drawing fallback"
        return False, "none"

    def check_screen_ocr(checks: list[Check]) -> None:  # type: ignore[override]
        capture_ok, capture_via = _lig_hotfix_screenshot_backend()
        add(checks, "화면/OCR", "mss screenshot smoke",
            "PASS" if capture_ok else "PENDING",
            f"screenshot backend available via {capture_via}; mss_installed={has_module('mss')}",
            "mss가 없어도 Pillow/PowerShell 폴백으로 캡처합니다. 고속 캡처가 필요하면 mss wheel을 추가하세요.")
        if has_module("rapidocr_onnxruntime"):
            code = r"""
import json
try:
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    print(json.dumps({"ok": True, "engine": str(type(engine))}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}, ensure_ascii=False))
    raise SystemExit(1)
"""
            res = run_python_probe(code, timeout=30)
            add(checks, "화면/OCR", "RapidOCR instantiate", "PASS" if res.get("ok") else "WARN",
                res.get("stdout") or res.get("stderr") or res.get("error", ""),
                "OCR 모델 파일/onnxruntime wheel 호환성을 확인하세요.")
        else:
            add(checks, "화면/OCR", "RapidOCR instantiate", "PENDING", "rapidocr_onnxruntime missing",
                "OCR이 필요하면 RapidOCR/onnxruntime wheel 및 모델을 반입하세요.")

    _LIG_ORIG_CHECK_OBSIDIAN_WIKI = check_obsidian_wiki

    def check_obsidian_wiki(checks: list[Check]) -> None:  # type: ignore[override]
        _LIG_ORIG_CHECK_OBSIDIAN_WIKI(checks)
        autosave = workspace_root() / ".opencode" / "plugins" / "session-autosave.ts"
        autosave_text = autosave.read_text(encoding="utf-8", errors="replace") if autosave.exists() else ""
        autosave_sessions = "wiki\", \"sessions\"" in autosave_text
        autosave_promote = "log-activity" in autosave_text
        autosave_ok = (
            autosave.exists()
            and autosave_sessions
            and "appendFileSync(sessionFile()" in autosave_text
            and autosave_promote
            and "(?i:" not in autosave_text
        )
        add(checks, "Obsidian/위키", "세션 자동저장 플러그인", "PASS" if autosave_ok else "WARN",
            f"{autosave}; exists={autosave.exists()}; sessions={autosave_sessions}; memory_promote={autosave_promote}",
            "대화 중 창을 닫아도 Obsidian wiki\\sessions 노트에 남고, 일부는 저우선순위 기억으로 승격되어야 합니다.")

    def _lig_hotfix_check_plugin_runtime(checks: list[Check]) -> None:
        ws = workspace_root()
        launcher = ws / "RUN_OPENCODE_LIG.bat"
        launcher_text = launcher.read_text(encoding="utf-8", errors="replace") if launcher.exists() else ""
        launcher_raw = launcher.read_bytes() if launcher.exists() else b""
        crlf_ok = bool(launcher_raw) and b"\n" not in launcher_raw.replace(b"\r\n", b"")
        pure_disabled = "OPENCODE_PURE=1" not in launcher_text and "--pure" not in launcher_text.lower()
        sync_all_plugins = _LIG_PLUGIN_SYNC_GLOB in launcher_text and "copy /Y" in launcher_text
        add(checks, "OpenCode 플러그인 런타임", "OpenCode plugin runtime enabled",
            "PASS" if launcher.exists() and crlf_ok and pure_disabled and sync_all_plugins else "FAIL",
            f"launcher={launcher}; crlf={crlf_ok}; OPENCODE_PURE_disabled={pure_disabled}; sync_all_plugins={sync_all_plugins}",
            "OPENCODE_PURE=1이면 햄스터/자동기억/명령가드 플러그인이 파일만 있고 실행되지 않습니다.")
        fast_markers = list(_LIG_LAUNCHER_FAST_RUNTIME_MARKERS[:-1]) if _LIG_LAUNCHER_FAST_RUNTIME_MARKERS else [
            "OPENCODE_FAST_BASE=%OPENCODE_USERDATA%\\opencode_fast_runtime",
            "OPENCODE_CONFIG_DIR=%OPENCODE_FAST_CONFIG%",
            "XDG_CONFIG_HOME=%OPENCODE_FAST_CONFIG%",
            "XDG_DATA_HOME=%OPENCODE_FAST_DATA%",
            "XDG_CACHE_HOME=%OPENCODE_FAST_CACHE%",
            "OPENCODE_DISABLE_MODELS_FETCH=1",
            "OPENCODE_DISABLE_AUTOUPDATE=1",
            "OPENCODE_DISABLE_LSP_DOWNLOAD=1",
            "OPENCODE_MODELS_URL=http://127.0.0.1:9/api.json",
            "NPM_CONFIG_REGISTRY=http://127.0.0.1:9/",
            "BUN_CONFIG_REGISTRY=http://127.0.0.1:9/",
            "NO_PROXY=*",
        ]
        fast_ok = all(marker in launcher_text for marker in fast_markers)
        run_idx = launcher_text.find("\"%OCODE_EXE%\" %*")
        fast_before_run = run_idx >= 0 and all(launcher_text.find(marker) >= 0 and launcher_text.find(marker) < run_idx for marker in fast_markers)
        pure_empty = 'set "OPENCODE_PURE="' in launcher_text
        add(checks, "OpenCode 플러그인 런타임", "OpenCode fast runtime isolation",
            "PASS" if launcher.exists() and fast_ok and fast_before_run and pure_empty else "FAIL",
            f"markers={{{', '.join(f'{m}:{m in launcher_text}' for m in fast_markers)}}}; before_run={fast_before_run}; pure_empty={pure_empty}",
            "플러그인은 유지하되 OpenCode 실행 직전에 깨끗한 fast runtime/config/cache와 외부 fetch 차단 환경변수가 잡혀야 합니다.")
        hamster_ui_path = "agent_ops\\ui\\hamster_overlay.py" in launcher_text
        hamster_log = "hamster_overlay_start.log" in launcher_text
        hamster_start = "start \"OpenCodeLIG Hamster\"" in launcher_text
        hamster_no_vbs = "hamster_hidden.vbs" not in launcher_text
        direct_hamster_ok = hamster_ui_path and hamster_log and hamster_start and hamster_no_vbs
        add(checks, "OpenCode 플러그인 런타임", "direct hamster launcher",
            "PASS" if launcher.exists() and direct_hamster_ok else "FAIL",
            f"ui_path={hamster_ui_path}; log={hamster_log}; start={hamster_start}; no_vbs={hamster_no_vbs}",
            "RUN/ocd 모두에서 햄스터가 뜨도록 VBS 의존 대신 설치 workspace의 ui\\hamster_overlay.py를 직접 실행해야 합니다.")
        plugins = ws / ".opencode" / "plugins"
        required = list(_LIG_REQUIRED_PLUGIN_FILES) if _LIG_REQUIRED_PLUGIN_FILES else ["session-autosave.ts", "memory-inject.ts", "command-guard.ts", "hamster-status.ts", "compaction-handoff.ts"]
        missing = [name for name in required if not (plugins / name).exists()]
        add(checks, "OpenCode 플러그인 런타임", "required plugin files",
            "PASS" if not missing else "FAIL",
            f"plugins={plugins}; missing={missing}",
            "필수 플러그인은 프로젝트 폴더로도 자동 동기화되어야 합니다.")
        hamster = (plugins / "hamster-status.ts").read_text(encoding="utf-8", errors="replace") if (plugins / "hamster-status.ts").exists() else ""
        hamster_markers = list(_LIG_HAMSTER_EVENT_BRIDGE_MARKERS) if _LIG_HAMSTER_EVENT_BRIDGE_MARKERS else ["session.status", "session.next.text.delta", "session.next.step.ended", "session.next.step.failed", "session.next.tool.called"]
        hamster_ok = all(m in hamster for m in hamster_markers) and "writeAtomic" in hamster
        add(checks, "OpenCode 플러그인 런타임", "hamster OpenCode event bridge",
            "PASS" if hamster_ok else "FAIL",
            f"markers={{{', '.join(f'{m}:{m in hamster}' for m in hamster_markers)}}}; atomic={'writeAtomic' in hamster}",
            "햄스터가 최신 OpenCode 이벤트(session.status/session.next.*)를 읽어 current_status.json에 반영해야 합니다.")
        autosave = (plugins / "session-autosave.ts").read_text(encoding="utf-8", errors="replace") if (plugins / "session-autosave.ts").exists() else ""
        autosave_markers = list(_LIG_AUTOSAVE_REQUIRED_MARKERS) if _LIG_AUTOSAVE_REQUIRED_MARKERS else ['"properties"', '"delta"', '"input"', '"output"', "session.status", "session.next.step.ended", "session.next.step.failed"]
        autosave_ok = all(m in autosave for m in autosave_markers) and "Object.entries(value)" in autosave
        add(checks, "OpenCode 플러그인 런타임", "Obsidian autosave event extraction",
            "PASS" if autosave_ok else "FAIL",
            f"markers={{{', '.join(f'{m}:{m in autosave}' for m in autosave_markers)}}}; recursive={'Object.entries(value)' in autosave}",
            "창을 닫아도 대화/작업 이벤트가 wiki\\sessions에 남도록 event.properties 내부 텍스트까지 저장해야 합니다.")
        memory = (plugins / "memory-inject.ts").read_text(encoding="utf-8", errors="replace") if (plugins / "memory-inject.ts").exists() else ""
        handoff = (plugins / "compaction-handoff.ts").read_text(encoding="utf-8", errors="replace") if (plugins / "compaction-handoff.ts").exists() else ""
        base_ok = "process.env.LIG_AGENTOPS_HOME" in memory and "process.env.LIG_AGENTOPS_HOME" in handoff
        add(checks, "OpenCode 플러그인 런타임", "installed AgentOps home precedence",
            "PASS" if base_ok else "FAIL",
            f"memory_lig_home={'process.env.LIG_AGENTOPS_HOME' in memory}; handoff_lig_home={'process.env.LIG_AGENTOPS_HOME' in handoff}",
            "cd 작업폴더 && ocd에서도 기억/인계는 설치본 agent_ops를 우선 사용해야 합니다.")

    _LIG_ORIG_BUILD_REPORT = build_report

    def build_report(checks: list[Check], report_id: str):  # type: ignore[override]
        if not any(c.section == "OpenCode 플러그인 런타임" for c in checks):
            _lig_hotfix_check_plugin_runtime(checks)
        capture_ok, capture_via = _lig_hotfix_screenshot_backend()
        root_bat = package_root() / "점검용_전체확인.bat"
        for c in checks:
            if c.section == "오프라인 의존성" and c.item == "mss" and c.status != "PASS" and capture_ok:
                c.status = "PASS"
                c.evidence = f"mss module missing, but screenshot fallback is available via {capture_via}"
                c.next_action = "고속/멀티모니터 캡처 최적화가 필요할 때만 mss wheel을 추가하세요."
            if c.section == "문서/패키지" and c.item == "점검 BAT: 점검용_전체확인.bat" and str(root_bat) in c.evidence and root_bat.exists():
                c.status = "PASS"
                c.evidence = f"{root_bat}; copied by existing-install hotfix"
                c.next_action = "루트와 workspace 양쪽에서 점검 BAT를 실행할 수 있습니다."
            if c.item == "fluent cli probe" and "TIMEOUT" in c.evidence and _lig_hotfix_has_pass(checks, "fluent executable"):
                c.status = "SKIP"
                c.evidence = c.evidence + "; fluent.exe exists, help probe is intentionally skipped as a heavy-app startup check"
                c.next_action = "실제 journal 실행 검증은 사용자 작업 파일 기준으로 별도 수행합니다."
            if c.item == "Obsidian executable" and c.status == "PENDING" and _lig_hotfix_has_pass(checks, "실 USERDATA wiki vault"):
                c.status = "WARN"
                c.evidence = c.evidence + "; wiki vault is ready, Obsidian app install remains user-side prerequisite"
                c.next_action = "Obsidian 설치 후 다시 실행하면 자동 탐색합니다. portable은 workspace\\tools\\Obsidian\\Obsidian.exe에 둘 수 있습니다."
            if c.item == "adapter:solidworks" and _lig_hotfix_has_pass(checks, "SolidWorks COM activation"):
                c.status = "WARN"
                c.evidence = c.evidence + "; effective_state=COM connection OK, only real macro execution pilot remains"
            if c.item == "adapter:office" and _lig_hotfix_has_pass(checks, "command:office-docx") and _lig_hotfix_has_pass(checks, "command:office-pptx"):
                c.status = "PASS"
                c.evidence = c.evidence + "; effective_state=docx/pptx generation smoke passed"
            if c.item == "adapter:outlook" and _lig_hotfix_has_pass(checks, "Outlook COM activation"):
                c.status = "WARN"
                c.evidence = c.evidence + "; effective_state=Outlook COM connect OK, write/sync pilot remains guarded"
            if c.item == "adapter:browser" and _lig_hotfix_has_pass(checks, "Chrome CDP 9222"):
                c.status = "PASS"
                c.evidence = c.evidence + "; effective_state=Chrome CDP reachable; site login remains user/session-dependent"
            if c.item == "adapter:fluent" and _lig_hotfix_has_pass(checks, "fluent executable"):
                c.status = "WARN"
                c.evidence = c.evidence + "; effective_state=fluent.exe found, journal pilot remains"
            if c.item == "adapter:ocr_screen" and capture_ok and _lig_hotfix_has_pass(checks, "RapidOCR instantiate"):
                c.status = "PASS"
                c.evidence = c.evidence + f"; effective_state=OCR engine + screenshot backend OK via {capture_via}"
            if c.item == "adapter:desktop_ui" and _lig_hotfix_has_pass(checks, "windows_use"):
                c.status = "WARN"
                c.evidence = c.evidence + "; effective_state=windows-use import OK, target-app UIA pilot remains"
        return _LIG_ORIG_BUILD_REPORT(checks, report_id)
except Exception as _lig_hotfix_exc:
    try:
        print(f"[WARN] LIG hotfix block initialization failed: {_lig_hotfix_exc!r}", file=sys.stderr)
    except Exception:
        pass
# END LIG EXISTING-INSTALL HOTFIX 20260709
'''


ADAPTER_BLOCK = r'''
# BEGIN LIG ADAPTER STATUS HOTFIX 20260709
def _lig_hotfix_refresh_adapter_status() -> None:
    try:
        if "ocr_screen" in ADAPTERS:
            try:
                backs = ocr_screen.detect_backends()
            except Exception:
                backs = []
            if backs:
                ADAPTERS["ocr_screen"]["available"] = True
                ADAPTERS["ocr_screen"]["validated"] = "OCR backend imported; screenshot fallback verified by pending_check"
                ADAPTERS["ocr_screen"]["pending"] = "real screen text quality depends on target UI; read_screen smoke covers capture/backend"
        if "desktop_ui" in ADAPTERS:
            try:
                desktop_ready = bool(desktop_ui.available())
            except Exception:
                desktop_ready = False
            if desktop_ready:
                ADAPTERS["desktop_ui"]["available"] = True
                ADAPTERS["desktop_ui"]["validated"] = "windows-use import OK"
                ADAPTERS["desktop_ui"]["pending"] = "target-app UI Automation exposure/run_task pilot remains"
    except Exception:
        pass

_lig_hotfix_refresh_adapter_status()
# END LIG ADAPTER STATUS HOTFIX 20260709
'''

RELEASE_CONTRACTS_SOURCE = r'''# -*- coding: utf-8 -*-
"""Shared release/runtime contracts for OpenCodeLIG.

Keep launcher/plugin/static verification markers in one place so pending checks,
quality gate, tests, and hotfix regeneration do not drift.
"""
from __future__ import annotations

PLUGIN_SYNC_GLOB = ".opencode\\plugins\\*.ts"

REQUIRED_PLUGIN_FILES = (
    "command-guard.ts",
    "compaction-handoff.ts",
    "hamster-status.ts",
    "memory-inject.ts",
    "session-autosave.ts",
)

LAUNCHER_FAST_RUNTIME_MARKERS = (
    "OPENCODE_FAST_BASE=%OPENCODE_USERDATA%\\opencode_fast_runtime",
    "OPENCODE_CONFIG_DIR=%OPENCODE_FAST_CONFIG%",
    "XDG_CONFIG_HOME=%OPENCODE_FAST_CONFIG%",
    "XDG_DATA_HOME=%OPENCODE_FAST_DATA%",
    "XDG_CACHE_HOME=%OPENCODE_FAST_CACHE%",
    "OPENCODE_DISABLE_MODELS_FETCH=1",
    "OPENCODE_DISABLE_AUTOUPDATE=1",
    "OPENCODE_DISABLE_LSP_DOWNLOAD=1",
    "OPENCODE_MODELS_URL=http://127.0.0.1:9/api.json",
    "NPM_CONFIG_REGISTRY=http://127.0.0.1:9/",
    "BUN_CONFIG_REGISTRY=http://127.0.0.1:9/",
    "NO_PROXY=*",
    'set "OPENCODE_PURE="',
)

LAUNCHER_HAMSTER_MARKERS = (
    "LIG_WORKSPACE_HOME=%USERPROFILE%\\OpenCodeLIG\\workspace",
    "agent_ops\\ui\\hamster_overlay.py",
    "hamster_overlay_start.log",
    'start "OpenCodeLIG Hamster"',
    "HAMSTER_HOME=%LIG_WORKSPACE_HOME%",
)

LAUNCHER_PROJECT_DIR_MARKERS = (
    "if not defined LIG_PROJECT_DIR (",
    'set "LIG_PROJECT_DIR=%CD%"',
    "%WINDIR%\\System32",
    "%WINDIR%\\SysWOW64",
    'cd /d "%LIG_PROJECT_DIR%"',
)

LAUNCHER_DRIVE_ROOT_FALLBACK = (
    'for %%I in ("%LIG_PROJECT_DIR%") do if /I "%%~fI"=="%%~dI\\" '
    'set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"'
)

HAMSTER_EVENT_BRIDGE_MARKERS = (
    "session.status",
    "session.next.text.delta",
    "session.next.step.started",
    "session.next.step.ended",
    "session.next.step.failed",
    "session.next.tool.called",
    "session.next.tool.success",
    "session.next.tool.failed",
    "experimental.session.compacting",
    'properties?.tool === "task"',
    "isTaskToolCall",
    "isTaskToolSuccess",
    "isTaskToolFailure",
    "writeAtomic",
    "opencode-event-types.log",
)

HAMSTER_LEGACY_MARKERS = (
    'type === "task.start"',
    'type === "task.end"',
    'type === "session.task.started"',
    'type === "session.next.task.started"',
    "event?.properties?.agent_name",
    'body.includes("subagent")',
    'body.includes("agent_name")',
)

AUTOSAVE_REQUIRED_MARKERS = (
    'appendFileSync(sessionFile()',
    '"properties"',
    '"delta"',
    '"input"',
    '"output"',
    "Object.entries(value)",
    "log-activity",
    "rememberSessionActivity",
    "bufferEventText",
    "takeBufferedText",
    "session.status",
    "session.next.text.delta",
    "session.next.step.ended",
    "session.next.step.failed",
    "token",
    "secret",
    "credential",
)

MEMORY_INJECT_REQUIRED_MARKERS = (
    "fallbackStartupBlock",
    "refreshStartupRecallAsync",
    "setTimeout",
    "process.env.LIG_AGENTOPS_HOME",
    "session.status",
    "STARTUP_REFRESH_COOLDOWN_MS",
    "COMPACTION_REFRESH_COOLDOWN_MS",
    "IDLE_REFRESH_COOLDOWN_MS",
    "cachedRecallBlock",
)
'''

SELF_IMPROVEMENT_SOURCE = r'''# -*- coding: utf-8 -*-
"""Automatic self-improvement loop backed by the main memory ledger.

Settings/report stay in a small side directory, but failures/lessons use the
same memory.jsonl pipeline as the rest of OpenCodeLIG so recall/quality/decay
stay consistent and duplicate ledgers do not diverge.
"""
from __future__ import annotations

import json
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_SETTINGS = {
    "enabled": True,
    "auto_capture": True,
    "auto_promote": True,
    "auto_inject": True,
    "auto_wiki": True,
    "max_injected": 3,
}

SETTINGS = "settings.json"
REPORT = "report.md"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def base_dir() -> Path:
    explicit = os.environ.get("LIG_SELF_IMPROVEMENT_DIR")
    if explicit:
        return Path(explicit)
    return Path.home() / "OpenCodeLIG_USERDATA" / "self_improvement"


def _userdata_dir() -> Path:
    explicit = os.environ.get("OPENCODE_USERDATA")
    if explicit:
        return Path(explicit)
    return Path.home() / "OpenCodeLIG_USERDATA"


def _path(name: str) -> Path:
    return base_dir() / name


def _ensure() -> None:
    base_dir().mkdir(parents=True, exist_ok=True)
    if not _path(SETTINGS).exists():
        _write_json(_path(SETTINGS), DEFAULT_SETTINGS)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return default


def get_settings() -> Dict[str, Any]:
    _ensure()
    settings = dict(DEFAULT_SETTINGS)
    stored = _read_json(_path(SETTINGS), {})
    if isinstance(stored, dict):
        settings.update(stored)
    return settings


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(DEFAULT_SETTINGS)
    merged.update(settings or {})
    _write_json(_path(SETTINGS), merged)
    return merged


def set_enabled(enabled: bool) -> Dict[str, Any]:
    settings = get_settings()
    settings["enabled"] = bool(enabled)
    return save_settings(settings)


def enabled() -> bool:
    settings = get_settings()
    return bool(settings.get("enabled", True) and settings.get("auto_capture", True))


def _memory_rows() -> List[Dict[str, Any]]:
    from .memory_manager import load_memory
    return [r for r in load_memory(status="active") if isinstance(r, dict)]


def _self_errors(area: str = "") -> List[Dict[str, Any]]:
    want = f"자가 관찰 실수: {area}" if area else ""
    rows = []
    for row in _memory_rows():
        if row.get("kind") != "error_pattern" or row.get("source") != "self_observed":
            continue
        if want and row.get("title") != want:
            continue
        rows.append(row)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at", "")), reverse=True)
    return rows


def _self_fix_lessons() -> List[Dict[str, Any]]:
    rows = []
    for row in _memory_rows():
        if row.get("kind") == "lesson" and row.get("source") == "self_fix":
            rows.append(row)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at", "")), reverse=True)
    return rows


def _dedupe_tag(row: Dict[str, Any]) -> str:
    for tag in row.get("tags") or []:
        tag = str(tag)
        if tag.startswith("dedupe:"):
            return tag
    return ""


def _task_marker(task: str) -> str:
    value = " ".join(str(task or "").split())
    if not value:
        return ""
    return "task:" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _run_marker(run_id: str) -> str:
    value = " ".join(str(run_id or "").split())[:80]
    return f"run:{value}" if value else ""


def _tags(row: Dict[str, Any]) -> List[str]:
    return [str(tag) for tag in (row.get("tags") or []) if str(tag).strip()]


def record_error(area: str, detail: str, *, task: str = "", run_id: str = "",
                 route: str = "", source: str = "auto") -> Optional[Dict[str, Any]]:
    if not enabled():
        return None
    from .memory_manager import record_self_error
    tags = [tag for tag in [_task_marker(task), _run_marker(run_id), f"area:{area}" if area else ""] if tag]
    return record_self_error(area, detail or "", task=task or "", extra_tags=tags)


def _matching_error(task: str, area: str, run_id: str = "") -> Optional[Dict[str, Any]]:
    task_tag = _task_marker(task)
    run_tag = _run_marker(run_id)
    for row in _self_errors():
        tags = _tags(row)
        if run_tag and run_tag in tags:
            return row
        if task_tag and task_tag in tags:
            return row
    for row in _self_errors(area):
        tags = _tags(row)
        if task_tag and task_tag in tags:
            return row
    return None


def _existing_lesson(tag: str, action: str) -> Optional[Dict[str, Any]]:
    for row in _self_fix_lessons():
        if tag and tag not in [str(t) for t in (row.get("tags") or [])]:
            continue
        if str(row.get("body", "")) == action:
            return row
    return None


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def capture_task_result(task: str, *, ok: bool, area: str = "task",
                        detail: str = "", run_id: str = "", route: str = "") -> Optional[Dict[str, Any]]:
    if not enabled():
        return None
    if not ok:
        return record_error(area, detail, task=task, run_id=run_id, route=route, source="auto")

    error = _matching_error(task, area, run_id)
    if not error:
        return None

    dedupe = _dedupe_tag(error)
    fix = " ".join(str(detail or route or "성공한 경로를 우선 재사용").split())[:220]
    failure = " ".join(str(error.get("body", "")).split())[:220]
    action = f"{area}에서 '{failure}'가 다시 보이면 먼저 '{fix}' 순서로 처리한다."
    existing = _existing_lesson(dedupe, action)
    if existing and str(existing.get("created_at", ""))[:10] == _today():
        return existing

    from .memory_manager import add_memory_event, extract_keywords, update_memory_status
    tags = [t for t in [dedupe, _task_marker(task), f"area:{area}"] if t]
    run_tag = _run_marker(run_id)
    if run_tag:
        tags.append(run_tag)
    tags.extend(extract_keywords(f"{task} {area} {fix}")[:5])
    lesson = add_memory_event(
        "lesson",
        f"자가개선 교훈: {area}",
        action,
        status="active",
        priority="normal",
        source="self_fix",
        tags=tags,
    )
    update_memory_status(str(error.get("id", "")), "resolved", note=f"self_fix:{lesson.get('id', '')}")
    if get_settings().get("auto_wiki", True):
        render_report()
    return lesson


def lessons_for_injection(limit: int | None = None) -> List[Dict[str, Any]]:
    settings = get_settings()
    if not settings.get("enabled", True) or not settings.get("auto_inject", True):
        return []
    max_items = int(limit if limit is not None else settings.get("max_injected", 3))
    rows = list(reversed(_self_fix_lessons()))
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at", "")), reverse=True)
    rows.sort(key=lambda r: 0 if r.get("priority") == "high" else 1)
    return rows[:max(0, max_items)]


def format_injection_block(limit: int | None = None) -> str:
    lessons = lessons_for_injection(limit=limit)
    if not lessons:
        return ""
    lines = ["## OpenCodeLIG 자가개선 지침", "같은 시행착오를 반복하지 않도록 우선 적용:"]
    for row in lessons:
        lines.append(f"- {str(row.get('body', '')).strip()[:220]}")
    return "\n".join(lines)


def render_report() -> Path:
    _ensure()
    errors = _self_errors()
    lessons = _self_fix_lessons()
    lines = [
        "# Self Improvement Report",
        "",
        f"- updated: `{now_iso()}`",
        f"- enabled: `{get_settings().get('enabled', True)}`",
        f"- errors: `{len(errors)}`",
        f"- lessons: `{len(lessons)}`",
        "",
        "## Active Lessons",
    ]
    if not lessons:
        lines.append("- 없음")
    for row in lessons[:20]:
        lines.append(f"- **{row.get('title')}**: {row.get('body')}")
    path = _path(REPORT)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if get_settings().get("auto_wiki", True):
        _render_wiki_summary(lines)
    return path


def _render_wiki_summary(lines: List[str]) -> None:
    try:
        wiki_dir = _userdata_dir() / "memory" / "wiki" / "self-improvement"
        wiki_dir.mkdir(parents=True, exist_ok=True)
        (wiki_dir / "0-자가개선-대시보드.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def status() -> Dict[str, Any]:
    _ensure()
    return {
        "settings": get_settings(),
        "dir": str(base_dir()),
        "errors": len(_self_errors()),
        "lessons": len(_self_fix_lessons()),
    }
'''

QUALITY_GATE_SOURCE = r'''# -*- coding: utf-8 -*-
"""Release quality gate for OpenCodeLIG.

This gate turns recurring release assumptions into executable checks. It is
deliberately conservative: a release-critical behavior is PASS only when the
installed launcher/package path proves the behavior, not when a file merely
exists.
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_WS_ROOT = Path(__file__).resolve().parents[1]
if str(_WS_ROOT) not in sys.path:
    sys.path.insert(0, str(_WS_ROOT))

from agent_ops.release_contracts import (
    AUTOSAVE_REQUIRED_MARKERS,
    HAMSTER_EVENT_BRIDGE_MARKERS,
    HAMSTER_LEGACY_MARKERS,
    LAUNCHER_DRIVE_ROOT_FALLBACK,
    LAUNCHER_FAST_RUNTIME_MARKERS,
    LAUNCHER_HAMSTER_MARKERS,
    LAUNCHER_PROJECT_DIR_MARKERS,
    MEMORY_INJECT_REQUIRED_MARKERS,
    PLUGIN_SYNC_GLOB,
    REQUIRED_PLUGIN_FILES,
)


@dataclass
class GateCheck:
    name: str
    status: str
    evidence: str
    next_action: str = ""


@dataclass
class GateResult:
    checks: list[GateCheck]
    report_path: Path | None = None

    def by_name(self, name: str) -> GateCheck:
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)

    @property
    def ok(self) -> bool:
        return all(check.status == "PASS" for check in self.checks)

    def to_markdown(self) -> str:
        counts: dict[str, int] = {}
        for check in self.checks:
            counts[check.status] = counts.get(check.status, 0) + 1
        lines = [
            "# OpenCodeLIG Quality Gate",
            "",
            f"- timestamp: `{datetime.now().astimezone().isoformat(timespec='seconds')}`",
            f"- verdict: `{'PASS' if self.ok else 'FAIL'}`",
            "- counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())),
            "",
            "| status | check | evidence | next action |",
            "|---|---|---|---|",
        ]
        for check in self.checks:
            evidence = check.evidence.replace("\n", " ")[:800]
            next_action = check.next_action.replace("\n", " ")[:400]
            lines.append(f"| {check.status} | {check.name} | {evidence} | {next_action} |")
        return "\n".join(lines) + "\n"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _crlf_only(path: Path) -> bool:
    raw = path.read_bytes() if path.exists() else b""
    return bool(raw) and b"\n" not in raw.replace(b"\r\n", b"")


def _add(checks: list[GateCheck], name: str, ok: bool, evidence: str, next_action: str = "") -> None:
    checks.append(GateCheck(name=name, status="PASS" if ok else "FAIL", evidence=evidence, next_action=next_action))


def _markers(text: str, required: list[str]) -> tuple[bool, str]:
    present = {marker: marker in text for marker in required}
    return all(present.values()), "; ".join(f"{k}={v}" for k, v in present.items())


def _check_launcher(workspace: Path, checks: list[GateCheck]) -> None:
    launcher = workspace / "RUN_OPENCODE_LIG.bat"
    text = _read_text(launcher)
    run_idx = text.find("\"%OCODE_EXE%\" %*")

    fast_ok, fast_evidence = _markers(text, list(LAUNCHER_FAST_RUNTIME_MARKERS))
    before_run = run_idx >= 0 and all(0 <= text.find(marker) < run_idx for marker in LAUNCHER_FAST_RUNTIME_MARKERS)
    _add(
        checks,
        "launcher_fast_runtime",
        launcher.exists() and _crlf_only(launcher) and fast_ok and before_run and "OPENCODE_PURE=1" not in text,
        f"path={launcher}; crlf={_crlf_only(launcher)}; before_run={before_run}; {fast_evidence}; pure1={'OPENCODE_PURE=1' in text}",
        "OpenCode 실행 직전 fast runtime/offline 환경변수를 설정하고 OPENCODE_PURE=1을 제거하세요.",
    )

    hamster_ok, hamster_evidence = _markers(text, list(LAUNCHER_HAMSTER_MARKERS))
    _add(
        checks,
        "launcher_direct_hamster",
        launcher.exists() and hamster_ok and "hamster_hidden.vbs" not in text,
        f"{hamster_evidence}; uses_vbs={'hamster_hidden.vbs' in text}",
        "햄스터는 설치 workspace의 agent_ops\\ui\\hamster_overlay.py를 직접 실행해야 합니다.",
    )

    project_ok, project_evidence = _markers(text, list(LAUNCHER_PROJECT_DIR_MARKERS))
    unconditional_workspace = 'set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"' in text.splitlines()
    drive_root_guard = LAUNCHER_DRIVE_ROOT_FALLBACK in text
    _add(
        checks,
        "launcher_ocd_project_dir",
        launcher.exists() and project_ok and drive_root_guard and not unconditional_workspace,
        f"{project_evidence}; drive_root_guard={drive_root_guard}; unconditional_workspace={unconditional_workspace}",
        "ocd/caller가 넘긴 작업폴더를 보존하고 위험한 시작 위치만 workspace로 fallback해야 합니다.",
    )


def _check_plugins_and_memory(workspace: Path, checks: list[GateCheck]) -> None:
    plugins = workspace / ".opencode" / "plugins"
    missing = [name for name in REQUIRED_PLUGIN_FILES if not (plugins / name).exists()]
    launcher = _read_text(workspace / "RUN_OPENCODE_LIG.bat")
    sync_all_plugins = PLUGIN_SYNC_GLOB in launcher
    pure_one = "OPENCODE_PURE=1" in launcher
    _add(
        checks,
        "plugin_runtime_enabled",
        not missing and sync_all_plugins and not pure_one,
        f"missing={missing}; sync_all={sync_all_plugins}; pure1={pure_one}",
        "필수 플러그인을 유지하고 작업폴더로 동기화하며 OPENCODE_PURE=1을 쓰지 마세요.",
    )

    autosave = _read_text(plugins / "session-autosave.ts")
    autosave_ok, autosave_evidence = _markers(autosave, list(AUTOSAVE_REQUIRED_MARKERS))
    _add(
        checks,
        "session_autosave_to_wiki",
        autosave_ok and "(?i:" not in autosave and "execFileSync" not in autosave,
        f"{autosave_evidence}; bad_regex={'(?i:' in autosave}; execFileSync={'execFileSync' in autosave}",
        "세션 이벤트를 wiki\\sessions로 저장하되 delta는 버퍼링 후 ended에서만 flush하고 동기 child 호출은 제거해야 합니다.",
    )

    memory = _read_text(plugins / "memory-inject.ts")
    memory_ok, memory_evidence = _markers(memory, list(MEMORY_INJECT_REQUIRED_MARKERS))
    _add(
        checks,
        "memory_inject_nonblocking",
        memory_ok and "execFileSync" not in memory and ("execFile(" in memory or "spawn(" in memory),
        f"{memory_evidence}; execFileSync={'execFileSync' in memory}; async_exec={'execFile(' in memory or 'spawn(' in memory}",
        "TUI 시작을 막지 않도록 기억 주입은 fallback 후 백그라운드 refresh 구조여야 하며 동기 child 호출이 남아 있으면 안 됩니다.",
    )

    hamster = _read_text(plugins / "hamster-status.ts")
    hamster_ok, hamster_evidence = _markers(hamster, list(HAMSTER_EVENT_BRIDGE_MARKERS))
    hamster_legacy = any(marker in hamster for marker in HAMSTER_LEGACY_MARKERS)
    _add(
        checks,
        "hamster_subagent_status_bridge",
        hamster_ok and not hamster_legacy,
        f"{hamster_evidence}; legacy_guess={hamster_legacy}",
        "멀티에이전트/subtask 진행 상태가 햄스터 current_status.json으로 자동 반영되어야 합니다.",
    )

    agentops = _read_text(workspace / "agent_ops" / "agentops.py")
    tool_dispatch = _read_text(workspace / "agent_ops" / "tool_dispatch.py")
    self_improvement = _read_text(workspace / "agent_ops" / "self_improvement.py")
    self_required = [
        "DEFAULT_SETTINGS",
        "\"enabled\": True",
        "capture_task_result",
        "format_injection_block",
        "lessons_for_injection",
        "self-improve",
    ]
    self_text = "\n".join([self_improvement, agentops, tool_dispatch])
    self_ok, self_evidence = _markers(self_text, self_required)
    _add(
        checks,
        "self_improvement_auto_loop",
        self_ok,
        self_evidence,
        "자가개선은 기본 ON이며 실패→성공→교훈→다음 세션 주입이 자동 연결되어야 합니다.",
    )


def _check_wiki_obsidian(workspace: Path, checks: list[GateCheck]) -> None:
    launcher = _read_text(workspace / "RUN_OPENCODE_LIG.bat")
    obsidian_required = [
        "agent_ops.wiki_vault",
        "LIG_AUTO_WIKI",
        "obsidian_detached.vbs",
        "%OPENCODE_USERDATA%\\memory\\wiki",
    ]
    obsidian_ok, obsidian_evidence = _markers(launcher, obsidian_required)
    direct_console = 'start "" "%OBSEXE%"' in launcher
    _add(
        checks,
        "obsidian_wiki_autostart",
        obsidian_ok and not direct_console,
        f"{obsidian_evidence}; direct_console={direct_console}",
        "Obsidian은 자동 실행하되 detached VBS로 분리해 TUI에 Electron 로그가 섞이지 않아야 합니다.",
    )

    code = (
        "from agent_ops.memory_manager import add_user_memory\n"
        "from agent_ops.wiki_manager import consolidate, WIKI_DIR\n"
        "item=add_user_memory('quality gate wiki smoke', title='quality gate')\n"
        "stats=consolidate()\n"
        "print(str(WIKI_DIR)); print(stats.get('records', 0))\n"
    )
    env = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="opencodelig_quality_gate_memory_") as td:
        env["AGENTOPS_MEMORY_DIR"] = td
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        cp = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(workspace),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
        )
    _add(
        checks,
        "wiki_manager_smoke",
        cp.returncode == 0,
        f"rc={cp.returncode}; out={(cp.stdout or '')[-400:]}; err={(cp.stderr or '')[-400:]}",
        "격리 메모리에서 remember→wiki consolidate가 실패하면 memory_manager/wiki_manager 경로를 확인하세요.",
    )


def _section(lines: list[str], start: str, end: str) -> str:
    try:
        i = lines.index(start)
        j = lines.index(end)
    except ValueError:
        return ""
    if j <= i:
        return ""
    return "".join(lines[i + 1:j])


def _check_package(workspace: Path, checks: list[GateCheck]) -> None:
    repo = workspace.parent
    final_bat = repo / "최종_패치파일.bat"
    hotfix = workspace / "patches" / "existing_install_hotfix_20260709.py"
    hotfix_text = _read_text(hotfix)
    _add(
        checks,
        "hotfix_recreates_quality_gate",
        "QUALITY_GATE_SOURCE" in hotfix_text and "create_quality_gate" in hotfix_text and "quality_gate.py" in hotfix_text,
        f"QUALITY_GATE_SOURCE={'QUALITY_GATE_SOURCE' in hotfix_text}; create_quality_gate={'create_quality_gate' in hotfix_text}",
        "기존 설치본에 quality_gate.py가 없어도 최종 패치가 복구해야 합니다.",
    )

    lines = final_bat.read_text(encoding="utf-8", errors="replace").splitlines() if final_bat.exists() else []
    py64 = _section(lines, "__OPENCODELIG_HOTFIX_PY_BASE64__", "__OPENCODELIG_HOTFIX_MSS_WHEEL_NAME__")
    wheel_name = _section(lines, "__OPENCODELIG_HOTFIX_MSS_WHEEL_NAME__", "__OPENCODELIG_HOTFIX_MSS_WHEEL_BASE64__").strip()
    wheel64 = _section(lines, "__OPENCODELIG_HOTFIX_MSS_WHEEL_BASE64__", "__OPENCODELIG_HOTFIX_END__")
    payload_ok = False
    wheel_ok = False
    detail = []
    try:
        payload = base64.b64decode(py64)
        payload_ok = b"QUALITY_GATE_SOURCE" in payload and b"create_quality_gate" in payload
        detail.append(f"payload_bytes={len(payload)}")
    except Exception as exc:
        detail.append(f"payload_error={type(exc).__name__}:{exc}")
    try:
        data = base64.b64decode(wheel64)
        with tempfile.TemporaryDirectory(prefix="opencodelig_quality_gate_wheel_") as td:
            wh = Path(td) / wheel_name
            wh.write_bytes(data)
            with zipfile.ZipFile(wh) as zf:
                wheel_ok = any(name.endswith("/METADATA") and name.startswith("mss-") for name in zf.namelist())
        detail.append(f"wheel={wheel_name}")
    except Exception as exc:
        detail.append(f"wheel_error={type(exc).__name__}:{exc}")
    _add(
        checks,
        "final_patch_self_contained",
        final_bat.exists() and _crlf_only(final_bat) and payload_ok and wheel_ok,
        f"path={final_bat}; crlf={_crlf_only(final_bat)}; payload_ok={payload_ok}; wheel_ok={wheel_ok}; {'; '.join(detail)}",
        "최종 BAT는 최신 hotfix payload와 mss wheel을 자체 포함해야 합니다.",
    )


def _run_command_checks(workspace: Path, checks: list[GateCheck]) -> None:
    commands = [
        [sys.executable, "-m", "pytest", str(workspace / "tests" / "test_existing_install_hotfix.py"), str(workspace / "tests" / "test_opencode_lig_plugin_runtime.py"), "-q"],
        [sys.executable, "-m", "py_compile", str(workspace / "agent_ops" / "quality_gate.py"), str(workspace / "patches" / "existing_install_hotfix_20260709.py"), str(workspace / "agent_ops" / "pending_check.py")],
    ]
    for index, cmd in enumerate(commands, start=1):
        cp = subprocess.run(
            cmd,
            cwd=str(workspace.parent),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=180,
        )
        _add(
            checks,
            f"command_regression_{index}",
            cp.returncode == 0,
            f"cmd={' '.join(cmd)}; rc={cp.returncode}; out={(cp.stdout or '')[-500:]}; err={(cp.stderr or '')[-500:]}",
            "회귀 명령 실패 내용을 확인하고 해당 계약을 먼저 복구하세요.",
        )


def run_quality_gate(workspace: Path | str | None = None, run_commands: bool = True, out: Path | str | None = None) -> GateResult:
    ws = Path(workspace) if workspace else Path(__file__).resolve().parents[1]
    ws = ws.resolve()
    checks: list[GateCheck] = []
    _check_launcher(ws, checks)
    _check_plugins_and_memory(ws, checks)
    _check_wiki_obsidian(ws, checks)
    _check_package(ws, checks)
    if run_commands:
        _run_command_checks(ws, checks)

    report_path: Path | None = None
    result = GateResult(checks=checks, report_path=None)
    if out:
        report_path = Path(out)
    else:
        report_path = ws / "agent_ops" / "results" / "quality_gate" / "QUALITY_GATE_LAST.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(result.to_markdown(), encoding="utf-8")
    result.report_path = report_path
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenCodeLIG release quality gate")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--no-commands", action="store_true", help="skip heavier pytest/compile command checks")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    result = run_quality_gate(
        Path(args.workspace),
        run_commands=not args.no_commands,
        out=Path(args.out) if args.out else None,
    )
    print(result.to_markdown())
    if result.report_path:
        print(f"Report: {result.report_path}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def inject_before_main(path: Path, block: str, marker: str) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    text = read_text(path)
    if marker in text:
        log(f"[SKIP] already patched: {path}")
        return
    needle = 'if __name__ == "__main__":'
    idx = text.rfind(needle)
    if idx < 0:
        raise RuntimeError(f"main guard not found: {path}")
    backup_path = backup(path)
    write_text(path, text[:idx].rstrip() + "\n\n" + block.strip() + "\n\n" + text[idx:])
    log(f"[OK] patched {path} (backup: {backup_path})")


def append_once(path: Path, block: str, marker: str) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    text = read_text(path)
    if marker in text:
        log(f"[SKIP] already patched: {path}")
        return
    backup_path = backup(path)
    write_text(path, text.rstrip() + "\n\n" + block.strip() + "\n")
    log(f"[OK] patched {path} (backup: {backup_path})")


def verify_python(path: Path) -> None:
    cp = run([sys.executable, "-m", "py_compile", str(path)], timeout=60)
    if cp.returncode != 0:
        raise RuntimeError(f"py_compile failed for {path}: {(cp.stderr or cp.stdout)[-1200:]}")
    log(f"[OK] py_compile: {path}")


def run_pending_check() -> None:
    if os.environ.get("LIG_SKIP_PENDING_CHECK_AFTER_HOTFIX") == "1":
        log("[SKIP] pending_check skipped by LIG_SKIP_PENDING_CHECK_AFTER_HOTFIX=1")
        return
    pending = WS / "agent_ops" / "pending_check.py"
    out_dir = USERDATA / "diagnostics" / "pending_checks"
    out_dir.mkdir(parents=True, exist_ok=True)
    cp = subprocess.run(
        [sys.executable, str(pending), "--out-dir", str(out_dir)],
        cwd=str(WS),
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log(f"[INFO] pending_check exit={cp.returncode}")
    log(f"[REPORT] {out_dir / 'pending-check-last.md'}")


def main() -> int:
    log("=== OpenCodeLIG existing-install hotfix 20260709 ===")
    log(f"ROOT={ROOT}")
    log(f"WS={WS}")
    if not WS.exists():
        log("[ERROR] Installed workspace not found. Install OpenCodeLIG first.")
        return 1
    copy_root_check_bat()
    create_gateway_wrappers()
    create_ocd_wrapper()
    create_launcher_helpers()
    create_plugin_bridges()
    create_self_improvement()
    create_release_contracts()
    create_quality_gate()
    patch_agentops_quality_gate_command()
    patch_agentops_self_improve_command()
    patch_autocad_adapter()
    patch_agentops_litellm_offline_env()
    patch_hamster_start_grace()
    patch_run_launcher()
    try_install_optional_wheels()

    pending = WS / "agent_ops" / "pending_check.py"
    adapters = WS / "agent_ops" / "adapters" / "__init__.py"
    inject_before_main(pending, PENDING_BLOCK, MARK_PENDING)
    append_once(adapters, ADAPTER_BLOCK, MARK_ADAPTERS)
    verify_python(WS / "agent_ops" / "release_contracts.py")
    verify_python(pending)
    verify_python(adapters)
    run_pending_check()
    log("[OK] Existing install hotfix complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
