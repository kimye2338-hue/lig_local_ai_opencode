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

from typing import Any, Callable, Dict, List, Optional

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
        "keywords": ["문서", "보고서", "작성", "요약", "정리", "메모", "설명서",
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
                     "표 정리", "표를", "데이터 정리", "spreadsheet"],
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
    "schedule_management": {
        "description": "일정/마감/약속 등록·조회·완료 처리",
        "status": "locally_validated",
        "artifact_kinds": [],
        "outputs": ["agent_ops/state schedule store"],
        "pending": [],
        "keywords": ["일정", "약속", "마감", "리마인드", "캘린더", "스케줄", "미루", "연기",
                     "schedule", "deadline"],
    },
    "meeting_minutes": {
        "description": "회의 메모/녹취 텍스트를 구조화된 회의록과 일정 등록 제안으로 정리",
        "status": "locally_validated",
        "artifact_kinds": ["meeting_minutes"],
        "outputs": ["회의록.md"],
        "pending": [],
        "keywords": ["회의록", "회의 정리", "미팅 정리", "회의 내용", "meeting minutes", "미팅노트"],
    },
    "weekly_report": {
        "description": "지난 7일의 audit/schedule/artifacts 기록으로 주간보고 초안 생성",
        "status": "locally_validated",
        "artifact_kinds": ["document"],
        "outputs": ["weekly_<YYYYMMDD>.md"],
        "pending": [],
        "keywords": ["주간보고", "주간 보고", "위클리", "weekly report"],
    },
    "matlab_automation": {
        "description": "시험 데이터 후처리용 MATLAB 스크립트 scaffold 생성",
        "status": "scaffold_available",
        "artifact_kinds": ["matlab_script"],
        "outputs": [".m"],
        "pending": ["app validation pending: MATLAB 2024a에서 -batch 실행 검증"],
        "keywords": ["매트랩", "matlab", "후처리", "플롯", "그래프 그려", ".m 스크립트", ".m 파일"],
    },
    "simulation_automation": {
        "description": "ANSYS/Fluent 해석 실행 절차 scaffold 생성 — 공학 판단은 사용자 책임",
        "status": "scaffold_available",
        "artifact_kinds": ["fluent_journal", "ansys_script"],
        "outputs": ["Fluent journal (.jou)", "Mechanical/SpaceClaim script scaffold (.py)"],
        "pending": ["app validation pending: ANSYS 2024R1 Fluent -g -i 실행 검증",
                    "app validation pending: Mechanical/SpaceClaim GUI 스크립팅 콘솔 실행 검증"],
        "keywords": ["앤시스", "ansys", "플루언트", "fluent", "시뮬레이션",
                     "메카니컬", "spaceclaim", "icepak", "cfd", "fea"],
    },
    "office_cad_automation": {
        "description": "Office/CAD 앱 자동화 (SolidWorks/Excel/Word/PowerPoint/HWP) — 매크로/절차 산출물",
        "status": "scaffold_available",
        "artifact_kinds": ["vba_macro", "autocad_script", "document"],
        "outputs": ["SolidWorks VBA", "Excel VBA", "자동화 절차 문서"],
        "pending": ["app validation pending: SolidWorks/Office/HWP 실제 실행",
                    "app validation pending: AutoCAD 2019 accoreconsole 실제 실행",
                    "dependency pending: COM 제어 채택 시 pywin32"],
        "keywords": ["solidworks", "솔리드웍스", "cad", "좌표", "어셈블리", "파트",
                     "도면", "word", "워드", "한글파일", "hwp", "com 자동화"],
    },
}

# Fallback when no keyword matches: the agent can always read/write files and
# produce a document, so route unknown office tasks there.
DEFAULT_CAPABILITIES = ["file_ops", "document_generation"]

# Planning metadata per artifact kind: which file(s) the kind yields and what
# the user gets from it. Actual filenames are owned by artifact_generators.py.
ARTIFACT_KIND_INFO: Dict[str, Dict[str, str]] = {
    "vba_macro": {
        "files": "macro_<app>.bas",
        "purpose": "대상 앱(SolidWorks/Excel/Word/PowerPoint)에서 import해 실행하는 VBA 매크로 scaffold",
    },
    "document": {
        "files": "문서.md",
        "purpose": "개요/목적/본문/결론/액션아이템 구조의 보고서 초안",
    },
    "slide_outline": {
        "files": "slide_outline.md, slide_spec.json",
        "purpose": "발표 흐름과 장별 핵심 메시지가 담긴 슬라이드 구성안",
    },
    "browser_script": {
        "files": "browser_macro.py",
        "purpose": "CDP/selenium/playwright 선택 기준이 담긴 브라우저 자동화 scaffold",
    },
    "mail_report": {
        "files": "메일_분류_보고서.md, 액션아이템.md",
        "purpose": "메일 분류/요약 보고서와 오늘 처리할 액션아이템 목록",
    },
    "matlab_script": {
        "files": "작업.m",
        "purpose": "MATLAB 2024a -batch로 실행할 시험 데이터 후처리 scaffold",
    },
    "autocad_script": {
        "files": "작업.scr",
        "purpose": "AutoCAD 2019 accoreconsole에서 /i 사본 dwg와 함께 실행할 script scaffold",
    },
    "fluent_journal": {
        "files": "작업.jou",
        "purpose": "ANSYS Fluent 2024R1에서 fluent 3ddp -g -i 작업.jou -t<코어수>로 실행할 journal scaffold",
    },
    "ansys_script": {
        "files": "mechanical_script.py",
        "purpose": "ANSYS Mechanical/SpaceClaim GUI 스크립팅 콘솔에서 실행할 ACT/IronPython scaffold",
    },
    "meeting_minutes": {
        "files": "회의록.md",
        "purpose": "회의 메모/녹취를 개요, 논의, 결정, 액션아이템, 일정 등록 제안으로 정리한 회의록",
    },
}


def _match_capabilities(task: str) -> List[Dict[str, Any]]:
    """Keyword scoring per capability, best match first, with evidence.

    Deterministic on purpose so weak models and tests get stable routing.
    Composite requests ("...읽고 표 정리해서 보고서랑 PPT...") naturally match
    several capabilities and are decomposed into all of them.
    """
    text = (task or "").lower()
    scored = []
    for cap_id, spec in CAPABILITIES.items():
        hits = [kw for kw in spec["keywords"] if kw in text]
        if hits:
            scored.append((len(hits), cap_id, hits))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [
        {"id": cap_id, "matched_keywords": hits,
         "confidence": "high" if score >= 2 else "medium"}
        for score, cap_id, hits in scored
    ]


def classify_task(task: str) -> List[str]:
    """Route a free-form task to capability ids, best match first.

    Returns DEFAULT_CAPABILITIES when nothing matches.
    """
    matches = _match_capabilities(task)
    return [m["id"] for m in matches] or list(DEFAULT_CAPABILITIES)


# A semantic planner receives (task, keyword_matches) and may return a
# replacement match list in the same shape as _match_capabilities() output.
SemanticPlanner = Callable[[str, List[Dict[str, Any]]], List[Dict[str, Any]]]


def plan_task(task: str, planner: Optional[SemanticPlanner] = None) -> Dict[str, Any]:
    """task -> capabilities -> artifact plan -> validation plan (no execution).

    Each capability entry carries its routing evidence (matched_keywords) and
    a confidence tag so a misrouted request is diagnosable, not silent.

    `planner` is the hook for a future semantic (LLM) planner: anything it
    returns that is invalid — unknown capability ids, empty list, exception —
    falls back to keyword routing, so routing never breaks because a smarter
    planner misbehaved. Real LLM planning stays company validation pending;
    the resulting mode is recorded in plan["planner_mode"].
    """
    matches = _match_capabilities(task)
    routing = "keyword_match"
    planner_mode = "deterministic_keyword"
    if planner is not None:
        try:
            proposed = planner(task, list(matches))
            valid = [m for m in (proposed or []) if m.get("id") in CAPABILITIES]
        except Exception as exc:
            valid = []
            planner_mode = f"deterministic_keyword (semantic planner failed: {type(exc).__name__})"
        else:
            if valid:
                matches = [{"id": m["id"],
                            "matched_keywords": list(m.get("matched_keywords", [])),
                            "confidence": m.get("confidence", "medium")}
                           for m in valid]
                routing = "semantic"
                planner_mode = "semantic"
            else:
                planner_mode = "deterministic_keyword (semantic planner returned nothing usable)"
    if not matches:
        routing = "default_fallback"
        matches = [{"id": c, "matched_keywords": [], "confidence": "low"}
                   for c in DEFAULT_CAPABILITIES]
    if (matches and matches[0]["id"] == "schedule_management"
            and matches[0].get("confidence") == "high"):
        matches = [matches[0]]
    cap_ids = [m["id"] for m in matches]
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
    # Split what the user can finish on this PC from what needs the company
    # network — the two blockers are different people/actions.
    company_pending = [p for p in pending if "company" in p]
    app_pending = [p for p in pending if "company" not in p]
    if routing == "default_fallback":
        task_summary = (f"'{task}' 요청이 알려진 업무 유형과 매칭되지 않았습니다. "
                        "기본 파일/문서 처리로 안전하게 계획합니다 (low confidence — 추정일 수 있음).")
    else:
        task_summary = (f"요청을 {len(cap_ids)}개 업무 영역({', '.join(cap_ids)})으로 분해, "
                        f"산출물 {len(artifact_kinds)}종 생성 계획.")
    artifact_plan = [
        {"kind": kind,
         "files": ARTIFACT_KIND_INFO.get(kind, {}).get("files", ""),
         "purpose": ARTIFACT_KIND_INFO.get(kind, {}).get("purpose", ""),
         "from_capabilities": [c for c in cap_ids
                               if kind in CAPABILITIES[c]["artifact_kinds"]]}
        for kind in artifact_kinds
    ]
    safe_task = task.replace('"', "'")
    if cap_ids == ["schedule_management"]:
        next_cmd = f'py -3.11 agent_ops\\agentops.py schedule add "{safe_task}"'
    elif artifact_kinds:
        next_cmd = f'py -3.11 agent_ops\\agentops.py plan --task "{safe_task}" --make-artifacts'
    else:
        next_cmd = f'py -3.11 agent_ops\\agentops.py agent --mode mock --task "{safe_task}"'
    validation_plan = (
        ["local: 산출물 생성 + artifact quality validator 통과 (자동)",
         "user: 생성 파일을 열어 TODO를 확정하고 내용 검토"]
        + [f"app: {p}" for p in app_pending]
        + [f"company: {p}" for p in company_pending]
    )
    return {
        "task": task,
        "task_summary": task_summary,
        "routing": routing,
        "planner_mode": planner_mode,
        "capabilities": [
            {"id": m["id"], "status": CAPABILITIES[m["id"]]["status"],
             "description": CAPABILITIES[m["id"]]["description"],
             "confidence": m["confidence"],
             "matched_keywords": m["matched_keywords"]}
            for m in matches
        ],
        "artifact_kinds": artifact_kinds,
        "artifact_plan": artifact_plan,
        "validation_plan": validation_plan,
        "pending": pending,
        "app_pending": app_pending,
        "company_pending": company_pending,
        "next_exact_command": next_cmd,
        "note": "산출물 생성은 로컬에서 수행되며, 앱/회사망이 필요한 검증은 pending으로 표시됩니다."
                + (" (keyword 미매칭: 기본 파일/문서 처리로 진행 — 요청을 더 구체적으로 쓰면 라우팅이 좋아집니다.)"
                   if routing == "default_fallback" else ""),
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
