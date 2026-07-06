# -*- coding: utf-8 -*-
"""공식 API 참조 코퍼스 로더 — 매크로/스크립트를 '공식 근거 기반'으로 생성.

문제: LLM이 매크로를 만들 때 존재하지 않는 메서드/명령을 지어내면(환각) 실제 앱에서
실패한다. 해결: 사용자 소프트웨어의 **공식 문서 발췌**를 `knowledge/apis/*.md`에 두고,
작업 프롬프트가 특정 소프트웨어를 가리키면 그 참조를 system 컨텍스트로 주입한다.
→ 모델이 실제 객체/메서드/명령 이름을 근거로 코드를 짠다.

코퍼스는 `agent_ops/knowledge/apis/`의 마크다운. 파일이 없어도 안전(주입 생략).
Haiku 리서치가 파일을 추가하면 재빌드 없이 자동 반영된다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

APIS_DIR = Path(__file__).resolve().parent / "knowledge" / "apis"

# 소프트웨어 → (참조 파일명, 프롬프트에서 이 소프트웨어를 가리키는 키워드들)
_SOFTWARE: Dict[str, Dict[str, object]] = {
    "excel":      {"file": "excel_vba.md",   "kw": ["excel", "엑셀", "xlsx", "xls", "vba", "워크시트", "셀 ", "매크로"]},
    "outlook":    {"file": "outlook_vba.md", "kw": ["outlook", "아웃룩", "메일", "mailitem", "이메일"]},
    "autocad":    {"file": "autocad.md",     "kw": ["autocad", "오토캐드", "dwg", "accoreconsole", "autolisp", ".scr", "도면"]},
    "matlab":     {"file": "matlab.md",      "kw": ["matlab", "매트랩", "-batch", ".m 스크립트", "simulink"]},
    "solidworks": {"file": "solidworks.md",  "kw": ["solidworks", "솔리드웍스", "sldworks", "파트", "어셈블리", "모델링"]},
    "fluent":     {"file": "fluent.md",      "kw": ["fluent", "플루언트", "ansys", "journal", "cfd", "유동해석"]},
}


def detect_software(prompt: str) -> List[str]:
    """프롬프트가 가리키는 소프트웨어 id 목록(키워드 매칭). 다중 가능."""
    low = (prompt or "").lower()
    hits: List[str] = []
    for sid, spec in _SOFTWARE.items():
        for kw in spec["kw"]:  # type: ignore[index]
            if str(kw).lower() in low:
                hits.append(sid)
                break
    return hits


def load_reference(software: str) -> Optional[str]:
    """소프트웨어 id의 공식 API 참조 마크다운 전문. 없으면 None."""
    spec = _SOFTWARE.get(software)
    if not spec:
        return None
    path = APIS_DIR / str(spec["file"])
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _excerpt(text: str, max_chars: int) -> str:
    """참조가 길면 핵심 섹션(핵심 객체/명령 + 최소 동작 예제) 위주로 자른다."""
    if len(text) <= max_chars:
        return text
    # 헤더 단위로 우선순위 섹션만 남긴다.
    keep_heads = ("# ", "## 핵심", "## 최소 동작", "## 자주")
    blocks = re.split(r"(?m)^(?=## )", text)
    out = blocks[0] if blocks else ""
    for b in blocks[1:]:
        if b.startswith(keep_heads):
            if len(out) + len(b) > max_chars:
                break
            out += b
    return out[:max_chars]


def context_for_prompt(prompt: str, max_chars: int = 2600) -> Optional[str]:
    """프롬프트에 맞는 공식 API 참조를 system 주입용 문자열로. 없으면 None.

    tool_dispatch.run_agent_loop 가 이 반환을 system 메시지로 삽입한다.
    """
    softwares = detect_software(prompt)
    if not softwares:
        return None
    chunks: List[str] = []
    budget = max_chars
    for sid in softwares[:2]:  # 과도 주입 방지: 최대 2개
        ref = load_reference(sid)
        if not ref:
            continue
        piece = _excerpt(ref, max(600, budget // (2 if len(softwares) > 1 else 1)))
        chunks.append(piece)
        budget -= len(piece)
        if budget <= 0:
            break
    if not chunks:
        return None
    header = ("아래는 대상 소프트웨어의 **공식 API 문서 발췌**다. 매크로/스크립트를 만들 때 "
              "여기 있는 실제 객체/메서드/명령 이름만 사용하고, 문서에 없는 API는 지어내지 말 것. "
              "확실하지 않으면 스캐폴드로 남기고 사용자에게 확인을 요청할 것.\n\n")
    return header + "\n\n---\n\n".join(chunks)


def corpus_status() -> Dict[str, bool]:
    """어떤 소프트웨어 참조가 채워졌는지(doctor/진단용)."""
    return {sid: (APIS_DIR / str(spec["file"])).exists()
            for sid, spec in _SOFTWARE.items()}


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 1:
        print(context_for_prompt(" ".join(sys.argv[1:])) or "(해당 소프트웨어 참조 없음)")
    else:
        print(json.dumps(corpus_status(), ensure_ascii=False, indent=2))
