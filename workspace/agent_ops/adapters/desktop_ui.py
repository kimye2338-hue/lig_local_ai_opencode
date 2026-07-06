# -*- coding: utf-8 -*-
"""임의 Windows GUI 앱 자동화 어댑터 (CursorTouch/Windows-Use 래퍼).

우리 어댑터는 COM(Excel/HWP/Outlook/SolidWorks)·CDP(브라우저)·배치(AutoCAD/MATLAB/
Fluent)로 앱을 다룬다. 그러나 **COM API가 없는 앱**(사내 데스크톱 포털 클라이언트,
레거시 유틸, 버튼만 있는 사내 프로그램)은 조작 수단이 없다. Windows-Use(MIT)는
Windows **UI Automation 접근성 트리**를 읽어 LLM 이 클릭/입력을 결정하고 PyAutoGUI 로
실행한다(비전 모델 불필요). 이 어댑터가 그 갭을 메운다.

설계(우리 optional-dep 패턴 — ocr_screen/doc_convert 와 동일):
  - windows_use 가 설치돼 있으면 사용, 없으면 **조용히 실패하지 않고** 반입 안내.
  - LLM 은 클라우드가 아니라 **사내 게이트웨이(OpenAI 호환)** 또는 로컬 모델로 지정.
  - 실제 앱 구동(run_task)은 회사 PC 파일럿에서 Windows-Use API/앱 호환성 검증 후 활성화.
    (그 전까지는 capabilities/detection 과 반입 안내만 제공 — 지어낸 API 호출 금지.)

반입(오프라인): 인터넷 PC에서 `pip download windows-use -d wheelhouse` →
회사 PC에서 `pip install --no-index --find-links wheelhouse windows-use`.
자세히: docs/EXTERNAL_TOOLS_REVIEW.md (Windows-Use 절).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    from ..core import now
except Exception:  # 단독 실행 폴백
    from datetime import datetime

    def now() -> str:  # type: ignore
        return datetime.now().astimezone().isoformat(timespec="seconds")

ACTIONS = {"capabilities", "run_task"}


def available() -> bool:
    try:
        import windows_use  # noqa: F401
        return True
    except Exception:
        return False


def _bring_in_hint() -> str:
    return ("windows-use 미반입 — 인터넷 PC에서 `pip download windows-use -d wheelhouse` 후 "
            "회사 PC에서 `pip install --no-index --find-links wheelhouse windows-use`. "
            "LLM 은 사내 게이트웨이(OpenAI 호환)로 지정. 자세히: docs/EXTERNAL_TOOLS_REVIEW.md")


def execute(action: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    action = str(action or "")

    if action == "capabilities":
        return {"ok": True, "available": available(), "timestamp": now(),
                "mechanism": "Windows UI Automation 접근성 트리 + PyAutoGUI (비전 불필요)",
                "use_when": "COM/CDP/배치로 못 다루는 앱(사내 데스크톱 클라이언트·레거시 유틸)",
                "prefer_instead": "Excel/HWP/Outlook/SolidWorks=COM, 브라우저=CDP, CAD/MATLAB/Fluent=배치",
                "hint": None if available() else _bring_in_hint()}

    if action == "run_task":
        # 실제 앱 구동은 파일럿 검증(Windows-Use API 시그니처 + 대상 앱 UIA 노출) 후 활성화.
        # 미검증 상태에서 지어낸 API 호출을 하지 않는다(조용한 실패/오작동 방지).
        if not available():
            return {"ok": False, "error": "windows-use 미반입", "hint": _bring_in_hint()}
        return {"ok": False,
                "error": "app validation pending",
                "detail": ("windows-use 는 설치됨. 실제 run_task 배선은 회사 PC 파일럿에서 "
                           "API 시그니처와 대상 앱의 UI Automation 노출을 검증한 뒤 활성화한다. "
                           "그 전까지 COM/CDP/배치 어댑터를 우선 사용."),
                "task": options.get("task", "")}

    return {"ok": False, "error": f"알 수 없는 action: {action}", "actions": sorted(ACTIONS)}


if __name__ == "__main__":
    import json
    import sys
    act = sys.argv[1] if len(sys.argv) > 1 else "capabilities"
    print(json.dumps(execute(act, {"task": " ".join(sys.argv[2:])}), ensure_ascii=False, indent=2))
