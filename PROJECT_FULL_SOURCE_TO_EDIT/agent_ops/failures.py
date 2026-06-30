# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, List

from .core import LOGS, REPORTS, now, append_jsonl, tail_jsonl, atomic_write_text
from .memory_manager import add_memory_event

def classify_failure(text: str) -> str:
    lower = (text or "").lower()
    if "llm not configured" in lower or "agentops_llm_base_url" in lower:
        return "LLM_NOT_CONFIGURED"
    if "tool call not allowed while generating summary" in lower or "looking at the conversation" in lower:
        return "SUMMARY_LOOP"
    if "bash {" in text or ("\"command\"" in text and "bash" in lower):
        return "TOOL_TEXT_ONLY"
    if "chromedriver" in lower and ("not found" in lower or "cannot find" in lower or "경로" in text):
        return "CHROMEDRIVER_NOT_FOUND"
    if "127.0.0.1:9222" in lower or "debuggeraddress" in lower or "chrome attach" in lower:
        return "CHROME_ATTACH_FAILED"
    if "syntaxerror" in lower or "unterminated string" in lower or "invalid syntax" in lower:
        return "PY_SYNTAX_ERROR"
    if "python -c" in lower and ("error" in lower or "syntax" in lower or "traceback" in lower):
        return "LONG_COMMAND_ESCAPE_FAIL"
    if "�" in text or "蹂" in text or "二쇱" in text:
        return "ENCODING_GARBAGE"
    if "no data" in lower or "empty result" in lower or "0 rows" in lower:
        return "NO_DATA"
    if "session expired" in lower or "login required" in lower or ("otp" in lower and "expired" in lower):
        return "SESSION_EXPIRED"
    if "risky action" in lower or "blocked action" in lower or "dangerous action" in lower:
        return "RISKY_ACTION_BLOCKED"
    if "unapproved" in lower and ("resume" in lower or "next step" in lower):
        return "UNAPPROVED_RESUME_ACTION"
    return "UNKNOWN"

def classify_failure_with_history(text: str, recent: List[Any]) -> str:
    ftype = classify_failure(text)
    recent_types = [r.get("type") for r in recent[-3:] if isinstance(r, dict)]
    if ftype != "UNKNOWN" and recent_types.count(ftype) >= 2:
        return "REPEATED_FAILURE"
    return ftype

def log_failure(text: str, source: str = "manual", task_id: str = "") -> Dict[str, Any]:
    recent = tail_jsonl(LOGS / "failure_log.jsonl", 5)
    ftype = classify_failure_with_history(text, recent)
    data = {"timestamp": now(), "source": source, "task_id": task_id, "type": ftype, "text_tail": (text or "")[-4000:]}
    append_jsonl(LOGS / "failure_log.jsonl", data)
    # Dedupe error-pattern memory: only record if this type isn't already in the
    # recent failure window (prevents co-growth memory from becoming co-bloat).
    recent_types = [r.get("type") for r in tail_jsonl(LOGS / "failure_log.jsonl", 10) if isinstance(r, dict)]
    if recent_types.count(ftype) <= 1:
        add_memory_event(
            kind="error_pattern",
            title=f"Failure pattern {ftype}",
            body=f"Observed failure type `{ftype}`. Source: {source}. Tail: {(text or '')[-800:]}",
            status="active",
            priority="high" if ftype in {"REPEATED_FAILURE", "RISKY_ACTION_BLOCKED", "UNAPPROVED_RESUME_ACTION"} else "normal",
            source="failure_log",
            tags=[ftype.lower()],
        )
    return data

RECOVERY_MAP = {
    "LLM_NOT_CONFIGURED": ["Set AGENTOPS_LLM_BASE_URL/API_KEY/MODEL or use non-LLM task kinds.", "Do not retry llm_plan until configured."],
    "SUMMARY_LOOP": ["Stop summary writes inside compaction.", "Read COMPACT_HANDOFF.md and RESUME_PLAN.md.", "Continue one bounded task only."],
    "TOOL_TEXT_ONLY": ["Stop printing fake tool JSON.", "Use real OpenCode tool interface.", "If unreliable, create normal script files."],
    "ENCODING_GARBAGE": ["Keep BAT ASCII-only.", "Use UTF-8 Python IO.", "Regenerate affected reports."],
    "CHROMEDRIVER_NOT_FOUND": ["Run doctor.", "Check CHROMEDRIVER_PATH.", "Check configured driver paths."],
    "CHROME_ATTACH_FAILED": ["Run doctor.", "Verify Chrome launched with --remote-debugging-port=9222.", "Do not automate login/OTP."],
    "PY_SYNTAX_ERROR": ["Back up file.", "Regenerate from safe template.", "Run py_compile."],
    "LONG_COMMAND_ESCAPE_FAIL": ["Ban long python -c.", "Use normal files or OpenCode write.", "Run py_compile."],
    "NO_DATA": ["Confirm source files/results exist.", "Generate report with missing-data caveat.", "Do not invent data."],
    "REPEATED_FAILURE": ["Stop retrying same action.", "Block current task.", "Escalate to repair/verifier or user review."],
    "SESSION_EXPIRED": ["Do not bypass login.", "Ask user to login manually if needed.", "Resume after authenticated Chrome is ready."],
    "RISKY_ACTION_BLOCKED": ["Do not click/execute risky action.", "Record blocker.", "Continue other safe tasks."],
    "UNAPPROVED_RESUME_ACTION": ["Treat resume next steps as planned, not approved.", "Block risky action.", "Require explicit current-session approval."],
    "UNKNOWN": ["Run doctor.", "Capture full error.", "Classify manually if needed."],
}

def make_selfheal_plan() -> Dict[str, Any]:
    failures = tail_jsonl(LOGS / "failure_log.jsonl", 10)
    latest = failures[-1] if failures and isinstance(failures[-1], dict) else {"type": "UNKNOWN", "text_tail": ""}
    ftype = latest.get("type", "UNKNOWN")
    actions = RECOVERY_MAP.get(ftype, RECOVERY_MAP["UNKNOWN"])
    plan = {
        "timestamp": now(),
        "latest_failure": latest,
        "failure_type": ftype,
        "actions": actions,
        "next_owner": "agentops-repair" if ftype in {"PY_SYNTAX_ERROR", "LONG_COMMAND_ESCAPE_FAIL", "ENCODING_GARBAGE"} else "agentops-supervisor",
        "requires_user": ftype in {"SESSION_EXPIRED", "RISKY_ACTION_BLOCKED", "UNAPPROVED_RESUME_ACTION"},
    }
    lines = ["# Self-Heal Plan", "", f"- Generated: {plan['timestamp']}", f"- Failure type: `{ftype}`", f"- Next owner: `{plan['next_owner']}`", f"- Requires user: `{plan['requires_user']}`", "", "## Recommended actions"]
    lines.extend(f"{idx+1}. {action}" for idx, action in enumerate(actions))
    lines += ["", "## Latest failure", "```json", json.dumps(latest, ensure_ascii=False, indent=2), "```"]
    atomic_write_text(REPORTS / "SELFHEAL_PLAN.md", "\n".join(lines))
    return plan
