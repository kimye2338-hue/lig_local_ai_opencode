# -*- coding: utf-8 -*-
"""방어용 <think> 스트립 회귀 테스트 (stdlib only, no network).

게이트웨이 라우트가 이미 *_think_off 라 평상시엔 no-op 이어야 하고,
think가 흘러들어온 경우에만 제거되는지 확인한다.

Run: py -3.11 tests\test_think_strip.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.toolcall_parser import parse_tool_calls, strip_reasoning  # noqa: E402
from agent_ops.lig_runtime import _message_content_text  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    # ① think 안에서 '언급'된 도구 JSON은 툴콜로 승격되면 안 된다.
    text = ('<think>도구를 쓸까? {"name": "bash", "arguments": {"command": "rm -rf /"}}'
            ' 아니다, 그냥 답하자.</think>서울의 인구는 약 940만 명입니다.')
    r = parse_tool_calls(text, available_tools=["bash", "read_file"])
    check("think 내부 도구 JSON은 툴콜로 승격 안 됨",
          r["parse_status"] == "none" and r["tool_calls"] == [], str(r))
    check("raw_excerpt에도 <think>가 남지 않음",
          "<think" not in r["raw_excerpt"] and "서울" in r["raw_excerpt"], r["raw_excerpt"])

    # ② 최종 content(_message_content_text)에 <think>가 남지 않는다.
    msg = {"content": "<think>속으로 계산...</think>답은 42입니다.",
           "reasoning_content": "이건 content로 취급되면 안 되는 reasoning"}
    out = _message_content_text(msg)
    check("최종 content에 <think> 없음", out == "답은 42입니다.", repr(out))
    check("reasoning_content 키는 무시됨", "reasoning" not in out, repr(out))
    # 멀티파트 content도 동일하게 스트립.
    out2 = _message_content_text({"content": [{"text": "<think>추론</think>확정 답변"}]})
    check("멀티파트 content도 스트립", out2 == "확정 답변", repr(out2))

    # ③ 닫는 태그 없는 선두 <think> — 잘린 출력도 안전 처리(그 지점부터 제거).
    check("닫히지 않은 선두 <think>는 통째로 제거",
          strip_reasoning("<think>중간에 끊긴 추론 {\"name\": \"bash\"") == "",
          repr(strip_reasoning("<think>중간에 끊긴")))
    r3 = parse_tool_calls('<think>끊긴 추론 {"name": "bash", "arguments": {}}',
                          available_tools=["bash"])
    check("닫히지 않은 think 속 도구 JSON도 승격 안 됨",
          r3["parse_status"] == "none" and r3["tool_calls"] == [], str(r3))

    # ④ <think 가 없는 평범한 텍스트는 원본 '그대로'(no-op, 동일 객체).
    plain = '결과 파일: {"name": "보고서.docx", "size": 3} 을 생성했습니다.'
    check("think 없는 텍스트는 no-op(동일 객체 반환)",
          strip_reasoning(plain) is plain)
    check("None-safe: falsy 입력은 그대로",
          strip_reasoning("") == "" and strip_reasoning(None) is None)  # type: ignore[arg-type]
    # 정상 툴콜은 스트립 후에도 그대로 복구된다.
    r4 = parse_tool_calls('<think>bash를 쓰자</think>{"name": "bash", "arguments": {"command": "dir"}}',
                          available_tools=["bash"])
    check("think 밖의 진짜 툴콜은 정상 복구",
          r4["parse_status"] == "repaired" and r4["tool_calls"]
          and r4["tool_calls"][0]["name"] == "bash", str(r4))

    print(f"\nALL {PASS} CHECKS PASS")


if __name__ == "__main__":
    main()
