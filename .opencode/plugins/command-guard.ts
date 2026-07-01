/**
 * AgentOps command guard (defense-in-depth).
 *
 * This plugin blocks dangerous / "corrupted" bash commands BEFORE execution. It
 * works with stock (unpatched) OpenCode via the `tool.execute.before` hook, and
 * it mirrors the guard built into the patched core resolver
 * (`packages/core/src/permission/mode.ts`). Keep both: the core guard is the
 * authoritative pre-approval chokepoint; this plugin is a second layer that
 * also catches commands on installs that do not have the core patch.
 *
 * It is active in ALL permission modes, including AUTO. AUTO must never become
 * "dangerously-skip-permissions".
 *
 * Drop this file in `.opencode/plugins/` (project) or `~/.config/opencode/
 * plugins/` (global). See https://opencode.ai/docs/plugins.
 */
import type { Plugin } from "@opencode-ai/plugin"

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

  // Remote code execution
  [/\b(curl|wget)\b[^\n]*\|\s*(sudo\s+)?(ba)?sh\b/i, "pipe download into shell (curl|bash)"],
  [/\b(iwr|invoke-webrequest)\b[^\n]*\|\s*(iex|invoke-expression)\b/i, "PowerShell download|iex"],
  [/\bpowershell\b[^\n]*-e(nc(odedcommand)?)?\b/i, "PowerShell EncodedCommand"],

  // "Corrupted" file-generation-via-bash anti-patterns (use the write/edit tool)
  [/\bcat\s*>>?\s*\S/i, "file generation via `cat >`"],
  [/<<-?\s*['"]?\w*EOF\w*/i, "heredoc file generation"],
  [/<<-?\s*['"]?[A-Z_]{2,}\b/, "heredoc file generation"],
  [/\b(echo|printf)\b[^\n|]*>>?\s*\S/i, "file generation via echo/printf redirect"],
  [/\b(python3?|py)\b\s+-c\b[^\n]*(open\s*\([^)]*['"][wa]['"]|>\s*\S)/i, "python -c file creation"],
  [/\btee\s+(-a\s+)?\S/i, "file generation via tee"],

  // Fake tool-call / prose mixed into command
  [/```/, "markdown fence inside a shell command"],
  [/<\/?(function_calls|invoke|antml:|tool_call|parameter)\b/i, "tool-call markup inside a shell command"],

  // Credential / OTP / cookie / token extraction
  [/(\.aws\/credentials|\.ssh\/id_(rsa|ed25519|ecdsa|dsa)|\.netrc|\.npmrc|\.docker\/config\.json)\b/i, "credential file access"],
  [/\bsecurity\s+find-(generic|internet)-password\b/i, "macOS keychain credential extraction"],
  [/\bcookies?\.sqlite\b|\bLogin Data\b|\bCookies\b.*\.(db|sqlite)/i, "browser cookie extraction"],
  [/\b(otp|2fa|totp|mfa)[-_ ]?(secret|code|token)\b/i, "OTP/2FA secret extraction"],
  [/\b(printenv|env)\b[^\n]*\|\s*(curl|wget|nc|ncat|netcat)\b/i, "environment exfiltration over network"],
  [/\b(cat|grep|rg)\b[^\n]*\b(secret|token|api[_-]?key|password|credential)s?\b[^\n]*\|\s*(curl|wget|nc)\b/i, "secret exfiltration over network"],
]

function inspect(command: string): string | undefined {
  if (typeof command !== "string") return undefined
  for (const [re, reason] of DANGEROUS) if (re.test(command)) return reason
  return undefined
}

export const CommandGuardPlugin: Plugin = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "bash") return
      const command: unknown = output?.args?.command
      if (typeof command !== "string") return
      const reason = inspect(command)
      if (reason) {
        throw new Error(`[command-guard] Blocked dangerous command (${reason}). ` + `Use the write/edit tools for file changes; this command was not executed.`)
      }
    },
  }
}

export default CommandGuardPlugin
