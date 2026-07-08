# -*- coding: utf-8 -*-
"""앱 어댑터 도구(전체 노출) + 자율 유지(하루 2회) 회귀 테스트.

script-style: `python tests/test_adapter_tools_maintain.py` 로 개별 실행."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASS = 0


def check(label, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        raise SystemExit(1)


def main():
    # 격리된 기억/USERDATA
    tmp = Path(tempfile.mkdtemp(prefix="adapter_maint_"))
    os.environ["AGENTOPS_MEMORY_DIR"] = str(tmp / "memory")

    import importlib
    import agent_ops.core as core; importlib.reload(core)
    import agent_ops.memory_manager as M; importlib.reload(M)
    import agent_ops.auto_maintain as A; importlib.reload(A)
    from agent_ops.tool_dispatch import REGISTRY, tool_definitions

    # --- Part A: 어댑터 도구 노출 ---
    adapters = {"excel_app", "outlook_app", "hwp_app", "solidworks_app", "ocr_screen",
                "desktop_ui", "matlab_run", "fluent_run", "autocad_run"}
    names = {x["function"]["name"] for x in tool_definitions()}
    check("9개 어댑터 도구 등록", adapters.issubset(names), str(sorted(adapters - names)))

    # 앱 없는 환경: 크래시 없이 우아한 실패(app_unavailable) — Office COM 미설치 가정
    r = REGISTRY["excel_app"]["fn"](Path("."), {"action": "read_range", "path": "x.xlsx"})
    check("앱 없으면 우아한 실패", r.get("ok") is False and r.get("root_cause_category") == "app_unavailable", str(r))

    # 잘못된 action 거부(임의 어댑터 호출 차단)
    r = REGISTRY["outlook_app"]["fn"](Path("."), {"action": "DELETE_ALL"})
    check("잘못된 action 거부", r.get("ok") is False and r.get("root_cause_category") == "invalid_argument", str(r))

    # 필수 인자 누락
    r = REGISTRY["matlab_run"]["fn"](Path("."), {})
    check("경로형 필수 인자 누락 감지", r.get("ok") is False and r.get("root_cause_category") == "missing_argument", str(r))

    # capabilities는 앱 없이도 응답(진단성)
    r = REGISTRY["ocr_screen"]["fn"](Path("."), {"action": "capabilities"})
    check("ocr capabilities 진단 응답", isinstance(r, dict) and "ok" in r, str(r))

    # --- Part B: 자율 유지 ---
    # 첫 호출 실행 + 마커 생성
    r1 = A.maybe_maintain()
    check("첫 유지 실행 + 마커 생성", r1.get("ran") is True and A.MARKER.exists(), str(r1))
    # 즉시 재호출 스로틀
    r2 = A.maybe_maintain()
    check("즉시 재호출 스로틀", r2.get("ran") is False and r2.get("reason") == "throttled", str(r2))

    # 중복 정리 + 보호(user/high 는 아카이브 금지)
    M.add_memory_event("lesson", "동일제목", "첫째", source="agent")
    M.add_memory_event("lesson", "동일제목", "둘째", source="agent")
    M.add_memory_event("preference", "동일제목", "사용자규칙", source="user", priority="high")
    d = A.dedup_memories()
    active = M.load_memory(status="active")
    agent_dupes = [x for x in active if x.get("source") == "agent" and x.get("title") == "동일제목"]
    user_kept = [x for x in active if x.get("source") == "user" and x.get("title") == "동일제목"]
    check("agent 중복 1개로 축소", len(agent_dupes) == 1, str(len(agent_dupes)))
    check("user/high 보호(아카이브 안 됨)", len(user_kept) == 1, str(len(user_kept)))
    check("아카이브 카운트 정확", d.get("count") == 1, str(d))

    # 자율 유지 예외가 add_memory_event 를 막지 않음(훅이 try/except)
    item = M.add_memory_event("lesson", "정상저장", "본문", source="agent")
    check("훅 있어도 기억 저장 정상", bool(item.get("id")), str(item))

    # --- Part C: 반복 실패 승격 + stall 계측 (WS-6) ---
    from agent_ops.core import read_jsonl, write_jsonl

    def _err_row(i, day, dedupe, title="자가 관찰 실수: excel"):
        return {"id": f"mem_test{i}", "created_at": f"{day}T10:00:00",
                "updated_at": f"{day}T10:00:00", "kind": "error_pattern",
                "status": "active", "priority": "normal", "source": "self_observed",
                "title": title, "body": f"원인 상세 {dedupe}",
                "tags": ["excel", f"dedupe:{dedupe}"], "importance": 0.7,
                "supersedes": [], "superseded_by": None, "review_after_days": 14}

    rows = [r for r in read_jsonl(M.MEMORY_JSONL) if isinstance(r, dict)]
    rows += [
        # 그룹 X: 같은 dedupe 해시, 서로 다른 3일 → 승격 대상
        _err_row(1, "2026-07-01", "aaaa111111"),
        _err_row(2, "2026-07-02", "aaaa111111"),
        _err_row(3, "2026-07-03", "aaaa111111"),
        # 그룹 Y: 서로 다른 2일뿐 → 승격 안 함
        _err_row(4, "2026-07-01", "bbbb222222", title="자가 관찰 실수: hwp"),
        _err_row(5, "2026-07-02", "bbbb222222", title="자가 관찰 실수: hwp"),
        # 그룹 Z: 같은 날 3회(중복 관측) → 서로 다른 날 아님, 승격 안 함
        _err_row(6, "2026-07-05", "cccc333333", title="자가 관찰 실수: ocr"),
        _err_row(7, "2026-07-05", "cccc333333", title="자가 관찰 실수: ocr"),
        _err_row(8, "2026-07-05", "cccc333333", title="자가 관찰 실수: ocr"),
    ]
    # 사용자 기억(user_rule/preference)은 3일 반복돼도 대상 아님
    for i, day in enumerate(["2026-07-01", "2026-07-02", "2026-07-03"]):
        rows.append({"id": f"mem_user{i}", "created_at": f"{day}T09:00:00",
                     "updated_at": f"{day}T09:00:00", "kind": "preference",
                     "status": "active", "priority": "normal", "source": "user",
                     "title": "사용자 규칙 반복", "body": "규칙", "tags": [],
                     "importance": 0.9, "supersedes": [], "superseded_by": None,
                     "review_after_days": 14})
    write_jsonl(M.MEMORY_JSONL, rows)
    count_before = len(rows)

    pr = A.promote_repeated_failures(min_count=3)
    check("서로 다른 3일 관측 그룹만 승격", pr.get("promoted") == 1 and pr.get("groups") == 1, str(pr))

    after = [r for r in read_jsonl(M.MEMORY_JSONL) if isinstance(r, dict)]
    check("원본 비파괴(개수 불변 또는 증가)", len(after) >= count_before,
          f"{count_before} -> {len(after)}")
    grp_x = [r for r in after if "dedupe:aaaa111111" in (r.get("tags") or [])]
    check("그룹 X 원본 3건 모두 유지", len(grp_x) == 3, str(len(grp_x)))
    rep = [r for r in grp_x if A.REPEATED_TAG in (r.get("tags") or [])]
    check("대표 항목만 승격(priority=high + 태그)",
          len(rep) == 1 and rep[0].get("priority") == "high"
          and rep[0].get("id") == "mem_test3", str(rep))
    grp_y = [r for r in after if "dedupe:bbbb222222" in (r.get("tags") or [])]
    grp_z = [r for r in after if "dedupe:cccc333333" in (r.get("tags") or [])]
    check("2일 관측 그룹은 승격 안 함",
          all(x.get("priority") == "normal" for x in grp_y), str(grp_y))
    check("같은 날 반복 그룹은 승격 안 함",
          all(x.get("priority") == "normal" for x in grp_z), str(grp_z))
    users = [r for r in after if r.get("source") == "user" and r.get("title") == "사용자 규칙 반복"]
    check("user preference 는 승격 대상 아님",
          len(users) == 3 and all(x.get("priority") == "normal"
                                  and A.REPEATED_TAG not in (x.get("tags") or []) for x in users),
          str(users))
    # 멱등: 재호출해도 다시 승격하지 않는다
    pr2 = A.promote_repeated_failures(min_count=3)
    check("승격 멱등(재호출 시 0)", pr2.get("promoted") == 0, str(pr2))

    # stall 계측: 순수 조회 — 700초 간격 1개면 stalls=1
    import json as _json
    audit_dir = tmp / "logs"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "audit.jsonl"
    audit_file.write_text("\n".join(_json.dumps(e) for e in [
        {"ts": "2026-07-08T10:00:00", "kind": "tool", "name": "a"},
        {"ts": "2026-07-08T10:11:40", "kind": "tool", "name": "b"},  # +700s → stall
        {"ts": "2026-07-08T10:12:00", "kind": "tool", "name": "c"},
    ]) + "\n", encoding="utf-8")
    import agent_ops.activity_timeline as T
    st = T.recent_stalls(threshold_seconds=600, audit_path=audit_file)
    check("recent_stalls 멈춤 1구간 감지", st.get("stalls") == 1 and st.get("events") == 3, str(st))
    st0 = T.recent_stalls(audit_path=audit_dir / "없는파일.jsonl")
    check("audit 없으면 stalls=0", st0.get("stalls") == 0 and st0.get("events") == 0, str(st0))

    # maybe_maintain summary 계측 키 + 스로틀 유지
    os.environ["LIG_AUDIT_DIR"] = str(audit_dir)
    r3 = A.maybe_maintain(force=True)
    check("summary에 promoted/stalls 키",
          r3.get("ran") is True and "promoted" in r3 and "stalls" in r3, str(r3))
    check("summary stalls 계측 반영", r3.get("stalls") == 1, str(r3))
    r4 = A.maybe_maintain()
    check("계측 후에도 스로틀 동작", r4.get("ran") is False and r4.get("reason") == "throttled", str(r4))
    os.environ.pop("LIG_AUDIT_DIR", None)

    print(f"\nALL {PASS} CHECKS PASSED (adapter tools + auto maintain + WS-6 promote/stalls)")


if __name__ == "__main__":
    main()
