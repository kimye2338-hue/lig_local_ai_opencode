# -*- coding: utf-8 -*-
"""지식책(Knowledge Book) — 전역 기억을 사람이 읽는 히스토리북 HTML로 엮는다.

설계 (복리 구조의 3층):
  1층 원장   memory.jsonl  — append-only. cap이 넘쳐도 삭제가 아니라 '보관'(deprecated).
                             절대 휘발되지 않는다.
  2층 증류   WIKI.md       — 사람/비서가 함께 다듬는 현행 규칙집.
  3층 열람   knowledge_book.html — 이 모듈이 '생성'하는 읽기 전용 책.
                             타임라인(언제 뭘 배웠나) + 카테고리 + 주간 복습 회전
                             + 검색 + 활동 기록. 언제든 재생성 가능(항상 최신).

자동 갱신: remember/브리핑/설치 때마다 조용히 재생성된다. 수동: `agentops.py book`.
오프라인 전제: 외부 리소스 0 (인라인 CSS/JS만). 파일명은 ASCII(knowledge_book.html) —
바탕화면 바로가기(.bat) 내용이 cp949로 파싱되어도 안전하도록.
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from . import audit
from .core import MEMORY, atomic_write_text, read_jsonl
from .memory_manager import MEMORY_JSONL, ensure_memory

BOOK_DIR = MEMORY / "book"
BOOK_FILE = BOOK_DIR / "knowledge_book.html"
WIKI_FILE = MEMORY / "WIKI.md"

KIND_LABEL = {
    "preference": ("내 규칙·선호", "#2563eb"),
    "lesson": ("배운 것", "#059669"),
    "error_pattern": ("실수 노트", "#dc2626"),
}


def _now(now: datetime | None) -> datetime:
    raw = os.environ.get("BRIEFING_NOW", "")
    if now is not None:
        return now
    if raw:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
    return datetime.now()


def _load_entries() -> List[Dict[str, Any]]:
    ensure_memory()
    rows = [r for r in read_jsonl(MEMORY_JSONL) if isinstance(r, dict)]
    return sorted(rows, key=lambda r: str(r.get("created_at", "")), reverse=True)


def _parse_dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)[:19])
    except (TypeError, ValueError):
        return None


def review_picks(entries: List[Dict[str, Any]], now: datetime, limit: int = 5) -> List[Dict[str, Any]]:
    """이번 주의 복습 — 결정적(주차 기반) 회전으로 오래된 활성 지식을 다시 띄운다.

    '알았는데 기억 안 나던 것'을 다시 만나게 하는 장치. 같은 주에는 같은 목록이
    나오고(테스트 가능), 주가 바뀌면 다른 항목으로 회전한다.
    """
    due = []
    for r in entries:
        if r.get("status") != "active":
            continue
        created = _parse_dt(r.get("created_at"))
        days = int(r.get("review_after_days") or 14)
        if created and (now - created) >= timedelta(days=days):
            due.append(r)
    if not due:
        return []
    due.sort(key=lambda r: str(r.get("id", "")))          # 안정적 순서
    week = int(now.strftime("%G%V"))                       # ISO 연+주차
    start = week % len(due)
    rotated = due[start:] + due[:start]
    return rotated[:limit]


def _audit_activity(now: datetime, days: int = 30) -> List[Dict[str, Any]]:
    """최근 활동(일자별 작업 수 + 대표 작업명) — '내가 뭘 했더라'의 근거."""
    path = Path(os.environ.get("LIG_AUDIT_DIR") or audit.AUDIT_DIR) / audit.AUDIT_FILE
    if not path.exists():
        return []
    since = now - timedelta(days=days)
    by_day: Dict[str, Dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        ts = _parse_dt(row.get("ts"))
        if not ts or ts < since or row.get("kind") != "work":
            continue
        day = ts.strftime("%Y-%m-%d")
        slot = by_day.setdefault(day, {"day": day, "count": 0, "tasks": []})
        slot["count"] += 1
        task = str(row.get("task", "")).strip()
        if task and task not in slot["tasks"]:
            slot["tasks"].append(task)
    return sorted(by_day.values(), key=lambda s: s["day"], reverse=True)


def _md_to_html(md: str) -> str:
    """WIKI.md 렌더용 초소형 마크다운 변환(헤딩/리스트/코드/문단만, stdlib)."""
    out: List[str] = []
    in_list = False
    for raw in md.splitlines():
        line = raw.rstrip()
        esc = html.escape(line)
        if line.startswith("#"):
            if in_list:
                out.append("</ul>")
                in_list = False
            level = min(len(line) - len(line.lstrip("#")), 4)
            out.append(f"<h{level + 1}>{html.escape(line.lstrip('#').strip())}</h{level + 1}>")
        elif line.strip().startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(line.strip()[2:])}</li>")
        elif not line.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
        else:
            out.append(f"<p>{esc}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _entry_card(r: Dict[str, Any], faded: bool = False) -> str:
    kind = str(r.get("kind", ""))
    label, color = KIND_LABEL.get(kind, (kind or "기록", "#6b7280"))
    title = html.escape(str(r.get("title", ""))[:120])
    body = html.escape(str(r.get("body", ""))[:600])
    created = html.escape(str(r.get("created_at", ""))[:10])
    src = html.escape(str(r.get("source", "")))
    badge = ""
    if r.get("status") != "active":
        badge = '<span class="badge archived">보관됨</span>'
        faded = True
    cls = "card faded" if faded else "card"
    search = html.escape((title + " " + body + " " + label).lower(), quote=True)
    return (f'<div class="{cls}" data-search="{search}">'
            f'<div class="meta"><span class="badge" style="background:{color}">{label}</span>'
            f'{badge}<span class="date">{created}</span><span class="src">{src}</span></div>'
            f'<div class="title">{title}</div><div class="body">{body}</div></div>')


_CSS = """
:root{--bg:#f8fafc;--fg:#0f172a;--card:#ffffff;--muted:#64748b;--line:#e2e8f0;--accent:#2563eb}
@media(prefers-color-scheme:dark){:root{--bg:#0b1220;--fg:#e2e8f0;--card:#111a2e;--muted:#94a3b8;--line:#1e293b}}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--fg);font-family:'Malgun Gothic','Apple SD Gothic Neo',system-ui,sans-serif;line-height:1.6;padding:24px;max-width:900px;margin:0 auto}
h1{font-size:26px;margin:8px 0 2px}h2{font-size:19px;margin:34px 0 12px;border-bottom:2px solid var(--line);padding-bottom:6px}
h3,h4,h5{margin:14px 0 6px}
.sub{color:var(--muted);font-size:13px;margin-bottom:18px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 18px;min-width:120px}
.stat b{display:block;font-size:22px;color:var(--accent)}
.stat span{font-size:12px;color:var(--muted)}
#q{width:100%;padding:10px 14px;font-size:15px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--fg);margin:6px 0 4px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:8px 0}
.card.faded{opacity:.55}
.meta{display:flex;gap:8px;align-items:center;font-size:12px;color:var(--muted);margin-bottom:4px;flex-wrap:wrap}
.badge{color:#fff;border-radius:20px;padding:1px 9px;font-size:11px}
.badge.archived{background:#6b7280}
.title{font-weight:700}.body{font-size:14px;white-space:pre-wrap}
.month{color:var(--muted);font-size:13px;font-weight:700;margin:16px 0 4px;letter-spacing:.5px}
.review{border-left:4px solid var(--accent)}
.day{display:flex;gap:10px;font-size:14px;padding:4px 0;border-bottom:1px dashed var(--line)}
.day b{min-width:96px}
.wiki{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:6px 18px}
.wiki ul{padding-left:20px}
footer{color:var(--muted);font-size:12px;margin-top:40px;text-align:center}
"""

_JS = """
document.getElementById('q').addEventListener('input',function(){
  var q=this.value.trim().toLowerCase();
  document.querySelectorAll('.card[data-search]').forEach(function(c){
    c.style.display=(!q||c.getAttribute('data-search').indexOf(q)>=0)?'':'none';
  });
});
"""


def build_book(now: datetime | None = None) -> Path:
    """지식책 HTML 생성 — 언제든 호출 가능, 항상 전체를 다시 그린다."""
    current = _now(now)
    entries = _load_entries()
    active = [r for r in entries if r.get("status") == "active"]
    week_ago = current - timedelta(days=7)
    new_this_week = [r for r in entries
                     if (_parse_dt(r.get("created_at")) or current) >= week_ago]
    picks = review_picks(entries, current)
    activity = _audit_activity(current)
    wiki_html = _md_to_html(WIKI_FILE.read_text(encoding="utf-8")) if WIKI_FILE.exists() else ""

    parts: List[str] = []
    parts.append(f"<h1>지식책</h1><div class='sub'>내가 배운 것들의 기록 — "
                 f"{current.strftime('%Y-%m-%d %H:%M')} 기준 · 자동 생성(수정은 WIKI.md에서)</div>")
    parts.append("<div class='stats'>"
                 f"<div class='stat'><b>{len(active)}</b><span>현재 지식</span></div>"
                 f"<div class='stat'><b>+{len(new_this_week)}</b><span>이번 주 새로 배움</span></div>"
                 f"<div class='stat'><b>{len(entries)}</b><span>누적 기록(보관 포함)</span></div>"
                 f"<div class='stat'><b>{sum(a['count'] for a in activity)}</b><span>최근 30일 작업</span></div>"
                 "</div>")
    parts.append("<input id='q' type='search' placeholder='검색 — 제목/내용/분류'>")

    if picks:
        parts.append("<h2>🔁 이번 주의 복습 — 잊기 전에 다시 보기</h2>")
        for r in picks:
            parts.append(_entry_card(r).replace("class=\"card\"", "class=\"card review\""))

    by_kind: Dict[str, List[Dict[str, Any]]] = {}
    for r in active:
        by_kind.setdefault(str(r.get("kind", "기록")), []).append(r)
    for kind in ("preference", "lesson", "error_pattern"):
        rows = by_kind.pop(kind, [])
        if rows:
            parts.append(f"<h2>{KIND_LABEL[kind][0]} ({len(rows)})</h2>")
            parts.extend(_entry_card(r) for r in rows)
    other = [r for rows in by_kind.values() for r in rows]
    if other:
        parts.append(f"<h2>기타 기록 ({len(other)})</h2>")
        parts.extend(_entry_card(r) for r in other)

    if wiki_html:
        parts.append("<h2>📖 위키 (현행 규칙집 — 직접 편집 가능)</h2>")
        parts.append(f"<div class='wiki'>{wiki_html}</div>")

    parts.append("<h2>📜 전체 타임라인 — 나의 히스토리북</h2>")
    month = ""
    for r in entries:
        m = str(r.get("created_at", ""))[:7]
        if m != month:
            month = m
            parts.append(f"<div class='month'>{month or '날짜 미상'}</div>")
        parts.append(_entry_card(r, faded=r.get("status") != "active"))
    if not entries:
        parts.append("<p class='sub'>아직 기록이 없습니다 — 오픈코드 채팅에서 \"기억해: ...\" 라고 말해 보세요.</p>")

    if activity:
        parts.append("<h2>🗓 최근 활동 (30일)</h2>")
        for a in activity[:14]:
            tasks = html.escape(" · ".join(a["tasks"][:3]))
            parts.append(f"<div class='day'><b>{a['day']}</b><span>{a['count']}건 — {tasks}</span></div>")

    parts.append("<footer>OpenCodeLIG 지식책 · 원본: OpenCodeLIG_USERDATA\\memory\\ "
                 "(memory.jsonl 원장은 삭제되지 않습니다)</footer>")

    doc = ("<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>지식책</title><style>{_CSS}</style></head><body>"
           + "\n".join(parts) + f"<script>{_JS}</script></body></html>")
    BOOK_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(BOOK_FILE, doc)
    return BOOK_FILE


def rebuild_quietly() -> None:
    """부수효과 훅(remember/브리핑/설치)용 — 실패해도 본 작업을 막지 않는다."""
    try:
        build_book()
    except Exception:  # noqa: BLE001 - 책 생성 실패가 기억 저장을 막으면 안 된다
        pass
