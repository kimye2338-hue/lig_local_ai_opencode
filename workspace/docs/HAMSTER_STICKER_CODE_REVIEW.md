# Hamster Sticker Final Code Review

## Reviewed areas

- Launcher path detection uses the installed layout:
  - `OpenCodeLIG/bin`
  - `OpenCodeLIG/userdata`
  - `OpenCodeLIG/workspace`
- API env is loaded from `OpenCodeLIG/userdata/secrets/lig-api.env`.
- `LIG_API_ENV_FILE`, `LIG_STATE_DIR`, and `LIG_DIAG_DIR` are exported before OpenCode starts.
- Hamster starts through `hamster_hidden.vbs` + `pythonw`, so it should not create extra visible console windows.
- The pet has a Windows mutex. Duplicate launches should immediately exit.
- The pet defaults to the bottom-right corner.
- The pet close button hides the pet instead of exiting it.
- The pet watches `opencode.exe` and exits after OpenCode is gone.
- A 20-second startup grace was added so the pet does not exit before `opencode.exe` appears.
- The sticker UI removes the speech bubble and uses a compact status-label + hamster layout.
- The sprite loader dynamically loads every `state_N.png` frame and does not assume 3 frames.
- Animation uses ping-pong motion so multi-frame states look less robotic.

## Validation

- `python -m py_compile workspace/agent_ops/ui/hamster_overlay.py`
- Final ZIP contains launcher, VBS hidden launcher, Pythonw resolver, sticker assets, and status writer.

## Remaining real-PC check

The following still requires the user's Windows PC because Tk transparent-color and tray behavior are Windows-runtime dependent:

- transparent overlay rendering
- tray menu interaction
- exact taskbar/right-bottom positioning on multi-monitor setups
