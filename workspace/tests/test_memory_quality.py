# -*- coding: utf-8 -*-
"""WS-9 기억 품질 관리 회귀 — 등급 분류 + 안전 apply(삭제 없음, 사용자 기억 불변).

기억은 AGENTOPS_MEMORY_DIR=tmp 로 격리 — 실제 USERDATA 를 절대 건드리지 않는다.

Run: py -3.11 tests\\test_memory_quality.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

# import 전에 지정해야 한다 — core.MEMORY 는 모듈 import 시점에 굳는다.
TMP = Path(tempfile.mkdtemp(prefix="agentops_mem_quality_"))
os.environ["AGENTOPS_MEMORY_DIR"] = str(TMP)
os.environ.pop("AGENTOPS_ROOT", None)

from agent_ops import memory_manager as M  # noqa: E402
from agent_ops import memory_quality as Q  # noqa: E402
from agent_ops.core import read_jsonl, write_jsonl  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def _day(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%dT10:00:00")


def _row(rid, kind, source, priority="normal", title="t", body="b",
         days_ago=0, status="active", importance=0.5, tags=None):
    return {"id": rid, "created_at": _day(days_ago), "updated_at": _day(days_ago),
            "kind": kind, "status": status, "priority": priority, "source": source,
            "title": title, "body": body, "tags": tags or [],
            "importance": importance, "supersedes": [], "superseded_by": None,
            "review_after_days": 14}


def main() -> None:
    check("기억 격리(tmp)", str(M.MEMORY) == str(TMP), str(M.MEMORY))

    # ── 등급 분류 ────────────────────────────────────────────────────────
    check("등급: source=user → user_rule",
          Q.classify_grade(_row("g1", "note", "user")) == "user_rule")
    check("등급: preference", Q.classify_grade(_row("g2", "preference", "agent")) == "preference")
    check("등급: project_fact", Q.classify_grade(_row("g3", "project_fact", "agent")) == "project_fact")
    check("등급: activity", Q.classify_grade(_row("g4", "activity", "agent")) == "activity")
    check("등급: error_pattern", Q.classify_grade(_row("g5", "error_pattern", "self_observed")) == "error_pattern")
    check("등급: lesson → candidate", Q.classify_grade(_row("g6", "lesson", "agent")) == "candidate")
    check("protected: source=manual", Q.is_protected(_row("g7", "note", "manual")))
    check("비protected: agent activity", not Q.is_protected(_row("g8", "activity", "agent")))

    # ── 원장 시드 ────────────────────────────────────────────────────────
    rows = [
        # 보호 대상들 — 어떤 경우에도 불변이어야 한다 (오래돼도!)
        _row("u1", "preference", "user", priority="high", title="사용자 규칙",
             body="보고서 제목은 [부서명]으로", days_ago=200),
        _row("u2", "project_fact", "agent", title="프로젝트 사실",
             body="게이트웨이는 H100", days_ago=200),
        _row("u3", "note", "manual", title="수동 메모", body="수동", days_ago=200),
        _row("u4", "activity", "user", title="사용자가 남긴 활동", body="유지", days_ago=200),
        # 오래된 activity → decay(archived) 대상
        _row("a1", "activity", "agent", priority="low", title="옛날 작업",
             body="산출물", days_ago=90),
        # 최근 activity → 유지
        _row("a2", "activity", "agent", priority="low", title="최근 작업",
             body="산출물", days_ago=2),
        # 완전 동일 내용 activity 중복(다른 날) → 오래된 쪽만 superseded
        _row("d1", "activity", "agent", priority="low", title="중복 작업", body="같은 내용", days_ago=10),
        _row("d2", "activity", "agent", priority="low", title="중복 작업", body="같은 내용", days_ago=3),
        # 같은 패턴 candidate 3일 반복 → 최신 대표만 promote
        _row("p1", "lesson", "task_success", title="반복 교훈", body="1", days_ago=5),
        _row("p2", "lesson", "task_success", title="반복 교훈", body="2", days_ago=4),
        _row("p3", "lesson", "task_success", title="반복 교훈", body="3", days_ago=3),
        # 1회 관측 저가치 오래된 candidate → priority 하향
        _row("c1", "log", "agent", title="일회성 로그", body="x", days_ago=90, importance=0.2),
        # error_pattern 은 WS-6 소관 — keep
        _row("e1", "error_pattern", "self_observed", title="자가 관찰 실수: excel",
             body="원인", days_ago=90, tags=["dedupe:abc"]),
    ]
    write_jsonl(M.MEMORY_JSONL, rows)
    before = {r["id"]: dict(r) for r in read_jsonl(M.MEMORY_JSONL)}

    # ── 순수 판정(부수효과 없음) ─────────────────────────────────────────
    decisions = {d["id"]: d for d in Q.quality_decisions(rows)}
    check("판정: 보호 대상은 전원 keep+protected",
          all(decisions[i]["decision"] == "keep" and decisions[i]["protected"]
              for i in ("u1", "u2", "u3", "u4")),
          str({i: decisions[i] for i in ("u1", "u2", "u3", "u4")}))
    check("판정: 오래된 activity 는 decay", decisions["a1"]["decision"] == "decay", str(decisions["a1"]))
    check("판정: 최근 activity 는 keep", decisions["a2"]["decision"] == "keep", str(decisions["a2"]))
    check("판정: 동일 내용 오래된 쪽만 dedupe_superseded",
          decisions["d1"]["decision"] == "dedupe_superseded"
          and decisions["d1"].get("superseded_by") == "d2"
          and decisions["d2"]["decision"] == "keep",
          str((decisions["d1"], decisions["d2"])))
    check("판정: 3일 반복 candidate 최신 대표만 promote",
          decisions["p3"]["decision"] == "promote"
          and decisions["p1"]["decision"] == "keep"
          and decisions["p2"]["decision"] == "keep",
          str((decisions["p1"], decisions["p3"])))
    check("판정: 1회 관측 저가치 candidate 는 decay",
          decisions["c1"]["decision"] == "decay", str(decisions["c1"]))
    check("판정: error_pattern 은 keep(WS-6 위임)",
          decisions["e1"]["decision"] == "keep", str(decisions["e1"]))
    check("판정은 순수(원장 미변경)",
          {r["id"]: dict(r) for r in read_jsonl(M.MEMORY_JSONL)} == before)

    # ── dry_run: 집계만, 기록 없음 ──────────────────────────────────────
    dr = Q.apply_quality(dry_run=True)
    check("dry_run 미기록", {r["id"]: dict(r) for r in read_jsonl(M.MEMORY_JSONL)} == before, str(dr))
    check("dry_run 집계", dr["promoted"] == 1 and dr["decayed"] == 2
          and dr["superseded"] == 1, str(dr))

    # ── apply: 삭제 없음 + 보호 불변 + status/priority 만 변경 ───────────
    res = Q.apply_quality()
    after_rows = [r for r in read_jsonl(M.MEMORY_JSONL) if isinstance(r, dict)]
    after = {r["id"]: r for r in after_rows}

    # ② 원장 행 삭제 없음(행 id 집합 불변, 개수 불변)
    check("② 행 id 집합 불변(삭제 없음)",
          set(after) == set(before) and len(after_rows) == len(rows),
          f"{sorted(set(before) - set(after))}")

    # ① 보호 대상 status/priority 불변
    for i in ("u1", "u2", "u3", "u4"):
        check(f"① 보호 불변: {i}",
              after[i]["status"] == before[i]["status"]
              and after[i]["priority"] == before[i]["priority"]
              and after[i]["tags"] == before[i]["tags"],
              str(after[i]))
    check("protected_untouched 집계", res["protected_untouched"] == 4, str(res))

    # ③ 오래된 activity 만 decay — 내용 보존, status/priority 만 변경
    check("③ 오래된 activity archived(내용 보존)",
          after["a1"]["status"] == "archived" and after["a1"]["body"] == "산출물"
          and after["a1"]["title"] == "옛날 작업", str(after["a1"]))
    check("③ 최근 activity 는 그대로 active", after["a2"]["status"] == "active", str(after["a2"]))
    check("③ 저가치 candidate priority 하향(행 유지)",
          after["c1"]["priority"] == "low" and after["c1"]["status"] == "active"
          and after["c1"]["body"] == "x", str(after["c1"]))

    # ⑤ dedupe 는 삭제가 아니라 status 변경
    check("⑤ 중복 오래된 쪽 status=superseded(행 유지)",
          after["d1"]["status"] == "superseded"
          and after["d1"]["superseded_by"] == "d2"
          and after["d2"]["status"] == "active", str(after["d1"]))

    # promote: 태그/우선순위만
    check("promote: priority=high + 태그",
          after["p3"]["priority"] == "high" and Q.PROMOTED_TAG in after["p3"]["tags"]
          and after["p3"]["body"] == "3", str(after["p3"]))
    check("error_pattern 불변(WS-6 소관)",
          after["e1"]["priority"] == before["e1"]["priority"]
          and after["e1"]["status"] == "active", str(after["e1"]))

    # 멱등: 재호출 시 변경 0
    res2 = Q.apply_quality()
    check("멱등(재호출 변경 0)", res2["changed"] == 0
          and res2["promoted"] == 0 and res2["superseded"] == 0, str(res2))

    # ④ recall: user_rule/preference 가 activity 보다 우선
    write_jsonl(M.MEMORY_JSONL, [
        _row("r1", "preference", "user", priority="high", title="보고서 규칙",
             body="보고서 제목 규칙", days_ago=40),
        _row("r2", "activity", "agent", priority="low", title="보고서 작성 작업",
             body="보고서 산출물 보고서 보고서", days_ago=1, importance=0.9),
    ])
    rec = M.recall(keywords=["보고서"], limit=2)
    check("④ recall 최상위 = 사용자 규칙(activity 하향)",
          rec and rec[0]["id"] == "r1", str([r.get("id") for r in rec]))

    # auto_maintain 배선: summary 에 quality 집계가 실린다
    import agent_ops.auto_maintain as A
    summary = A.maybe_maintain(force=True)
    check("auto_maintain summary 에 quality",
          isinstance(summary.get("quality"), dict)
          and set(summary["quality"]) >= {"promoted", "decayed", "superseded",
                                          "protected_untouched"},
          str(summary))

    # intelligence_map 등록
    from agent_ops.intelligence_map import by_id
    item = by_id().get("memory:memory_quality")
    check("intelligence_map 에 memory:memory_quality",
          item is not None and item.status == "auto" and "삭제 없음" in item.safety,
          str(item))

    print(f"\nALL {PASS} CHECKS PASSED (memory quality)")


if __name__ == "__main__":
    main()
