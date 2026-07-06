# -*- coding: utf-8 -*-
"""문서/슬라이드 디자인 가이드 주입 — 생성물 품질을 높인다.

매크로 생성에 공식 API 를 주입하듯(api_reference), 보고서/문서/PPT 생성 작업에는
**디자인 원칙 체크리스트**를 system 컨텍스트로 주입한다. 그러면 모델이 밋밋한
기본 결과가 아니라 위계·정렬·여백·1슬라이드1메시지 같은 원칙을 지킨 결과물을 만든다.

코퍼스: `agent_ops/knowledge/design/*.md`. 파일이 없어도 안전(주입 생략).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

DESIGN_DIR = Path(__file__).resolve().parent / "knowledge" / "design"
_GUIDE_FILE = "document_slides.md"

# 이 키워드가 작업에 있으면 "문서/발표물 생성"으로 보고 디자인 가이드를 주입.
_KEYWORDS = (
    "보고서", "리포트", "report", "문서", "docx", "워드", "한글파일", "hwp",
    "ppt", "pptx", "슬라이드", "발표", "프레젠테이션", "presentation", "slide",
    "제안서", "기획서", "회의록", "요약본", "브로슈어", "포스터", "디자인",
    "design doc", "레이아웃", "표지", "양식",
)


def is_document_task(prompt: str) -> bool:
    low = (prompt or "").lower()
    return any(kw.lower() in low for kw in _KEYWORDS)


def _load_guide() -> Optional[str]:
    path = DESIGN_DIR / _GUIDE_FILE
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _excerpt(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    # 헤더 단위로 잘라 최대 예산까지.
    blocks = re.split(r"(?m)^(?=## )", text)
    out = blocks[0] if blocks else ""
    for b in blocks[1:]:
        if len(out) + len(b) > max_chars:
            break
        out += b
    return out[:max_chars]


def context_for_prompt(prompt: str, max_chars: int = 2200) -> Optional[str]:
    """문서/발표물 작업이면 디자인 가이드 주입 문자열, 아니면 None."""
    if not is_document_task(prompt):
        return None
    guide = _load_guide()
    if not guide:
        return None
    header = ("아래는 보고서/문서/슬라이드를 만들 때 적용할 **디자인·구성 원칙**이다. "
              "결과물이 밋밋한 기본형이 되지 않게 위계·정렬·여백·대비·일관성과 "
              "'슬라이드 1장=1메시지', '결론 먼저'를 지켜라.\n\n")
    return header + _excerpt(guide, max_chars)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(context_for_prompt(" ".join(sys.argv[1:])) or "(문서 작업 아님 — 주입 없음)")
    else:
        print("guide present:", _load_guide() is not None)
