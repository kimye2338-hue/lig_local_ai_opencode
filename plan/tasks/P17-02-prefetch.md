# P17-02 — 의존성 prefetch + SHA256 확정

| 항목 | 값 |
|------|-----|
| 단계 | P17 (MASTER_PLAN §4 P17 작업 항목 1) |
| 담당 | codex |
| 선행 | P16-04 (필요 목록 확정 후) |
| 환경 | **INTERNET 필수** (집/개발 PC) |

## 목표
회사 반입에 필요한 모든 외부물을 실제로 내려받아 SHA256과 함께 확정한다.
용량 제한 없음 (사용자 확정).

> **실측 반영 (2026-07-03)**: 회사 PC에 Python 3.11.3 + pywin32가 **이미 설치**되어
> 있음 (probe/results/ env). wheel은 재현성 위해 그대로 반입하되, setup.bat은 기존
> 설치를 감지하면 스킵하도록.

## 작업 항목
1. `release/dependencies.json`의 PENDING_PREFETCH 전 항목 해소 + 신규 항목 추가:
   - pywin32 (py3.11 win_amd64 wheel), openpyxl(+의존 et_xmlfile), python-pptx(+의존)
   - llama.cpp server (Windows 릴리스 zip) + **Qwen2.5-7B-Instruct GGUF Q4_K_M**
     (+ 여유 있으면 14B — 사내 PC 16GB VRAM 백업 서빙용)
   - whisper.cpp (Windows 릴리스) + ggml-medium 모델 (P20 대비 선반입)
   - ffmpeg 단일 exe
2. 각 항목: 다운로드 → `certutil -hashfile <파일> SHA256` → manifest에
   {name, version, url, sha256, size, purpose, license} 기록. 다운로드 파일 자체는
   `release/prefetch/`(디렉터리는 .gitignore 등록 — **바이너리 커밋 금지**)에 보관.
3. `release/verify_prefetch.py` (stdlib): manifest의 전 항목이 prefetch/에 존재+해시 일치
   검사. `tests/test_release_manifest.py`: manifest 스키마 검사(전 항목 sha256/url 존재,
   PENDING_PREFETCH 0건) — 파일 존재 검사는 prefetch 있는 환경에서만(없으면 SKIP).

## 검증 명령
```bat
py -3.11 release\verify_prefetch.py
py -3.11 tests\test_release_manifest.py
(회귀 9개 전부)
```

## DoD
- [ ] PENDING_PREFETCH 0건, 전 항목 sha256 기록
- [ ] verify_prefetch 전 항목 통과 (출력 첨부)
- [ ] 바이너리 git 미커밋 (.gitignore 확인 — git status 증빙)
- [ ] 라이선스 필드 기록 (재배포 가능성 확인)

## 금지
- 비공식 미러/신뢰 불가 URL 사용 금지 (공식 릴리스/PyPI만).
- 모델·바이너리 git 커밋 금지.
