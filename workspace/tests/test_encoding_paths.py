# -*- coding: utf-8 -*-
"""Korean path / UTF-8 BOM / CMD codepage validation (stdlib only).

Run: py -3.11 tests\\test_encoding_paths.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent_ops.encoding_ops import BOM_BYTES, detect_style, edit_replace, read_text, write_text  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    # 1. Korean directory + Korean filename with spaces: create/read/edit
    kdir = base / "한글 경로 테스트" / "하위 폴더"
    kfile = kdir / "보고서 초안.txt"
    write_text(kfile, "첫 번째 줄\n두 번째 줄\n")
    text, style = read_text(kfile)
    check("korean path create/read", text == "첫 번째 줄\n두 번째 줄\n" and style["bom"] is False, repr(text))
    r = edit_replace(kfile, "두 번째", "수정된")
    check("korean path edit", r["ok"] and "수정된 줄" in read_text(kfile)[0], str(r))

    # 2. New file default: UTF-8 without BOM
    check("new file has no BOM", not kfile.read_bytes().startswith(BOM_BYTES))

    # 3. UTF-8 with BOM: read without corruption, edit preserves BOM
    bfile = base / "BOM 문서.md"
    bfile.write_bytes(BOM_BYTES + "# 제목\r\n한글 내용\r\n".encode("utf-8"))
    text, style = read_text(bfile)
    check("BOM read clean", text.startswith("# 제목") and style == {"bom": True, "newline": "crlf"}, str(style))
    r = edit_replace(bfile, "한글 내용", "바뀐 내용")
    raw = bfile.read_bytes()
    check("BOM preserved after edit", r["ok"] and raw.startswith(BOM_BYTES), str(r))
    check("CRLF preserved after edit", b"\xeb\xb0\x94\xeb\x80\x90 \xeb\x82\xb4\xec\x9a\xa9\r\n" in raw, repr(raw[-40:]))
    check("BOM not duplicated", raw.count(BOM_BYTES[:3]) >= 1 and not raw[3:].startswith(BOM_BYTES), repr(raw[:12]))

    # 4. no-BOM file stays no-BOM after edit
    nfile = base / "no-bom.txt"
    nfile.write_bytes("plain 한글\n".encode("utf-8"))
    edit_replace(nfile, "plain", "still")
    check("no-BOM stays no-BOM", not nfile.read_bytes().startswith(BOM_BYTES))

    # 5. Missing old text -> clean error, file untouched
    before = nfile.read_bytes()
    r = edit_replace(nfile, "없는 문자열", "x")
    check("missing old text safe", r["ok"] is False and nfile.read_bytes() == before, str(r))

    # 6. Python roundtrip via BOM-tolerant read of both styles
    check("utf-8-sig tolerant both", read_text(bfile)[0][0] == "#" and read_text(nfile)[0].startswith("still"))

    # 7. CMD: chcp 65001 BAT calling py -3.11 from a Korean/space path
    bat = kdir / "run test.bat"
    kout = kdir / "cmd-out.txt"
    # BAT references a Korean path, so it cannot be ASCII. Pattern: UTF-8
    # without BOM, ASCII-only lines until `chcp 65001`, Korean paths after it.
    # PYTHONUTF8=1 is required: with stdout redirected to a file, Python
    # otherwise encodes with the ANSI codepage (cp949) despite chcp 65001.
    bat.write_text(
        "@echo off\r\nchcp 65001 >nul\r\nset PYTHONUTF8=1\r\n"
        f'py -3.11 -c "print(\'OK-\' + chr(54620) + chr(44544))" > "{kout}"\r\n',
        encoding="utf-8",
    )
    cp = subprocess.run(["cmd", "/c", str(bat)], capture_output=True, timeout=60)
    out = kout.read_text(encoding="utf-8", errors="replace") if kout.exists() else ""
    check("BAT+chcp65001+py311 from korean path", cp.returncode == 0 and "OK-한글" in out, f"rc={cp.returncode} out={out!r} err={cp.stderr[:200]!r}")

    # 8. Record current codepage (diagnostic, not an assertion)
    cp = subprocess.run(["cmd", "/c", "chcp"], capture_output=True, text=True, timeout=30)
    print(f"INFO  host codepage: {cp.stdout.strip()}")

print(f"\n{PASS} checks passed")
