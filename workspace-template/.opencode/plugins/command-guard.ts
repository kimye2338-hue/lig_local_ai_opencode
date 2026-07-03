// AgentOps command guard - runs in OpenCode's tool.execute.before path.
// No external imports (offline / mangbunri safe).
//
// Design (v2, soft-block):
//   * Primary destructive-command defense now lives in native opencode.json
//     `permission.bash` deny patterns (see agent_ops/config/opencode.permission.example.json).
//     This plugin is a SECOND layer that catches things native permissions cannot
//     see: corrupted/leaked tool-call text and malformed heredocs.
//   * It NO LONGER blocks legitimate shell file-writes (echo>, printf>, cat<<EOF,
//     python -c). When the LIG model cannot emit native tool_calls, shell is the
//     agent's only fallback for writing files; blocking it caused AUTO to stall.
//   * When it must block, it throws ONE short line (not a multi-reason English
//     dump) so nothing floods the chat. The message tells the model the exact
//     recovery path; it is not shown as a final answer.

// Corruption: the "command" is actually leaked tool-call JSON / reasoning text,
// not a runnable command. Running it always fails, so block with a short hint.
const CORRUPTION_MARKERS = [
  'functions.bash(', "functions.write(", "<tool_call>", "</tool_call>",
  '"name":"bash"', '"name": "bash"', '"tool":"write"', '"tool": "write"',
  "the content contains", "let's write the file", "better to use write",
  "olbareun json",            // romanized "correct JSON" leak marker
]

// Genuinely destructive. Native permission deny is primary; this is defense-in-depth.
const DESTRUCTIVE = [
  /\brm\s+-[rf]{1,2}\b/i, /\bdel\s+\/[qsf]\b/i, /\brmdir\s+\/s\b/i, /\brd\s+\/s\b/i,
  /\bformat\s+[A-Za-z]:/i, /\bpowershell\b[^\n]*encodedcommand/i,
  /\b(curl|wget|iwr)\b[^\n]*\|\s*(bash|sh|python|iex|powershell)/i,
  /\bInvoke-Expression\b/i,
]

type Block = { kind: "corruption" | "destructive" | "malformed"; hint: string }

function inspect(cmd: string): Block | null {
  const lower = cmd.toLowerCase()

  for (const m of CORRUPTION_MARKERS) {
    if (lower.includes(m.toLowerCase()))
      return { kind: "corruption", hint: "This looks like leaked tool-call/JSON text, not a shell command. Call the write/edit tool directly, or run agent_ops/safe_file_writer.py." }
  }

  for (const re of DESTRUCTIVE) {
    if (re.test(cmd))
      return { kind: "destructive", hint: "Destructive command blocked by policy. If truly required, ask the user in one sentence." }
  }

  // Malformed heredoc: delimiter opened but never closed on its own line -> will hang/fail.
  const delims = [...cmd.matchAll(/<<\s*['"]?([A-Za-z0-9_]+)['"]?/g)].map((m) => m[1])
  for (const d of delims) {
    if (!new RegExp(`(?:^|\\n)${d}\\s*(?:\\n|$)`).test(cmd))
      return { kind: "malformed", hint: `Heredoc '${d}' is not closed on its own line. Use the write tool or agent_ops/safe_file_writer.py instead.` }
  }

  if (cmd.length > 8000)
    return { kind: "malformed", hint: "Command too long to run reliably; write a file with the write tool, then execute it." }

  return null
}

export const AgentOpsCommandGuard = async (_ctx: any) => ({
  "tool.execute.before": async (input: any, output: any) => {
    if (input?.tool !== "bash") return
    const cmd = String(output?.args?.command ?? "")
    if (!cmd.trim()) return
    const block = inspect(cmd)
    if (block) throw new Error(`AgentOps guard [${block.kind}]: ${block.hint}`)
  },
})
