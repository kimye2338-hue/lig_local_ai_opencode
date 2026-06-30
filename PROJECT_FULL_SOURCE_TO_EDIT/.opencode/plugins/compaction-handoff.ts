import { readFileSync } from "fs"

export const CompactionHandoff = async () => ({
  "experimental.session.compacting": async (_input: any, output: any) => {
    let handoff = ""
    try {
      handoff = readFileSync("agent_ops/state/COMPACT_HANDOFF.md", "utf-8")
    } catch {}
    output.prompt = [
      "Summarize the session. Preserve all durable state references below.",
      "After compaction, your FIRST action MUST be to read these files:",
      "agent_ops/state/COMPACT_HANDOFF.md",
      "agent_ops/state/RESUME_PLAN.md",
      "agent_ops/state/ACTIVE_TASK.json",
      "agent_ops/state/CHECKPOINT.json",
      "",
      "CRITICAL: items under next_step, planned action, or queue are PLANNED, not approved.",
      "Do not perform any risk:review_required action without explicit user approval in this current session.",
      "",
      "=== DURABLE HANDOFF ===",
      handoff,
    ].join("\n")
  },
})
