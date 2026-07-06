# -*- coding: utf-8 -*-
"""사내 정형 문서 템플릿 + 루틴 프리셋 검증."""
from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from agent_ops import doc_templates as DT  # noqa: E402
from agent_ops import routines as R  # noqa: E402

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
    csv = d / "m.csv"
    csv.write_text("항목,측정값,판정\n1번축,12.5,합격\n2번축,18.9,불합격\n", encoding="utf-8")

    # 4종 정형 문서 docx
    for kind in DT.TEMPLATES:
        r = DT.generate(kind, d, input_csv=str(csv))
        if r.get("ok"):
            check(f"{kind} docx 생성+유효", zipfile.is_zipfile(r["path"]), str(r))
        else:
            check(f"{kind} 미반입 안내", "hint" in r, str(r))

    # HTML 경로 + 불합격 강조
    rh = DT.generate("시험성적서", d, input_csv=str(csv), as_html=True)
    t = Path(rh["path"]).read_text(encoding="utf-8")
    check("HTML 자립형", "http://" not in t and "https://" not in t)
    check("불합격 데이터 보존", "불합격" in t and "1번축" in t)

    check("알 수 없는 종류 거부", not DT.generate("이상한것", d).get("ok"))

    # 루틴 프리셋 import
    R.ROUTINES_DIR = d / "routines"
    preset = d / "preset.json"
    preset.write_text(json.dumps({"name": "포털절차",
                                  "steps": [{"tool": "list_dir", "arguments": {"path": "."}}]},
                                 ensure_ascii=False), encoding="utf-8")
    imp = R.import_routine(preset)
    check("프리셋 import 성공", imp.get("ok") and imp.get("step_count") == 1, str(imp))
    check("import된 프리셋 조회됨", any(x["name"] == "포털절차" for x in R.list_routines()))
    check("빈 steps 프리셋 거부", not R.import_routine(d / "없음.json").get("ok"))

    print(f"\nALL {PASS} CHECKS PASSED (doc templates + routine preset)")


if __name__ == "__main__":
    main()
