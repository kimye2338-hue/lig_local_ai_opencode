# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
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


def _work_risk_items(plan: dict, execute: bool, input_paths=()) -> list[dict]:
    items = []
    for kind in plan.get("artifact_kinds", []):
        items.append({"action_kind": "create_file", "target": f"results/artifacts/{kind}", "risk": "safe"})
    if execute:
        # 실제로 자동 실행될 어댑터 매핑에만 dangerous 승인 항목을 만든다
        # (매핑 없는 kind에 가짜 위험 항목을 만들지 않는다 — 승인 신뢰 유지).
        from agent_ops.adapters import executable_kinds
        for kind in executable_kinds(plan.get("artifact_kinds", []), input_paths):
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


def _adapter_execution_summary(plan: dict, artifact_result: dict, execute: bool,
                               input_paths=()) -> list[dict]:
    if not execute:
        return [{"adapter": "-", "verdict": "not requested", "detail": "--execute 미지정"}]
    from agent_ops.adapters import plan_execution
    summaries = []
    entries = plan_execution(plan.get("artifact_kinds", []),
                             artifact_result.get("files", []), input_paths)
    for e in entries:
        if e["ready"]:
            result = e["invoke"]()
            ok = bool(result.get("ok"))
            detail = e["reason"] if ok else str(result.get("error", ""))[:160]
            if not ok:
                try:  # 어댑터 실패도 자가 관찰 실수로 기억 (같은 날 중복 방지)
                    from agent_ops.memory_manager import record_self_error
                    record_self_error(f"{e['adapter']} 어댑터 실행 실패", detail)
                except Exception:  # noqa: BLE001
                    pass
            if ok and result.get("out_path"):
                detail += f" -> {result['out_path']}"
            summaries.append({"adapter": e["adapter"],
                              "verdict": "ok" if ok else "failed",
                              "detail": detail})
        else:
            summaries.append({"adapter": e["adapter"] if e["adapter"] != "-" else e["kind"],
                              "verdict": "no-auto-run", "detail": e["reason"]})
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

def cmd_watch(args):
    """감시용 1회 판정 — 에이전트 모드의 메인이 위임 작업이 '먹통'인지 폴링한다.

    출력: 한 줄 판정 + JSON. 종료코드로 분기 가능:
      0 = 진행중/대기(정상), 3 = 멈춤 의심(stale heartbeat), 4 = 정지 요청됨.
    메인은 위임(orchestrator/work 등) 사이사이 이 명령을 돌려, 멈춤이면 개입한다.
    """
    max_age = int(getattr(args, "max_age", 0) or 600)
    interruption = detect_interruption(max_age_seconds=max_age)
    active = read_json(STATE / "ACTIVE_TASK.json", {})
    run_state = read_json(STATE / "RUN_STATE.json", {})
    stopped = is_stop_requested()
    if stopped:
        verdict, code = "정지 요청됨 — 실행을 멈추고 사용자에게 확인", 4
    elif interruption.get("interrupted"):
        verdict, code = f"멈춤 의심 — {interruption.get('reason')}. 개입 필요(원인 확인→재지시/이관)", 3
    elif str(run_state.get("status") or "") in {"continuous", "continuous_external", "continuous_parallel", "running", "active", "orchestrator_once"}:
        verdict, code = "진행중 — 하트비트 정상", 0
    else:
        verdict, code = "대기/유휴 — 실행 중인 작업 없음", 0
    data = {
        "timestamp": now(),
        "verdict": verdict,
        "stalled": bool(interruption.get("interrupted")),
        "stop_requested": stopped,
        "run_status": run_state.get("status"),
        "last_heartbeat": run_state.get("last_heartbeat"),
        "active_task": {k: active.get(k) for k in ("task", "status", "blocked_reason") if k in active},
    }
    print(verdict)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return code


def cmd_report_html(args):
    """CSV → 자립형 HTML 리포트(표+막대차트). 브라우저로 여는 산출물."""
    from pathlib import Path as _P
    from agent_ops.html_report import report_from_csv
    src = _P(args.input)
    if not src.exists():
        print(f"[report-html] 입력 파일 없음: {src}")
        return 1
    out_dir = _P("agent_ops/results/reports")
    path = report_from_csv(src, out_dir, title=(args.title or None))
    print(f"HTML 리포트 생성: {path}")
    print("브라우저로 열면 표/차트가 보입니다 (오프라인, 외부 리소스 없음).")
    return 0


def cmd_report_xlsx(args):
    """CSV → 서식 있는 .xlsx (Office 설치 불필요, openpyxl). 헤더 굵게/숫자 우측정렬."""
    from pathlib import Path as _P
    from agent_ops.html_report import build_from_csv
    from agent_ops.office_writer import write_xlsx
    src = _P(args.input)
    if not src.exists():
        print(f"[report-xlsx] 입력 파일 없음: {src}")
        return 1
    headers, rows, _ = build_from_csv(src)
    out = _P(args.out) if args.out else (_P("agent_ops/results/reports") / f"{src.stem}.xlsx")
    r = write_xlsx(out, headers, rows)
    if not r.get("ok"):
        print(f"[report-xlsx] 실패: {r.get('error')}\n  {r.get('hint','')}")
        return 1
    print(f"XLSX 생성: {r['path']}")
    return 0


def cmd_office_doc(args):
    """JSON 스펙 → .docx/.pptx (Office 설치 불필요, python-docx/pptx).

    docx 스펙: {"title","sections":[{heading,paragraphs[],bullets[],table:{headers,rows}}]}
    pptx 스펙: {"title","slides":[{title(=핵심 메시지),points[]}]}
    """
    from pathlib import Path as _P
    spec_path = _P(args.spec)
    if not spec_path.exists():
        print(f"[office-doc] 스펙 파일 없음: {spec_path}")
        return 1
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception as exc:
        print(f"[office-doc] 스펙 JSON 파싱 실패: {exc!r}")
        return 1
    title = str(spec.get("title") or "문서")
    out = _P(args.out) if args.out else (_P("agent_ops/results/reports") / f"{title}.{args.kind}")
    if args.kind == "docx":
        from agent_ops.office_writer import write_docx
        r = write_docx(out, title, spec.get("sections", []) or [])
    else:
        from agent_ops.office_writer import write_pptx
        r = write_pptx(out, spec.get("slides", []) or [], title=title)
    if not r.get("ok"):
        print(f"[office-doc] 실패: {r.get('error')}\n  {r.get('hint','')}")
        return 1
    print(f"{args.kind.upper()} 생성: {r['path']}")
    return 0


def cmd_routine(args):
    """검증된 작업을 저장→LLM 없이 재생. save(직전 성공 블록)/list/run."""
    from pathlib import Path as _P
    from agent_ops.lig_providers import DIAG_DIR
    from agent_ops import routines as R
    op = args.op
    if op == "list":
        items = R.list_routines()
        if not items:
            print("저장된 루틴이 없습니다. 작업을 성공시킨 뒤 'routine save <이름>'.")
            return 0
        for it in items:
            print(f"- {it['name']} (steps {it['steps']}, {it['created']})")
        return 0
    if op == "import":
        if not args.name:
            print("사용: routine import <프리셋.json>")
            return 2
        res = R.import_routine(_P(args.name))
        if not res.get("ok"):
            print(f"[routine import] {res.get('error')}")
            return 1
        print(f"프리셋 등록: {res['slug']} (단계 {res['step_count']}) → routine run 으로 재생")
        return 0
    if op == "save":
        if not args.name:
            print("사용: routine save <이름>")
            return 2
        steps = R.routine_from_history(DIAG_DIR)
        res = R.save_routine(args.name, steps, description=args.desc)
        if not res.get("ok"):
            print(f"[routine save] {res.get('error')}")
            return 1
        print(f"루틴 저장: {res['slug']} (단계 {res['step_count']}) → {res['path']}")
        print("재생: python agent_ops/agentops.py routine run \"" + args.name + "\"")
        return 0
    if op == "run":
        if not args.name:
            print("사용: routine run <이름>")
            return 2
        from agent_ops.tool_dispatch import ToolDispatcher
        disp = ToolDispatcher(_P.cwd())
        res = R.run_routine(args.name, disp)
        if res.get("ok"):
            print(f"루틴 재생 완료: {res['total']}단계 모두 성공")
            return 0
        print(f"루틴 재생 중단: {res.get('stopped_at')}단계에서 실패 — {res.get('reason')}")
        return 1
    return 2


def cmd_doc_template(args):
    """사내 정형 문서 템플릿(시험성적서/품질보고서/주간보고/회의록) → docx/HTML."""
    from pathlib import Path as _P
    from agent_ops.doc_templates import generate, TEMPLATES
    if args.kind not in TEMPLATES:
        print(f"[doc-template] 종류: {' | '.join(TEMPLATES)}")
        return 2
    out_dir = _P(args.out) if args.out else _P("agent_ops/results/reports")
    res = generate(args.kind, out_dir, input_csv=(args.input or None),
                   title=(args.title or None), as_html=args.html, note=args.note)
    if not res.get("ok"):
        print(f"[doc-template] 실패: {res.get('error')}" + (f"\n  {res.get('hint','')}" if res.get("hint") else ""))
        return 1
    print(f"{res.get('kind')} 생성({res.get('format')}): {res['path']}")
    return 0


def cmd_ocr(args):
    """화면 스크린샷 OCR(한/영) 또는 이미지 파일 OCR — 막힐 때 '화면을 눈으로' 읽는다."""
    from agent_ops.adapters import ocr_screen
    if getattr(args, "image", ""):
        res = ocr_screen.execute("read_image", {"path": args.image, "lang": args.lang})
    else:
        res = ocr_screen.execute("read_screen", {"lang": args.lang})
    if not res.get("ok"):
        print(f"[ocr] {res.get('error')}" + (f"\n  {res.get('hint','')}" if res.get("hint") else ""))
        return 1
    text = (res.get("text") or "").strip()
    print(text[:4000] if text else "(인식된 텍스트 없음)")
    if res.get("source_image"):
        print(f"\n[스크린샷: {res['source_image']}]", file=sys.stderr)
    return 0


def cmd_timeline(args):
    """audit.jsonl → 활동 타임라인 HTML(멈춤 의심 구간 강조). 무한대기 감시 시각화."""
    from pathlib import Path as _P
    from agent_ops.activity_timeline import build_timeline
    out_dir = _P("agent_ops/results/reports")
    path = build_timeline(out_dir, stall_gap=int(getattr(args, "gap", 600) or 600))
    print(f"활동 타임라인 생성: {path}")
    print("브라우저로 열면 활동·멈춤 의심 구간이 보입니다 (오프라인).")
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
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
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
    from agent_ops.knowledge_book import rebuild_quietly
    rebuild_quietly()   # 기억이 쌓일 때마다 지식책도 최신으로
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
        else:
            # 백업이 없던 신규 파일: 깨진 결과물을 디스크에 남기지 않는다.
            try:
                target.unlink()
            except Exception:
                pass
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
            print("  lig-api.env 를 채운 뒤 다시 실행하세요.", file=sys.stderr)
            return 2
        print("[real 모드] LIG gateway로 실제 요청을 보냅니다.")
        result = run_agent_loop(task, WS_ROOT, max_turns=args.max_turns,
                                capability_ids=capability_ids)

    out = RESULTS / "llm_responses" / "agent_cli_last.md"
    atomic_write_text(out, result.get("final_content", ""))
    print(f"결과: {result['outcome']}  (턴 {result['turns']}, 도구 실행 {len(result['tool_results'])}회)")
    if result.get("outcome") == "local_fallback":
        print("[게이트웨이 오류] 모든 제공자 폴백이 실패했습니다 — 네트워크/게이트웨이 상태를"
              " 확인한 뒤 다시 시도하세요.", file=sys.stderr)
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

    input_paths = list(getattr(args, "input", []) or [])
    risks = _work_risk_items(plan, bool(getattr(args, "execute", False)), input_paths)
    approval = request_approval(risks, assume_yes=bool(getattr(args, "yes", False)))
    _audit_work(run_id, task, "approval", "approved" if approval.get("approved") else "denied",
                approval.get("mode", ""), risk="dangerous" if approval.get("dangerous_count") else "safe")
    if not approval.get("approved"):
        print("승인 거부로 중단", file=sys.stderr)
        return 3

    if plan["artifact_kinds"]:
        mode = getattr(args, "mode", "mock")
        llm_client = None
        if mode == "real":
            from agent_ops.lig_providers import SECRET_ENV_PATH, validate_config
            cfg = validate_config()
            if cfg.get("ready"):
                from agent_ops.lig_runtime import chat_with_fallback
                capability_ids = [c["id"] for c in plan.get("capabilities", [])]
                def llm_client(prompt, _ids=capability_ids):
                    return chat_with_fallback([{"role": "user", "content": prompt}],
                                              capability_ids=_ids)
                print("[real 모드] 게이트웨이 LLM으로 산출물 내용을 채웁니다 (품질검사 통과분만 반영).")
            else:
                print("[real 모드] LIG provider 설정이 없어 서식(scaffold)만 생성합니다.", file=sys.stderr)
                for item in cfg.get("missing", []):
                    print(f"  - {item}", file=sys.stderr)
                print(f"  설정 파일: {SECRET_ENV_PATH} 를 채우면 내용까지 채워집니다.", file=sys.stderr)
        else:
            print("[mock 모드] 실제 모델 호출 없이 서식/규칙 기반으로 생성합니다 (--mode real 로 내용 채움).")
        # 축적된 규칙/교훈을 기계 주입 — 페르소나가 잊어도 반영된다 (복리 구조의 쐐기돌)
        memories_text = ""
        try:
            from agent_ops.memory_manager import (extract_keywords,
                                                  format_recall_for_prompt, recall)
            mem_items = recall(keywords=extract_keywords(task), limit=5)
            memories_text = format_recall_for_prompt(mem_items) if mem_items else ""
            if memories_text:
                print(f"축적된 기억 {len(mem_items)}건 반영 (recall)")
        except Exception:  # noqa: BLE001
            pass
        artifact_result = generate_artifacts(task, plan["artifact_kinds"],
                                             out_dir=RESULTS / "artifacts" / run_id,
                                             context=ctx,
                                             enrich=llm_client is not None,
                                             llm_client=llm_client,
                                             memories=memories_text or None,
                                             self_learn=True)
        enr = artifact_result.get("enrichment", {})
        if enr.get("requested"):
            print(f"LLM 내용 채움: {enr.get('status', '')}")
            for fb in enr.get("fallback", [])[:3]:
                print(f"  - {fb.get('file')}: {fb.get('reason')}")
        _print_artifact_result(plan, artifact_result, inputs)
        _audit_work(run_id, task, "artifacts", "approved" if artifact_result.get("ok") else "failed",
                    f"{len(artifact_result.get('files', []))} files")
        work_step = {"name": "artifacts", "verdict": "approved" if artifact_result.get("ok") else "failed"}
        adapter_summary = _adapter_execution_summary(plan, artifact_result,
                                                      bool(getattr(args, "execute", False)),
                                                      input_paths)
    else:
        agent_result = _run_agent_work(task, plan, getattr(args, "mode", "mock"))
        if agent_result.get("outcome") == "config_missing":
            from agent_ops.lig_providers import SECRET_ENV_PATH, validate_config
            print("[real 모드] LIG provider 설정이 준비되지 않았습니다.", file=sys.stderr)
            for item in validate_config().get("missing", []):
                print(f"  - {item}", file=sys.stderr)
            print(f"  설정 파일 위치: {SECRET_ENV_PATH}", file=sys.stderr)
            print("  lig-api.env 를 채운 뒤 다시 실행하세요.", file=sys.stderr)
            return 2
        if agent_result.get("outcome") == "local_fallback":
            print("[게이트웨이 오류] 모든 제공자 폴백이 실패했습니다 — 네트워크/게이트웨이 상태를"
                  " 확인한 뒤 다시 시도하세요. (진단: OpenCodeLIG_USERDATA\\diagnostics)", file=sys.stderr)
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
    ok = artifact_result.get("ok") and artifact_result.get("quality_ok", True)
    # 완료된 작업을 기억에 자동 적재 → 증류되어 Obsidian 위키에 정리(사용자 개입 없이).
    # 활동 기억은 low 우선순위라 사용자 규칙 회상을 밀어내지 않는다.
    if ok:
        try:
            from agent_ops.memory_manager import add_activity
            files = artifact_result.get("files", []) or []
            outcome = f"산출물 {len(files)}건" + (f": {os.path.basename(str(files[0]))}" if files else "") \
                + (f" (+{len(files) - 1})" if len(files) > 1 else "")
            add_activity(task, outcome)
        except Exception:  # noqa: BLE001 - 자동 적재 실패가 작업을 막으면 안 된다
            pass
    return 0 if ok else 1


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
    if action == "sync-outlook":
        from agent_ops.adapters import outlook_com
        result = outlook_com.execute("sync_calendar", {"days": args.days})
        if not result.get("ok"):
            print(result.get("error") or "Outlook 동기화 실패", file=sys.stderr)
            return 2
        print("Outlook 동기화: 추가 %d건, 중복/제외 %d건" % (
            len(result.get("added", [])), int(result.get("skipped", 0))))
        return 0
    return 2


def cmd_briefing(args):
    from agent_ops.secretary import build_briefing
    from agent_ops.knowledge_book import rebuild_quietly
    path, text = build_briefing()
    print(text)
    print(f"브리핑 저장: {path}")
    rebuild_quietly()   # 아침마다 지식책 자동 갱신 (리마인더 등록 시 무인 동작)
    return 0


def cmd_book(args):
    """지식책 생성(+열기). 기억 원장/위키/활동기록을 한 권의 HTML로 엮는다."""
    from agent_ops.knowledge_book import build_book
    path = build_book()
    print(f"지식책 생성: {path}")
    if getattr(args, "open", False) and os.name == "nt":
        os.startfile(str(path))  # noqa: S606
    return 0


def cmd_wiki(args):
    """LLM Wiki 운영: 주제 페이지 재통합 + lint(+선택 LLM 큐레이션)."""
    from agent_ops.wiki_manager import WIKI_DIR, consolidate, curate, lint
    stats = consolidate()
    print(f"위키 통합: 페이지 {stats['pages']}개 (갱신 {len(stats['updated'])}개, "
          f"원장 {stats['records']}건) — {WIKI_DIR}")
    report = lint()
    issues = (len(report["duplicates"]) + len(report["orphan_pages"])
              + len(report["stale_topics"]))
    if issues:
        print(f"lint: 중복 {len(report['duplicates'])} · 고아 {len(report['orphan_pages'])}"
              f" · 정체 {len(report['stale_topics'])} — wiki\\log.md 참고")
    else:
        print("lint: 이상 없음")
    if getattr(args, "curate", False):
        result = curate()
        print(f"LLM 큐레이션: 성공 {len(result['curated'])}개, 건너뜀 {len(result['skipped'])}개")
        for s in result["skipped"][:5]:
            print(f"  - {s['topic']}: {s['reason']}")
    from agent_ops.knowledge_book import rebuild_quietly
    rebuild_quietly()
    if getattr(args, "open", False) and os.name == "nt":
        os.startfile(str(WIKI_DIR / "index.md"))  # noqa: S606
    return 0


def cmd_weekly(args):
    from agent_ops.secretary import build_weekly_report
    path, text = build_weekly_report()
    print(text)
    print(f"주간보고 저장: {path}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="OpenCode AgentOps v3.1 Co-Growth Runtime")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init").set_defaults(func=cmd_init)
    p = sub.add_parser("status"); p.add_argument("--ko", action="store_true"); p.set_defaults(func=cmd_status)
    p = sub.add_parser("fix"); p.add_argument("--ko", action="store_true"); p.set_defaults(func=cmd_fix)
    sub.add_parser("dashboard").set_defaults(func=cmd_dashboard)
    sub.add_parser("resume").set_defaults(func=cmd_resume)
    p = sub.add_parser("watch"); p.add_argument("--max-age", dest="max_age", type=int, default=600); p.set_defaults(func=cmd_watch)
    p = sub.add_parser("report-html"); p.add_argument("--input", required=True); p.add_argument("--title", default=""); p.set_defaults(func=cmd_report_html)
    p = sub.add_parser("timeline"); p.add_argument("--gap", type=int, default=600); p.set_defaults(func=cmd_timeline)
    p = sub.add_parser("report-xlsx"); p.add_argument("--input", required=True); p.add_argument("--out", default=""); p.set_defaults(func=cmd_report_xlsx)
    p = sub.add_parser("office-doc"); p.add_argument("--kind", required=True, choices=["docx", "pptx"]); p.add_argument("--spec", required=True); p.add_argument("--out", default=""); p.set_defaults(func=cmd_office_doc)
    p = sub.add_parser("routine"); p.add_argument("op", choices=["save", "list", "run", "import"]); p.add_argument("name", nargs="?", default=""); p.add_argument("--desc", default=""); p.set_defaults(func=cmd_routine)
    p = sub.add_parser("ocr"); p.add_argument("--image", default=""); p.add_argument("--lang", default="korean+english"); p.set_defaults(func=cmd_ocr)
    p = sub.add_parser("doc-template"); p.add_argument("kind"); p.add_argument("--input", default=""); p.add_argument("--out", default=""); p.add_argument("--title", default=""); p.add_argument("--note", default=""); p.add_argument("--html", action="store_true"); p.set_defaults(func=cmd_doc_template)
    p = sub.add_parser("checkpoint"); p.add_argument("--note", default=""); p.set_defaults(func=cmd_checkpoint)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("verify").set_defaults(func=cmd_verify)
    sub.add_parser("report").set_defaults(func=cmd_report)
    sub.add_parser("selfheal").set_defaults(func=cmd_selfheal)
    p = sub.add_parser("log-failure"); p.add_argument("text", nargs="*"); p.set_defaults(func=cmd_log_failure)
    sub.add_parser("memorycheck").set_defaults(func=cmd_memorycheck)
    p = sub.add_parser("remember"); p.add_argument("text", nargs="*"); p.add_argument("--title", default="User instruction"); p.set_defaults(func=cmd_remember)
    p = sub.add_parser("recall"); p.add_argument("keywords", nargs="*"); p.add_argument("--kind", default=""); p.add_argument("--limit", type=int, default=6); p.set_defaults(func=cmd_recall)
    p = sub.add_parser("enqueue"); p.add_argument("title"); p.add_argument("--kind", default="manual"); p.add_argument("--owner", default="agent"); p.add_argument("--priority", type=int, default=5); p.add_argument("--risk", default="safe"); p.add_argument("--payload", default=""); p.add_argument("--touches", nargs="*", default=[]); p.set_defaults(func=cmd_enqueue)
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
    sp = sched.add_parser("sync-outlook"); sp.add_argument("--days", type=int, default=7); sp.set_defaults(func=cmd_schedule)
    sub.add_parser("briefing").set_defaults(func=cmd_briefing)
    sub.add_parser("weekly").set_defaults(func=cmd_weekly)
    p = sub.add_parser("book"); p.add_argument("--open", action="store_true"); p.set_defaults(func=cmd_book)
    p = sub.add_parser("wiki"); p.add_argument("--curate", action="store_true"); p.add_argument("--open", action="store_true"); p.set_defaults(func=cmd_wiki)
    p = sub.add_parser("safety-check"); p.add_argument("text", nargs="*"); p.set_defaults(func=cmd_safety_check)
    p = sub.add_parser("safe-write"); p.add_argument("target"); p.add_argument("content_file"); p.set_defaults(func=cmd_safe_write)
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        return cmd_status(args)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
