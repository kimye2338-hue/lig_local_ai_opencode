# -*- coding: utf-8 -*-
"""지식책(knowledge_book) 회귀 — 복리 기억 구조의 계약을 고정한다.

Run: py -3.11 tests\\test_knowledge_book.py

계약:
  - 원장은 휘발되지 않는다: 보관(deprecated) 항목도 타임라인에 '보관됨'으로 남는다.
  - 책은 언제든 재생성 가능하고(멱등), 섹션(통계/복습/분류/타임라인/위키/검색)을 갖춘다.
  - 복습 회전은 결정적(같은 주=같은 목록)이고 주가 바뀌면 회전한다.
  - remember 훅이 책을 자동 갱신한다. 오프라인 자기완결(외부 URL 0).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def seed(root: Path) -> Path:
    mem = root / ".agent-memory"
    mem.mkdir(parents=True, exist_ok=True)
    rows = [
        {"id": "mem_a1", "created_at": "2026-06-01T09:00:00", "kind": "lesson",
         "status": "active", "priority": "high", "source": "user",
         "title": "몰랐다가 알게 된 것", "body": "MATLAB -batch 출력 규칙", "review_after_days": 14},
        {"id": "mem_a2", "created_at": "2026-06-02T09:00:00", "kind": "lesson",
         "status": "active", "priority": "normal", "source": "user",
         "title": "오래된 교훈 2", "body": "두번째", "review_after_days": 14},
        {"id": "mem_a3", "created_at": "2026-06-03T09:00:00", "kind": "preference",
         "status": "active", "priority": "high", "source": "user",
         "title": "보고서 제목 규칙", "body": "[부서명]으로 시작", "review_after_days": 14},
        {"id": "mem_old", "created_at": "2026-05-20T09:00:00", "kind": "preference",
         "status": "deprecated", "priority": "normal", "source": "user",
         "title": "옛 규칙", "body": "지금은 안 씀", "review_after_days": 14},
    ]
    (mem / "memory.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    (mem / "WIKI.md").write_text("# 업무 위키\n## 사용자 선호\n- 규칙 하나\n", encoding="utf-8")
    audit_dir = root / "audit"
    audit_dir.mkdir(exist_ok=True)
    (audit_dir / "audit.jsonl").write_text(json.dumps(
        {"ts": "2026-07-03T10:00:00", "kind": "work", "task": "회의록 초안", "verdict": "approved"},
        ensure_ascii=False) + "\n", encoding="utf-8")
    return mem


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, AGENTOPS_ROOT=str(root), LIG_AUDIT_DIR=str(root / "audit"),
               BRIEFING_NOW="2026-07-05 09:00", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(WS / "agent_ops" / "agentops.py"), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, cwd=str(WS))


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="book_"))
    seed(root)

    r = run_cli(root, "book")
    check("book command exits 0", r.returncode == 0, r.stdout + r.stderr)
    book = root / ".agent-memory" / "book" / "knowledge_book.html"
    check("book html written", book.exists(), str(book))
    h = book.read_text(encoding="utf-8")

    for label, needle in [
        ("통계 카드", "이번 주 새로 배움"),
        ("복습 섹션", "이번 주의 복습"),
        ("규칙·선호 분류", "내 규칙·선호"),
        ("타임라인", "나의 히스토리북"),
        ("월 그룹핑", "2026-06"),
        ("보관 항목 보존(휘발 없음)", "보관됨"),
        ("보관 항목 내용", "옛 규칙"),
        ("위키 렌더", "사용자 선호"),
        ("활동 기록", "회의록 초안"),
        ("검색 준비", "data-search"),
    ]:
        check(f"book has {label}", needle in h, needle)
    check("book is offline self-contained",
          "http://" not in h and "https://" not in h, "external url found")

    # 복습 회전: 결정적 + 주 단위 회전 (due 3개 시드 기준)
    sys.path.insert(0, str(WS))
    os.environ["AGENTOPS_ROOT"] = str(root)
    for mod in list(sys.modules):
        if mod.startswith("agent_ops"):
            del sys.modules[mod]
    from agent_ops.knowledge_book import review_picks, _load_entries  # noqa: E402
    entries = _load_entries()
    w1 = [x["id"] for x in review_picks(entries, datetime(2026, 7, 6), limit=2)]
    w1b = [x["id"] for x in review_picks(entries, datetime(2026, 7, 8), limit=2)]
    w2 = [x["id"] for x in review_picks(entries, datetime(2026, 7, 13), limit=2)]
    check("review picks deterministic within a week", w1 == w1b, f"{w1} vs {w1b}")
    check("review picks rotate across weeks", w1 != w2, f"{w1} vs {w2}")
    check("review picks only active entries", "mem_old" not in w1 + w2, str(w1 + w2))

    # remember 훅 → 책 자동 갱신
    r = run_cli(root, "remember", "훅으로 배운 것")
    check("remember exits 0", r.returncode == 0, r.stderr)
    check("remember hook rebuilt book with new entry",
          "훅으로 배운 것" in book.read_text(encoding="utf-8"), "hook missed")

    # 브리핑 '오늘의 복습' 라인
    r = run_cli(root, "briefing")
    check("briefing includes 오늘의 복습", "오늘의 복습" in r.stdout, r.stdout[-400:])

    print(f"\nALL {PASS} CHECKS PASSED (knowledge book)")


if __name__ == "__main__":
    main()
