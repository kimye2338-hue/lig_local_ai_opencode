# company_check 종합 계측 — 회사 PC (2026-07-03 17:07, 사용자 제공, sanitized)

전 항목 실측. 남은 미지수 대부분 해소. (원 출력의 한글 mojibake는 의미 복원, 계측기
인코딩 버그는 커밋에서 수정 완료)

## 1. Gateway (LLM) — 전부 성공

| 항목 | 결과 |
|------|------|
| coding / chat / fallback | 200 / 93ms / 93ms / 140ms |
| **function calling (tools)** | **accepted=True, tool_calls_present=True, finish_reason="tool_calls"** — EXAONE이 read_file을 native tool_calls로 반환 |
| streaming | 지원 (`data:` SSE) |
| 512토큰 지연 | 3717ms (H100, 실사용 양호) |
| think_on 라우트 | 존재 (200) — reasoning 분리 가능 |
| /models | 200, id="EXAONE-4.5-33B-vibe_coding_think_off" (vllm 서빙) |
| 프롬프트 tool-call 원문 | `{"tool":"read_file","args":{"path":"메모.txt"}}` (텍스트 파싱 fallback도 정상) |

**결론: 파서 리스크 소멸.** native function calling 사용 가능 → P11은 native tools 1차.

## 2. 앱/COM 실동작 — 전부 성공

| 앱 | 결과 |
|----|------|
| Excel 실왕복 + **VBProject 접근** | OK — **가능 (매크로 자동 주입 OK)**, Excel 16.0 |
| Outlook COM | OK — 16.0.0.5507 |
| 한글(HWP) COM | OK — 10.0.0.14727 |
| SolidWorks COM | OK — 접속 성공 |
| MATLAB -batch | OK — exit 0, "2" 출력, **22.1초** (라이선스+기동 포함) |
| Chrome CDP 실기동 | OK — Chrome/148.0.7778.217 |

**결론: P15(Excel 자동주입)·P16(MATLAB/HWP/SW) 실행 어댑터의 실기 전제가 전부 확인됨.**

## 3. OpenCode 기동 / 느린 창

- `--version`: cold 1.3s / warm 1.0s → **exe 자체는 빠름**. 느린 건 TUI 초기화 단계.
- `OPENCODE_PURE`/`DISABLE_DEFAULT_PLUGINS`/`NO_UPDATE_NOTIFIER` = 전부 False,
  workspace opencode.json autoupdate 미설정 → **현재 구 런처로 실행 중**.
- build marker: capabilities_py=True (신버전 코드), legacy lig_diag=없음, proxy 8765=없음.
- **판정: 느림 원인은 TUI 초기화(플러그인/업데이트 확인). 새 아티팩트의 강화 런처
  (잔류 정리 + PURE + 플러그인 차단 + autoupdate:false)로 개선 예상 → 재설치 후 재측정.**

## 4. 앱 경로/정책 (확정)

- Excel AccessVBOM=1/VBAWarnings=1/정책잠금 없음. Word/PPT/Outlook은 키 없음(기본).
- MATLAB R2024a, AutoCAD `C:\AutoCAD 2019\{accoreconsole,acad}.exe`,
  Fluent v241, Chrome, 전 Office/HWP/SolidWorks 설치 확인. pywin32·py3.11.3 기설치.
