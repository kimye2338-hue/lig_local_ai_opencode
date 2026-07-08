# -*- coding: utf-8 -*-
"""에이전트 활동 타임라인 → 자립형 HTML (오프라인).

우리가 이미 남기는 audit.jsonl(감사 로그)로 "무엇을 언제 했는지"를 세로 타임라인으로
보여준다. **이벤트 사이 간격이 크면 '멈춤 의심'으로 강조** — 서브에이전트/작업이 어디서
오래 멈췄는지 사용자가 눈으로 본다(무한대기 감시의 시각화). agentsview 같은 무거운
별도 스택(Go+Node+SQLite) 없이, 우리 데이터로 완전 오프라인 self-contained HTML 생성.

CLI: python -m agent_ops.activity_timeline [out_dir] [--gap 초]
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .core import MEMORY  # noqa: F401
    from .html_report import _CSS, _ICON_OK, _ICON_WARN, write_report
except Exception:  # 단독 폴백
    from agent_ops.html_report import _CSS, _ICON_OK, _ICON_WARN, write_report  # type: ignore

DEFAULT_STALL_GAP = 600  # 초. 이벤트 간격이 이보다 크면 멈춤 의심으로 표시.


def _diag_dir() -> Path:
    return Path(os.environ.get("LIG_DIAG_DIR")
                or (Path.home() / "OpenCodeLIG_USERDATA" / "diagnostics"))


def _audit_dir() -> Path:
    # audit.jsonl 은 agent_ops/logs 아래(command_guard/ audit 기록 위치)
    return Path(os.environ.get("LIG_AUDIT_DIR") or (Path.cwd() / "agent_ops" / "logs"))


def _parse_ts(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(s))
    except Exception:
        return None


def load_events(audit_path: Optional[Path] = None, limit: int = 300) -> List[Dict[str, Any]]:
    """audit.jsonl 을 시간순 이벤트 목록으로. 없으면 빈 목록."""
    path = audit_path or (_audit_dir() / "audit.jsonl")
    events: List[Dict[str, Any]] = []
    if not Path(path).exists():
        return events
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except Exception:
        return events
    for raw in lines:
        try:
            e = json.loads(raw)
        except Exception:
            continue
        events.append(e)
    return events


def _fmt_gap(seconds: float) -> str:
    if seconds >= 3600:
        return f"{seconds/3600:.1f}시간"
    if seconds >= 60:
        return f"{seconds/60:.0f}분"
    return f"{seconds:.0f}초"


def render_timeline_html(events: List[Dict[str, Any]], stall_gap: int = DEFAULT_STALL_GAP,
                         title: str = "에이전트 활동 타임라인") -> str:
    rows: List[str] = []
    prev_dt: Optional[datetime] = None
    stalls = 0
    for e in events:
        ts = str(e.get("ts") or e.get("timestamp") or "")
        dt = _parse_ts(ts)
        # 간격 큰 구간 = 멈춤 의심
        if prev_dt and dt:
            gap = (dt - prev_dt).total_seconds()
            if gap >= stall_gap:
                stalls += 1
                rows.append(
                    f"<li class='gap'>{_ICON_WARN} <b>{_fmt_gap(gap)}</b> 동안 활동 없음 "
                    f"— 멈춤 의심 구간</li>")
        prev_dt = dt or prev_dt
        ok = e.get("verdict") not in ("block", "deny", "error") and e.get("ok") is not False
        icon = _ICON_OK if ok else _ICON_WARN
        kind = html.escape(str(e.get("kind") or ""))
        name = html.escape(str(e.get("name") or ""))
        target = html.escape(str(e.get("target") or ""))
        verdict = html.escape(str(e.get("verdict") or ""))
        task = html.escape(str(e.get("task") or "")[:60])
        label = " · ".join(x for x in (kind, name, target) if x) or "(이벤트)"
        meta = " · ".join(x for x in (task, verdict) if x)
        rows.append(
            f"<li class='{'ok' if ok else 'bad'}'>{icon} "
            f"<span class='t'>{html.escape(ts[-8:] if len(ts) >= 8 else ts)}</span> "
            f"<span class='ev'>{label}</span>"
            + (f" <span class='meta'>{meta}</span>" if meta else "") + "</li>")

    if not rows:
        body = "<p class='sub'>기록된 활동이 없습니다 (audit.jsonl 없음 또는 비어 있음).</p>"
        summary = ""
    else:
        body = "<ul class='timeline'>" + "".join(rows) + "</ul>"
        summary = (f"<p class='sub'>이벤트 {len(events)}건"
                   + (f" · <span class='flag-badge'>멈춤 의심 {stalls}구간</span>" if stalls else "")
                   + f" · 멈춤 기준 {_fmt_gap(stall_gap)}</p>")

    extra_css = (".timeline{list-style:none;padding-left:0}"
                 ".timeline li{border-left:3px solid #e3e8ee;padding:4px 0 4px 12px;margin:0}"
                 ".timeline li.bad{border-color:#dc2626}"
                 ".timeline li.gap{border-color:#dc2626;color:#dc2626;background:#fff4f4;"
                 "padding:6px 12px;font-weight:600}"
                 ".timeline .t{color:#5b6b7b;font-variant-numeric:tabular-nums;margin-right:6px}"
                 ".timeline .ev{font-weight:600}"
                 ".timeline .meta{color:#5b6b7b;font-size:12px}")
    return (f"<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{_CSS}{extra_css}</style></head>"
            f"<body><div class='wrap'><h1>{html.escape(title)}</h1>{summary}{body}"
            f"<p class='foot'>OpenCodeLIG 활동 타임라인 — audit.jsonl 기반, 오프라인. "
            f"멈춤 의심 구간은 서브에이전트/작업이 오래 진행 없이 멈춘 지점입니다.</p>"
            f"</div></body></html>")


def build_timeline(out_dir: Path, stall_gap: int = DEFAULT_STALL_GAP,
                   audit_path: Optional[Path] = None) -> Path:
    events = load_events(audit_path)
    html_text = render_timeline_html(events, stall_gap=stall_gap)
    return write_report(out_dir, "활동 타임라인", html_text, filename="활동타임라인.html")


def main(argv: Optional[List[str]] = None) -> int:
    import sys
    argv = argv if argv is not None else sys.argv[1:]
    gap = DEFAULT_STALL_GAP
    positional = []
    i = 0
    while i < len(argv):
        if argv[i] == "--gap" and i + 1 < len(argv):
            try:
                gap = int(argv[i + 1])
            except Exception:
                pass
            i += 2
        else:
            positional.append(argv[i])
            i += 1
    out_dir = Path(positional[0]) if positional else (Path.cwd() / "agent_ops" / "results" / "reports")
    path = build_timeline(out_dir, stall_gap=gap)
    print(f"활동 타임라인 생성: {path}")
    print("브라우저로 열면 활동·멈춤 의심 구간이 보입니다 (오프라인).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
