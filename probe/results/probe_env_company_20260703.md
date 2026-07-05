# 환경 probe 결과 — 회사 PC (2026-07-03 16:00:33, 사용자 제공)

- OS: Windows-10-10.0.19044-SP0 / Python 3.11.3 / RAM 127.9GB / 디스크 여유 261.1GB
- pywin32: True (이미 설치됨 — 반입 의존성 감소)

## 자동화 대상 앱

- excel: {"installed": true, "curver": "Excel.Application.16"}
- word: {"installed": true, "curver": "Word.Application.16"}
- powerpoint: {"installed": true, "curver": "PowerPoint.Application.16"}
- outlook: {"installed": true, "curver": "Outlook.Application.16"}
- hwp: {"installed": true, "curver": "HWPFrame.HwpObject.2"}
- solidworks: {"installed": true, "curver": ""}
- chrome: {"installed": true, "path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"}
- matlab_exe: "C:\\Program Files\\MATLAB\\R2024a\\bin\\matlab.exe"
- accoreconsole_exe: ""   ← **미발견: AutoCAD 설치 여부/경로 확인 필요 (P16-02 영향)**
- fluent_exe: "C:\\Program Files\\ANSYS Inc\\v241\\fluent\\ntbin\\win64\\fluent.exe"

## Office 매크로 보안 정책

- excel: {"office_ver_key": "16.0", "AccessVBOM": "1", "VBAWarnings": "1"}
  ← **매크로 자동 주입 가능 + 그룹 정책 잠금 없음 (P15-02: run_macro_file이 1차 경로)**
- word / powerpoint / outlook: 키 없음 (기본 차단이나 정책 잠금 없음 → Trust Center에서 변경 가능)

## 계획 반영 사항

- 실측 OS는 Windows 10 19044(21H2), RAM 128GB — MASTER_PLAN §1.2 갱신됨.
- Excel COM 자동 주입 리스크 해소 (실측). AutoCAD accoreconsole 경로는 사용자 확인 대기.
