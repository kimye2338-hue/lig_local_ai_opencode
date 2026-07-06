# LIG OpenCode patched offline package

This package contains a Windows OpenCode binary built from upstream OpenCode with the LIG permission approval controller patch applied.

Install on the offline company PC:

1. Download the `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE` artifact from GitHub Actions.
2. Extract the downloaded artifact ZIP. The extracted folder should contain `payload`, `workspace`, `SHA256SUMS.txt`, and `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt` directly.
3. Rename `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt` to `INSTALL_OFFLINE_LIG_OPENCODE.bat`.
4. Run it.
5. Start OpenCode with `%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat`.
6. Verify with `%USERPROFILE%\OpenCodeLIG\workspace\VERIFY_OFFLINE_INSTALL.bat`.

The installer checks the `payload/opencode.exe` SHA256 before copying files. If `%USERPROFILE%\OpenCodeLIG` already exists, it backs it up before overwriting.

Permission approval control:

- `Shift+Tab` toggles `[PERM:ASK]` / `[PERM:AUTO]`.
- `Shift+F3` is the previous-agent shortcut.
- `/permission status`, `/permission auto`, `/permission ask`, `/permission cycle`.
- `/perm status`, `/perm auto`, `/perm ask`, `/perm cycle`.

The installer uses local files only. It does not clone GitHub and does not use PowerShell execution-policy bypass.
