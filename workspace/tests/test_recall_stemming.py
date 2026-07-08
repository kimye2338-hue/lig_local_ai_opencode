# -*- coding: utf-8 -*-
"""회귀: 한국어 조사 스테밍 recall + 별칭 확장 + recall --pinned (stdlib only, 네트워크 0).

기억은 AGENTOPS_MEMORY_DIR=tmp 로 격리 — 실제 USERDATA 를 절대 건드리지 않는다.

Run: py -3.11 tests\\test_recall_stemming.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# import 전에 지정해야 한다 — core.MEMORY 는 모듈 import 시점에 굳는다.
TMP_MEM = Path(tempfile.mkdtemp(prefix="agentops_mem_stem_"))
os.environ["AGENTOPS_MEMORY_DIR"] = str(TMP_MEM)

from agent_ops import memory_manager as mm  # noqa: E402

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
    check("기억 격리(tmp)", str(mm.MEMORY) == str(TMP_MEM), str(mm.MEMORY))

    # ① 조사 스테밍: '엑셀로'/'규칙을' 같은 토큰에서 어간이 함께 추출된다.
    kws = mm.extract_keywords("엑셀로 매크로 규칙을 기억해 줘")
    check("① 어간 '엑셀' 포함", "엑셀" in kws, str(kws))
    check("① 어간 '규칙' 포함", "규칙" in kws, str(kws))
    check("① 원형 '엑셀로' 도 보유", "엑셀로" in kws, str(kws))
    check("① '보고서를' → '보고서'", "보고서" in mm.extract_keywords("보고서를 만들어"),
          str(mm.extract_keywords("보고서를 만들어")))

    # ② remember 후 조사 붙은 질의로 회상.
    saved = mm.add_user_memory("엑셀 매크로는 반드시 xlsm 형식으로 저장한다", title="엑셀 매크로 규칙")
    items = mm.recall(keywords=mm.extract_keywords("엑셀로 정리해줘"), limit=5)
    check("② '엑셀로' 질의가 엑셀 규칙 회상",
          any(i.get("id") == saved.get("id") for i in items),
          str([i.get("title") for i in items]))
    # ②b 별칭 확장: 영문 'excel' 질의도 한글 '엑셀' 기억과 만난다.
    items2 = mm.recall(keywords=["excel"], limit=5)
    check("②b 별칭 excel→엑셀 회상",
          any(i.get("id") == saved.get("id") for i in items2),
          str([i.get("title") for i in items2]))

    # ③ recall --pinned: 키워드 인자 없이 core memory 를 출력한다(CLI 경유).
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "agent_ops" / "agentops.py"), "recall", "--pinned"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(ROOT))
    check("③ recall --pinned 종료코드 0", proc.returncode == 0, proc.stderr[-500:])
    check("③ core memory(사용자 규칙) 출력", "xlsm" in (proc.stdout or ""),
          (proc.stdout or "")[-500:])

    print(f"ALL PASS ({PASS} checks)")


if __name__ == "__main__":
    main()
