export * as PermissionMode from "./mode"

/**
 * Claude-Code-like session permission mode.
 *
 * This module is intentionally dependency-light and side-effect free so it can
 * be unit tested in isolation and reused by the PermissionV2 resolver, the
 * server routes, and (conceptually) the TUI.
 *
 * The mode is SESSION-LEVEL runtime state. It does NOT change the active
 * agent/persona; it only overlays the permission decision produced by the
 * normal OpenCode resolver.
 */

export type Mode = "normal" | "plan" | "auto"

/** Permission effect, mirrors `Permission.Effect` from @opencode-ai/schema. */
export type Effect = "allow" | "deny" | "ask"

export const DEFAULT: Mode = "normal"

/** Cycle order: NORMAL -> AUTO -> PLAN -> NORMAL (matches Claude Code feel). */
export const ORDER: readonly Mode[] = ["normal", "auto", "plan"]

export function isMode(value: unknown): value is Mode {
  return value === "normal" || value === "plan" || value === "auto"
}

export function parse(value: unknown): Mode | undefined {
  if (typeof value !== "string") return undefined
  const v = value.trim().toLowerCase()
  return isMode(v) ? v : undefined
}

export function cycle(mode: Mode): Mode {
  const i = ORDER.indexOf(mode)
  return ORDER[(i + 1) % ORDER.length]
}

export function label(mode: Mode): string {
  return mode.toUpperCase()
}

// ---------------------------------------------------------------------------
// Action categories (based on OpenCode tool `action` strings).
// ---------------------------------------------------------------------------

const READ_ACTIONS = new Set(["read", "glob", "grep", "list", "ls", "lsp", "todoread", "todowrite", "question"])
const EDIT_ACTIONS = new Set(["edit", "write", "apply_patch", "patch"])
const NETWORK_ACTIONS = new Set(["webfetch", "websearch", "fetch", "web"])
const EXTERNAL_ACTIONS = new Set(["external_directory"])

function categoryOf(action: string): "read" | "edit" | "network" | "external" | "bash" | "other" {
  const a = action.toLowerCase()
  if (a === "bash") return "bash"
  if (EXTERNAL_ACTIONS.has(a)) return "external"
  if (EDIT_ACTIONS.has(a)) return "edit"
  if (NETWORK_ACTIONS.has(a)) return "network"
  if (READ_ACTIONS.has(a)) return "read"
  return "other"
}

// ---------------------------------------------------------------------------
// Command guard — dangerous / corrupted bash. Blocks in ALL modes (incl AUTO).
// ---------------------------------------------------------------------------

export interface GuardResult {
  readonly blocked: boolean
  readonly reason?: string
}

const SAFE: GuardResult = { blocked: false }
const block = (reason: string): GuardResult => ({ blocked: true, reason })

const DANGEROUS: ReadonlyArray<readonly [RegExp, string]> = [
  // Destructive filesystem
  [/\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r|--recursive\s+--force|--force\s+--recursive)\b/i, "recursive force delete (rm -rf)"],
  [/\brm\s+-[a-z]*\s+\/(?:\s|$|\*)/i, "rm targeting filesystem root"],
  [/\bdel\s+\/[sq]/i, "Windows recursive delete (del /s)"],
  [/\b(rmdir|rd)\s+\/s/i, "Windows recursive rmdir (/s)"],
  [/\bformat\s+[a-z]:/i, "drive format"],
  [/\bmkfs\b/i, "filesystem format (mkfs)"],
  [/\bdd\s+.*\bof=\/dev\//i, "raw device write (dd of=/dev/...)"],
  [/>\s*\/dev\/sd[a-z]/i, "raw write to block device"],
  [/:\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:/, "fork bomb"],

  // Remote-code execution (curl|bash, iwr|iex)
  [/\b(curl|wget)\b[^\n]*\|\s*(sudo\s+)?(ba)?sh\b/i, "pipe download into shell (curl|bash)"],
  [/\b(iwr|invoke-webrequest)\b[^\n]*\|\s*(iex|invoke-expression)\b/i, "PowerShell download|iex"],
  [/\bpowershell\b[^\n]*-e(nc(odedcommand)?)?\b/i, "PowerShell EncodedCommand"],

  // "Corrupted" file-generation-via-bash anti-patterns (model should use edit/write tools)
  [/\bcat\s*>>?\s*\S/i, "file generation via `cat >` (use the write/edit tool)"],
  [/<<-?\s*['"]?\w*EOF\w*/i, "heredoc file generation (use the write/edit tool)"],
  [/<<-?\s*['"]?[A-Z_]{2,}\b/, "heredoc file generation (use the write/edit tool)"],
  [/\b(echo|printf)\b[^\n|]*>>?\s*\S/i, "file generation via echo/printf redirect (use the write/edit tool)"],
  [/\b(python3?|py)\b\s+-c\b[^\n]*(open\s*\([^)]*['"][wa]['"]|>\s*\S)/i, "python -c file creation (use the write/edit tool)"],
  [/\btee\s+(-a\s+)?\S/i, "file generation via tee (use the write/edit tool)"],

  // Fake tool-call / prose-mixed-into-command
  [/```/, "markdown fence inside a shell command (corrupted command)"],
  [/<\/?(function_calls|invoke|antml:|tool_call|parameter)\b/i, "tool-call markup inside a shell command"],

  // Credential / OTP / cookie / token extraction
  [/(\.aws\/credentials|\.ssh\/id_(rsa|ed25519|ecdsa|dsa)|\.netrc|\.npmrc|\.docker\/config\.json)\b/i, "credential file access"],
  [/\bsecurity\s+find-(generic|internet)-password\b/i, "macOS keychain credential extraction"],
  [/\bcookies?\.sqlite\b|\bLogin Data\b|\bCookies\b.*\.(db|sqlite)/i, "browser cookie extraction"],
  [/\b(otp|2fa|totp|mfa)[-_ ]?(secret|code|token)\b/i, "OTP/2FA secret extraction"],
  [/\b(printenv|env)\b[^\n]*\|\s*(curl|wget|nc|ncat|netcat)\b/i, "environment exfiltration over network"],
  [/\b(cat|grep|rg)\b[^\n]*\b(secret|token|api[_-]?key|password|credential)s?\b[^\n]*\|\s*(curl|wget|nc)\b/i, "secret exfiltration over network"],
]

export function commandGuard(command: string): GuardResult {
  if (typeof command !== "string") return SAFE
  const cmd = command
  for (const [re, reason] of DANGEROUS) {
    if (re.test(cmd)) return block(reason)
  }
  return SAFE
}

// ---------------------------------------------------------------------------
// Safe-bash allowlist — AUTO may upgrade ask -> allow only for these.
// Conservative on purpose: false negatives only cost an extra prompt.
// ---------------------------------------------------------------------------

const SAFE_BASH_LEADERS = new Set([
  "ls", "pwd", "cat", "head", "tail", "wc", "grep", "rg", "find", "which",
  "echo", "true", "date", "whoami", "uname", "stat", "file", "tree", "du", "df",
  "node", "tsc", "tsgo", "jq", "diff", "cmp", "basename", "dirname", "realpath",
])

const SAFE_GIT_SUB = new Set(["status", "diff", "log", "branch", "show", "rev-parse", "remote", "describe", "ls-files", "blame"])
const SAFE_PKG_SUB = new Set(["test", "typecheck", "lint", "run", "x"])
const SAFE_PKG_RUN_SCRIPT = new Set(["test", "typecheck", "lint", "build", "check"])

// Operators that introduce side effects / chaining / redirection / network.
const UNSAFE_OPERATORS = /[>;`]|\|\||&&|\$\(|\bsudo\b|\bnc\b|\bcurl\b|\bwget\b|\bssh\b|\bscp\b|\brsync\b|\bnpm\s+publish\b|\bgit\s+push\b/i

export function safeBash(command: string): boolean {
  if (typeof command !== "string") return false
  const cmd = command.trim()
  if (!cmd) return false
  if (commandGuard(cmd).blocked) return false
  if (UNSAFE_OPERATORS.test(cmd)) return false
  // single bare pipe between read-only commands is tolerated; reject any redirection already handled above.
  const segments = cmd.split("|").map((s) => s.trim()).filter(Boolean)
  return segments.every(isSafeSegment)
}

function isSafeSegment(seg: string): boolean {
  const tokens = seg.split(/\s+/)
  const leader = (tokens[0] ?? "").toLowerCase()
  if (SAFE_BASH_LEADERS.has(leader)) return true
  if (leader === "git") return SAFE_GIT_SUB.has((tokens[1] ?? "").toLowerCase())
  if (leader === "bun" || leader === "npm" || leader === "pnpm" || leader === "yarn") {
    const sub = (tokens[1] ?? "").toLowerCase()
    if (!SAFE_PKG_SUB.has(sub)) return false
    if (sub === "run") return SAFE_PKG_RUN_SCRIPT.has((tokens[2] ?? "").toLowerCase())
    return true
  }
  return false
}

// ---------------------------------------------------------------------------
// Overlay — apply the mode on top of the base resolver decision.
//
// Invariants:
//   - explicit `deny` from the base resolver is NEVER weakened.
//   - the command guard (applied by the caller) is NEVER weakened.
//   - PLAN only makes mutations stricter (allow -> ask/deny).
//   - AUTO only upgrades `ask` -> `allow` for bounded, safe, project-local ops.
//   - NORMAL is a no-op.
// ---------------------------------------------------------------------------

export function overlay(base: Effect, mode: Mode, action: string, command?: string): Effect {
  if (mode === "normal") return base
  if (base === "deny") return "deny"

  const cat = categoryOf(action)

  if (mode === "plan") {
    switch (cat) {
      case "read":
        return "allow"
      case "edit":
        return "ask"
      case "external":
        return "deny"
      case "network":
        // deny unless config already granted allow
        return base === "allow" ? "allow" : "deny"
      case "bash":
        return "ask"
      default:
        // unknown / potentially mutating action: never auto-allow in plan
        return base === "allow" ? "ask" : base
    }
  }

  // mode === "auto"
  switch (cat) {
    case "read":
      return "allow"
    case "edit":
      // project-local edit (external edits use the `external_directory` action)
      return base === "ask" ? "allow" : base
    case "external":
      return "deny"
    case "network":
      // do not auto-open network beyond config
      return base
    case "bash":
      if (base === "allow") return "allow"
      if (base === "ask") return safeBash(command ?? "") ? "allow" : "ask"
      return base
    default:
      // unknown action (submit/delete/send/upload/download style): keep base,
      // never auto-allow.
      return base
  }
}
