# -*- coding: utf-8 -*-
"""Batch adapter tests for MATLAB -batch and AutoCAD accoreconsole.

Run: py -3.11 tests\\test_batch_adapters.py
"""
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

tmp_root = Path(tempfile.mkdtemp(prefix="batch_adapter_test_"))
os.environ["AGENTOPS_ROOT"] = str(tmp_root / "agentops")
os.environ["LIG_AUDIT_DIR"] = str(tmp_root / "audit")
os.environ["LIG_SCHEDULE_DIR"] = str(tmp_root / "schedule")

WS_TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_TEMPLATE))

from agent_ops.adapters import ADAPTERS  # noqa: E402
from agent_ops.adapters import autocad_batch, matlab_batch  # noqa: E402
from agent_ops.artifact_generators import generate_artifacts  # noqa: E402
from agent_ops.artifact_quality import validate_artifact_set  # noqa: E402
from agent_ops.capabilities import ARTIFACT_KIND_INFO, CAPABILITIES, plan_task  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: object = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def _write_fake_exe(base: Path, *, win_body: str, unix_body: str) -> Path:
    if os.name == "nt":
        path = base.with_suffix(".cmd")
        path.write_text(win_body, encoding="utf-8")
    else:
        path = base.with_suffix(".sh")
        path.write_text(unix_body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IRUSR)
    return path


def main() -> None:
    old_matlab = os.environ.get("MATLAB_EXE")
    old_accore = os.environ.get("ACCORECONSOLE_EXE")
    try:
        os.environ["MATLAB_EXE"] = ""
        os.environ["ACCORECONSOLE_EXE"] = ""
        missing_mat = matlab_batch.execute(str(tmp_root / "missing.m"), {})
        check("matlab missing script fails cleanly",
              missing_mat["ok"] is False and "script 파일 없음" in missing_mat["error"], missing_mat)
        script = tmp_root / "작업.m"
        script.write_text("disp('ok')\n", encoding="utf-8")
        missing_exe = matlab_batch.execute(str(script), {})
        check("matlab missing executable explains env/PATH",
              missing_exe["ok"] is False and "MATLAB_EXE" in missing_exe["error"], missing_exe)

        fake_matlab = _write_fake_exe(
            tmp_root / "fake_matlab",
            win_body="@echo off\r\necho MATLAB fake ok\r\nexit /b 0\r\n",
            unix_body="#!/bin/sh\necho MATLAB fake ok\nexit 0\n",
        )
        os.environ["MATLAB_EXE"] = str(fake_matlab)
        check("find_matlab uses env override", matlab_batch.find_matlab() == str(fake_matlab))
        ok_mat = matlab_batch.execute(str(script), {"timeout_s": 30})
        check("matlab fake executable succeeds",
              ok_mat["ok"] is True and ok_mat["returncode"] == 0 and "-batch" in ok_mat["cmd"],
              ok_mat)
        check("matlab cwd is script folder by command shape",
              ok_mat["cmd"][-1] == "run('작업.m')", ok_mat["cmd"])

        missing_dwg = autocad_batch.execute(str(tmp_root / "missing.dwg"), str(tmp_root / "x.scr"), {})
        check("autocad missing dwg fails cleanly",
              missing_dwg["ok"] is False and "DWG 파일 없음" in missing_dwg["error"], missing_dwg)
        dwg = tmp_root / "원본.dwg"
        dwg.write_bytes(b"ORIGINAL_DWG_BYTES")
        missing_scr = autocad_batch.execute(str(dwg), str(tmp_root / "missing.scr"), {})
        check("autocad missing script fails cleanly",
              missing_scr["ok"] is False and "script 파일 없음" in missing_scr["error"], missing_scr)
        scr = tmp_root / "작업.scr"
        scr.write_text("._QUIT\nY\n", encoding="utf-8")
        missing_accore = autocad_batch.execute(str(dwg), str(scr), {})
        check("autocad missing executable explains env/PATH",
              missing_accore["ok"] is False and "ACCORECONSOLE_EXE" in missing_accore["error"], missing_accore)

        fake_ok = _write_fake_exe(
            tmp_root / "fake_accore_ok",
            win_body="@echo off\r\npowershell -NoProfile -Command \"$b=[Text.Encoding]::Unicode.GetBytes('AutoCAD 유니코드 로그'); [Console]::OpenStandardOutput().Write($b,0,$b.Length)\"\r\nexit /b 0\r\n",
            unix_body="#!/bin/sh\nprintf 'AutoCAD fake ok'\nexit 0\n",
        )
        os.environ["ACCORECONSOLE_EXE"] = str(fake_ok)
        check("find_accoreconsole uses env override", autocad_batch.find_accoreconsole() == str(fake_ok))
        original_bytes = dwg.read_bytes()
        ok_cad = autocad_batch.execute(str(dwg), str(scr), {"timeout_s": 30})
        copy_path = Path(ok_cad.get("copy_path", ""))
        check("autocad fake executable succeeds", ok_cad["ok"] is True and ok_cad["returncode"] == 0, ok_cad)
        check("autocad command uses /i copy and /s script",
              "/i" in ok_cad["cmd"] and str(copy_path) in ok_cad["cmd"] and "/s" in ok_cad["cmd"], ok_cad["cmd"])
        check("autocad runs against copy path", copy_path.name.startswith("사본_") and copy_path.exists(), copy_path)
        check("autocad original dwg unchanged", dwg.read_bytes() == original_bytes)
        if os.name == "nt":
            check("autocad decodes utf16le stdout", "유니코드 로그" in ok_cad.get("stdout_tail", ""), ok_cad)

        fake_53 = _write_fake_exe(
            tmp_root / "fake_accore_53",
            win_body="@echo off\r\npowershell -NoProfile -Command \"$b=[Text.Encoding]::Unicode.GetBytes('ErrorStatus=53'); [Console]::OpenStandardOutput().Write($b,0,$b.Length)\"\r\nexit /b 53\r\n",
            unix_body="#!/bin/sh\nprintf '\\377\\376E\\000r\\000r\\000o\\000r\\000S\\000t\\000a\\000t\\000u\\000s\\000=\\0005\\0003\\000'\nexit 53\n",
        )
        os.environ["ACCORECONSOLE_EXE"] = str(fake_53)
        exit53 = autocad_batch.execute(str(dwg), str(scr), {"timeout_s": 30})
        check("autocad exit 53 classified as dwg open problem",
              exit53["ok"] is False and "exit 53" in exit53["error"] and "ErrorStatus=53" in exit53["log_tail"],
              exit53)

        plan = plan_task("AutoCAD 도면 정리 스크립트 만들어줘")
        check("office cad plan includes autocad_script",
              "autocad_script" in plan["artifact_kinds"], str(plan["artifact_kinds"]))
        out = generate_artifacts("AutoCAD 도면 정리 스크립트 만들어줘", ["autocad_script"], out_dir=tmp_root / "artifacts")
        check("autocad script generated ok", out["ok"] and out["quality"]["autocad_script"]["ok"], str(out))
        text = Path(out["files"][0]).read_text(encoding="utf-8")
        check("autocad script states copy policy and pending",
              "사본" in text and "app validation pending" in text and "AutoCAD 2019" in text, text)
        check("autocad script has no qsave command",
              not any(line.strip().upper() == "QSAVE" for line in text.splitlines()), text)
        bad = validate_artifact_set("autocad_script", [text + "\nQSAVE\n"],
                                    task="AutoCAD 도면 정리 스크립트 만들어줘", filenames=["작업.scr"])
        check("autocad quality catches qsave command",
              not bad["ok"] and any(v["rule"] == "autocad_no_qsave_command" for v in bad["violations"]),
              bad["violations"])

        check("artifact kind metadata includes autocad_script", "autocad_script" in ARTIFACT_KIND_INFO)
        check("office cad capability emits autocad_script",
              "autocad_script" in CAPABILITIES["office_cad_automation"]["artifact_kinds"])
        check("matlab adapter registered unavailable",
              ADAPTERS["matlab"]["available"] is False and ADAPTERS["matlab"].get("execute") is matlab_batch.execute)
        check("autocad adapter registered unavailable",
              ADAPTERS["autocad"]["available"] is False and ADAPTERS["autocad"].get("execute") is autocad_batch.execute)
    finally:
        if old_matlab is None:
            os.environ.pop("MATLAB_EXE", None)
        else:
            os.environ["MATLAB_EXE"] = old_matlab
        if old_accore is None:
            os.environ.pop("ACCORECONSOLE_EXE", None)
        else:
            os.environ["ACCORECONSOLE_EXE"] = old_accore

    print(f"\nALL {PASS} CHECKS PASSED (batch adapters)")


if __name__ == "__main__":
    main()
