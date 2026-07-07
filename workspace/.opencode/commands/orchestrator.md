---
description: Explain external orchestrator use
agent: agent
subtask: false
---

Do not run infinite loops inside OpenCode bash. For an unattended run, open a separate CMD in the workspace folder and run the orchestrator launcher. In this offline package it ships as `launch\RUN_AGENTOPS_ORCHESTRATOR.bat.txt`(in the workspace's launch folder) — rename it to `RUN_AGENTOPS_ORCHESTRATOR.bat` first, then run it. For parallel mode, do the same with `launch\RUN_AGENTOPS_ORCHESTRATOR_PARALLEL.bat.txt` → `RUN_AGENTOPS_ORCHESTRATOR_PARALLEL.bat`.