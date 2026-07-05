# Product vision and proactive implementation brief — 2026-07-05

This document is for Fable, Codex, Claude Code, and future implementation agents.

The user is not asking for a narrow OpenCode fork. The target product is a company-PC offline/local AI work assistant that can operate real Windows engineering and office tools, remember lessons, recover from failures, and improve through patches without losing accumulated user state.

## 1. Product identity

OpenCodeLIG should be treated as:

> A durable personal work-automation agent for a Korean defense-company mechanical engineer on an internal Windows PC.

It must help with:

- browser-based company portal work,
- Excel/Word/PowerPoint/Outlook automation,
- HWP automation,
- SolidWorks / AutoCAD / MATLAB / Ansys-adjacent workflows,
- report writing and repetitive document generation,
- file inspection and conversion,
- local project work through `ocd`,
- long-term memory of user preferences, environment quirks, and repeated failures.

Do not optimize only for generic coding-chat behavior. The user wants a practical 업무비서 that can act on local applications and learn from company-PC trials.

## 2. User profile that should shape implementation

The user is a non-full-time developer using AI tools to automate engineering and office work. Implementations should assume:

- Korean Windows environment.
- Internal/offline network restrictions.
- Company PC with installed engineering/office software.
- Frequent CMD/PowerShell copy-paste usage.
- Need for simple commands and low-friction operation.
- Strong preference for concrete working patches over abstract explanations.
- Strong sensitivity to antivirus warnings and suspicious installer patterns.
- Desire for autonomous progress, but with durable state and auditability.

Important UX principle:

> The user should not need to understand GitHub, Python packaging, CDP, registry wiring, or OpenCode internals to get work done.

## 3. Core product direction

### 3.1 One-command daily use

Target commands:

```bat
ai
oc
ocd
```

Suggested meaning:

- `ai`: open the simple office-assistant menu/dashboard.
- `oc`: open OpenCodeLIG in the default workspace.
- `ocd`: open OpenCodeLIG in the current folder with folder-local profile files.

Installation should place these launchers in `%USERPROFILE%\OpenCodeLIG\bin` and ensure that directory is added to the user PATH.

### 3.2 Durable memory first

Runtime patches and reinstallations may replace program files, but must not erase:

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\memory
```

Global memory is a product feature, not temporary cache.

The assistant should remember:

- user preferences,
- failed approaches,
- successful fixes,
- company-PC environment facts,
- adapter quirks,
- model limitations,
- project decisions,
- install/package constraints.

### 3.3 Global memory plus folder-local profiles

Implement `ocd` so every project folder can have:

```text
.opencodelig\
  profile.json
  PERSONA.md
  PROJECT_MEMORY.md
  RULES.md
  TASKS.md
```

The agent should combine:

1. global user memory,
2. project-local memory,
3. folder persona,
4. folder rules,
5. current task.

This lets one folder be a quant/trading workspace, another be a SolidWorks automation workspace, and another be a company portal automation workspace while all share the same long-term user preferences.

## 4. Proactive implementation expectations

The user explicitly wants future agents to think ahead and implement missing support that the user may not know how to request.

Implementation agents should proactively consider these areas when working on a task.

### 4.1 Tool exposure completeness

When adding an adapter capability, always check the whole chain:

1. adapter code,
2. public action list,
3. `tool_dispatch.py` registry,
4. LLM tool schema,
5. tests,
6. docs/diagnostics.

Do not stop after writing a helper function.

### 4.2 Diagnostics before blame

Every major capability should have a diagnostic path that answers:

- Is the required app installed?
- Is the process reachable?
- Is the adapter available?
- Can a minimal action run?
- Where are logs/results saved?
- What should the user do next?

For example, browser automation should report:

- Chrome executable found,
- debug port available,
- tab count,
- current URL/title,
- screenshot path,
- rendered text length.

### 4.3 Failure recovery

If an action fails, the system should prefer structured recovery over stopping.

Examples:

- If a result folder path exists as a file, rename/delete/fallback instead of crashing.
- If Chrome has no debug tab, create one.
- If text extraction is empty, try rendered DOM and screenshot fallback.
- If a tool is unknown but adapter code exists, report that registry exposure is missing.
- If encoding output is garbled, preserve raw logs and try alternate decoding.

### 4.4 Restart/resume continuity

The user may close CMD/OpenCode and reopen it. The system should continue from durable state where possible.

Maintain:

- run/session ID,
- task queue,
- checkpoints,
- last tool results,
- pending actions,
- recovery notes,
- memory updates,
- local project profile.

### 4.5 Multi-agent usage

The user wants active use of subagents/specialists where helpful, especially because the internal model may be weaker than public frontier models.

Suggested specialist roles:

- browser automation specialist,
- Windows installer/package specialist,
- Office COM specialist,
- CAD/CAE macro specialist,
- code reviewer,
- diagnostics/root-cause specialist,
- memory curator,
- documentation/handoff specialist.

The coordinator should delegate bounded tasks, then merge findings into one clear result.

### 4.6 Guardrails without blocking useful work

AUTO mode and autonomous repair are desired, but not at the cost of unsafe behavior.

Keep these boundaries:

- no suspicious self-extracting BAT payloads,
- no hidden credential export,
- no destructive file operations without clear target and backup where appropriate,
- no internet dependency on the company PC,
- no package manager downloads during offline install,
- no silent memory deletion,
- no bypassing explicit user-deny or command guard policy.

## 5. Application automation priorities

### 5.1 Browser / company portal

High priority because the user is testing company portal automation now.

Needed capabilities:

- open/select/new tab,
- rendered SPA snapshot,
- clickable discovery,
- JS-based click,
- selector wait,
- screenshot,
- SPA map,
- stable result folders,
- mojibake-resistant filenames,
- Chrome restore prompt suppression,
- diagnostics.

### 5.2 Office automation

High priority because the user frequently needs reports, Excel workbooks, PowerPoint, Outlook, and Word/HWP.

Needed capabilities:

- Excel macro generation and execution,
- workbook read/write without duplicate weight/count errors,
- Word report drafting/conversion,
- PowerPoint generation,
- Outlook draft/send/search where allowed,
- HWP automation,
- safe backups before modifying office files.

### 5.3 Mechanical engineering tools

The product should keep growing toward engineering workflow automation.

Relevant applications:

- SolidWorks,
- AutoCAD,
- MATLAB,
- Ansys Mechanical,
- SpaceClaim,
- Icepak,
- Fluent where applicable.

Needed pattern:

- verify installed version,
- prefer version-specific APIs/macros,
- save generated scripts/macros with run instructions,
- record known COM/API quirks in memory,
- avoid claiming execution if only code generation was done.

### 5.4 File/package transfer

The user often moves files into an internal PC.

Needed priorities:

- offline bundles,
- manifest/checksum verification,
- no suspicious BAT payload methods,
- split-safe transfer formats where needed,
- clear install/run commands,
- rollback/backups.

## 6. UX principles

### 6.1 User should see progress

Long tasks should emit short progress updates.

Examples:

- what was inspected,
- what was changed,
- what failed and how it recovered,
- where output was saved,
- what remains.

### 6.2 Korean-first, non-developer-friendly

User-facing output should be Korean and practical.

Avoid making the user reason about:

- internal class names,
- JSON schemas,
- Git internals,
- CDP mechanics,
- package manager details.

Expose only what helps them act.

### 6.3 Evidence over confidence

When reporting that something works, include evidence:

- test name,
- command run,
- output file path,
- diagnostic result,
- workflow/artifact IDs when applicable.

Do not say “done” when only docs were changed.

## 7. Proactive features Fable should consider implementing

These are not all immediate blockers, but should be considered as future tasks.

### 7.1 Capability dashboard

A command/menu that shows:

- available adapters,
- app install status,
- last validation time,
- known limitations,
- quick test buttons/commands,
- where results/logs are saved.

### 7.2 Self-repair suggestions

When an adapter fails, generate a structured patch suggestion:

```text
problem → suspected cause → files to inspect → proposed patch → test command → restart needed?
```

### 7.3 Local project bootstrap templates

`ocd` could offer templates:

- `office-report`
- `solidworks-macro`
- `browser-portal`
- `quant-research`
- `general`

Each template could seed different `PERSONA.md`, `RULES.md`, and `TASKS.md`.

### 7.4 Memory review UI

A simple menu to review:

- active user memories,
- repeated failure lessons,
- deprecated memories,
- project-local memory,
- proposed cleanup actions.

No automatic deletion of protected user memories.

### 7.5 Encoding-safe command runner

Implement a Windows-aware command runner that:

- captures raw bytes,
- tries UTF-8,
- tries CP949,
- records raw output if decoding is uncertain,
- avoids corrupting Korean filenames in logs.

### 7.6 App-specific “first successful action” tests

For every adapter, define a minimal proof:

- Browser: capture title/text/screenshot.
- Excel: create workbook, write/read cell, optionally run macro.
- Outlook: list/draft capability only where permitted.
- HWP: open/create small doc.
- MATLAB: run simple expression/script.
- AutoCAD: verify executable/console.
- SolidWorks: connect COM and list version.

## 8. Implementation attitude expected from Fable

Fable should not wait for the user to name every missing connector. When implementing a feature, it should ask:

- What will break on Korean Windows?
- What happens on a company offline PC?
- Is the tool exposed to the LLM, not just implemented internally?
- Is there a diagnostic command?
- Is there a test?
- Does this preserve memory?
- Will the user know what command to run?
- Can this recover if interrupted?
- Does it avoid antivirus-suspicious packaging?

Then implement the small supporting pieces that are obviously necessary.

## 9. Near-term recommended implementation order

1. Finish/validate PR #10 browser CDP tool exposure.
2. Implement `ocd` folder-local profiles with shared global memory.
3. Add local profile context injection into agent prompt assembly.
4. Add capability dashboard/doctor output for browser and memory paths.
5. Fix Windows command-output mojibake in the command runner.
6. Add first-success tests for major adapters.
7. Add project templates for `ocd`.

## 10. Definition of success

The product is on the right path when the user can:

1. install from an offline bundle,
2. open CMD anywhere,
3. type `ocd`,
4. get a folder-specialized OpenCodeLIG session,
5. keep global memory across folders and reinstallations,
6. ask for browser/office/CAD automation in Korean,
7. receive working files/scripts/actions,
8. see diagnostics and recovery when something fails,
9. avoid repeating the same setup/debug mistakes.
