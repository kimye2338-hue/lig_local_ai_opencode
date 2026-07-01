# -*- coding: utf-8 -*-
"""Korean plain-text status rendering for AgentOps (read-only).

Turns the same state files /status reads (queue, active task, last failure,
stop flag, interruption) into a short Korean paragraph plus a next-action hint,
so a non-developer user sees plain sentences instead of raw JSON.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .core import STATE, LOGS, REPORTS, now, read_json, tail_jsonl, is_stop_requested, atomic_write_text
from .queue_manager import summary as queue_summary
from .state_manager import detect_interruption

_STATUS_KO = {
    "pending": "대기",
    "active": "진행중",
    "done": "완료",
    "failed": "실패",
    "blocked": "차단됨",
    "unknown": "알수없음",
}

def _last_failure() -> Dict[str, Any]:
    rows: List[Any] = tail_jsonl(LOGS / "failure_log.jsonl", 1)
    if rows and isinstance(rows[-1], dict):
        return rows[-1]
    return {}

def gather_status() -> Dict[str, Any]:
    """Collect the same read-only data /status uses."""
    return {
        "timestamp": now(),
        "stop_requested": is_stop_requested(),
        "interruption": detect_interruption(),
        "queue": queue_summary(),
        "active_task": read_json(STATE / "ACTIVE_TASK.json", {}),
        "last_failure": _last_failure(),
    }

def _next_action_ko(data: Dict[str, Any]) -> str:
    counts = (data.get("queue") or {}).get("counts", {}) or {}
    active = data.get("active_task") or {}
    if data.get("stop_requested"):
        return "중지 플래그가 설정되어 있습니다. 재개하려면 `python agent_ops/agentops.py unstop` 을 실행하세요."
    if (data.get("interruption") or {}).get("interrupted"):
        return "이전 실행이 중단된 것으로 보입니다. `/start` 또는 `python agent_ops/agentops.py resume` 으로 복구하세요."
    if active.get("status") == "active" and active.get("title"):
        return f"진행 중인 작업이 있습니다: '{active.get('title')}'. `/continue` 로 한 단계 진행하세요."
    if int(counts.get("pending", 0)) > 0:
        return "대기 중인 작업이 있습니다. `/work <목표>` 또는 `/continue` 로 진행하세요."
    if int(counts.get("failed", 0)) > 0:
        return "실패한 작업이 있습니다. `/fix` 로 자가 복구를 시도하세요."
    return "대기 중인 작업이 없습니다. `/work <목표>` 로 새 작업을 시작하세요."

def render_status_ko(data: Dict[str, Any] | None = None) -> str:
    if data is None:
        data = gather_status()
    queue = data.get("queue") or {}
    counts = queue.get("counts", {}) or {}
    total = queue.get("total", 0)
    active = data.get("active_task") or {}
    last_fail = data.get("last_failure") or {}

    count_parts = []
    for key in ("pending", "active", "done", "failed", "blocked"):
        if key in counts:
            count_parts.append(f"{_STATUS_KO.get(key, key)} {counts[key]}개")
    count_line = ", ".join(count_parts) if count_parts else "작업 없음"

    if active.get("status") == "active" and active.get("title"):
        active_line = f"현재 작업: '{active.get('title')}' (종류: {active.get('kind', '-')})"
    else:
        active_line = "현재 진행 중인 작업이 없습니다."

    stop_line = "중지 플래그: 켜짐" if data.get("stop_requested") else "중지 플래그: 꺼짐"

    if last_fail.get("type"):
        fail_line = f"최근 실패 유형: {last_fail.get('type')}"
    else:
        fail_line = "최근 실패 기록: 없음"

    lines = [
        "AgentOps 상태 요약",
        f"- 큐: 총 {total}개 ({count_line})",
        f"- {active_line}",
        f"- {stop_line}",
        f"- {fail_line}",
        f"- 다음 권장 조치: {_next_action_ko(data)}",
        f"- 갱신 시각: {data.get('timestamp')}",
    ]
    return "\n".join(lines)

def write_status_ko(data: Dict[str, Any] | None = None) -> str:
    text = render_status_ko(data)
    atomic_write_text(REPORTS / "STATUS_KO.md", "# AgentOps 상태 (한국어)\n\n" + text + "\n")
    return text
