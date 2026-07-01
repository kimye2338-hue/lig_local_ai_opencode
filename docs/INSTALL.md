# Offline install guide

Use the latest successful `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE` artifact from the `Build LIG OpenCode offline package` workflow.

## Steps

1. Download the artifact from GitHub Actions.
2. Extract the artifact ZIP once.
3. Confirm the extracted folder directly contains:
   - `payload/`
   - `workspace/`
   - `SHA256SUMS.txt`
   - `README_OFFLINE_INSTALL.md`
   - `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt`
4. Rename `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt` to `INSTALL_OFFLINE_LIG_OPENCODE.bat`.
5. Run `INSTALL_OFFLINE_LIG_OPENCODE.bat` on the offline Windows PC.
6. Start OpenCode with:

```cmd
%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat
```

7. Verify with:

```cmd
%USERPROFILE%\OpenCodeLIG\workspace\VERIFY_OFFLINE_INSTALL.bat
```

## What the installer does

- Verifies `payload/opencode.exe` against `SHA256SUMS.txt` using Windows `certutil`.
- Copies the executable to `%USERPROFILE%\OpenCodeLIG\bin\opencode.exe`.
- Copies the workspace to `%USERPROFILE%\OpenCodeLIG\workspace`.
- Creates `RUN_OPENCODE_LIG.bat` and `VERIFY_OFFLINE_INSTALL.bat` in the installed workspace.
- Backs up an existing `%USERPROFILE%\OpenCodeLIG` to `%USERPROFILE%\OpenCodeLIG_backup_%RANDOM%` before overwriting.

## Offline constraints

The installer should not:

- clone GitHub
- run npm, bun, or git on the company PC
- download from the internet
- run PowerShell execution-policy bypass
- unpack base64 payloads from BAT files

## First runtime checks

Inside OpenCode:

- Press `Shift+Tab`; the permission badge should switch ASK/AUTO.
- Run `/permission status`.
- Run `/perm status`.
- Ask OpenCode to do a simple local task and confirm the UI does not crash with `unknown component type spinner`.
