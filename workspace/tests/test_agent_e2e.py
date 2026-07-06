# -*- coding: utf-8 -*-
"""Korean E2E: mock LLM tool-calls -> real file operations via run_agent_loop.

Run: py -3.11 tests\\test_agent_e2e.py
The LLM transport is mocked (scripted OpenAI-style responses, including one
malformed tool-call emitted as text). Real EXAONE/Qwen behavior remains
company validation pending.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.lig_runtime import TransportError  # noqa: E402
from agent_ops.tool_dispatch import run_agent_loop  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


ENV = {
    "LIG_GATEWAY_BASE_URL": "http://10.9.9.9/gw",
    "LIG_API_KEY": "sk-fake-secret-9999",
    "LIG_DEFAULT_PROVIDER": "lig-coding",
}


def resp_tool(name, args):
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
    ]}}]}


def resp_text(text):
    return {"choices": [{"message": {"content": text}}]}


def scripted(*events):
    seq = list(events)
    sent = []

    def transport(url, payload, headers, timeout):
        sent.append(payload)
        ev = seq.pop(0) if seq else TransportError("provider_unreachable", "script exhausted")
        if isinstance(ev, TransportError):
            raise ev
        return ev

    transport.sent = sent
    return transport


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="agentops_e2e_"))
    ws = tmp / "작업 공간"  # Korean workspace root with a space
    ws.mkdir()
    diag = tmp / "diag"

    # ------------------------------------------------------------------
    # Scenario 1: read a Korean document, write a summary, append a section,
    # replace a string, search — then finish with a text answer.
    # ------------------------------------------------------------------
    (ws / "문서").mkdir()
    (ws / "문서" / "보고서.md").write_text("# 프로젝트 보고서\n상태: 진행중\n담당: 김예찬\n", encoding="utf-8")

    transport = scripted(
        resp_tool("read_file", {"path": "문서/보고서.md"}),
        resp_tool("write_file", {"path": "문서/요약.md", "content": "# 요약\n프로젝트는 진행중이다.\n"}),
        resp_tool("append_file", {"path": "문서/보고서.md", "content": "\n## 추가 섹션\n검토 완료.\n"}),
        resp_tool("replace_in_file", {"path": "문서/보고서.md", "old": "진행중", "new": "완료"}),
        resp_tool("search_files", {"query": "완료", "pattern": "**/*.md"}),
        resp_text("보고서를 요약하고 상태를 완료로 갱신했습니다."),
    )
    r = run_agent_loop("보고서를 요약하고 상태를 갱신해라", ws, env=ENV, transport=transport, diag_dir=diag)
    check("E2E loop completed", r["ok"] and r["outcome"] == "completed", str(r))
    check("final answer is Korean text", "완료" in r["final_content"], r["final_content"])
    check("5 tools executed, all ok", len(r["tool_results"]) == 5 and all(t["ok"] for t in r["tool_results"]), str(r["tool_results"]))
    check("summary file created", (ws / "문서" / "요약.md").read_text(encoding="utf-8").startswith("# 요약"))
    report = (ws / "문서" / "보고서.md").read_text(encoding="utf-8")
    check("append + replace applied", "## 추가 섹션" in report and "완료" in report and "진행중" not in report, report)
    search_result = r["tool_results"][4]
    check("search found replaced text", len(search_result["matches"]) >= 2, str(search_result))
    # tool results were fed back to the model
    check("tool role messages sent back to LLM", any(
        m.get("role") == "tool" for m in transport.sent[-1]["messages"]), str(transport.sent[-1]["messages"])[:300])

    # ------------------------------------------------------------------
    # Scenario 2: malformed tool-call in plain text is repaired and dispatched.
    # ------------------------------------------------------------------
    transport2 = scripted(
        resp_text('도구를 호출하겠습니다: {"name": "read_file", "arguments": {"path": "문서/요약.md"},'),  # broken JSON
        resp_text("요약 파일 내용을 확인했습니다."),
    )
    r2 = run_agent_loop("요약 파일을 읽어라", ws, env=ENV, transport=transport2, diag_dir=diag)
    check("repaired text tool-call dispatched", r2["ok"] and len(r2["tool_results"]) == 1 and r2["tool_results"][0]["ok"], str(r2))

    # ------------------------------------------------------------------
    # Scenario 3: path traversal is blocked, loop still ends safely.
    # ------------------------------------------------------------------
    transport3 = scripted(
        resp_tool("write_file", {"path": "../탈출.txt", "content": "pwn"}),
        resp_text("경로가 차단되어 작업을 중단합니다."),
    )
    r3 = run_agent_loop("상위 폴더에 파일을 써라", ws, env=ENV, transport=transport3, diag_dir=diag)
    check("path traversal blocked in loop", r3["tool_results"][0]["root_cause_category"] == "path_escape", str(r3))
    check("no escape file created", not (tmp / "탈출.txt").exists())

    # ------------------------------------------------------------------
    # Scenario 4: unknown tool triggers provider-level fallback (never executed).
    # ------------------------------------------------------------------
    transport4 = scripted(
        resp_tool("delete_everything", {"path": "."}),
        resp_tool("delete_everything", {"path": "."}),
        resp_tool("delete_everything", {"path": "."}),
        resp_tool("delete_everything", {"path": "."}),
    )
    r4 = run_agent_loop("전부 지워라", ws, env=ENV, transport=transport4, diag_dir=diag)
    check("unknown tool never executed", r4["outcome"] == "llm_failed" and not r4["tool_results"], str(r4))

    # ------------------------------------------------------------------
    # Scenario 5: repeated identical failing call is cut off.
    # ------------------------------------------------------------------
    bad = resp_tool("read_file", {"path": "없는파일.txt"})
    transport5 = scripted(bad, bad, bad, bad, bad, bad)
    r5 = run_agent_loop("없는 파일을 계속 읽어라", ws, env=ENV, transport=transport5, diag_dir=diag)
    check("repeated failing call cut off", r5["outcome"] == "tool_loop_cutoff" and len(r5["tool_results"]) == 2, str(r5))

    # ------------------------------------------------------------------
    # Scenario 6: BOM+CRLF file edited through the loop keeps its style.
    # ------------------------------------------------------------------
    bom_doc = ws / "공지.txt"
    bom_doc.write_bytes(b"\xef\xbb\xbf" + "공지: 기존 내용\r\n".encode("utf-8"))
    transport6 = scripted(
        resp_tool("replace_in_file", {"path": "공지.txt", "old": "기존 내용", "new": "새 내용"}),
        resp_text("공지를 갱신했습니다."),
    )
    r6 = run_agent_loop("공지를 갱신해라", ws, env=ENV, transport=transport6, diag_dir=diag)
    raw = bom_doc.read_bytes()
    check("BOM preserved through agent edit", r6["ok"] and raw.startswith(b"\xef\xbb\xbf"), repr(raw[:20]))
    check("CRLF preserved through agent edit", raw.endswith(b"\r\n"), repr(raw[-10:]))
    check("Korean replacement applied", "새 내용" in raw.decode("utf-8-sig"))

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    check("agent-loop diagnostics written", (diag / "agent-loop-last.json").exists() and (diag / "tool-dispatch-history.jsonl").exists())
    hist = (diag / "tool-dispatch-history.jsonl").read_text(encoding="utf-8")
    check("diagnostics secret-free", "sk-fake-secret-9999" not in hist and "10.9.9.9" not in hist)

    print(f"\nALL {PASS} CHECKS PASSED (agent E2E)")


if __name__ == "__main__":
    main()
