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
  - lint 가 중복/고아/정체/모순후보를 찾아 log.md 에 남긴다 (자동 삭제·자동 해결 없음).

Obsidian 호환: 폴더(MEMORY/wiki)를 Obsidian vault 로 열면 [[링크]] 그래프가
그대로 보인다. 파일명은 주제 슬러그(한글 허용, 경로 위험문자만 치환).

## 커뮤니티 확장 기법 (2026-07-05 추가, 조사 근거 명시)

Karpathy 원안 이후 커뮤니티가 실제로 얹은 기법 중, 우리 제약(오프라인·
사람이 직접 손보는 개인 기억이라 자동 삭제/자동 해결은 절대 금지)에 맞는
것만 채택했다:

  - **모순 후보 탐지** (rohitg00 "LLM Wiki v2"; Karpathy 원안의 "flag for
    human review"): 같은 주제에서 부정어 유무가 갈리고 문구가 겹치는 쌍을
    lint 가 찾아 보고한다. **자동으로 어느 쪽이 맞는지 판단하지 않는다** —
    일부 재구현은 "출처 신뢰도로 자동 화해"까지 가지만, 개인 기억을 잘못
    지우면 되돌리기 어려워 우리는 사람 검토까지만 간다.
  - **별칭/동의어 확장** (green-dalii/obsidian-llm-wiki 의 "mandatory
    aliases"): 검색(recall) 시점에만 별칭을 확장한다 — 페이지 이름/그룹핑은
    바꾸지 않는다(사용자가 이미 아는 페이지 이름이 조용히 바뀌면 안 되므로).
  - **백링크** (같은 플러그인의 bidirectional link): `[[주제]]` 로 서로를
    언급한 다른 페이지(자동+manual/)를 텍스트 스캔으로 찾아 역방향으로도
    보여준다.
  - **강화 신호(확인 횟수)** (rohitg00 의 confidence scoring 비판 반영):
    소수점 가짜 정밀도 점수 대신, "같은 제목이 몇 번 반복 확인됐는가"를
    그대로 보여준다 — 세지 않은 척하지 않는다.
  - **의도적으로 채택하지 않은 것**: 시간 기반 망각/감쇠. rohitg00 의 리뷰가
    직접 경고한다 — "잊은 버그는 반복되는 버그다(bugs you forget are bugs
    you repeat)". 이 제품은 실수 노트/사용자 규칙을 절대 조용히 깎지 않는다
    (workspace-template/docs/MEMORY_AND_SELF_EXTENSION.md 의 보존 불변식).
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

ALIASES_FILE = WIKI_DIR / "aliases.json"

# 검색(recall) 시점 전용 별칭 시드 — 페이지 이름/그룹핑에는 쓰지 않는다
# (이미 만들어진 페이지 이름이 조용히 바뀌면 사용자가 혼란스럽다). 사용자가
# aliases.json 을 직접 편집해 늘릴 수 있고, 이미 있으면 절대 덮어쓰지 않는다.
ALIASES_SEED: Dict[str, List[str]] = {
    "excel": ["엑셀"],
    "outlook": ["아웃룩"],
    "hwp": ["한글", "한글파일"],
    "solidworks": ["솔리드웍스"],
    "autocad": ["오토캐드", "캐드"],
    "matlab": ["매트랩"],
    "ansys": ["앤시스"],
    "fluent": ["플루언트"],
    "browser": ["브라우저", "크롬", "chrome"],
    "macro": ["매크로", "vba"],
    "meeting": ["회의", "회의록"],
}

# 모순 후보 탐지용 부정어 — 정밀하지 않다(오탐 있을 수 있음). lint 는 보고만
# 하고 사람이 확인하므로, 놓치는 것보다 과하게 잡는 쪽이 안전하다.
NEGATION_MARKERS = (
    "하지 마", "하지마", "금지", "안 된다", "안된다", "불가", "하면 안",
    "쓰지 마", "쓰지마", "말 것", "말자", "마라", "없다",
    " not ", "n't", "never", "don't", "do not", "avoid",
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
- lint: 중복 제목/고아 페이지/오래 정체된 페이지/**모순 후보**를 찾아 log.md 에
  보고한다. 모순 후보는 **자동으로 어느 쪽이 맞는지 판단하지 않는다** —
  사람이 확인할 때까지 둘 다 남아 있는다.
- curate: (게이트웨이 있을 때만) 페이지 개요를 LLM 이 다듬는다 — 원장은 불변.
- 매일 아침 자동 브리핑을 켜두면(메뉴 9번) consolidate+lint 가 자동으로
  같이 돈다 — 사람이 매번 memorycheck 를 안 돌려도 위키가 스스로 정리된다.

## 에이전트에게
새 지식을 발견하면 remember 도구로 원장에 남겨라. 위키는 따라온다.
페이지와 모순되는 사실을 발견하면 그것도 remember 로 남겨라 — lint 가 잡는다.
"""


def _events() -> List[Dict[str, Any]]:
    from .memory_manager import MEMORY_JSONL, ensure_memory
    ensure_memory()
    return [r for r in read_jsonl(MEMORY_JSONL) if isinstance(r, dict)]


# Windows 예약 장치명 — 파일명으로 쓰면 os.replace가 OSError로 실패해
# consolidate 전체가 죽는다 ("con"/"aux" 같은 3자 토큰은 태그로 흔히 등장).
_WIN_RESERVED = ({"con", "prn", "aux", "nul"}
                 | {f"com{i}" for i in range(1, 10)}
                 | {f"lpt{i}" for i in range(1, 10)})


def _slug(topic: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|#\[\]\s]+", "_", str(topic).strip()).strip("._")
    s = (s or "topic")[:60]
    if s.lower() in _WIN_RESERVED:
        s += "_page"
    return s


def _slug_map(topics) -> Dict[str, str]:
    """topic→slug 매핑. 슬러그 충돌(예: 'a/b'와 'a:b' 모두 'a_b') 시 접미사로
    구분해 두 주제가 같은 파일을 번갈아 덮어쓰는 것을 막는다."""
    slugs: Dict[str, str] = {}
    used: set = set()
    for t in topics:
        base = _slug(t)
        s = base
        n = 2
        while s in used:
            s = f"{base}-{n}"
            n += 1
        used.add(s)
        slugs[t] = s
    return slugs


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


def ensure_aliases() -> Dict[str, List[str]]:
    """별칭 파일을 1회 시드하고 읽는다. 사용자가 늘려도 절대 덮어쓰지 않는다."""
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    if not ALIASES_FILE.exists():
        atomic_write_text(ALIASES_FILE, json.dumps(ALIASES_SEED, ensure_ascii=False, indent=2))
    try:
        data = json.loads(read_text(ALIASES_FILE) or "{}")
        return {str(k): [str(v) for v in vs] for k, vs in data.items()} if isinstance(data, dict) else {}
    except Exception:
        return dict(ALIASES_SEED)


def _expand_query_terms(keys: List[str]) -> List[str]:
    """recall 검색어에 별칭을 더한다 — 페이지 이름/그룹핑은 안 바꾸고 검색만 넓힌다."""
    aliases = ensure_aliases()
    reverse: Dict[str, str] = {}
    for canon, alts in aliases.items():
        reverse[canon.lower()] = canon.lower()
        for a in alts:
            reverse[a.lower()] = canon.lower()
    expanded = set(keys)
    for k in keys:
        canon = reverse.get(k)
        if not canon:
            continue
        expanded.add(canon)
        expanded.update(v.lower() for v in aliases.get(canon, []))
    return sorted(expanded)


def _detect_contradictions(topic_rows: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    """같은 주제·비슷한 문구인데 부정어 유무가 갈리는 쌍 = 모순 후보.

    출처: rohitg00 "LLM Wiki v2"(contradiction detection) + Karpathy 원안의
    "flag for human review". 어느 쪽이 맞는지 자동 판단하지 않는다 — 개인
    기억은 잘못 지우면 되돌리기 어려우므로 보고만 하고 사람이 확인한다.
    """
    from .memory_manager import extract_keywords
    found: List[Dict[str, str]] = []
    seen_pairs: set = set()
    for topic, rows in topic_rows.items():
        active = [r for r in rows if r.get("status") == "active"]
        if len(active) < 2 or len(active) > 60:  # 너무 크면 O(n^2) 방지, 스킵
            continue
        for i, a in enumerate(active):
            a_text = (str(a.get("title", "")) + " " + str(a.get("body", ""))).lower()
            # 태그도 키워드에 포함 — 같은 태그를 공유하는 건 이미 의미 있는
            # 겹침 신호다(짧은 한국어 문장은 본문만으로 40% 겹침을 못 채운다).
            a_keys = set(extract_keywords(a_text)) | set(_event_tags(a))
            a_neg = any(m in a_text for m in NEGATION_MARKERS)
            for b in active[i + 1:]:
                pair_key = tuple(sorted([str(a.get("id")), str(b.get("id"))]))
                if pair_key in seen_pairs or a.get("id") == b.get("id"):
                    continue
                b_text = (str(b.get("title", "")) + " " + str(b.get("body", ""))).lower()
                b_neg = any(m in b_text for m in NEGATION_MARKERS)
                if a_neg == b_neg:  # 둘 다 부정형이거나 둘 다 아니면 모순 신호 아님
                    continue
                b_keys = set(extract_keywords(b_text)) | set(_event_tags(b))
                if not a_keys or not b_keys:
                    continue
                overlap = len(a_keys & b_keys) / max(1, len(a_keys | b_keys))
                if overlap >= 0.3:
                    seen_pairs.add(pair_key)
                    found.append({"topic": topic, "a_id": str(a.get("id")), "a_title": str(a.get("title")),
                                 "b_id": str(b.get("id")), "b_title": str(b.get("title"))})
        if len(found) >= 20:
            break
    return found


def _backlinks_for(all_bodies: Dict[str, str], manual_texts: Dict[str, str]) -> Dict[str, List[str]]:
    """`[[주제]]` 텍스트 스캔으로 역방향 링크(백링크)를 만든다.

    출처: obsidian-llm-wiki 플러그인의 bidirectional link. 우리 forward
    링크(_related)는 원장 co-occurrence 기반이라, 텍스트에 실제 적힌
    `[[..]]` 언급을 다시 스캔하면 manual/ 이 자동 페이지를 언급하는 것까지
    잡을 수 있어 상호보완적이다.
    """
    link_re = re.compile(r"\[\[([^\]|]+)\]\]")
    backlinks: Dict[str, List[str]] = {}
    sources = [("", name, text) for name, text in all_bodies.items()]
    sources += [("manual/", name, text) for name, text in manual_texts.items()]
    for prefix, name, text in sources:
        label = prefix + name
        for m in link_re.finditer(text):
            target = m.group(1).strip()
            if not target or target == name:
                continue
            backlinks.setdefault(target, [])
            if label not in backlinks[target]:
                backlinks[target].append(label)
    return backlinks


def _load_curated() -> Dict[str, Any]:
    try:
        data = json.loads(read_text(CURATED_FILE) or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _reinforcement_note(active: List[Dict[str, Any]]) -> str:
    """"확인 횟수" — 소수점 가짜 정밀도 대신 실제 반복 횟수를 그대로 보여준다.

    같은 제목이 여러 번 기록됐다 = 그 규칙/교훈이 여러 사건에서 재확인됐다는
    뜻(rohitg00 confidence-scoring 아이디어의 정직한 버전). lint 의 "중복
    제목" 경고와 같은 신호를 다루지만 여기서는 긍정적 신호로 보여준다.
    """
    counts = Counter(str(r.get("title", "")).strip() for r in active if r.get("title"))
    reinforced = sorted(((t, c) for t, c in counts.items() if c >= 2), key=lambda x: -x[1])
    if not reinforced:
        return ""
    top = reinforced[0]
    extra = f" (예: \"{top[0][:30]}\" {top[1]}회 확인)" if top[1] >= 2 else ""
    return f"반복 확인된 규칙/교훈: {len(reinforced)}건{extra}"


def _page_markdown(topic: str, rows: List[Dict[str, Any]],
                   related: List[str], curated: Optional[Dict[str, Any]],
                   backlinks: Optional[List[str]] = None) -> str:
    active = [r for r in rows if r.get("status") == "active"]
    rows_sorted = sorted(rows, key=lambda r: str(r.get("created_at", "")), reverse=True)
    kinds = Counter(str(r.get("kind", "")) for r in active)
    updated = str(rows_sorted[0].get("created_at", ""))[:10] if rows_sorted else ""
    recency = ""
    try:
        days = (datetime.fromisoformat(now()[:10]) - datetime.fromisoformat(updated)).days
        if days == 0:
            recency = "오늘 갱신"
        elif days > 0:
            recency = f"{days}일 전 갱신"
    except ValueError:
        pass

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
    meta_bits = [b for b in (recency, _reinforcement_note(active)) if b]
    if meta_bits:
        lines.append("*" + " · ".join(meta_bits) + "*")
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
    if backlinks:
        lines.append("## 언급된 곳 (백링크)")
        lines.append(" · ".join(f"[[{b}]]" for b in backlinks))
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
    slugs: Dict[str, str] = _slug_map(topic_rows)

    # 1차: 백링크 없이 본문을 만들어 텍스트 스캔 재료로 쓴다 (백링크는
    # 다른 페이지가 이 주제를 [[언급]]했는지 알아야 하므로 전체가 먼저 필요).
    draft_bodies = {topic: _page_markdown(topic, trows, _related(topic, topic_rows),
                                          curated_all.get(topic))
                    for topic, trows in topic_rows.items()}
    manual_texts = {p.stem: read_text(p) for p in MANUAL_DIR.glob("*.md")}
    backlink_map = _backlinks_for(draft_bodies, manual_texts)

    written: List[str] = []
    for topic, trows in topic_rows.items():
        # 페이지 단위 실패 격리 — 한 페이지의 쓰기 실패(경로 문제 등)가
        # 나머지 전체 위키 갱신을 중단시키지 않게 한다.
        try:
            page = _page_markdown(topic, trows, _related(topic, topic_rows),
                                  curated_all.get(topic), backlinks=backlink_map.get(topic))
            path = WIKI_DIR / f"{slugs[topic]}.md"
            if read_text(path) != page:
                atomic_write_text(path, page)
                written.append(topic)
        except Exception as exc:  # noqa: BLE001
            _log("error", f"페이지 쓰기 실패: {topic} — {exc!r}"[:200])

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
    # Obsidian 자연 연동: 위키에 내용이 생기는 순간 vault 설정(.obsidian)을 1회
    # 자동 시드한다 — 사용자가 wiki.bat 등 아무것도 안 눌러도 폴더를 Obsidian으로
    # 열면 바로 그래프/백링크/대시보드가 준비돼 있다. 이미 있으면 건드리지 않는다.
    try:
        if not (WIKI_DIR / ".obsidian").exists():
            from .wiki_vault import seed_obsidian_vault
            seed_obsidian_vault(WIKI_DIR)
    except Exception:  # noqa: BLE001 - vault 시드 실패가 위키 통합을 막지 않게
        pass
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
    slugs = set(_slug_map(topic_rows).values())
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

    contradictions = _detect_contradictions(topic_rows)

    report = {"duplicates": duplicates, "orphan_pages": orphans, "stale_topics": stale,
              "contradictions": contradictions,
              "checked_records": len(active), "checked_pages": len(topic_rows)}
    parts = []
    if duplicates:
        parts.append(f"중복 제목 {len(duplicates)}건")
    if orphans:
        parts.append(f"고아 페이지 {len(orphans)}개({', '.join(orphans[:5])})")
    if stale:
        parts.append(f"정체 주제 {len(stale)}개")
    if contradictions:
        parts.append(f"모순 후보 {len(contradictions)}건 — 사람 확인 필요")
    # '이상 없음'은 기록하지 않는다 — 매 빌드마다 append하면 log.md가 상한 없이 자란다.
    if parts:
        _log("lint", "; ".join(parts))
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
    # 별칭 확장: "엑셀"로 물어도 "excel" 페이지를 찾는다 (green-dalii
    # obsidian-llm-wiki 의 alias 기법 — 페이지 이름은 그대로, 검색만 넓힌다).
    keys = _expand_query_terms(keys)
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
