# OpenCodeLIG Complete Hamster Pet Overlay

## Complete version target

This is the Codex-pet style direction requested by the user.

The complete install ZIP includes:

- user's hamster image converted into transparent animation frames
- 3-frame animation per state
- always-on-top overlay
- drag-to-move
- saved/restored position
- double-click recent briefing
- right-click menu
- Windows tray icon with Show, Hide, Details, Exit

## Runtime states

- idle
- working
- done
- needs_user
- error
- stalled

## Run

```bat
launch\hamster.bat
```

## Test status

```bat
launch\hamster-test-status.bat
```

## Data sources

1. `%LIG_STATE_DIR%\current_status.json`
2. `%LIG_DIAG_DIR%\agent-loop-last.json`
3. `%LIG_DIAG_DIR%\tool-dispatch-last.json`
4. `%LIG_DIAG_DIR%\tool-dispatch-history.jsonl`

## Fable integration

See `docs/FABLE_HAMSTER_CONNECT_PROMPT.md`.

The intended architecture is:

```text
OpenCodeLIG core loop / tool dispatcher
        -> status_writer.py
current_status.json + events.ndjson
        -> hamster_overlay.py
        -> animated pet + tray + briefing
```

## Binary asset note

The complete install ZIP includes the real PNG and ICO hamster assets. Some connector flows can only write text files, so Fable should add those binary files through a normal git workflow or copy them from the complete install ZIP during final integration.
