# -*- coding: utf-8 -*-
"""자율 기억·위키 유지 — 사용자가 아무것도 호출하지 않아도 알아서 돈다.

`add_memory_event` 꼬리에서 `maybe_maintain()`이 불린다. 마커로 스로틀해
하루 약 2회(기본 11.5시간 간격)만 무거운 정리를 수행한다:
  1) 위키 consolidate 최신화 + lint(중복/모순/정체 탐지 → wiki/log.md)
  2) 기억 중복 정리(정규화 제목이 같으면 최고가치 1개만 남기고 아카이브;
     source=user / priority=high 는 항상 보호)
  3) 지식책 재생성

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
        summary["dedup_error"] = repr(exc)[:120]
    # 3) 지식책 재생성(위키는 방금 통합했으니 재통합 생략)
    try:
        from .knowledge_book import build_book
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
