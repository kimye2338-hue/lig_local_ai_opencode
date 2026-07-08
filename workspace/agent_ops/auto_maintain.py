# -*- coding: utf-8 -*-
"""자율 기억·위키 유지 — 사용자가 아무것도 호출하지 않아도 알아서 돈다.

`add_memory_event` 꼬리에서 `maybe_maintain()`이 불린다. 마커로 스로틀해
하루 약 2회(기본 11.5시간 간격)만 무거운 정리를 수행한다:
  1) 위키 consolidate 최신화 + lint(중복/모순/정체 탐지 → wiki/log.md)
  2) 기억 중복 정리(정규화 제목이 같으면 최고가치 1개만 남기고 아카이브;
     source=user / priority=high 는 항상 보호)
  2b) 반복 실패 승격 — 같은 원인 error_pattern이 서로 다른 날 3회 이상 관측되면
      대표 항목만 priority=high + '반복확인됨' 태그(원본 비파괴, 태그/우선순위 갱신만)
  2c) stall 계측 — audit.jsonl 기반 멈춤 의심 구간을 세어 summary에 기록(관측만,
      자동 개입 없음)
  3) 지식책 재생성(원장·위키가 책보다 새것일 때만; 최신이면 skipped: fresh)

모든 단계는 best-effort — 실패해도 기억 저장/작업을 막지 않는다.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List

from .core import MEMORY, now

MARKER = MEMORY / ".maintenance.json"
DEFAULT_INTERVAL_HOURS = 11.5


def _read_marker() -> Dict[str, Any]:
    try:
        return json.loads(MARKER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _hours_since(iso: str) -> float:
    try:
        then = datetime.fromisoformat(iso)
        cur = datetime.fromisoformat(now())
        # tz-aware/naive 혼용 방지: 둘 다 naive로 비교
        if then.tzinfo is not None:
            then = then.replace(tzinfo=None)
        if cur.tzinfo is not None:
            cur = cur.replace(tzinfo=None)
        return (cur - then).total_seconds() / 3600.0
    except Exception:
        return 1e9  # 파싱 실패 시 '오래됨'으로 간주해 1회 수행


def _norm_title(row: Dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", str(row.get("title", "")).strip().lower())


def _is_protected(row: Dict[str, Any]) -> bool:
    return row.get("source") == "user" or row.get("priority") == "high"


def dedup_memories() -> Dict[str, Any]:
    """정규화 제목이 같은 active 기억 중 최고가치 1개만 남기고 나머지 아카이브.

    보호 대상(source=user / priority=high)은 절대 아카이브하지 않는다. 보호 대상이
    한 그룹에 여러 개면 모두 유지한다(사용자 규칙 손실 방지)."""
    from .memory_manager import MEMORY_JSONL, _protect_rank
    from .core import read_jsonl, write_jsonl, file_lock

    archived: List[str] = []
    with file_lock("memory"):
        rows = [r for r in read_jsonl(MEMORY_JSONL) if isinstance(r, dict)]
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            if r.get("status") == "active" and _norm_title(r):
                groups.setdefault(_norm_title(r), []).append(r)
        drop_ids = set()
        for _title, grp in groups.items():
            if len(grp) < 2:
                continue
            # 보호 대상은 후보에서 제외하고 항상 유지
            unprotected = [r for r in grp if not _is_protected(r)]
            if len(unprotected) < 2:
                continue
            # 최고가치(보호랭크 큰 것, 동률이면 최신) 1개만 남기고 나머지 아카이브
            unprotected.sort(key=lambda r: (_protect_rank(r), str(r.get("created_at", ""))), reverse=True)
            for r in unprotected[1:]:
                drop_ids.add(r.get("id"))
        if drop_ids:
            for r in rows:
                if r.get("id") in drop_ids:
                    r["status"] = "deprecated"
                    r["deprecated_reason"] = "auto-maintain: duplicate title archived"
                    archived.append(str(r.get("id")))
            write_jsonl(MEMORY_JSONL, rows)
    return {"archived": archived, "count": len(archived)}


REPEATED_TAG = "반복확인됨"


def _failure_group_key(row: Dict[str, Any]) -> str:
    """error_pattern 그룹 키 — dedupe:<sha1> 태그 우선, 없으면 정규화 제목."""
    for t in row.get("tags") or []:
        if str(t).startswith("dedupe:"):
            return str(t)
    title = _norm_title(row)
    return ("title:" + title) if title else ""


def promote_repeated_failures(min_count: int = 3) -> Dict[str, Any]:
    """같은 원인 실패가 서로 다른 날 min_count회 이상 관측되면 대표 항목을 승격.

    - 대상은 error_pattern(자가 관찰 실수)뿐 — user_rule/preference 등 사용자가
      남긴 기억은 절대 건드리지 않는다(source=user 도 방어적으로 제외).
    - 원본 비파괴: 삭제·병합·아카이브 없음. 대표 항목(그룹 내 최신)의
      priority=high + '반복확인됨' 태그만 갱신한다 — 이후 recall/core_memory와
      캡 아카이브 보호에서 반복 실수가 우선 노출·보존된다.
    - 멱등: 이미 승격된 그룹은 다시 세지 않는다.
    반환: {promoted: 갱신 수, groups: 기준 충족 그룹 수, ids: 갱신된 id}.
    """
    from .memory_manager import MEMORY_JSONL
    from .core import read_jsonl, write_jsonl, file_lock

    promoted: List[str] = []
    groups_met = 0
    with file_lock("memory"):
        rows = [r for r in read_jsonl(MEMORY_JSONL) if isinstance(r, dict)]
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            if r.get("kind") != "error_pattern" or r.get("source") == "user":
                continue
            key = _failure_group_key(r)
            if key:
                groups.setdefault(key, []).append(r)
        for _key, grp in groups.items():
            days = {str(r.get("created_at", ""))[:10] for r in grp
                    if str(r.get("created_at", ""))[:10]}
            if len(days) < max(1, min_count):
                continue
            groups_met += 1
            rep = max(grp, key=lambda r: str(r.get("created_at", "")))
            tags = [str(t) for t in (rep.get("tags") or [])]
            if REPEATED_TAG in tags and rep.get("priority") == "high":
                continue  # 이미 승격됨 — 멱등
            if REPEATED_TAG not in tags:
                tags.append(REPEATED_TAG)
            rep["tags"] = tags
            rep["priority"] = "high"
            rep["updated_at"] = now()
            promoted.append(str(rep.get("id")))
        if promoted:
            write_jsonl(MEMORY_JSONL, rows)
    return {"promoted": len(promoted), "groups": groups_met, "ids": promoted}


def maybe_maintain(force: bool = False, interval_hours: float = DEFAULT_INTERVAL_HOURS) -> Dict[str, Any]:
    """스로틀된 자율 유지. 마지막 실행 후 interval_hours 이상 지났을 때만 수행.

    반환: {ran: bool, ...요약}. 어떤 단계가 실패해도 예외를 밖으로 던지지 않는다."""
    marker = _read_marker()
    if not force and marker.get("last_run") and _hours_since(marker["last_run"]) < interval_hours:
        return {"ran": False, "reason": "throttled", "last_run": marker.get("last_run")}

    summary: Dict[str, Any] = {"ran": True, "at": now()}
    # 1) 위키 통합 + lint
    try:
        from .wiki_manager import consolidate, lint
        summary["consolidate"] = consolidate().get("pages", 0)
        rep = lint()
        summary["lint"] = {"duplicates": len(rep.get("duplicates", [])),
                           "orphans": len(rep.get("orphan_pages", [])),
                           "stale": len(rep.get("stale_topics", [])),
                           "contradictions": len(rep.get("contradictions", []))}
    except Exception as exc:  # noqa: BLE001
        summary["wiki_error"] = repr(exc)[:120]
    # 2) 기억 중복 정리
    try:
        summary["dedup"] = dedup_memories().get("count", 0)
    except Exception as exc:  # noqa: BLE001
        summary["dedup"] = 0
        summary["dedup_error"] = repr(exc)[:120]
    # 2b) 반복 실패 승격 — 관측 기반, 원본 비파괴(태그/우선순위만). 없으면 0.
    try:
        summary["promoted"] = promote_repeated_failures().get("promoted", 0)
    except Exception as exc:  # noqa: BLE001
        summary["promoted"] = 0
        summary["promote_error"] = repr(exc)[:120]
    # 2c) stall 계측 — audit.jsonl 관측/기록만, 자동 개입 없음(안전).
    try:
        from .activity_timeline import recent_stalls
        summary["stalls"] = recent_stalls().get("stalls", 0)
    except Exception as exc:  # noqa: BLE001
        summary["stalls"] = 0
        summary["stalls_error"] = repr(exc)[:120]
    # 3) 지식책 재생성(위키는 방금 통합했으니 재통합 생략).
    #    원장(memory.jsonl)·위키(WIKI.md)가 책보다 새것일 때만 다시 그린다 —
    #    변화가 없으면 skipped: fresh 로 사유를 남긴다(관측 후 최적화).
    try:
        from .knowledge_book import build_book, BOOK_FILE, WIKI_FILE
        from .memory_manager import MEMORY_JSONL
        fresh = False
        try:
            if BOOK_FILE.exists():
                book_mtime = BOOK_FILE.stat().st_mtime
                sources = [p for p in (MEMORY_JSONL, WIKI_FILE) if p.exists()]
                fresh = bool(sources) and all(p.stat().st_mtime <= book_mtime for p in sources)
        except Exception:  # noqa: BLE001 - 신선도 판정 실패 시 재생성(안전)
            fresh = False
        if fresh:
            summary["book"] = "skipped: fresh"
        else:
            build_book(refresh_wiki=False)
            summary["book"] = "rebuilt"
    except Exception as exc:  # noqa: BLE001
        summary["book_error"] = repr(exc)[:120]

    try:
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text(json.dumps({"last_run": now(), "summary": summary},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return summary
