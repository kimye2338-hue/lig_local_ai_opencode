# OpenCode Tool-Call Compatibility Notes

This file is persistent project guidance for OpenCodeLIG. Keep it in the repository so Codex, Claude Code, and OpenCode agents do not repeatedly rediscover the same tool-call issues.

## Source references checked

Official OpenCode docs checked on 2026-07-01:

- OpenCode Tools documentation: `https://opencode.ai/docs/tools/`
- OpenCode Permissions documentation: `https://opencode.ai/docs/permissions/`
- OpenCode Custom Tools documentation: `https://opencode.ai/docs/custom-tools/`
- OpenCode MCP servers documentation: `https://opencode.ai/docs/mcp-servers/`

## Official OpenCode tool model

OpenCode exposes a fixed set of built-in tools unless custom tools or MCP servers are configured.

Core built-in tool names include:

- `bash`
- `edit`
- `write`
- `read`
- `grep`
- `glob`
- `lsp` when enabled
- `apply_patch`
- `skill`
- `todowrite`
- `webfetch`
- `websearch` when enabled
- `question`

OpenCode permissions are configured through `permission`, not the old legacy `tools` boolean. Permission values are `allow`, `ask`, and `deny`.

Important permission facts:

- `write` and `apply_patch` are controlled by the `edit` permission.
- `external_directory` is a separate guard for paths outside the working directory.
- `doom_loop` is a guard for repeated identical tool calls.
- `--auto` only auto-approves requests that would otherwise ask; explicit `deny` still wins.
- `websearch` is only available with the OpenCode provider or when `OPENCODE_ENABLE_EXA` is set truthy.

## LIG internal-model compatibility issue

The LIG internal API/model stack should not be assumed to support native OpenAI `tool_calls`.

Previously observed and remembered:

- Internal APIs may accept chat/completions style requests, but native `messages/tools/tool_calls` support is not guaranteed.
- The proxy should not forward OpenAI `tools` directly to the internal model if the model does not support native tool calling.
- Tool-use should be bridged through prompt conventions or a compatibility layer.
- When OpenCode expects a tool call, the returned call must map to one of OpenCode's available tool names and the correct JSON argument schema.

## Known bad symptoms

These symptoms indicate the model/proxy emitted invalid tool-call syntax or tool names:

```text
invalid [tool=:, error=Model tried to call unavailable tool ':']
invalid [tool=bash, error=Invalid input for tool bash: JSON parsing failed]
```

Do not treat this as a user problem. It is a model/proxy/tool-call-format compatibility problem.

## Required behavior for agents

When using OpenCodeLIG:

1. Never invent tool names.
2. Never emit `tool=:` or any empty/punctuation-only tool name.
3. For `bash`, emit exactly the schema OpenCode expects, not malformed JSON strings.
4. Do not print raw tool-call failure dumps into user-facing chat unless debugging this exact issue.
5. Summarize tool errors briefly: cause + next action.
6. If unsure whether a tool exists, ask OpenCode for available tools or use only known built-ins.
7. Prefer `read`, `grep`, `glob`, `edit`, `write`, `bash`, `todowrite`, `question` for local work.
8. Do not rely on `websearch` unless the provider/environment enables it.
9. Do not rely on `webfetch` in restricted internal network unless explicitly available.
10. Keep user-facing output concise.

## Recommended proxy normalization rules

If maintaining the LIG proxy/tool-call bridge, enforce these rules before returning tool calls to OpenCode:

- Reject unknown tool names before they reach OpenCode.
- If the model emits colon-prefixed or markdown-ish pseudo calls, parse them as text, not tool calls.
- Validate JSON arguments with a strict parser.
- For `bash`, accept only an object matching the actual OpenCode bash input schema.
- If parsing fails, return a concise model-facing correction message and retry once.
- Preserve `finish_reason: "tool_calls"` only for valid tool calls.
- Use `finish_reason: "stop"` for normal text.
- Do not pass `tools` directly to the internal API if the internal model cannot natively use them.
- Keep `temperature=0` for tool-call extraction/bridging.

## User-facing output policy

The user does not want chat flooded with execution logs.

Do not print:

- full `pip list`
- large `dir` or `tree` outputs
- repeated shell prompts
- raw invalid tool-call traces
- long self-narration

Print only:

- result
- what changed
- what the user must do
- short failure reason when needed

## Persistent memory interaction

This file complements the external persistent memory path:

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\memory\TOOLING_NOTES.md
```

Patch installers should keep both the repository copy and the persistent user-data copy aligned when possible.
