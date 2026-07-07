---
title: AutoCAD 2019 배치/스크립트 자동화 레퍼런스
domain: autocad
aliases: autocad, 오토캐드, dwg, accoreconsole, autolisp, .scr, 도면, 스크립트, 배치, entmake
sources: [help.autodesk.com/cloudhelp/2019/ENU/, Autodesk University BES227196, Autodesk 공식 블로그]
verified: true
confidence: medium
version: "2019"
reviewed: 2026-07-07
---

# AutoCAD 2019 배치/스크립트 자동화

> 대상: AutoCAD **2019**, accoreconsole.exe 헤드리스 + .scr 스크립트 + AutoLISP.

## ⚠️ 절대 규칙 (스크립트 생성 전 항상)

1. **accoreconsole.exe는 미문서화 도구** — Autodesk 정식 커맨드 레퍼런스에 없음(공식 블로그/AU
   클래스에서만). `/i`,`/s` 스위치는 널리 검증됐지만 하위호환 공식 보증 없음. 새 스위치는 실제
   실행으로 확인.
2. **헤드리스 = 대화상자 명령 금지** — 반드시 하이픈 버전(`-INSERT`, `-LAYER`, `-PLOT`, `-PURGE`).
   대화상자 버전은 응답 대기하다 무한 hang.
3. **스크립트의 모든 공백(space)=Enter** — 공백 개수가 명령 프롬프트 단계와 정확히 일치해야 함.
   불일치 시 다음 입력 무한 대기(hang)가 최대 원인.
4. **마지막 줄은 반드시 빈 줄** — 없으면 마지막 명령 유실(공식 명시).
5. **명시적 저장 필수** — 스크립트 끝에 `QSAVE`/`SAVEAS`. 없으면 변경 소실.
6. 주석은 `;`로 시작. 파일명에 공백이면 큰따옴표. 로케일 소수점(콤마) 주의(좌표 콤마와 충돌).

## accoreconsole 배치 실행
```
accoreconsole.exe /i <input.dwg> /s <script.scr>
```
- 경로: `C:\Program Files\Autodesk\AutoCAD 2019\accoreconsole.exe`
- 정식 AutoCAD 라이선스 필요. PNGOUT/JPGOUT 등 이미지 출력은 헤드리스서 실패 사례 있음 → 벡터/문서
  출력(EXPORTPDF/DXFOUT)을 우선.
- 성능: 대량 작업 전 `UNDO Control None`, 끝나면 `UNDO Control All`(공식 권장).

## .scr 문법 예시 (공백=Enter 규칙 적용)
```
; 절대좌표 사각형(LINE)
LINE 0,0 100,0 100,50 0,50 c
; 폭 지정 폴리라인
PLINE 0,0 W 2 2 100,0 100,50
CIRCLE 50,50 25
TEXT 10,10 5 0 Hello World

```
(각 줄 뒤 공백 1개 = Enter. 옵션 많은 명령은 GUI 커맨드 히스토리를 복사해 시퀀스 확인 후 SCR화 — 공식 권장 워크플로우.)

레이어/정리:
```
-LAYER M NEWLAYER C 8 NEWLAYER LT Continuous NEWLAYER 
-PURGE A * N
```
(`-LAYER`: M=Make&현재화, C=Color, LT=Linetype, 마지막 빈입력 종료. `-PURGE A * N`: 모든 미사용 확인없이 정리.)

내보내기: `DXFOUT`(파일명→버전), `EXPORTPDF`, `EXPORT`(형식 프롬프트). 대화상자 `PLOT` 금지 → `-PLOT`.

## AutoLISP 핵심 (헤드리스 로직에 최적)

**entmake — 대화상자 없이 엔티티 직접 생성** (헤드리스 최선):
```lisp
(entmake '((0 . "CIRCLE") (62 . 3) (10 4.0 4.0 0.0) (40 . 1.0)))   ; 녹색 원(공식 예제)
(entmake (list '(0 . "LINE") '(8 . "0") (cons 10 '(0.0 0.0 0.0)) (cons 11 '(100.0 0.0 0.0))))
```
- DXF 그룹코드 dotted-pair 리스트. 존재 않는 레이어명 주면 자동 생성. VIEWPORT는 생성 불가.

**ssget — 헤드리스 선택(대화식 금지, 필터/전체선택)**:
```lisp
(setq ss (ssget "X" '((0 . "CIRCLE") (8 . "0"))))   ; "X"=도면 전체
```

**ActiveX(vla-)**:
```lisp
(vl-load-com)
(setq acadDoc (vla-get-ActiveDocument (vlax-get-acad-object)))
(vlax-for obj (vla-get-ModelSpace acadDoc) ... )   ; 모델스페이스 순회
```

**표준 에러 핸들링**:
```lisp
(defun c:MYCMD (/ *error* old)
  (defun *error* (msg) (if (/= msg "Function cancelled") (princ (strcat "\n오류: " msg)))
    (setvar "CMDECHO" old) (princ))
  (setq old (getvar "CMDECHO")) (setvar "CMDECHO" 0)
  ;; 작업
  (setvar "CMDECHO" old) (princ))
```

## 자주 필요한 작업 패턴
1. **좌표리스트→폴리라인**: LISP `entmake`로 LWPOLYLINE(90=정점수, 10=정점)이 SCR PLINE보다 안전(공백오류 없음).
2. **블록 삽입**: `-INSERT 블록명 삽입점 X축척 Y축척 회전각`.
3. **속성 추출**: `-EATTEXT`는 템플릿(.dxe) 필요 → 대신 LISP `vlax-for`+`vla-GetAttributes`+`write-line`으로 CSV 직접.
4. **배치 플롯/PDF**: `-PLOT` 또는 `EXPORTPDF`/`DXFOUT`.
5. **레이어 정리**: `-LAYER` + `-PURGE A * N`.

## 신뢰도 메모
공식 2019 문서(About Command Scripts, LAYER, EXPORT, entmake/ssget/vlax) 기반. accoreconsole 자체는
미문서화가 최대 리스크. HATCH/MTEXT/치수 SCR 상세는 미확인. AI 생성 스크립트는 "사전에 GUI 또는
accoreconsole 소규모 테스트로 검증" 문구를 항상 포함할 것.
