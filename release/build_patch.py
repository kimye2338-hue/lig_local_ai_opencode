# -*- coding: utf-8 -*-
"""기존 설치 위에 덮는 '패치파일' 빌더 — 설치파일(build_bundle)과 짝.

Run: py -3.11 release\\build_patch.py [--date YYYYMMDD] [--out DIR]

만드는 것: OpenCodeLIG_PATCH_<date>.zip
  패치.bat              더블클릭 한 번 — 파이썬 찾고 patch_impl 에 위임
  patch/patch_impl.py   실제 패치 로직 (아래 APPLY 절 참고)
  patch/setup_impl.py   런처 재생성 재사용 (release/setup_impl.py 사본)
  workspace-template/** 새 프로그램 파일 전체
  MANIFEST_SHA256.txt   전 파일 해시

패치 정책 (docs/PRODUCT_VISION §3.2, MEMORY_AND_SELF_EXTENSION §2):
  - 프로그램(workspace)만 교체한다. %USERPROFILE%\\OpenCodeLIG_USERDATA
    (기억/비밀/진단/감사)는 절대 쓰지도 지우지도 않는다.
  - 덮어쓰기 전에 달라진 파일만 OpenCodeLIG\\patch_backups\\<날짜>\\ 로 백업.
  - 투명한 zip (자가압축 exe/인코딩 payload 없음 — 백신 안전).

전체 재설치가 필요하면 build_bundle.py 의 설치파일을 쓴다. 이 패치는
이미 설치된 PC의 코드만 최신화한다.
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

INCLUDE_DIRS = ["workspace-template"]

EXCLUDE_SUBSTRINGS = [
    "lig-api.env",
    "__pycache__/",
    ".pyc",
    "/results/",     # 산출물/실측 흔적은 패치에 불필요 (설치본의 results 보존)
    ".git/",
]


def _is_secret_file(rel: str) -> bool:
    low = rel.lower()
    name = low.rsplit("/", 1)[-1]
    if name == "lig-api.env" or "/secrets/" in low:
        return True
    return name.endswith(".env") and not name.endswith(".env.example")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files() -> list[tuple[Path, str]]:
    items: list[tuple[Path, str]] = []
    for d in INCLUDE_DIRS:
        base = REPO_ROOT / d
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO_ROOT).as_posix()
            if any(sub in rel for sub in EXCLUDE_SUBSTRINGS):
                continue
            items.append((p, rel))
    return items


PATCH_BAT = (
    "@echo off\r\n"
    "rem OpenCodeLIG patch shim - finds Python 3.11 then delegates to patch_impl.py\r\n"
    "chcp 65001 >nul\r\n"
    "set PYTHONUTF8=1\r\n"
    "setlocal\r\n"
    "set \"HERE=%~dp0\"\r\n"
    "set \"PYEXE=\"\r\n"
    "py -3.11 --version >nul 2>&1 && set \"PYEXE=py -3.11\"\r\n"
    "if not defined PYEXE (\r\n"
    "    for %%P in (python python3.11 python3) do (\r\n"
    "        if not defined PYEXE (\r\n"
    "            for /f \"tokens=2\" %%V in ('%%P --version 2^>^&1') do (\r\n"
    "                echo %%V | findstr /b /c:\"3.11.\" >nul && set \"PYEXE=%%P\"\r\n"
    "            )\r\n"
    "        )\r\n"
    "    )\r\n"
    ")\r\n"
    "if not defined PYEXE (\r\n"
    "    echo [STOP] Python 3.11 not found. Open a new cmd and check: python --version\r\n"
    "    goto :the_end\r\n"
    ")\r\n"
    "%PYEXE% \"%HERE%patch\\patch_impl.py\"\r\n"
    ":the_end\r\n"
    "echo.\r\n"
    "pause\r\n"
)

PATCH_IMPL = '''# -*- coding: utf-8 -*-
"""OpenCodeLIG 패치 적용 — 프로그램만 교체, 기억/설정은 보존.

패치.bat 이 이 파일에 위임한다. stdlib only, 네트워크 없음.
"""
from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
import time
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]     # 패치 zip 을 푼 폴더
SRC = BUNDLE / "workspace-template"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default="", help="설치 홈 (기본 %USERPROFILE% — 테스트용)")
    a = ap.parse_args(argv)
    home = Path(a.home) if a.home else Path(os.environ.get("USERPROFILE", str(Path.home())))

    target = home / "OpenCodeLIG" / "workspace"
    userdata = home / "OpenCodeLIG_USERDATA"
    if not SRC.is_dir():
        print("[중단] 패치 구조가 아닙니다 — zip 을 통째로 푼 폴더의 패치.bat 으로 실행하세요.")
        return 2
    if not target.is_dir():
        print(f"[중단] 기존 설치를 찾지 못했습니다: {target}")
        print("       처음 설치라면 전체 번들(OpenCodeLIG_BUNDLE_*.zip)의 설치.bat 을 쓰세요.")
        return 3

    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_root = home / "OpenCodeLIG" / "patch_backups" / stamp
    updated = added = 0
    for src in sorted(SRC.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(SRC)
        dst = target / rel
        if dst.is_file():
            if filecmp.cmp(str(src), str(dst), shallow=False):
                continue
            bak = backup_root / rel
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(dst), str(bak))
            updated += 1
        else:
            added += 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))

    print(f"[1/3] 프로그램 갱신: 변경 {updated}개 (백업: {backup_root if updated else '불필요'}), 추가 {added}개")

    # 런처/전역 페르소나 재생성 (setup_impl 재사용 — 로직 중복 금지)
    sys.path.insert(0, str(BUNDLE / "patch"))
    try:
        import setup_impl
        setup_impl.install_global_brain(home, target)
        setup_impl.install_bin_launchers(home)
        print("[2/3] 런처(ocd/ai)·전역 페르소나 갱신 완료")
    except Exception as exc:  # noqa: BLE001 - 런처 재생성 실패해도 코드 패치는 유효
        print(f"[2/3] 런처 갱신 일부 실패({type(exc).__name__}) — 코드 패치는 적용됨")

    mem = userdata / "memory"
    print(f"[3/3] 기억/설정 보존 확인: {mem} {'(존재 — 그대로 유지됨)' if mem.is_dir() else '(아직 없음 — 첫 실행 때 생성)'}")
    print()
    print(" ==============================================")
    print("   패치 완료. 새 명령창에서 `ocd` 또는 바탕화면 [AI비서] 실행.")
    print(" ==============================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

FIRST_READ = ("OpenCodeLIG 패치 (30초)\r\n"
              "\r\n"
              "이미 설치된 PC의 프로그램만 최신으로 바꿉니다.\r\n"
              "기억/설정(OpenCodeLIG_USERDATA)은 절대 지워지지 않습니다.\r\n"
              "\r\n"
              "1. 이 zip 을 아무 폴더에 통째로 풉니다\r\n"
              "2. 패치.bat 더블클릭\r\n"
              "3. 새 명령창에서 아무 폴더든  ocd  입력 - 그 폴더 전용 비서가 뜹니다\r\n"
              "\r\n"
              "처음 설치라면 이 패치가 아니라 전체 번들(OpenCodeLIG_BUNDLE_*.zip)을 쓰세요.\r\n")


def build(date: str, out_dir: Path) -> Path:
    files = _iter_files()
    secret_hits = [rel for _p, rel in files if _is_secret_file(rel)]
    if secret_hits:
        raise SystemExit(f"[ABORT] secret-like files would be patched in: {secret_hits}")

    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"OpenCodeLIG_PATCH_{date}.zip"
    setup_impl_src = REPO_ROOT / "release" / "setup_impl.py"

    manifest = ["# MANIFEST_SHA256 — every archived file", f"# patch: {zip_path.name}", ""]
    print(f"packing {len(files)} workspace files ...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, rel in files:
            zf.write(p, rel)
            manifest.append(f"{_sha256(p)}  {rel}")
        zf.write(setup_impl_src, "patch/setup_impl.py")
        manifest.append(f"{_sha256(setup_impl_src)}  patch/setup_impl.py")
        for rel, text in (("패치.bat", PATCH_BAT),
                          ("patch/patch_impl.py", PATCH_IMPL),
                          ("처음_읽어주세요.txt", FIRST_READ)):
            data = text.encode("utf-8")
            zf.writestr(rel, data)
            manifest.append(f"{_sha256_bytes(data)}  {rel}")
        zf.writestr("MANIFEST_SHA256.txt", "\n".join(manifest) + "\n")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"built {zip_path}  ({size_mb:.1f} MB, {len(files)} files + patch scripts + MANIFEST)")
    return zip_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="unstamped", help="YYYYMMDD")
    ap.add_argument("--out", default=str(REPO_ROOT / "release" / "dist"))
    args = ap.parse_args(argv)
    build(args.date, Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
