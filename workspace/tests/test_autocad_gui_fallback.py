# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_ops.adapters import autocad_batch


def test_autocad_falls_back_to_acad_gui_command(monkeypatch, tmp_path: Path) -> None:
    acad = tmp_path / "acad.exe"
    acad.write_text("fake", encoding="utf-8")
    dwg = tmp_path / "input.dwg"
    dwg.write_text("dwg", encoding="utf-8")
    scr = tmp_path / "job.scr"
    scr.write_text("ZOOM\n", encoding="utf-8")
    captured = {}

    monkeypatch.setattr(autocad_batch, "find_accoreconsole", lambda: "")
    monkeypatch.setattr(autocad_batch, "find_acad", lambda: str(acad))

    class Result:
        returncode = 0
        stdout = b""
        stderr = b""

    def fake_run(cmd, cwd, capture_output, timeout):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["capture_output"] = capture_output
        captured["timeout"] = timeout
        return Result()

    monkeypatch.setattr(autocad_batch.subprocess, "run", fake_run)
    monkeypatch.setattr(autocad_batch, "_audit", lambda copy_dwg, scr_path, result: None)

    result = autocad_batch.execute(str(dwg), str(scr), {})

    assert result["ok"] is True
    assert captured["cmd"][0] == str(acad)
    assert "/p" in captured["cmd"]
    assert "LIGNEX1" in captured["cmd"]
    assert "/product" in captured["cmd"]
    assert "ACADM" in captured["cmd"]
    assert "/b" in captured["cmd"]
    assert str(scr) in captured["cmd"]
    assert any(Path(part).name.startswith("사본_input") for part in captured["cmd"])
