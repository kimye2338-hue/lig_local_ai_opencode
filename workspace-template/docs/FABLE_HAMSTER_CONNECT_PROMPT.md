# Fable prompt: connect Hamster Pet Overlay to the existing OpenCodeLIG system

Read this repository and integrate the hamster pet overlay with the existing OpenCodeLIG runtime.

## Goal

The overlay already reads diagnostics, but it should be connected to the real agent lifecycle so it feels like a Codex-style pet.

## Required connections

1. Import `agent_ops.status_writer` from long-running agent paths.
2. On task start, call:

```python
publish_event("TASK_STARTED", status="working", task=<short task>, message="작업을 시작했습니다.")
```

3. Before each tool call, call:

```python
publish_event("TOOL_STARTED", status="working", task=<tool name>, message=f"{tool_name} 실행 중입니다.")
```

4. After each tool call:
   - success: `publish_event("TOOL_DONE", status="working", task=<tool name>, message="다음 단계를 진행 중입니다.")`
   - failure:
     - missing approval/user input: `status="needs_user"`
     - normal error: `status="error"`

5. On final completion:

```python
publish_event("TASK_DONE", status="done", task=<short task>, message=<final concise summary>)
```

6. On loop cutoff, repeated failure, max turns, or stalled condition:
   - `status="stalled"` when the agent appears stuck
   - `status="needs_user"` when user action or approval is required
   - `status="error"` for actual execution/LLM failures

7. Keep all status writes best-effort. Failure to write status must never break the agent.

## Files provided by the complete ZIP

- `agent_ops/ui/hamster_overlay.py`
- `agent_ops/status_writer.py`
- `agent_ops/ui/assets/hamster_pet/*.png`
- `launch/hamster.bat`
- `launch/hamster-test-status.bat`

## Important constraints

- Do not add self-extracting BAT payloads.
- Do not embed base64 ZIP payloads in BAT files.
- Keep installer/cmd files ASCII-only where possible.
- Keep the overlay separate from core logic; core logic only publishes status/events.
- Preserve restart/resume durability and existing diagnostics behavior.

## Expected user experience

- Hamster appears as an always-on-top pet while OpenCodeLIG works.
- User can drag it and its position is remembered.
- Tray icon can show/hide/details/exit.
- State changes use the matching 3-frame animation:
  - `done`
  - `needs_user`
  - `working`
  - `error`
  - `stalled`
  - `idle`
