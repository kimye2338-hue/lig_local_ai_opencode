# -*- coding: utf-8 -*-
"""LLM Wiki 회귀 — 복리 구조(주제 페이지·링크·정리·recall)가 실제로 작동하는가.

Run: py -3.11 tests\\test_wiki_manager.py  (리눅스에서도 동작 — stdlib only)

검증하는 복리 성질:
  - 기록이 쌓이면 '같은 페이지'가 두꺼워진다 (새 파일이 아니라 제자리 성장).
  - 관련 주제는 [[위키링크]]로 연결된다 (연결이 지식).
  - remember 한 번마다 위키가 자동 갱신된다 (ingest 워크플로).
  - recall 이 원장 사건뿐 아니라 '증류된 페이지'를 프롬프트에 주입한다.
  - lint 가 중복/고아를 보고한다 (자동 삭제는 없음).
  - LLM 큐레이션은 품질 게이트를 통과할 때만 반영, 게이트웨이 없으면 무해.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

TMP = Path(tempfile.mkdtemp(prefix="wiki_mgr_"))
os.environ["AGENTOPS_ROOT"] = str(TMP / "ws")
(TMP / "ws").mkdir(parents=True, exist_ok=True)
os.environ.pop("AGENTOPS_MEMORY_DIR", None)
os.environ.pop("AGENTOPS_PROJECT_DIR", None)

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
    from agent_ops import wiki_manager as wm
    from agent_ops.memory_manager import add_memory_event

    # --- ingest: remember 만으로 페이지가 생긴다 (자동 통합) ---
    add_memory_event("preference", "엑셀 보고서 규칙", "엑셀 보고서는 항상 사본에서 작업",
                     tags=["excel", "보고서"])
    add_memory_event("lesson", "엑셀 매크로 교훈", "excel 매크로는 VBProject 접근 허용 필요",
                     tags=["excel", "매크로"])
    add_memory_event("error_pattern", "엑셀 원본 수정 실수", "원본 xlsx 직접 수정으로 데이터 손상",
                     tags=["excel"])
    add_memory_event("lesson", "보고서 제목 형식", "보고서 제목은 [부서명]으로 시작",
                     tags=["보고서"])
    page = wm.WIKI_DIR / "excel.md"
    check("remember auto-creates topic page", page.is_file(), str(list(wm.WIKI_DIR.glob('*'))))
    text = page.read_text(encoding="utf-8")
    check("page has kind sections", "## 규칙·선호" in text and "## 배운 것" in text
          and "## 실수 노트" in text)
    check("page bullets carry ledger facts", "사본에서 작업" in text and "VBProject" in text)
    check("related topics use wikilinks", "[[보고서]]" in text or "[[매크로]]" in text, text[-300:])
    check("page marked auto-generated", wm.AUTO_MARK in text)
    check("schema seeded", wm.SCHEMA_FILE.is_file()
          and "복리 지식 위키" in wm.SCHEMA_FILE.read_text(encoding="utf-8"))
    check("index catalogs pages", wm.INDEX_FILE.is_file()
          and "[[excel]]" in wm.INDEX_FILE.read_text(encoding="utf-8"))
    check("operation log appended", wm.LOG_FILE.is_file()
          and "[consolidate]" in wm.LOG_FILE.read_text(encoding="utf-8"))

    # --- 복리: 기록 추가 → 같은 페이지가 두꺼워진다 ---
    before_records = text.count("- **")
    add_memory_event("lesson", "엑셀 피벗 교훈", "excel 피벗은 원본 시트를 참조로",
                     tags=["excel", "피벗"])
    text2 = page.read_text(encoding="utf-8")
    check("page compounds in place", text2.count("- **") == before_records + 1
          and "피벗" in text2, f"{before_records} -> {text2.count('- **')}")
    stats = wm.consolidate()
    text3 = page.read_text(encoding="utf-8")
    check("consolidate idempotent (no dup bullets)", text3.count("피벗은 원본 시트") == 1)

    # --- schema/manual 은 불가침 ---
    wm.SCHEMA_FILE.write_text("# 내가 고친 스키마\n", encoding="utf-8")
    (wm.MANUAL_DIR / "excel수동노트.md").write_text("# 수동 노트\n내 글\n", encoding="utf-8")
    wm.consolidate()
    check("customized schema preserved",
          wm.SCHEMA_FILE.read_text(encoding="utf-8").startswith("# 내가 고친 스키마"))
    check("manual pages untouched + indexed",
          (wm.MANUAL_DIR / "excel수동노트.md").read_text(encoding="utf-8") == "# 수동 노트\n내 글\n"
          and "manual/excel수동노트" in wm.INDEX_FILE.read_text(encoding="utf-8"))

    # --- lint: 중복 제목 + 고아 페이지 보고 ---
    add_memory_event("lesson", "엑셀 피벗 교훈", "같은 제목 중복", tags=["excel"])
    (wm.WIKI_DIR / "옛주제.md").write_text("---\ntopic: 옛주제\n---\n" + wm.AUTO_MARK + "\n# 옛주제\n",
                                          encoding="utf-8")
    report = wm.lint()
    check("lint flags duplicate titles",
          any("엑셀 피벗 교훈" in d["title"] for d in report["duplicates"]), str(report["duplicates"]))
    check("lint flags orphan pages", "옛주제" in report["orphan_pages"], str(report["orphan_pages"]))
    check("lint never deletes", (wm.WIKI_DIR / "옛주제.md").is_file())

    # --- recall_pages + 에이전트 루프 주입 ---
    pages = wm.recall_pages(["excel", "매크로"])
    check("recall_pages returns distilled excerpt",
          pages and pages[0]["topic"] == "excel" and "VBProject" in pages[0]["excerpt"], str(pages)[:120])

    from agent_ops.tool_dispatch import run_agent_loop
    captured = {}

    def fake_transport(url, payload, headers, timeout):
        captured["messages"] = payload["messages"]
        return {"choices": [{"message": {"content": "완료"}}]}

    env = {"LIG_GATEWAY_BASE_URL": "http://127.0.0.1:9", "LIG_API_KEY": "x",
           "LIG_DEFAULT_PROVIDER": "lig-coding"}
    run_agent_loop("excel 매크로 만들어줘", TMP / "ws", env=env, transport=fake_transport,
                   diag_dir=TMP / "diag")
    sys_texts = [m["content"] for m in captured["messages"] if m["role"] == "system"]
    check("agent loop injects wiki page knowledge",
          any("위키 'excel'" in t and "VBProject" in t for t in sys_texts),
          str([t[:50] for t in sys_texts]))

    # --- curate: 품질 게이트 + 게이트웨이 부재 무해 ---
    good = wm.curate(["excel"], llm=lambda p: "excel 작업의 핵심: 엑셀 보고서 규칙과 매크로 "
                                              "교훈을 지켜 사본에서만 작업한다. 피벗은 참조로.")
    check("curate accepts anchored summary", good["curated"] == ["excel"], str(good))
    check("curated summary lands on page + stale marker fields",
          "LLM 정리" in page.read_text(encoding="utf-8"))
    bad = wm.curate(["excel"], llm=lambda p: "무관한 말")
    check("curate quality gate rejects unanchored", bad["curated"] == []
          and bad["skipped"][0]["reason"] == "quality_gate", str(bad))
    def boom(p):
        raise OSError("no gateway")
    offline = wm.curate(["excel"], llm=boom)
    check("curate offline-safe", offline["curated"] == []
          and "llm_unavailable" in offline["skipped"][0]["reason"], str(offline))
    add_memory_event("lesson", "엑셀 새 교훈", "curate 이후 추가 기록", tags=["excel"])
    check("stale curated summary marked",
          "이후 기록" in page.read_text(encoding="utf-8"), page.read_text(encoding="utf-8")[:400])

    # --- 지식책: 주제 위키 챕터 + 위키링크 앵커 ---
    from agent_ops.knowledge_book import build_book
    book = build_book()
    html_text = book.read_text(encoding="utf-8")
    check("book has topic wiki chapter", "주제별 지식 (위키)" in html_text and "id='topics'" in html_text)
    check("book renders excel page", "id='wiki-excel'" in html_text and "VBProject" in html_text)
    check("book renders wikilinks as anchors", "class='wl' href='#wiki-" in html_text)
    check("book shows manual page", "수동 노트" in html_text)

    # --- memorycheck 가 위키 정리를 포함 ---
    from agent_ops.memory_manager import memorycheck
    mc = memorycheck()
    check("memorycheck runs wiki consolidate+lint",
          isinstance(mc.get("wiki", {}).get("consolidate", {}).get("pages"), int)
          and "duplicates" in mc["wiki"]["lint"], str(mc.get("wiki"))[:150])

    print(f"\nALL {PASS} CHECKS PASSED (llm wiki)")


if __name__ == "__main__":
    main()
