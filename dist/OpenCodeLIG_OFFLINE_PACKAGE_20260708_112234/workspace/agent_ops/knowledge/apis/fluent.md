---
title: ANSYS Fluent 2024R1 배치 저널/TUI 레퍼런스
domain: fluent
aliases: fluent, 플루언트, ansys, journal, jou, cfd, 유동해석, 열유체, tui, 배치, 저널
sources: [ansyshelp.ansys.com v242 (2024R2, R1→R2 변경부록 대조), Fluent Text Command List]
verified: true
confidence: medium
version: "2024R1"
reviewed: 2026-07-07
---

# ANSYS Fluent 2024R1 배치 저널/TUI 자동화

> 대상: **2024R1**, `fluent 3ddp -g -i journal.jou` 헤드리스. TUI 트리·문법은 버전 안정적이나
> 세부 프롬프트 시퀀스는 대화형 캡처로 검증 권장.

## ⚠️ 절대 규칙 (저널 생성 전 항상)

1. **저널 맨 앞에 배치 옵션** — 예기치 못한 확인창이 배치를 무한 정지시키는 걸 막음:
   ```
   /file/set-batch-options yes yes yes
   ```
   순서: Confirm-Overwrite / Hide-Questions(yes 권장) / Exit-on-Error(yes 권장). **케이스에 저장 안 됨 → 매번 명시.**
   Exit-on-Error 종료코드: 0=정상, 1=명령/입력 오류, 2=라이선스.
2. **Windows `-g` ≠ 완전 비대화형** — 작업표시줄 최소화일 뿐. 완전 무인은 `-hidden`.
3. **콘솔 출력 파일 저장** — Windows는 셸 리다이렉트 안 됨 → 저널 안에 `/file/start-transcript "log.trn"`.
4. **프롬프트 시퀀스 검증** — velocity-inlet/materials 등은 모델 조합(에너지·다상 여부)에 따라 질문
   수·순서가 달라짐. 초안 생성 후 대화형 1회 + `/file/start-journal "capture.jou"`로 실제 순서 캡처·대조.
5. 저널엔 **TUI 명령만**(GUI 명령 불가). `;`로 시작하는 줄은 주석.

## 배치 실행 (명령행)
```
fluent 3ddp -g -i journal.jou          REM 3D 배정밀도, GUI최소화, 저널 실행
fluent 3ddp -t4 -g -i journal.jou       REM 4프로세스 병렬
fluent 3ddp -hidden -i journal.jou      REM 완전 숨김 비대화형
fluent 3ddp -g -wait -i journal.jou     REM DOS 배치가 종료까지 대기
```
`2ddp/3ddp`=2D/3D 배정밀도, `2d/3d`=단정밀도. `-t<N>`=병렬수.

## TUI 문법 기본
- 메뉴는 디렉터리처럼 계층. 전체경로로 바로 진입(`/file/read-case`). 벗어나기 `q`.
- 프롬프트 `[기본값]`은 Enter로 기본값 사용. y/n = yes/no. Scheme 불리언 `#t`/`#f`.
- **문자열**(제목 등)은 큰따옴표 필수. **심볼**(zone/surface/material 이름)은 따옴표 없이, 와일드카드
  `* > ^` 로 일괄 선택 가능. 변수 치환 없음(리터럴).
- 저널은 축약형 대신 **전체 명령이름** 사용(버전간 충돌 방지). `(`로 시작하면 Scheme 평가.

## 작업별 저널 코드

```
; 케이스/데이터 읽기
/file/read-case-data "model.cas.h5"
; 점성 모델 (예: k-epsilon Realizable / k-omega SST)
/define/models/viscous/ke-realizable yes
; /define/models/viscous/kw-sst yes
; 재료 (인자 순서는 대화형 캡처 검증 권장)
/define/materials/change-create air air yes constant 1.225 no no yes constant 1.7894e-05 no no no
; 경계조건 (⚠️ 프롬프트 순서 모델 의존 — 캡처 검증)
/define/boundary-conditions/velocity-inlet inlet yes no yes yes no 10 no 300 no yes 5 10
/define/boundary-conditions/pressure-outlet outlet yes no 0 no 300 no yes no no yes 5 10
; 초기화(hybrid) + 반복 + 수렴기준
/solve/initialize/hyb-initialization
/solve/monitors/residual/convergence-criteria 1e-4 1e-4 1e-4 1e-4 1e-4 1e-4
/solve/iterate 500
; 저장 + 내보내기 + 보고
/file/write-case-data "result.cas.h5" yes
/file/export/ensight-gold "result" () yes velocity-magnitude pressure () yes
/report/surface-integrals/area-weighted-avg outlet () pressure yes "pressure_avg.txt"
/report/forces/wall-forces yes wall-1 () 1 0 0 yes "forces.txt"
/report/fluxes/mass-flow yes inlet outlet () yes "massflow.txt"
```

## 여러 케이스 배치 (Scheme 루프)
```scheme
(for-each
  (lambda (c)
    (ti-menu-load-string (string-append "/file/read-case-data \"" c "\""))
    (ti-menu-load-string "/solve/iterate 500")
    (ti-menu-load-string (string-append "/file/write-case-data \"" c "-done\" yes")))
  (list "run1.cas.h5" "run2.cas.h5"))
```
(Scheme 표준 기능 — 공식 예제 아님, 소규모 테스트 권장.)

## 신뢰도 메모
v241(2024R1) 공개 페이지가 로그인 벽으로 막혀 v242 + R1→R2 변경 부록 대조로 구성. TUI 트리/문법은
신뢰도 높음. **velocity-inlet/pressure-outlet/materials 인자 순서와 Scheme 루프는 추정** → 대화형
캡처로 반드시 검증. 사내 ANSYS 포털 계정 있으면 R1 원문 1회 대조 권장.
