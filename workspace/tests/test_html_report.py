# -*- coding: utf-8 -*-
"""자립형 HTML 리포트 생성 검증 (오프라인·외부리소스 0)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from agent_ops import html_report as hr  # noqa: E402

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
    csv = d / "진동.csv"
    csv.write_text("항목,측정값,판정\n1번축,12.5,합격\n2번축,18.9,불합격\n3번축,9.2,합격\n",
                   encoding="utf-8")

    p = hr.report_from_csv(csv, d, title="진동시험 결과")
    t = p.read_text(encoding="utf-8")
    check("리포트 파일 생성", p.exists() and p.suffix == ".html")
    check("DOCTYPE로 시작", t.startswith("<!DOCTYPE"))
    check("표 포함", "<table" in t and "측정값" in t)
    check("SVG 막대차트 포함", "<svg" in t and "<rect" in t)
    check("한글 데이터 보존", "불합격" in t and "1번축" in t)
    check("외부 리소스 없음(자립형)", "http://" not in t and "https://" not in t
          and "cdn" not in t.lower() and "<script src" not in t)
    check("인라인 CSS", "<style>" in t)

    # CP949 CSV 도 읽힘(한국 Windows)
    csv2 = d / "cp949.csv"
    csv2.write_bytes("이름,값\n가나다,10\n라마바,20\n".encode("cp949"))
    p2 = hr.report_from_csv(csv2, d)
    t2 = p2.read_text(encoding="utf-8")
    check("CP949 CSV 디코드", "가나다" in t2 and "라마바" in t2)

    # 직접 렌더(모델이 계산한 표)
    table = hr.render_table(["부서", "매출"], [["영업", "120"], ["개발", "80"]])
    html = hr.render_report("실적", facts=["2개 부서"], notable=["개발 목표 미달"], table_html=table)
    check("직접 렌더 표/이상항목", "영업" in html and "개발 목표 미달" in html)
    check("숫자열 우측정렬 클래스", 'class="num"' in table)

    # 빈 입력 안전
    check("빈 차트 안전", hr._svg_bar_chart([], []) == "")

    print(f"\nALL {PASS} CHECKS PASSED (html report)")


if __name__ == "__main__":
    main()
