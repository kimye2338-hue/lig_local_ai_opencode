# -*- coding: utf-8 -*-
"""App adapters: where real app execution plugs in later.

Artifact *generation* (artifact_generators.py) is separated from app
*execution* on purpose: scaffolds are produced and validated locally today,
while running them inside SolidWorks/Office/Chrome/HWP is added here later
as independent adapters — without touching generators or the planner.

Each adapter declares what it would automate, what it needs (dependency /
app install / company network), and its validation status. Nothing here
claims to execute anything yet: every adapter is a skeleton and stays
"app validation pending" (or company validation pending) until proven on
a machine that has the app.

Adding a real adapter later:
  1) implement `execute(artifact_path, options) -> dict` in its module
  2) flip `available` to True only after an actual run on the target app
  3) record any new dependency in release/dependencies.json first
"""
from __future__ import annotations

from typing import Any, Dict

from . import browser_cdp

# adapter id -> spec. Keys mirror the capability registry vocabulary so
# doctor/plan can report generation and execution status side by side.
ADAPTERS: Dict[str, Dict[str, Any]] = {
    "solidworks": {
        "description": "SolidWorks 매크로 실행/COM 제어 (파트/어셈블리/도면)",
        "consumes": ["vba_macro"],
        "available": False,
        "requires": ["SolidWorks 설치", "pywin32 (COM 채택 시 — dependencies.json 'pywin32')"],
        "pending": "app validation pending: SolidWorks가 있는 PC에서 매크로 실행 검증",
    },
    "office": {
        "description": "Excel/Word/PowerPoint 매크로 실행/COM 제어",
        "consumes": ["vba_macro", "slide_outline"],
        "available": False,
        "requires": ["MS Office 설치", "pywin32 또는 python-pptx/openpyxl (dependencies.json 'office-doc-wheels')"],
        "pending": "app validation pending: Office가 있는 PC에서 매크로/변환 실행 검증",
    },
    "browser": {
        "description": "Chrome 실제 제어 (CDP/selenium/playwright)",
        "consumes": ["browser_script"],
        "available": False,
        "requires": ["Chrome", "CDP는 추가 설치 불필요; selenium/playwright는 dependencies.json 'browser-automation-wheels'"],
        "pending": "real browser validation pending; 사내 시스템 로그인은 company validation pending",
        "execute": browser_cdp.execute,
    },
    "hwp": {
        "description": "한글(HWP) 문서 자동화",
        "consumes": ["document"],
        "available": False,
        "requires": ["한글 설치", "pywin32 (HwpFrame COM)"],
        "pending": "app validation pending: 한글이 있는 PC에서 검증",
    },
}


def adapter_summary() -> Dict[str, Any]:
    """Secret-free execution-side inventory for doctor/diagnostics."""
    return {
        adapter_id: {
            "description": spec["description"],
            "consumes": spec["consumes"],
            "available": spec["available"],
            "pending": spec["pending"],
        }
        for adapter_id, spec in ADAPTERS.items()
    }
