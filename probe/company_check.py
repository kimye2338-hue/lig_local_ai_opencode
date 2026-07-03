# -*- coding: utf-8 -*-
"""OpenCodeLIG 회사 PC 종합 계측기 — 파일 하나, 실행 한 번, 보고서 하나.

목적: 다음 회사 방문에서 남은 미지수를 한 번에 측정한다. 반입물은 이 .py 하나뿐.

실행 (택1):
  py -3.11 company_check.py           (더블클릭도 가능 — 끝에 대기)
  py -3.11 company_check.py --quick   (앱/COM/MATLAB 무거운 검사 생략, gateway+환경만)

산출물 (실행 폴더에 생성):
  company_check_result.json   기계 판독용 전체
  company_check_result.md     사람 판독용 요약  ← 이거 열어서 내용 복사해 전달하면 됨

안전:
  - stdlib만 사용. 외부 패키지 불필요 (pywin32는 있으면 COM 검사, 없으면 스킵).
  - gateway host / API key / Windows 사용자명 / 컴퓨터명을 자동 마스킹.
    파일로 쓰기 직전 전체 텍스트를 재검사해 secret 잔존 시 그 필드를 지운다.
  - COM/앱/브라우저/MATLAB 등 멈출 수 있는 검사는 자기 자신을 하위 프로세스로
    격리 실행하고 타임아웃으로 회수한다 (본체는 절대 hang되지 않는다).
  - 원본 파일을 건드리지 않는다. Excel 검사는 임시 폴더의 새 파일에서만.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

TIMEOUT_GATEWAY = 30
TIMEOUT_COM = 40
TIMEOUT_MATLAB = 150
TIMEOUT_CHROME = 40
TIMEOUT_OPENCODE = 100

# ---------------------------------------------------------------- 마스킹 ---

def _secret_values() -> list:
    """마스킹 대상 실제 문자열 수집 (출력 전 제거용)."""
    vals = []
    env = _load_env()
    key = env.get("LIG_API_KEY", "")
    if key and "REPLACE" not in key:
        vals.append(key)
    gw = env.get("LIG_GATEWAY_BASE_URL", "")
    if gw:
        try:
            from urllib.parse import urlparse
            net = urlparse(gw).netloc
            if net:
                vals.append(net)
                vals.append(net.split(":")[0])  # host without port
        except Exception:
            pass
    for extra in (os.environ.get("USERNAME", ""), socket.gethostname()):
        if extra and len(extra) >= 3:
            vals.append(extra)
    return [v for v in vals if v]


def _mask(text: str, secrets: list) -> str:
    out = str(text or "")
    for s in secrets:
        if s and len(s) >= 3:
            out = out.replace(s, "<MASKED>")
    return out


def _mask_path(p: str) -> str:
    home = str(Path.home())
    return str(p or "").replace(home, "%USERPROFILE%")


# ------------------------------------------------------------- env 로더 ---

def _load_env() -> dict:
    path = Path(os.environ.get("LIG_API_ENV_FILE")
                or (Path.home() / "OpenCodeLIG_USERDATA" / "secrets" / "lig-api.env"))
    values = {}
    if not path.exists():
        return values
    try:
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return values


# ---------------------------------------------------- 격리 실행 헬퍼 ---

def _isolated(name: str, timeout: int) -> dict:
    """위험 검사를 하위 프로세스로 격리 실행하고 타임아웃으로 회수."""
    child_env = dict(os.environ)
    child_env["PYTHONUTF8"] = "1"            # 자식 stdout을 UTF-8로 (한글 깨짐 방지)
    child_env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--run", name],
                           capture_output=True, timeout=timeout, text=True,
                           encoding="utf-8", errors="replace", env=child_env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": f"timeout(>{timeout}s) — 이 검사가 멈춤/대기 상태"}
    except Exception as exc:
        return {"ok": False, "status": f"실행 실패: {type(exc).__name__}"}
    out = r.stdout or ""
    m = re.search(r"<<<RESULT>>>(.*?)<<<END>>>", out, re.S)
    if not m:
        return {"ok": False, "status": "결과 파싱 실패",
                "stderr_tail": (r.stderr or "")[-300:]}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {"ok": False, "status": "결과 JSON 오류"}


def _emit(payload: dict) -> None:
    # UTF-8 바이트로 직접 써서 콘솔 코드페이지(cp949)와 무관하게 한글 보존.
    data = ("<<<RESULT>>>" + json.dumps(payload, ensure_ascii=False) + "<<<END>>>")
    try:
        sys.stdout.buffer.write(data.encode("utf-8"))
        sys.stdout.buffer.flush()
    except Exception:
        sys.stdout.write(data)


# =================================================================
#  개별 검사 (하위 프로세스에서 --run <name> 으로 호출됨)
# =================================================================

def probe_gateway() -> dict:
    import urllib.error
    import urllib.request
    env = _load_env()
    root = env.get("LIG_GATEWAY_BASE_URL", "").rstrip("/")
    key = env.get("LIG_API_KEY", "")
    if not root or "REPLACE" in root:
        return {"ok": False, "status": "lig-api.env 미설정 — gateway 검사 생략"}
    routes = [
        ("coding", env.get("LIG_ROUTE_CODING", "/gateway/EXAONE-4.5-33B-vibe_coding_think_off/v1"), "EXAONE-4.5-33B"),
        ("chat", env.get("LIG_ROUTE_CHAT", "/gateway/EXAONE-4.5-33B-default_think_off/v1"), "EXAONE-4.5-33B"),
        ("fallback", env.get("LIG_ROUTE_FALLBACK", "/gateway/Qwen3.6-27B-vibe_coding_think_off/v1"), "Qwen3.6-27B"),
    ]

    def call(url, payload, timeout=25, stream=False):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(4000).decode("utf-8", errors="replace")
        return int((time.time() - t0) * 1000), body

    result = {"ok": True, "routes": {}}
    base_coding = root + routes[0][1]
    # 1) 3라우트 기본 응답
    for name, route, model in routes:
        url = root + route + "/chat/completions"
        entry = {}
        try:
            ms, body = call(url, {"model": model, "max_tokens": 16,
                                  "messages": [{"role": "user", "content": "1+1은? 숫자만."}]})
            entry = {"status": 200, "latency_ms": ms, "sample": body[:200]}
        except urllib.error.HTTPError as e:
            entry = {"status": e.code, "sample": e.read(200).decode("utf-8", "replace")}
        except Exception as e:
            entry = {"status": "error", "error": type(e).__name__}
        result["routes"][name] = entry
    # 2) function calling (tools) 지원 여부 — 최대 관심사
    try:
        tools = [{"type": "function", "function": {
            "name": "read_file", "description": "파일을 읽는다",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                           "required": ["path"]}}}]
        ms, body = call(base_coding + "/chat/completions", {
            "model": "EXAONE-4.5-33B", "max_tokens": 128, "tools": tools,
            "messages": [{"role": "user", "content": "메모.txt 파일을 읽어줘"}]})
        parsed = json.loads(body)
        msg = (parsed.get("choices") or [{}])[0].get("message", {})
        result["function_calling"] = {
            "accepted": True,
            "tool_calls_present": bool(msg.get("tool_calls")),
            "finish_reason": (parsed.get("choices") or [{}])[0].get("finish_reason"),
            "sample": body[:400]}
    except urllib.error.HTTPError as e:
        result["function_calling"] = {"accepted": False, "status": e.code,
                                      "sample": e.read(300).decode("utf-8", "replace")}
    except Exception as e:
        result["function_calling"] = {"accepted": False, "error": type(e).__name__}
    # 3) 프롬프트 기반 tool-call 원문 (파서 보강 근거)
    try:
        prompt = ('다음 JSON 형식으로만 답하라: {"tool":"read_file","args":{"path":"<파일>"}}\n'
                  "작업: 메모.txt 파일을 읽어라.")
        ms, body = call(base_coding + "/chat/completions", {
            "model": "EXAONE-4.5-33B", "max_tokens": 128,
            "messages": [{"role": "user", "content": prompt}]})
        content = json.loads(body).get("choices", [{}])[0].get("message", {}).get("content", "")
        result["text_toolcall_raw"] = content[:400]
    except Exception as e:
        result["text_toolcall_raw"] = f"(수집 실패: {type(e).__name__})"
    # 4) 스트리밍 지원 여부
    try:
        req = urllib.request.Request(base_coding + "/chat/completions",
            data=json.dumps({"model": "EXAONE-4.5-33B", "max_tokens": 16, "stream": True,
                             "messages": [{"role": "user", "content": "안녕"}]}).encode(),
            method="POST", headers={"Content-Type": "application/json",
                                    "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            first = resp.read(120).decode("utf-8", errors="replace")
        result["streaming"] = {"supported": first.startswith("data:") or "data:" in first,
                               "first_bytes": first[:80]}
    except Exception as e:
        result["streaming"] = {"supported": False, "error": type(e).__name__}
    # 5) 장문 응답 지연 (실사용 체감 — 512토큰)
    try:
        ms, body = call(base_coding + "/chat/completions", {
            "model": "EXAONE-4.5-33B", "max_tokens": 512,
            "messages": [{"role": "user", "content": "기계 연구원의 하루 업무를 10문장으로 설명해줘."}]},
            timeout=60)
        result["long_latency"] = {"max_tokens": 512, "latency_ms": ms}
    except Exception as e:
        result["long_latency"] = {"error": type(e).__name__}
    # 6) /models 목록 (실제 모델 ID 확인)
    try:
        req = urllib.request.Request(base_coding + "/models",
            headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            result["models_endpoint"] = {"status": 200,
                                         "sample": resp.read(500).decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        result["models_endpoint"] = {"status": e.code}
    except Exception as e:
        result["models_endpoint"] = {"error": type(e).__name__}
    # 7) think_on 라우트 존재 여부 (있으면 reasoning 분리 가능)
    think_route = routes[1][1].replace("think_off", "think_on")
    try:
        ms, body = call(root + think_route + "/chat/completions", {
            "model": "EXAONE-4.5-33B", "max_tokens": 16,
            "messages": [{"role": "user", "content": "1+1"}]})
        result["think_on_route"] = {"exists": True, "status": 200}
    except urllib.error.HTTPError as e:
        result["think_on_route"] = {"exists": e.code != 404, "status": e.code}
    except Exception as e:
        result["think_on_route"] = {"exists": "unknown", "error": type(e).__name__}
    return result


def probe_excel_com() -> dict:
    """Excel 실왕복 + VBProject 접근(AccessVBOM 실동작). 임시 새 파일만 사용."""
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
    except ImportError:
        return {"ok": False, "status": "pywin32 없음 — COM 검사 생략"}
    tmp = Path(os.environ.get("TEMP", ".")) / f"occ_xl_{os.getpid()}.xlsx"
    xl = None
    info = {"ok": True}
    try:
        pythoncom.CoInitialize()
        xl = win32com.client.DispatchEx("Excel.Application")
        xl.Visible = False
        xl.DisplayAlerts = False
        info["excel_version"] = str(xl.Version)
        wb = xl.Workbooks.Add()
        ws = wb.Worksheets(1)
        ws.Range("A1").Value = "계측"
        ws.Range("A2").Value = 2026
        rt = ws.Range("A1").Value
        info["cell_roundtrip_ok"] = (rt == "계측")
        wb.SaveAs(str(tmp))
        info["saveas_ok"] = tmp.exists()
        # VBProject 접근 — AccessVBOM=1 실동작 확인 (매크로 자동 주입 가능 여부의 핵심)
        try:
            _ = wb.VBProject.VBComponents.Count
            info["vbproject_access"] = "가능 (매크로 자동 주입 OK)"
        except Exception as e:
            info["vbproject_access"] = f"차단 ({type(e).__name__}) — 수동 import 필요"
        wb.Close(SaveChanges=False)
    except Exception as e:
        info = {"ok": False, "status": f"Excel COM 실패: {type(e).__name__}: {e}"}
    finally:
        try:
            if xl:
                xl.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
    return info


def _com_connect(progid: str, label: str) -> dict:
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
    except ImportError:
        return {"ok": False, "status": "pywin32 없음"}
    obj = None
    try:
        pythoncom.CoInitialize()
        obj = win32com.client.DispatchEx(progid)
        ver = ""
        for attr in ("Version", "Application"):
            try:
                ver = str(getattr(obj, attr, ""))[:40]
                if ver:
                    break
            except Exception:
                pass
        return {"ok": True, "status": f"{label} COM 접속 성공", "version_hint": ver}
    except Exception as e:
        return {"ok": False, "status": f"{label} COM 실패: {type(e).__name__}"}
    finally:
        for fn in (lambda: obj.Quit() if obj else None,):
            try:
                fn()
            except Exception:
                pass
        try:
            import pythoncom  # type: ignore
            pythoncom.CoUninitialize()
        except Exception:
            pass


def probe_outlook_com() -> dict:
    return _com_connect("Outlook.Application", "Outlook")


def probe_hwp_com() -> dict:
    return _com_connect("HWPFrame.HwpObject", "한글(HWP)")


def probe_solidworks_com() -> dict:
    return _com_connect("SldWorks.Application", "SolidWorks")


def probe_matlab() -> dict:
    """matlab -batch 실실행 (라이선스/기동 포함 실체감 시간)."""
    exe = ""
    import glob
    hits = sorted(glob.glob(r"C:\Program Files\MATLAB\R20*\bin\matlab.exe"))
    if hits:
        exe = hits[-1]
    exe = os.environ.get("MATLAB_EXE", exe)
    if not exe or not Path(exe).exists():
        return {"ok": False, "status": "matlab.exe 미발견"}
    t0 = time.time()
    try:
        r = subprocess.run([exe, "-batch", "disp(1+1)"], capture_output=True,
                           timeout=TIMEOUT_MATLAB - 10, text=True, encoding="utf-8", errors="replace")
        secs = round(time.time() - t0, 1)
        out = (r.stdout or "") + (r.stderr or "")
        return {"ok": r.returncode == 0 and "2" in out, "exit": r.returncode,
                "seconds": secs, "output_tail": out.strip()[-120:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": f"timeout(>{TIMEOUT_MATLAB-10}s) — 라이선스 대기 등"}
    except Exception as e:
        return {"ok": False, "status": f"실행 실패: {type(e).__name__}"}


def probe_chrome_cdp() -> dict:
    """Chrome을 별도 프로필/headless로 띄워 CDP endpoint 응답 확인."""
    import glob
    import urllib.request
    exe = ""
    for pat in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]:
        if Path(pat).exists():
            exe = pat
            break
    if not exe:
        return {"ok": False, "status": "chrome.exe 미발견"}
    port = 9245  # 사용자 기본 디버그 포트와 충돌 회피
    prof = Path(os.environ.get("TEMP", ".")) / f"occ_chrome_{os.getpid()}"
    proc = None
    try:
        proc = subprocess.Popen(
            [exe, f"--remote-debugging-port={port}", f"--user-data-dir={prof}",
             "--headless=new", "--no-first-run", "--no-default-browser-check",
             "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        version = None
        for _ in range(20):  # 최대 ~10초 대기
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as r:
                    version = json.loads(r.read(1000).decode("utf-8", "replace"))
                    break
            except Exception:
                continue
        if version:
            return {"ok": True, "status": "CDP endpoint 응답 OK",
                    "browser": version.get("Browser", "")[:40]}
        return {"ok": False, "status": "CDP endpoint 무응답 (기동 실패/차단)"}
    except Exception as e:
        return {"ok": False, "status": f"실행 실패: {type(e).__name__}"}
    finally:
        try:
            if proc:
                proc.terminate()
        except Exception:
            pass
        try:
            shutil.rmtree(prof, ignore_errors=True)
        except Exception:
            pass


def probe_opencode_startup() -> dict:
    """OpenCode --version cold/warm 시간 + 구버전 잔재 + proxy env."""
    exe = shutil.which("opencode") or ""
    if not exe:
        cand = Path.home() / "OpenCodeLIG" / "bin" / "opencode.exe"
        if cand.exists():
            exe = str(cand)
    info = {"exe_found": bool(exe), "exe": _mask_path(exe)}
    if exe:
        timings = []
        for label in ("cold", "warm"):
            t0 = time.time()
            try:
                subprocess.run([exe, "--version"], capture_output=True,
                               timeout=TIMEOUT_OPENCODE - 10)
                timings.append({label: round(time.time() - t0, 1)})
            except subprocess.TimeoutExpired:
                timings.append({label: f"timeout(>{TIMEOUT_OPENCODE-10}s)"})
                break
            except Exception as e:
                timings.append({label: f"error:{type(e).__name__}"})
                break
        info["version_seconds"] = timings
    # 구버전 잔재
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            info["legacy_proxy_8765"] = "리스닝 중 (구버전 proxy 잔류)"
    except Exception:
        info["legacy_proxy_8765"] = "없음"
    ws = Path.home() / "OpenCodeLIG" / "workspace"
    info["build_marker"] = {
        "capabilities_py(신버전)": (ws / "agent_ops" / "capabilities.py").exists() if ws.exists() else False,
        "legacy_lig_diag": bool(list(ws.glob("**/lig_diag*.py"))) if ws.exists() else False,
        "opencode_json_autoupdate": (
            "autoupdate" in (ws / "opencode.json").read_text(encoding="utf-8", errors="replace")
            if (ws / "opencode.json").exists() else False),
    }
    info["proxy_env"] = {k: bool(os.environ.get(k)) for k in
                         ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")}
    info["opencode_env"] = {k: bool(os.environ.get(k)) for k in
                            ("OPENCODE_PURE", "OPENCODE_DISABLE_DEFAULT_PLUGINS",
                             "NO_UPDATE_NOTIFIER")}
    return info


ISOLATED = {
    "gateway": (probe_gateway, TIMEOUT_GATEWAY),
    "excel": (probe_excel_com, TIMEOUT_COM),
    "outlook": (probe_outlook_com, TIMEOUT_COM),
    "hwp": (probe_hwp_com, TIMEOUT_COM),
    "solidworks": (probe_solidworks_com, TIMEOUT_COM),
    "matlab": (probe_matlab, TIMEOUT_MATLAB),
    "chrome": (probe_chrome_cdp, TIMEOUT_CHROME),
    "opencode": (probe_opencode_startup, TIMEOUT_OPENCODE),
}


# ------------------------------------------------ 인프로세스(빠르고 안전) ---

def collect_environment() -> dict:
    import ctypes

    def ram_gb():
        try:
            class M(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            ("tot", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong),
                            ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tv", ctypes.c_ulonglong), ("avv", ctypes.c_ulonglong),
                            ("ae", ctypes.c_ulonglong)]
            s = M(); s.l = ctypes.sizeof(s)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            return round(s.tot / (1024**3), 1)
        except Exception:
            return -1

    try:
        import win32com  # noqa: F401
        pywin32 = True
    except ImportError:
        pywin32 = False
    return {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "ram_gb": ram_gb(),
        "disk_free_gb": round(shutil.disk_usage(Path.home()).free / (1024**3), 1),
        "pywin32": pywin32,
        "gateway_config": {k: (k in _load_env() and "REPLACE" not in _load_env().get(k, ""))
                           for k in ("LIG_GATEWAY_BASE_URL", "LIG_API_KEY")},
        "route_prefix_ok": _load_env().get("LIG_ROUTE_CHAT", "/gateway/").startswith("/gateway/")
                           if _load_env().get("LIG_ROUTE_CHAT") else "기본값 사용(/gateway/ 포함)",
    }


def collect_apps() -> dict:
    import glob
    try:
        import winreg
    except ImportError:
        return {"error": "winreg 없음"}

    def progid(pid):
        try:
            winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, pid).Close()
            return True
        except OSError:
            return False

    def first(paths):
        for p in paths:
            hits = sorted(glob.glob(p))
            if hits:
                return _mask_path(hits[-1])
        return ""

    apps = {p: progid(f"{p.title()}.Application" if p != "hwp" else "HWPFrame.HwpObject")
            for p in ("excel", "word", "powerpoint", "outlook")}
    apps["hwp"] = progid("HWPFrame.HwpObject")
    apps["solidworks"] = progid("SldWorks.Application")
    apps["matlab"] = first([r"C:\Program Files\MATLAB\R20*\bin\matlab.exe"])
    apps["accoreconsole"] = first([r"C:\AutoCAD*\accoreconsole.exe",
                                   r"C:\Program Files\Autodesk\AutoCAD*\accoreconsole.exe"])
    apps["acad"] = first([r"C:\AutoCAD*\acad.exe",
                          r"C:\Program Files\Autodesk\AutoCAD*\acad.exe"])
    apps["fluent"] = first([r"C:\Program Files\ANSYS Inc\v*\fluent\ntbin\win64\fluent.exe"])
    apps["chrome"] = first([r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"])
    return apps


def collect_office_security() -> dict:
    try:
        import winreg
    except ImportError:
        return {}
    out = {}
    for app in ("Excel", "Word", "PowerPoint", "Outlook"):
        rec = {"AccessVBOM": "키 없음", "VBAWarnings": "키 없음", "policy_lock": False}
        for ver in ("16.0", "15.0"):
            base = rf"Software\Microsoft\Office\{ver}\{app}\Security"
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as k:
                    for field in ("AccessVBOM", "VBAWarnings"):
                        try:
                            rec[field] = str(winreg.QueryValueEx(k, field)[0])
                        except OSError:
                            pass
                    break
            except OSError:
                continue
        pol = rf"Software\Policies\Microsoft\Office\16.0\{app}\Security"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, pol) as k:
                winreg.QueryValueEx(k, "VBAWarnings")
                rec["policy_lock"] = True
        except OSError:
            pass
        out[app.lower()] = rec
    return out


# ------------------------------------------------------------- 보고서 ---

def _md(report: dict) -> str:
    L = ["# OpenCodeLIG 회사 PC 계측 보고서", "",
         f"- 생성: {report['timestamp']}",
         f"- OS: {report['environment']['os']} / Python {report['environment']['python']}"
         f" / RAM {report['environment']['ram_gb']}GB / pywin32 {report['environment']['pywin32']}",
         ""]
    g = report.get("gateway", {})
    L += ["## 1. Gateway (LLM) — 최우선", ""]
    if g.get("ok"):
        for name, r in g.get("routes", {}).items():
            L.append(f"- {name}: status {r.get('status')} / {r.get('latency_ms','-')}ms")
        fc = g.get("function_calling", {})
        L.append(f"- **function calling**: accepted={fc.get('accepted')}, "
                 f"tool_calls_present={fc.get('tool_calls_present')} "
                 f"(True면 native tools 경로 사용 가능)")
        L.append(f"- streaming: {g.get('streaming', {}).get('supported')}")
        ll = g.get("long_latency", {})
        L.append(f"- 512토큰 지연: {ll.get('latency_ms','-')}ms")
        L.append(f"- think_on 라우트: {g.get('think_on_route', {}).get('exists')}")
        L.append(f"- /models: status {g.get('models_endpoint', {}).get('status','-')}")
        L.append("")
        L.append("프롬프트 기반 tool-call 원문 (파서 보강 근거):")
        L.append("```")
        L.append(str(g.get("text_toolcall_raw", ""))[:400])
        L.append("```")
    else:
        L.append(f"- {g.get('status', '검사 안 됨')}")
    L.append("")
    L += ["## 2. 앱/COM 실동작", ""]
    for key, label in [("excel", "Excel 실왕복+VBProject"), ("outlook", "Outlook"),
                       ("hwp", "한글"), ("solidworks", "SolidWorks"),
                       ("matlab", "MATLAB -batch"), ("chrome", "Chrome CDP")]:
        if key not in report.get("live", {}):
            L.append(f"- {label}: 검사 안 함 (--quick 모드)")
            continue
        r = report["live"][key]
        extra = ""
        if key == "excel" and r.get("ok"):
            extra = f" / VBProject: {r.get('vbproject_access')}"
        if key == "matlab" and r.get("seconds"):
            extra = f" / {r.get('seconds')}s"
        L.append(f"- {label}: {'OK' if r.get('ok') else '실패/스킵'} — {r.get('status', r.get('vbproject_access',''))}{extra}")
    L.append("")
    L += ["## 3. OpenCode 기동 / 구버전 잔재", ""]
    oc = report.get("live", {}).get("opencode", {})
    L.append(f"- exe 발견: {oc.get('exe_found')}")
    L.append(f"- --version 시간: {oc.get('version_seconds')}")
    L.append(f"- 구버전 proxy(8765): {oc.get('legacy_proxy_8765')}")
    L.append(f"- build marker: {oc.get('build_marker')}")
    L.append(f"- opencode env(PURE/플러그인차단/업데이트): {oc.get('opencode_env')}")
    L.append("")
    L += ["## 4. Office 매크로 보안 정책", ""]
    for app, rec in report.get("office_security", {}).items():
        L.append(f"- {app}: {json.dumps(rec, ensure_ascii=False)}")
    L += ["", "## 5. 앱 설치/경로", ""]
    for k, v in report.get("apps", {}).items():
        L.append(f"- {k}: {v}")
    L += ["", "> 이 파일(.md)과 .json을 그대로 전달하면 됩니다. host/key/사용자명은 마스킹됨."]
    return "\n".join(L)


def main() -> int:
    quick = "--quick" in sys.argv
    print("OpenCodeLIG 계측 시작 — 잠시 걸립니다 (앱/gateway 실검사 포함)...\n")
    report = {
        "tool": "company_check", "version": 1,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "environment": collect_environment(),
        "apps": collect_apps(),
        "office_security": collect_office_security(),
        "gateway": {}, "live": {},
    }
    order = ["gateway", "opencode"]
    if not quick:
        order += ["excel", "outlook", "hwp", "solidworks", "chrome", "matlab"]
    for name in order:
        fn, timeout = ISOLATED[name]
        print(f"  [{name}] 검사 중 (최대 {timeout}s)...", flush=True)
        res = _isolated(name, timeout)
        if name == "gateway":
            report["gateway"] = res
        else:
            report["live"][name] = res
    secrets = _secret_values()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    text = _mask(text, secrets)
    # 최종 안전망: secret 잔존 시 통째로 대체
    for s in secrets:
        if s and len(s) >= 3 and s in text:
            text = text.replace(s, "<MASKED>")
    report = json.loads(text)
    out_json = Path.cwd() / "company_check_result.json"
    out_md = Path.cwd() / "company_check_result.md"
    out_json.write_text(text, encoding="utf-8")
    out_md.write_text(_mask(_md(report), secrets), encoding="utf-8")
    print(f"\n완료. 아래 두 파일을 전달해 주세요 (host/key/사용자명 마스킹됨):")
    print(f"  {out_json}")
    print(f"  {out_md}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--run":
        name = sys.argv[2]
        fn = ISOLATED.get(name, (lambda: {"ok": False, "status": "unknown probe"},))[0]
        try:
            _emit(fn())
        except Exception as exc:
            _emit({"ok": False, "status": f"probe 예외: {type(exc).__name__}: {exc}"})
        sys.exit(0)
    rc = main()
    if sys.stdout.isatty() or os.environ.get("PROMPT"):
        try:
            input("\n[Enter] 키를 누르면 닫힙니다...")
        except Exception:
            pass
    sys.exit(rc)
