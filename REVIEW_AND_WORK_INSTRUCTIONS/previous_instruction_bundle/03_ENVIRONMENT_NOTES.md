# Environment notes for Claude Code

The actual implementation will be run on the user's home computer, not necessarily on the original company PC.

Known user/project context:

- Project: OpenCode AgentOps v3.1 self-maintenance/co-growth layer.
- Target OS: Windows 10/11.
- Target Python: Python 3.11.
- The user prefers `.bat.txt` files instead of raw `.bat` for transfer.
- Avoid self-contained base64 BAT payloads if possible. They are fragile and may trigger antivirus.
- No external dependency installation unless explicitly approved.
- OpenCode source itself is not included here.
- If OpenCode core patch is needed, do not implement it blindly. Write `REQUIRES_OPENCODE_SOURCE_PATCH.md`.

If the user runs this on a different project root, preserve relative paths.
