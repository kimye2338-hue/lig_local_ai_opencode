# -*- coding: utf-8 -*-
"""One-shot pending validation report for OpenCodeLIG user packages.

This script is intentionally self-contained and conservative:
- it does not delete or overwrite USERDATA;
- it does not print gateway URLs or API keys;
- it writes a timestamped JSON/Markdown report under USERDATA diagnostics;
- it checks every currently pending class of feature in one run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

_WS_ROOT = Path(__file__).resolve().parents[1]
if str(_WS_ROOT) not in sys.path:
    sys.path.insert(0, str(_WS_ROOT))


@dataclass
class Check:
    section: str
    item: str
    status: str
    evidence: str
    next_action: str = ""


STATUSES = ("PASS", "WARN", "PENDING", "FAIL", "SKIP")


def now_stamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def workspace_root() -> Path:
    return _WS_ROOT


def package_root() -> Path:
    return workspace_root().parent


def diagnostics_dir() -> Path:
    env = os.environ.get("LIG_DIAG_DIR", "").strip().strip('"')
    if env:
        return Path(env)
    return Path.home() / "OpenCodeLIG_USERDATA" / "diagnostics"


def safe_rel(path: Path) -> str:
    try:
        return str(path)
    except Exception:
        return repr(path)


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def run_cmd(args: list[str], timeout: int = 10, cwd: Path | None = None) -> dict[str, Any]:
    try:
        cp = subprocess.run(args, cwd=str(cwd or workspace_root()), capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return {
            "ok": cp.returncode == 0,
            "returncode": cp.returncode,
            "stdout": (cp.stdout or "").strip()[:500],
            "stderr": (cp.stderr or "").strip()[:500],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]}


def find_existing(paths: Iterable[Path]) -> list[str]:
    found = []
    for p in paths:
        try:
            if p.exists():
                found.append(str(p))
        except Exception:
            pass
    return found


def common_program_paths() -> dict[str, list[Path]]:
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    pfx86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    return {
        "chrome": [
            pf / "Google" / "Chrome" / "Application" / "chrome.exe",
            pfx86 / "Google" / "Chrome" / "Application" / "chrome.exe",
        ],
        "obsidian": [
            local / "Programs" / "Obsidian" / "Obsidian.exe",
            pf / "Obsidian" / "Obsidian.exe",
        ],
        "matlab": [
            pf / "MATLAB" / "R2024a" / "bin" / "matlab.exe",
            pf / "MATLAB" / "R2023b" / "bin" / "matlab.exe",
        ],
        "autocad": [
            pf / "Autodesk" / "AutoCAD 2019" / "accoreconsole.exe",
            pf / "Autodesk" / "AutoCAD 2024" / "accoreconsole.exe",
        ],
        "fluent": [
            pf / "ANSYS Inc" / "v241" / "fluent" / "ntbin" / "win64" / "fluent.exe",
            pf / "ANSYS Inc" / "v242" / "fluent" / "ntbin" / "win64" / "fluent.exe",
        ],
        "solidworks": [
            pf / "SOLIDWORKS Corp" / "SOLIDWORKS" / "SLDWORKS.exe",
        ],
        "hwp": [
            pf / "Hnc" / "Office 2022" / "HOffice120" / "Bin" / "Hwp.exe",
            pfx86 / "Hnc" / "Office 2022" / "HOffice120" / "Bin" / "Hwp.exe",
        ],
    }


def registry_progid_exists(progid: str) -> bool:
    if platform.system().lower() != "windows":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid):
            return True
    except Exception:
        return False


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def add(checks: list[Check], section: str, item: str, status: str,
        evidence: str, next_action: str = "") -> None:
    if status not in STATUSES:
        status = "WARN"
    checks.append(Check(section, item, status, evidence, next_action))


def check_core(checks: list[Check]) -> None:
    ws = workspace_root()
    root = package_root()
    add(checks, "필수 설치", "Windows", "PASS" if platform.system() == "Windows" else "WARN",
        f"{platform.platform()}", "Windows PC에서 실행해야 실제 앱 자동화를 확인할 수 있습니다.")
    add(checks, "필수 설치", "Python 3.11", "PASS" if sys.version_info[:2] == (3, 11) else "FAIL",
        sys.version.replace("\n", " "), "Python 3.11을 설치하고 py -3.11이 잡히는지 확인하세요.")
    add(checks, "필수 설치", "workspace", "PASS" if (ws / "agent_ops").is_dir() else "FAIL",
        safe_rel(ws), "설치 패키지를 다시 설치하세요.")
    add(checks, "필수 설치", "RUN_OPENCODE_LIG.bat", "PASS" if (ws / "RUN_OPENCODE_LIG.bat").exists() else "FAIL",
        safe_rel(ws / "RUN_OPENCODE_LIG.bat"), "workspace 복사 상태를 확인하세요.")

    payloads = [
        root / "payload" / "opencode.exe",
        Path.home() / "OpenCodeLIG" / "bin" / "opencode.exe",
    ]
    found = find_existing(payloads)
    add(checks, "필수 설치", "opencode.exe payload", "PASS" if found else "FAIL",
        "; ".join(found) if found else "not found",
        "패키지 payload/opencode.exe 또는 설치된 bin/opencode.exe가 필요합니다.")
    for p in payloads:
        if p.exists():
            result = run_cmd([str(p), "--version"], timeout=10, cwd=ws)
            add(checks, "필수 설치", f"opencode 실행: {p.name}",
                "PASS" if result.get("ok") else "WARN",
                result.get("stdout") or result.get("stderr") or result.get("error", ""),
                "실행 실패 시 payload 손상 또는 보안 차단 여부를 확인하세요.")
            break

    sums = root / "SHA256SUMS.txt"
    payload = root / "payload" / "opencode.exe"
    if sums.exists() and payload.exists():
        text = sums.read_text(encoding="utf-8", errors="replace")
        actual = sha256(payload)
        add(checks, "필수 설치", "payload SHA256", "PASS" if actual in text.lower() else "FAIL",
            actual, "SHA256SUMS.txt와 payload가 같은 패키지에서 온 것인지 확인하세요.")

    path_opencode = shutil.which("opencode")
    add(checks, "필수 설치", "opencode PATH", "PASS" if path_opencode else "WARN",
        path_opencode or "PATH에는 없음",
        "일반 셸에서 opencode를 직접 칠 필요가 있으면 %USERPROFILE%\\OpenCodeLIG\\bin을 PATH에 추가하세요.")


def check_config_and_loop(checks: list[Check]) -> None:
    ws = workspace_root()
    try:
        from agent_ops.lig_providers import build_providers, load_lig_env, validate_config
        env = load_lig_env()
        cfg = validate_config()
        add(checks, "모델/설정", "게이트웨이 설정", "PASS" if cfg.get("ready") else "FAIL",
            json.dumps({k: cfg.get(k) for k in ("profile", "secret_file_found", "gateway_url_set", "api_key_set", "default_provider", "missing")}, ensure_ascii=False),
            "USERDATA\\secrets\\lig-api.env를 확인하세요.")
        providers = build_providers()
        ready_routes = [name for name, p in providers.items() if p.get("base_url") and p.get("model")]
        add(checks, "모델/설정", "provider routes", "PASS" if ready_routes else "FAIL",
            ", ".join(ready_routes), "config/lig-api.env.example 및 USERDATA secret을 확인하세요.")
        # Optional live gateway probe. Secret and host are never printed.
        ok_count = 0
        tried = 0
        for p in providers.values():
            base = str(p.get("base_url", "")).rstrip("/")
            if not base:
                continue
            tried += 1
            try:
                req = urllib.request.Request(
                    base + "/models",
                    headers={"Authorization": "Bearer " + str(env.get("LIG_API_KEY", ""))},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if 200 <= int(resp.status) < 500:
                        ok_count += 1
            except Exception:
                pass
        add(checks, "모델/설정", "게이트웨이 live probe", "PASS" if ok_count else "PENDING",
            f"reachable_routes={ok_count}, tried={tried} (URL/API key hidden)",
            "사내망에서 실행했는데 0이면 게이트웨이/프록시/키를 확인하세요.")
    except Exception as exc:  # noqa: BLE001
        add(checks, "모델/설정", "게이트웨이 설정", "FAIL", repr(exc)[:500],
            "agent_ops.lig_providers import 오류를 확인하세요.")

    opencode_json = ws / "opencode.json"
    try:
        data = json.loads(opencode_json.read_text(encoding="utf-8-sig"))
        model = str(data.get("model", ""))
        add(checks, "모델/설정", "opencode.json", "PASS" if "/" in model else "FAIL",
            f"default_model={model}", "opencode.json JSON 및 provider/model 형식을 확인하세요.")
    except Exception as exc:  # noqa: BLE001
        add(checks, "모델/설정", "opencode.json", "FAIL", repr(exc)[:500],
            "opencode.json을 복구하세요.")

    try:
        from agent_ops.intelligence_map import all_items, coverage_summary
        items = all_items()
        pending = [asdict(i) for i in items if i.status == "pending"]
        add(checks, "자동지능 루프", "intelligence map", "PASS",
            f"items={len(items)}, pending={len(pending)}, summary={json.dumps(coverage_summary(), ensure_ascii=False, sort_keys=True)}")
    except Exception as exc:  # noqa: BLE001
        add(checks, "자동지능 루프", "intelligence map", "FAIL", repr(exc)[:500],
            "agent_ops.intelligence_map 오류를 확인하세요.")

    with tempfile.TemporaryDirectory(prefix="agentops_pending_") as td:
        env = dict(os.environ)
        env.update({
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "AGENTOPS_ROOT": str(Path(td) / "workspace"),
            "AGENTOPS_MEMORY_DIR": str(Path(td) / "memory"),
            "LIG_DIAG_DIR": str(Path(td) / "diag"),
        })
        cmd = [sys.executable, str(ws / "agent_ops" / "agentops.py"), "auto",
               "--task", "크롬으로 회사 포털 확인해줘", "--dry-run"]
        try:
            cp = subprocess.run(cmd, cwd=str(ws), env=env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=30)
            trace = Path(td) / "diag" / "auto-route-last.json"
            trace_data = json.loads(trace.read_text(encoding="utf-8")) if trace.exists() else {}
            has_fields = all(k in trace_data for k in ("capability_ids", "policy", "route_hints", "evaluation", "memory_hooks"))
            add(checks, "자동지능 루프", "/auto trace dry-run",
                "PASS" if cp.returncode == 0 and has_fields else "FAIL",
                f"returncode={cp.returncode}, fields={sorted(trace_data.keys())}",
                "trace에 capability/policy/tools/evaluation/memory hook 필드가 모두 있어야 합니다.")
        except Exception as exc:  # noqa: BLE001
            add(checks, "자동지능 루프", "/auto trace dry-run", "FAIL", repr(exc)[:500],
                "agentops.py auto 실행 경로를 확인하세요.")


def check_optional_modules(checks: list[Check]) -> None:
    modules = {
        "openpyxl": "xlsx 생성/읽기",
        "docx": "Word docx 생성",
        "pptx": "PowerPoint pptx 생성",
        "markitdown": "PDF/Office 문서 읽기",
        "rapidocr_onnxruntime": "OCR",
        "onnxruntime": "OCR backend",
        "win32com": "Office/HWP/Outlook/SolidWorks COM",
        "mss": "화면 캡처",
        "PIL": "이미지 처리",
        "windows_use": "Desktop UI 자동화",
    }
    for mod, purpose in modules.items():
        add(checks, "오프라인 의존성", mod, "PASS" if has_module(mod) else "PENDING",
            purpose, f"필요하면 workspace\\launch\\install-tools.bat 또는 wheelhouse로 오프라인 설치하세요.")
    wh = workspace_root() / "tools" / "wheelhouse"
    wheels = list(wh.glob("*.whl")) if wh.exists() else []
    add(checks, "오프라인 의존성", "wheelhouse", "PASS" if wheels else "WARN",
        f"{len(wheels)} wheel(s) at {wh}", "오프라인 추가 설치가 필요하면 wheelhouse를 채우세요.")


def check_apps_and_pending(checks: list[Check]) -> None:
    paths = common_program_paths()
    env_paths = {
        "matlab": os.environ.get("MATLAB_EXE", ""),
        "autocad": os.environ.get("ACCORECONSOLE_EXE", ""),
        "fluent": os.environ.get("FLUENT_EXE", ""),
    }
    env_names = {
        "matlab": "MATLAB_EXE",
        "autocad": "ACCORECONSOLE_EXE",
        "fluent": "FLUENT_EXE",
    }
    for key, env_path in env_paths.items():
        candidates = ([Path(env_path)] if env_path else []) + paths.get(key, [])
        found = find_existing(candidates)
        add(checks, "앱/도구 pending", f"{key} executable", "PASS" if found else "PENDING",
            "; ".join(found) if found else "not found",
            f"{env_names[key]} 환경변수 또는 표준 설치 경로를 확인하세요.")

    chrome_found = find_existing(paths["chrome"]) or ([shutil.which("chrome")] if shutil.which("chrome") else [])
    add(checks, "앱/도구 pending", "Chrome", "PASS" if chrome_found else "PENDING",
        "; ".join(str(x) for x in chrome_found) if chrome_found else "not found",
        "Chrome 설치 및 launch\\chrome-debug.bat 실행 여부를 확인하세요.")
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2) as resp:
            cdp_ok = 200 <= int(resp.status) < 500
    except Exception:
        cdp_ok = False
    add(checks, "앱/도구 pending", "Chrome CDP 9222", "PASS" if cdp_ok else "PENDING",
        "reachable" if cdp_ok else "not reachable",
        "브라우저 자동화 검증 전 launch\\chrome-debug.bat로 디버그 크롬을 여세요.")

    obsidian_found = find_existing(paths["obsidian"]) or ([shutil.which("obsidian")] if shutil.which("obsidian") else [])
    wiki_dir = Path.home() / "OpenCodeLIG_USERDATA" / "memory" / "wiki"
    add(checks, "Obsidian/위키", "Obsidian", "PASS" if obsidian_found else "PENDING",
        "; ".join(str(x) for x in obsidian_found) if obsidian_found else "not found",
        "Obsidian을 설치하고 USERDATA\\memory\\wiki를 vault로 열 수 있게 준비하세요.")
    add(checks, "Obsidian/위키", "wiki vault directory", "PASS" if wiki_dir.exists() else "WARN",
        str(wiki_dir), "첫 기억/위키 실행 후 자동 생성됩니다.")

    progids = {
        "Excel COM": "Excel.Application",
        "Word COM": "Word.Application",
        "PowerPoint COM": "PowerPoint.Application",
        "Outlook COM": "Outlook.Application",
        "HWP COM": "HWPFrame.HwpObject",
        "SolidWorks COM": "SldWorks.Application",
    }
    for label, progid in progids.items():
        add(checks, "앱/도구 pending", label, "PASS" if registry_progid_exists(progid) else "PENDING",
            f"ProgID={progid}", f"{label} 등록/설치 상태를 확인하세요.")

    try:
        from agent_ops.adapters import ADAPTERS
        for adapter_id, spec in ADAPTERS.items():
            pending = str(spec.get("pending", "") or "")
            available = bool(spec.get("available"))
            validated = str(spec.get("validated", "") or "")
            if pending:
                status = "WARN" if available else "PENDING"
                evidence = f"available={available}, validated={'yes' if validated else 'no'}, pending={pending}"
                add(checks, "앱/도구 pending", f"adapter:{adapter_id}", status, evidence,
                    "위 항목의 실행파일/COM/의존성 결과와 함께 판단하세요.")
    except Exception as exc:  # noqa: BLE001
        add(checks, "앱/도구 pending", "adapter inventory", "FAIL", repr(exc)[:500],
            "agent_ops.adapters import 오류를 확인하세요.")


def check_docs_package(checks: list[Check]) -> None:
    ws = workspace_root()
    required_docs = [
        ws / "docs" / "사용법" / "GUIDE.md",
        ws / "docs" / "사용법" / "RUNBOOK.md",
        ws / "docs" / "운영" / "INTELLIGENCE_COVERAGE_REPORT.md",
    ]
    for p in required_docs:
        add(checks, "문서/패키지", p.name, "PASS" if p.exists() else "FAIL",
            safe_rel(p), "사용자용 패키지에 문서가 포함되어야 합니다.")
    tests_dir = ws / "tests"
    add(checks, "문서/패키지", "사용자 패키지 테스트폴더", "WARN" if tests_dir.exists() else "PASS",
        f"tests_dir_exists={tests_dir.exists()}",
        "배포 패키지에서는 tests 폴더가 제외되는 것이 정상입니다.")
    add(checks, "문서/패키지", "점검 BAT", "PASS" if (ws / "점검용_전체확인.bat").exists() else "WARN",
        safe_rel(ws / "점검용_전체확인.bat"), "패키지 루트와 설치 workspace에 점검 BAT가 있어야 합니다.")


def build_report(checks: list[Check], report_id: str) -> tuple[dict[str, Any], str]:
    counts = {s: sum(1 for c in checks if c.status == s) for s in STATUSES}
    blocking = [c for c in checks if c.status == "FAIL"]
    pending = [c for c in checks if c.status in {"PENDING", "WARN"}]
    payload = {
        "report_id": report_id,
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace": str(workspace_root()),
        "counts": counts,
        "blocking_failures": [asdict(c) for c in blocking],
        "pending_or_warning": [asdict(c) for c in pending],
        "checks": [asdict(c) for c in checks],
    }
    lines = [
        f"# OpenCodeLIG pending validation report",
        "",
        f"- report_id: `{report_id}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- workspace: `{payload['workspace']}`",
        f"- summary: PASS {counts['PASS']} / WARN {counts['WARN']} / PENDING {counts['PENDING']} / FAIL {counts['FAIL']} / SKIP {counts['SKIP']}",
        "",
        "## 판정 기준",
        "",
        "- FAIL: 필수 설치/핵심 자동 루프가 깨진 항목입니다. 먼저 해결해야 합니다.",
        "- PENDING: 사내 앱, COM, 브라우저, OCR, Fluent 등 현장 검증이 필요한 항목입니다.",
        "- WARN: 동작은 가능하지만 직접 실행 경로, 문서, 선택 기능 확인이 남은 항목입니다.",
        "- PASS: 현재 PC에서 확인된 항목입니다.",
        "",
    ]
    for section in sorted({c.section for c in checks}):
        lines += [f"## {section}", "", "| status | item | evidence | next action |",
                  "|---|---|---|---|"]
        for c in [x for x in checks if x.section == section]:
            ev = c.evidence.replace("|", "/").replace("\n", " ")[:300]
            nxt = c.next_action.replace("|", "/").replace("\n", " ")[:240]
            lines.append(f"| {c.status} | {c.item} | {ev} | {nxt} |")
        lines.append("")
    return payload, "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else diagnostics_dir() / "pending_checks"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_id = "pending_check_" + now_stamp()

    checks: list[Check] = []
    check_core(checks)
    check_config_and_loop(checks)
    check_optional_modules(checks)
    check_apps_and_pending(checks)
    check_docs_package(checks)

    payload, markdown = build_report(checks, report_id)
    json_path = out_dir / f"{report_id}.json"
    md_path = out_dir / f"{report_id}.md"
    last_json = out_dir / "pending-check-last.json"
    last_md = out_dir / "pending-check-last.md"
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    last_json.write_text(json_text, encoding="utf-8")
    last_md.write_text(markdown, encoding="utf-8")

    print(markdown)
    print("")
    print(f"[REPORT_JSON] {json_path}")
    print(f"[REPORT_MD]   {md_path}")
    return 1 if payload["counts"]["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
