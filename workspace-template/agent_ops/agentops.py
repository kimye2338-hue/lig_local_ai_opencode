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


SCHEDULE_DUE_HINT = ('기한을 인식하지 못했습니다. 날짜를 포함해 다시 입력하세요. '
                     '예: "7월 4일까지 진동시험 보고서"')


def _load_task_arg(args) -> str:
    task = (getattr(args, "task", "") or "").strip()
    task_file = (getattr(args, "task_file", "") or "").strip()
    if task_file:
        path = Path(task_file)
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"task file not found: {path}")
        file_task = path.read_text(encoding="utf-8", errors="replace").strip()
        task = task or file_task
    return task


def _ingest_from_args(args):
    if not getattr(args, "input", None):
        return None
    from agent_ops.input_ingest import ingest_inputs
    return ingest_inputs(args.input)


def _print_input_summary(inputs) -> None:
    if inputs is None:
        return
    print(f"입력 자료 요약: {inputs['summary']}")
    for f in inputs["files"]:
        first = f["facts"][0] if f["facts"] else f["type"]
        print(f"  - {f['name']} ({f['size_bytes']:,} bytes): {first}")
    for u in inputs["unsupported"]:
        print(f"  - [unsupported] {u['name']}: {u['reason']}")
    for e in inputs["errors"]:
        print(f"  - [error] {e}")


def _plan_context(task: str, inputs):
    from agent_ops.capabilities import plan_task
    from agent_ops.artifact_generators import build_artifact_context
    plan = plan_task(task)
    ctx = build_artifact_context(task, plan, inputs)
    return plan, ctx


def _record_work_context(ctx: dict) -> None:
    try:
        from agent_ops.lig_providers import DIAG_DIR
        DIAG_DIR.mkdir(parents=True, exist_ok=True)
        (DIAG_DIR / "work-context-last.json").write_text(
            json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _print_artifact_result(plan: dict, result: dict, inputs) -> None:
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


def _work_risk_items(plan: dict, execute: bool) -> list[dict]:
    items = []
    for kind in plan.get("artifact_kinds", []):
        items.append({"action_kind": "create_file", "target": f"results/artifacts/{kind}", "risk": "safe"})
    if execute:
        for kind in plan.get("artifact_kinds", []):
            items.append({"action_kind": "adapter_execute", "target": kind, "risk": "dangerous"})
    return items


def _audit_work(run_id: str, task: str, name: str, verdict: str, detail: str = "", risk: str = "safe") -> None:
    from agent_ops.audit import record
    record({
        "run_id": run_id,
        "task": task,
        "kind": "work",
        "name": name,
        "target": name,
        "risk": risk,
        "verdict": verdict,
        "detail": detail,
    })


def _adapter_execution_summary(plan: dict, artifact_result: dict, execute: bool) -> list[dict]:
    if not execute:
        return [{"adapter": "-", "verdict": "not requested", "detail": "--execute 미지정"}]
    from agent_ops.adapters import ADAPTERS
    summaries = []
    artifact_kinds = set(plan.get("artifact_kinds", []))
    for adapter_id, spec in ADAPTERS.items():
        if not artifact_kinds.intersection(set(spec.get("consumes", []))):
            continue
        if not spec.get("available"):
            summaries.append({"adapter": adapter_id, "verdict": "adapter pending", "detail": spec.get("pending", "")})
            continue
        execute_fn = spec.get("execute")
        if not callable(execute_fn):
            summaries.append({"adapter": adapter_id, "verdict": "adapter pending", "detail": "execute callable 없음"})
            continue
        result = execute_fn("artifact", {"files": artifact_result.get("files", [])})
        summaries.append({"adapter": adapter_id, "verdict": "ok" if result.get("ok") else "failed", "detail": result.get("error", "")})
    return summaries or [{"adapter": "-", "verdict": "adapter pending", "detail": "matching adapter 없음"}]


def _run_agent_work(task: str, plan: dict, mode: str) -> dict:
    from agent_ops.tool_dispatch import run_agent_loop
    from agent_ops.lig_providers import validate_config, SECRET_ENV_PATH

    capability_ids = [cap["id"] for cap in plan.get("capabilities", [])]
    if mode == "mock":
        from agent_ops.mock_transport import MOCK_ENV, make_mock_transport
        return run_agent_loop(task, ROOT, env=MOCK_ENV, transport=make_mock_transport(),
                              max_turns=10, capability_ids=capability_ids)
    cfg = validate_config()
    if not cfg.get("ready"):
        return {
            "ok": False,
            "outcome": "config_missing",
            "final_content": f"real 모드 설정이 준비되지 않았습니다: {SECRET_ENV_PATH}",
            "tool_results": [],
        }
    return run_agent_loop(task, ROOT, max_turns=10, capability_ids=capability_ids)


def _write_work_report(task: str, plan: dict, inputs, artifact_result: dict,
                       approval: dict, risks: list[dict], audit_rows: list[dict],
                       adapter_summary: list[dict]) -> Path:
    run_id = artifact_result.get("context", {}).get("run_id") or "unknown"
    reports_dir = RESULTS / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"work_{run_id}.md"
    quality_lines = []
    for kind, verdict in artifact_result.get("quality", {}).items():
        mark = "OK" if verdict.get("ok") else "FAIL"
        quality_lines.append(f"- {kind}: {mark} ({verdict.get('checked_rules')} rules)")
    adapter_lines = [f"- {a['adapter']}: {a['verdict']} - {a['detail']}" for a in adapter_summary]
    audit_lines = [f"- {r.get('name')}: {r.get('verdict')}" for r in audit_rows]
    input_names = artifact_result.get("context", {}).get("input_files", [])
    lines = [
        f"# Work Report {run_id}",
        "",
        "## 요청",
        task,
        "",
        "## 입력",
        ", ".join(input_names) if input_names else "없음",
        "",
        "## 계획",
        json.dumps({
            "capabilities": [c["id"] for c in plan.get("capabilities", [])],
            "artifact_kinds": plan.get("artifact_kinds", []),
            "pending": plan.get("pending", []),
        }, ensure_ascii=False, indent=2),
        "",
        "## 승인",
        json.dumps({"approval": approval, "risks": risks}, ensure_ascii=False, indent=2),
        "",
        "## 수행",
        "\n".join(adapter_lines) if adapter_lines else "없음",
        "",
        "## 산출물과 품질",
        "\n".join([f"- {f}" for f in artifact_result.get("files", [])]) or "없음",
        "",
        "\n".join(quality_lines) if quality_lines else "품질 검사 대상 없음",
        "",
        "## audit 요약",
        "\n".join(audit_lines) if audit_lines else "없음",
        "",
        "## pending",
        "\n".join([f"- {p}" for p in plan.get("pending", [])]) if plan.get("pending") else "없음",
        "",
        "## 다음 명령",
        plan.get("next_exact_command", "없음"),
        "",
    ]
    atomic_write_text(path, "\n".join(lines))
    return path

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


def cmd_work(args):
    """One-command workflow: input -> plan -> approval -> artifacts -> report."""
    from agent_ops.approval import request_approval
    from agent_ops.artifact_generators import generate_artifacts

    try:
        task = _load_task_arg(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not task:
        print("작업 내용이 없습니다. --task 또는 --task-file 을 지정하세요.", file=sys.stderr)
        return 2
    inputs = _ingest_from_args(args)
    _print_input_summary(inputs)
    plan, ctx = _plan_context(task, inputs)
    run_id = ctx["run_id"]
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    _record_work_context(ctx)
    _audit_work(run_id, task, "plan", "approved", "planned")

    risks = _work_risk_items(plan, bool(getattr(args, "execute", False)))
    approval = request_approval(risks, assume_yes=bool(getattr(args, "yes", False)))
    _audit_work(run_id, task, "approval", "approved" if approval.get("approved") else "denied",
                approval.get("mode", ""), risk="dangerous" if approval.get("dangerous_count") else "safe")
    if not approval.get("approved"):
        print("승인 거부로 중단", file=sys.stderr)
        return 3

    if plan["artifact_kinds"]:
        artifact_result = generate_artifacts(task, plan["artifact_kinds"],
                                             out_dir=RESULTS / "artifacts" / run_id,
                                             context=ctx)
        _print_artifact_result(plan, artifact_result, inputs)
        _audit_work(run_id, task, "artifacts", "approved" if artifact_result.get("ok") else "failed",
                    f"{len(artifact_result.get('files', []))} files")
        work_step = {"name": "artifacts", "verdict": "approved" if artifact_result.get("ok") else "failed"}
        adapter_summary = _adapter_execution_summary(plan, artifact_result, bool(getattr(args, "execute", False)))
    else:
        agent_result = _run_agent_work(task, plan, getattr(args, "mode", "mock"))
        out = RESULTS / "llm_responses" / f"work_{run_id}.md"
        atomic_write_text(out, agent_result.get("final_content", ""))
        artifact_result = {
            "ok": agent_result.get("ok"),
            "quality_ok": True,
            "out_dir": str(out.parent),
            "files": [str(out)],
            "errors": [],
            "quality": {},
            "context": {"run_id": run_id, "input_files": [f["name"] for f in ctx.get("inputs", {}).get("files", [])]},
        }
        _audit_work(run_id, task, "agent_loop", "approved" if agent_result.get("ok") else "failed",
                    agent_result.get("outcome", ""))
        work_step = {"name": "agent_loop", "verdict": "approved" if agent_result.get("ok") else "failed"}
        adapter_summary = [{"adapter": "agent_loop", "verdict": agent_result.get("outcome", ""),
                            "detail": f"{len(agent_result.get('tool_results', []))} tool results"}]

    for item in adapter_summary:
        _audit_work(run_id, task, f"adapter:{item['adapter']}", item["verdict"], item["detail"],
                    risk="dangerous" if getattr(args, "execute", False) else "safe")
        print(f"adapter {item['adapter']}: {item['verdict']} - {item['detail']}")

    audit_rows = [
        {"name": "plan", "verdict": "approved"},
        {"name": "approval", "verdict": "approved"},
        work_step,
    ]
    report = _write_work_report(task, plan, inputs, artifact_result, approval, risks,
                                audit_rows, adapter_summary)
    _audit_work(run_id, task, "report", "approved", report.name)
    print(f"최종 보고: {report}")
    return 0 if (artifact_result.get("ok") and artifact_result.get("quality_ok", True)) else 1


def cmd_plan(args):
    """Task (+ optional input files) -> capability routing -> artifacts.

    Shows which capabilities a request maps to, what stays app/company
    validation pending, and with --make-artifacts generates the scaffolds
    into results/artifacts/<run>/. --input <파일|폴더> (repeatable) reads the
    user's actual material so artifacts cite its contents; the ingested work
    context is saved secret-free to diagnostics."""
    from agent_ops.artifact_generators import generate_artifacts

    task = (args.task or "").strip()
    if not task:
        print("작업 내용이 없습니다. --task \"작업 설명\" 을 지정하세요.", file=sys.stderr)
        return 2
    inputs = _ingest_from_args(args)
    _print_input_summary(inputs)
    plan, ctx = _plan_context(task, inputs)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.make_artifacts:
        print(f"\n다음 명령: {plan['next_exact_command']}")
        return 0
    if not plan["artifact_kinds"]:
        print("생성할 산출물 종류가 없습니다 (file_ops 계열 작업은 agent 명령을 사용하세요).")
        print(f"다음 명령: {plan['next_exact_command']}")
        return 0
    _record_work_context(ctx)
    result = generate_artifacts(task, plan["artifact_kinds"], context=ctx)
    _print_artifact_result(plan, result, inputs)
    print("다음: 생성된 파일을 열어 TODO를 확정하세요. "
          "LLM 자동 채움(enrich)의 실제 gateway 연동은 company validation pending.")
    for err in result["errors"]:
        print(f"[ERROR] {err}", file=sys.stderr)
    return 0 if (result["ok"] and result.get("quality_ok", True)) else 1


def _schedule_display_id(value: object) -> str:
    try:
        return "sch_%04d" % int(value)
    except Exception:
        return "sch_0000"


def _schedule_parse_id(raw: str) -> int:
    text = str(raw or "").strip()
    if text.startswith("sch_"):
        text = text[4:]
    try:
        return int(text)
    except ValueError:
        return -1


def _schedule_due_label(due: str) -> str:
    from datetime import datetime
    text = str(due or "")
    fmt = "%Y-%m-%d %H:%M" if " " in text else "%Y-%m-%d"
    try:
        day = datetime.strptime(text, fmt)
    except ValueError:
        return text
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    label = day.strftime("%Y-%m-%d") + f"({weekdays[day.weekday()]})"
    if " " in text:
        label += day.strftime(" %H:%M")
    return label


def _schedule_clean_title(text: str) -> str:
    import re
    title = str(text or "")
    patterns = [
        r"\d{4}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2})?",
        r"\d{1,2}월\s*\d{1,2}일(?:\s*(?:오전|오후)?\s*\d{1,2}(?::\d{2})?\s*시?)?",
        r"\d{1,2}/\d{1,2}",
        r"(?:오늘|내일|모레|글피)(?:\s*(?:오전|오후)?\s*\d{1,2}(?::\d{2})?\s*시?)?",
        r"(?:월요일|화요일|수요일|목요일|금요일|토요일|일요일)(?:\s*(?:오전|오후)?\s*\d{1,2}(?::\d{2})?\s*시?)?",
        r"(?:이번주|다음주|다음 주|오는)\s*[월화수목금토일](?:\s*(?:오전|오후)?\s*\d{1,2}(?::\d{2})?\s*시?)?",
        r"\d+\s*(?:일|주|주일)\s*후",
        r"(?:오전|오후)?\s*\d{1,2}(?::\d{2})?\s*시",
    ]
    for pat in patterns:
        title = re.sub(pat, " ", title)
    title = re.sub(r"\b(schedule|deadline)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"(?:까지)(?=$|\s)", " ", title)
    title = re.sub(r"(일정|약속|스케줄|캘린더|등록해줘|등록|추가해줘|추가)", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" .'\"")
    return title or str(text or "").strip()


def _schedule_print_items(items: list[dict]) -> None:
    if not items:
        print("등록된 일정이 없습니다.")
        return
    print("%-9s %-16s %-4s %-4s %s" % ("ID", "기한", "분류", "상태", "제목"))
    for item in items:
        print("%-9s %-16s %-4s %-4s %s" % (
            _schedule_display_id(item.get("id")),
            _schedule_due_label(str(item.get("due", ""))),
            str(item.get("category", "")),
            str(item.get("status", "")),
            str(item.get("title", "")),
        ))


def cmd_schedule(args):
    from agent_ops import schedule_store
    from agent_ops.approval import classify_risk
    from agent_ops.core import ROOT

    action = args.schedule_cmd
    if action == "add":
        text = " ".join(args.text).strip()
        parsed = schedule_store.parse_due(text)
        if not parsed.get("ok"):
            print(SCHEDULE_DUE_HINT, file=sys.stderr)
            return 2
        title = _schedule_clean_title(text)
        result = schedule_store.add(title, text)
        if not result.get("ok"):
            print(SCHEDULE_DUE_HINT, file=sys.stderr)
            return 2
        item = result["item"]
        print("등록됨: %s %s %s" % (_schedule_display_id(item["id"]), _schedule_due_label(item["due"]), item["title"]))
        return 0
    if action in {"list", "today"}:
        when = "today" if action == "today" else args.when
        _schedule_print_items(schedule_store.list_items(when))
        return 0
    if action == "done":
        item_id = _schedule_parse_id(args.id)
        result = schedule_store.mark_done(item_id)
        if not result.get("ok"):
            print("일정을 찾지 못했습니다.", file=sys.stderr)
            return 2
        print("완료됨: %s" % _schedule_display_id(item_id))
        return 0
    if action == "remove":
        item_id = _schedule_parse_id(args.id)
        risk = classify_risk("schedule.remove", str(item_id), ROOT)
        if risk == "dangerous" and not args.yes:
            answer = (input("삭제할까요? [y/N] ") or "").strip().lower()
            if answer != "y":
                print("삭제를 취소했습니다.")
                return 3
        result = schedule_store.remove(item_id)
        if not result.get("ok"):
            print("일정을 찾지 못했습니다.", file=sys.stderr)
            return 2
        print("삭제됨: %s" % _schedule_display_id(item_id))
        return 0
    return 2


def cmd_briefing(args):
    from agent_ops.secretary import build_briefing
    path, text = build_briefing()
    print(text)
    print(f"브리핑 저장: {path}")
    return 0


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
    p = sub.add_parser("work"); p.add_argument("--task", default=""); p.add_argument("--task-file", default=""); p.add_argument("--input", action="append", default=[], help="입력 파일/폴더 (반복 지정 가능)"); p.add_argument("--mode", choices=["mock", "real"], default="mock"); p.add_argument("--execute", action="store_true"); p.add_argument("--yes", action="store_true"); p.set_defaults(func=cmd_work)
    p = sub.add_parser("schedule")
    sched = p.add_subparsers(dest="schedule_cmd", required=True)
    sp = sched.add_parser("add"); sp.add_argument("text", nargs="+"); sp.set_defaults(func=cmd_schedule)
    sp = sched.add_parser("list"); sp.add_argument("--when", choices=["today", "week", "all", "overdue"], default="all"); sp.set_defaults(func=cmd_schedule)
    sp = sched.add_parser("today"); sp.set_defaults(func=cmd_schedule)
    sp = sched.add_parser("done"); sp.add_argument("id"); sp.set_defaults(func=cmd_schedule)
    sp = sched.add_parser("remove"); sp.add_argument("id"); sp.add_argument("--yes", action="store_true"); sp.set_defaults(func=cmd_schedule)
    sub.add_parser("briefing").set_defaults(func=cmd_briefing)
    p = sub.add_parser("safety-check"); p.add_argument("text", nargs="*"); p.set_defaults(func=cmd_safety_check)
    p = sub.add_parser("safe-write"); p.add_argument("target"); p.add_argument("content_file"); p.set_defaults(func=cmd_safe_write)
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        return cmd_status(args)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
