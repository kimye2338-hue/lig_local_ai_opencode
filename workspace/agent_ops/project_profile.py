# -*- coding: utf-8 -*-
"""폴더-로컬 프로필(.opencodelig) + 전역 기억 결합.

제품 방향(docs/archive/PRODUCT_VISION_AND_PROACTIVE_IMPLEMENTATION_20260705.md §3.3):
전역 기억은 모든 폴더가 공유하고, 폴더마다 페르소나/규칙/프로젝트 기억을
따로 둘 수 있다. 이 모듈이 그 단일 진실 소스다 — ocd 런처, 에이전트 루프
컨텍스트 주입, doctor 진단, LLM tool(project_info)이 전부 여기를 쓴다.

충돌 규칙(문서 §6.3):
  1) 안전 규칙과 전역 사용자 선호가 로컬 페르소나보다 우선한다.
  2) 로컬 프로젝트 규칙은 일반 기본값보다 우선한다.
  3) 충돌은 무시하지 말고 보고한다.

기억 보존 불변식(workspace-template/docs/기능/MEMORY_AND_SELF_EXTENSION.md):
이 모듈은 전역 기억 폴더를 절대 삭제/초기화하지 않는다. 로컬 시드 파일은
'없을 때만' 생성하고, 이미 있는 파일은 절대 덮어쓰지 않는다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

PROFILE_DIRNAME = ".opencodelig"
MAX_SECTION_CHARS = 4000  # 약모델 컨텍스트 보호: 로컬 파일 1개당 주입 상한

PROFILE_JSON_SEED: Dict[str, Any] = {
    "version": 1,
    "name": "folder-default",
    "created_by": "ocd",
    "global_memory": True,
    "local_memory": True,
    "persona_file": "PERSONA.md",
    "rules_file": "RULES.md",
    "project_memory_file": "PROJECT_MEMORY.md",
}

PERSONA_SEED = """# Folder persona

이 폴더의 전용 작업 스타일을 정의한다. 전역 사용자 선호는 그대로 유지된다.

## Role
- 커스터마이즈 전까지는 일반 프로젝트 비서.

## Style
- 전역 사용자 기억을 먼저 따른다.
- 프로젝트 고유 행동은 이 폴더의 RULES.md 를 따른다.
"""

PROJECT_MEMORY_SEED = """# Project memory

폴더 고유의 사실/결정/교훈을 여기에 적는다.

비밀(API 키/암호)은 여기에 저장하지 않는다.
"""

RULES_SEED = """# Project rules

- 전역 기억을 보존한다.
- 명시적 요청 없이 로컬 프로필 파일을 덮어쓰지 않는다.
- 프로젝트 고유 교훈은 전역 기억을 오염시키지 말고 여기에 기록한다.
"""

TASKS_SEED = """# Project tasks

이 폴더의 할 일을 적는다. 형식 자유 — 비서가 읽고 참고한다.

- [ ] (예) 첫 작업을 여기에 적으세요.
"""

SEED_FILES: Dict[str, str] = {
    "profile.json": json.dumps(PROFILE_JSON_SEED, ensure_ascii=False, indent=2) + "\n",
    "PERSONA.md": PERSONA_SEED,
    "PROJECT_MEMORY.md": PROJECT_MEMORY_SEED,
    "RULES.md": RULES_SEED,
    "TASKS.md": TASKS_SEED,
}

# 폴더 루트에 두는 '클릭용' 런처. 처음 ocd 하면 초기파일로 같이 생긴다 — 다음부터는
# 터미널 없이 이 파일만 더블클릭하면 이 폴더에서 OpenCode 가 바로 열린다(폴더 전용 페르소나).
# 설치된 ocd.bat 을 풀 경로로 호출해 PATH 설정 여부와 무관하게 동작. CRLF+chcp 로 기록.
LAUNCHER_NAME = "OpenCode_열기.bat"
LAUNCHER_BAT = (
    "@echo off\r\n"
    "chcp 65001 >nul\r\n"
    "rem 더블클릭하면 이 폴더에서 OpenCode 가 열린다(폴더 전용 페르소나 + 전역 기억).\r\n"
    "rem 터미널에서 `cd 이폴더` 후 `ocd` 친 것과 같은 효과. 처음 ocd 시 자동 생성됨.\r\n"
    'cd /d "%~dp0"\r\n'
    'call "%USERPROFILE%\\OpenCodeLIG\\bin\\ocd.bat" %*\r\n'
    "if errorlevel 9 (\r\n"
    "  echo.\r\n"
    "  echo [!] OpenCode(OpenCodeLIG) 설치를 찾지 못했습니다. 먼저 설치기를 실행하세요.\r\n"
    "  pause\r\n"
    ")\r\n"
)

CONFLICT_RULE = (
    "충돌 규칙: 안전 규칙과 전역 사용자 선호가 로컬 페르소나보다 우선. "
    "로컬 프로젝트 규칙은 일반 기본값보다 우선. "
    "전역 기억과 로컬 규칙이 충돌하면 무시하지 말고 사용자에게 보고."
)


def global_memory_dir() -> Path:
    """전역 기억 폴더 — core.MEMORY 와 같은 우선순위, 호출 시점 env 반영.

    AGENTOPS_MEMORY_DIR(명시) > AGENTOPS_ROOT/.agent-memory(테스트 격리)
    > %USERPROFILE%\\OpenCodeLIG_USERDATA\\memory (기본: 전역)
    """
    explicit = os.environ.get("AGENTOPS_MEMORY_DIR")
    if explicit:
        return Path(explicit)
    if os.environ.get("AGENTOPS_ROOT"):
        return Path(os.environ["AGENTOPS_ROOT"]) / ".agent-memory"
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    return home / "OpenCodeLIG_USERDATA" / "memory"


def resolve_project_dir(cwd: Optional[Path] = None) -> Optional[Path]:
    """활성 프로젝트 프로필 폴더. env 명시 > cwd/.opencodelig(존재 시) > None."""
    explicit = os.environ.get("AGENTOPS_PROJECT_DIR")
    if explicit:
        p = Path(explicit)
        return p if p.is_dir() else None
    base = Path(cwd) if cwd else Path.cwd()
    candidate = base / PROFILE_DIRNAME
    return candidate if candidate.is_dir() else None


def seed_profile(cwd: Path) -> Dict[str, Any]:
    """cwd/.opencodelig 생성 + 시드 파일을 '없을 때만' 생성.

    이미 존재하는(사용자가 고친) 파일은 절대 건드리지 않는다.
    반환: {"profile_dir", "created": [...], "reused": [...], "first_run": bool}
    """
    profile_dir = Path(cwd) / PROFILE_DIRNAME
    first_run = not profile_dir.is_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("diagnostics", "state"):
        (profile_dir / sub).mkdir(exist_ok=True)
    created: List[str] = []
    reused: List[str] = []
    for name, seed in SEED_FILES.items():
        target = profile_dir / name
        if target.exists():
            reused.append(name)
            continue
        target.write_text(seed, encoding="utf-8")
        created.append(name)
    # 폴더 루트에 클릭용 런처를 초기파일로 생성(없을 때만) — 다음부터 터미널 없이 더블클릭.
    launcher = Path(cwd) / LAUNCHER_NAME
    launcher_created = False
    if launcher.exists():
        reused.append(LAUNCHER_NAME)
    else:
        try:
            launcher.write_bytes(LAUNCHER_BAT.encode("utf-8"))  # CRLF 유지(바이트 기록)
            created.append(LAUNCHER_NAME)
            launcher_created = True
        except Exception:
            pass  # 폴더 쓰기 불가여도 ocd 자체는 계속 동작
    return {
        "profile_dir": str(profile_dir),
        "created": created,
        "reused": reused,
        "first_run": first_run,
        "launcher": str(launcher) if (launcher_created or launcher.exists()) else None,
    }


def _read_capped(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""
    if len(text) > MAX_SECTION_CHARS:
        text = text[:MAX_SECTION_CHARS] + "\n...(생략)"
    return text


def _project_file(project_dir: Path, env_key: str, default_name: str) -> Path:
    explicit = os.environ.get(env_key)
    return Path(explicit) if explicit else project_dir / default_name


def load_project_context(cwd: Optional[Path] = None) -> Dict[str, Any]:
    """활성 폴더 프로필의 persona/rules/project memory 텍스트를 읽는다.

    프로필이 없으면 {} — 주입은 조용히 생략된다(폴더 프로필은 선택 기능).
    """
    project_dir = resolve_project_dir(cwd)
    if project_dir is None:
        return {}
    persona_path = _project_file(project_dir, "AGENTOPS_PROJECT_PERSONA", "PERSONA.md")
    memory_path = _project_file(project_dir, "AGENTOPS_PROJECT_MEMORY", "PROJECT_MEMORY.md")
    rules_path = _project_file(project_dir, "AGENTOPS_PROJECT_RULES", "RULES.md")
    ctx = {
        "project_dir": str(project_dir),
        "persona_file": str(persona_path),
        "persona": _read_capped(persona_path),
        "project_memory_file": str(memory_path),
        "project_memory": _read_capped(memory_path),
        "rules_file": str(rules_path),
        "rules": _read_capped(rules_path),
    }
    if not (ctx["persona"] or ctx["project_memory"] or ctx["rules"]):
        return {}
    return ctx


def format_context_for_prompt(ctx: Dict[str, Any]) -> str:
    """주입 순서(문서 §6.3): 프로젝트 기억 → 페르소나 → 규칙 → 충돌 규칙."""
    if not ctx:
        return ""
    parts: List[str] = ["이 폴더의 프로젝트 프로필(.opencodelig) — 작업에 반영:"]
    if ctx.get("project_memory"):
        parts.append("[프로젝트 기억]\n" + ctx["project_memory"])
    if ctx.get("persona"):
        parts.append("[폴더 페르소나]\n" + ctx["persona"])
    if ctx.get("rules"):
        parts.append("[프로젝트 규칙]\n" + ctx["rules"])
    parts.append(CONFLICT_RULE)
    return "\n\n".join(parts)


def profile_diagnostics(cwd: Optional[Path] = None) -> Dict[str, Any]:
    """secret-free 진단: 어떤 전역/로컬 컨텍스트가 잡히는지 한눈에."""
    base = Path(cwd) if cwd else Path.cwd()
    project_dir = resolve_project_dir(base)
    mem = global_memory_dir()
    info: Dict[str, Any] = {
        "cwd": str(base),
        "global_memory_dir": str(mem),
        "global_memory_exists": mem.is_dir(),
        "global_memory_jsonl": (mem / "memory.jsonl").is_file(),
        "project_profile_dir": str(project_dir) if project_dir else "",
        "project_profile_active": project_dir is not None,
        "files": {},
    }
    if project_dir is not None:
        for name in SEED_FILES:
            info["files"][name] = (project_dir / name).is_file()
    return info
