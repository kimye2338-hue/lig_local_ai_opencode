import { readFileSync } from "fs"
import { join } from "path"

export const CompactionHandoff = async (ctx: any) => ({
  "experimental.session.compacting": async (_input: any, output: any) => {
    const base = ctx?.directory || ctx?.worktree?.path || process.cwd()
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
  },
})
