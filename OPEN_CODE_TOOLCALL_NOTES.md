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
- `question` is a real tool for asking the user structured questions. Its JSON schema must not be printed to the user as normal assistant text.

## LIG internal-model compatibility issue

The LIG internal API/model stack should not be assumed to support native OpenAI `tool_calls`.

Previously observed and remembered:

- Internal APIs may accept chat/completions style requests, but native `messages/tools/tool_calls` support is not guaranteed.
- The proxy should not forward OpenAI `tools` directly to the internal model if the model does not support native tool calling.
- Tool-use should be bridged through prompt conventions or a compatibility layer.
- When OpenCode expects a tool call, the returned call must map to one of OpenCode's available tool names and the correct JSON argument schema.

## Full failure taxonomy to guard against

Treat all of these as the same family of compatibility / leakage problems, not one-off user mistakes.

### A. Invalid tool names

Symptoms:

```text
invalid [tool=:, error=Model tried to call unavailable tool ':']
invalid [tool=python, error=Model tried to call unavailable tool 'python']
invalid [tool=terminal, error=Model tried to call unavailable tool 'terminal']
invalid [tool=run_command, error=Model tried to call unavailable tool 'run_command']
```

Rules:

- Never invent tool names.
- Never emit punctuation-only tool names such as `:`.
- Map model intentions only to actual OpenCode tools.
- If there is no matching tool, answer in text or use `question` if valid.

### B. Malformed tool arguments

Symptoms:

```text
invalid [tool=bash, error=Invalid input for tool bash: JSON parsing failed]
invalid [tool=edit, error=Invalid input for tool edit]
invalid [tool=write, error=Invalid input for tool write]
```

Rules:

- Tool arguments must be strict JSON matching the tool schema.
- Do not pass a raw shell command string where an object is expected.
- Do not double-encode JSON.
- Do not include markdown fences in tool arguments.
- If JSON parsing fails, repair internally and retry once; do not flood the user.

### C. Tool schema leaked as assistant text

Symptoms:

```text
[
  {"question":"...","header":"...","options":[...],"multiple":false,"custom":true}
]
```

or any of these printed in normal chat:

```text
{"tool":"bash","arguments":{...}}
{"name":"question","input":{...}}
<tool_call>...</tool_call>
functions.bash({...})
question([...])
```

Rules:

- Tool-call JSON, XML-ish tags, function-call examples, and internal schemas must never be shown to the user as the final answer.
- If a tool call cannot be made, convert it to a short natural-language question or answer.
- For `question`, ask at most 1-3 concise natural-language questions unless the real `question` tool is successfully invoked.
- Do not print `header`, `options`, `multiple`, `custom`, or other internal UI schema fields.

### D. Raw execution logs flood the chat

Symptoms:

```text
$ python --version
$ pip list
Package Version ...
Click to expand
```

Rules:

- Do not print long raw logs unless the user explicitly requests them.
- Summarize shell output: success/failure + important lines only.
- Never print full `pip list`, directory trees, large `dir`, large `grep`, or repeated shell prompts.
- Keep noisy logs in internal/debug context, not user-facing final text.

### E. Progress narration flood

Symptoms:

```text
현재 제한사항...
먼저 확인하겠습니다...
다음과 같은 질문을 사용자에게 하여 계획을 구체화하겠습니다...
```

Rules:

- Do not narrate routine internal steps.
- Report only conclusions, required user action, and blocker summaries.
- Ask clarifying questions only when they are necessary and not already known.

### F. Unsupported web/tool assumptions

Symptoms:

```text
websearch unavailable
webfetch blocked
ChromeDriver missing
```

Rules:

- Do not assume `websearch` is available unless enabled.
- Do not assume public internet access on the company PC.
- For internal network work, prefer browser/manual HTML/source input when web tools are unavailable.
- If a dependency is missing, list exactly what is needed, not a long diagnostic dump.

### G. Final-text examples accidentally executed as tools

Symptoms:

- The model writes code examples or pseudo-calls, and the harness tries to execute them.
- Example text like `functions.NAME({...})` or `tool({...})` is treated as a real call.

Rules:

- Treat code fences, inline examples, and explanatory pseudo-tool calls as text only.
- The proxy must only execute tool calls emitted in the official tool-call channel/format.
- Never infer executable tools from final answer prose.

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
11. Never expose internal tool schemas or question arrays as final text.
12. If the model cannot call a tool correctly, fall back to concise natural-language output.

## Recommended proxy normalization rules

If maintaining the LIG proxy/tool-call bridge, enforce these rules before returning tool calls to OpenCode:

- Reject unknown tool names before they reach OpenCode.
- If the model emits colon-prefixed, markdown-ish, JSON-ish, XML-ish, or function-call-looking pseudo calls in normal text, parse them as text, not tool calls.
- Validate JSON arguments with a strict parser.
- For `bash`, accept only an object matching the actual OpenCode bash input schema.
- If parsing fails, return a concise model-facing correction message and retry once.
- Preserve `finish_reason: "tool_calls"` only for valid tool calls.
- Use `finish_reason: "stop"` for normal text.
- Do not pass `tools` directly to the internal API if the internal model cannot natively use them.
- Keep `temperature=0` for tool-call extraction/bridging.
- Maintain a whitelist of valid tool names.
- Maintain per-tool JSON-schema validation before execution.
- Add a final sanitizer: if assistant final text contains a raw tool schema, replace it with a natural-language summary before displaying it to the user.

## User-facing output policy

The user does not want chat flooded with execution logs.

Do not print:

- full `pip list`
- large `dir` or `tree` outputs
- repeated shell prompts
- raw invalid tool-call traces
- long self-narration
- `question` JSON arrays
- tool schemas
- function-call pseudo syntax
- raw stack traces unless explicitly debugging

Print only:

- result
- what changed
- what the user must do
- short failure reason when needed
- exact files/libraries needed when asked

## Persistent memory interaction

This file complements the external persistent memory path:

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\memory\TOOLING_NOTES.md
```

Patch installers should keep both the repository copy and the persistent user-data copy aligned when possible.
