// AgentOps command guard — runs in OpenCode's tool execution path.
// No external imports (offline / 망분리 safe).

const PROSE_MARKERS = [
  "the content contains", "let's write", "let's create", "better to use",
  "actually the content", "json error", "manual formatting",
  "use echo for each part",
]

// Common Korean words that show up legitimately inside quoted arguments
// (commit messages, file names, echoed text — e.g. `git commit -m "설명 추가"`).
// A single hit inside quotes is not enough evidence of prose leaking into the
// command, so these only block when they appear outside quotes or two+ show up
// together (a stronger dumped-prose signal). Mirrors command_guard.py.
const WEAK_PROSE_MARKERS = ["생략", "하려고", "설명", "대안", "생각"]

function stripQuoted(text: string): string {
  return text.replace(/"[^"]*"/g, "").replace(/'[^']*'/g, "")
}

const FAKE_TOOL_MARKERS = [
  'bash {"command"', "functions.bash(", "<tool_call>", '"name":"bash"', '"name": "bash"',
]

const WRITE_CODE = [
  /\bcat\s*>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b/i,
  /\bcat\s+<<\s*['"]?[A-Za-z0-9_]+['"]?/i,
  /<<\s*['"]?EOF['"]?/i,
  /\becho\b.+>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b/i,
  /\bprintf\b.+>\s*[^&|;]+?\.(py|js|ts|tsx|jsx|bat|cmd|ps1|json|yaml|yml|md)\b/i,
  /\bpython(?:3)?\s+-c\b/i,
  /\bpy\s+-3(?:\.\d+)?\s+-c\b/i,
]

const DANGEROUS = [
  /\brm\s+-rf\b/i, /\bdel\s+\/[qsf]\b/i, /\bdel\s+\S/i,
  /\brmdir\s+\/s\b/i, /\brd\s+\/s\b/i,
  /\bformat\s+[A-Za-z]:/i, /\bformat\b(?:\s+\/\S+)+\s+[A-Za-z]:/i,
  /\bpowershell\b.+encodedcommand/i,
  /\b(?:powershell|pwsh)\b.*\s-e(?:n?c?o?d?e?d?c?o?m?m?a?n?d?)?\b/is,
  /\bremove-item\b.*-(?:recurse|force)\b/is,
  /\bstop-computer\b/i,
  /\bshutdown\b(?=.*\s\/f\b)(?=.*\s\/[sr]\b)/is,
  /\bvssadmin\s+delete\s+shadows\b/i,
  /\bdiskpart\b/i,
  /\breg\s+delete\b.*\s\/f\b/is,
  /\bbcdedit\b/i,
  /\bwmic\b.*\bcall\s+create\b/is,
  /\btaskkill\b.*\s\/f\b/is,
  /\bcipher\b.*\/w/is,
  /\bnew-object\s+(?:system\.)?net\.webclient\b/i,
  /\bdownloadstring\b/i,
  /\b(?:iex|invoke-expression)\b.*\b(?:iwr|invoke-webrequest|wget|curl)\b/is,
  /\b(?:iwr|invoke-webrequest|wget|curl)\b.*\b(?:iex|invoke-expression)\b/is,
  /\bcurl\b.+\|\s*(bash|sh|python)/i, /\biwr\b.+\|\s*(iex|powershell)/i,
]

function reasonsFor(cmd: string): string[] {
  const lower = cmd.toLowerCase()
  const reasons: string[] = []
  for (const m of PROSE_MARKERS) if (lower.includes(m)) reasons.push(`prose/reasoning in command: ${m}`)
  const outsideQuotesLower = stripQuoted(cmd).toLowerCase()
  const weakHits = WEAK_PROSE_MARKERS.filter(m => lower.includes(m))
  for (const m of weakHits) {
    if (outsideQuotesLower.includes(m) || weakHits.length >= 2) reasons.push(`prose/reasoning in command: ${m}`)
  }
  for (const m of FAKE_TOOL_MARKERS) if (lower.includes(m.toLowerCase())) reasons.push(`fake tool-call text: ${m}`)
  for (const re of WRITE_CODE) if (re.test(cmd)) reasons.push("heredoc/cat/echo/printf/python -c writes a file; use write/apply_patch/safe_file_writer")
  for (const re of DANGEROUS) if (re.test(cmd)) reasons.push("dangerous destructive shell pattern")
  // unclosed heredoc: delimiter never appears alone on its own line
  const delims = [...cmd.matchAll(/<<\s*['"]?([A-Za-z0-9_]+)['"]?/g)].map(m => m[1])
  for (const d of delims) {
    const own = new RegExp(`(?:^|\\n)${d}\\s*(?:\\n|$)`)
    if (!own.test(cmd)) reasons.push(`heredoc delimiter ${d} not closed on its own line`)
  }
  if ((cmd.match(/"/g)?.length ?? 0) >= 6 && cmd.includes("<<")) reasons.push("many quotes inside heredoc; high escaping-failure risk")
  if (cmd.length > 4000) reasons.push("command too long; split into a real file + verification")
  return reasons
}

export const AgentOpsCommandGuard = async (_ctx: any) => ({
  "tool.execute.before": async (input: any, output: any) => {
    if (input?.tool !== "bash") return
    const cmd = String(output?.args?.command ?? "")
    const reasons = reasonsFor(cmd)
    if (reasons.length > 0) {
      throw new Error(
        "AgentOps command guard BLOCKED this command (corrupted/unsafe).\n- " +
        reasons.join("\n- ") +
        "\nUse OpenCode write / apply_patch, or: python agent_ops/safe_file_writer.py <target> --content-file <staging>."
      )
    }
  },
})
