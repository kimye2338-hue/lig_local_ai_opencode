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

    print(f"\nALL {PASS} CHECKS PASSED (adapter tools + auto maintain)")


if __name__ == "__main__":
    main()
