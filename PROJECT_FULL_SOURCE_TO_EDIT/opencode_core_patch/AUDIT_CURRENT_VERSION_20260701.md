# Current version audit - permission mode patched OpenCode

Audit date: 2026-07-01
Repository: kimye2338-hue/lig_local_ai_opencode
Reviewed workflow run: https://github.com/kimye2338-hue/lig_local_ai_opencode/actions/runs/28494990662
Artifact: LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE
Artifact ID: 8000706677
Artifact digest: sha256:14f4f9ba4144f5879fd5e2c49fefb0371ec415bf62baf50f057bfd75129f82b3
Upstream OpenCode commit: afff74eb2c9fc3808a9795f365707f32853099e9

## Final audit decision for the previous artifact

Decision: PASS_WITH_MINOR_FIXES_REQUIRED

The previous artifact built successfully and the patch matched the main functional intent: Shift+Tab was moved from agent reverse cycling to permission ASK/AUTO cycling, the prompt badge was added, `/permission` commands were added, and AUTO used `reply: "once"` instead of `reply: "always"`.

The build evidence was strong for static and packaging validation:

- upstream commit was pinned
- `git apply --recount --check` succeeded
- `bun install` succeeded
- typecheck succeeded
- Windows binary build succeeded
- `payload/opencode.exe` existed in the package verification step
- `opencode.exe --version` returned `0.0.0--202607010513`

The previous artifact still needed minor fixes before being called optimal for company PC use.

## Findings from the previous version

### 1. `/perm` alias was registered but not fully implemented for subcommands

The app command registered `slashAliases: ["perm"]`, but the direct prompt parser only matched `/permission ...`:

```ts
const permissionCommand = inputText.trim().match(/^\/permission(?:\s+(\S+))?\s*$/i)
```

Impact: `/permission ask`, `/permission auto`, `/permission cycle`, and `/permission status` worked by code inspection, but `/perm ask`, `/perm auto`, `/perm cycle`, and `/perm status` were not guaranteed to follow the same local parser path.

Required fix: accept both `/permission` and `/perm` in the same parser.

### 2. AUTO duplicate-reply guard was component-local, not request-id based

The previous implementation used one boolean:

```ts
let autoReplied = false
```

Impact: this prevents duplicate reply for one mounted prompt, but if the component instance receives a new `props.request.id` without remounting, AUTO mode could skip the next permission request.

Required fix: track the replied request id, not only a boolean.

### 3. GitHub artifact download produced a ZIP containing another package ZIP

The workflow assembled `LIG_OPENCODE_PATCHED_OFFLINE_PACKAGE.zip` and uploaded that file as the artifact path. GitHub artifact downloads are themselves ZIP archives, so the downloaded artifact contained an inner ZIP instead of the install files directly.

Impact: non-developer users could extract the artifact once and not see `payload/opencode.exe`, `SHA256SUMS.txt`, and the installer at the expected level.

Required fix: upload the package directory rather than the pre-compressed ZIP.

### 4. Installer did not verify payload checksum before copying

`SHA256SUMS.txt` was generated, but the installer did not check `payload/opencode.exe` against it before installing.

Impact: checksum existed but was not part of the normal install path.

Required fix: installer should verify `payload/opencode.exe` with `certutil` before copying.

### 5. Installer overwrote an existing `%USERPROFILE%\OpenCodeLIG` without backup

The previous installer copied over the target location directly.

Impact: rollback was harder if an existing company PC installation already existed.

Required fix: back up the existing install directory before overwrite.

## Next-version remediation summary

This branch addresses the audit findings with the following changes:

- `/perm` now uses the same direct parser as `/permission`.
- AUTO reply duplicate protection is based on `props.request.id`.
- The workflow uploads the package directory, avoiding the ZIP-inside-ZIP artifact layout.
- The workflow validates required package files and validates all `SHA256SUMS.txt` entries.
- The installer verifies `payload/opencode.exe` checksum before copying.
- The installer backs up existing `%USERPROFILE%\OpenCodeLIG` before overwrite.
- The README documents `/perm`, `Shift+F3`, checksum behavior, backup behavior, and the expected artifact extraction layout.

## Validation still required after the next build

The next GitHub Actions run should be checked for:

- `git apply --recount --check` success
- typecheck success
- Windows binary build success
- package required-file validation success
- SHA256SUMS validation success
- artifact contents showing install files directly, not only an inner ZIP

Runtime/manual validation should still confirm:

- Shift+Tab toggles ASK to AUTO
- Shift+Tab toggles AUTO to ASK
- Shift+Tab does not change agent/persona/model/workflow
- Shift+F3 performs previous-agent cycling
- `/permission status`, `/permission ask`, `/permission auto`, `/permission cycle`
- `/perm status`, `/perm ask`, `/perm auto`, `/perm cycle`
- AUTO replies `once` for consecutive permission requests
- ASK mode keeps the existing prompt UI
- reject/always/subagent reject flows still work
- explicit deny and command guard blocks are not bypassed
