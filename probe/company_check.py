# -*- coding: utf-8 -*-
"""OpenCodeLIG 회사 PC 종합 계측기 — 파일 하나, 실행 한 번, 보고서 하나(.md).

목적: 회사(내부망) 환경이 현재 빌드가 요구하는 것을 지원하는지 한 번에 측정한다.
반입물은 이 .py 하나뿐 (회사에 이미 있는 것 — Python 3.11 / pywin32 / 각종 앱 — 은 재활용).

무엇을 점검하나 (지금 기준):
  0. 현재 빌드(agent_ops) 런타임 — 이 스크립트 옆(또는 번들 workspace-template 안)에
     agent_ops가 있으면 doctor + mock work E2E + (lig-api.env 있으면) real agent E2E를
     자동 실행. 없으면 '환경만 점검'이라 정직 표기.
  1. Gateway(LLM) — 3라우트/function calling/streaming/지연/모델ID (현 _ROUTE_DEFAULTS와 동일)
  2. 앱/COM 실동작, 3. OpenCode 기동, 4. Office 매크로 정책, 5. 앱 경로, 6. 업무 시나리오 6종

실행 (택1):
  py -3.11 company_check.py           (더블클릭도 가능 — 끝에 대기)
  py -3.11 company_check.py --quick   (앱/COM/MATLAB 무거운 검사 생략, 런타임+gateway+환경만)
  py -3.11 company_check.py --json    (부록 JSON을 별도 .json으로도 저장 — 기본은 .md 하나)

산출물 (실행 폴더에 생성):
  company_check_result.md     ← 이 '하나'만 전달하면 됨. 사람 요약 + 부록에 전체 JSON 포함.

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
TIMEOUT_SCN_AGENT = 90
TIMEOUT_SCN_EXCEL = 60
TIMEOUT_SCN_MATLAB = 150
TIMEOUT_SCN_HWP = 60
TIMEOUT_SCN_OUTLOOK = 40
TIMEOUT_SCN_AUTOCAD = 120
TIMEOUT_AGENTOPS = 130

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


# =================================================================
#  업무 시나리오 실동작 (접속 확인이 아니라 "실제 1회 끝까지")
# =================================================================

def scn_gateway_agent() -> dict:
    """native function calling으로 파일 읽기 tool 왕복 전체 — real work의 핵심 실증.

    LLM에게 파일을 읽으라고 시키고 → tool_calls를 받아 → 실제로 파일을 읽어
    되돌리고 → 최종 답변이 파일 내용을 반영하는지까지 end-to-end로 확인한다.
    (P11-A native tools 경로와 P13-02 work real 경로가 실제로 돈다는 증거)
    """
    import urllib.error
    import urllib.request
    env = _load_env()
    root = env.get("LIG_GATEWAY_BASE_URL", "").rstrip("/")
    key = env.get("LIG_API_KEY", "")
    if not root or "REPLACE" in root:
        return {"ok": False, "status": "lig-api.env 미설정"}
    base = root + env.get("LIG_ROUTE_CODING", "/gateway/EXAONE-4.5-33B-vibe_coding_think_off/v1") + "/chat/completions"
    tmp = Path(os.environ.get("TEMP", ".")) / f"occ_agent_{os.getpid()}.txt"
    tmp.write_text("시험 항목A 측정값 12.4 판정 합격\n시험 항목B 측정값 13.9 판정 불합격\n",
                   encoding="utf-8")

    def post(payload, timeout=60):
        req = urllib.request.Request(base, data=json.dumps(payload).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json",
                                    "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))

    tools = [{"type": "function", "function": {
        "name": "read_file", "description": "워크스페이스의 텍스트 파일을 읽어 내용을 반환한다",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}}]
    info = {"ok": False}
    try:
        msgs = [{"role": "user",
                 "content": f"{tmp.name} 파일을 read_file 도구로 읽고, 판정이 불합격인 항목만 알려줘."}]
        r1 = post({"model": "EXAONE-4.5-33B", "max_tokens": 256, "tools": tools,
                   "messages": msgs})
        choice = (r1.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        tcs = msg.get("tool_calls") or []
        info["tool_call_requested"] = bool(tcs)
        info["finish_reason"] = choice.get("finish_reason")
        if not tcs:
            info["status"] = "tool_calls 미반환 (native 경로 불가 — 텍스트 파싱 필요)"
            info["assistant_content"] = str(msg.get("content", ""))[:200]
            return info
        tc = tcs[0]
        call_id = tc.get("id") or "call_1"
        if call_id == "N/A":
            call_id = "occ_call_1"  # gateway id 신뢰 불가 → 자체 발급
        try:
            args = json.loads(tc.get("function", {}).get("arguments") or "{}")
        except Exception:
            args = {}
        info["tool_args"] = args
        file_content = tmp.read_text(encoding="utf-8")  # 실제 도구 실행
        info["file_read_back"] = True
        # 2차: 도구 결과를 되돌려 최종 답변
        assistant_msg = {"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": [{"id": call_id, "type": "function",
                                         "function": tc.get("function", {})}]}
        msgs += [assistant_msg,
                 {"role": "tool", "tool_call_id": call_id, "name": "read_file",
                  "content": file_content}]
        r2 = post({"model": "EXAONE-4.5-33B", "max_tokens": 256, "messages": msgs})
        final = (r2.get("choices") or [{}])[0].get("message", {}).get("content", "")
        info["final_answer"] = final[:300]
        info["e2e_ok"] = ("B" in final) or ("불합격" in final)
        info["ok"] = info["e2e_ok"]
        info["status"] = ("전체 tool 왕복 성공 — 최종 답변이 파일 내용 반영"
                          if info["e2e_ok"] else "왕복은 됐으나 최종 답변이 내용 미반영")
    except urllib.error.HTTPError as e:
        info["status"] = f"HTTP {e.code}: {e.read(200).decode('utf-8','replace')}"
    except Exception as e:
        info["status"] = f"실패: {type(e).__name__}: {e}"
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass
    return info


def scn_excel_macro() -> dict:
    """임시 xlsx에 VBA 모듈을 주입하고 실행 — 자동주입 end-to-end (AccessVBOM 실증)."""
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
    except ImportError:
        return {"ok": False, "status": "pywin32 없음"}
    tmp = Path(os.environ.get("TEMP", ".")) / f"occ_xlmac_{os.getpid()}.xlsm"
    xl = None
    info = {"ok": False}
    try:
        pythoncom.CoInitialize()
        xl = win32com.client.DispatchEx("Excel.Application")
        xl.Visible = False
        xl.DisplayAlerts = False
        wb = xl.Workbooks.Add()
        try:
            mod = wb.VBProject.VBComponents.Add(1)  # 1 = 표준 모듈
            mod.CodeModule.AddFromString(
                'Sub OccMacroTest()\n'
                '    ThisWorkbook.Worksheets(1).Range("A1").Value = 42\n'
                'End Sub')
            info["macro_injected"] = True
            xl.Run("OccMacroTest")
            val = wb.Worksheets(1).Range("A1").Value
            info["macro_ran"] = True
            info["result_cell"] = val
            info["ok"] = (val == 42)
            info["status"] = ("매크로 주입+실행 성공 (A1=42)" if info["ok"]
                              else f"실행됐으나 결과 불일치 (A1={val})")
        except Exception as e:
            info["status"] = f"VBProject 주입/실행 차단: {type(e).__name__} — 수동 import 필요"
        wb.Close(SaveChanges=False)
    except Exception as e:
        info["status"] = f"Excel COM 실패: {type(e).__name__}"
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


def scn_matlab_process() -> dict:
    """MATLAB로 실제 데이터 계산 실행 (읽기/집계 대표) — -batch end-to-end."""
    import glob
    hits = sorted(glob.glob(r"C:\Program Files\MATLAB\R20*\bin\matlab.exe"))
    exe = os.environ.get("MATLAB_EXE", hits[-1] if hits else "")
    if not exe or not Path(exe).exists():
        return {"ok": False, "status": "matlab.exe 미발견"}
    t0 = time.time()
    try:
        r = subprocess.run(
            [exe, "-batch", "M=[12.4 13.9 11.2]; fprintf('mean=%.2f max=%.2f\\n', mean(M), max(M))"],
            capture_output=True, timeout=TIMEOUT_SCN_MATLAB - 10, text=True,
            encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        return {"ok": r.returncode == 0 and "mean=" in out, "seconds": round(time.time() - t0, 1),
                "output_tail": out.strip()[-120:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": f"timeout(>{TIMEOUT_SCN_MATLAB-10}s)"}
    except Exception as e:
        return {"ok": False, "status": f"실패: {type(e).__name__}"}


def scn_hwp_doc() -> dict:
    """새 HWP 문서에 텍스트 삽입 후 임시 파일로 저장 — 문서 생성 end-to-end."""
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
    except ImportError:
        return {"ok": False, "status": "pywin32 없음"}
    tmp = Path(os.environ.get("TEMP", ".")) / f"occ_hwp_{os.getpid()}.hwp"
    hwp = None
    info = {"ok": False}
    try:
        pythoncom.CoInitialize()
        hwp = win32com.client.DispatchEx("HWPFrame.HwpObject")
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        try:
            hwp.XHwpDocuments.Add(0)
        except Exception:
            pass
        try:
            act = hwp.CreateAction("InsertText")
            pset = act.CreateSet()
            pset.SetItem("Text", "OpenCodeLIG 계측 문서 — 자동 생성 테스트")
            act.Execute(pset)
            info["text_inserted"] = True
        except Exception as e:
            info["text_inserted"] = f"실패: {type(e).__name__}"
        try:
            hwp.SaveAs(str(tmp), "HWP", "")
            info["saved"] = tmp.exists()
            info["ok"] = tmp.exists()
            info["status"] = "HWP 문서 생성+저장 성공" if info["ok"] else "저장 실패"
        except Exception as e:
            info["status"] = f"저장 차단: {type(e).__name__}"
    except Exception as e:
        info["status"] = f"HWP COM 실패: {type(e).__name__}"
    finally:
        try:
            if hwp:
                hwp.Quit()
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


def scn_outlook_read() -> dict:
    """Outlook 일정/받은편지함 개수 read — 비서 연동 실동작(읽기)."""
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
    except ImportError:
        return {"ok": False, "status": "pywin32 없음"}
    ol = None
    info = {"ok": False}
    try:
        pythoncom.CoInitialize()
        ol = win32com.client.DispatchEx("Outlook.Application")
        ns = ol.GetNamespace("MAPI")
        inbox = ns.GetDefaultFolder(6)   # olFolderInbox
        cal = ns.GetDefaultFolder(9)     # olFolderCalendar
        info["inbox_count"] = int(inbox.Items.Count)
        info["calendar_count"] = int(cal.Items.Count)
        info["ok"] = True
        info["status"] = "Outlook 받은편지함/일정 read 성공"
    except Exception as e:
        info["status"] = f"Outlook read 실패: {type(e).__name__}"
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
    return info


def scn_autocad_script() -> dict:
    """accoreconsole로 사본 dwg에 .scr 실행 — CAD 배치 자동화 end-to-end."""
    import glob
    hits = (sorted(glob.glob(r"C:\AutoCAD*\accoreconsole.exe"))
            + sorted(glob.glob(r"C:\Program Files\Autodesk\AutoCAD*\accoreconsole.exe")))
    exe = os.environ.get("ACCORECONSOLE_EXE", hits[-1] if hits else "")
    if not exe or not Path(exe).exists():
        return {"ok": False, "status": "accoreconsole.exe 미발견"}
    tmpdir = Path(os.environ.get("TEMP", ".")) / f"occ_acad_{os.getpid()}"
    tmpdir.mkdir(exist_ok=True)
    scr = tmpdir / "test.scr"
    # 새 도면에 원 하나 그리고 사본으로 저장 후 종료 (원본 없이 동작)
    scr.write_text('_CIRCLE\n0,0\n10\n_SAVEAS\n2013\n"' + str(tmpdir / "out.dwg").replace("\\", "/") + '"\n_QUIT\n',
                   encoding="utf-8")
    t0 = time.time()
    try:
        r = subprocess.run([exe, "/s", str(scr)], capture_output=True,
                           timeout=TIMEOUT_SCN_AUTOCAD - 10, text=True,
                           encoding="utf-8", errors="replace", cwd=str(tmpdir))
        secs = round(time.time() - t0, 1)
        made = (tmpdir / "out.dwg").exists()
        return {"ok": made or r.returncode == 0, "seconds": secs, "out_dwg_created": made,
                "exit": r.returncode, "output_tail": ((r.stdout or "") + (r.stderr or "")).strip()[-150:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": f"timeout(>{TIMEOUT_SCN_AUTOCAD-10}s) — 대화형 대기 가능성"}
    except Exception as e:
        return {"ok": False, "status": f"실패: {type(e).__name__}"}
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


# ------------------------------------ 현재 빌드 런타임 (동봉 시 자동) ---

def _find_agentops() -> str:
    """이 스크립트와 함께(또는 번들 안에) agent_ops가 있으면 그 agentops.py 경로."""
    here = Path(os.path.abspath(__file__)).parent
    env_home = os.environ.get("AGENTOPS_HOME", "")
    cands = []
    if env_home:
        cands.append(Path(env_home) / "agentops.py")
        cands.append(Path(env_home) / "agent_ops" / "agentops.py")
    cands += [
        here / "agent_ops" / "agentops.py",
        here / "workspace-template" / "agent_ops" / "agentops.py",
        here.parent / "agent_ops" / "agentops.py",
        here.parent / "workspace-template" / "agent_ops" / "agentops.py",
        Path.cwd() / "agent_ops" / "agentops.py",
        Path.cwd() / "workspace-template" / "agent_ops" / "agentops.py",
    ]
    for c in cands:
        try:
            if c and c.exists():
                return str(c.resolve())
        except OSError:
            continue
    return ""


def probe_agentops() -> dict:
    """현재 빌드(agent_ops)가 이 회사 PC에서 실제로 로드·기동되는지.
    동봉 안 됐으면 환경만 점검했다고 정직히 보고(실패 아님)."""
    ap = _find_agentops()
    if not ap:
        return {"ok": None, "found": False,
                "status": "agent_ops 미동봉 — 이 스크립트 단독 실행이라 '환경'만 점검함. "
                          "번들(workspace-template)을 같은 위치에 두고 재실행하면 런타임까지 자동 점검."}
    workdir = str(Path(ap).parent.parent)   # workspace-template
    out = {"ok": True, "found": True, "root": _mask_path(workdir)}

    def run(args, timeout):
        r = subprocess.run([sys.executable, ap] + args, capture_output=True, text=True,
                           timeout=timeout, cwd=workdir, encoding="utf-8", errors="replace",
                           env=dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8"))
        return r.returncode, (r.stdout or ""), (r.stderr or "")

    # 1) doctor — capabilities/adapters/artifact pipeline/LLM endpoints 인벤토리
    try:
        rc, so, se = run(["doctor"], 90)
        out["doctor_exit"] = rc
        out["doctor_tail"] = _mask_path(so[-1800:] or se[-400:])
    except subprocess.TimeoutExpired:
        out["doctor_exit"] = "timeout"
    except Exception as e:
        out["doctor_exit"] = "error"; out["doctor_error"] = f"{type(e).__name__}: {e}"

    # 2) mock work 스모크 — gateway 없이도 도는 파이프라인 (E2E 1회). --quick면 생략.
    if os.environ.get("CC_QUICK") == "1":
        out["mock_work_exit"] = "skipped(--quick)"
    else:
        try:
            rc, so, se = run(["work", "--task", "회의록 초안 만들어줘", "--mode", "mock"], 100)
            out["mock_work_exit"] = rc
            out["mock_work_tail"] = _mask_path((so or se)[-700:])
        except subprocess.TimeoutExpired:
            out["mock_work_exit"] = "timeout"
        except Exception as e:
            out["mock_work_exit"] = "error"; out["mock_work_error"] = f"{type(e).__name__}: {e}"

    # 3) real agent E2E — 실제 게이트웨이로 tool-use 루프 1회. 이게 "진짜 됨"의 증거.
    #    gateway(lig-api.env) 설정 시에만. 미설정이면 정직히 생략.
    env = _load_env()
    gw = env.get("LIG_GATEWAY_BASE_URL", "")
    key = env.get("LIG_API_KEY", "")
    gw_ready = bool(gw) and "REPLACE" not in gw and bool(key) and "REPLACE" not in key
    if not gw_ready:
        out["real_agent_exit"] = "skipped(lig-api.env 미설정 — gateway 없이 런타임/파이프라인만 검증)"
    elif os.environ.get("CC_QUICK") == "1":
        out["real_agent_exit"] = "skipped(--quick)"
    else:
        try:
            rc, so, se = run(["agent", "--mode", "real", "--max-turns", "4",
                              "--task", "작업 폴더의 파일을 확인하고 한 줄로 요약해줘"], 100)
            out["real_agent_exit"] = rc
            out["real_agent_tail"] = _mask_path((so or se)[-900:])
        except subprocess.TimeoutExpired:
            out["real_agent_exit"] = "timeout"
        except Exception as e:
            out["real_agent_exit"] = "error"; out["real_agent_error"] = f"{type(e).__name__}: {e}"
    return out


ISOLATED = {
    "gateway": (probe_gateway, TIMEOUT_GATEWAY),
    "excel": (probe_excel_com, TIMEOUT_COM),
    "outlook": (probe_outlook_com, TIMEOUT_COM),
    "hwp": (probe_hwp_com, TIMEOUT_COM),
    "solidworks": (probe_solidworks_com, TIMEOUT_COM),
    "matlab": (probe_matlab, TIMEOUT_MATLAB),
    "chrome": (probe_chrome_cdp, TIMEOUT_CHROME),
    "opencode": (probe_opencode_startup, TIMEOUT_OPENCODE),
    "agentops": (probe_agentops, TIMEOUT_AGENTOPS),
    # 시나리오 (실제 1회 끝까지)
    "scn_agent": (scn_gateway_agent, TIMEOUT_SCN_AGENT),
    "scn_excel_macro": (scn_excel_macro, TIMEOUT_SCN_EXCEL),
    "scn_matlab": (scn_matlab_process, TIMEOUT_SCN_MATLAB),
    "scn_hwp": (scn_hwp_doc, TIMEOUT_SCN_HWP),
    "scn_outlook": (scn_outlook_read, TIMEOUT_SCN_OUTLOOK),
    "scn_autocad": (scn_autocad_script, TIMEOUT_SCN_AUTOCAD),
}

SCENARIOS = ["scn_agent", "scn_excel_macro", "scn_matlab", "scn_hwp", "scn_outlook", "scn_autocad"]


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
    ao = report.get("live", {}).get("agentops", {})
    L += ["## 0. 현재 빌드(agent_ops) 런타임 — 지금 기준", ""]
    if ao.get("found") is False:
        L.append(f"- {ao.get('status', '미점검')}")
        L.append("- (이번 반입은 이 스크립트 하나 = **환경만 점검**. 런타임은 번들 반입 후 동일 파일 재실행 시 자동.)")
    elif ao.get("found"):
        L.append(f"- agent_ops 위치: {ao.get('root')}")
        L.append(f"- **doctor 종료코드**: {ao.get('doctor_exit')} (0=정상 로드)")
        L.append(f"- **mock work E2E**: {ao.get('mock_work_exit')} (0=파이프라인 정상, gateway 불필요)")
        L.append(f"- **real agent E2E**: {ao.get('real_agent_exit')} "
                 f"(0=실제 게이트웨이로 tool-use 루프 성공 ← '진짜 됨'의 증거)")
        L.append("")
        L.append("doctor 출력(끝부분 — capabilities/adapters/artifact/LLM 인벤토리):")
        L.append("```")
        L.append(str(ao.get("doctor_tail", ""))[-1200:])
        L.append("```")
        if ao.get("real_agent_tail"):
            L.append("real agent 실행 로그(끝부분):")
            L.append("```")
            L.append(str(ao.get("real_agent_tail", ""))[-700:])
            L.append("```")
    else:
        L.append("- 점검 안 됨")
    L.append("")
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
    scn = report.get("scenarios", {})
    if scn:
        L += ["", "## 6. 업무 시나리오 실동작 (실제 1회 끝까지)", ""]
        labels = {
            "scn_agent": "① LLM native tool 왕복 (파일 읽기→답변)",
            "scn_excel_macro": "② Excel 매크로 주입+실행",
            "scn_matlab": "③ MATLAB 데이터 계산 -batch",
            "scn_hwp": "④ HWP 문서 생성+저장",
            "scn_outlook": "⑤ Outlook 일정/메일 read",
            "scn_autocad": "⑥ AutoCAD accoreconsole .scr 실행",
        }
        for key in SCENARIOS:
            r = scn.get(key, {})
            mark = "✅ OK" if r.get("ok") else "❌ 실패/차단"
            detail = r.get("status", "")
            extra = ""
            if key == "scn_agent" and r.get("ok"):
                extra = f" / 최종답변: {str(r.get('final_answer',''))[:60]}"
            if key in ("scn_matlab", "scn_autocad") and r.get("seconds"):
                extra += f" / {r.get('seconds')}s"
            L.append(f"- {labels.get(key, key)}: {mark} — {detail}{extra}")
        L += ["", "> 시나리오 ①이 OK면 real 업무 자동화(파일 읽고 처리)가 실제로 돈다는 뜻.",
              "> ②~⑥은 각 앱 자동화 어댑터의 실기 전제 확인."]
    L += ["", "> 이 .md 파일 하나만 그대로 전달하면 됩니다 (전체 JSON은 부록 A에 포함). "
          "host/key/사용자명은 마스킹됨."]
    return "\n".join(L)


def main() -> int:
    quick = "--quick" in sys.argv
    if quick:
        os.environ["CC_QUICK"] = "1"   # 자식 프로세스(agentops mock work)로 전파
    print("OpenCodeLIG 계측 시작 — 잠시 걸립니다 (앱/gateway 실검사 포함)...\n")
    report = {
        "tool": "company_check", "version": 2,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "environment": collect_environment(),
        "apps": collect_apps(),
        "office_security": collect_office_security(),
        "gateway": {}, "live": {}, "scenarios": {},
    }
    order = ["agentops", "gateway", "opencode"]
    if not quick:
        order += ["excel", "outlook", "hwp", "solidworks", "chrome", "matlab"]
        order += SCENARIOS
    for name in order:
        fn, timeout = ISOLATED[name]
        print(f"  [{name}] 검사 중 (최대 {timeout}s)...", flush=True)
        res = _isolated(name, timeout)
        if name == "gateway":
            report["gateway"] = res
        elif name in SCENARIOS:
            report["scenarios"][name] = res
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
    # 결과는 .md 하나로 통합 — 사람 판독용 요약 + 부록에 전체 JSON(기계 판독용)을 접어 넣는다.
    md = _mask(_md(report), secrets)
    md += ("\n\n---\n\n## 부록 A. 전체 원자료 (JSON — 기계 판독용, 마스킹됨)\n\n"
           "<details><summary>펼치기</summary>\n\n```json\n" + text + "\n```\n\n</details>\n")
    out_md = Path.cwd() / "company_check_result.md"
    out_md.write_text(md, encoding="utf-8")
    outputs = [out_md]
    if "--json" in sys.argv:   # 선택: 별도 .json도 원하면
        out_json = Path.cwd() / "company_check_result.json"
        out_json.write_text(text, encoding="utf-8")
        outputs.append(out_json)
    print("\n완료. 아래 파일 '하나'만 전달해 주세요 (host/key/사용자명 마스킹됨, JSON은 부록에 포함):")
    for p in outputs:
        print(f"  {p}")
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
