# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_ops.core import CONTROL, STATE, REPORTS, RESULTS, now, atomic_write_text, atomic_write_json, read_text, read_json, validate_written_file, backup_file, is_stop_requested
from agent_ops.state_manager import init_state, heartbeat, detect_interruption, consume_interruption, update_checkpoint, update_resume_plan, update_compact_handoff, append_blocker
from agent_ops.queue_manager import enqueue_task, summary as queue_summary, recover_interrupted_active_tasks
from agent_ops.doctor import run_doctor
from agent_ops.verifier import verify
from agent_ops.reporter import write_report
from agent_ops.failures import log_failure, make_selfheal_plan
from agent_ops.memory_manager import memorycheck, ensure_memory, add_user_memory, recall, extract_keywords, format_recall_for_prompt
from agent_ops.safety import classify_action
from agent_ops.orchestrator import run_once, run_loop, run_loop_parallel

def cmd_init(args):
    interruption = init_state()
    ensure_memory()
    print("AgentOps v3.1 initialized.")
    if interruption.get("interrupted"):
        print("Interrupted run recovered:", interruption.get("reason"))
    return 0

def cmd_status(args):
    # Read-only (P1-7): report interruption but do NOT consume/recover or mutate
    # task state here. Recovery happens only in init/resume/orchestrator tick.
    # Note: we intentionally do NOT heartbeat here — a one-shot status read must
    # not refresh liveness (that would mask a real stale-heartbeat interruption
    # from a later resume/init, since "status" is not a watched run status).
    interruption = detect_interruption()
    data = {
        "timestamp": now(),
        "stop_requested": is_stop_requested(),
        "interruption": interruption,
        "queue": queue_summary(),
        "checkpoint": read_json(STATE / "CHECKPOINT.json", {}),
        "active_task": read_json(STATE / "ACTIVE_TASK.json", {}),
    }
    atomic_write_text(REPORTS / "STATUS.md", "# AgentOps Status\n\n```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```\n")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0

def cmd_resume(args):
    interruption = detect_interruption()
    if interruption.get("interrupted"):
        consume_interruption(interruption)
        recover_interrupted_active_tasks(interruption.get("reason") or "interrupted run")
    heartbeat("resume")
    update_resume_plan("resume requested")
    update_compact_handoff("resume requested")
    print(read_text(STATE / "RESUME_PLAN.md"))
    return 0

def cmd_checkpoint(args):
    update_checkpoint(args.note or "manual checkpoint")
    print("Checkpoint updated.")
    return 0

def cmd_doctor(args):
    result = run_doctor()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

def cmd_verify(args):
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1

def cmd_report(args):
    result = write_report()
    print("Report generated: agent_ops/reports/EXECUTIVE_REPORT.md")
    return 0

def cmd_selfheal(args):
    result = make_selfheal_plan()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

def cmd_log_failure(args):
    result = log_failure(" ".join(args.text), source="cli")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

def cmd_memorycheck(args):
    result = memorycheck()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

def cmd_remember(args):
    text = " ".join(args.text).strip()
    if not text:
        print("No memory text provided.", file=sys.stderr)
        return 2
    item = add_user_memory(text, title=args.title or "User instruction")
    print(json.dumps(item, ensure_ascii=False, indent=2))
    return 0

def cmd_recall(args):
    keywords = extract_keywords(" ".join(args.keywords))
    items = recall(task_kind=args.kind or "", keywords=keywords, limit=args.limit)
    print(format_recall_for_prompt(items))
    return 0

def cmd_enqueue(args):
    payload = {}
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except Exception as exc:
            print("Invalid payload JSON:", exc, file=sys.stderr)
            return 2
    task = enqueue_task(args.title, kind=args.kind, owner_agent=args.owner, priority=args.priority, risk=args.risk, payload=payload, touches=args.touches or [])
    print(json.dumps(task, ensure_ascii=False, indent=2))
    return 0

def cmd_continue(args):
    result = run_once()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1

def cmd_orchestrator(args):
    if args.parallel:
        return run_loop_parallel(interval_seconds=args.interval, max_workers=args.workers)
    return run_loop(interval_seconds=args.interval)

def cmd_agentstop(args):
    atomic_write_text(CONTROL / "STOP", f"stop requested at {now()}\n")
    heartbeat("stop_requested")
    update_checkpoint("stop requested")
    print("STOP file created: agent_ops/control/STOP")
    return 0

def cmd_unstop(args):
    try:
        (CONTROL / "STOP").unlink()
    except FileNotFoundError:
        pass
    heartbeat("unstop")
    update_checkpoint("stop cleared")
    print("STOP file removed.")
    return 0

def cmd_safety_check(args):
    result = classify_action(" ".join(args.text))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

def cmd_safe_write(args):
    target = (ROOT / args.target).resolve()
    content_file = (ROOT / args.content_file).resolve()
    if not str(target).startswith(str(ROOT.resolve())):
        print("Refusing to write outside project root.", file=sys.stderr)
        return 1
    if not content_file.exists():
        print("Content file not found.", file=sys.stderr)
        return 1
    backup = backup_file(target)
    from agent_ops.core import atomic_write_text
    atomic_write_text(target, content_file.read_text(encoding="utf-8", errors="replace"))
    validation = validate_written_file(target)
    if not validation.get("ok"):
        if backup and backup.exists():
            target.write_text(backup.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        print(json.dumps({"ok": False, "validation": validation}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    update_checkpoint(f"safe_write completed: {args.target}")
    print(json.dumps({"ok": True, "validation": validation}, ensure_ascii=False, indent=2))
    return 0

def main(argv=None):
    parser = argparse.ArgumentParser(description="OpenCode AgentOps v3.1 Co-Growth Runtime")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init").set_defaults(func=cmd_init)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("resume").set_defaults(func=cmd_resume)
    p = sub.add_parser("checkpoint"); p.add_argument("--note", default=""); p.set_defaults(func=cmd_checkpoint)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("verify").set_defaults(func=cmd_verify)
    sub.add_parser("report").set_defaults(func=cmd_report)
    sub.add_parser("selfheal").set_defaults(func=cmd_selfheal)
    p = sub.add_parser("log-failure"); p.add_argument("text", nargs="*"); p.set_defaults(func=cmd_log_failure)
    sub.add_parser("memorycheck").set_defaults(func=cmd_memorycheck)
    p = sub.add_parser("remember"); p.add_argument("text", nargs="*"); p.add_argument("--title", default="User instruction"); p.set_defaults(func=cmd_remember)
    p = sub.add_parser("recall"); p.add_argument("keywords", nargs="*"); p.add_argument("--kind", default=""); p.add_argument("--limit", type=int, default=6); p.set_defaults(func=cmd_recall)
    p = sub.add_parser("enqueue"); p.add_argument("title"); p.add_argument("--kind", default="manual"); p.add_argument("--owner", default="agentops-supervisor"); p.add_argument("--priority", type=int, default=5); p.add_argument("--risk", default="safe"); p.add_argument("--payload", default=""); p.add_argument("--touches", nargs="*", default=[]); p.set_defaults(func=cmd_enqueue)
    sub.add_parser("continue-once").set_defaults(func=cmd_continue)
    p = sub.add_parser("orchestrator"); p.add_argument("--interval", type=int, default=60); p.add_argument("--parallel", action="store_true"); p.add_argument("--workers", type=int, default=3); p.set_defaults(func=cmd_orchestrator)
    sub.add_parser("stop").set_defaults(func=cmd_agentstop)
    sub.add_parser("unstop").set_defaults(func=cmd_unstop)
    p = sub.add_parser("safety-check"); p.add_argument("text", nargs="*"); p.set_defaults(func=cmd_safety_check)
    p = sub.add_parser("safe-write"); p.add_argument("target"); p.add_argument("content_file"); p.set_defaults(func=cmd_safe_write)
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        return cmd_status(args)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
