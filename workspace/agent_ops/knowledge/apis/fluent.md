# ANSYS Fluent 2024R1 — 공식 API 참조

- 공식 출처: https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/flu_ug/flu_ug_BatchExecution.html, https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/pdf/Ansys_Fluent_Text_Command_List.pdf
- 검증상태: verified-from-official
- 확인일: 2026-07-06

## 핵심 객체/명령

### 배치 실행 명령줄 옵션
| 옵션 | 용도 |
|------|------|
| **fluent 3ddp** | 3D double precision 모드 |
| **-g** | GUI/그래픽스 비활성화 (배치 모드) |
| **-t4** | 4개 프로세서 병렬 실행 |
| **-i journal_file** | 저널 파일 입력 |
| **-hidden** | Windows 배치: 숨겨진 창 실행 |
| **-wait** | 완료까지 대기 (배치 스크립트용) |

### 저널 파일 명령
| 명령 | 용도 |
|------|------|
| **/file/read-case** | 케이스 파일 읽기 |
| **/file/read-data** | 데이터 파일 읽기 |
| **/solve/iterate** | 반복 계산 실행 |
| **/file/write-data** | 데이터 파일 저장 |
| **exit yes** | Fluent 종료 (저장 후) |

## 최소 동작 예제

### 배치 실행 명령줄 (Linux C-shell)
```bash
fluent 2d -g < inputfile > & outputfile &
```

### 배치 실행 명령줄 (Windows)
```batch
REM 저널 파일로 배치 모드 실행
fluent 3ddp -g -wait -i journal.jou

REM 또는 숨겨진 창으로 실행
fluent 3ddp -hidden -i journal.jou
```

### 저널 파일 (journal.jou)
```
; ANSYS Fluent 2024R1 저널 파일 최소 예제
; 주석은 세미콜론(;)으로 시작

; 케이스 파일 읽기
/file/read-case case.cas

; 데이터 파일 읽기 (선택)
/file/read-data data.dat

; 초기 설정
/define/boundary-conditions/inlet inlet-1 () velo-m normal-velocity 10

; 반복 계산 (100회)
/solve/iterate 100

; 데이터 저장
/file/write-data result.dat

; 로그 파일 저장
/file/start-transcript output.trn

; Fluent 종료
exit yes
```

출처: ANSYS Fluent User Guide - Batch Execution

## 자주 쓰는 작업

### 1. 기본 배치 실행 스크립트
```bash
# Linux/Mac
fluent 3ddp -g -i job1.jou > log1.txt 2>&1 &
fluent 3ddp -g -i job2.jou > log2.txt 2>&1 &

# Windows
fluent 3ddp -g -wait -i job1.jou
```

### 2. 병렬 처리 (멀티 프로세서)
```bash
# 4개 프로세서로 실행
fluent 3ddp -t4 -g -i mycase.jou

# 병렬 클러스터 실행
fluent 3ddp -nt 8 -g -i mycase.jou
```

### 3. 저널 파일에서 자동 로그 기록
```
; 출력 로그 시작
/file/start-transcript output.trn

; ... 계산 명령어들 ...

/solve/iterate 200

; 로그 저장 (자동)
```

### 4. 경계 조건 설정 예제
```
/file/read-case airfoil.cas

; 입구 경계: 유속 10 m/s
/define/boundary-conditions/inlet inlet 5 () velo-m normal-velocity 10

; 출구 경계: 압력 0
/define/boundary-conditions/outlet outlet 5 () pressure 0

; 벽: 무슬립
/define/boundary-conditions/wall wall 4 () wall-interaction no-slip

/solve/iterate 500
/file/write-data result.dat
exit yes
```

### 5. 케이스/데이터 파일 읽기-쓰기
```
; 사전 계산된 데이터로 시작
/file/read-case base.cas
/file/read-data previous_solution.dat

; 경계 조건 조정
/define/boundary-conditions/inlet inlet-1 () velo-m normal-velocity 15

; 추가 반복
/solve/iterate 100

; 결과 저장
/file/write-data updated_solution.dat
exit yes
```

## 주의/버전 유의점

- **GUI 필수 비활성화**: 배치 모드(-g)에서는 GUI 명령(메뉴 클릭 등) 불가, TUI/스키마 명령만 사용
- **저널 파일 구조**: 텍스트 인터페이스(TUI) 명령만 포함, 명령 순서 엄격
- **공백 민감도**: 저널 파일의 명령 구문이 엄격하므로 오타 주의
- **화면 출력 vs 로그**: -g 모드에서도 출력은 리다이렉션으로 캡처 가능 (> file.txt)
- **Exit Code**: 성공=0, 실패=0 아님 (배치 스크립트에서 확인 가능)
- **Windows -wait**: 배치 파일에서 Fluent 완료까지 대기 필수
- **주석**: 세미콜론(;)으로 시작하는 라인은 무시됨
- **도메인 설정**: /solver/set/... 명령으로 솔버 옵션 설정 가능 (병렬 프로세서, 모델 등)
