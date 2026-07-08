# -*- coding: utf-8 -*-
"""WS-9 기억 품질 관리 — 등급 분류 + 장기 승격/감쇠 판정(순수) + 안전 apply.

철학: 많이 기억한다고 똑똑해지지 않는다. 사용자 규칙·반복 확인된 선호·검증된
사실·반복 실패 교훈만 장기 승격하고, 일회성 활동 로그는 낮은 등급으로 두었다가
시간이 지나면 정리(=상태 조정, 삭제 아님)한다.

안전 계약(위반 금지):
- user_rule/preference/project_fact, source=user, source=manual 은 절대 자동
  감쇠·중복정리하지 않는다(protected). manual 위키 노트는 이 모듈이 아예
  건드리지 않는다 — 원장(memory.jsonl)만 다룬다.
- 원장 행을 삭제하지 않는다. decay/dedupe 는 status/priority/tags 갱신뿐이며,
  apply_quality 는 쓰기 직전에 행 id 집합 불변을 검사해 다르면 기록을 포기한다.
- 반복 실패(error_pattern) 승격은 WS-6 auto_maintain.promote_repeated_failures
  가 담당한다 — 여기서는 error_pattern 을 판정 대상에서 제외한다(중복 구현 금지).
- append/rewrite 경로(add_memory_event 등)는 이 모듈과 무관하다.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List

from .core import now, read_jsonl, write_jsonl, file_lock

# 사용자가 남긴 것으로 간주해 어떤 자동 정제에서도 제외하는 범위.
PROTECTED_KINDS = {"user_rule", "preference", "project_fact"}
PROTECTED_SOURCES = {"user", "manual"}

DECAY_AFTER_DAYS = 60          # 이보다 오래된 activity 만 감쇠 후보
PROMOTE_MIN_DAYS = 3           # 같은 패턴이 서로 다른 N일 이상 관측되면 승격
LOW_VALUE_IMPORTANCE = 0.45    # 1회 관측 candidate 감쇠의 저가치 기준
PROMOTED_TAG = "품질승격"
DECAYED_TAG = "quality:decayed"


def is_protected(row: Dict[str, Any]) -> bool:
    """사용자가 남긴 기억인지 — decay/dedupe 절대 금지 대상."""
    return (str(row.get("source", "")) in PROTECTED_SOURCES
            or str(row.get("kind", "")) in PROTECTED_KINDS)


def classify_grade(record: Dict[str, Any]) -> str:
    """kind+source(+priority) 기반 등급. 반환:
    user_rule / preference / project_fact / error_pattern / activity / candidate."""
    kind = str(record.get("kind", ""))
    if record.get("source") == "user" or kind == "user_rule":
        return "user_rule"
    if kind in {"preference", "project_fact"}:
        return kind
    if kind == "error_pattern":
        return "error_pattern"
    if kind == "activity":
        return "activity"
    return "candidate"  # lesson/log/note 등 — 반복 관측 전까지 후보


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _age_days(row: Dict[str, Any]) -> float:
    """created_at 기준 경과 일수. 파싱 실패 시 0(감쇠하지 않는 쪽이 안전)."""
    try:
        created = datetime.fromisoformat(str(row.get("created_at", ""))[:19])
        cur = datetime.fromisoformat(now()[:19])
        if created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        if cur.tzinfo is not None:
            cur = cur.replace(tzinfo=None)
        return (cur - created).total_seconds() / 86400.0
    except Exception:  # noqa: BLE001 - 날짜 불명 행은 건드리지 않는다
        return 0.0


def quality_decisions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """순수 판정 — 부수효과 없음. 각 행에 대해
    {id, decision: keep|promote|decay|dedupe_superseded, reason, protected} 반환.

    - protected 행은 항상 keep.
    - error_pattern 은 keep(승격은 WS-6 promote_repeated_failures 소관).
    - promote: 같은 정규화 제목의 candidate 가 서로 다른 PROMOTE_MIN_DAYS일 이상
      관측되면 최신 active 대표만(태그/우선순위 갱신용).
    - dedupe_superseded: 제목+본문이 완전히 같은 active activity/candidate 중복에서
      최신 1개만 남기고 오래된 쪽(status 변경용, 삭제 아님).
    - decay: DECAY_AFTER_DAYS 넘은 activity, 또는 1회 관측 + 저가치 + 오래된
      candidate 만.
    """
    valid = [r for r in rows if isinstance(r, dict) and r.get("id")
             and not r.get("parse_error")]

    # 관측 횟수는 상태 불문 전체 그룹으로 센다(dedup 이 먼저 아카이브해도 반복
    # 관측 이력이 사라지면 안 됨). 갱신 대상 선정은 active 에서만 한다.
    title_groups: Dict[str, List[Dict[str, Any]]] = {}
    content_groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in valid:
        grade = classify_grade(r)
        if grade in {"candidate", "activity"} and not is_protected(r):
            key = _norm(r.get("title"))
            if key:
                title_groups.setdefault(grade + "|" + key, []).append(r)
            if r.get("status") == "active":
                content_groups.setdefault(
                    (grade, _norm(r.get("title")), _norm(r.get("body"))), []
                ).append(r)

    promote_ids: Dict[str, str] = {}   # id -> reason
    for key, grp in title_groups.items():
        if not key.startswith("candidate|"):
            continue
        days = {str(r.get("created_at", ""))[:10] for r in grp
                if str(r.get("created_at", ""))[:10]}
        if len(days) < PROMOTE_MIN_DAYS:
            continue
        actives = [r for r in grp if r.get("status") == "active"]
        if not actives:
            continue
        rep = max(actives, key=lambda r: str(r.get("created_at", "")))
        tags = [str(t) for t in (rep.get("tags") or [])]
        if rep.get("priority") == "high" and PROMOTED_TAG in tags:
            continue  # 멱등 — 이미 승격됨
        promote_ids[str(rep.get("id"))] = (
            f"같은 패턴 {len(days)}일 반복 관측 → 장기 승격(priority=high)")

    supersede_ids: Dict[str, str] = {}  # id -> newest id(살아남는 쪽)
    for (_grade, title, body), grp in content_groups.items():
        if len(grp) < 2 or not (title or body):
            continue
        grp_sorted = sorted(grp, key=lambda r: str(r.get("created_at", "")))
        newest = grp_sorted[-1]
        for old in grp_sorted[:-1]:
            supersede_ids[str(old.get("id"))] = str(newest.get("id"))

    out: List[Dict[str, Any]] = []
    for r in valid:
        rid = str(r.get("id"))
        grade = classify_grade(r)
        protected = is_protected(r)
        decision, reason = "keep", f"grade={grade}"
        if protected:
            reason = f"protected(grade={grade}) — 자동 감쇠/정리 금지"
        elif grade == "error_pattern":
            reason = "error_pattern — 승격은 WS-6 promote_repeated_failures 소관"
        elif r.get("status") != "active":
            reason = f"grade={grade}, status={r.get('status')} — 비active 미변경"
        elif rid in promote_ids:
            decision, reason = "promote", promote_ids[rid]
        elif rid in supersede_ids:
            decision = "dedupe_superseded"
            reason = f"동일 내용 중복 — 최신 {supersede_ids[rid]} 유지, 이 행은 status만 변경"
        elif grade == "activity" and _age_days(r) >= DECAY_AFTER_DAYS:
            decision = "decay"
            reason = f"activity {int(_age_days(r))}일 경과 — status=archived(삭제 아님)"
        elif (grade == "candidate"
              and len(title_groups.get("candidate|" + _norm(r.get("title")), [r])) <= 1
              and float(r.get("importance", 0.4)) < LOW_VALUE_IMPORTANCE
              and _age_days(r) >= DECAY_AFTER_DAYS
              # 멱등: 이미 감쇠된(태그 보유) 행은 다시 세지 않는다
              and DECAYED_TAG not in [str(t) for t in (r.get("tags") or [])]):
            decision = "decay"
            reason = "1회 관측 저가치 candidate — priority 하향(삭제 아님)"
        item = {"id": rid, "decision": decision, "reason": reason,
                "protected": protected}
        if decision == "dedupe_superseded":
            item["superseded_by"] = supersede_ids[rid]
        out.append(item)
    return out


def apply_quality(dry_run: bool = False) -> Dict[str, Any]:
    """판정을 원장에 반영 — status/priority/tags(+updated_at/superseded_by)만.

    행 삭제/추가 없음: 쓰기 직전 id 집합·행 개수 불변을 검사하고, 달라졌으면
    기록을 포기한다(안전 우선). dry_run=True 면 판정만 하고 기록하지 않는다.
    반환: {promoted, decayed, superseded, protected_untouched, changed, dry_run}.
    """
    from .memory_manager import MEMORY_JSONL, ensure_memory
    ensure_memory()
    counts: Dict[str, Any] = {"promoted": 0, "decayed": 0, "superseded": 0,
                              "protected_untouched": 0, "changed": 0,
                              "dry_run": bool(dry_run)}
    with file_lock("memory"):
        rows = [r for r in read_jsonl(MEMORY_JSONL) if isinstance(r, dict)]
        ids_before = [str(r.get("id")) for r in rows]
        decisions = {d["id"]: d for d in quality_decisions(rows)}
        for r in rows:
            d = decisions.get(str(r.get("id")))
            if not d:
                continue
            if d["protected"]:
                counts["protected_untouched"] += 1
                continue  # protected 는 어떤 필드도 만지지 않는다
            if d["decision"] == "promote":
                counts["promoted"] += 1
                if dry_run:
                    continue
                tags = [str(t) for t in (r.get("tags") or [])]
                if PROMOTED_TAG not in tags:
                    tags.append(PROMOTED_TAG)
                r["tags"] = tags
                r["priority"] = "high"
                r["updated_at"] = now()
                counts["changed"] += 1
            elif d["decision"] == "decay":
                counts["decayed"] += 1
                if dry_run:
                    continue
                tags = [str(t) for t in (r.get("tags") or [])]
                if DECAYED_TAG not in tags:
                    tags.append(DECAYED_TAG)
                r["tags"] = tags
                if classify_grade(r) == "activity":
                    r["status"] = "archived"   # 삭제 아님 — 원장에 그대로 남는다
                else:
                    r["priority"] = "low"
                r["updated_at"] = now()
                counts["changed"] += 1
            elif d["decision"] == "dedupe_superseded":
                counts["superseded"] += 1
                if dry_run:
                    continue
                r["status"] = "superseded"     # 삭제 아님 — status 변경만
                r["superseded_by"] = d.get("superseded_by")
                r["updated_at"] = now()
                counts["changed"] += 1
        if not dry_run and counts["changed"]:
            ids_after = [str(r.get("id")) for r in rows]
            # 행 삭제/추가 금지 계약의 최종 방어선 — 다르면 기록하지 않는다.
            if ids_after == ids_before:
                write_jsonl(MEMORY_JSONL, rows)
            else:  # pragma: no cover - 위 로직상 도달 불가, 방어적 안전장치
                counts["aborted"] = "row id set changed; write skipped"
    return counts
