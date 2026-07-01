# Next version change report - permission mode package

Date: 2026-07-01
Branch: codex/permission-mode-next-version

## What changed

### Permission command handling

- `/permission status`, `/permission ask`, `/permission auto`, and `/permission cycle` are still supported.
- `/perm status`, `/perm ask`, `/perm auto`, and `/perm cycle` now use the same direct TUI parser.
- Invalid permission actions now mention that `/perm` aliases are supported.

### AUTO reply handling

- AUTO mode still replies with `reply: "once"` only.
- Duplicate reply protection now tracks `props.request.id` instead of using one component-local boolean.
- This keeps repeated effects from replying twice to the same request while allowing a later permission request to be auto-approved.

### Artifact packaging

- The workflow now uploads the package directory instead of uploading a pre-built ZIP as the artifact payload.
- A downloaded GitHub artifact should expose the install files directly after one extraction.
- The workflow validates required package files before upload.

### SHA256 validation

- The workflow validates every listed `SHA256SUMS.txt` entry before uploading the artifact.
- The installer verifies `payload/opencode.exe` with Windows `certutil` before copying it into `%USERPROFILE%\OpenCodeLIG\bin`.

### Installer rollback safety

- If `%USERPROFILE%\OpenCodeLIG` already exists, the installer backs it up to `%USERPROFILE%\OpenCodeLIG_backup_%RANDOM%` before overwriting.
- This gives the user a simple rollback path if the new package does not behave as expected.

### Documentation

- The offline install README now explains the expected artifact extraction layout.
- It documents `Shift+Tab`, `Shift+F3`, `/permission`, and `/perm` behavior.
- It states that the installer does not clone GitHub and does not use PowerShell execution-policy bypass.

## User-visible improvements

- The user can type the shorter `/perm auto` or `/perm ask` command instead of needing the full `/permission ...` form.
- The downloaded artifact is easier to understand because install files are visible after one extraction instead of being hidden inside another ZIP.
- The installer now stops early if the executable checksum does not match, reducing the risk of installing a corrupted payload.
- Existing installs are backed up automatically, so trying the new version feels less risky.
- The README better matches the actual installation flow and includes the shifted previous-agent shortcut.

## Functional improvements

- Permission AUTO mode is more reliable for consecutive permission requests.
- The package verification step catches missing required files before upload.
- The SHA256 verification step catches mismatched package contents before upload.
- The binary selection step now fails if a Windows x64 `opencode.exe` is not found instead of silently falling back to a wrong candidate.
- Branch pushes under `codex/**` and pull requests now trigger the package workflow, making next-version validation easier.

## Remaining validation checklist

Before merging or using the next artifact on a company PC, verify:

- GitHub Actions package workflow passes on this branch or PR.
- `payload/opencode.exe --version` runs in the artifact verification step.
- Artifact extraction exposes `payload`, `workspace`, `SHA256SUMS.txt`, `README_OFFLINE_INSTALL.md`, and `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt` directly.
- Shift+Tab toggles `[PERM:ASK]` and `[PERM:AUTO]` without changing agent.
- Shift+F3 still changes to the previous agent.
- `/perm` and `/permission` command variants behave identically.
- AUTO mode replies `once` for multiple consecutive permission requests.
- ASK mode, reject, always, and subagent reject flows are unchanged.
- command guard and explicit deny behavior are not bypassed.
