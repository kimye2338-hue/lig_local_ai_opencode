# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, List

from .core import POLICIES, PORTAL, now, read_text, append_jsonl, atomic_write_text

DEFAULT_DANGEROUS = ["삭제", "저장", "등록", "제출", "전송", "발송", "승인", "반려", "결재", "확정", "취소", "업로드", "다운로드", "초기화", "마감", "배포", "실행", "처리", "적용", "완료", "delete", "save", "submit", "send", "approve", "reject", "confirm", "cancel", "upload", "download", "execute", "apply", "complete", "push", "deploy"]
DEFAULT_ALLOWED = ["조회", "검색", "열기", "닫기", "탭", "메뉴", "상세", "보기", "확인", "search", "view", "open", "close", "tab", "menu", "detail", "inspect"]

def ensure_policy_files() -> None:
    POLICIES.mkdir(parents=True, exist_ok=True)
    d = POLICIES / "DANGEROUS_ACTIONS.txt"
    a = POLICIES / "ALLOWED_ACTIONS.txt"
    if not d.exists():
        atomic_write_text(d, "\n".join(DEFAULT_DANGEROUS) + "\n")
    if not a.exists():
        atomic_write_text(a, "\n".join(DEFAULT_ALLOWED) + "\n")

def load_words(path_name: str, defaults: List[str]) -> List[str]:
    ensure_policy_files()
    text = read_text(POLICIES / path_name)
    words = [line.strip().lower() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    return words or [w.lower() for w in defaults]

def element_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        keys = ["text", "aria-label", "aria_label", "title", "value", "id", "class", "href", "name", "type", "role", "form_action"]
        return " ".join(str(data.get(k, "")) for k in keys)
    return str(data)

def classify_action(data: Any) -> Dict[str, Any]:
    text = element_text(data).lower()
    dangerous = load_words("DANGEROUS_ACTIONS.txt", DEFAULT_DANGEROUS)
    allowed = load_words("ALLOWED_ACTIONS.txt", DEFAULT_ALLOWED)
    matched_danger = [w for w in dangerous if w and w in text]
    matched_allowed = [w for w in allowed if w and w in text]
    if matched_danger:
        decision = "blocked"; risk = "review_required"
    elif matched_allowed:
        decision = "safe"; risk = "safe"
    else:
        decision = "review_required"; risk = "review_required"
    result = {"timestamp": now(), "decision": decision, "risk": risk, "matched_danger": matched_danger, "matched_allowed": matched_allowed, "text": text[:1000]}
    append_jsonl(PORTAL / "results" / "safety_decisions.jsonl", result)
    return result

def scan_jsonl_file(path: str) -> Dict[str, Any]:
    p = PORTAL / "results" / path
    if not p.exists():
        return {"ok": False, "error": f"not found: {p}"}
    decisions = []
    for line in read_text(p).splitlines():
        try:
            obj = json.loads(line)
        except Exception:
            obj = line
        decisions.append(classify_action(obj))
    summary = {"ok": True, "source": str(p), "total": len(decisions), "blocked": sum(1 for d in decisions if d["decision"] == "blocked"), "review_required": sum(1 for d in decisions if d["decision"] == "review_required"), "safe": sum(1 for d in decisions if d["decision"] == "safe")}
    atomic_write_text(PORTAL / "reports" / "SAFETY_SCAN_REPORT.md", "# Safety Scan Report\n\n```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n")
    return summary
