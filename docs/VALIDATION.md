# Validation checklist

Use this checklist before distributing a new artifact broadly.

## GitHub Actions validation

Required workflow: `Build LIG OpenCode offline package`

Must pass:

- clone pinned upstream OpenCode commit
- `git apply --recount --check`
- `git apply --recount`
- `bun install`
- `bun run --cwd packages/opencode typecheck`
- Windows binary build
- locate Windows x64 `opencode.exe`
- assemble offline package
- required-file checks
- full `SHA256SUMS.txt` verification
- upload artifact with hidden files included

## Artifact download validation

After downloading the artifact:

- Extract once; no inner package ZIP should be required.
- Confirm top-level files/folders:
  - `payload/`
  - `workspace/`
  - `SHA256SUMS.txt`
  - `README_OFFLINE_INSTALL.md`
  - `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt`
- Confirm hidden workspace files exist:
  - `workspace/.opencode/commands/permission.md`
  - `workspace/.opencode/commands/agentmode.md`
  - `workspace/.opencode/agents/agentops-supervisor.md`
  - `workspace/.opencode/plugins/command-guard.ts`
- Confirm context files exist:
  - `workspace/docs/AI_HANDOFF.md`
  - `workspace/patches/opencode-permission-mode-toggle.patch`
- Verify all hashes in `SHA256SUMS.txt`.
- Run `payload/opencode.exe --version`.

## Windows runtime validation

On the target Windows PC:

- Run `VERIFY_OFFLINE_INSTALL.bat`.
- Start OpenCode through `RUN_OPENCODE_LIG.bat`.
- Confirm the TUI opens without crash.
- Ask OpenCode to do a simple local read-only task.
- Confirm no `reconciler unknown component type spinner` crash.
- Press `Shift+Tab`; permission badge toggles ASK/AUTO.
- Press `Shift+Tab` again; permission badge toggles back.
- Confirm `Shift+Tab` does not change the agent/persona/model/workflow.
- Press `Shift+F3`; previous-agent behavior still works.
- Run `/permission status`.
- Run `/permission ask`.
- Run `/permission auto`.
- Run `/permission cycle`.
- Run `/perm status`.
- Run `/perm ask`.
- Run `/perm auto`.
- Run `/perm cycle`.

## Permission safety validation

- ASK mode still shows the normal permission prompt.
- AUTO mode replies with once-only approval for permission prompts that reach the TUI.
- AUTO handles consecutive permission prompts once each.
- Reject flow still works.
- Always flow still works if manually selected.
- Subagent reject flow still works.
- Command guard blocks dangerous or corrupted bash commands.
- Explicit deny rules are not bypassed.

## Report format

When updating `docs/CURRENT_RELEASE.md`, include:

- workflow run ID
- artifact ID
- artifact digest
- `payload/opencode.exe` SHA256
- checked file count
- mismatch count
- hidden file presence result
- manual Windows runtime result, if performed
