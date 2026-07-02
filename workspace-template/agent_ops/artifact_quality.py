# -*- coding: utf-8 -*-
"""Artifact quality validator: would a user who opens this file get real help?

Rules are deterministic and per artifact *kind*, not per task. They encode the
minimum usable bar for a scaffold: the request is embedded, validation status
(app/company pending) is explicit, TODOs carry a concrete hint instead of a
bare marker, Korean text is not mojibake, and each kind has its structural
essentials (VBA guards, document sections, slide spec fields, ...).

Used three ways:
  1) generate_artifacts() validates its own output and reports per-kind verdicts
  2) the capability benchmark enforces the bar in tests
  3) the LLM enrichment path accepts a filled file only if it still passes here
     (otherwise the scaffold is kept — quality can never regress via enrichment)

stdlib-only, no imports from other agent_ops modules (safe to reuse anywhere).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

# (rule id, why it matters to the user, predicate over the artifact text)
Rule = Tuple[str, str, Callable[[str], bool]]

# A TODO at end-of-line with no hint after it is a placeholder, not guidance.
_BARE_TODO = re.compile(r"TODO\s*:?\s*$", re.MULTILINE)


def _common_rules(task: str) -> List[Rule]:
    rules: List[Rule] = [
        ("status_declared", "검증 상태(locally .../pending)가 명시되어야 함",
         lambda t: ("pending" in t) or ("locally" in t)),
        ("no_mojibake", "한글 깨짐 문자(U+FFFD)가 없어야 함",
         lambda t: "�" not in t),
        ("substantial", "빈 껍데기가 아니어야 함 (실질 내용 최소 분량)",
         lambda t: len(t.strip()) >= 200),
        ("no_bare_todo", "TODO는 무엇을 채울지 힌트를 포함해야 함",
         lambda t: not _BARE_TODO.search(t)),
    ]
    if task:
        rules.insert(0, ("task_embedded", "요청 원문이 산출물에 포함되어야 함",
                         lambda t: task in t))
    return rules


_KIND_RULES: Dict[str, List[Rule]] = {
    "vba_macro": [
        ("option_explicit", "Option Explicit로 변수 오타를 컴파일 타임에 잡아야 함",
         lambda t: "Option Explicit" in t),
        ("entry_sub", "명확한 진입점 Sub Main이 있어야 함",
         lambda t: "Sub Main" in t),
        ("error_handling", "On Error 에러 처리가 있어야 함",
         lambda t: "On Error" in t),
        ("how_to_run", "실행/import 방법 안내가 있어야 함",
         lambda t: "실행 방법" in t),
        ("app_pending", "실제 앱 실행 검증이 pending임을 밝혀야 함",
         lambda t: "app validation pending" in t),
    ],
    "document": [
        ("has_title", "문서 제목(# 헤딩)으로 시작해야 함",
         lambda t: t.lstrip().startswith("#")),
        ("section_overview", "개요 섹션이 있어야 함", lambda t: "개요" in t),
        ("section_purpose", "목적 섹션이 있어야 함", lambda t: "목적" in t),
        ("section_body", "본문 섹션이 있어야 함", lambda t: "본문" in t),
        ("section_conclusion", "결론 섹션이 있어야 함", lambda t: "결론" in t),
        ("section_actions", "액션 아이템 섹션이 있어야 함",
         lambda t: ("액션 아이템" in t) or ("액션아이템" in t)),
    ],
    "slide_outline": [
        ("presentation_flow", "발표 흐름(도입/본론/결론)이 설명되어야 함",
         lambda t: "발표 흐름" in t),
        ("pptx_pending", "pptx 자동 생성이 pending임을 밝혀야 함",
         lambda t: "dependency_or_app_pending" in t),
    ],
    "browser_script": [
        ("credential_notice", "계정/비밀번호 하드코딩 금지 안내가 있어야 함",
         lambda t: "하드코딩하지 마세요" in t),
        ("target_placeholder", "대상 URL placeholder(TARGET_URL)가 있어야 함",
         lambda t: "TARGET_URL" in t),
        ("engine_choice", "CDP/selenium/playwright 선택 기준이 있어야 함",
         lambda t: all(k in t for k in ("CDP", "selenium", "playwright"))),
        ("browser_pending", "실제 브라우저 검증이 pending임을 밝혀야 함",
         lambda t: "real browser validation pending" in t),
    ],
    "mail_report": [
        ("classification_table", "분류 결과 표가 있어야 함",
         lambda t: "| 분류 |" in t),
        ("summary_counts", "분류별 건수 요약이 있어야 함",
         lambda t: "건" in t),
        ("action_items", "액션 아이템 목록이 있어야 함",
         lambda t: ("액션 아이템" in t) or ("액션아이템" in t)),
        ("source_and_company", "분류 근거(mock 또는 입력 메일)와 실제 메일함은 company pending임을 구분해야 함",
         lambda t: (("mock" in t) or ("입력 메일" in t)) and ("company validation pending" in t)),
    ],
}

# Host-app-specific VBA rules, activated by the generated filename
# (macro_<app>.bas). These are what make a macro safe to try, not just open.
_VBA_APP_RULES: Dict[str, List[Rule]] = {
    "solidworks": [
        ("sw_activedoc_guard", "ActiveDoc 없음(Nothing) guard가 있어야 함",
         lambda t: ("ActiveDoc" in t) and ("Nothing" in t)),
        ("sw_doc_type_branch", "파트/어셈블리/도면 문서 타입 분기(GetType)가 있어야 함",
         lambda t: "GetType" in t),
        ("sw_backup_warning", "형상 변경 전 백업/사본 경고가 있어야 함",
         lambda t: ("백업" in t) or ("사본" in t)),
        ("sw_late_binding", "SldWorks late binding 참조가 있어야 함",
         lambda t: "SldWorks" in t),
    ],
    "excel": [
        ("xl_target_constants", "적용 대상 상수(TARGET_SHEET/TARGET_RANGE)가 있어야 함",
         lambda t: ("TARGET_SHEET" in t) and ("TARGET_RANGE" in t)),
        ("xl_screen_updating_restore", "ScreenUpdating을 끄고 오류 시에도 복원해야 함",
         lambda t: t.count("ScreenUpdating") >= 2),
        ("xl_import_path", "Alt+F11 import 경로 안내가 있어야 함",
         lambda t: "Alt+F11" in t),
    ],
}


# Allowed file extensions per kind: a macro delivered as .txt or a report
# delivered as .py would not serve its purpose even with perfect content.
_KIND_SUFFIXES: Dict[str, set] = {
    "vba_macro": {".bas"},
    "document": {".md", ".txt"},
    "slide_outline": {".md", ".json"},
    "browser_script": {".py"},
    "mail_report": {".md"},
}


def _validate_slide_spec(text: str) -> List[Dict[str, str]]:
    """Structural check of slide_spec.json (parsed, not substring-matched)."""
    violations: List[Dict[str, str]] = []
    try:
        spec = json.loads(text)
    except Exception:
        return [{"rule": "spec_json_parse", "why": "slide_spec.json이 유효한 JSON이어야 함"}]
    slides = spec.get("slides") or []
    if len(slides) < 4:
        violations.append({"rule": "spec_min_slides", "why": "슬라이드가 4장 이상이어야 함"})
    if not all(s.get("title") and s.get("message") and s.get("points") for s in slides):
        violations.append({"rule": "spec_slide_fields",
                           "why": "모든 슬라이드에 title/message/points가 있어야 함"})
    if not spec.get("flow"):
        violations.append({"rule": "spec_flow", "why": "발표 흐름(flow)이 정의되어야 함"})
    if spec.get("pptx_generation") != "dependency_or_app_pending":
        violations.append({"rule": "spec_pptx_pending",
                           "why": "pptx 자동 생성 상태가 dependency_or_app_pending이어야 함"})
    return violations


def validate_artifact_set(kind: str, texts: Sequence[str], task: str = "",
                          filenames: Sequence[str] = (),
                          required_terms: Sequence[str] = ()) -> Dict[str, Any]:
    """Validate all files one kind produced for one task (as a set).

    Some rules span files on purpose (e.g. mail_report = 보고서 + 액션아이템),
    so rules run over the joined text; slide specs get structural JSON checks;
    VBA gets host-app rules keyed off the generated filename.

    `required_terms` are input-grounding anchors (e.g. input file names): if
    the caller claims artifacts were built from user inputs, every term must
    actually appear in the set — this blocks "read it but didn't use it"
    fake successes.
    """
    joined = "\n".join(texts)
    rules = _common_rules(task) + _KIND_RULES.get(kind, [])
    if kind == "vba_macro":
        for name in filenames:
            for app, app_rules in _VBA_APP_RULES.items():
                if f"macro_{app}" in Path(str(name)).name:
                    rules = rules + app_rules
    violations: List[Dict[str, str]] = []
    for rule_id, why, predicate in rules:
        try:
            ok = bool(predicate(joined))
        except Exception:
            ok = False
        if not ok:
            violations.append({"rule": rule_id, "why": why})
    checked = len(rules)
    if required_terms:
        checked += 1
        missing = [term for term in required_terms if term and term not in joined]
        if missing:
            violations.append(
                {"rule": "input_reflected",
                 "why": f"입력 근거가 산출물에 반영되지 않음: {', '.join(missing[:5])}"})
    allowed = _KIND_SUFFIXES.get(kind)
    if allowed and filenames:
        checked += 1
        for name in filenames:
            suffix = Path(str(name)).suffix.lower()
            if suffix not in allowed:
                violations.append(
                    {"rule": "file_extension",
                     "why": f"{Path(str(name)).name}: {kind} 산출물 확장자가 목적에 맞지 않음 "
                            f"(허용: {sorted(allowed)})"})
    if kind == "slide_outline":
        for text, name in zip(texts, list(filenames) or [""] * len(texts)):
            if str(name).endswith(".json"):
                spec_violations = _validate_slide_spec(text)
                violations.extend(spec_violations)
                checked += 4
    return {"kind": kind, "ok": not violations, "checked_rules": checked,
            "violations": violations}


def validate_files(kind: str, paths: Sequence[Any], task: str = "",
                   required_terms: Sequence[str] = ()) -> Dict[str, Any]:
    """Read and validate the files one kind generated (see validate_artifact_set)."""
    texts = [Path(p).read_text(encoding="utf-8", errors="replace") for p in paths]
    return validate_artifact_set(kind, texts, task, [str(p) for p in paths],
                                 required_terms=required_terms)
