# START HERE — Claude Code low-token Opus-manager workflow

You are Claude Code working on this local package.

The user has Claude Pro / limited tokens. Optimize for quality and token economy.

## Source to edit

Edit only:

```text
PROJECT_FULL_SOURCE_TO_EDIT/
```

Do not edit the review documents except to write reports.

## Main review document

Read this first:

```text
REVIEW_AND_WORK_INSTRUCTIONS/01_OPUS_FEEDBACK_FULL.md
```

Then read only the target files needed for the current task.

## Model/orchestration strategy

Use the strongest model only for management and verification.

Recommended workflow:

1. Use Opus only to:
   - read the Opus feedback;
   - create the phase plan;
   - identify exact files/functions to edit;
   - review the final diffs;
   - decide if a source-level OpenCode patch is actually needed.

2. Use Sonnet or a lower-cost model for:
   - direct code edits from the already-specific Opus tasks;
   - adding files from exact snippets;
   - py_compile fixes;
   - small command/Markdown additions;
   - report generation.

3. Do not make Opus reread the whole tree repeatedly.
   - Keep a short `WORKLOG.md`.
   - After each phase, summarize only:
     - files changed;
     - tests run;
     - failures;
     - next target file list.

4. Do not load large optional ZIPs unless required.
   - The editable source is already expanded in `PROJECT_FULL_SOURCE_TO_EDIT/`.
   - `OPTIONAL_REFERENCE_PACKAGES/` is only backup/reference.

## Execution mode

Start in planning mode, then implement phase by phase.

Do not rewrite the whole system. Preserve AgentOps v3.1 structure.

## Required implementation order

### Phase 0 — P0 blockers

Implement only these before anything else:

1. P0-1 Windows lock fix
   - `PROJECT_FULL_SOURCE_TO_EDIT/agent_ops/core.py`
   - Fix `_pid_alive`, `_lock_is_stale`.

2. P0-2 real command guard plugin
   - create/replace:
     `PROJECT_FULL_SOURCE_TO_EDIT/.opencode/plugins/command-guard.ts`
   - Must use OpenCode `tool.execute.before`.
   - Must be offline-safe: no npm imports.
   - Must block corrupted/prose-mixed bash commands before execution.

3. P0-3 parallel claim/race fix
   - `PROJECT_FULL_SOURCE_TO_EDIT/agent_ops/queue_manager.py`
   - `PROJECT_FULL_SOURCE_TO_EDIT/agent_ops/orchestrator.py`
   - Add atomic `claim_task`.
   - Parallel workers must not write shared `ACTIVE_TASK.json` / `CHECKPOINT.json`.

4. P0-4 keyless internal LLM gateway
   - `PROJECT_FULL_SOURCE_TO_EDIT/agent_ops/llm_client.py`
   - Support `AGENTOPS_LLM_NO_AUTH=1` and config `"no_auth": true`.
   - Do not send Authorization when no key is present.
   - Parse non-perfect OpenAI responses defensively.

Stop if any Phase 0 validation fails.

### Phase 1 — reliability

Implement after Phase 0 passes:

1. Retry backoff and explicit retry accounting.
2. Memory anti-bloat and dedupe.
3. `.bat.txt` / `.cmd.txt` ASCII validation.
4. Additive compaction hook with robust root path.
5. `/status` read-only.

### Phase 2 — user-visible UX

Implement small, high-impact UX only:

1. Front-door commands:
   - `/start`
   - `/work`
   - `/fix`
   - `/status`
   - `/remember`

2. Korean plain-text status:
   - queue counts;
   - active task;
   - last failure;
   - stop flag;
   - next recommended action.

3. Simple HTML dashboard if safe:
   - `agent_ops/reports/dashboard.html`.

4. One-click `.bat.txt` runners if safe:
   - `RUN_AGENTOPS_START.bat.txt`
   - `RUN_AGENTOPS_FIX.bat.txt`.

### Phase 3 — do not implement unless OpenCode source exists

Do not implement true Claude-Code-style permission-mode hotkey in this pass unless OpenCode source is present.

Instead create:

```text
PROJECT_FULL_SOURCE_TO_EDIT/REQUIRES_OPENCODE_SOURCE_PATCH.md
```

Include:
- permission-mode toggle design;
- required OpenCode source files/functions to find;
- why AgentOps-only source cannot fully implement it.

## Token-saving rules

- Do not paste entire files into the conversation unless absolutely required.
- Use targeted reads/searches.
- For each task, read only:
  - Opus section for that task;
  - target files;
  - directly imported helper files if needed.
- Prefer patch/diff edits.
- Avoid long explanations. Write reports to files instead.
- Do not re-summarize already completed phases unless a test fails.

## File-generation safety

Never create long files through:

```text
cat >
heredoc
long echo
long printf
python -c
py -3.11 -c
```

Use file edit/write/apply_patch or safe writer.

## Validation commands

Run from:

```text
PROJECT_FULL_SOURCE_TO_EDIT/
```

Minimum validation:

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
- all py_compile commands pass;
- bad command returns block;
- safe command returns allow;
- keyless LLM prints True.

If a command cannot run on this machine, write it into:

```text
PROJECT_FULL_SOURCE_TO_EDIT/VALIDATION_TODO_ON_WINDOWS.md
```

## Required output files

At the end, create:

```text
PROJECT_FULL_SOURCE_TO_EDIT/IMPLEMENTATION_REPORT.md
PROJECT_FULL_SOURCE_TO_EDIT/WINDOWS_TEST_PLAN.md
PROJECT_FULL_SOURCE_TO_EDIT/REMAINING_RISKS.md
```

Report exactly:
- files changed;
- P0/P1/P2 items completed;
- tests run and output;
- failures or skipped tests;
- remaining risks;
- next recommended step.

## Stop conditions

Stop and ask for direction if:

- Phase 0 validation fails after one focused fix attempt;
- OpenCode plugin hook behavior cannot be verified and a source patch would be required;
- any change would require external downloads;
- any change would touch outside `PROJECT_FULL_SOURCE_TO_EDIT/`;
- any action could automate credentials, OTP, cookies, tokens, approval, submission, delete, send, upload, or download.
