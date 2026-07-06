# -*- coding: utf-8 -*-
"""구(舊) 모드/에이전트 파일 정리 — 설치·패치 시 잉여 primary 를 제거한다.

합의된 구조: 모드는 build/plan/agent 3개뿐이고, 커스텀 **primary 에이전트는 정확히
하나(agent.md)** 다. 과거 버전이 남긴 다른 custom primary(.opencode/agents/*.md 중
`mode: primary` 인데 agent.md 가 아닌 것)를 그대로 두면 Tab 순환에 옛 모드가 계속
끼어든다. 이 스크립트가 그런 파일을 삭제해 'primary=agent 하나'를 강제한다.

안전 원칙:
  - **subagent 는 절대 건드리지 않는다** (agentops-* 는 canonical).
  - `mode: primary` 이고 파일명이 agent.md 가 아닌 것만 삭제.
  - 삭제한 파일은 stdout 에 남긴다(조용한 삭제 금지). USERDATA/기억은 불가침 —
    이 스크립트는 프로그램 설정(.opencode)만 만진다.

사용:
  python -m agent_ops.clean_stale [.opencode 경로]
인자 없으면 이 파일 기준 `../.opencode` (설치된 workspace)를 쓴다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

CANONICAL_PRIMARY = "agent.md"


def _opencode_dir(arg: str | None = None) -> Path:
    if arg:
        return Path(arg)
    # agent_ops/clean_stale.py -> workspace/.opencode
    return Path(__file__).resolve().parent.parent / ".opencode"


def _is_primary(md_text: str) -> bool:
    # 프론트매터의 `mode: primary` 만 본다(본문 우연 매치 방지: 앞부분에서 검색).
    head = md_text[:1500]
    return bool(re.search(r"(?m)^\s*mode:\s*primary\s*$", head))


def clean_stale(opencode_dir: Path | None = None) -> Dict[str, List[str]]:
    root = opencode_dir or _opencode_dir()
    agents = root / "agents"
    removed: List[str] = []
    kept_primary: List[str] = []
    if not agents.is_dir():
        return {"removed": removed, "kept_primary": kept_primary, "root": [str(root)]}
    for md in sorted(agents.glob("*.md")):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not _is_primary(text):
            continue  # subagent 등은 유지
        if md.name == CANONICAL_PRIMARY:
            kept_primary.append(md.name)
            continue
        try:
            md.unlink()
            removed.append(md.name)
        except Exception as exc:  # noqa: BLE001
            removed.append(f"{md.name} (삭제 실패: {exc!r})")
    return {"removed": removed, "kept_primary": kept_primary, "root": [str(root)]}


def main(argv: List[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    result = clean_stale(_opencode_dir(argv[0] if argv else None))
    if result["removed"]:
        print("[clean-stale] 구 primary/모드 파일 삭제:")
        for name in result["removed"]:
            print(f"  - {name}")
    else:
        print("[clean-stale] 구 primary 없음 — 구조 정상(primary=agent 하나).")
    if not result["kept_primary"]:
        print("[clean-stale] 경고: agent.md primary 가 없습니다. 패키지 확인 필요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
