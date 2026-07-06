# -*- coding: utf-8 -*-
"""루틴(record & replay) — 검증된 작업을 저장했다가 LLM 없이 자동 재생.

"한 번 (에이전트로) 해보고 성공한 작업은, 다음부터 매번 모델이 다시 생각하지 말고
검증된 도구 호출 순서를 그대로 재생한다." 반복 업무(양식 채우기, 포털 절차, 정형 보고서)에
유용하고 토큰/시간을 아낀다. RPA 개념(openclaw-rpa/HyperAgent의 deterministic replay)을
우리 인프라로 자체 구현 — 우리는 이미 모든 도구 호출을 tool-dispatch-history.jsonl 에 기록.

- 저장 소스: `<diag>/tool-dispatch-history.jsonl` 의 **직전 성공 호출 블록**.
- 재생: 각 단계를 ToolDispatcher 로 실행 → command_guard/safety 를 그대로 통과(안전 유지).
- 루틴은 `USERDATA/memory/routines/*.json` 에 저장(패치/재설치해도 보존).

주의: 재생은 결정적 도구(파일/데이터/정형 절차)에 적합. 화면이 바뀌는 브라우저 절차는
셀렉터가 달라지면 실패할 수 있으니, 재생 결과의 성공/실패를 반드시 확인한다(맹신 금지).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .core import MEMORY, now
except Exception:  # 폴백
    from datetime import datetime

    MEMORY = Path.home() / "OpenCodeLIG_USERDATA" / "memory"

    def now() -> str:  # type: ignore
        return datetime.now().astimezone().isoformat(timespec="seconds")

ROUTINES_DIR = MEMORY / "routines"
MAX_STEPS = 50
# 재생하면 안 되는(부작용/일회성) 도구는 저장에서 제외.
_SKIP_TOOLS = {"run_diagnostic", "remember", "project_info", "screenshot"}


def _slug(name: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|#\[\]\s]+", "_", str(name).strip()).strip("._")
    return (s or "routine")[:60]


def routine_from_history(diag_dir: Path, max_steps: int = MAX_STEPS) -> List[Dict[str, Any]]:
    """히스토리에서 '직전 성공 호출 블록'을 단계 목록으로. 실패를 만나면 거기서 끊는다."""
    path = Path(diag_dir) / "tool-dispatch-history.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    steps: List[Dict[str, Any]] = []
    for raw in reversed(lines):  # 뒤에서부터, 성공 블록만
        try:
            e = json.loads(raw)
        except Exception:
            continue
        if not e.get("ok"):
            break  # 마지막 실패 이전까지가 '검증된' 블록
        tool = str(e.get("tool") or "")
        if not tool or tool in _SKIP_TOOLS:
            continue
        steps.append({"tool": tool, "arguments": e.get("arguments", {})})
        if len(steps) >= max_steps:
            break
    steps.reverse()
    return steps


def save_routine(name: str, steps: List[Dict[str, Any]], description: str = "") -> Dict[str, Any]:
    if not steps:
        return {"ok": False, "error": "저장할 성공 단계가 없습니다 (먼저 작업을 성공시키세요)"}
    ROUTINES_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug(name)
    data = {"name": name, "slug": slug, "created": now(),
            "description": description, "steps": steps}
    path = ROUTINES_DIR / f"{slug}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(path), "slug": slug, "step_count": len(steps)}


def list_routines() -> List[Dict[str, Any]]:
    if not ROUTINES_DIR.is_dir():
        return []
    out = []
    for p in sorted(ROUTINES_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            out.append({"slug": d.get("slug") or p.stem, "name": d.get("name") or p.stem,
                        "steps": len(d.get("steps", [])), "created": d.get("created", "")})
        except Exception:
            continue
    return out


def load_routine(name_or_slug: str) -> Optional[Dict[str, Any]]:
    slug = _slug(name_or_slug)
    path = ROUTINES_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def import_routine(path: Path) -> Dict[str, Any]:
    """JSON 파일에서 루틴을 등록(프리셋). 관리자/사용자가 미리 정의한 절차를 반입한다.

    파일 형식: {"name": "...", "steps": [{"tool": "...", "arguments": {...}}, ...]}
    또는 steps 만 있는 리스트. 검증된 프리셋만 넣을 것(재생은 command_guard 를 통과한다).
    """
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"파일 없음: {path}"}
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"JSON 파싱 실패: {exc!r}"}
    if isinstance(data, list):
        name, steps = p.stem, data
    else:
        name, steps = data.get("name") or p.stem, data.get("steps") or []
    steps = [{"tool": str(s.get("tool")), "arguments": s.get("arguments", {})}
             for s in steps if isinstance(s, dict) and s.get("tool")]
    if not steps:
        return {"ok": False, "error": "유효한 steps 가 없습니다"}
    return save_routine(name, steps, description=(data.get("description", "") if isinstance(data, dict) else ""))


def run_routine(name_or_slug: str, dispatcher: Any) -> Dict[str, Any]:
    """루틴을 ToolDispatcher 로 순서대로 재생. 실패 단계에서 멈추고 결과 보고."""
    routine = load_routine(name_or_slug)
    if not routine:
        return {"ok": False, "error": f"루틴 없음: {name_or_slug}"}
    results = []
    for i, step in enumerate(routine.get("steps", [])):
        call = {"name": step.get("tool"), "arguments": step.get("arguments", {})}
        try:
            r = dispatcher.dispatch(call)
        except Exception as exc:  # noqa: BLE001
            r = {"ok": False, "error": f"dispatch 예외: {exc!r}"}
        results.append({"step": i + 1, "tool": call["name"], "ok": bool(r.get("ok")),
                        "error": r.get("error", "")})
        if not r.get("ok"):
            return {"ok": False, "stopped_at": i + 1, "reason": r.get("error", "step failed"),
                    "results": results, "total": len(routine.get("steps", []))}
    return {"ok": True, "results": results, "total": len(results)}
