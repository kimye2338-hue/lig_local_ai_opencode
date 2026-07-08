# -*- coding: utf-8 -*-
"""opencode.json 무결성 고정 — WS-5 1단계(오프라인 검증 가능).

사내망에서 opencode.json 이 깨지면 TUI 가 게이트웨이에 못 붙고 원격 복구가 어렵다.
그래서 값 자체(불변 규칙)는 건드리지 않되, 아래 구조 불변식을 테스트로 못박는다:
  1) JSON 이 유효하다.
  2) 최상위 기본 model 이 "provider/model" 이고 실제 정의된 provider·model 로 resolve 된다.
  3) 모든 provider 는 baseURL/apiKey/models 를 갖는다.
  4) 모든 baseURL 이 사내 게이트웨이(.../gateway/<모델-템플릿>/v1)를 가리킨다(외부 URL 유입 방지).
  5) 기본 model 의 라우트는 think_off(=tool calling 확인됨)여야 한다 — 기본값이 tool 미확인 라우트로
     바뀌면 에이전트 루프가 깨지므로 회귀로 막는다. (모델 A/B 로 기본값을 바꾸더라도 think_off 는 유지)

Run: py -3.11 tests\\test_opencode_config.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
CONFIG = WS / "opencode.json"
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
    check("opencode.json exists", CONFIG.is_file(), str(CONFIG))
    raw = CONFIG.read_text(encoding="utf-8")
    try:
        cfg = json.loads(raw)
        ok = True
    except Exception as exc:  # noqa: BLE001
        ok = False
        check("opencode.json is valid JSON", False, str(exc))
    check("opencode.json is valid JSON", ok)

    providers = cfg.get("provider", {})
    check("has at least one provider", isinstance(providers, dict) and len(providers) >= 1,
          str(list(providers)))

    # 2) 기본 model resolve
    model = cfg.get("model", "")
    check("top-level model is 'provider/model'", isinstance(model, str) and model.count("/") >= 1, model)
    prov_id, _, model_id = model.partition("/")
    check("default provider is defined", prov_id in providers, f"{prov_id} not in {list(providers)}")
    default_prov = providers.get(prov_id, {})
    check("default model id is defined under provider",
          model_id in (default_prov.get("models") or {}),
          f"{model_id} not in {list((default_prov.get('models') or {}))}")

    # 3) provider 구조 + 4) baseURL 이 사내 게이트웨이
    for pid, p in providers.items():
        opts = p.get("options", {})
        base = opts.get("baseURL", "")
        check(f"{pid}: baseURL present", isinstance(base, str) and base.strip() != "", str(base))
        check(f"{pid}: apiKey present", isinstance(opts.get("apiKey"), str) and opts["apiKey"] != "", "")
        check(f"{pid}: has models", isinstance(p.get("models"), dict) and len(p["models"]) >= 1, "")
        check(f"{pid}: baseURL points to internal gateway",
              "ligdefenseaerospace.com" in base and "/gateway/" in base and base.rstrip("/").endswith("/v1"),
              base)

    # 5) 기본 라우트는 think_off (tool calling 확인된 라우트만 기본값 허용)
    default_base = default_prov.get("options", {}).get("baseURL", "")
    check("default route is think_off (tool-calling safe)",
          "think_off" in default_base, default_base)

    print(f"\nALL {PASS} CHECKS PASSED (opencode config)")


if __name__ == "__main__":
    main()
