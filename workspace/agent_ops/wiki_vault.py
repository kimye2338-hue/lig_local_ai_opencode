# -*- coding: utf-8 -*-
"""Obsidian vault 시드 — LLM 위키를 Obsidian으로 직접 열람/편집하기 위한 설정.

위키 원본은 `%USERPROFILE%\\OpenCodeLIG_USERDATA\\memory\\wiki\\` (전역 기억, 불가침).
이 모듈은 그 폴더를 Obsidian vault 로 만드는 `.obsidian/` 설정을 **없을 때만** 시드한다
(사용자가 Obsidian 에서 바꾼 설정은 절대 덮어쓰지 않는다). 위키 페이지는 이미
`[[주제]]` 위키링크를 쓰므로 Obsidian 이 백링크/그래프로 그대로 렌더링한다.

오프라인 전제: 네트워크 0. 커뮤니티 플러그인 불필요 — 코어 플러그인만 켠다.

사용:
  python -m agent_ops.wiki_vault [vault_dir]
인자 없으면 core.MEMORY / "wiki" 를 vault 로 사용한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from .core import MEMORY
except Exception:  # 단독 실행 폴백
    MEMORY = Path.home() / "OpenCodeLIG_USERDATA" / "memory"


def _vault_dir(arg: str | None = None) -> Path:
    if arg:
        return Path(arg)
    return MEMORY / "wiki"


def _write_if_absent(path: Path, data: Dict[str, Any]) -> bool:
    """파일이 없을 때만 JSON 을 쓴다. 사용자 설정 보존이 최우선."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def seed_obsidian_vault(vault_dir: Path | None = None) -> Dict[str, Any]:
    """vault 폴더에 Obsidian 최소 설정을 시드한다. 멱등(있으면 미변경)."""
    vault = vault_dir or _vault_dir()
    vault.mkdir(parents=True, exist_ok=True)
    obs = vault / ".obsidian"
    seeded = []

    # 코어 플러그인만 (오프라인/망분리 안전). 백링크·그래프·검색·아웃라인.
    if _write_if_absent(obs / "core-plugins.json", {
        "file-explorer": True,
        "global-search": True,
        "switcher": True,
        "graph": True,
        "backlink": True,
        "outgoing-link": True,
        "tag-pane": True,
        "page-preview": True,
        "note-composer": True,
        "command-palette": True,
        "outline": True,
        "word-count": True,
    }):
        seeded.append("core-plugins.json")

    # 커뮤니티 플러그인 비활성(빈 목록) — 인터넷 없이도 경고 없이 열리게.
    if _write_if_absent(obs / "community-plugins.json", []):
        seeded.append("community-plugins.json")

    # 앱 동작: 위키링크 사용, 새 링크는 상대경로, md 확장자 자동.
    if _write_if_absent(obs / "app.json", {
        "useMarkdownLinks": False,          # [[위키링크]] 유지
        "newLinkFormat": "shortest",
        "attachmentFolderPath": "manual",
        "alwaysUpdateLinks": True,
        "showUnsupportedFiles": True,
        "defaultViewMode": "preview",
    }):
        seeded.append("app.json")

    # 한국어 사용자 기본 다크 테마 + 가독성.
    if _write_if_absent(obs / "appearance.json", {
        "baseFontSize": 16,
        "theme": "obsidian",
    }):
        seeded.append("appearance.json")

    # 첫 방문 안내 노트 (없을 때만).
    welcome = vault / "0-위키-안내.md"
    if not welcome.exists():
        welcome.write_text(
            "# OpenCodeLIG 기억 위키 (Obsidian)\n\n"
            "이 폴더는 AI 비서의 **장기 기억**입니다. Obsidian 으로 직접 읽고 고칠 수 있습니다.\n\n"
            "- `index.md` — 전체 주제 색인\n"
            "- 각 `주제.md` — 자동 정리된 지식 페이지 (`[[주제]]` 로 서로 연결)\n"
            "- `manual/` — 사용자가 직접 쓰는 노트 (AI 가 지우지 않음)\n"
            "- `log.md` — lint(중복/고아/모순 후보) 보고\n\n"
            "왼쪽 그래프 뷰로 기억의 연결을 볼 수 있고, 백링크 패널로 역참조를 봅니다.\n"
            "AI 가 자동 생성한 페이지도 여기서 직접 수정하면 다음 정리에 반영됩니다.\n",
            encoding="utf-8",
        )
        seeded.append("0-위키-안내.md")

    # 대시보드 노트 (없을 때만). Dataview 플러그인이 있으면 쿼리가 표로 렌더되고,
    # 없어도 일반 노트로 읽힌다. 일정/기억은 아래 폴더의 노트를 스캔한다.
    dashboard = vault / "0-대시보드.md"
    if not dashboard.exists():
        dashboard.write_text(
            "# 대시보드\n\n"
            "> Dataview 플러그인을 켜면 아래가 표로 자동 집계됩니다. (설치: docs/기능/OBSIDIAN_WIKI.md)\n\n"
            "## 미결 액션아이템\n\n"
            "```dataview\n"
            "TASK\n"
            "WHERE !completed\n"
            "```\n\n"
            "## 최근 활동 (기억 위키)\n\n"
            "```dataview\n"
            "TABLE file.mtime AS \"수정\"\n"
            "FROM \"\"\n"
            "SORT file.mtime DESC\n"
            "LIMIT 15\n"
            "```\n\n"
            "## 최근 정리된 주제 페이지\n\n"
            "```dataview\n"
            "LIST\n"
            "FROM \"\"\n"
            "WHERE file.name != this.file.name\n"
            "SORT file.mtime DESC\n"
            "LIMIT 20\n"
            "```\n\n"
            "미결 할 일은 아무 노트에서나 `- [ ] 내용` 으로 적으면 위 목록에 모입니다.\n",
            encoding="utf-8",
        )
        seeded.append("0-대시보드.md")

    return {"vault": str(vault), "seeded": seeded, "already_ready": not seeded}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    result = seed_obsidian_vault(_vault_dir(argv[0] if argv else None))
    if result["already_ready"]:
        print(f"[wiki-vault] Obsidian vault 준비됨: {result['vault']}")
    else:
        print(f"[wiki-vault] Obsidian 설정 시드: {result['vault']}")
        for name in result["seeded"]:
            print(f"  + {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
