# -*- coding: utf-8 -*-
"""활동 타임라인 HTML 검증 — 멈춤 의심 구간 강조(무한대기 감시 시각화)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from agent_ops import activity_timeline as at  # noqa: E402

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
    d = Path(tempfile.mkdtemp())
    audit = d / "audit.jsonl"
    events = [
        {"ts": "2026-07-06T09:00:00", "kind": "adapter", "name": "excel_com.run", "target": "a.xlsx"},
        {"ts": "2026-07-06T09:00:20", "kind": "tool", "name": "write_file", "target": "보고서.md"},
        {"ts": "2026-07-06T09:40:00", "kind": "adapter", "name": "solidworks.run",
         "target": "b.sldprt", "verdict": "error", "ok": False},
    ]
    audit.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events), encoding="utf-8")

    loaded = at.load_events(audit)
    check("audit.jsonl 로드", len(loaded) == 3)

    h = at.render_timeline_html(loaded, stall_gap=600)
    check("DOCTYPE 자립형 HTML", h.startswith("<!DOCTYPE") and "<style>" in h)
    check("멈춤 의심 구간 감지(40분>10분)", "동안 활동 없음" in h and "class='gap'" in h)
    check("실패 이벤트 강조", "class='bad'" in h or 'class="bad"' in h)
    check("한글 대상 보존", "보고서.md" in h and "b.sldprt" in h)
    check("외부 리소스 없음", "http://" not in h and "https://" not in h and "cdn" not in h.lower())

    # 간격이 작으면 멈춤 표시 없음
    close = [{"ts": "2026-07-06T09:00:00", "kind": "tool", "name": "a"},
             {"ts": "2026-07-06T09:00:10", "kind": "tool", "name": "b"}]
    check("정상 간격은 멈춤 표시 없음", "동안 활동 없음" not in at.render_timeline_html(close, stall_gap=600))

    # 빈 데이터 안전
    check("빈 audit 안전", "활동이 없습니다" in at.render_timeline_html([]))

    p = at.build_timeline(d, stall_gap=600, audit_path=audit)
    check("파일 생성", p.exists() and p.suffix == ".html")

    print(f"\nALL {PASS} CHECKS PASSED (activity timeline)")


if __name__ == "__main__":
    main()
