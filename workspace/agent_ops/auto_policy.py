# -*- coding: utf-8 -*-
"""WS-7 execution policy engine: minimize user choices, stop only for danger.

Philosophy (AUTO_ORCHESTRATION_PLAN WS-7):
  * Do not push feature selection onto the user. Reversible work executes
    quietly; only genuinely risky work stops clearly.
  * Never bypass safety (approval/command_guard/classify_action). The safety
    result is an *input* that can only make the decision MORE conservative
    (execute -> ask_user/blocked). It can never promote ask_user/blocked back
    to execute. This one-way property is structural: the final mode is
    max(base_severity, safety_floor) on the severity ladder.

choose_execution_policy() is a pure function: no I/O, no side effects,
offline-deterministic for identical inputs.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

# Severity ladder. Higher = more conservative. Transitions may only go up.
MODE_SEVERITY: Dict[str, int] = {
    "execute": 0,
    "plan_only": 1,
    "ask_user": 2,
    "blocked": 3,
}
_SEVERITY_MODE = {v: k for k, v in MODE_SEVERITY.items()}

# Paths whose delegated command is reversible by construction:
#  - memory_wiki: USERDATA append-only (remember/recall/wiki/book), manual notes preserved
#  - command_native: schedule/routine local store, remove is separately guarded
#  - plan_only: read-only planning
#  - artifact: creates NEW local files under results/ (real app execution still
#    requires --execute which has its own approval gate in cmd_work)
REVERSIBLE_PATHS = {"memory_wiki", "command_native", "plan_only", "artifact"}

# Request signals that mean the user is asking for something hard to undo.
# These force ask_user regardless of route (still overridable via --yes).
ASK_SIGNALS: Dict[str, Tuple[str, ...]] = {
    "file_delete": ("삭제", "지워", "지우고", "휴지통", "delete", "remove"),
    "app_save": ("덮어쓰", "overwrite", "원본에 저장", "원본 저장", "원본 수정",
                 "엑셀에 저장", "엑셀 저장", "excel 저장", "한글로 저장",
                 "hwp 저장", "앱에서 저장", "저장하고 닫", "다른 이름으로 저장",
                 "실제 저장", "실제로 저장"),
    "external_change": ("메일 보내", "메일 발송", "메일 전송", "발송해", "전송해",
                        "송부", "제출", "업로드", "결재 올려", "결재 상신",
                        "포털에 등록", "시스템에 등록", "send mail", "send email",
                        "send the mail", "submit", "upload", "배포", "deploy",
                        "push"),
    "model_change": ("모델 바꿔", "모델 변경", "모델을 바꿔", "기본 모델",
                     "default model", "모델 기본값", "게이트웨이 변경",
                     "provider 변경", "api 키 변경", "라우트 변경"),
}

# Safety matched_danger terms that mean irreversible/system-wiping intent:
# these escalate straight to blocked (never just ask).
HARD_DENY_TERMS = {"초기화", "포맷", "format", "rm -rf", "reset"}

# Danger terms that demote even reversible/trusted routes to ask_user when the
# safety classifier matched them (deletion / outbound / approval chains).
CONFIRM_ALWAYS_TERMS = {
    "삭제", "delete", "발송", "전송", "제출", "submit", "send", "업로드",
    "upload", "배포", "deploy", "push", "결재", "승인", "approve", "반려",
}

_PRIORITY_BY_PATH = {
    "memory_wiki": "learning",
    "artifact": "quality",
    "command_native": "speed",
    "tool_agent": "speed",
    "plan_only": "quality",
}


def _match_signals(text: str) -> List[Dict[str, str]]:
    """Return [{group, word}] for every ASK_SIGNALS hit in the request."""
    hits: List[Dict[str, str]] = []
    for group, words in ASK_SIGNALS.items():
        for word in words:
            if word in text:
                hits.append({"group": group, "word": word})
                break
    return hits


def _safety_floor(safety: Optional[Dict[str, Any]], selected_path: str) -> Tuple[int, str]:
    """Map a safety classification to a severity FLOOR (one-way, only demotes).

    classify_action() vocabulary: decision in {blocked, safe, review_required},
    risk in {safe, review_required}. We additionally accept explicit
    deny/high-risk markers so a stricter upstream classifier keeps working.
    Returns (severity, reason). severity 0 means "no demotion".
    """
    if not isinstance(safety, dict):
        return 0, "safety input absent; no demotion"
    decision = str(safety.get("decision", "")).lower()
    risk = str(safety.get("risk", "")).lower()
    matched = [str(m).lower() for m in safety.get("matched_danger", []) or []]
    if decision in {"deny", "denied"} or risk in {"deny", "high", "high_risk", "critical"}:
        return MODE_SEVERITY["blocked"], f"safety classified deny/high-risk (decision={decision or risk})"
    if decision == "blocked":
        hard = sorted(set(matched) & HARD_DENY_TERMS)
        if hard:
            return MODE_SEVERITY["blocked"], f"safety matched irreversible terms: {', '.join(hard)}"
        confirm = sorted(set(matched) & CONFIRM_ALWAYS_TERMS)
        if confirm:
            return MODE_SEVERITY["ask_user"], f"safety matched confirmation-required terms: {', '.join(confirm)}"
        if selected_path in REVERSIBLE_PATHS:
            # Keyword-tier match (e.g. 등록/마감/저장 vocabulary) on a route that
            # is reversible by construction: do not demote, keep quiet execution.
            return 0, "safety keyword match on reversible route; no demotion"
        return MODE_SEVERITY["ask_user"], ("safety matched danger keywords on a "
                                           f"non-reversible route: {', '.join(sorted(set(matched))) or 'unknown'}")
    # decision safe, or review_required with no matched keyword: the word-list
    # classifier simply has no signal — not a reason to interrupt the user.
    return 0, "safety has no danger match; no demotion"


def choose_execution_policy(
    request: str,
    capabilities: Optional[Sequence[Dict[str, Any]]],
    context: Optional[Dict[str, Any]],
    safety: Optional[Dict[str, Any]],
    hint: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Decide how the auto entrypoint should treat one request.

    Args:
        request: raw user task text.
        capabilities: plan_task() capability matches (list of dicts with id/confidence).
        context: extra planner context, e.g. {"pending": [...], "routing": ...}.
        safety: classify_action(request) result (or a stricter classifier's).
        hint: _auto_command_hint() result ({selected_path, command, reason}).

    Returns dict:
        mode: execute | plan_only | ask_user | blocked
        path: hint's selected_path (routing layer stays WS-1's job)
        priority: speed | quality | safety | learning
        requires_confirmation: True only for ask_user
        reason: one-sentence Korean explanation
        fallback: safe path used when not executing
        signals / safety_reason / question: evidence for the trace (WS-8 input)
    """
    text = (request or "").lower()
    hint = hint or {}
    context = context or {}
    selected_path = hint.get("selected_path", "plan_only")

    reasons: List[str] = []
    base = MODE_SEVERITY["execute"]

    # 1) Routing layer already gave up -> plan.
    if selected_path == "plan_only":
        base = MODE_SEVERITY["plan_only"]
        reasons.append("라우팅 신뢰도가 낮아 계획만 세운다")

    # 2) Tool/app route whose prerequisites are pending -> plan, don't ask.
    pending = list(context.get("pending", []) or [])
    if selected_path == "tool_agent" and pending:
        base = max(base, MODE_SEVERITY["plan_only"])
        reasons.append(f"앱/도구 준비가 미완료(pending {len(pending)}건)라 계획으로 대체한다")

    # 3) Hard-to-undo request signals -> ask the user (only these; reversible
    #    work never asks — user-choice minimization).
    signals = _match_signals(text)
    if signals:
        base = max(base, MODE_SEVERITY["ask_user"])
        groups = ", ".join(sorted({s["group"] for s in signals}))
        reasons.append(f"되돌리기 어려운 신호({groups})가 있어 확인이 필요하다")

    # 4) Safety overlay: one-way conservative floor.
    safety_severity, safety_reason = _safety_floor(safety, selected_path)
    severity = max(base, safety_severity)
    if safety_severity > base:
        reasons.append(safety_reason)

    mode = _SEVERITY_MODE[severity]
    if not reasons:
        reasons.append("되돌릴 수 있는 작업이라 묻지 않고 실행한다")

    if mode in {"ask_user", "blocked"}:
        priority = "safety"
    else:
        priority = _PRIORITY_BY_PATH.get(selected_path, "speed")

    question = ""
    if mode == "ask_user":
        what = ", ".join(sorted({s["word"] for s in signals})) or "위험 신호"
        question = (f"요청에 '{what}' 신호가 있어 실행 전 확인이 필요합니다. "
                    "진행하려면 --yes(또는 --execute)로 다시 실행하세요.")

    return {
        "mode": mode,
        "path": selected_path,
        "priority": priority,
        "requires_confirmation": mode == "ask_user",
        "reason": "; ".join(reasons),
        "fallback": "plan_only",
        "signals": signals,
        "safety_reason": safety_reason,
        "question": question,
    }
