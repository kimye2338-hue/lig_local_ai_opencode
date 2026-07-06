# -*- coding: utf-8 -*-
"""ocd 폴더-로컬 프로필 + 전역 기억 회귀 (FABLE-OCD-WORKSPACE-PROFILES).

Run: py -3.11 tests\\test_ocd_profiles.py  (리눅스에서도 동작 — stdlib only)

수용 기준 대응:
  1. 첫 실행이 .opencodelig 과 시드 5종을 만든다.
  2. 두 번째 실행이 사용자가 고친 로컬 파일을 덮어쓰지 않는다.
  3. 전역 기억 경로는 override 없으면 USERPROFILE 기준 전역이다.
  4. 로컬 페르소나/규칙/프로젝트 기억이 컨텍스트 조립에 잡힌다.
  5. 생성되는 ocd.bat/ai.bat 은 ASCII + CRLF 다.
  6. 에이전트 루프가 프로필 컨텍스트를 실제로 LLM 메시지에 주입한다.
  7. project_info/remember 가 LLM tool 로 노출된다 (구현≠노출 교훈).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

TMP = Path(tempfile.mkdtemp(prefix="ocd_profiles_"))
os.environ["AGENTOPS_ROOT"] = str(TMP / "ws")   # 기억/산출물 격리 (import 전에)
(TMP / "ws").mkdir(parents=True, exist_ok=True)
for key in ("AGENTOPS_MEMORY_DIR", "AGENTOPS_PROJECT_DIR", "AGENTOPS_PROJECT_PERSONA",
            "AGENTOPS_PROJECT_MEMORY", "AGENTOPS_PROJECT_RULES"):
    os.environ.pop(key, None)

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
    from agent_ops import project_profile as pp

    # --- 1. 첫 시드 ---
    proj = TMP / "프로젝트A"
    proj.mkdir()
    seeded = pp.seed_profile(proj)
    check("first run creates 5 seed files", sorted(seeded["created"]) == sorted(pp.SEED_FILES)
          and seeded["first_run"], str(seeded))
    pdir = proj / ".opencodelig"
    check("profile dir + state dirs exist", pdir.is_dir() and (pdir / "diagnostics").is_dir()
          and (pdir / "state").is_dir())
    profile = json.loads((pdir / "profile.json").read_text(encoding="utf-8"))
    check("profile.json seed sane", profile["version"] == 1 and profile["global_memory"] is True,
          str(profile))

    # --- 2. 재실행은 사용자 수정본을 보존 ---
    (pdir / "PERSONA.md").write_text("# 퀀트 전용 페르소나\n금융 데이터 우선.\n", encoding="utf-8")
    seeded2 = pp.seed_profile(proj)
    check("second run creates nothing", seeded2["created"] == [] and not seeded2["first_run"],
          str(seeded2))
    check("customized persona preserved",
          "퀀트 전용" in (pdir / "PERSONA.md").read_text(encoding="utf-8"))

    # --- 3. 전역 기억 경로 규칙 ---
    save_root = os.environ.pop("AGENTOPS_ROOT")
    save_up = os.environ.get("USERPROFILE")
    os.environ["USERPROFILE"] = str(TMP / "home")
    check("global memory defaults to USERDATA",
          pp.global_memory_dir() == TMP / "home" / "OpenCodeLIG_USERDATA" / "memory",
          str(pp.global_memory_dir()))
    os.environ["AGENTOPS_MEMORY_DIR"] = str(TMP / "mem_override")
    check("explicit memory override wins", pp.global_memory_dir() == TMP / "mem_override")
    os.environ.pop("AGENTOPS_MEMORY_DIR")
    os.environ["AGENTOPS_ROOT"] = save_root
    if save_up is None:
        os.environ.pop("USERPROFILE", None)
    else:
        os.environ["USERPROFILE"] = save_up

    # --- 4. 컨텍스트 조립 ---
    check("resolve by cwd", pp.resolve_project_dir(proj) == pdir)
    os.environ["AGENTOPS_PROJECT_DIR"] = str(pdir)
    ctx = pp.load_project_context()
    check("context loads persona/rules/memory",
          "퀀트 전용" in ctx.get("persona", "") and "전역 기억을 보존" in ctx.get("rules", ""),
          str({k: v[:40] for k, v in ctx.items() if isinstance(v, str)}))
    text = pp.format_context_for_prompt(ctx)
    check("prompt block ordered + conflict rule",
          text.index("[프로젝트 기억]") < text.index("[폴더 페르소나]") < text.index("[프로젝트 규칙]")
          and "충돌 규칙" in text)
    diag = pp.profile_diagnostics(proj)
    check("diagnostics reports active profile",
          diag["project_profile_active"] and diag["files"]["PERSONA.md"], str(diag))

    # --- 6. 에이전트 루프 주입 (가짜 transport 로 페이로드 캡처) ---
    from agent_ops.tool_dispatch import REGISTRY, run_agent_loop, tool_definitions
    captured = {}

    def fake_transport(url, payload, headers, timeout):
        captured["messages"] = payload["messages"]
        return {"choices": [{"message": {"content": "완료"}}]}

    env = {"LIG_GATEWAY_BASE_URL": "http://127.0.0.1:9", "LIG_API_KEY": "x",
           "LIG_DEFAULT_PROVIDER": "lig-coding"}
    result = run_agent_loop("테스트 작업", proj, env=env, transport=fake_transport,
                            diag_dir=TMP / "diag")
    sys_texts = [m["content"] for m in captured["messages"] if m["role"] == "system"]
    check("agent loop injects project context",
          result["ok"] and any("프로젝트 프로필" in t and "퀀트 전용" in t for t in sys_texts),
          str([t[:60] for t in sys_texts]))
    check("safety/global-first conflict rule injected",
          any("전역 사용자 선호가 로컬 페르소나보다 우선" in t for t in sys_texts))
    os.environ.pop("AGENTOPS_PROJECT_DIR")

    # --- 7. LLM tool 노출 (구현만 있고 노출 안 되는 실수 방지) ---
    names = {d["function"]["name"] for d in tool_definitions()}
    check("project_info + remember exposed to LLM",
          {"project_info", "remember"}.issubset(names) and set(REGISTRY) == names)

    # --- 5. 설치 런처 생성물 (ASCII + CRLF) + ocd CLI E2E ---
    sys.path.insert(0, str(WS.parent / "release"))
    import setup_impl
    for content in (setup_impl.OCD_BAT, setup_impl.AI_BAT):
        raw = content.encode("ascii")  # 비ASCII면 여기서 폭발
        check("bat is CRLF-only ascii", raw.count(b"\n") == raw.count(b"\r\n") > 0)
    home = TMP / "home2"
    bin_dir = setup_impl.install_bin_launchers(home)
    check("install_bin_launchers writes ocd/ai",
          (bin_dir / "ocd.bat").is_file() and (bin_dir / "ai.bat").is_file())
    check("installer never touches userdata memory",
          not (home / "OpenCodeLIG_USERDATA" / "memory").exists())

    proj2 = TMP / "프로젝트B"
    proj2.mkdir()
    env2 = dict(os.environ, USERPROFILE=str(home), HOME=str(home))
    env2.pop("AGENTOPS_PROJECT_DIR", None)
    r = subprocess.run([sys.executable, str(WS / "agent_ops" / "ocd.py"), "--no-launch", "--status"],
                       cwd=str(proj2), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env2)
    check("ocd first run: created + exit 0",
          r.returncode == 0 and "Local profile created" in r.stdout, r.stdout + r.stderr)
    r2 = subprocess.run([sys.executable, str(WS / "agent_ops" / "ocd.py"), "--no-launch"],
                        cwd=str(proj2), capture_output=True, text=True,
                        encoding="utf-8", errors="replace", env=env2)
    check("ocd second run: found (no reseed)",
          r2.returncode == 0 and "Local profile found" in r2.stdout, r2.stdout)
    r3 = subprocess.run([sys.executable, str(WS / "agent_ops" / "ocd.py")],
                        cwd=str(proj2), capture_output=True, text=True,
                        encoding="utf-8", errors="replace", env=env2)
    check("ocd without launcher: honest exit 3", r3.returncode == 3 and "설치" in r3.stdout, r3.stdout)

    # --- 인코딩 폴백 (RUNTIME_LESSONS §4: cp949 mojibake) ---
    from agent_ops.encoding_ops import decode_console_bytes
    check("decode utf-8", decode_console_bytes("한글 OK".encode("utf-8")) == "한글 OK")
    check("decode cp949 fallback", decode_console_bytes("한글 경로".encode("cp949")) == "한글 경로")
    check("decode garbage does not crash", isinstance(decode_console_bytes(b"\xff\xfe\x00\x99"), str))
    from agent_ops.core import run_cmd
    r = run_cmd([sys.executable, "-c",
                 "import sys; sys.stdout.buffer.write('한글출력'.encode('cp949'))"])
    check("run_cmd survives cp949 child output", r["ok"] and r["stdout"] == "한글출력", str(r))

    print(f"\nALL {PASS} CHECKS PASSED (ocd profiles + global memory)")


if __name__ == "__main__":
    main()
