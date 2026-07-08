# -*- coding: utf-8 -*-
"""프로세스 스킬 자동 라우팅 — 작업 유형에 맞는 '일하는 절차'를 자동 주입.

api_reference(공식 API)·design_guidance(디자인)·domain_context(한국 비즈니스)가
'무엇을 아는가'를 주입한다면, 이 라우터는 '어떻게 처리하는가'(절차)를 주입한다.
작업 유형을 판별해 `knowledge/skills/process_skills.md` 의 해당 섹션 하나만 넣는다
(도구가 많아도 적재적소의 '스킬'이 알아서 적용되게 — superpowers 식 자동 적용).

파일이 없어도 안전(주입 생략). 한 번에 한 섹션만(과주입 방지).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

SKILL_FILE = Path(__file__).resolve().parent / "knowledge" / "skills" / "process_skills.md"

# (섹션 제목 키워드, 그 스킬을 트리거하는 작업 키워드들). 위에서부터 먼저 매칭.
_SKILLS: List[Tuple[str, Tuple[str, ...]]] = [
    ("매크로", ("매크로", "vba", "코드", "스크립트", "자동화 코드", "솔리드웍스", "오토캐드",
                "autocad", "solidworks", "matlab", "매트랩", "hwp 자동")),
    ("데이터 분석", ("데이터", "분석", "csv", "엑셀 데이터", "통계", "이상", "불량", "측정",
                    "차트", "그래프", "집계")),
    ("웹", ("포털", "웹", "브라우저", "크롬", "사이트", "로그인", "페이지", "탭")),
    ("문제 해결", ("오류", "안 됨", "안돼", "실패", "에러", "디버그", "고쳐", "문제", "진단", "복구")),
    ("보고서", ("보고서", "리포트", "문서", "회의록", "ppt", "슬라이드", "발표", "제안서",
                "기획서", "요약", "초안", "작성")),
]

_SKILLS_BY_CAPABILITY = {
    "macro_generation": "매크로",
    "spreadsheet_generation": "데이터 분석",
    "browser_automation": "웹",
    "web_mail_assistant": "웹",
    "document_generation": "보고서",
    "presentation_generation": "보고서",
    "meeting_minutes": "보고서",
    "weekly_report": "보고서",
    "matlab_automation": "데이터 분석",
    "simulation_automation": "매크로",
    "office_cad_automation": "매크로",
}


def detect_skill(prompt: str, capability_ids: Optional[List[str]] = None) -> Optional[str]:
    for cap_id in capability_ids or []:
        section = _SKILLS_BY_CAPABILITY.get(cap_id)
        if section:
            return section
    low = (prompt or "").lower()
    for section, keys in _SKILLS:
        if any(k.lower() in low for k in keys):
            return section
    return None


def _section_text(section_title_kw: str, max_chars: int) -> Optional[str]:
    if not SKILL_FILE.exists():
        return None
    try:
        text = SKILL_FILE.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    blocks = re.split(r"(?m)^(?=## )", text)
    for b in blocks:
        if b.startswith("## ") and section_title_kw in b.splitlines()[0]:
            return b.strip()[:max_chars]
    return None


def context_for_prompt(prompt: str, max_chars: int = 1200,
                       capability_ids: Optional[List[str]] = None) -> Optional[str]:
    """작업 유형에 맞는 절차 스킬 하나를 system 주입 문자열로. 없으면 None."""
    section = detect_skill(prompt, capability_ids=capability_ids)
    if not section:
        return None
    body = _section_text(section, max_chars)
    if not body:
        return None
    header = ("아래는 이 유형의 작업을 처리하는 **절차**다. 이 순서(근거→계획→실행→검증→기록)를 "
              "따라 일하라.\n\n")
    return header + body


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(context_for_prompt(" ".join(sys.argv[1:])) or "(해당 절차 없음)")
    else:
        print("skills present:", SKILL_FILE.exists())
