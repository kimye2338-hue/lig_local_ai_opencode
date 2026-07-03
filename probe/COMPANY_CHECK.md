# company_check.py — 회사 PC 종합 계측기 (파일 하나)

다음 회사 방문에서 남은 미지수를 **한 번에** 측정하는 단일 파일 도구.

## 쓰는 법

1. `probe/company_check.py` **하나만** 회사 PC로 반입 (USB 등).
2. 실행 (사전에 `lig-api.env`가 있으면 gateway까지 측정됨):
   ```bat
   py -3.11 company_check.py
   ```
   - 빠르게(gateway+환경만, 앱/COM/MATLAB 생략): `py -3.11 company_check.py --quick`
   - 더블클릭도 가능(끝에 Enter 대기).
3. 같은 폴더에 생기는 **`company_check_result.md` + `.json`** 두 파일을 전달.

## 측정 항목

| 구분 | 내용 |
|------|------|
| Gateway | 3라우트 응답, **function calling(tools) 지원 여부**, tool-call 원문, 스트리밍, 512토큰 지연, think_on 라우트 존재, /models |
| 앱 COM 실동작 | **Excel 실왕복 + VBProject 접근**(매크로 자동주입 실동작), Outlook/HWP/SolidWorks 접속, MATLAB `-batch` 실실행, Chrome CDP 실기동 |
| OpenCode | `--version` cold/warm 시간(느림 판정), 구버전 proxy(8765)·lig_diag 잔재, 신버전 표식, 강화 env 적용 여부 |
| 환경 | OS/RAM/디스크/pywin32, 앱 설치 경로, Office 매크로 보안 정책 |

## 안전

- stdlib만 사용 (pywin32는 있으면 COM 검사, 없으면 스킵).
- gateway host / API key / 사용자명 / 컴퓨터명 **자동 마스킹** + 파일 쓰기 직전 재검사.
- 멈출 수 있는 검사(COM/앱/브라우저/MATLAB)는 **하위 프로세스로 격리 + 타임아웃 회수** —
  본체는 절대 hang되지 않는다 (집 PC full 모드 8검사 전부 정상 종료 확인).
- 원본 파일 불가침 — Excel 검사는 임시 폴더의 새 파일에서만.

## 결과가 결정하는 것

- function calling True → P11은 native tools 경로를 1차로 측정 / False → 텍스트 파싱 유지
- Excel VBProject 접근 가능 → P15-02 자동 주입 확정
- MATLAB/Chrome 실동작 → P16/P12 어댑터 available 전환 근거
- OpenCode 기동 시간 → "느린 창" 종결 판정
