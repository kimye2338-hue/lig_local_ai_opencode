# -*- coding: utf-8 -*-
"""Gateway probe: measure how the company LLM API actually behaves.

The user runs launch\\probe-gateway.bat on the company PC (after filling
lig-api.env). It calls each configured route and records, secret-free:
  1. reachability + latency + a basic completion
  2. whether OpenAI-style `tools` (function calling) is supported —
     does the response carry `tool_calls`?
  3. how the model answers a *prompt-based* tool-call instruction
     (our pipeline's format) — raw text sample for parser tuning

Masking guarantees (safe to upload to the public repo):
  - API key never logged; Authorization header never logged
  - base_url host is replaced by <GATEWAY>; only the route path is kept
  - request/response samples are truncated and scanned for the key value

Local dev: works the same against LIG_PROVIDER_PROFILE=local_openai (Ollama).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_ops.lig_providers import build_providers, load_lig_env, validate_config  # noqa: E402

_SAMPLE_LIMIT = 1500

_TOOLS_SCHEMA = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "워크스페이스의 텍스트 파일을 읽는다",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]},
    },
}]

_TEXT_TOOLCALL_PROMPT = (
    "당신은 도구를 호출하는 에이전트다. 다음 JSON 형식으로만 응답하라. 다른 말 금지.\n"
    '{"tool": "read_file", "args": {"path": "<읽을 파일>"}}\n'
    "작업: 메모.txt 파일을 읽어라."
)


def _mask(text: str, secrets: list) -> str:
    out = text or ""
    for s in secrets:
        if s and len(s) >= 4:
            out = out.replace(s, "<MASKED>")
    return out[:_SAMPLE_LIMIT]


def _route_only(base_url: str) -> str:
    try:
        return "<GATEWAY>" + urlparse(base_url).path
    except Exception:
        return "<GATEWAY>/<unparsed>"


def _post(base_url: str, api_key: str, payload: dict, timeout: int):
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {api_key}"} if api_key else {})},
        method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return int((time.time() - t0) * 1000), body


def _try_url(url: str, api_key: str, secrets: list, timeout: int,
             method: str = "GET", payload: dict = None) -> dict:
    """One discovery attempt: record status + masked body sample, never raise."""
    try:
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {api_key}"} if api_key else {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status": resp.status,
                    "body": _mask(resp.read(600).decode("utf-8", errors="replace"), secrets)}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code,
                "body": _mask(exc.read(600).decode("utf-8", errors="replace"), secrets)}
    except Exception as exc:
        return {"status": "error", "body": _mask(repr(exc), secrets)[:200]}


def discover_paths(gateway_root: str, route_base: str, model: str,
                   api_key: str, secrets: list, timeout: int) -> list:
    """When the configured path 404s, systematically try common variants so
    the user learns the correct lig-api.env values from one run.

    Every attempt is recorded with masked path + status + body sample —
    404 bodies often name the valid routes, which is exactly what we need.
    """
    chat_payload = {"model": model, "max_tokens": 8,
                    "messages": [{"role": "user", "content": "ping"}]}
    root = gateway_root.rstrip("/")
    base = route_base.rstrip("/")
    no_v1 = base[:-3] if base.endswith("/v1") else base
    candidates = [
        ("POST", base + "/chat/completions", chat_payload),      # 설정값 그대로 (기준)
        ("POST", no_v1 + "/chat/completions", chat_payload),     # 라우트에 /v1 없음
        ("POST", root + "/v1/chat/completions", chat_payload),   # 모델이 payload로만 구분
        ("POST", root + "/chat/completions", chat_payload),
        ("GET", base + "/models", None),                          # 모델 목록 (경로 힌트)
        ("GET", no_v1 + "/models", None),
        ("GET", root + "/v1/models", None),
        ("GET", root + "/models", None),
        ("GET", root, None),                                      # 루트 응답 (안내 페이지/목록)
    ]
    results = []
    seen = set()
    for method, url, payload in candidates:
        if url in seen:
            continue
        seen.add(url)
        outcome = _try_url(url, api_key, secrets, timeout, method, payload)
        results.append({"method": method, "path": _route_only(url), **outcome})
    return results


def probe_route(name: str, provider: dict, api_key: str, secrets: list) -> dict:
    result = {"route": name, "endpoint": _route_only(provider["base_url"]),
              "model": provider["model"]}
    timeout = int(provider.get("timeout", "120") or "120")
    base = provider["base_url"]
    if not base:
        result["error"] = "base_url 미설정 (lig-api.env 확인)"
        return result
    # 1) basic completion
    try:
        ms, body = _post(base, api_key, {
            "model": provider["model"], "max_tokens": 32,
            "messages": [{"role": "user", "content": "1+1은? 숫자만."}]}, timeout)
        result["basic"] = {"ok": True, "latency_ms": ms,
                           "sample": _mask(body, secrets)}
    except urllib.error.HTTPError as exc:
        # 404 등 HTTP 오류: 응답 본문에 올바른 라우트 힌트가 있을 수 있다.
        detail = exc.read(600).decode("utf-8", errors="replace")
        result["basic"] = {"ok": False, "http_status": exc.code,
                           "error": _mask(repr(exc), secrets),
                           "body_sample": _mask(detail, secrets)}
        if exc.code == 404:
            gateway_root = os.environ.get("LIG_GATEWAY_BASE_URL") or ""
            if not gateway_root:
                from agent_ops.lig_providers import load_lig_env as _lle
                gateway_root = _lle().get("LIG_GATEWAY_BASE_URL", "")
            result["discovery"] = discover_paths(
                gateway_root or base, base, provider["model"],
                api_key, secrets, min(timeout, 15))
            result["discovery_hint"] = ("status 200/400/422가 나온 path가 올바른 형태입니다. "
                                        "lig-api.env의 LIG_ROUTE_*/LIG_GATEWAY_BASE_URL을 그 형태로 수정하세요 "
                                        "(코드 수정 불필요).")
        return result
    except Exception as exc:
        result["basic"] = {"ok": False, "error": _mask(repr(exc), secrets)}
        return result  # 기본 호출 실패면 나머지 생략
    # 2) OpenAI function-calling support
    try:
        ms, body = _post(base, api_key, {
            "model": provider["model"], "max_tokens": 128,
            "messages": [{"role": "user", "content": "메모.txt 파일을 읽어줘"}],
            "tools": _TOOLS_SCHEMA}, timeout)
        parsed = json.loads(body)
        msg = (parsed.get("choices") or [{}])[0].get("message", {})
        result["openai_tools"] = {
            "accepted": True,
            "tool_calls_present": bool(msg.get("tool_calls")),
            "latency_ms": ms,
            "sample": _mask(body, secrets),
        }
    except urllib.error.HTTPError as exc:
        result["openai_tools"] = {
            "accepted": False,
            "http_status": exc.code,
            "sample": _mask(exc.read().decode("utf-8", errors="replace"), secrets)}
    except Exception as exc:
        result["openai_tools"] = {"accepted": False,
                                  "error": _mask(repr(exc), secrets)}
    # 3) prompt-based tool call (our pipeline format)
    try:
        ms, body = _post(base, api_key, {
            "model": provider["model"], "max_tokens": 128,
            "messages": [{"role": "user", "content": _TEXT_TOOLCALL_PROMPT}]}, timeout)
        parsed = json.loads(body)
        content = (parsed.get("choices") or [{}])[0].get("message", {}).get("content", "")
        result["text_toolcall"] = {"ok": True, "latency_ms": ms,
                                   "raw_content": _mask(content, secrets)}
    except Exception as exc:
        result["text_toolcall"] = {"ok": False, "error": _mask(repr(exc), secrets)}
    return result


def main() -> int:
    env = load_lig_env()
    report_cfg = validate_config(env)  # presence flags only
    profile = os.environ.get("LIG_PROVIDER_PROFILE", "company_gateway")
    if profile == "local_openai":
        base = os.environ.get("LIG_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1")
        model = os.environ.get("LIG_LOCAL_MODEL", "qwen2.5:7b-instruct")
        providers = {"local": {"base_url": base, "model": model, "timeout": "120"}}
        api_key = ""
    else:
        if not report_cfg.get("ready"):
            print("gateway 설정이 없습니다. 다음을 채우세요:", file=sys.stderr)
            for m in report_cfg.get("missing", []):
                print(f"  - {m}", file=sys.stderr)
            return 2
        providers = build_providers(env)
        api_key = env.get("LIG_API_KEY", "")
    secrets = [api_key, env.get("LIG_GATEWAY_BASE_URL", "")]
    # host부만 추가 마스킹 대상으로 등록
    try:
        secrets.append(urlparse(env.get("LIG_GATEWAY_BASE_URL", "")).netloc)
    except Exception:
        pass
    report = {"probe": "gateway", "version": 1,
              "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
              "profile": profile, "config": {k: report_cfg[k] for k in
                                             ("secret_file_found", "gateway_url_set", "api_key_set")
                                             if k in report_cfg},
              "routes": [probe_route(n, p, api_key, secrets)
                         for n, p in providers.items()]}
    out_dir = Path(os.environ.get("PROBE_OUT_DIR") or Path.cwd())
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"probe_gateway_{time.strftime('%Y%m%d')}.json"
    text = json.dumps(report, ensure_ascii=False, indent=2)
    # 마지막 안전망: 결과 전체에서 secret 잔존 검사
    for s in secrets:
        if s and len(s) >= 4 and s in text:
            print("[중단] 마스킹 실패 감지 — 파일을 쓰지 않았습니다.", file=sys.stderr)
            return 3
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n결과 파일 (repo의 probe/results/ 에 올려주세요):\n  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
