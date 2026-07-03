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
from agent_ops.render_ko import write_status_ko

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
    if getattr(args, "ko", False):
        print(write_status_ko())
        return 0
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

def cmd_fix(args):
    # Front-door self-service recovery: self-heal plan + verify.
    plan = make_selfheal_plan()
    result = verify()
    summary_obj = {"selfheal": plan, "verify": result}
    if getattr(args, "ko", False):
        ftype = plan.get("failure_type", "UNKNOWN")
        ok = "정상" if result.get("ok") else "문제 있음"
        lines = [
            "AgentOps 자가 복구 결과",
            f"- 최근 실패 유형: {ftype}",
            f"- 권장 조치: {plan.get('actions', ['없음'])[0] if plan.get('actions') else '없음'}",
            f"- 검증 결과: {ok}",
            f"- 사용자 확인 필요: {'예' if plan.get('requires_user') else '아니오'}",
        ]
        print("\n".join(lines))
    else:
        print(json.dumps(summary_obj, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1

def cmd_dashboard(args):
    from agent_ops.dashboard import write_dashboard
    path = write_dashboard()
    print(f"Dashboard written: {path}")
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

def cmd_agent(args):
    """User-facing tool-use agent run. --mode mock validates the whole
    pipeline offline; --mode real needs lig-api.env (company validation
    pending on non-company machines)."""
    from agent_ops.core import ROOT as WS_ROOT
    from agent_ops.tool_dispatch import run_agent_loop
    from agent_ops.lig_providers import DIAG_DIR, SECRET_ENV_PATH, validate_config
    from agent_ops.capabilities import plan_task

    task = (args.task or "").strip()
    if not task:
        print("작업 내용이 없습니다. --task \"작업 설명\" 을 지정하세요.", file=sys.stderr)
        return 2
    plan = plan_task(task)
    capability_ids = [cap["id"] for cap in plan.get("capabilities", [])]

    if args.mode == "mock":
        from agent_ops.mock_transport import MOCK_ENV, make_mock_transport
        print("[mock 모드] 회사 API 없이 파이프라인만 검증합니다 (실제 모델 응답 아님).")
        result = run_agent_loop(task, WS_ROOT, env=MOCK_ENV,
                                transport=make_mock_transport(),
                                max_turns=args.max_turns,
                                capability_ids=capability_ids)
    else:
        cfg = validate_config()
        if not cfg.get("ready"):
            print("[real 모드] LIG provider 설정이 준비되지 않았습니다.", file=sys.stderr)
            for item in cfg.get("missing", []):
                print(f"  - {item}", file=sys.stderr)
            print(f"  설정 파일 위치: {SECRET_ENV_PATH}", file=sys.stderr)
            print("  회사 PC에서 lig-api.env를 채운 뒤 다시 실행하세요 (company validation pending).", file=sys.stderr)
            return 2
        print("[real 모드] LIG gateway로 실제 요청을 보냅니다.")
        result = run_agent_loop(task, WS_ROOT, max_turns=args.max_turns,
                                capability_ids=capability_ids)

    out = RESULTS / "llm_responses" / "agent_cli_last.md"
    atomic_write_text(out, result.get("final_content", ""))
    print(f"결과: {result['outcome']}  (턴 {result['turns']}, 도구 실행 {len(result['tool_results'])}회)")
    failed = [r for r in result["tool_results"] if not r.get("ok")]
    if failed:
        print(f"실패한 도구 호출 {len(failed)}건: " + ", ".join(
            f"{r.get('tool')}({r.get('root_cause_category')})" for r in failed))
    print("--- 최종 응답 ---")
    print(result.get("final_content", ""))
    print("-----------------")
    print(f"응답 저장: {out}")
    print(f"진단 위치: {DIAG_DIR}")
    return 0 if result["ok"] else 1

def cmd_plan(args):
    """Task (+ optional input files) -> capability routing -> artifacts.

    Shows which capabilities a request maps to, what stays app/company
    validation pending, and with --make-artifacts generates the scaffolds
    into results/artifacts/<run>/. --input <파일|폴더> (repeatable) reads the
    user's actual material so artifacts cite its contents; the ingested work
    context is saved secret-free to diagnostics."""
    from agent_ops.capabilities import plan_task
    from agent_ops.artifact_generators import build_artifact_context, generate_artifacts

    task = (args.task or "").strip()
    if not task:
        print("작업 내용이 없습니다. --task \"작업 설명\" 을 지정하세요.", file=sys.stderr)
        return 2
    inputs = None
    if getattr(args, "input", None):
        from agent_ops.input_ingest import ingest_inputs
        inputs = ingest_inputs(args.input)
        print(f"입력 자료 요약: {inputs['summary']}")
        for f in inputs["files"]:
            first = f["facts"][0] if f["facts"] else f["type"]
            print(f"  - {f['name']} ({f['size_bytes']:,} bytes): {first}")
        for u in inputs["unsupported"]:
            print(f"  - [unsupported] {u['name']}: {u['reason']}")
        for e in inputs["errors"]:
            print(f"  - [error] {e}")
    plan = plan_task(task)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.make_artifacts:
        print(f"\n다음 명령: {plan['next_exact_command']}")
        return 0
    if not plan["artifact_kinds"]:
        print("생성할 산출물 종류가 없습니다 (file_ops 계열 작업은 agent 명령을 사용하세요).")
        print(f"다음 명령: {plan['next_exact_command']}")
        return 0
    ctx = build_artifact_context(task, plan, inputs)
    try:  # secret-free work context for diagnostics; never blocks generation
        from agent_ops.lig_providers import DIAG_DIR
        DIAG_DIR.mkdir(parents=True, exist_ok=True)
        (DIAG_DIR / "work-context-last.json").write_text(
            json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    result = generate_artifacts(task, plan["artifact_kinds"], context=ctx)
    if inputs is not None:
        grounded = "예" if result.get("input_grounded") else "아니오 (입력 반영 검증 실패 또는 읽은 파일 없음)"
        print(f"입력 근거 반영(input-grounded): {grounded}")
    print(f"산출물 폴더: {result['out_dir']}")
    for f in result["files"]:
        print(f"  - {f}")
    for kind, verdict in result.get("quality", {}).items():
        mark = "OK" if verdict["ok"] else "FAIL"
        print(f"품질 검사 [{kind}]: {mark} ({verdict['checked_rules']} rules)")
        for v in verdict["violations"]:
            print(f"    - {v['rule']}: {v['why']}")
    if plan["pending"]:
        print("검증 pending:")
        for item in plan["pending"]:
            print(f"  - {item}")
    print("다음: 생성된 파일을 열어 TODO를 확정하세요. "
          "LLM 자동 채움(enrich)의 실제 gateway 연동은 company validation pending.")
    for err in result["errors"]:
        print(f"[ERROR] {err}", file=sys.stderr)
    return 0 if (result["ok"] and result.get("quality_ok", True)) else 1

def main(argv=None):
    parser = argparse.ArgumentParser(description="OpenCode AgentOps v3.1 Co-Growth Runtime")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init").set_defaults(func=cmd_init)
    p = sub.add_parser("status"); p.add_argument("--ko", action="store_true"); p.set_defaults(func=cmd_status)
    p = sub.add_parser("fix"); p.add_argument("--ko", action="store_true"); p.set_defaults(func=cmd_fix)
    sub.add_parser("dashboard").set_defaults(func=cmd_dashboard)
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
    p = sub.add_parser("agent"); p.add_argument("--mode", choices=["mock", "real"], required=True); p.add_argument("--task", default=""); p.add_argument("--max-turns", type=int, default=10); p.set_defaults(func=cmd_agent)
    p = sub.add_parser("plan"); p.add_argument("--task", default=""); p.add_argument("--input", action="append", default=[], help="입력 파일/폴더 (반복 지정 가능)"); p.add_argument("--make-artifacts", action="store_true"); p.set_defaults(func=cmd_plan)
    p = sub.add_parser("safety-check"); p.add_argument("text", nargs="*"); p.set_defaults(func=cmd_safety_check)
    p = sub.add_parser("safe-write"); p.add_argument("target"); p.add_argument("content_file"); p.set_defaults(func=cmd_safe_write)
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        return cmd_status(args)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
