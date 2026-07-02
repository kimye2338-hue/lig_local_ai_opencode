# -*- coding: utf-8 -*-
"""Artifact generators: turn a task into openable, usable output files.

Each generator produces a scaffold the user can open, understand, and apply:
what it is for, how to run/import it, and which validation is still pending.
Generators are generic per artifact *kind* (macro, document, slide outline,
browser script, mail report) — the task text is embedded as context/TODO, not
pattern-matched into bespoke behavior. Real content comes from the LLM in
real mode; these scaffolds keep the pipeline working without any dependency.

Output locations:
  results/artifacts/<run>/          user-facing outputs (default)
  results/capability_bench/         benchmark test outputs (tests pass out_dir)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import RESULTS, atomic_write_text

ARTIFACTS_DIR = RESULTS / "artifacts"
BENCH_DIR = RESULTS / "capability_bench"

_PENDING_APP = "app validation pending: 실제 앱에서 실행/적용 후 결과를 확인하세요."


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


def gen_vba_macro(task: str, out_dir: Path) -> List[Path]:
    app = _detect_target_app(task)
    app_name, how_to_run, caution = _VBA_HOST_NOTES[app]
    body = f"""Attribute VB_Name = "OpenCodeLIG_Macro"
' =====================================================================
' OpenCodeLIG 생성 매크로 scaffold
' 요청 작업: {task}
' 대상 앱  : {app_name}
' 실행 방법: {how_to_run}
' 주의     : {caution}
' 상태     : static scaffold — {_PENDING_APP}
' =====================================================================
Option Explicit

Sub Main()
    ' TODO: 아래에 실제 작업 로직을 채우세요.
    ' real 모드에서는 LLM이 이 scaffold를 요청 내용에 맞게 완성합니다.
    MsgBox "OpenCodeLIG macro scaffold: 작업 로직을 채운 뒤 실행하세요.", vbInformation
End Sub
"""
    path = out_dir / f"macro_{app}.bas"
    atomic_write_text(path, body)
    return [path]


def gen_document(task: str, out_dir: Path) -> List[Path]:
    body = f"""# 작업 문서

- 요청: {task}
- 생성: {time.strftime('%Y-%m-%d %H:%M:%S')} (OpenCodeLIG)
- 상태: locally generated — 내용 확정 후 그대로 사용하거나 편집하세요.

## 개요

(real 모드에서는 LLM이 요청 내용을 기반으로 본문을 작성합니다.)

## 본문

- TODO: 핵심 내용

## 다음 단계

- 검토 후 필요한 형식(hwp/docx 등)으로 변환 — 해당 앱 변환은 app validation pending
"""
    path = out_dir / "문서.md"
    atomic_write_text(path, body)
    return [path]


def gen_slide_outline(task: str, out_dir: Path) -> List[Path]:
    outline = f"""# 슬라이드 구성안

- 요청: {task}
- 상태: locally generated. .pptx 자동 생성은 dependency_or_app_pending
  (python-pptx 설치 또는 PowerPoint COM — release/dependencies.json 참고)

## 사용 방법

slide_spec.json의 슬라이드별 제목/핵심 메시지를 PowerPoint에 옮기거나,
python-pptx 확보 후 자동 변환하세요.

## 구성

1. 표지 — 제목/발표자
2. 배경 및 목적
3. 핵심 내용 (요청 기반으로 채움)
4. 결론 및 다음 단계
"""
    spec = {
        "task": task,
        "status": "outline_only",
        "pptx_generation": "dependency_or_app_pending",
        "slides": [
            {"n": 1, "title": "표지", "points": ["제목", "발표자/일자"]},
            {"n": 2, "title": "배경 및 목적", "points": ["요청 배경", "목표"]},
            {"n": 3, "title": "핵심 내용", "points": ["TODO: 요청 내용 기반 핵심 메시지"]},
            {"n": 4, "title": "결론 및 다음 단계", "points": ["결론", "후속 조치"]},
        ],
    }
    p1 = out_dir / "slide_outline.md"
    p2 = out_dir / "slide_spec.json"
    atomic_write_text(p1, outline)
    atomic_write_text(p2, json.dumps(spec, ensure_ascii=False, indent=2))
    return [p1, p2]


def gen_browser_script(task: str, out_dir: Path) -> List[Path]:
    body = f'''# -*- coding: utf-8 -*-
"""브라우저 자동화 scaffold (OpenCodeLIG 생성)

요청: {task}

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

TARGET_URL = "https://example.com"  # TODO: 대상 페이지로 변경


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


def gen_mail_report(task: str, out_dir: Path,
                    inbox: Optional[List[Dict[str, str]]] = None) -> List[Path]:
    items = inbox if inbox is not None else SAMPLE_INBOX
    rows = []
    counts: Dict[str, int] = {}
    for item in items:
        cat = classify_mail(item)
        counts[cat] = counts.get(cat, 0) + 1
        rows.append(f"| {cat} | {item.get('from','')} | {item.get('subject','')} | {item.get('body','')[:40]} |")
    summary = ", ".join(f"{k} {v}건" for k, v in counts.items())
    body = f"""# 메일 분류/요약 보고서

- 요청: {task}
- 메일 수: {len(items)}건 — {summary}
- 상태: locally validated with mock inbox.
  실제 웹메일 연동은 company validation pending (로그인/세션/사내망),
  브라우저 제어는 real browser validation pending.

| 분류 | 발신 | 제목 | 요약 |
|------|------|------|------|
{chr(10).join(rows)}

## 다음 조치

- 결재/보고/검토 항목부터 처리 권장. 광고/스팸은 무시 가능.
"""
    path = out_dir / "메일_분류_보고서.md"
    atomic_write_text(path, body)
    return [path]


GENERATORS = {
    "vba_macro": gen_vba_macro,
    "document": gen_document,
    "slide_outline": gen_slide_outline,
    "browser_script": gen_browser_script,
    "mail_report": gen_mail_report,
}


def generate_artifacts(task: str, kinds: List[str],
                       out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Generate scaffolds for the given kinds; never raises per-kind.

    Default out_dir is a per-run folder under results/artifacts/ so user
    outputs never mix with test/bench outputs.
    """
    target = Path(out_dir) if out_dir else ARTIFACTS_DIR / time.strftime("%Y%m%d_%H%M%S")
    target.mkdir(parents=True, exist_ok=True)
    files: List[str] = []
    errors: List[str] = []
    for kind in kinds:
        fn = GENERATORS.get(kind)
        if fn is None:
            errors.append(f"unknown artifact kind: {kind}")
            continue
        try:
            files.extend(str(p) for p in fn(task, target))
        except Exception as exc:
            errors.append(f"{kind}: {exc!r}"[:300])
    return {"ok": not errors, "out_dir": str(target), "files": files, "errors": errors}
