# Fable prompt: connect Hamster Pet Overlay to OpenCodeLIG

Integrate the hamster pet overlay with the existing OpenCodeLIG runtime.

Goal: make the pet reflect the real agent lifecycle, not only diagnostic-file inference.

Required lifecycle events:

- task start: write working status
- each tool start: write working status with tool name
- each tool success: append event and keep working status
- approval or user input needed: write needs_user status
- execution error: write error status
- repeated failure, timeout, or no progress: write stalled status
- final completion: write done status with concise result summary

Use `agent_ops.status_writer.publish_status` and `agent_ops.status_writer.publish_event` from long-running agent paths. All writes must be best-effort and must never break the agent.

Keep the overlay separate from the core loop. Core logic should only publish status and events. The overlay should continue to read:

- `%LIG_STATE_DIR%\current_status.json`
- `%LIG_STATE_DIR%\events.ndjson`
- `%LIG_DIAG_DIR%\agent-loop-last.json`
- `%LIG_DIAG_DIR%\tool-dispatch-last.json`
- `%LIG_DIAG_DIR%\tool-dispatch-history.jsonl`

Complete package handoff:

- ZIP: `OpenCodeLIG_Complete_Hamster_Pet_Overlay_20260705.zip`
- SHA256: `ce1a5565f2831bd819b6c65c898424065b5ec7e366368d136f2d31e627654f29`

That ZIP contains the full Windows overlay implementation plus binary PNG/ICO assets extracted from the user-provided hamster image. Add those binary assets through normal git or by copying from the ZIP.

Constraints:

- no self-extracting BAT
- no base64 ZIP payload inside BAT
- keep cmd installers ASCII-only where possible
- preserve restart/resume durability and existing diagnostics behavior
