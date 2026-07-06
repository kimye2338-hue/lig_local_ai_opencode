# AutoCAD 2019 — 공식 API 참조

- 공식 출처: https://help.autodesk.com/cloudhelp/2019/ENU/AutoCAD-Customization/, https://knowledge.autodesk.com/support/autocad/learn-explore/caas/CloudHelp/cloudhelp/2019/ENU/AutoCAD-AutoLISP/
- 검증상태: verified-from-official
- 확인일: 2026-07-06

## 핵심 객체/명령

### Script (.scr) 명령
| 명령 | 용도 |
|------|------|
| **OPEN** | 도면 파일 열기 |
| **SAVEAS** | 파일 다른 이름으로 저장 |
| **EXIT** | AutoCAD 종료 |
| **QUIT** | AutoCAD 종료 |
| **ZOOM** | 화면 확대/축소 |
| **LAYER** | 레이어 관리 |

### AutoLISP 함수
| 함수 | 용도 |
|------|------|
| **(defun name (args) ...)** | 함수 정의 |
| **(command "CMD" arg1 ...)** | AutoCAD 명령 실행 |
| **(autoload "file" '("cmd1" "cmd2"))** | 필요시 파일 로드 |
| **(S::STARTUP)** | 도면 초기화 후 실행 함수 |

## 최소 동작 예제

### .scr 스크립트 파일 (Notepad)
```
; AutoCAD 2019 최소 스크립트
; 각 줄은 명령어, 공백=Enter, 빈 줄도 유의
OPEN
C:\drawings\test.dwg

ZOOM
A

SAVEAS
test_new.dwg

EXIT
yes
```
출처: Autodesk Knowledge Network - About Scripts

### AutoLISP 기본 예제
```lisp
; AutoCAD 2019 AutoLISP 최소 예제
(defun c:HELLO ()
  (command "circle" PAUSE 100)
  (princ "\nCircle created.")
  (princ)
)

; 시작 시 실행 (도면 초기화 후)
(defun S::STARTUP ()
  (command "undefine" "hatch")
)

; 필요시에만 로드
(autoload "mycommands" '("MYCMD1" "MYCMD2"))
```

## 자주 쓰는 작업

### 1. 배치 스크립트 생성 및 실행
```
; batch.scr - 여러 도면 처리
OPEN
drawing1.dwg
PURGE
A
SAVEAS
drawing1_cleaned.dwg

OPEN
drawing2.dwg
PURGE
A
SAVEAS
drawing2_cleaned.dwg

EXIT
yes
```
명령줄: `acad.exe /b batch.scr`

### 2. 파일 경로 처리
```
; 공백이 있는 경로는 따옴표로 감싼다
OPEN
"C:\My Documents\drawing file.dwg"

SAVEAS
"C:\output\result file.dwg"
```

### 3. AutoLISP 함수 정의
```lisp
(defun c:DRAWSQUARE (/ pt size)
  (setq pt (getpoint "\nPick first corner: "))
  (setq size (getdist pt "\nEnter size: "))
  (command "rectangle" pt (list (+ (car pt) size) (+ (cadr pt) size)))
  (princ)
)
```

### 4. 시작 파일 자동 로드
```lisp
; acaddoc.lsp (각 도면 열기시마다 자동 실행)
(defun-q S::STARTUP ()
  (princ "\nLoading custom startup functions...")
  ; 커스텀 명령 정의
)
```

## 주의/버전 유의점

- **공백 처리**: 스크립트에서 "각 공백이 유의미"하므로 ENTER 대신 공백 사용
- **마지막 줄**: 스크립트 파일은 반드시 빈 줄로 끝나야 한다
- **댓글**: 세미콜론(;)으로 시작하는 줄은 무시됨
- **PAUSE**: 스크립트 일시정지, 사용자 입력 대기
- **파일명 인용**: 경로/파일명에 공백이 있으면 "따옴표"로 반드시 감싼다
- **GUI 대화상자**: 스크립트는 대화상자 명령 실행 불가, 하이픈 접두사 사용 (예: `-INSERT` 대신 `INSERT`)
- **AutoLISP 버전**: 2014+ 보안 모드에서는 신뢰할 수 있는 파일 위치에서만 실행
