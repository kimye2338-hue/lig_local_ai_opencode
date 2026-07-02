# -*- coding: utf-8 -*-
"""Artifact generators: turn a task into openable, usable output files.

Each generator produces a scaffold the user can open, understand, and apply:
what it is for, how to run/import it, and which validation is still pending.
Generators are generic per artifact *kind* (macro, document, slide outline,
browser script, mail report) — the task text is embedded as context/TODO, not
pattern-matched into bespoke behavior.

All artifacts of one run share one ArtifactContext (run id, task summary,
sibling artifacts, pending items), so a report and its slide outline read as
parts of the same job, not unrelated files. Every generated set is checked by
artifact_quality before being reported OK.

Content filling: scaffolds are deterministic; generate_artifacts(enrich=True,
llm_client=...) lets an LLM fill the TODOs, but the filled file replaces the
scaffold only if it still passes the quality validator — otherwise the
scaffold is kept and the fallback is recorded. Real LLM fill via the company
gateway stays company validation pending; mock clients validate the path.

Output locations:
  results/artifacts/<run>/          user-facing outputs (default)
  results/capability_bench/         benchmark test outputs (tests pass out_dir)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .core import RESULTS, atomic_write_text
from .artifact_quality import validate_artifact_set, validate_files

ARTIFACTS_DIR = RESULTS / "artifacts"
BENCH_DIR = RESULTS / "capability_bench"

_PENDING_APP = "app validation pending: 실제 앱에서 실행/적용 후 결과를 확인하세요."


def build_artifact_context(task: str, plan: Optional[Dict[str, Any]] = None,
                           inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One shared context for every artifact of one run (dict-based on purpose).

    Generators embed it so sibling artifacts (report, slides, macro, ...)
    visibly belong to the same job: same run id, same task summary, same
    pending items — and, when `inputs` (input_ingest.ingest_inputs() result)
    is given, the same input evidence: file facts, notable/abnormal items,
    parsed mails. input_grounded stays False without readable input files, so
    artifacts can honestly distinguish "based on your data" from "task only".
    """
    if plan is None:
        from .capabilities import plan_task
        plan = plan_task(task)
    inputs = inputs or {}
    input_files = inputs.get("files", [])
    assumptions = ["산출물은 scaffold이며 사용자가 내용을 확정해야 합니다."]
    if input_files:
        assumptions.append(f"입력 자료 {len(input_files)}건의 요약/추출 내용을 근거로 사용합니다.")
    limitations = [f"미지원 입력: {u['name']} — {u['reason']}"
                   for u in inputs.get("unsupported", [])]
    limitations += [f"입력 오류: {e}" for e in inputs.get("errors", [])]
    return {
        "task": task,
        "run_id": time.strftime("%Y%m%d_%H%M%S"),
        "task_summary": plan.get("task_summary", task),
        "capabilities": [c["id"] for c in plan.get("capabilities", [])],
        "artifact_kinds": list(plan.get("artifact_kinds", [])),
        "inputs": {
            "files": input_files,
            "unsupported": inputs.get("unsupported", []),
            "facts": inputs.get("facts", []),
            "notable_items": inputs.get("notable_items", []),
            "mails": inputs.get("mails"),
        },
        "input_grounded": bool(input_files),
        "assumptions": assumptions,
        "limitations": limitations,
        "validation_status": "locally generated + quality validator 적용",
        "pending": list(plan.get("pending", [])),
    }


def _context_block(ctx: Dict[str, Any]) -> str:
    """Markdown block shared verbatim across a run's artifacts."""
    siblings = ", ".join(ctx.get("artifact_kinds", [])) or "-"
    lines = [
        "## 작업 컨텍스트 (이 작업의 모든 산출물이 공유)",
        "",
        f"- 실행 ID: {ctx['run_id']}",
        f"- 작업 요약: {ctx['task_summary']}",
        f"- 함께 생성되는 산출물: {siblings}",
        f"- 입력 자료: {_input_names(ctx)}",
        f"- 검증 상태: {ctx['validation_status']}",
    ]
    for item in (ctx.get("limitations") or [])[:4]:
        lines.append(f"- 제한: {item}")
    pending = ctx.get("pending") or []
    if pending:
        lines.append(f"- pending: {'; '.join(pending[:4])}")
    return "\n".join(lines)


def _input_names(ctx: Dict[str, Any]) -> str:
    files = (ctx.get("inputs") or {}).get("files", [])
    if not files:
        return "없음 (task 문장만으로 생성)"
    return ", ".join(f["name"] for f in files)


def _input_section(ctx: Dict[str, Any]) -> str:
    """Markdown '## 입력 자료' section; empty string when nothing was given."""
    inp = ctx.get("inputs") or {}
    if not inp.get("files") and not inp.get("unsupported"):
        return ""
    lines = ["## 입력 자료", ""]
    for f in inp.get("files", []):
        first = f["facts"][0] if f.get("facts") else f.get("type", "")
        lines.append(f"- `{f['name']}` ({f['size_bytes']:,} bytes): {first}")
    for u in inp.get("unsupported", []):
        lines.append(f"- `{u['name']}`: 지원되지 않는 형식 — {u['reason']} "
                     "(내용 미반영: 텍스트로 변환 후 다시 시도하세요)")
    return "\n".join(lines) + "\n\n"


def _ensure_context(task: str, ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return ctx if ctx else build_artifact_context(task)


def _detect_target_app(task: str) -> str:
    """Pick the VBA host app hinted by the task; 'generic' when unclear."""
    text = (task or "").lower()
    for app, kws in [
        ("solidworks", ["solidworks", "솔리드웍스", "좌표축", "어셈블리", "파트", "도면"]),
        ("excel", ["excel", "엑셀", "시트", "xlsx", "스프레드시트"]),
        ("word", ["word", "워드"]),
        ("powerpoint", ["powerpoint", "파워포인트", "ppt", "슬라이드"]),
    ]:
        if any(kw in text for kw in kws):
            return app
    return "generic"


_VBA_HOST_NOTES = {
    "solidworks": ("SolidWorks", "도구 > 매크로 > 편집(Alt+F8)에서 .bas를 불러오거나 새 매크로에 붙여넣기",
                   "SldWorks.Application / ActiveDoc 기준. 어셈블리/파트/도면에 따라 문서 타입 확인 필요. 좌표계 변경은 저장 전 반드시 백업."),
    "excel": ("Excel", "Alt+F11 (VBA 편집기) > 파일 > 파일 가져오기로 .bas import 후 Alt+F8로 실행",
              "적용 대상 시트/범위를 상단 상수로 지정. 실행 전 통합문서를 저장하고 사본에서 먼저 테스트."),
    "word": ("Word", "Alt+F11 > 파일 가져오기로 .bas import 후 매크로 실행",
             "ActiveDocument 기준. 실행 전 문서 저장."),
    "powerpoint": ("PowerPoint", "Alt+F11 > 파일 가져오기로 .bas import 후 매크로 실행",
                   "ActivePresentation 기준."),
    "generic": ("대상 앱", "해당 앱의 VBA 편집기에서 .bas import 후 실행",
                "대상 앱과 문서 타입을 먼저 확인하세요."),
}


# Per-app VBA bodies: real host-app structure (active-doc guard, doc-type
# branches, error handling) so the user fills in work logic, not boilerplate.
_VBA_BODIES = {
    "solidworks": """Option Explicit

' SolidWorks VBA — SldWorks 형식 라이브러리 참조 없이도 동작하는 late binding.
Dim swApp As Object    ' SldWorks.Application
Dim swModel As Object  ' ModelDoc2

Sub Main()
    On Error GoTo Fail
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Then
        MsgBox "열려 있는 SolidWorks 문서가 없습니다. 문서를 연 뒤 실행하세요.", vbExclamation
        Exit Sub
    End If

    ' 좌표계/형상 변경 전 반드시 사본을 저장하세요 (되돌리기 불가한 작업 있음).
    ' 문서 타입 (swDocumentTypes_e): 1=Part, 2=Assembly, 3=Drawing
    Select Case swModel.GetType
        Case 1 ' 파트
            ' TODO: 파트 작업 로직 (예: 기준 좌표계 선택 후 Feature 수정)
        Case 2 ' 어셈블리
            ' TODO: 어셈블리 작업 로직 (예: 컴포넌트 순회 - swModel.GetComponents)
        Case 3 ' 도면
            ' TODO: 도면 작업 로직
        Case Else
            MsgBox "지원하지 않는 문서 타입입니다.", vbExclamation
            Exit Sub
    End Select

    swModel.EditRebuild3
    MsgBox "작업 완료. 결과를 확인하고 이상 없으면 저장하세요.", vbInformation
    Exit Sub
Fail:
    MsgBox "오류 발생: " & Err.Number & " - " & Err.Description, vbCritical
End Sub
""",
    "excel": """Option Explicit

' 적용 대상 — 실행 전 반드시 확인/수정하세요.
Const TARGET_SHEET As String = "Sheet1"
Const TARGET_RANGE As String = "A1"     ' 데이터 시작 셀

Sub Main()
    On Error GoTo Fail
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Worksheets(TARGET_SHEET)

    Application.ScreenUpdating = False

    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, ws.Range(TARGET_RANGE).Column).End(xlUp).Row
    ' TODO: 실제 작업 로직 (예: 데이터 정리/정렬/서식/집계)
    ' Dim r As Long
    ' For r = ws.Range(TARGET_RANGE).Row To lastRow
    '     ...
    ' Next r

    Application.ScreenUpdating = True
    MsgBox "작업 완료 (" & TARGET_SHEET & ", 마지막 행: " & lastRow & ")", vbInformation
    Exit Sub
Fail:
    Application.ScreenUpdating = True
    MsgBox "오류 발생: " & Err.Number & " - " & Err.Description, vbCritical
End Sub
""",
    "word": """Option Explicit

Sub Main()
    On Error GoTo Fail
    If Documents.Count = 0 Then
        MsgBox "열려 있는 문서가 없습니다.", vbExclamation
        Exit Sub
    End If
    Dim doc As Document
    Set doc = ActiveDocument
    ' TODO: 실제 작업 로직 (예: doc.Paragraphs 순회, 찾기/바꾸기)
    MsgBox "작업 완료: " & doc.Name, vbInformation
    Exit Sub
Fail:
    MsgBox "오류 발생: " & Err.Number & " - " & Err.Description, vbCritical
End Sub
""",
    "powerpoint": """Option Explicit

Sub Main()
    On Error GoTo Fail
    If Presentations.Count = 0 Then
        MsgBox "열려 있는 프레젠테이션이 없습니다.", vbExclamation
        Exit Sub
    End If
    Dim pres As Presentation
    Set pres = ActivePresentation
    ' TODO: 실제 작업 로직 (예: pres.Slides 순회, 서식 일괄 적용)
    MsgBox "작업 완료: " & pres.Name & " (" & pres.Slides.Count & "장)", vbInformation
    Exit Sub
Fail:
    MsgBox "오류 발생: " & Err.Number & " - " & Err.Description, vbCritical
End Sub
""",
    "generic": """Option Explicit

Sub Main()
    On Error GoTo Fail
    ' TODO: 대상 앱을 확인한 뒤 작업 로직을 채우세요.
    MsgBox "OpenCodeLIG macro scaffold: 작업 로직을 채운 뒤 실행하세요.", vbInformation
    Exit Sub
Fail:
    MsgBox "오류 발생: " & Err.Number & " - " & Err.Description, vbCritical
End Sub
""",
}


def gen_vba_macro(task: str, out_dir: Path,
                  ctx: Optional[Dict[str, Any]] = None) -> List[Path]:
    ctx = _ensure_context(task, ctx)
    app = _detect_target_app(task)
    app_name, how_to_run, caution = _VBA_HOST_NOTES[app]
    body = f"""Attribute VB_Name = "OpenCodeLIG_Macro"
' =====================================================================
' OpenCodeLIG 생성 매크로 scaffold
' 요청 작업: {task}
' 작업 요약: {ctx['task_summary']}
' 입력 자료: {_input_names(ctx)}
' 실행 ID  : {ctx['run_id']} (같은 ID의 문서/슬라이드와 한 작업 세트)
' 대상 앱  : {app_name}
' 실행 방법: {how_to_run}
' 주의     : {caution}
' 상태     : static scaffold — {_PENDING_APP}
' =====================================================================
{_VBA_BODIES[app]}"""
    path = out_dir / f"macro_{app}.bas"
    atomic_write_text(path, body)
    return [path]


def gen_document(task: str, out_dir: Path,
                 ctx: Optional[Dict[str, Any]] = None) -> List[Path]:
    ctx = _ensure_context(task, ctx)
    inp = ctx.get("inputs") or {}
    grounded = ctx.get("input_grounded", False)
    notable = inp.get("notable_items", [])
    if grounded:
        status_lines = "\n".join(f"- {fact}" for fact in inp.get("facts", [])[:12]) \
            or "- (입력에서 추출된 요약 없음 — 파일 내용을 확인하세요)"
        core_lines = ("\n".join(f"- {n}" for n in notable[:8]) if notable
                      else "- 입력에서 특이/이상 항목이 자동 감지되지 않았습니다. 내용 확인 후 핵심을 채우세요.")
        conclusion = ("- 이상/주의 항목에 대한 판단과 권고를 한 줄로 정리하세요." if notable
                      else "- 입력 요약을 근거로 판단/권고를 한 줄로 정리하세요.")
        action_rows = "\n".join(
            f"| {i + 1} | {n} — 원인 확인 및 조치 |      |      |"
            for i, n in enumerate(notable[:5])) \
            or "| 1 | TODO: 입력 검토 결과에 따른 후속 조치 정의 |      |      |"
    else:
        status_lines = "- TODO: 현재 상태/데이터 요약"
        core_lines = "- TODO: 요청의 핵심 내용"
        conclusion = "- TODO: 판단/권고 한 줄 요약"
        action_rows = "| 1 | TODO: 후속 조치 정의 |      |      |"
    body = f"""# 작업 문서

- 요청: {task}
- 생성: {time.strftime('%Y-%m-%d %H:%M:%S')} (OpenCodeLIG)
- 상태: locally generated — 내용 확정 후 그대로 사용하거나 편집하세요.

{_context_block(ctx)}

{_input_section(ctx)}## 1. 개요

(요청 배경을 한 단락으로. real 모드에서는 LLM이 요청 내용을 기반으로 작성합니다.)

## 2. 목적

- 이 문서가 답해야 할 질문:
- 대상 독자:

## 3. 본문

### 3.1 현황

{status_lines}

### 3.2 핵심 내용

{core_lines}

## 4. 결론

{conclusion}

## 5. 액션 아이템

| # | 할 일 | 담당 | 기한 |
|---|------|------|------|
{action_rows}

## 참고

- 검토 후 필요한 형식(hwp/docx 등)으로 변환 — 해당 앱 변환은 app validation pending
"""
    path = out_dir / "문서.md"
    atomic_write_text(path, body)
    return [path]


def gen_slide_outline(task: str, out_dir: Path,
                      ctx: Optional[Dict[str, Any]] = None) -> List[Path]:
    ctx = _ensure_context(task, ctx)
    inp = ctx.get("inputs") or {}
    grounded = ctx.get("input_grounded", False)
    facts = inp.get("facts", [])
    notable = inp.get("notable_items", [])
    if grounded:
        ground_lines = ["## 입력 기반 핵심 요약", ""]
        ground_lines += [f"- {fact}" for fact in facts[:6]]
        ground_lines += [f"- 주의: {n}" for n in notable[:5]]
        ground_block = "\n".join(ground_lines) + "\n\n"
        slide3_points = facts[:3] or ["입력 요약을 여기에 채우세요"]
        slide4_points = ([f"주의/이상: {n}" for n in notable[:3]]
                         or ["입력에서 이상 항목 미감지 — 핵심 메시지를 채우세요"])
        slide4_message = (f"주의 항목 {len(notable)}건: 우선 확인/조치 필요" if notable
                          else "입력 데이터 기준 특이사항 없음 (확인 필요)")
    else:
        ground_block = ""
        slide3_points = ["TODO: 근거 데이터/현황 요약"]
        slide4_points = ["TODO: 요청 내용 기반 핵심 메시지"]
        slide4_message = "TODO: 이 발표의 핵심 한 문장"
    outline = f"""# 슬라이드 구성안

- 요청: {task}
- 상태: locally generated. .pptx 자동 생성은 dependency_or_app_pending
  (python-pptx 설치 또는 PowerPoint COM — release/dependencies.json 참고)

{_context_block(ctx)}

{ground_block}## 사용 방법

slide_spec.json의 슬라이드별 제목/핵심 메시지를 PowerPoint에 옮기거나,
python-pptx 확보 후 자동 변환하세요.

## 발표 흐름

도입(1~2장: 왜 이 발표인가) → 본론(3~4장: 근거와 핵심 내용) → 결론(5장: 요청/다음 단계).
슬라이드마다 "이 장이 전달할 한 문장(message)"을 먼저 정하고 본문을 채우세요.

## 구성

1. 표지 — 제목/발표자
2. 배경 및 목적
3. 현황/데이터
4. 핵심 내용 (요청 기반으로 채움)
5. 결론 및 다음 단계
"""
    spec = {
        "task": task,
        "status": "outline_only",
        "pptx_generation": "dependency_or_app_pending",
        "context": {"run_id": ctx["run_id"], "task_summary": ctx["task_summary"],
                    "related_artifacts": ctx.get("artifact_kinds", [])},
        "flow": ["도입", "본론", "결론"],
        "slides": [
            {"n": 1, "title": "표지", "message": "발표 주제 소개",
             "points": ["제목", "발표자/일자"]},
            {"n": 2, "title": "배경 및 목적", "message": "왜 이 작업이 필요한가",
             "points": ["요청 배경", "목표"]},
            {"n": 3, "title": "현황/데이터", "message": "지금 상태는 이렇다",
             "points": slide3_points},
            {"n": 4, "title": "핵심 내용", "message": slide4_message,
             "points": slide4_points},
            {"n": 5, "title": "결론 및 다음 단계", "message": "결정/요청 사항",
             "points": ["결론", "후속 조치"]},
        ],
    }
    p1 = out_dir / "slide_outline.md"
    p2 = out_dir / "slide_spec.json"
    atomic_write_text(p1, outline)
    atomic_write_text(p2, json.dumps(spec, ensure_ascii=False, indent=2))
    return [p1, p2]


def gen_browser_script(task: str, out_dir: Path,
                       ctx: Optional[Dict[str, Any]] = None) -> List[Path]:
    ctx = _ensure_context(task, ctx)
    url_match = re.search(r"https?://[^\s\"'<>]+", task or "")
    target_url = url_match.group(0) if url_match else "https://example.com"
    url_comment = ("요청에서 추출한 대상 페이지 — 실행 전 확인하세요" if url_match
                   else "TODO: 대상 페이지로 변경")
    body = f'''# -*- coding: utf-8 -*-
"""브라우저 자동화 scaffold (OpenCodeLIG 생성)

요청: {task}
작업 요약: {ctx['task_summary']}
입력 자료: {_input_names(ctx)}
실행 ID: {ctx['run_id']} (같은 ID의 산출물과 한 작업 세트)

실행 방법:
  py -3.11 browser_macro.py

상태: static scaffold — real browser validation pending.
기본 경로는 stdlib(urllib)로 페이지를 가져오는 것까지만 검증 가능하며,
실제 클릭/입력 자동화는 아래 중 하나를 채택해야 합니다:
  1) Chrome CDP:  chrome.exe --remote-debugging-port=9222 후 웹소켓 제어 (추가 설치 불필요)
  2) selenium:    chromedriver 필요 (release/dependencies.json 'chromedriver' 항목)
  3) playwright:  회사망 설치 정책 확인 필요

주의: 회사 웹메일/사내 시스템 로그인은 company validation pending.
      계정/비밀번호를 이 파일에 하드코딩하지 마세요.
"""
import urllib.request

TARGET_URL = "{target_url}"  # {url_comment}


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> None:
    html = fetch(TARGET_URL)
    print(f"fetched {{len(html)}} chars from {{TARGET_URL}}")
    # TODO: 파싱/자동화 로직 (CDP/selenium/playwright 채택 후 구현)


if __name__ == "__main__":
    main()
'''
    path = out_dir / "browser_macro.py"
    atomic_write_text(path, body)
    return [path]


# Sample inbox for mock-mode validation of the mail assistant workflow.
# Real webmail access stays company validation pending.
SAMPLE_INBOX = [
    {"from": "팀장", "subject": "주간 보고 취합 요청", "body": "금요일까지 주간 보고 제출 바랍니다."},
    {"from": "구매팀", "subject": "결재 요청: 시험 장비 구매", "body": "결재 문서 확인 부탁드립니다."},
    {"from": "noreply@newsletter", "subject": "[광고] 특가 안내", "body": "이번 주 특가 상품 안내."},
    {"from": "연구소", "subject": "회의 일정 변경 안내", "body": "내일 회의가 14시로 변경되었습니다."},
    {"from": "품질팀", "subject": "시험 성적서 검토 요청", "body": "첨부 성적서 검토 후 회신 바랍니다."},
]

_MAIL_RULES = [
    ("결재/승인", ["결재", "승인", "approval"]),
    ("회의/일정", ["회의", "일정", "meeting"]),
    ("보고/제출", ["보고", "제출", "report"]),
    ("검토 요청", ["검토", "확인", "회신", "review"]),
    ("광고/스팸", ["광고", "특가", "newsletter", "noreply"]),
]


def classify_mail(item: Dict[str, str]) -> str:
    text = (item.get("from", "") + " " + item.get("subject", "") + " " + item.get("body", "")).lower()
    for category, kws in _MAIL_RULES:
        if any(kw in text for kw in kws):
            return category
    return "기타"


# Categories that demand user action today, in priority order.
_ACTIONABLE = ["결재/승인", "보고/제출", "검토 요청", "회의/일정"]


def gen_mail_report(task: str, out_dir: Path,
                    ctx: Optional[Dict[str, Any]] = None,
                    inbox: Optional[List[Dict[str, str]]] = None) -> List[Path]:
    ctx = _ensure_context(task, ctx)
    provided = (ctx.get("inputs") or {}).get("mails") if inbox is None else None
    items = inbox if inbox is not None else (provided or SAMPLE_INBOX)
    if provided:
        basis = "입력 메일 목록 기반 — locally validated with provided input"
    else:
        basis = "locally validated with mock inbox"
    rows = []
    counts: Dict[str, int] = {}
    by_cat: Dict[str, List[Dict[str, str]]] = {}
    for item in items:
        cat = classify_mail(item)
        counts[cat] = counts.get(cat, 0) + 1
        by_cat.setdefault(cat, []).append(item)
        rows.append(f"| {cat} | {item.get('from','')} | {item.get('subject','')} | {item.get('body','')[:40]} |")
    summary = ", ".join(f"{k} {v}건" for k, v in counts.items())
    body = f"""# 메일 분류/요약 보고서

- 요청: {task}
- 메일 수: {len(items)}건 — {summary}
- 상태: {basis}.
  실제 웹메일 연동은 company validation pending (로그인/세션/사내망),
  브라우저 제어는 real browser validation pending.

{_context_block(ctx)}

| 분류 | 발신 | 제목 | 요약 |
|------|------|------|------|
{chr(10).join(rows)}

## 다음 조치

- 결재/보고/검토 항목부터 처리 권장. 광고/스팸은 무시 가능.
- 오늘 처리할 항목은 `액션아이템.md` 참고.
"""
    action_lines = []
    n = 0
    for cat in _ACTIONABLE:
        for item in by_cat.get(cat, []):
            n += 1
            action_lines.append(
                f"| {n} | {cat} | {item.get('subject','')} | {item.get('from','')} | 대기 |")
    actions = f"""# 오늘 처리할 액션 아이템

- 요청: {task}
- 실행 ID: {ctx['run_id']} (`메일_분류_보고서.md`와 한 작업 세트)
- 기준: 메일 분류 결과 중 조치가 필요한 분류({', '.join(_ACTIONABLE)})만 우선순위 순으로 추출.
- 상태: {basis} — 실제 메일함 기준 목록은 company validation pending.

| # | 분류 | 제목 | 발신 | 처리 |
|---|------|------|------|------|
{chr(10).join(action_lines) if action_lines else '| - | - | 조치 필요 메일 없음 | - | - |'}

처리 완료 시 '처리' 열을 완료로 바꿔서 관리하세요.
"""
    p1 = out_dir / "메일_분류_보고서.md"
    p2 = out_dir / "액션아이템.md"
    atomic_write_text(p1, body)
    atomic_write_text(p2, actions)
    return [p1, p2]


GENERATORS = {
    "vba_macro": gen_vba_macro,
    "document": gen_document,
    "slide_outline": gen_slide_outline,
    "browser_script": gen_browser_script,
    "mail_report": gen_mail_report,
}


# Only text artifacts the user edits are enrichable; specs (json) stay exact.
_ENRICHABLE_SUFFIXES = (".md", ".bas", ".py")


def _enrich_prompt(kind: str, task: str, scaffold: str) -> str:
    return (f"다음은 '{task}' 요청으로 생성된 {kind} scaffold입니다.\n"
            "TODO 항목을 요청에 맞는 실제 내용으로 채우세요.\n"
            "문서 구조(섹션/코드 골격), 안전 안내, 검증 상태/pending 표시는 그대로 유지해야 합니다.\n"
            "파일 전체를 다시 출력하세요.\n\n" + scaffold)


def _maybe_enrich(task: str, files_by_kind: Dict[str, List[str]], enrich: bool,
                  llm_client: Optional[Callable[[str], str]],
                  required_terms: Optional[List[str]] = None) -> Dict[str, Any]:
    """Optionally let an LLM fill scaffold TODOs — quality-gated, never lossy.

    A filled file replaces its scaffold only if the whole artifact set still
    passes the quality validator with the candidate swapped in; any failure
    (bad output, exception, missing client) keeps the scaffold and is recorded.
    """
    result: Dict[str, Any] = {"requested": bool(enrich), "applied": [],
                              "fallback": [], "status": ""}
    if not enrich:
        result["status"] = "not requested — deterministic scaffold 그대로 사용"
        return result
    if llm_client is None:
        result["status"] = ("skipped: llm_client 없음 — real LLM fill은 "
                            "company validation pending (LIG gateway)")
        return result
    for kind, paths in files_by_kind.items():
        names = [Path(p).name for p in paths]
        originals = {p: Path(p).read_text(encoding="utf-8") for p in paths}
        for p in paths:
            path = Path(p)
            if path.suffix not in _ENRICHABLE_SUFFIXES:
                continue
            try:
                candidate = llm_client(_enrich_prompt(kind, task, originals[p]))
            except Exception as exc:
                result["fallback"].append(
                    {"file": path.name, "reason": f"llm error: {exc!r}"[:200]})
                continue
            texts = [candidate if q == p else originals[q] for q in paths]
            verdict = validate_artifact_set(kind, [t or "" for t in texts], task, names,
                                            required_terms=required_terms or [])
            if verdict["ok"]:
                atomic_write_text(path, candidate)
                result["applied"].append(path.name)
            else:
                failed = ", ".join(v["rule"] for v in verdict["violations"][:5])
                result["fallback"].append(
                    {"file": path.name,
                     "reason": f"quality validator rejected: {failed}"})
    result["status"] = (f"applied {len(result['applied'])} file(s), "
                        f"fallback {len(result['fallback'])} file(s) — "
                        "실패한 파일은 scaffold 유지")
    return result


def _record_enrich_diag(task: str, enrichment: Dict[str, Any]) -> None:
    """Secret-free enrichment trace for diagnostics; never fails the caller."""
    try:
        from .lig_providers import DIAG_DIR
        DIAG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "task": task, **enrichment}
        (DIAG_DIR / "artifact-enrich-last.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def generate_artifacts(task: str, kinds: List[str],
                       out_dir: Optional[Path] = None,
                       context: Optional[Dict[str, Any]] = None,
                       enrich: bool = False,
                       llm_client: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
    """Generate scaffolds for the given kinds; never raises per-kind.

    Default out_dir is a per-run folder under results/artifacts/ so user
    outputs never mix with test/bench outputs. All kinds share one
    ArtifactContext; every generated set is quality-validated ("quality"),
    and enrich=True routes files through the LLM fill path ("enrichment").
    """
    target = Path(out_dir) if out_dir else ARTIFACTS_DIR / time.strftime("%Y%m%d_%H%M%S")
    target.mkdir(parents=True, exist_ok=True)
    ctx = dict(context) if context else build_artifact_context(task)
    ctx.setdefault("run_id", time.strftime("%Y%m%d_%H%M%S"))
    files: List[str] = []
    errors: List[str] = []
    files_by_kind: Dict[str, List[str]] = {}
    for kind in kinds:
        fn = GENERATORS.get(kind)
        if fn is None:
            errors.append(f"unknown artifact kind: {kind}")
            continue
        try:
            made = [str(p) for p in fn(task, target, ctx)]
            files.extend(made)
            files_by_kind[kind] = made
        except Exception as exc:
            errors.append(f"{kind}: {exc!r}"[:300])
    # Input-grounding anchors: if this run claims to be based on user inputs,
    # every input file name must actually appear in the generated set.
    required_terms: List[str] = []
    if ctx.get("input_grounded"):
        required_terms = [f["name"] for f in ctx.get("inputs", {}).get("files", [])]
    quality = {kind: validate_files(kind, paths, task, required_terms=required_terms)
               for kind, paths in files_by_kind.items()}
    quality_ok = all(v["ok"] for v in quality.values()) if quality else True
    enrichment = _maybe_enrich(task, files_by_kind, enrich, llm_client,
                               required_terms=required_terms)
    if enrichment["requested"]:
        _record_enrich_diag(task, enrichment)
    return {"ok": not errors, "out_dir": str(target), "files": files,
            "errors": errors, "quality": quality, "quality_ok": quality_ok,
            "input_grounded": bool(required_terms) and quality_ok,
            "enrichment": enrichment,
            "context": {"run_id": ctx["run_id"],
                        "task_summary": ctx.get("task_summary", task),
                        "input_files": [f["name"] for f in ctx.get("inputs", {}).get("files", [])]}}
