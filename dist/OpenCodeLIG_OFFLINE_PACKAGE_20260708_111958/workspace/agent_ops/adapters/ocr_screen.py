# -*- coding: utf-8 -*-
"""오프라인 화면 OCR 어댑터 (한/영).

목적: 브라우저/앱 자동화 중 "화면을 봐야만 알 수 있는" 상황(포털 SPA가 예상과
다르게 렌더링됨, 버튼/에러 메시지가 DOM 밖 이미지로만 있음)에서, 스크린샷을 찍어
글자를 읽어(OCR) LLM이 다음 행동을 판단하게 한다. 완전 오프라인.

설계 원칙:
  - **백엔드 플러거블·오프라인 우선**: 실행 시 네트워크 0. 사용 가능한 백엔드를
    자동 탐지해 쓰고, 없으면 명확히 "OCR 엔진 미반입"으로 보고(조용한 실패 금지).
    우선순위: RapidOCR(onnxruntime) → pytesseract(kor+eng) → (없음).
  - **표준 라이브러리 폴백 캡처**: mss/Pillow가 있으면 그걸로, 없으면 Windows
    PowerShell 스크린샷으로 캡처(무설치 폴백).
  - 결과는 텍스트 + 신뢰도 + 박스(가능 시). 산출 이미지는 진단 폴더에 남긴다.

action:
  execute("read_screen", {"region": [x,y,w,h]?, "lang": "korean+english"?, "save": true?})
  execute("read_image",  {"path": "...png", "lang": ...})
  execute("capabilities", {})
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from ..core import now
except Exception:  # 단독 실행/테스트 폴백
    from datetime import datetime

    def now() -> str:  # type: ignore
        return datetime.now().astimezone().isoformat(timespec="seconds")

ACTIONS = {"read_screen", "read_image", "capabilities"}

# 반입 경로 규약 (docs/기능/OCR_SCREEN.md, tools/README.md)
_ROOT = Path.home() / "OpenCodeLIG"
_TOOLS_OCR = Path(os.environ.get("LIG_OCR_DIR") or (_ROOT / "tools" / "ocr"))
_DIAG_DIR = Path(os.environ.get("LIG_DIAG_DIR") or (Path.home() / "OpenCodeLIG_USERDATA" / "diagnostics"))


# ----------------------------------------------------------------------------
# 백엔드 탐지
# ----------------------------------------------------------------------------
def _has_rapidocr() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


def _tesseract_exe() -> Optional[str]:
    bundled = _TOOLS_OCR / "tesseract" / "tesseract.exe"
    if bundled.exists():
        return str(bundled)
    found = shutil.which("tesseract")
    return found


def _has_pytesseract() -> bool:
    if not _tesseract_exe():
        return False
    try:
        import pytesseract  # noqa: F401
        return True
    except Exception:
        return False


def detect_backends() -> List[str]:
    backends: List[str] = []
    if _has_rapidocr():
        backends.append("rapidocr")
    if _has_pytesseract():
        backends.append("tesseract")
    return backends


# ----------------------------------------------------------------------------
# 스크린샷 캡처 (mss → Pillow → PowerShell 폴백)
# ----------------------------------------------------------------------------
def _capture(region: Optional[List[int]], out_path: Path) -> Dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 1) mss
    try:
        import mss  # type: ignore
        import mss.tools  # type: ignore
        with mss.mss() as sct:
            if region and len(region) == 4:
                mon = {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
            else:
                mon = sct.monitors[0]
            img = sct.grab(mon)
            mss.tools.to_png(img.rgb, img.size, output=str(out_path))
        return {"ok": True, "path": str(out_path), "via": "mss"}
    except Exception:
        pass
    # 2) Pillow ImageGrab (Windows/mac)
    try:
        from PIL import ImageGrab  # type: ignore
        bbox = None
        if region and len(region) == 4:
            bbox = (region[0], region[1], region[0] + region[2], region[1] + region[3])
        im = ImageGrab.grab(bbox=bbox)
        im.save(str(out_path))
        return {"ok": True, "path": str(out_path), "via": "pillow"}
    except Exception:
        pass
    # 3) PowerShell 폴백 (무설치)
    if sys.platform.startswith("win"):
        # region 이 지정되면 전체 화면 대신 그 영역만 캡처한다 — 조용히 전체를 찍어
        # LLM 이 '요청 영역의 텍스트'로 오인하는 것을 막는다.
        region_ok = bool(region) and len(region) == 4 and int(region[2]) > 0 and int(region[3]) > 0
        if region_ok:
            x, y, w, h = int(region[0]), int(region[1]), int(region[2]), int(region[3])
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
                f"$bmp=New-Object System.Drawing.Bitmap {w},{h};"
                "$g=[System.Drawing.Graphics]::FromImage($bmp);"
                f"$g.CopyFromScreen({x},{y},0,0,$bmp.Size);"
                f"$bmp.Save('{out_path.as_posix()}');"
            )
        else:
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
                "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
                "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
                "$g=[System.Drawing.Graphics]::FromImage($bmp);"
                "$g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size);"
                f"$bmp.Save('{out_path.as_posix()}');"
            )
        try:
            cp = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                capture_output=True, timeout=20)
            if out_path.exists():
                res = {"ok": True, "path": str(out_path), "via": "powershell"}
                # region 을 줬는데 무효 좌표라 전체를 찍은 경우 명시적으로 알린다.
                if region and not region_ok:
                    res["region_ignored"] = True
                return res
            return {"ok": False, "error": "powershell capture produced no file",
                    "stderr": (cp.stderr or b"")[:200].decode("utf-8", "replace")}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"powershell capture failed: {exc!r}"}
    return {"ok": False, "error": "no screenshot backend (mss/Pillow/PowerShell 모두 불가)"}


# ----------------------------------------------------------------------------
# OCR 실행
# ----------------------------------------------------------------------------
def _ocr_rapidocr(image_path: Path) -> Dict[str, Any]:
    from rapidocr_onnxruntime import RapidOCR  # type: ignore
    engine = RapidOCR()
    result, _ = engine(str(image_path))
    lines: List[Dict[str, Any]] = []
    texts: List[str] = []
    for item in result or []:
        box, text, score = item[0], item[1], item[2]
        texts.append(text)
        lines.append({"text": text, "score": float(score), "box": box})
    return {"ok": True, "engine": "rapidocr", "text": "\n".join(texts), "lines": lines}


def _ocr_tesseract(image_path: Path, lang: str) -> Dict[str, Any]:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    exe = _tesseract_exe()
    if exe:
        pytesseract.pytesseract.tesseract_cmd = exe
    tessdata = _TOOLS_OCR / "tesseract" / "tessdata"
    config = f'--tessdata-dir "{tessdata}"' if tessdata.exists() else ""
    text = pytesseract.image_to_string(Image.open(str(image_path)), lang=lang, config=config)
    return {"ok": True, "engine": "tesseract", "text": text, "lines": []}


_LANG_MAP = {
    "korean+english": "kor+eng", "kor+eng": "kor+eng",
    "korean": "kor", "english": "eng", "eng": "eng", "kor": "kor",
}


def _run_ocr(image_path: Path, lang: str) -> Dict[str, Any]:
    backends = detect_backends()
    if not backends:
        return {"ok": False, "error": "OCR 엔진 미반입",
                "hint": "tools/ocr 에 RapidOCR 또는 Tesseract(kor+eng) 반입 필요 — docs/기능/OCR_SCREEN.md",
                "backends": []}
    if "rapidocr" in backends:  # 언어 무관, 한/영 동시
        try:
            return _ocr_rapidocr(image_path)
        except Exception as exc:  # noqa: BLE001
            if "tesseract" not in backends:
                return {"ok": False, "error": f"rapidocr 실패: {exc!r}", "backends": backends}
    tess_lang = _LANG_MAP.get(str(lang or "").lower(), "kor+eng")
    try:
        return _ocr_tesseract(image_path, tess_lang)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"tesseract 실패: {exc!r}", "backends": backends}


# ----------------------------------------------------------------------------
# 공개 진입점
# ----------------------------------------------------------------------------
def execute(action: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    action = str(action or "")
    if action == "capabilities":
        return {"ok": True, "backends": detect_backends(),
                "screenshot": True, "tools_ocr_dir": str(_TOOLS_OCR),
                "note": "backends 가 비면 tools/ocr 에 엔진 반입 필요"}

    if action == "read_image":
        path = Path(str(options.get("path") or ""))
        if not path.exists():
            return {"ok": False, "error": f"이미지 없음: {path}"}
        res = _run_ocr(path, options.get("lang", "korean+english"))
        res["source_image"] = str(path)
        res["timestamp"] = now()
        return res

    if action == "read_screen":
        stamp = now().replace(":", "").replace("-", "").replace("+", "_")
        shot = _DIAG_DIR / f"ocr_screen_{stamp}.png"
        cap = _capture(options.get("region"), shot)
        if not cap.get("ok"):
            return {"ok": False, "error": "스크린샷 실패", "detail": cap}
        res = _run_ocr(Path(cap["path"]), options.get("lang", "korean+english"))
        res["source_image"] = cap["path"]
        res["capture_via"] = cap.get("via")
        res["timestamp"] = now()
        if not options.get("save", True):
            try:
                Path(cap["path"]).unlink()
                res["source_image"] = None
            except Exception:
                pass
        return res

    return {"ok": False, "error": f"알 수 없는 action: {action}", "actions": sorted(ACTIONS)}


if __name__ == "__main__":
    import json
    act = sys.argv[1] if len(sys.argv) > 1 else "capabilities"
    print(json.dumps(execute(act, {}), ensure_ascii=False, indent=2))
