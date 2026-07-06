# -*- coding: utf-8 -*-
"""루틴(record & replay) 검증 — 검증된 도구 호출을 저장→LLM 없이 재생."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from agent_ops import routines as R  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


class _Disp:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.calls = []

    def dispatch(self, call):
        self.calls.append(call["name"])
        if self.fail_at and len(self.calls) == self.fail_at:
            return {"ok": False, "error": "boom"}
        return {"ok": True}


def main() -> None:
    d = Path(tempfile.mkdtemp())
    diag = d / "diag"
    diag.mkdir()
    R.ROUTINES_DIR = d / "routines"

    entries = [
        {"tool": "write_file", "arguments": {"path": "x", "content": "a"}, "ok": False},
        {"tool": "write_file", "arguments": {"path": "보고서.md", "content": "c"}, "ok": True},
        {"tool": "run_diagnostic", "arguments": {}, "ok": True},   # 일회성 → 제외
        {"tool": "list_dir", "arguments": {"path": "."}, "ok": True},
    ]
    (diag / "tool-dispatch-history.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries), encoding="utf-8")

    steps = R.routine_from_history(diag)
    check("마지막 성공블록만 추출(실패 이전 제외)", [s["tool"] for s in steps] == ["write_file", "list_dir"], str(steps))
    check("일회성 도구(run_diagnostic) 제외", all(s["tool"] != "run_diagnostic" for s in steps))

    res = R.save_routine("월간보고", steps, "테스트")
    check("루틴 저장", res["ok"] and res["step_count"] == 2, str(res))
    check("한글 이름 조회", any(x["name"] == "월간보고" for x in R.list_routines()))

    loaded = R.load_routine("월간보고")
    check("한글 대상 인자 보존", loaded["steps"][0]["arguments"]["path"] == "보고서.md")

    ok = R.run_routine("월간보고", _Disp())
    check("전체 성공 재생", ok["ok"] and ok["total"] == 2, str(ok))

    stopped = R.run_routine("월간보고", _Disp(fail_at=2))
    check("실패 단계에서 중단", not stopped["ok"] and stopped["stopped_at"] == 2, str(stopped))

    check("빈 단계 저장 거부", not R.save_routine("빈것", [])["ok"])
    check("없는 루틴 재생 안전", not R.run_routine("없음", _Disp())["ok"])

    print(f"\nALL {PASS} CHECKS PASSED (routines)")


if __name__ == "__main__":
    main()
