# -*- coding: utf-8 -*-
"""패치파일(build_patch) 빌드+적용 E2E — 기억 보존이 핵심 검증.

Run: py -3.11 tests\\test_patch_build.py  (리눅스에서도 동작 — stdlib only)

검증:
  - 패치 zip 구조 (패치.bat / patch_impl / setup_impl / workspace / MANIFEST)
  - secret / results 미반입
  - 가짜 설치 위에 실제 적용: 코드 갱신 + 백업 생성 + 사용자 파일/기억 무손상
  - 설치가 없으면 정직하게 중단 (exit 3)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
REPO = WS.parent
sys.path.insert(0, str(REPO / "release"))

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
    import build_patch

    tmp = Path(tempfile.mkdtemp(prefix="patch_build_"))
    zip_path = build_patch.build("test", tmp / "dist")
    check("patch zip built", zip_path.is_file(), str(zip_path))

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for required in ("패치.bat", "patch/patch_impl.py", "patch/setup_impl.py",
                         "처음_읽어주세요.txt", "MANIFEST_SHA256.txt",
                         "workspace-template/agent_ops/ocd.py",
                         "workspace-template/agent_ops/project_profile.py"):
            check(f"zip contains {required}", required in names)
        check("no secrets in patch",
              not any("lig-api.env" in n or "/secrets/" in n for n in names))
        check("no results payload in patch",
              not any("/results/" in n for n in names), str([n for n in names if "/results/" in n][:3]))
        bat = zf.read("패치.bat")
        check("패치.bat is ascii CRLF", bat.decode("ascii") is not None
              and bat.count(b"\n") == bat.count(b"\r\n") > 0)
        manifest = zf.read("MANIFEST_SHA256.txt").decode("utf-8")
        check("manifest lists every file",
              all(n in manifest for n in names if n != "MANIFEST_SHA256.txt"))

    # --- 적용 E2E: 가짜 기존 설치 ---
    extract = tmp / "extract"
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract)
    home = tmp / "home"
    target = home / "OpenCodeLIG" / "workspace"
    (target / "agent_ops").mkdir(parents=True)
    (target / "agent_ops" / "core.py").write_text("OLD CODE\n", encoding="utf-8")
    (target / "user_note.md").write_text("사용자 메모 — 지우면 안 됨\n", encoding="utf-8")
    mem = home / "OpenCodeLIG_USERDATA" / "memory"
    mem.mkdir(parents=True)
    (mem / "memory.jsonl").write_text('{"id":"mem_keep"}\n', encoding="utf-8")
    (mem / "WIKI.md").write_text("# 위키 원본\n", encoding="utf-8")

    r = subprocess.run([sys.executable, str(extract / "patch" / "patch_impl.py"),
                        "--home", str(home)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONUTF8="1"))
    check("patch applies exit 0", r.returncode == 0, r.stdout + r.stderr)
    new_core = (target / "agent_ops" / "core.py").read_text(encoding="utf-8")
    check("old code replaced", "OLD CODE" not in new_core and "decode_console_bytes" in new_core)
    backups = list((home / "OpenCodeLIG" / "patch_backups").rglob("core.py"))
    check("changed file backed up", len(backups) == 1 and backups[0].read_text(encoding="utf-8") == "OLD CODE\n",
          str(backups))
    check("user file preserved", (target / "user_note.md").read_text(encoding="utf-8").startswith("사용자 메모"))
    check("memory.jsonl untouched", (mem / "memory.jsonl").read_text(encoding="utf-8") == '{"id":"mem_keep"}\n')
    check("WIKI.md untouched", (mem / "WIKI.md").read_text(encoding="utf-8") == "# 위키 원본\n")
    check("bin launchers regenerated", (home / "OpenCodeLIG" / "bin" / "ocd.bat").is_file())
    check("patch reports memory preserved", "보존" in r.stdout, r.stdout[-500:])

    # --- 설치 없는 PC에서는 정직하게 중단 ---
    r2 = subprocess.run([sys.executable, str(extract / "patch" / "patch_impl.py"),
                         "--home", str(tmp / "no_install")],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        env=dict(os.environ, PYTHONUTF8="1"))
    check("no install -> exit 3 with guidance", r2.returncode == 3 and "설치.bat" in r2.stdout,
          r2.stdout)

    print(f"\nALL {PASS} CHECKS PASSED (patch build + apply)")


if __name__ == "__main__":
    main()
