# -*- coding: utf-8 -*-
"""데이터 → 자립형 HTML 리포트 (오프라인).

CSV/분석결과를 브라우저에서 바로 보는 깔끔한 HTML 로 렌더링한다. 완전 오프라인:
외부 리소스 0 (인라인 CSS + 인라인 SVG 차트, JS 불필요). 회사 PC에서 파일을
더블클릭하면 열린다. 디자인 가이드(위계·절제·남색 본문·표 정렬)를 반영.

사용:
  render_report(title, subtitle, facts, notable, table) -> HTML 문자열
  build_from_csv(path) -> (headers, rows, chart)  # 표 + 첫 숫자열 막대차트
  write_report(out_dir, ...) -> Path
CLI:
  python -m agent_ops.html_report <data.csv> [out.html]
"""
from __future__ import annotations

import csv
import html
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from .encoding_ops import decode_file_bytes
except Exception:  # 단독 실행 폴백
    def decode_file_bytes(data: bytes) -> str:  # type: ignore
        for enc in ("utf-8-sig", "cp949"):
            try:
                return data.decode(enc)
            except Exception:
                pass
        return data.decode("utf-8", errors="replace")

MAX_TABLE_ROWS = 200
MAX_CHART_BARS = 24

_CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font-family:'Malgun Gothic','맑은 고딕',system-ui,sans-serif;
 color:#0d253d;background:#f6f7f9;line-height:1.6}
.wrap{max-width:960px;margin:0 auto;padding:32px 24px}
h1{font-size:28px;margin:0 0 4px;letter-spacing:-.5px}
.sub{color:#5b6b7b;font-size:14px;margin:0 0 24px}
h2{font-size:19px;margin:32px 0 12px;border-bottom:2px solid #e3e8ee;padding-bottom:6px}
ul{margin:0;padding-left:20px}
li{margin:3px 0}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}
th,td{border:1px solid #e3e8ee;padding:7px 10px;text-align:left;vertical-align:top}
th{background:#eef2f6;font-weight:700}
td.num{text-align:right;font-variant-numeric:tabular-nums;font-feature-settings:'tnum'}
tr.flag{background:#fff4f4}
.flag-badge{color:#dc2626;font-weight:700}
.chart{margin:12px 0}
.bar{fill:#2f6fb0}.bar-flag{fill:#dc2626}
.axis{stroke:#c9d3dd;stroke-width:1}
.blabel{font-size:11px;fill:#5b6b7b}
.foot{color:#8a97a4;font-size:12px;margin-top:32px}
@media(prefers-color-scheme:dark){
 body{color:#e6edf3;background:#0d1117}.sub,.blabel{color:#9aa7b3}
 h2{border-color:#22303c}th{background:#161d26}th,td{border-color:#22303c}
 tr.flag{background:#2a1416}}
"""


def _svg_bar_chart(labels: Sequence[str], values: Sequence[float],
                   flags: Optional[Sequence[bool]] = None) -> str:
    """순수 인라인 SVG 막대차트(JS/외부 의존 없음)."""
    labels = list(labels)[:MAX_CHART_BARS]
    values = [float(v) for v in values][:MAX_CHART_BARS]
    if not values:
        return ""
    flags = list(flags or [])[:MAX_CHART_BARS]
    vmax = max(values) or 1.0
    n = len(values)
    bw, gap, top, bottom, left = 34, 10, 16, 46, 8
    h, w = 180, left * 2 + n * (bw + gap)
    plot_h = h - top - bottom
    bars = []
    for i, v in enumerate(values):
        bh = (v / vmax) * plot_h
        x = left + i * (bw + gap)
        y = top + (plot_h - bh)
        cls = "bar-flag" if (i < len(flags) and flags[i]) else "bar"
        lab = html.escape(str(labels[i])[:10]) if i < len(labels) else ""
        bars.append(
            f'<rect class="{cls}" x="{x:.0f}" y="{y:.1f}" width="{bw}" height="{bh:.1f}" rx="2"/>'
            f'<text class="blabel" x="{x + bw/2:.0f}" y="{top+plot_h+12:.0f}" text-anchor="middle">{lab}</text>'
            f'<text class="blabel" x="{x + bw/2:.0f}" y="{y-3:.0f}" text-anchor="middle">{_fmt_num(v)}</text>'
        )
    axis = f'<line class="axis" x1="{left}" y1="{top+plot_h:.0f}" x2="{w-left}" y2="{top+plot_h:.0f}"/>'
    return (f'<div class="chart"><svg viewBox="0 0 {w} {h}" width="100%" '
            f'style="max-width:{w}px" role="img">{axis}{"".join(bars)}</svg></div>')


# 직접 그린 범용 상태 아이콘(인라인 SVG, 상표/외부의존 없음).
_ICON_WARN = ("<svg viewBox='0 0 16 16' width='13' height='13' aria-hidden='true' "
              "style='vertical-align:-1px'><path d='M8 1 L15 14 H1 Z' fill='none' "
              "stroke='#dc2626' stroke-width='1.5' stroke-linejoin='round'/>"
              "<rect x='7.2' y='6' width='1.6' height='4' fill='#dc2626'/>"
              "<rect x='7.2' y='11' width='1.6' height='1.6' fill='#dc2626'/></svg>")
_ICON_OK = ("<svg viewBox='0 0 16 16' width='13' height='13' aria-hidden='true' "
            "style='vertical-align:-1px'><path d='M3 8.5 L6.5 12 L13 4' fill='none' "
            "stroke='#2f9e44' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/></svg>")


def _fmt_num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _is_number(s: str) -> bool:
    try:
        float(str(s).replace(",", "").strip())
        return True
    except Exception:
        return False


def _num(s: str) -> float:
    return float(str(s).replace(",", "").strip())


def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]],
                 flag_rows: Optional[Sequence[bool]] = None) -> str:
    if not headers and not rows:
        return ""
    numeric_col = [all(_is_number(r[c]) for r in rows if c < len(r) and str(r[c]).strip())
                   for c in range(len(headers))] if headers else []
    thead = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = []
    flags = list(flag_rows or [])
    for i, r in enumerate(rows[:MAX_TABLE_ROWS]):
        cells = []
        for c, cell in enumerate(r):
            num = c < len(numeric_col) and numeric_col[c]
            cells.append(f'<td class="{"num" if num else ""}">{html.escape(str(cell))}</td>')
        cls = ' class="flag"' if i < len(flags) and flags[i] else ""
        body.append(f"<tr{cls}>{''.join(cells)}</tr>")
    more = (f'<p class="sub">… {len(rows) - MAX_TABLE_ROWS}행 더 (상위 {MAX_TABLE_ROWS}행만 표시)</p>'
            if len(rows) > MAX_TABLE_ROWS else "")
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(body)}</tbody></table>{more}"


def render_report(title: str, subtitle: str = "", facts: Optional[Sequence[str]] = None,
                  notable: Optional[Sequence[str]] = None, table_html: str = "",
                  chart_html: str = "") -> str:
    parts = [f"<div class='wrap'><h1>{html.escape(title)}</h1>"]
    if subtitle:
        parts.append(f"<p class='sub'>{html.escape(subtitle)}</p>")
    if facts:
        parts.append("<h2>요약</h2><ul>"
                     + "".join(f"<li>{html.escape(str(f))}</li>" for f in facts) + "</ul>")
    if notable:
        parts.append(f"<h2>{_ICON_WARN} <span class='flag-badge'>주의/이상 항목</span></h2><ul>"
                     + "".join(f"<li class='flag-badge'>{_ICON_WARN} {html.escape(str(n))}</li>" for n in notable)
                     + "</ul>")
    if chart_html:
        parts.append("<h2>차트</h2>" + chart_html)
    if table_html:
        parts.append("<h2>데이터</h2>" + table_html)
    parts.append("<p class='foot'>OpenCodeLIG 자립형 리포트 — 오프라인(외부 리소스 없음). "
                 "브라우저에서 열림.</p></div>")
    return (f"<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{_CSS}</style></head>"
            f"<body>{''.join(parts)}</body></html>")


def build_from_csv(path: Path, delimiter: str = ",") -> Tuple[List[str], List[List[str]], str]:
    """CSV → (headers, rows, chart_html). 첫 숫자열로 막대차트, 첫 텍스트열을 라벨로."""
    raw = Path(path).read_bytes()
    text = decode_file_bytes(raw)
    reader = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter)
              if any(str(c).strip() for c in r)]
    if not reader:
        return [], [], ""
    headers, rows = reader[0], reader[1:]
    # 첫 숫자열 찾기
    num_col = None
    for c in range(len(headers)):
        vals = [r[c] for r in rows if c < len(r) and str(r[c]).strip()]
        if vals and all(_is_number(v) for v in vals):
            num_col = c
            break
    chart = ""
    if num_col is not None and rows:
        label_col = 0 if num_col != 0 else (1 if len(headers) > 1 else 0)
        labels = [r[label_col] if label_col < len(r) else str(i)
                  for i, r in enumerate(rows)]
        values = [_num(r[num_col]) if num_col < len(r) and _is_number(r[num_col]) else 0.0
                  for r in rows]
        chart = _svg_bar_chart(labels, values)
    return headers, rows, chart


def write_report(out_dir: Path, title: str, html_text: str, filename: str = "리포트.html") -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(html_text, encoding="utf-8")
    return path


def report_from_csv(path: Path, out_dir: Path, title: Optional[str] = None) -> Path:
    p = Path(path)
    headers, rows, chart = build_from_csv(p)
    facts = [f"{p.name}: {len(rows)}행 × {len(headers)}열"]
    table = render_table(headers, rows)
    html_text = render_report(title or f"{p.stem} 데이터 리포트",
                              subtitle=str(p), facts=facts, table_html=table, chart_html=chart)
    return write_report(out_dir, title or p.stem, html_text)


def main(argv: Optional[List[str]] = None) -> int:
    import sys
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("사용: python -m agent_ops.html_report <data.csv> [out_dir]")
        return 2
    src = Path(argv[0])
    out_dir = Path(argv[1]) if len(argv) > 1 else src.parent
    path = report_from_csv(src, out_dir)
    print(f"HTML 리포트 생성: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
