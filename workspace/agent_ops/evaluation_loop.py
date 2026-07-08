# -*- coding: utf-8 -*-
"""WS-8 self-evaluation and growth loop.

Every /auto run is scored after the fact so the system leaves evidence for its
next choice. Hard constraints (AUTO_ORCHESTRATION philosophy):

- 평가는 **보조 신호**다. auto_policy/safety/approval을 대체하거나 바꾸지 않는다.
  이 모듈은 auto_policy를 import하지 않고, 정책 입력으로도 쓰이지 않는다.
- 단일 성공은 장기 선호가 되지 않는다: route_preferences는 표본이
  MIN_SAMPLES(3) 미만인 route를 preference로 승격하지 않는다.
- 저장은 append-only JSONL(DIAG_DIR/evaluations.jsonl)이며 USERDATA의
  기억/위키/일정 파일은 건드리지 않는다. 저장 실패는 조용히 무시된다.

Score fields (EvaluationRecord["scores"], all 0.0~1.0):

- route_confidence  높을수록 라우팅 확신이 높았다 (planner/routing/capability).
- tool_success      1.0 성공, 0.0 실패, 0.5 중립(dry_run/미실행).
- artifact_quality  산출물 검증 신호가 있으면 반영, 없으면 0.5 중립.
- user_friction     높을수록 사용자를 귀찮게 했다 (ask_user=높음, 조용한 실행=0).
- learning_value    기억으로 남길 가치 (완료후크 발화/실패 교훈은 높음).
- safety_margin     높을수록 보수적으로 행동했다 (blocked=1.0, 조용한 실행=0.5).

score_run은 순수 함수(부수효과 없음)이고 같은 trace에 대해 결정적이다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

MIN_SAMPLES = 3          # 이 미만 표본의 route는 선호로 승격하지 않는다.
PROMOTION_THRESHOLD = 0.7  # growth_report의 승격 후보 커트라인(신호 노출용).

_CONFIDENCE_SCORE = {"high": 0.9, "medium": 0.6, "low": 0.3}


def _default_eval_path() -> Path:
    """Evaluation JSONL under DIAG_DIR (env LIG_DIAG_DIR isolates tests)."""
    env_dir = os.environ.get("LIG_DIAG_DIR", "").strip()
    if env_dir:
        return Path(env_dir) / "evaluations.jsonl"
    from agent_ops.lig_providers import DIAG_DIR
    return DIAG_DIR / "evaluations.jsonl"


def _clamp(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 3)


def score_run(trace: dict, outcome: str = "", timestamp: str = "") -> dict:
    """Score one /auto run from its trace. Pure, offline, deterministic.

    ``outcome``/``timestamp``는 비어 있으면 trace 값을 쓴다. trace에도 없을
    때만 core.now()로 채운다(그 외에는 시계에 의존하지 않는다).
    """
    trace = trace or {}
    outcome = (outcome or trace.get("outcome") or "unknown")
    mode = trace.get("effective_mode") or (
        "dry_run" if trace.get("dry_run") else trace.get("policy", {}).get("mode", ""))
    exit_code = trace.get("exit_code")
    policy = trace.get("policy") or {}

    # route_confidence: 라우팅이 얼마나 확신 있었나.
    caps = trace.get("capabilities") or []
    top_conf = (caps[0].get("confidence") if caps else "") or ""
    route_confidence = _CONFIDENCE_SCORE.get(top_conf, 0.4)
    if trace.get("routing") == "default_fallback" or trace.get("selected_path") == "plan_only":
        route_confidence = min(route_confidence, 0.2)
    if trace.get("planner_mode") == "llm":
        route_confidence = _clamp(route_confidence + 0.05)

    # tool_success: 실행 결과. 실행되지 않은 모드는 중립.
    if outcome in {"dry_run", "needs_confirmation", "blocked"}:
        tool_success = 0.5
    elif outcome == "failed" or (isinstance(exit_code, int) and exit_code != 0):
        tool_success = 0.0
    elif outcome == "completed" and (exit_code in (0, None)):
        tool_success = 1.0
    else:
        tool_success = 0.5

    # artifact_quality: 검증 신호가 있으면 반영, 없으면 중립.
    artifact_quality = 0.5
    quality = trace.get("artifact_quality")
    if isinstance(quality, dict) and quality:
        verdicts = [bool(v.get("ok")) for v in quality.values() if isinstance(v, dict)]
        if verdicts:
            artifact_quality = _clamp(sum(verdicts) / len(verdicts))
    else:
        verification = [str(v).lower() for v in (trace.get("verification") or [])]
        if any("fail" in v for v in verification):
            artifact_quality = 0.2

    # user_friction: 사용자를 얼마나 귀찮게 했나 (높을수록 마찰 큼).
    if mode == "ask_user" or outcome == "needs_confirmation" or policy.get("requires_confirmation"):
        user_friction = 0.8
    elif trace.get("policy_override"):
        user_friction = 0.4  # 사용자가 --yes로 직접 승격 = 개입 1회 있었음.
    elif mode == "blocked" or outcome == "blocked":
        user_friction = 0.6  # 요청이 거부되어 대안 상호작용이 필요.
    else:
        user_friction = 0.0

    # learning_value: 기억으로 남길 가치.
    hooks = " ".join(str(h) for h in (trace.get("memory_hooks") or []))
    if outcome == "failed":
        learning_value = 0.8  # 실패 교훈은 다음 선택에 가장 값지다.
    elif "_complete_activity fired" in hooks:
        learning_value = 0.7
    elif "delegated" in hooks:
        learning_value = 0.6
    elif outcome == "dry_run":
        learning_value = 0.2
    else:
        learning_value = 0.4

    # safety_margin: 얼마나 보수적으로 행동했나.
    if mode == "blocked" or outcome == "blocked":
        safety_margin = 1.0
    elif mode == "ask_user" or outcome == "needs_confirmation":
        safety_margin = 0.9
    elif mode == "plan_only" or trace.get("selected_path") == "plan_only":
        safety_margin = 0.8
    elif trace.get("policy_override"):
        safety_margin = 0.4  # 사용자가 확인을 승격시켰으니 여유는 줄었다.
    else:
        safety_margin = 0.5

    ts = timestamp or trace.get("timestamp") or ""
    if not ts:
        from agent_ops.core import now
        ts = now()
    return {
        "timestamp": ts,
        "request": str(trace.get("request") or "")[:200],
        "route": trace.get("selected_path", ""),
        "command": trace.get("command", ""),
        "mode": mode or "unknown",
        "outcome": outcome,
        "scores": {
            "route_confidence": _clamp(route_confidence),
            "tool_success": _clamp(tool_success),
            "artifact_quality": _clamp(artifact_quality),
            "user_friction": _clamp(user_friction),
            "learning_value": _clamp(learning_value),
            "safety_margin": _clamp(safety_margin),
        },
        "note": "auxiliary signal only; does not alter policy/safety",
    }


def append_evaluation(record: dict, path: Optional[Path] = None) -> None:
    """Append one EvaluationRecord as a JSONL line. Never raises.

    append-only: 기존 줄은 절대 다시 쓰지 않는다. 경로 기본값은 DIAG_DIR
    (진단 영역)이며 USERDATA 기억/위키 파일에는 접근하지 않는다.
    """
    try:
        target = Path(path) if path else _default_eval_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with target.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _load_records(path: Optional[Path], limit: int) -> list[dict]:
    try:
        target = Path(path) if path else _default_eval_path()
        if not target.exists():
            return []
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    records: list[dict] = []
    for line in lines[-max(1, int(limit)):]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            records.append(row)
    return records


def _record_quality(record: dict) -> float:
    """Single comparable quality number per record (higher is better)."""
    scores = record.get("scores") or {}
    keys = ("route_confidence", "tool_success", "artifact_quality")
    vals = [float(scores.get(k, 0.5)) for k in keys]
    return round(sum(vals) / len(vals), 3)


def route_preferences(limit: int = 200, path: Optional[Path] = None,
                      min_samples: int = MIN_SAMPLES) -> dict:
    """Aggregate recent evaluations per route. Read-only signal.

    단일 성공 과잉승격 금지: 표본 min_samples 미만인 route는 preferences에
    올리지 않고 insufficient로만 노출한다. 이 함수는 auto_policy를 바꾸지
    않는다 — 신호를 보여줄 뿐이다.
    """
    grouped: dict[str, list[float]] = {}
    for rec in _load_records(path, limit):
        route = rec.get("route") or rec.get("command") or "unknown"
        grouped.setdefault(route, []).append(_record_quality(rec))
    preferences: dict[str, dict] = {}
    insufficient: dict[str, int] = {}
    for route, vals in grouped.items():
        if len(vals) < min_samples:
            insufficient[route] = len(vals)
            continue
        preferences[route] = {
            "avg_score": round(sum(vals) / len(vals), 3),
            "samples": len(vals),
        }
    return {
        "preferences": preferences,
        "insufficient": insufficient,
        "min_samples": min_samples,
        "note": "read-only signal; single successes are not promoted; policy unchanged",
    }


def growth_report(limit: int = 500, path: Optional[Path] = None) -> dict:
    """Human-readable growth summary over recent evaluations."""
    records = _load_records(path, limit)
    command_counts: dict[str, int] = {}
    ask_user = blocked = failed = completed = 0
    history: dict[str, list[float]] = {}
    for rec in records:
        cmd = rec.get("command") or "unknown"
        command_counts[cmd] = command_counts.get(cmd, 0) + 1
        outcome = rec.get("outcome", "")
        if outcome == "needs_confirmation" or rec.get("mode") == "ask_user":
            ask_user += 1
        if outcome == "blocked":
            blocked += 1
        if outcome == "failed":
            failed += 1
        if outcome == "completed":
            completed += 1
        route = rec.get("route") or "unknown"
        history.setdefault(route, []).append(
            float((rec.get("scores") or {}).get("tool_success", 0.5)))
    improved = []
    for route, successes in history.items():
        # 반복 실패 후 나중에 성공으로 돌아선 route만 개선으로 본다.
        if len(successes) >= 2 and 0.0 in successes:
            first_fail = successes.index(0.0)
            if any(v >= 1.0 for v in successes[first_fail + 1:]):
                improved.append(route)
    prefs = route_preferences(limit=limit, path=path)
    promotion_candidates = sorted(
        route for route, info in prefs["preferences"].items()
        if info["avg_score"] >= PROMOTION_THRESHOLD)
    return {
        "total_runs": len(records),
        "command_distribution": dict(sorted(command_counts.items())),
        "ask_user_count": ask_user,
        "blocked_count": blocked,
        "failed_count": failed,
        "completed_count": completed,
        "improved_routes": sorted(improved),
        "promotion_candidates": promotion_candidates,
        "promotion_candidate_count": len(promotion_candidates),
        "held_routes": dict(sorted(prefs["insufficient"].items())),
        "min_samples": prefs["min_samples"],
        "note": "평가는 보조 신호 — 안전/정책을 대체하지 않는다",
    }
