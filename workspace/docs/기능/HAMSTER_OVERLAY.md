# OpenCodeLIG Hamster Overlay

A small always-on-top desktop companion for OpenCodeLIG. It shows a beige hamster-style character and a speech bubble while you work in other windows.

## What it does

- Watches OpenCodeLIG state/diagnostic files.
- Shows a topmost hamster overlay.
- Briefs the current state as one of:
  - `대기 중`
  - `작업 중`
  - `완료`
  - `확인 필요`
  - `오류`
  - `멈춤 의심`
- Distinguishes OpenCode model output, tool execution, and native
  subagent/task work through the `hamster-status.ts` plugin.
- Double-click the hamster to see recent events.
- Right-click the hamster for details, refresh, or close.
- Drag the hamster with the left mouse button to move it.

## Why it is implemented separately

The overlay is intentionally separate from the OpenCode runtime. OpenCode writes diagnostics as usual, and the hamster reads those files. This keeps the core agent loop low-risk and avoids breaking the terminal UI.

The first implementation reads, in order:

1. `%LIG_STATE_DIR%\current_status.json` when available
2. `%LIG_DIAG_DIR%\agent-loop-last.json`
3. `%LIG_DIAG_DIR%\tool-dispatch-last.json`
4. `%LIG_DIAG_DIR%\tool-dispatch-history.jsonl` for the detail view

Default paths:

```bat
%USERPROFILE%\OpenCodeLIG_USERDATA\state
%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
```

## How to run

From the installed workspace:

```bat
launch\hamster.bat
```

Keep it open while using OpenCodeLIG. It can run even when OpenCode itself is not focused.

## Character asset policy

No external stock image is bundled. The hamster is drawn procedurally with Tkinter canvas shapes so the offline/company bundle does not depend on copyrighted image files or remote downloads.

The intended visual direction is a simple beige real-hamster companion rather than a copied photo.

## OpenCode subagent/task status

The overlay does not patch the OpenCode TUI. Instead, the OpenCode plugin
`workspace\.opencode\plugins\hamster-status.ts` listens to session/tool/task
events and writes `%LIG_STATE_DIR%\current_status.json`.

For native OpenCode subagents and tasks, the plugin treats task/subagent start
events as `working` and task/subagent end events as `done`. It also appends
event type names to `%LIG_DIAG_DIR%\opencode-event-types.log` so future OpenCode
event-name changes can be diagnosed without storing chat content or secrets.

If `working` stays stale for too long, the overlay displays `멈춤 의심`.

## Next upgrade path

For stronger live progress, add explicit status publishing in long-running agent paths:

```json
{
  "status": "working",
  "task": "browser automation patch",
  "message": "테스트 실행 중입니다.",
  "needs_user": false,
  "last_update": "2026-07-05T18:00:00+09:00"
}
```

Write that JSON to `%LIG_STATE_DIR%\current_status.json`, and append important events to `%LIG_STATE_DIR%\events.ndjson`.
