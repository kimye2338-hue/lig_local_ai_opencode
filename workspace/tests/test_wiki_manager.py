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

    # --- 커뮤니티 확장 기법 (2026-07-05): 별칭/모순후보/백링크/강화신호 ---
    # ① 별칭 확장: "엑셀"(한글)로 물어도 "excel"(영문) 페이지를 찾는다.
    #    페이지 이름/그룹핑은 안 바뀐다 — 검색 시점에만 넓힌다.
    alias_pages = wm.recall_pages(["엑셀"])
    check("alias expansion finds excel page via 엑셀",
          alias_pages and alias_pages[0]["topic"] == "excel", str(alias_pages)[:120])
    aliases_file = json.loads(wm.ALIASES_FILE.read_text(encoding="utf-8"))
    check("aliases file seeded with excel<->엑셀", "엑셀" in aliases_file.get("excel", []),
          str(aliases_file.get("excel")))

    # ② 반복 확인(강화 신호): "엑셀 피벗 교훈" 중복 제목이 lint 에도 잡히지만
    #    페이지에는 긍정적 신호("반복 확인된 규칙/교훈")로도 나타나야 한다.
    check("page shows reinforcement note for repeated title",
          "반복 확인된 규칙/교훈" in page.read_text(encoding="utf-8"))

    # ③ 모순 후보: 같은 주제("결재")에서 부정어 유무가 갈리고 문구가 겹치는
    #    쌍을 lint 가 찾아야 한다 — 어느 쪽이 맞는지 자동 판단하지 않는다.
    add_memory_event("preference", "결재 승인 규칙", "부서장 결재 없이 진행하면 안 된다",
                     tags=["결재", "승인"])
    add_memory_event("preference", "결재 승인 예외", "긴급 건은 부서장 결재 없이 진행한다",
                     tags=["결재", "승인"])
    report2 = wm.lint()
    # 태그가 둘 다 붙어 있어("결재","승인") 어느 쪽 주제 버킷이 먼저 잡는지는
    # 순서에 따라 달라질 수 있다 — 같은 쌍이 두 주제 중 하나에서만 잡히면 된다
    # (동일 쌍 중복 보고 방지를 위해 전역 dedup 하기 때문).
    check("lint flags contradiction candidate",
          any(c["topic"] in ("결재", "승인") for c in report2["contradictions"]),
          str(report2["contradictions"]))
    check("contradiction report never deletes either side",
          any("결재 승인 규칙" in c["a_title"] or "결재 승인 규칙" in c["b_title"]
              for c in report2["contradictions"]))

    # ④ 백링크: manual/ 페이지가 [[excel]] 을 언급하면 excel.md 에 역방향으로
    #    나타나야 한다 (obsidian-llm-wiki 의 bidirectional link).
    (wm.MANUAL_DIR / "포털노트.md").write_text("# 포털 노트\n엑셀 자동화는 [[excel]] 참고.\n",
                                              encoding="utf-8")
    wm.consolidate()
    excel_text = page.read_text(encoding="utf-8")
    check("backlink from manual page appears on excel.md",
          "## 언급된 곳" in excel_text and "manual/포털노트" in excel_text, excel_text[-400:])

    # --- WS-4: 사람이 쓴 manual/ 노트도 자동 recall (읽기 전용) ---
    # ①·④ frontmatter 없는 manual 노트 — 본문이 통째로 살아 excerpt 에 나온다.
    ws4_note = wm.MANUAL_DIR / "출장정산 꿀팁.md"
    ws4_note.write_text("# 출장 정산\n법인카드 출장정산은 전표를 먼저 끊는다.\n",
                        encoding="utf-8")
    from agent_ops.memory_manager import MEMORY_JSONL
    ledger_before = MEMORY_JSONL.read_text(encoding="utf-8")
    manual_before = {p.name: p.read_text(encoding="utf-8")
                     for p in wm.MANUAL_DIR.glob("*.md")}
    ws4 = wm.recall_pages(["출장정산"])
    check("WS-4 manual note recalled with source=manual",
          ws4 and ws4[0]["source"] == "manual" and ws4[0]["topic"] == "출장정산 꿀팁",
          str(ws4)[:150])
    check("WS-4 frontmatter-less manual body survives in excerpt",
          "전표를 먼저 끊는다" in ws4[0]["excerpt"], str(ws4)[:200])
    # ② auto+manual 같은 키워드 → 결과에 manual 최소 1개 포함 (auto 는 source=auto)
    both = wm.recall_pages(["excel"], limit=2)
    check("WS-4 mixed recall keeps auto page with source=auto",
          any(x["source"] == "auto" and x["topic"] == "excel" for x in both), str(both)[:200])
    check("WS-4 mixed recall guarantees at least one manual",
          any(x["source"] == "manual" for x in both), str(both)[:200])
    # limit=1 이라도 manual 매칭이 있으면 manual 이 최소 1개 슬롯을 확보한다.
    one = wm.recall_pages(["excel"], limit=1)
    check("WS-4 manual slot guaranteed even at limit=1",
          len(one) == 1 and one[0]["source"] == "manual", str(one)[:200])
    # ③ recall 은 읽기 전용 — manual 원본/원장 모두 불변이어야 한다.
    check("WS-4 recall never mutates manual notes",
          {p.name: p.read_text(encoding="utf-8")
           for p in wm.MANUAL_DIR.glob("*.md")} == manual_before)
    check("WS-4 recall never back-feeds the ledger",
          MEMORY_JSONL.read_text(encoding="utf-8") == ledger_before)

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
    # WS-4 이후: tool_dispatch 는 limit=1 로 부르고, manual 매칭이 있으면 manual
    # 노트가 최소 1개 슬롯을 확보한다 — 여기서는 excel수동노트가 주입된다.
    # (auto 페이지 주입 자체는 위 recall_pages 검사들이 보장.)
    check("agent loop injects wiki page knowledge",
          any("축적된 주제 지식(위키" in t and ("VBProject" in t or "수동 노트" in t)
              for t in sys_texts),
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
    check("book shows contradiction banner", "모순 후보" in html_text and "결재 승인 규칙" in html_text)

    # --- memorycheck 가 위키 정리를 포함 ---
    from agent_ops.memory_manager import memorycheck
    mc = memorycheck()
    check("memorycheck runs wiki consolidate+lint",
          isinstance(mc.get("wiki", {}).get("consolidate", {}).get("pages"), int)
          and "duplicates" in mc["wiki"]["lint"], str(mc.get("wiki"))[:150])

    print(f"\nALL {PASS} CHECKS PASSED (llm wiki)")


if __name__ == "__main__":
    main()
