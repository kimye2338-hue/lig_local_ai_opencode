# Claude Code implementation prompt — OpenCode AgentOps v3.1 P0/P1 + UX fix

You are Claude Code working as a senior Windows/OpenCode/agentic tooling developer.

You are editing the project in `SOURCE_TO_EDIT/`.

Read these first:

1. `REVIEW_AND_INSTRUCTIONS/01_OPUS_REVIEW_AGENTOPS_V3_1_OUTPUT.md`
2. `REVIEW_AND_INSTRUCTIONS/prior_review_context/IMPLEMENTATION_STATUS_AND_LIMITATIONS.md`
3. `REVIEW_AND_INSTRUCTIONS/prior_review_context/DESIRED_FINAL_BEHAVIOR.md`

Your job is to implement the Opus review findings, not to redesign the whole project from scratch.

## Main rule

Do not make broad rewrites. Preserve the existing AgentOps v3.1 structure. Apply small, safe, testable patches in the order below.

## Hard constraints

- Windows 10 target.
- Python 3.11 target.
- No external downloads.
- Do not add new pip/npm dependencies.
- BAT files must be ASCII-only and distributed as `.bat.txt`.
- Python files must be UTF-8.
- Do not create long files using `cat >`, heredoc, long echo, long printf, or long `python -c`.
- Use file edit/write/apply_patch mechanisms instead.
- Do not automate OTP/password/cookie/token extraction.
- Risky portal actions such as approve/submit/delete/send/upload/download must remain blocked unless the user explicitly approves the exact action in the current session.
- Do not delete user files or external directories.
- Keep OpenCode plugin files dependency-free unless already available offline.

## Implementation order

### Phase 0 — must-fix blockers before install

Implement exactly these P0 items from Opus review:

1. `P0-1-winlock`
   - File: `agent_ops/core.py`
   - Fix `_pid_alive` and `_lock_is_stale` to be Windows-safe.
   - Use the code from the Opus review unless you find a clear bug.

2. `P0-2-guard-plugin`
   - Create `.opencode/plugins/command-guard.ts`.
   - It must use `tool.execute.before` to block unsafe/corrupted bash commands before they run.
   - Keep it offline-safe: no npm imports.
   - Make sure it blocks:
     - prose/reasoning mixed into shell commands;
     - fake tool call text;
     - `cat >`, heredoc, long echo/printf file generation;
     - `python -c` / `py -3.11 -c`;
     - destructive shell patterns.

3. `P0-3-parallel-claim`
   - Files: `agent_ops/queue_manager.py`, `agent_ops/orchestrator.py`
   - Add atomic `claim_task`.
   - Parallel workers must not write shared `ACTIVE_TASK.json` / `CHECKPOINT.json`.
   - Workers must claim before running.
   - Main loop updates checkpoint only once per batch.

4. `P0-4-keyless-llm`
   - File: `agent_ops/llm_client.py`
   - Support internal keyless gateway:
     - `AGENTOPS_LLM_NO_AUTH=1`
     - config `"no_auth": true`
   - Omit Authorization header when no API key exists.
   - Parse non-perfect OpenAI responses defensively.

Stop after Phase 0 if any validation fails.

### Phase 1 — reliability fixes

Implement:

1. Retry backoff and explicit retry accounting.
2. Memory anti-bloat:
   - do not write a success lesson for every trivial success;
   - dedupe repeated failure memories;
   - cap active memory and archive/deprecate overflow.
3. Validate `.bat.txt` and `.cmd.txt` as ASCII, not only `.bat` and `.cmd`.
4. Improve compaction plugin:
   - use additive `output.context.push` if available;
   - resolve project root robustly;
   - do not silently lose handoff.
5. Make `/status` read-only:
   - status can report interruption;
   - recovery/mutation should happen in resume/init/orchestrator, not status.

### Phase 2 — user-visible UX improvements

Implement the highest-impact UX items, but keep them small and safe:

1. Add front-door commands:
   - `/start`
   - `/work`
   - `/fix`
   - `/status`
   - `/remember`
2. Keep advanced commands but do not make the user depend on them.
3. Add Korean plain-text status output:
   - queue counts;
   - active task;
   - stop requested;
   - last failure;
   - next recommended action.
4. Add a simple local HTML dashboard if it is safe and not too large:
   - `agent_ops/reports/dashboard.html`
   - current state, queue, recent done/failures, memory count.
5. Add one-click runner if easy:
   - `RUN_AGENTOPS_START.bat.txt`
   - `RUN_AGENTOPS_FIX.bat.txt`

### Phase 3 — OpenCode source-level ideas

Do not implement source-level OpenCode fork changes in this pass unless the required source is present.

Instead, create:

`REQUIRES_OPENCODE_SOURCE_PATCH.md`

Include:
- permission-mode hotkey toggle design;
- command sanitizer core patch alternative;
- what files/functions must be found in OpenCode source before editing;
- why this is not safe to implement in AgentOps-only source.

## Validation requirements

After each phase, run the relevant validation commands from the Opus review.

Minimum commands:

```bat
py -3.11 -m py_compile agent_ops\core.py
py -3.11 -m py_compile agent_ops\queue_manager.py
py -3.11 -m py_compile agent_ops\orchestrator.py
py -3.11 -m py_compile agent_ops\llm_client.py
py -3.11 -m py_compile agent_ops\command_guard.py
py -3.11 -m py_compile agent_ops\safe_file_writer.py
py -3.11 agent_ops\command_guard.py check "cat > a.py << 'EOF'"
py -3.11 agent_ops\command_guard.py check "python agent_ops/agentops.py status"
set AGENTOPS_LLM_NO_AUTH=1
set AGENTOPS_LLM_BASE_URL=http://127.0.0.1:1/v1
set AGENTOPS_LLM_MODEL=test
py -3.11 -c "from agent_ops.llm_client import is_configured; print(is_configured())"
```

Expected:
- py_compile passes.
- bad command returns block.
- safe command returns allow.
- keyless LLM config test prints True.

If a command cannot be run in the current environment, write it into `VALIDATION_TODO_ON_WINDOWS.md` with expected output.

## Output required

When done, produce:

1. `IMPLEMENTATION_REPORT.md`
   - what changed;
   - files edited;
   - which P0/P1/P2 items were completed;
   - what was not completed and why;
   - validation commands and outputs;
   - remaining risks.

2. `WINDOWS_TEST_PLAN.md`
   - exact commands for the user's home PC.

3. Keep all modified files in place under `SOURCE_TO_EDIT/`.

4. Do not package final release unless the user asks.
