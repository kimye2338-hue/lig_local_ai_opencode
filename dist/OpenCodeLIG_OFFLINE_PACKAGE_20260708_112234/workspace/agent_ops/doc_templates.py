# -*- coding: utf-8 -*-
"""사내 정형 문서 템플릿 — 시험성적서·품질보고서·주간보고·회의록.

반복되는 회사 문서의 **표준 구조**를 미리 정의해, 데이터만 넣으면 일관된 형식으로
.docx(또는 HTML)를 만든다. 잘못된 자유형 대신 늘 같은 골격 → 결재·검토가 빨라진다.
office_writer(Office 없이 진짜 파일)와 html_report(자립형 HTML)를 재사용.

CLI: python -m agent_ops.doc_templates <종류> [--input data.csv] [--out 파일] [--html]
종류: 시험성적서 | 품질보고서 | 주간보고 | 회의록
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .encoding_ops import decode_file_bytes
except Exception:  # 폴백
    def decode_file_bytes(data: bytes) -> str:  # type: ignore
        for enc in ("utf-8-sig", "cp949"):
            try:
                return data.decode(enc)
            except Exception:
                pass
        return data.decode("utf-8", errors="replace")

TEMPLATES = ("시험성적서", "품질보고서", "주간보고", "회의록")


def _today() -> str:
    # Date.now 계열이 막힌 환경 대비: 파일 스탬프는 호출부에서, 여기선 빈 값 허용
    try:
        return datetime.now().strftime("%Y-%m-%d")
    except Exception:
        return ""


def _read_table(path: Optional[str]) -> Tuple[List[str], List[List[str]]]:
    if not path:
        return [], []
    p = Path(path)
    if not p.exists():
        return [], []
    text = decode_file_bytes(p.read_bytes())
    rows = [r for r in csv.reader(io.StringIO(text)) if any(str(c).strip() for c in r)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _flag_rows(headers: List[str], rows: List[List[str]]) -> List[bool]:
    markers = ("불합격", "불량", "이상", "초과", "미달", "fail", "ng")
    return [any(m in " ".join(str(c) for c in r).lower() for m in markers) for r in rows]


def build_sections(kind: str, title: str, headers: List[str], rows: List[List[str]],
                   note: str = "") -> List[Dict[str, Any]]:
    """docx용 sections 구조를 만든다. 종류별 표준 골격."""
    d = _today()
    table = {"headers": headers, "rows": rows} if headers else None
    flagged = sum(_flag_rows(headers, rows)) if rows else 0
    if kind == "시험성적서":
        return [
            {"heading": "1. 시험 정보", "bullets": [f"작성일: {d}", "품명/모델: (기입)",
                                                  "시험 담당: (기입)", "시험 기준/규격: (기입)"]},
            {"heading": "2. 시험 조건", "paragraphs": ["시험 환경·장비·조건을 기입."]},
            {"heading": "3. 시험 결과", "paragraphs":
                [f"측정 {len(rows)}건 중 판정 주의 {flagged}건." if rows else "결과 데이터를 기입."],
             "table": table},
            {"heading": "4. 판정", "bullets": [
                ("일부 항목 기준 미달 — 재시험/조치 필요." if flagged else "전 항목 기준 이내(적합)."),
                "판정: (합격/불합격) — 담당 확인"]},
            {"heading": "5. 특이사항", "paragraphs": [note or "(없음)"]},
        ]
    if kind == "품질보고서":
        return [
            {"heading": "1. 개요", "bullets": [f"작성일: {d}", "대상/공정: (기입)", "기간: (기입)"]},
            {"heading": "2. 현황/데이터", "paragraphs":
                [f"수집 {len(rows)}건, 이상 {flagged}건." if rows else "현황 데이터를 기입."],
             "table": table},
            {"heading": "3. 이상 항목", "bullets":
                [f"주의/이상으로 감지된 {flagged}건 우선 확인." if flagged else "감지된 이상 없음."]},
            {"heading": "4. 원인 분석", "paragraphs": ["이상 항목의 원인을 분석해 기입."]},
            {"heading": "5. 조치/재발방지", "paragraphs": ["조치 사항과 재발방지 대책."]},
            {"heading": "6. 결론", "paragraphs": [note or "종합 판단과 권고를 한 단락으로."]},
        ]
    if kind == "주간보고":
        return [
            {"heading": "금주 실적", "bullets": [r[0] if r else "" for r in rows[:8]]
                or ["(항목 기입)"]},
            {"heading": "차주 계획", "bullets": ["(계획 기입)"]},
            {"heading": "이슈/리스크", "bullets": [note] if note else ["(없음)"]},
        ]
    # 회의록
    return [
        {"heading": "회의 정보", "bullets": [f"일시: {d}", "참석: (기입)", "안건: (기입)"]},
        {"heading": "결정 사항", "bullets": [r[0] if r else "" for r in rows[:10]] or ["(기입)"]},
        {"heading": "액션 아이템", "table": {"headers": ["할 일", "담당", "기한"],
                                          "rows": [[r[0] if r else "", "", ""] for r in rows[:10]]
                                                  or [["(기입)", "", ""]]}},
        {"heading": "이월/미결", "paragraphs": [note or "(없음)"]},
    ]


def generate(kind: str, out_dir: Path, input_csv: Optional[str] = None,
             title: Optional[str] = None, as_html: bool = False,
             note: str = "") -> Dict[str, Any]:
    if kind not in TEMPLATES:
        return {"ok": False, "error": f"알 수 없는 종류: {kind}", "templates": list(TEMPLATES)}
    title = title or kind
    headers, rows = _read_table(input_csv)
    sections = build_sections(kind, title, headers, rows, note=note)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if as_html:
        from .html_report import render_report, render_table
        facts = [f"{sec['heading']}" for sec in sections if sec.get("heading")]
        body_table = render_table(headers, rows, _flag_rows(headers, rows)) if headers else ""
        # 섹션을 간단 목록으로 + 데이터 표
        notable = []
        parts_facts = []
        for sec in sections:
            parts_facts.append(sec.get("heading", ""))
            for b in sec.get("bullets", []) or []:
                parts_facts.append("· " + str(b))
            for p in sec.get("paragraphs", []) or []:
                parts_facts.append("  " + str(p))
        html = render_report(title, subtitle=f"{kind} (템플릿)", facts=parts_facts,
                             notable=notable, table_html=body_table)
        path = out_dir / f"{title}.html"
        path.write_text(html, encoding="utf-8")
        return {"ok": True, "path": str(path), "format": "html", "kind": kind}
    from .office_writer import write_docx
    res = write_docx(out_dir / f"{title}.docx", title, sections)
    res["kind"] = kind
    return res


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="사내 정형 문서 템플릿")
    parser.add_argument("kind", choices=list(TEMPLATES))
    parser.add_argument("--input", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--html", action="store_true")
    args = parser.parse_args(argv)
    out_dir = Path(args.out) if args.out else Path("agent_ops/results/reports")
    res = generate(args.kind, out_dir, input_csv=(args.input or None),
                   title=(args.title or None), as_html=args.html, note=args.note)
    if not res.get("ok"):
        print(f"[template] 실패: {res.get('error')}" + (f"\n  {res.get('hint','')}" if res.get("hint") else ""))
        return 1
    print(f"{res.get('kind')} 생성({res.get('format')}): {res['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
