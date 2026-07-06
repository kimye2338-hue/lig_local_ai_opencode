# -*- coding: utf-8 -*-
"""LLM Wiki — 기억 원장을 '주제별 페이지'로 증류하는 복리 지식 층.

Karpathy의 LLM Wiki 패턴(3층: raw sources / compiled wiki / schema)을
내부망·오프라인 제약에 맞게 옮긴 것:

  raw    memory.jsonl            append-only 원장 (불변 — 절대 삭제 안 함)
  wiki   MEMORY/wiki/*.md        주제별 페이지 — 기록이 쌓일수록 같은 페이지가
                                 두꺼워진다(복리). [[위키링크]]로 서로 연결.
         MEMORY/wiki/index.md    페이지 카탈로그 (한 줄 요약 + 개수)
         MEMORY/wiki/log.md      운영 로그 (consolidate/lint/curate 이력)
         MEMORY/wiki/manual/     사람이 쓰는 페이지 — 여기는 절대 안 건드림
  schema MEMORY/wiki/WIKI_SCHEMA.md  유지보수 규칙 (에이전트/사람 공용, 1회 시드)

원칙:
  - 자동 페이지는 원장에서 '결정적으로' 재생성된다 — LLM 없이도 항상 동작.
    (같은 원장 → 같은 페이지. 손실 없음: 원장이 진실.)
  - 사람 편집은 WIKI.md 와 wiki/manual/ 에서만 — 자동 페이지 상단에 명시.
  - LLM 큐레이션(개요 다듬기)은 '선택' — curated.json 사이드카에 저장하고,
    이후 기록이 더 쌓이면 낡음(stale)을 표시한다. 게이트웨이 없어도 무해.
  - lint 가 중복/고아/정체를 찾아 log.md 에 남긴다 (자동 삭제는 없음).

Obsidian 호환: 폴더(MEMORY/wiki)를 Obsidian vault 로 열면 [[링크]] 그래프가
그대로 보인다. 파일명은 주제 슬러그(한글 허용, 경로 위험문자만 치환).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .core import MEMORY, atomic_write_text, now, read_jsonl, read_text

WIKI_DIR = MEMORY / "wiki"
MANUAL_DIR = WIKI_DIR / "manual"
INDEX_FILE = WIKI_DIR / "index.md"
LOG_FILE = WIKI_DIR / "log.md"
SCHEMA_FILE = WIKI_DIR / "WIKI_SCHEMA.md"
CURATED_FILE = WIKI_DIR / "curated.json"

MAX_PAGES = 40          # 빈도순 상위 주제만 페이지化 (노이즈 태그 방지)
MIN_EVENTS = 2          # 주제 페이지가 되려면 최소 기록 수
MAX_BULLETS = 30        # 페이지 섹션당 최대 항목 (오래된 것은 원장 참조로)
AUTO_MARK = "<!-- auto-generated: 원장(memory.jsonl)에서 재생성됨 — 직접 편집은 WIKI.md 또는 wiki/manual/ 에 -->"

KIND_SECTION = (
    ("preference", "규칙·선호"),
    ("lesson", "배운 것"),
    ("error_pattern", "실수 노트"),
)

SCHEMA_SEED = """# WIKI_SCHEMA — 이 위키의 유지보수 규칙 (에이전트/사람 공용)

이 폴더는 OpenCodeLIG 의 '복리 지식 위키'다. 구조와 규칙:

## 3층 구조
1. 원장: `../memory.jsonl` — append-only. 절대 수정/삭제하지 않는다.
2. 위키(이 폴더): 주제별 페이지. `<주제>.md` 는 원장에서 자동 재생성된다.
3. 스키마: 이 문서. 규칙이 바뀌면 여기에 기록한다.

## 페이지 규칙
- 자동 페이지는 손으로 고치지 않는다 (재생성 시 사라짐). 고치고 싶으면:
  - 지식 자체가 틀렸다 → 새로 기억시킨다 ("기억해: ...") — 원장에 쌓여 페이지에 반영.
  - 서술을 남기고 싶다 → `manual/` 에 같은 주제의 페이지를 만든다 (절대 안 건드림).
- 링크는 `[[주제]]` 형식. 연결이 지식이다 — 관련 주제는 반드시 링크한다.
- `index.md` 는 카탈로그다. 페이지를 추가하면 index 도 갱신된다(자동).

## 운영 워크플로
- ingest: 새 기억 저장 → 관련 주제 페이지들 갱신 + log.md 한 줄.
- lint: 중복 제목/고아 페이지/오래 정체된 페이지를 찾아 log.md 에 보고.
- curate: (게이트웨이 있을 때만) 페이지 개요를 LLM 이 다듬는다 — 원장은 불변.

## 에이전트에게
새 지식을 발견하면 remember 도구로 원장에 남겨라. 위키는 따라온다.
페이지와 모순되는 사실을 발견하면 그것도 remember 로 남겨라 — lint 가 잡는다.
"""


def _events() -> List[Dict[str, Any]]:
    from .memory_manager import MEMORY_JSONL, ensure_memory
    ensure_memory()
    return [r for r in read_jsonl(MEMORY_JSONL) if isinstance(r, dict)]


def _slug(topic: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|#\[\]\s]+", "_", str(topic).strip()).strip("._")
    return (s or "topic")[:60]


def _event_tags(row: Dict[str, Any]) -> List[str]:
    tags = [str(t).strip().lower() for t in (row.get("tags") or []) if str(t).strip()]
    if tags:
        return tags
    from .memory_manager import extract_keywords
    return extract_keywords(str(row.get("title", "")) + " " + str(row.get("body", "")))[:6]


def _topic_map(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """주제(태그) → 기록 목록. 빈도 MIN_EVENTS 이상, 상위 MAX_PAGES 개."""
    freq: Counter = Counter()
    tagged: List[Tuple[Dict[str, Any], List[str]]] = []
    for r in rows:
        tags = [t for t in _event_tags(r) if len(t) >= 2]
        tagged.append((r, tags))
        freq.update(set(tags))
    topics = [t for t, n in freq.most_common(MAX_PAGES * 2) if n >= MIN_EVENTS][:MAX_PAGES]
    topic_set = set(topics)
    out: Dict[str, List[Dict[str, Any]]] = {t: [] for t in topics}
    for r, tags in tagged:
        for t in tags:
            if t in topic_set:
                out[t].append(r)
    return out


def _related(topic: str, topic_rows: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """같은 기록을 공유하는 다른 주제 = 관련 주제 (연결이 지식)."""
    ids = {r.get("id") for r in topic_rows.get(topic, [])}
    scored = []
    for other, rows in topic_rows.items():
        if other == topic:
            continue
        overlap = sum(1 for r in rows if r.get("id") in ids)
        if overlap:
            scored.append((overlap, other))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [t for _n, t in scored[:6]]


def _bullet(r: Dict[str, Any]) -> str:
    day = str(r.get("created_at", ""))[:10]
    title = str(r.get("title", "")).strip()
    body = str(r.get("body", "")).strip().replace("\n", " ")
    if len(body) > 200:
        body = body[:200] + "…"
    line = f"- **{day}** {title}"
    if body and body != title:
        line += f" — {body}"
    if r.get("status") != "active":
        line += " *(보관됨)*"
    return line


def _load_curated() -> Dict[str, Any]:
    try:
        data = json.loads(read_text(CURATED_FILE) or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _page_markdown(topic: str, rows: List[Dict[str, Any]],
                   related: List[str], curated: Optional[Dict[str, Any]]) -> str:
    active = [r for r in rows if r.get("status") == "active"]
    rows_sorted = sorted(rows, key=lambda r: str(r.get("created_at", "")), reverse=True)
    kinds = Counter(str(r.get("kind", "")) for r in active)
    updated = str(rows_sorted[0].get("created_at", ""))[:10] if rows_sorted else ""

    lines = [
        "---",
        f"topic: {topic}",
        f"updated: {updated}",
        f"records: {len(rows)}",
        f"active: {len(active)}",
        "---",
        AUTO_MARK,
        "",
        f"# {topic}",
        "",
    ]
    # 개요: 큐레이션본이 있으면 우선 (이후 기록이 더 쌓였으면 낡음 표시)
    if curated and str(curated.get("summary", "")).strip():
        lines.append(str(curated["summary"]).strip())
        newer = len(rows) - int(curated.get("records", 0) or 0)
        stamp = str(curated.get("updated", ""))[:10]
        note = f"*(LLM 정리 {stamp}"
        if newer > 0:
            note += f" — 이후 기록 {newer}건 추가됨, 아래 최신 항목 참고"
        lines.append(note + ")*")
    else:
        summary = (f"이 주제로 {len(active)}건의 현행 지식"
                   + (f" (규칙 {kinds.get('preference', 0)} · 배움 {kinds.get('lesson', 0)}"
                      f" · 실수 {kinds.get('error_pattern', 0)})" if active else "")
                   + f", 누적 {len(rows)}건.")
        lines.append(summary)
    lines.append("")

    for kind, section in KIND_SECTION:
        items = [r for r in rows_sorted if str(r.get("kind")) == kind and r.get("status") == "active"]
        if not items:
            continue
        lines.append(f"## {section}")
        lines.extend(_bullet(r) for r in items[:MAX_BULLETS])
        if len(items) > MAX_BULLETS:
            lines.append(f"- … 외 {len(items) - MAX_BULLETS}건 (원장 참조)")
        lines.append("")
    others = [r for r in rows_sorted
              if str(r.get("kind")) not in {k for k, _s in KIND_SECTION} and r.get("status") == "active"]
    if others:
        lines.append("## 기타 기록")
        lines.extend(_bullet(r) for r in others[:MAX_BULLETS])
        lines.append("")

    if related:
        lines.append("## 관련 주제")
        lines.append(" · ".join(f"[[{t}]]" for t in related))
        lines.append("")
    lines.append(f"*원장 근거: {', '.join(str(r.get('id')) for r in rows_sorted[:10])}"
                 + (" …" if len(rows_sorted) > 10 else "") + "*")
    return "\n".join(lines) + "\n"


def _log(kind: str, message: str) -> None:
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now()[:19]
    line = f"- {stamp} [{kind}] {message}\n"
    if LOG_FILE.exists():
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    else:
        LOG_FILE.write_text("# 위키 운영 로그 (append-only)\n\n" + line, encoding="utf-8")


def ensure_schema() -> None:
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    if not SCHEMA_FILE.exists():
        SCHEMA_FILE.write_text(SCHEMA_SEED, encoding="utf-8")


def consolidate() -> Dict[str, Any]:
    """원장 → 주제 페이지 재생성 (결정적). 반환: 요약 통계."""
    ensure_schema()
    rows = _events()
    topic_rows = _topic_map(rows)
    curated_all = _load_curated()

    written: List[str] = []
    slugs: Dict[str, str] = {t: _slug(t) for t in topic_rows}
    for topic, trows in topic_rows.items():
        page = _page_markdown(topic, trows, _related(topic, topic_rows),
                              curated_all.get(topic))
        path = WIKI_DIR / f"{slugs[topic]}.md"
        if read_text(path) != page:
            atomic_write_text(path, page)
            written.append(topic)

    # 고아 자동 페이지 제거가 아니라 '보관' 표시: 원장이 진실이므로 페이지는
    # 지우지 않고 orphan 마크만 남긴다 (lint 가 보고).
    auto_pages = {p.stem for p in WIKI_DIR.glob("*.md")
                  if p.name not in ("index.md", "log.md", "WIKI_SCHEMA.md")
                  and AUTO_MARK in read_text(p)}
    orphans = sorted(auto_pages - set(slugs.values()))

    manual_pages = sorted(p.stem for p in MANUAL_DIR.glob("*.md"))
    index_lines = ["# 위키 카탈로그 (자동 생성)", "",
                   f"갱신: {now()[:19]} · 페이지 {len(topic_rows)}개 · 원장 {len(rows)}건", "",
                   "| 주제 | 현행 | 누적 | 마지막 기록 |", "|---|---|---|---|"]
    for topic in sorted(topic_rows, key=lambda t: -len(topic_rows[t])):
        trows = topic_rows[topic]
        act = sum(1 for r in trows if r.get("status") == "active")
        last = max((str(r.get("created_at", ""))[:10] for r in trows), default="")
        index_lines.append(f"| [[{topic}]] | {act} | {len(trows)} | {last} |")
    if manual_pages:
        index_lines += ["", "## 수동 페이지 (사람 작성 — 자동 갱신 없음)", ""]
        index_lines += [f"- [[manual/{p}]]" for p in manual_pages]
    if orphans:
        index_lines += ["", f"*고아 자동 페이지 {len(orphans)}개 — lint 보고 참조*"]
    atomic_write_text(INDEX_FILE, "\n".join(index_lines) + "\n")

    if written:
        _log("consolidate", f"페이지 {len(written)}개 갱신: {', '.join(written[:8])}"
             + (" …" if len(written) > 8 else ""))
    return {"pages": len(topic_rows), "updated": written, "orphans": orphans,
            "records": len(rows)}


def lint() -> Dict[str, Any]:
    """위키 건강검진 — 중복/고아/정체를 찾아 보고 (자동 삭제 없음)."""
    ensure_schema()
    rows = _events()
    active = [r for r in rows if r.get("status") == "active"]

    seen: Dict[str, str] = {}
    duplicates: List[Dict[str, str]] = []
    for r in active:
        title = str(r.get("title", "")).strip().lower()
        if title and title in seen:
            duplicates.append({"title": title, "ids": f"{seen[title]},{r.get('id')}"})
        elif title:
            seen[title] = str(r.get("id", ""))

    topic_rows = _topic_map(rows)
    slugs = {_slug(t) for t in topic_rows}
    orphans = sorted(p.stem for p in WIKI_DIR.glob("*.md")
                     if p.name not in ("index.md", "log.md", "WIKI_SCHEMA.md")
                     and AUTO_MARK in read_text(p) and p.stem not in slugs)

    stale: List[str] = []
    today = now()[:10]
    for topic, trows in topic_rows.items():
        last = max((str(r.get("created_at", ""))[:10] for r in trows), default="")
        try:
            days = (datetime.fromisoformat(today) - datetime.fromisoformat(last)).days
        except ValueError:
            continue
        if days > 60:
            stale.append(f"{topic} ({days}일)")

    report = {"duplicates": duplicates, "orphan_pages": orphans, "stale_topics": stale,
              "checked_records": len(active), "checked_pages": len(topic_rows)}
    parts = []
    if duplicates:
        parts.append(f"중복 제목 {len(duplicates)}건")
    if orphans:
        parts.append(f"고아 페이지 {len(orphans)}개({', '.join(orphans[:5])})")
    if stale:
        parts.append(f"정체 주제 {len(stale)}개")
    _log("lint", "; ".join(parts) if parts else "이상 없음")
    return report


def recall_pages(keywords: List[str], limit: int = 2, max_chars: int = 1200) -> List[Dict[str, str]]:
    """프롬프트 키워드에 맞는 주제 페이지 발췌 — 증류된 지식을 recall 에 얹는다.

    원장 recall(개별 사건)보다 페이지(주제 전체 요약)가 복리 효과가 크다:
    기록이 쌓일수록 같은 주제 발췌가 더 풍부해진다.
    """
    if not WIKI_DIR.is_dir():
        return []
    keys = [k.lower() for k in keywords if k and len(str(k)) >= 2]
    if not keys:
        return []
    scored: List[Tuple[int, str, Path]] = []
    for p in WIKI_DIR.glob("*.md"):
        if p.name in ("index.md", "log.md", "WIKI_SCHEMA.md"):
            continue
        stem = p.stem.lower()
        score = sum(3 for k in keys if k in stem)
        if not score:
            head = read_text(p)[:800].lower()
            score = sum(1 for k in keys if k in head)
        if score:
            scored.append((score, stem, p))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out = []
    for _s, stem, p in scored[:limit]:
        text = read_text(p)
        text = text.split("---", 2)[-1].replace(AUTO_MARK, "").strip()  # frontmatter 제거
        if len(text) > max_chars:
            text = text[:max_chars] + "\n…(원문: wiki/" + p.name + ")"
        out.append({"topic": stem, "excerpt": text})
    return out


CURATE_PROMPT = (
    "다음은 사용자의 업무 지식 위키 '{topic}' 페이지 원문이다. 이 주제의 핵심을 "
    "3~6문장의 한국어 개요로 다듬어라. 규칙/교훈/실수의 요지를 보존하고, 새 사실을 "
    "지어내지 말고, 비밀값(키/주소)을 쓰지 마라. 개요 문장만 출력:\n\n{page}"
)


def curate(topics: Optional[List[str]] = None, llm=None) -> Dict[str, Any]:
    """(선택) LLM 으로 페이지 개요를 다듬는다 — 게이트웨이 없으면 조용히 건너뜀.

    llm: callable(prompt)->str 주입 가능(테스트). 기본은 lig_runtime 경유.
    큐레이션 결과는 curated.json 사이드카에 저장되고 consolidate 가 페이지에 심는다.
    품질 게이트: 비어있거나, 원문 제목을 하나도 언급 안 하면 폐기(스캐폴드 유지).
    """
    ensure_schema()
    rows = _events()
    topic_rows = _topic_map(rows)
    targets = [t for t in (topics or list(topic_rows))][:10]

    if llm is None:
        def llm(prompt: str) -> str:  # noqa: ANN001
            from .lig_runtime import chat_with_fallback
            return chat_with_fallback([{"role": "user", "content": prompt}])

    curated_all = _load_curated()
    done, skipped = [], []
    for topic in targets:
        trows = topic_rows.get(topic)
        if not trows:
            skipped.append({"topic": topic, "reason": "no such topic"})
            continue
        page = _page_markdown(topic, trows, [], None)
        try:
            summary = str(llm(CURATE_PROMPT.format(topic=topic, page=page[:6000]))).strip()
        except Exception as exc:  # noqa: BLE001 - 게이트웨이 부재는 정상 경로
            skipped.append({"topic": topic, "reason": f"llm_unavailable:{type(exc).__name__}"})
            continue
        titles = [str(r.get("title", "")) for r in trows if r.get("status") == "active"]
        anchored = any(t and (t[:20] in summary or topic in summary) for t in titles + [topic])
        if not summary or len(summary) < 20 or not anchored:
            skipped.append({"topic": topic, "reason": "quality_gate"})
            continue
        curated_all[topic] = {"summary": summary[:2000], "updated": now(),
                              "records": len(trows)}
        done.append(topic)
    if done:
        atomic_write_text(CURATED_FILE, json.dumps(curated_all, ensure_ascii=False, indent=2))
        consolidate()
        _log("curate", f"LLM 개요 갱신: {', '.join(done)}")
    return {"curated": done, "skipped": skipped}


def consolidate_quietly() -> None:
    """부수효과 훅(remember/브리핑/memorycheck)용 — 실패해도 본 작업을 막지 않는다."""
    try:
        consolidate()
    except Exception:  # noqa: BLE001 - 위키 갱신 실패가 기억 저장을 막으면 안 된다
        pass
