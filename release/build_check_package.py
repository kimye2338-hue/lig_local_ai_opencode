# -*- coding: utf-8 -*-
"""Build the one-shot company CHECK package (env + runtime + real pipeline).

Run: py -3.11 release\\build_check_package.py [--date YYYYMMDD] [--out DIR]

Bundles probe/company_check.py together with the agent_ops runtime
(workspace-template) into a single zip so that, on the company PC, one run of
company_check.py auto-detects the runtime and checks everything at once:
section 0 (doctor + mock work + real agent E2E) plus gateway/apps/scenarios.

This is intentionally lean (source only — agent_ops core is stdlib; the company
already has Python 3.11 + pywin32 + the apps). No wheels, no models, no secrets.
Pure stdlib. No network.
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

EXCLUDE = ("__pycache__/", ".pyc", "/results/", "/diagnostics/", "/secrets/",
           "lig-api.env", "/모의_결과/", ".git/")

README = """# OpenCodeLIG 회사 환경+런타임 종합 점검 (이번 한 번에 다 점검)

이 zip 하나로 **환경 + 현재 빌드 런타임 + 실제 게이트웨이 파이프라인**까지 한 번에 점검합니다.

## 실행
1. 이 zip을 회사 PC에 풀기.
2. 압축 푼 폴더에서:
   ```bat
   py -3.11 company_check.py
   ```
   - 더블클릭도 가능(끝에 Enter 대기). 빠르게: `company_check.py --quick`
3. 생기는 **`company_check_result.md` 하나**만 전달.

## 무엇이 자동 점검되나
- 섹션 0 (현재 빌드 런타임): doctor + mock work E2E + **real agent E2E**
  (lig-api.env 있으면 실제 게이트웨이 tool-use 루프)
- 섹션 1 Gateway / 2 앱·COM / 3 OpenCode / 4 Office 정책 / 5 앱경로 / 6 업무 시나리오 6종

## real 점검까지 하려면 (선택, 권장)
`%USERPROFILE%\\OpenCodeLIG_USERDATA\\secrets\\lig-api.env` 에 게이트웨이 값이 있으면
섹션 0의 real agent가 실제로 돕니다. 없으면 그 항목만 자동 생략(나머지는 정상 점검).
lig-api.env 는 절대 커밋/반출하지 마세요 — 결과 .md에는 값이 마스킹됩니다.

## 안전
stdlib만 사용(런타임 core도 stdlib). 회사에 이미 있는 Python 3.11/pywin32/앱을 재활용.
secret/host/사용자명 자동 마스킹. 위험 검사는 하위 프로세스 격리+타임아웃.
"""


def _excluded(rel: str) -> bool:
    if rel.endswith(".env") and not rel.endswith(".env.example"):
        return True
    return any(s in rel for s in EXCLUDE)


def build(date: str, out_dir: Path) -> Path:
    top = f"OpenCodeLIG_CHECK_FULL_{date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    zp = out_dir / f"{top}.zip"

    items: list = [(REPO_ROOT / "probe" / "company_check.py", f"{top}/company_check.py")]
    base = REPO_ROOT / "workspace-template"
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel = "workspace-template/" + p.relative_to(base).as_posix()
        if _excluded(rel):
            continue
        items.append((p, f"{top}/{rel}"))

    secret_hits = [arc for _p, arc in items
                   if arc.rsplit("/", 1)[-1] == "lig-api.env" or "/secrets/" in arc]
    if secret_hits:
        raise SystemExit(f"[ABORT] secret files would be packaged: {secret_hits}")

    manifest = ["# MANIFEST_SHA256", ""]
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, arc in items:
            zf.write(p, arc)
            manifest.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {arc}")
        readme_bytes = README.encode("utf-8")
        zf.writestr(f"{top}/README_추가.md", readme_bytes)
        manifest.append(f"{hashlib.sha256(readme_bytes).hexdigest()}  {top}/README_추가.md")
        zf.writestr(f"{top}/MANIFEST_SHA256.txt", "\n".join(manifest) + "\n")

    size_mb = zp.stat().st_size / (1024 * 1024)
    outer = hashlib.sha256(zp.read_bytes()).hexdigest()
    print(f"built {zp}  ({size_mb:.1f} MB, {len(items) + 2} files)")
    print(f"OUTER SHA256: {outer}")
    return zp


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="unstamped")
    ap.add_argument("--out", default=str(REPO_ROOT / "release" / "dist"))
    args = ap.parse_args(argv)
    build(args.date, Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
