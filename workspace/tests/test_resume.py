# -*- coding: utf-8 -*-
"""Checkpoint/resume validation across fresh processes (stdlib only).

Run: py -3.11 tests\\test_resume.py

Simulates: multi-step task -> checkpoint -> interruption (stale heartbeat) ->
fresh process load -> interruption detected, task returned to pending,
completed steps not re-run. Uses AGENTOPS_ROOT to isolate state in a temp dir.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1]
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def run_py(code: str, root: Path) -> str:
    """Run a snippet in a FRESH python process with isolated AGENTOPS_ROOT."""
    env = dict(os.environ)
    env["AGENTOPS_ROOT"] = str(root)
    env["PYTHONIOENCODING"] = "utf-8"
    cp = subprocess.run([sys.executable, "-c", code], cwd=str(TEMPLATE), env=env,
                        capture_output=True, text=True, encoding="utf-8", timeout=60)
    if cp.returncode != 0:
        print(f"SUBPROCESS FAIL:\n{cp.stderr}")
        sys.exit(1)
    return cp.stdout.strip()


PRE = "import sys, json; sys.path.insert(0, '.');"

with tempfile.TemporaryDirectory() as td:
    root = Path(td)

    # Step 1: fresh process initializes state and starts a 3-step task
    out = run_py(PRE + """
from agent_ops.state_manager import init_state, set_active_task, update_checkpoint, heartbeat
init_state()
task = {"task_id": "t-001", "title": "다단계 작업", "status": "active",
        "steps_done": ["step1"], "steps_pending": ["step2", "step3"]}
set_active_task(task)
update_checkpoint("step1 done", active_task=task)
heartbeat("running")
print("started")
""", root)
    check("state initialized in fresh process", out == "started", out)
    state_dir = root / "agent_ops" / "state"
    check("checkpoint file exists", (state_dir / "CHECKPOINT.json").exists())

    # Step 2: simulate interruption — backdate the heartbeat, no clean shutdown
    rs = json.loads((state_dir / "RUN_STATE.json").read_text(encoding="utf-8"))
    rs["last_heartbeat"] = "2020-01-01T00:00:00+09:00"
    rs["status"] = "running"
    (state_dir / "RUN_STATE.json").write_text(json.dumps(rs, ensure_ascii=False), encoding="utf-8")

    # Step 3: second fresh process detects the interruption and recovers
    out = run_py(PRE + """
from agent_ops.state_manager import init_state, get_active_task
interruption = init_state()
task = get_active_task()
print(json.dumps({"interrupted": bool(interruption.get("interrupted")),
                  "task_status": task.get("status"),
                  "steps_done": task.get("steps_done"),
                  "steps_pending": task.get("steps_pending")}, ensure_ascii=False))
""", root)
    r = json.loads(out)
    check("interruption detected on fresh start", r["interrupted"] is True, out)
    check("task returned to pending (not lost)", r["task_status"] == "pending", out)
    check("completed steps preserved", r["steps_done"] == ["step1"], out)
    check("pending steps preserved", r["steps_pending"] == ["step2", "step3"], out)

    cp = json.loads((state_dir / "CHECKPOINT.json").read_text(encoding="utf-8"))
    check("checkpoint records interruption", cp.get("interrupted") is True and cp.get("interruption_reason"), str(cp))

    # Step 4: resume — third fresh process continues from pending steps only
    out = run_py(PRE + """
from agent_ops.state_manager import get_active_task, set_active_task, update_checkpoint
task = get_active_task()
task["status"] = "active"
done = task["steps_done"]; pending = task["steps_pending"]
next_step = pending.pop(0)
assert next_step not in done, "would re-run a completed step"
done.append(next_step)
set_active_task(task)
update_checkpoint(f"resumed, {next_step} done", active_task=task)
print(json.dumps({"done": done, "pending": pending}))
""", root)
    r = json.loads(out)
    check("resume continues from step2", r["done"] == ["step1", "step2"] and r["pending"] == ["step3"], out)

    # Step 5: no stale-interruption false positive after healthy heartbeat
    out = run_py(PRE + """
from agent_ops.state_manager import heartbeat, detect_interruption
heartbeat("running")
print(json.dumps(detect_interruption().get("interrupted")))
""", root)
    check("no false interruption after heartbeat", out == "false", out)

print(f"\n{PASS} checks passed")
