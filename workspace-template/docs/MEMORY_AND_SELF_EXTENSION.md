# Memory and tool self-extension rules

This note records two runtime invariants that must survive future patches.

## 1. Tool self-extension lifecycle

The model cannot instantly add a new callable tool to the same already-started tool schema just because it edited code.

When a task needs a missing browser/app/file tool, the agent should follow this lifecycle:

1. Inspect the adapter implementation first.
   - Example: `workspace-template/agent_ops/adapters/browser_cdp.py` may already contain a private helper such as `_new_tab()`.
2. Inspect `workspace-template/agent_ops/tool_dispatch.py`.
   - A helper is not actually usable by the LLM unless `REGISTRY` and `tool_definitions()` expose it.
3. Add or repair the adapter action.
4. Register the action in the tool dispatcher.
5. Add or update tests.
6. Report whether a restart/new agent loop is needed before the model can use the new tool.

Practical rule:

- Adapter function = tool stored in the warehouse.
- Dispatcher registry = tool issued to the worker.
- LLM tool schema = button the model can actually press.

If any one of those three layers is missing, the model may say the capability exists but still fail with `unknown tool` or `unsupported action`.

## 2. Memory preservation invariant

User-provided memories, preferences, repeated-failure lessons, and project operating rules are part of the product state. They must not be treated as disposable cache.

The installed runtime already separates program files from user memory:

- Program/workspace: `%USERPROFILE%\OpenCodeLIG\workspace`
- User memory/data: `%USERPROFILE%\OpenCodeLIG_USERDATA\memory`
- Optional override: `AGENTOPS_MEMORY_DIR`

Future installers and patches must preserve this separation.

Do not:

- delete `%USERPROFILE%\OpenCodeLIG_USERDATA\memory`
- overwrite `memory.jsonl`
- overwrite `WIKI.md` if it already exists
- reset memories during runtime patching
- archive explicit user preferences automatically just because routine memory cleanup runs

Allowed:

- add new memory views such as `ACTIVE_MEMORY.md`, `LESSONS_LEARNED.md`, or `MEMORY_INDEX.json`
- deduplicate low-priority self-observed noise
- mark stale self-observed lessons for review
- create backups before migrations

Required before changing memory storage format:

1. Back up the existing memory directory.
2. Migrate append-only records without dropping fields.
3. Preserve unknown future fields.
4. Verify that `remember`, `recall`, `memorycheck`, and prompt injection still work.
5. Document the migration in `docs/AI_HANDOFF.md`.

## 3. Why this matters

The user expects the assistant to improve over time by remembering prior mistakes, environment details, tool quirks, and preferred operating style. Losing that memory during a patch would make the program regress even if the code became cleaner.

Therefore, tool patches should be allowed to replace runtime code, but user memory must be treated like durable personal state.