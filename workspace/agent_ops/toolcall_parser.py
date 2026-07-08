# -*- coding: utf-8 -*-
"""Tool-call extraction/repair for weak internal models (EXAONE/Qwen class).

Production models may emit malformed JSON, partial tool calls, tool calls in
plain text, or mixed natural language + JSON. This module normalizes all of
those into a single shape and reports how far recovery had to go, so the
runtime can decide: accept / retry with tighter instruction / fall back.

Normalized tool call: {"name": str, "arguments": dict, "id": str}

parse_status values:
  ok        - structured tool_calls field parsed cleanly
  repaired  - tool call recovered from content text or after JSON repair
  none      - response contains no tool-call attempt (plain answer)
  failed    - a tool-call attempt was detected but could not be recovered
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

_FENCE_RE = re.compile(r"```(?:json|tool|tool_call)?\s*(.*?)```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
# Signals that the text is *trying* to call a tool even if JSON is broken.
_INTENT_RE = re.compile(r'"?(?:tool_calls?|function_call|tool_name|name)"?\s*[:=]', re.IGNORECASE)
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_reasoning(s: str) -> str:
    """<think>...</think> reasoning 블록 제거 — 방어용 안전장치.

    게이트웨이 라우트가 이미 *_think_off 라서 평상시엔 순수 no-op:
    입력에 <think 가 없으면 원본을 그대로 반환한다. think가 흘러들어온
    경우에만 닫힌 블록을 제거하고, 닫는 태그 없이 열린 <think>는 그
    지점부터 끝까지 reasoning으로 간주해 잘라낸다(잘린 출력 대응).
    """
    if not s or "<think" not in s:
        return s
    out = _THINK_BLOCK_RE.sub("", s)
    idx = out.find("<think>")
    if idx != -1:
        out = out[:idx]
    return out


def _repair_json_text(text: str) -> Optional[Any]:
    """Try progressively safer repairs; return parsed object or None."""
    candidates = [text, _TRAILING_COMMA_RE.sub(r"\1", text)]
    # Truncated output: try closing unbalanced braces/brackets (max 4 levels).
    stripped = _TRAILING_COMMA_RE.sub(r"\1", text).rstrip().rstrip(",")
    opens = stripped.count("{") - stripped.count("}")
    opens_sq = stripped.count("[") - stripped.count("]")
    if 0 < opens <= 4 or 0 < opens_sq <= 4:
        candidates.append(stripped + "]" * max(opens_sq, 0) + "}" * max(opens, 0))
    for cand in candidates:
        try:
            return json.loads(cand)
        except Exception:
            continue
    return None


def _extract_json_objects(text: str) -> List[Any]:
    """Find JSON objects embedded in mixed prose via balanced-brace scan."""
    objs: List[Any] = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                parsed = _repair_json_text(text[start : i + 1])
                if parsed is not None:
                    objs.append(parsed)
    # Truncated trailing object (opened, never closed).
    if depth > 0 and start >= 0:
        parsed = _repair_json_text(text[start:])
        if parsed is not None:
            objs.append(parsed)
    return objs


def _coerce_arguments(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    if isinstance(raw, str):
        parsed = _repair_json_text(raw) if raw.strip() else {}
        if isinstance(parsed, dict):
            return parsed
    return None


def _normalize_one(obj: Any, strict: bool = False,
                   known: Optional[set] = None) -> Optional[Dict[str, Any]]:
    """Accept the many shapes weak models emit for a single tool call.

    strict=True (content 복구 경로): arguments/parameters/args 키가 실제로
    있거나 name이 알려진 도구일 때만 툴콜로 인정한다 — 아니면 평문 답변 속
    데이터 JSON(예: {"name": "보고서.docx", "size": 3})이 툴콜로 승격되어
    정상 답변이 재시도/폴백을 유발한다.
    """
    if not isinstance(obj, dict):
        return None
    raw_id = obj.get("id")
    call_id = raw_id.strip() if isinstance(raw_id, str) else ""
    if call_id.upper() == "N/A":
        call_id = ""
    # OpenAI shape: {"function": {"name":..., "arguments":...}}
    if isinstance(obj.get("function"), dict):
        obj = obj["function"]
    name = obj.get("name") or obj.get("tool_name") or obj.get("tool")
    if not isinstance(name, str) or not name.strip():
        return None
    has_args_key = any(k in obj for k in ("arguments", "parameters", "args"))
    if strict and not has_args_key and not (known and name.strip() in known):
        return None
    args = _coerce_arguments(
        obj.get("arguments") if "arguments" in obj else obj.get("parameters") if "parameters" in obj else obj.get("args")
    )
    if args is None:
        return None
    return {"name": name.strip(), "arguments": args, "id": call_id}


def _normalize_many(obj: Any, strict: bool = False,
                    known: Optional[set] = None) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    items = obj if isinstance(obj, list) else [obj]
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("tool_calls"), list):
            for sub in item["tool_calls"]:
                one = _normalize_one(sub, strict=strict, known=known)
                if one:
                    calls.append(one)
            continue
        one = _normalize_one(item, strict=strict, known=known)
        if one:
            calls.append(one)
    return calls


def parse_tool_calls(response: Any, available_tools: Optional[List[str]] = None) -> Dict[str, Any]:
    """Parse an OpenAI-style response dict or raw model text.

    Returns {parse_status, tool_calls, unavailable_tools, errors, raw_excerpt}.
    """
    errors: List[str] = []
    content = ""
    structured: List[Dict[str, Any]] = []

    if isinstance(response, dict):
        try:
            msg = (response.get("choices") or [{}])[0].get("message") or {}
        except Exception:
            msg = {}
        # content가 리스트(멀티파트)/기타 타입이어도 항상 str로 강제 — 아래
        # 정규식 스캔에서 TypeError로 call_llm 전체가 죽는 것을 막는다.
        raw_content = msg.get("content")
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            content = "\n".join(
                str(p.get("text", "")) if isinstance(p, dict) else str(p)
                for p in raw_content)
        elif raw_content:
            content = str(raw_content)
        raw_calls = msg.get("tool_calls") or ([msg["function_call"]] if isinstance(msg.get("function_call"), dict) else [])
        # tool_calls가 JSON '문자열'로 오는 게이트웨이/약한 모델 대응 — 그대로
        # 순회하면 문자 단위로 돌아 글자 수만큼 오류가 쌓이고 실제 콜은 유실된다.
        if isinstance(raw_calls, str):
            parsed = _repair_json_text(raw_calls)
            raw_calls = parsed if isinstance(parsed, list) else ([parsed] if isinstance(parsed, dict) else [])
        elif not isinstance(raw_calls, list):
            raw_calls = [raw_calls]
        for rc in raw_calls:
            one = _normalize_one(rc)
            if one:
                structured.append(one)
            else:
                errors.append(f"unrecoverable structured tool call: {str(rc)[:200]}")
        if raw_calls and not structured and not errors:
            errors.append("tool_calls field present but empty/invalid")
    else:
        content = str(response or "")

    # 방어용: think가 흘러들어와도 <think> 블록은 스캔/발췌 대상에서 제외 —
    # think 안에서 '언급'된 도구 JSON이 실제 툴콜로 승격되는 것을 막는다.
    content = strip_reasoning(content)

    status = "ok" if structured else "none"
    calls = structured
    repaired = False

    if not calls and content:
        # 복구 경로는 엄격 모드: args 키가 있거나 알려진 도구명일 때만 인정.
        known = set(available_tools) if available_tools else None
        # 1) fenced blocks first (most explicit), then embedded objects.
        segments = _FENCE_RE.findall(content) or [content]
        for seg in segments:
            parsed = _repair_json_text(seg.strip())
            found = (_normalize_many(parsed, strict=True, known=known) if parsed is not None
                     else _normalize_many(_extract_json_objects(seg), strict=True, known=known))
            if found:
                calls = found
                repaired = True
                break
        if not calls and segments != [content]:
            found = _normalize_many(_extract_json_objects(content), strict=True, known=known)
            if found:
                calls = found
                repaired = True
        if calls:
            status = "repaired"
        elif _INTENT_RE.search(content):
            status = "failed"
            errors.append("tool-call intent detected in text but not recoverable")

    unavailable: List[str] = []
    if available_tools is not None:
        known = set(available_tools)
        unavailable = sorted({c["name"] for c in calls if c["name"] not in known})

    return {
        "parse_status": status,
        "tool_calls": calls,
        "repaired": repaired,
        "unavailable_tools": unavailable,
        "errors": errors,
        "raw_excerpt": content[:400],
    }
