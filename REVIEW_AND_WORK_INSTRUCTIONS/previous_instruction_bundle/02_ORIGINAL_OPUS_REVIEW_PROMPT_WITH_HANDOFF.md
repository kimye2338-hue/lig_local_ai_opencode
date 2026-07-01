# Review prompt for Claude Opus

You are Claude Opus acting as a senior OpenCode / agentic tooling / Windows automation architect.

Your task is to review and improve the attached OpenCode AgentOps v3.1 source package.

Do not merely summarize. Find concrete bugs, design flaws, official OpenCode compatibility problems, and missing pieces. Then propose exact patches or full file replacements.

## Important: make recommendations implementable by weaker coding models

Your review output will likely be implemented by models weaker than you, such as Claude Sonnet, GPT-5, GPT-5 mini, or an internal company LLM. Therefore, do not give high-level advice only.

For every improvement, bug fix, or redesign you propose, write it so that a lower-capability implementation model can follow it without guessing.

Required style:

1. Be specific enough for direct implementation.
2. Avoid vague phrases such as “improve robustness,” “add better validation,” or “handle edge cases” unless you immediately define the exact code behavior.
3. For each proposed fix, include:
   - target file path;
   - target function/class/section;
   - current problem;
   - exact desired behavior;
   - step-by-step implementation plan;
   - acceptance tests;
   - expected output after the test.
4. When possible, provide exact replacement code or patch-style snippets.
5. If full code is too long, provide a precise implementation checklist that a weaker model can execute line by line.
6. Mark each item as:
   - `READY_FOR_SONNET/GPT5_IMPLEMENTATION`
   - `NEEDS_OPUS_LEVEL_DESIGN`
   - `REQUIRES_OPENCODE_SOURCE_PATCH`
   - `DO_NOT_IMPLEMENT_YET`
7. Separate conceptual architecture recommendations from immediately actionable patch tasks.
8. If a proposal depends on unknown OpenCode internals, explicitly say what must be verified first and how to verify it.
9. Prefer small, safe, testable patches over broad rewrites.
10. Include a final section named `Implementation handoff for lower-capability models`.

In `Implementation handoff for lower-capability models`, provide the work as a concrete task plan:

- Phase 0: must-fix blockers before install
- Phase 1: safe AgentOps-layer improvements
- Phase 2: user-visible UX improvements
- Phase 3: OpenCode source-level changes
- Phase 4: optional advanced improvements

For each task in the handoff, use this format:

```text
Task ID:
Priority:
Can be implemented by: Sonnet / GPT-5 / GPT-5 mini / Opus only
Files to edit:
Files to avoid editing:
Goal:
Exact steps:
Code changes:
Validation commands:
Expected validation result:
Rollback plan:
Risks:
```

Do not assume the implementation model will infer missing details. Your output should be usable as a direct implementation backlog.

At the end, include one more section named `Lower-model execution prompt`. This section must be a copy-paste-ready prompt that can be given directly to Sonnet/GPT-5/internal LLM to implement the highest-priority safe changes. It must include file names, edit order, validation commands, and stop conditions.


## Project goal

The user is building an AgentOps/self-maintenance layer for OpenCode on a Windows internal-network PC. The goal is not just a prompt pack. The goal is a durable runtime that can:

- preserve context across compaction/restart,
- recover interrupted tasks,
- run external orchestrator work outside OpenCode bash,
- use specialist agents,
- remember lessons and inject them into future tasks,
- avoid fake tool calls and corrupted command approval windows,
- safely automate project-local work,
- keep risky portal actions blocked,
- eventually support Claude-Code-like permission mode switching.

## User environment / constraints

- Windows 10.
- Python 3.11.x.
- Internal network.
- No external downloads by default.
- BAT files distributed as `.bat.txt`.
- BAT should be ASCII-only.
- Python should be UTF-8.
- User dislikes manual repeated prompt fixes and wants durable self-maintenance.
- Company LLM API is OpenAI-compatible but model may be weaker than Claude/OpenAI and may not emit OpenAI tool_calls natively.
- Do not automate OTP/password/cookie/token extraction.
- Risky portal actions such as approve/submit/delete/send/upload/download must remain blocked unless explicitly approved in the current session.

## Attached files to read first

1. `review_context/AGENTOPS_V2_DEEP_REVIEW.md`
2. `review_context/AGENTOPS_V3_OPUS_REVIEW.md`
3. `review_context/AGENTOPS_V3_FINAL_FEEDBACK.md`
4. `review_context/IMPLEMENTATION_STATUS_AND_LIMITATIONS.md`
5. `review_context/DESIRED_FINAL_BEHAVIOR.md`
6. `current_source/`

## What changed after your previous v3 feedback

The current snapshot attempts to implement v3.1:

- interruption detection before heartbeat;
- zombie active task recovery to pending;
- stale lock recovery;
- memory recall -> llm_plan prompt injection;
- success lesson recording;
- `/remember`;
- external parallel orchestrator with `touches`;
- compaction handoff plugin;
- LLM_NOT_CONFIGURED failure type;
- guarded autopilot mode;
- command guard for corrupted approval-window commands;
- safe file writer to replace heredoc/cat/python-c file generation.

## Critical review questions

### A. Official OpenCode compatibility

Verify all `.opencode/agents/*.md` and `.opencode/commands/*.md` frontmatter.

Check:

- Is `permission:` syntax valid?
- Does `bash:` mapping syntax and glob/precedence work as intended?
- Are `deny` patterns like `"cat > *": deny` and `"* << *": deny` actually effective in OpenCode?
- Is `doom_loop: deny` valid or a dead/invalid key?
- Are `subtask: true/false` values correctly used?
- Does `.opencode/plugins/compaction-handoff.ts` load automatically? If not, how should it be enabled?
- Is there any deprecated `tools:` or nonexistent `patch` tool usage left?
- Is the custom `agentops-autopilot` primary mode likely to work as intended?

### B. Command approval-window corruption

The user saw an approval modal containing this kind of corrupted text:

```text
cat > portal_research/scripts/portal_autonomous_research_runner.py << 'EOF'
#!/usr/bin/env python3
"""...
The content contains triple quotes and escaped newlines that broke JSON.
Let's write it line by line...
```

This must not be automatically run. Review `agent_ops/command_guard.py`, `agent_ops/safe_file_writer.py`, and `agentops-autopilot.md`.

Determine:

- Does the current guard actually prevent the bad command from auto-running?
- Can it be bypassed due to OpenCode permission matching?
- Should the guard be integrated into the actual bash execution path, not just used manually?
- Can OpenCode core be patched to add a pre-approval/pre-exec command sanitizer?
- Give exact implementation approach.

### C. Claude-Code-like permission UX

The user wants permission mode switching separate from agent/persona, similar to Claude Code.

Current workaround:

- `agentops-supervisor`: cautious mode
- `agentops-autopilot`: project-local guarded auto mode

Review whether OpenCode supports a true session-level permission mode toggle. If not, design a source-level patch.

Desired behavior:

- mode = plan | normal | auto
- keybind to cycle mode, ideally Shift+Tab or another suitable key
- visible status indicator
- permission resolver checks current mode
- agent/persona remains unchanged while permission mode changes

If this requires OpenCode source modification, describe exactly where/how to patch and provide a suggested implementation plan.

### D. Context preservation / compaction / restart

Review:

- `agent_ops/state_manager.py`
- `COMPACT_HANDOFF.md`
- `RESUME_PLAN.md`
- `CHECKPOINT.json`
- `.opencode/plugins/compaction-handoff.ts`

Questions:

- Is interruption recovery complete?
- Are active tasks safely recovered to pending?
- Does checkpoint stay slim enough?
- Does compaction hook actually enforce handoff?
- What fallback exists if plugin hook is unsupported?
- What tests prove context preservation works?

### E. Co-growth / memory

Review:

- `.agent-memory/memory.jsonl`
- `memory_manager.py`
- `orchestrator.py` llm_plan
- `/remember`

Questions:

- Is recall scoring useful enough?
- Is memory injected in the right place?
- Does it avoid compaction bloat?
- Does success lesson recording create noisy memory?
- How to improve without external packages?
- How to support reflection: repeated failures -> generalized rule?

### F. External orchestrator / parallelism

Review:

- `queue_manager.py`
- `orchestrator.py`
- lock handling in `core.py`

Questions:

- Are task status transitions safe?
- Can active tasks race under parallel mode?
- Are write/repair tasks truly serialized?
- Is `touches` conflict logic sufficient?
- Is stale lock recovery safe on Windows?
- What failure cases still leave zombie tasks?

### G. Portal automation safety

Review:

- `safety.py`
- policy files
- any portal-related assumptions

User eventually wants portal research automation, but not credential/OTP automation or risky submission. Propose architecture:

- attach to existing Chrome only;
- no cookie/storage/token extraction;
- snapshot HTML/screenshots safely;
- classify clickable elements;
- block risky actions;
- save evidence/reports;
- never click approve/submit/send/delete/upload/download unless current-session explicit approval.

### H. Installer and deployment

This review package excludes heavy one-file installers. Review lightweight installer logic:

- `current_source/installers_light/`
- `INSTALL_OPENCODE_AGENTOPS_V3_1_COGROWTH.py.txt`

Questions:

- Is merge_opencode safe?
- Does it preserve existing config?
- Does it avoid adding `.agent-memory` to instructions?
- Can it install command guard/autopilot current files too?
- Provide a safer single-file installer design if possible, but do not rely on fragile BAT base64 extraction if a better method exists.

## Additional requirement: user-visible product improvement review

In addition to correctness and safety review, evaluate whether this system will *feel meaningfully better to the user* in day-to-day use.

The user does not only want internal architecture improvements. They want a program that feels like a practical, helpful, persistent local agent assistant.

Please identify feature improvements that would create noticeable UX/product gains, especially for a non-developer user on a Windows internal-network PC.

Review and propose improvements for:

### 1. Day-to-day workflow UX

- What should the user type when they open OpenCode?
- What should happen after `/resume`, `/continue`, `/autopilot`, `/doctor`, `/verify`, `/remember`?
- Are commands too many, confusing, or overlapping?
- Should there be a single `/start`, `/work`, or `/fix` command that chooses the right flow?
- How can the system explain current status in simple Korean, not just JSON?
- How can it reduce the feeling that the user has to babysit the agent?

### 2. Observable progress

The user wants to feel that the agent is actually working, not just writing plans.

Propose concrete features such as:

- progress dashboard/report;
- current task card;
- next action preview;
- “what changed since last run” summary;
- “why stopped” summary;
- “what I fixed automatically” summary;
- plain Korean daily/work session summary;
- task queue UI/report that is easy to read.

### 3. Better failure recovery UX

When something fails, the user should not just see a traceback.

Propose:

- friendly failure report;
- root cause classification;
- exact next step;
- auto-created repair task;
- retry limit with explanation;
- “safe rollback available” message;
- blocked/risky action report;
- command corruption warning with replacement suggestion.

### 4. Fewer confusing modes

Currently there are multiple agents and commands:

- `agentops-supervisor`
- `agentops-autopilot`
- `agentops-repair`
- `agentops-command-sentinel`
- `/continue`
- `/resume`
- `/autopilot`
- `/safecreate`
- `/lintcmd`
- `/agentmode`
- `/doctor`
- `/verify`
- `/selfheal`
- `/memorycheck`

Review whether this is too complex. Propose a simpler command/mode design.

For example:

- `/start` = resume + status + next recommended action
- `/work <goal>` = guarded execution
- `/fix` = selfheal + repair + verify
- `/status` = plain Korean status
- `/remember <note>` = save correction/preference
- advanced commands hidden from normal use

### 5. Proactive self-improvement

The user wants the system to improve itself.

Propose how to make self-improvement visible and useful:

- recurring reflection task;
- pattern extraction from repeated failures;
- memory quality review;
- command guard rule updates from real blocked commands;
- automatic “I learned this” summary;
- stale/contradictory memory cleanup with approval;
- before/after metrics for reliability.

### 6. Better Windows/internal-network fit

Review for features that would make it feel robust on the user's actual PC:

- path handling for Korean/space paths;
- Python detection;
- Chrome/ChromeDriver/CDP diagnostics;
- no fragile long BAT payloads;
- simple log file locations;
- clear `.bat.txt` rename guidance;
- minimal dependency design;
- offline/internal-network safe operation.

### 7. Feature ideas Opus should propose even if not implemented now

Please propose concrete, prioritized feature upgrades that would most improve perceived usefulness.

Examples:

- local mini dashboard HTML generated from state files;
- tray/status script;
- one-click doctor/fix runner;
- restart-resume bootstrap command;
- agent activity timeline;
- task queue visualizer;
- portal snapshot viewer;
- “approve only this action” safe approval workflow;
- command approval sanitizer integrated at OpenCode core level;
- permission-mode hotkey toggle;
- Korean natural-language status summaries.

For each feature idea, include:

- user-visible benefit;
- implementation difficulty;
- risk;
- exact files/components likely involved;
- whether it can be done in AgentOps layer or requires OpenCode source patch;
- priority: P0/P1/P2.

### 8. Final deliverable requirement

Add a separate section in your answer:

`User-visible improvement roadmap`

Include 10-20 concrete improvements ranked by expected user impact, not just engineering elegance.

## Output format required

Please produce:

1. Executive verdict:
   - Is this v3.1 ready to install?
   - If not, what P0 blocks installation?

2. P0/P1/P2 issue table:
   - File
   - Problem
   - Why it matters
   - Exact fix

3. Exact patch proposal:
   - Prefer full file replacements for small files.
   - For large files, provide precise diffs or replacement sections.
   - Avoid vague suggestions.

4. Test plan:
   - Commands to run on Windows.
   - Expected outputs.
   - Include tests for:
     - bad command guard sample,
     - safe command allow,
     - safe_file_writer validation,
     - stale heartbeat recovery,
     - memory recall injection,
     - parallel touches conflict,
     - compaction handoff behavior.

5. If source-level OpenCode patch is needed for permission-mode toggle or command sanitizer:
   - describe target files/functions conceptually,
   - describe state model,
   - describe keybind/action,
   - describe permission resolver change,
   - describe backward compatibility.

6. Implementation priority:
   - What to fix before user installs,
   - what can wait,
   - what is impossible without OpenCode source changes.

Be strict. Assume user will actually run this on a Windows internal-network work PC.
