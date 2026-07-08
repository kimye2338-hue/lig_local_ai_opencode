# -*- coding: utf-8 -*-
"""도메인 맥락 주입 — 한국 회사 업무 커뮤니케이션 톤.

메일 초안/회의록/보고서/대외 문서 작업이면 한국 회사 맥락(결재/완곡표현/격식/톤)을
system 컨텍스트로 주입해, 결과물이 한국 비즈니스 관행에 맞게 나오게 한다.
api_reference/design_guidance 와 동일한 optional-지식 주입 패턴.

코퍼스: `agent_ops/knowledge/domain/korean_business.md`. 없으면 주입 생략(안전).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

DOMAIN_DIR = Path(__file__).resolve().parent / "knowledge" / "domain"
_FILE = "korean_business.md"

_KEYWORDS = (
    "메일", "이메일", "e-mail", "email", "회신", "답장",
    "회의록", "회의 정리", "미팅", "안건", "액션아이템",
    "보고서", "공문", "품의", "기안", "결재", "대외", "거래처", "협력사",
    "고객사", "상급자", "부서장", "팀장", "정중", "격식", "사내 공지",
)


def is_business_comm(prompt: str) -> bool:
    low = (prompt or "").lower()
    return any(kw.lower() in low for kw in _KEYWORDS)


def _load() -> Optional[str]:
    path = DOMAIN_DIR / _FILE
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _excerpt(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    blocks = re.split(r"(?m)^(?=## )", text)
    out = blocks[0] if blocks else ""
    for b in blocks[1:]:
        if len(out) + len(b) > max_chars:
            break
        out += b
    return out[:max_chars]


def context_for_prompt(prompt: str, max_chars: int = 1600) -> Optional[str]:
    if not is_business_comm(prompt):
        return None
    guide = _load()
    if not guide:
        return None
    header = ("아래는 한국 회사 업무 맥락이다. 메일/회의록/보고서/대외 문서는 이 관행(두괄식·"
              "격식·존대, 완곡표현 해석, 액션아이템에 담당·기한)에 맞춰 작성하라.\n\n")
    return header + _excerpt(guide, max_chars)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(context_for_prompt(" ".join(sys.argv[1:])) or "(업무 커뮤니케이션 아님 — 주입 없음)")
    else:
        print("guide present:", _load() is not None)
