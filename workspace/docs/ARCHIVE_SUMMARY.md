# Archive summary

This file replaces the old scattered `REVIEW_AND_WORK_INSTRUCTIONS/`, `OPTIONAL_PATCH_AND_INSTALLER_REFERENCES/`, `README_FIRST.md`, and root-level review notes.

The old files were useful during development, but they made the repository hard to navigate. Their important conclusions are kept here so Codex and Claude Code can preserve context without reopening large prompt bundles.

## Old instruction bundle purpose

The removed instruction bundle was created for a home-PC / low-token Claude Code workflow. It included:

- copy-paste prompts for Claude Code
- Opus review output
- prior AgentOps v2/v3 review context
- optional installer references
- optional reference package notes
- environment notes

That workflow is no longer the active source of truth. The active source of truth is now:

- `README.md`
- `AGENTS.md`
- `docs/AI_HANDOFF.md`
- `.github/workflows/build-offline-package.yml`
- `patches/opencode-permission-mode-toggle.patch`
- `workspace-template/`

## Retained OpenCode facts from prior review

- OpenCode local plugins live under `.opencode/plugins/`.
- The compaction hook is `experimental.session.compacting`.
- Bash permission matching is string/glob based and should not be the only guard for corrupted compound commands.
- `doom_loop` and `external_directory` are valid OpenCode permission keys.
- Command frontmatter keys such as `agent`, `subtask`, `model`, `description`, and `template` were considered valid for the targeted OpenCode version.
- Strong command blocking belongs in a `tool.execute.before` plugin.
- Offline plugins should use no npm imports unless the offline install path explicitly installs dependencies.
- OpenCode did not provide a built-in permission-mode keybind independent from agent cycling, which is why the source patch exists.

## Retained AgentOps runtime lessons

Previously identified and mostly addressed AgentOps runtime priorities:

- Make file locks Windows-safe.
- Ensure command guard is in the execution path, not only a manual CLI.
- Atomically claim tasks before parallel execution to avoid double-run races.
- Avoid shared `ACTIVE_TASK.json` / `CHECKPOINT.json` corruption in parallel workers.
- Allow internal LLM gateways that require no API key.
- Parse LLM responses defensively.
- Add retry backoff.
- Prevent unbounded memory growth.
- Validate `.bat.txt` and `.cmd.txt` as ASCII because users rename them.
- Keep `/status` read-only.
- Use additive compaction context where possible.

## Retained product goals

The desired final behavior remains:

- Continue until stopped, with durable recovery across restarts.
- Self-maintain by detecting failures, stopping repeated bad actions, repairing, verifying, checkpointing, and recording useful lessons.
- Preserve co-growth: user corrections and lessons should affect later decisions.
- Keep autonomy safe: project-local edits may be low-friction, but risky external/portal actions stay blocked.
- Maintain command integrity: no corrupted shell text, fake tool calls, or half-explanation/half-command approval prompts.
- Keep permission UX separate from agent/persona/model selection.
- Use external orchestration for safe parallel read-only work and serialize repair/write tasks.

## What was intentionally not retained as separate files

- Old one-shot installer scripts.
- Old full Opus feedback dumps.
- Previous implementation prompts.
- Prior review zip/package placeholders.
- Old root-level manifest files.

Reason: their actionable content is now represented by the current patch, workflow, workspace template, and the summarized docs above.
