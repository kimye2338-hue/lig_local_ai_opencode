# -*- coding: utf-8 -*-
"""General-purpose capability inventory: what OpenCodeLIG can do right now.

This is NOT a per-task feature list. Each capability describes a class of
office/engineering work, its current validation status, which artifact kinds
it can produce, and what remains pending (app / company validation). New work
types are added by extending CAPABILITIES — no if/else per user phrasing.

classify_task() routes a free-form Korean/English request to capabilities by
keyword scoring; artifact generation itself lives in artifact_generators.py.
Status vocabulary (keep consistent with reports):
  locally_validated       proven by local tests without external apps
  locally_validated_with_mock  proven only against mock transport/data
  scaffold_available      generates a usable artifact; final validation pending
"""
from __future__ import annotations

from typing import Any, Dict, List

# capability id -> spec. keywords are matched case-insensitively as substrings
# of the task text; they route work, they do not implement it.
CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "file_ops": {
        "description": "워크스페이스 파일 읽기/쓰기/검색/수정",
        "status": "locally_validated",
        "tools": ["read_file", "write_file", "append_file", "replace_in_file",
                  "list_dir", "search_files", "run_diagnostic"],
        "artifact_kinds": [],
        "outputs": ["임의 텍스트 파일"],
        "pending": [],
        "keywords": ["파일", "읽고", "읽어", "수정", "정리해", "분류해", "찾아",
                     "file", "read", "edit"],
    },
    "document_generation": {
        "description": "문서/보고서/요약 산출물 생성 (.md/.txt)",
        "status": "locally_validated",
        "artifact_kinds": ["document"],
        "outputs": [".md", ".txt"],
        "pending": [],
        "keywords": ["문서", "보고서", "작성", "요약", "정리", "메모",
                     "document", "report", "summary", "write up"],
    },
    "macro_generation": {
        "description": "앱 매크로 코드 생성 (VBA .bas 등) — 실행은 해당 앱 필요",
        "status": "scaffold_available",
        "artifact_kinds": ["vba_macro"],
        "outputs": [".bas", ".vba", ".py", ".bat"],
        "pending": ["app validation pending: 생성된 매크로의 실제 앱 실행 검증"],
        "keywords": ["매크로", "macro", "vba", "자동화 스크립트", "automation script"],
    },
    "spreadsheet_generation": {
        "description": "표/CSV/Excel VBA 산출물 생성",
        "status": "scaffold_available",
        "artifact_kinds": ["vba_macro", "document"],
        "outputs": [".csv", ".bas", ".md plan"],
        "pending": ["xlsx 직접 생성: dependency_or_app_pending (openpyxl 또는 Excel COM)",
                    "app validation pending: Excel에서 매크로 실행"],
        "keywords": ["엑셀", "excel", "xlsx", "스프레드시트", "시트", "csv", "표로",
                     "spreadsheet"],
    },
    "presentation_generation": {
        "description": "PPT 슬라이드 구성안/스펙 생성",
        "status": "scaffold_available",
        "artifact_kinds": ["slide_outline"],
        "outputs": ["slide_outline.md", "slide_spec.json"],
        "pending": ["pptx 직접 생성: dependency_or_app_pending (python-pptx 또는 PowerPoint COM)"],
        "keywords": ["ppt", "피피티", "파워포인트", "powerpoint", "슬라이드", "발표자료",
                     "presentation", "slide"],
    },
    "browser_automation": {
        "description": "브라우저 자동화 스크립트/절차 scaffold 생성",
        "status": "scaffold_available",
        "artifact_kinds": ["browser_script"],
        "outputs": ["python CDP/selenium/playwright scaffold (.py)"],
        "pending": ["real browser validation pending: 실제 Chrome 제어 검증",
                    "dependency pending: selenium/playwright 채택 시 manifest 반영"],
        "keywords": ["브라우저", "크롬", "chrome", "browser", "웹페이지", "웹 자동화",
                     "selenium", "playwright", "크롤링", "스크래핑"],
    },
    "web_mail_assistant": {
        "description": "메일 확인/분류/요약 비서 워크플로 (현재 mock inbox 기준)",
        "status": "locally_validated_with_mock",
        "artifact_kinds": ["mail_report", "browser_script"],
        "outputs": ["메일 분류/요약 보고서 (.md)"],
        "pending": ["company validation pending: 실제 웹메일 로그인/세션",
                    "real browser validation pending"],
        "keywords": ["메일", "mail", "이메일", "email", "inbox", "받은편지함", "수신함"],
    },
    "office_cad_automation": {
        "description": "Office/CAD 앱 자동화 (SolidWorks/Excel/Word/PowerPoint/HWP) — 매크로/절차 산출물",
        "status": "scaffold_available",
        "artifact_kinds": ["vba_macro", "document"],
        "outputs": ["SolidWorks VBA", "Excel VBA", "자동화 절차 문서"],
        "pending": ["app validation pending: SolidWorks/Office/HWP 실제 실행",
                    "dependency pending: COM 제어 채택 시 pywin32"],
        "keywords": ["solidworks", "솔리드웍스", "cad", "좌표", "어셈블리", "파트",
                     "도면", "word", "워드", "한글파일", "hwp", "com 자동화"],
    },
}

# Fallback when no keyword matches: the agent can always read/write files and
# produce a document, so route unknown office tasks there.
DEFAULT_CAPABILITIES = ["file_ops", "document_generation"]


def classify_task(task: str) -> List[str]:
    """Route a free-form task to capability ids, best match first.

    Keyword scoring only — deliberately simple so weak models and tests get
    deterministic routing. Returns DEFAULT_CAPABILITIES when nothing matches.
    """
    text = (task or "").lower()
    scored = []
    for cap_id, spec in CAPABILITIES.items():
        score = sum(1 for kw in spec["keywords"] if kw in text)
        if score > 0:
            scored.append((score, cap_id))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [cap_id for _, cap_id in scored] or list(DEFAULT_CAPABILITIES)


def plan_task(task: str) -> Dict[str, Any]:
    """task -> capabilities -> artifact kinds -> pending items (no execution)."""
    cap_ids = classify_task(task)
    artifact_kinds: List[str] = []
    pending: List[str] = []
    for cap_id in cap_ids:
        spec = CAPABILITIES[cap_id]
        for kind in spec["artifact_kinds"]:
            if kind not in artifact_kinds:
                artifact_kinds.append(kind)
        for item in spec["pending"]:
            if item not in pending:
                pending.append(item)
    return {
        "task": task,
        "capabilities": [
            {"id": c, "status": CAPABILITIES[c]["status"],
             "description": CAPABILITIES[c]["description"]}
            for c in cap_ids
        ],
        "artifact_kinds": artifact_kinds,
        "pending": pending,
        "note": "산출물 생성은 로컬에서 수행되며, 앱/회사망이 필요한 검증은 pending으로 표시됩니다.",
    }


def capability_summary() -> Dict[str, Any]:
    """Secret-free inventory for doctor/diagnostics ('뭐 할 수 있어?')."""
    return {
        cap_id: {
            "description": spec["description"],
            "status": spec["status"],
            "outputs": spec["outputs"],
            "pending": spec["pending"],
        }
        for cap_id, spec in CAPABILITIES.items()
    }
