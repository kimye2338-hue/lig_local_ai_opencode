# OpenCode AgentOps v3.1 Co-Growth Runtime

## What changed from v3

- interruption detection is consumed before heartbeat refresh
- zombie active tasks are returned to pending after interrupted runs
- stale lock files can be reclaimed
- memory recall is injected into `llm_plan`
- successful tasks create lessons
- `/remember` records user feedback as high-priority memory
- external orchestrator supports parallel safe batches with `touches` conflict avoidance
- optional compaction plugin is included under `.opencode/plugins/compaction-handoff.ts`

## First run

```cmd
python agent_ops\agentops.py init
python agent_ops\agentops.py doctor
python agent_ops\agentops.py verify
```

## OpenCode flow

```text
/status
/resume
/continue
```

## External unattended flow

Rename and run:

```text
RUN_AGENTOPS_ORCHESTRATOR.bat.txt -> RUN_AGENTOPS_ORCHESTRATOR.bat
```

Parallel mode:

```text
RUN_AGENTOPS_ORCHESTRATOR_PARALLEL.bat.txt -> RUN_AGENTOPS_ORCHESTRATOR_PARALLEL.bat
```
