# gateway 2차 실측 — 회사 PC (2026-07-03 16:27, 사용자 제공, host sanitized)

## 발견 (404 원인 확정)

- 경로 변형 9종 전부 404였고, 응답 본문이 **Apache/2.4.52 (Ubuntu), Port 80** 오류
  페이지 — 즉 LLM 백엔드가 아니라 **80포트 웹서버가 직접 404**를 반환.
- 옛 저장 설정(구 히스토리) 실증과 대조한 결과: 라우트에 **`/gateway/` 접두가 누락**
  되어 있었음. 올바른 형태:
  `{BASE}/gateway/EXAONE-4.5-33B-default_think_off/v1/chat/completions`
- 조치: `_ROUTE_DEFAULTS`와 env.example 기본값에 `/gateway/` 접두 반영 (코드 커밋).
  기존 설치는 lig-api.env에 `LIG_ROUTE_*` 3줄 추가만으로 해결 (P09-01 env 오버라이드).
- 남은 확인: `default_think_off`만 원본 실증 — vibe_coding/Qwen 라우트 실존 여부는
  회사 재실측(3라우트 ping)으로 확정. → 200 확인 전까지 company validation pending.

## AutoCAD 확정 (같은 날 사용자 확인)

- `C:\AutoCAD 2019\accoreconsole.exe` **존재 확인** (467,840 bytes, 2018-09-14 빌드)
- `acad.exe` 동일 폴더. 실행 방식: `/p <회사프로파일> /product ACADM` (Mechanical)
- → P16-02 AutoCAD 배치 자동화 경로 확정, "미발견" 리스크 해소.

## 교훈 (probe 품질)

- 약식 스크립트는 응답 본문 내 hostname을 마스킹하지 못했음 — 정식 probe v2는
  netloc을 secrets에 포함해 본문까지 마스킹함. **회사 반출물은 정식 probe 사용.**
