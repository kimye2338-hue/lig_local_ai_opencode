# OpenCodeLIG 사용 가이드

이 문서 하나로 설치, 첫 실행, 기본 사용법, 기억/Obsidian 위키, 문제 해결까지 익힐 수 있습니다.
OpenCodeLIG는 사내 오프라인 Windows PC에서 쓰는 한국어 AI 업무비서입니다. 사내 H100 LLM
게이트웨이를 OpenAI 호환 방식으로 사용하고, 문서 작성·데이터 정리·업무 자동화·기억 위키를
한 흐름으로 묶습니다.

## 1. 한눈에 이해하기

OpenCodeLIG는 세 층으로 동작합니다.

| 층 | 역할 | 사용자가 보는 것 |
|---|---|---|
| OpenCode 채팅 | 한국어 지시를 받고 작업을 조율 | `RUN_OPENCODE_LIG.bat` |
| agent_ops 런타임 | 문서 생성, 앱 자동화, 일정, 기억, 진단 실행 | `launch\menu.bat`, 각종 산출물 |
| USERDATA 기억 | 개인 규칙, 교훈, 일정, 위키를 영구 보존 | `%USERPROFILE%\OpenCodeLIG_USERDATA` |

중요한 원칙은 간단합니다.

- 한국어로 그냥 시키면 적절한 도구를 자동 선택합니다.
- 게이트웨이 주소와 API 키는 사용자 PC의 USERDATA에만 저장합니다.
- 기억과 일정은 프로그램을 재설치해도 지워지지 않습니다.
- 위험 명령 차단은 승인 모드가 바뀌어도 유지됩니다.

## 2. 설치와 첫 실행

1. 배포 폴더(또는 zip을 푼 폴더)를 엽니다.
2. `INSTALL_OFFLINE_LIG_OPENCODE.bat`를 더블클릭합니다.
   (전송 과정에서 `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt`로 보이면 확장자를 `.bat`로 바꾼 뒤 실행하세요.)
3. 설치가 끝나면 아래 위치에 프로그램이 놓입니다.

```text
%USERPROFILE%\OpenCodeLIG\workspace
```

첫 실행은 다음 파일을 더블클릭합니다.

```text
%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat
```

게이트웨이 주소·키·라우트·모델은 배포 설정에 이미 채워져 있어 **보통은 그대로 두면 바로 연결**됩니다.
값이 비어 있거나 플레이스홀더일 때만 실행 중 메모장이 열리며, 그 경우에만 아래 두 줄을 채웁니다.

```env
LIG_GATEWAY_BASE_URL=http://사내게이트웨이주소
LIG_API_KEY=발급받은키
```

설정 파일 위치:

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env
```

이 파일은 비밀 파일입니다. 메일, 메신저, 문서, git 커밋으로 내보내면 안 됩니다.

## 3. 실행 방법

### 기본: OpenCode 채팅

```text
%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat
```

실행 후 한국어로 원하는 일을 말합니다.

```text
이 폴더의 회의메모.txt로 회의록 만들어줘
지난주 기록으로 주간보고 초안 써줘
이 진동시험.csv로 표와 차트가 있는 HTML 보고서 만들어줘
이 PDF 읽고 핵심과 액션아이템 정리해줘
금요일 14시 진동시험 보고서 마감 일정 등록해줘
기억해: 보고서 제목은 항상 [부서명]으로 시작
```

사용자가 `office-doc`, `report-html`, `wiki` 같은 도구 이름을 외울 필요는 없습니다.
요청 의도에 따라 런타임이 문서 생성, 데이터 리포트, 일정, 기억, 앱 자동화 등을 고릅니다.

### 보조: 번호 메뉴

채팅 없이 빠르게 실행하려면 메뉴를 씁니다.

```text
%USERPROFILE%\OpenCodeLIG\workspace\launch\menu.bat
```

주요 메뉴:

| 메뉴 | 용도 |
|---|---|
| 업무 시키기 | 짧은 작업을 바로 실행 |
| 아침 브리핑 | 오늘 일정, 복습, 최근 기억 확인 |
| 주간보고 | 기록 기반 주간보고 초안 |
| 일정 | 일정 추가/조회 |
| 상태 진단 | 설치, Python, LLM 설정, 런타임 점검 |
| 지식책 | 배운 것과 기억을 HTML 책으로 열기 |

## 4. 자주 시키는 일

| 하고 싶은 일 | 예시 지시 |
|---|---|
| 회의록 | `회의메모.txt 읽고 회의록 만들어줘` |
| 보고서 초안 | `이 시험 결과로 품질보고서 초안 작성해줘` |
| Excel 파일 | `이 CSV를 보기 좋은 xlsx로 만들어줘` |
| HTML 리포트 | `표와 차트가 있는 자립형 HTML 보고서 만들어줘` |
| PPT/Word | `요약본을 5장짜리 PPT로 만들어줘` |
| 문서 읽기 | `이 PDF의 결론, 리스크, 할 일을 정리해줘` |
| 일정 | `다음 주 화요일 10시 설계검토 일정 등록해줘` |
| 기억 | `기억해: 시험 보고서는 원본 파일이 아니라 사본에서 작업` |
| 위키 | `내 기억 위키 정리해줘`, `지식책 열어줘` |
| 앱 자동화 | `열린 엑셀 파일을 사본으로 정리하고 차트 만들어줘` |
| 웹/포털 | `열린 크롬 탭의 공지사항 요약해줘` |

산출물은 보통 아래에 저장됩니다.

```text
%USERPROFILE%\OpenCodeLIG\workspace\agent_ops\results\artifacts
%USERPROFILE%\OpenCodeLIG\workspace\agent_ops\results\reports
```

## 5. 승인 모드

작업 중 명령 실행 승인이 필요할 수 있습니다. `Shift+Tab`으로 승인 정책을 바꿉니다.

| 모드 | 의미 |
|---|---|
| ASK | 위험하지 않은 일도 실행 전 확인 |
| AUTO | 같은 요청 안에서 필요한 승인을 자동 처리 |
| FULL | 세션 동안 반복 승인을 줄여 맡겨두기 좋음 |

`AUTO`나 `FULL`이어도 명시적으로 위험한 명령은 계속 차단됩니다.

## 6. 기억, 지식책, LLM Wiki

OpenCodeLIG는 일을 하면서 배운 내용을 USERDATA에 저장합니다.

| 구성 | 위치 | 역할 |
|---|---|---|
| 원장 | `memory\memory.jsonl` | append-only 기억 기록. 삭제하지 않음 |
| 규칙집 | `memory\WIKI.md` | 사람이 직접 적을 수 있는 전역 규칙 |
| LLM Wiki | `memory\wiki\*.md` | 원장에서 자동 생성되는 주제별 페이지 |
| 수동 노트 | `memory\wiki\manual\` | 사람이 Obsidian에서 직접 작성하는 노트 |
| 지식책 | HTML | 기억, 복습, 위키를 보기 좋게 묶은 책 |

기억시키는 방법:

```text
기억해: 보고서 제목은 항상 [부서명]으로 시작
앞으로 엑셀 원본은 직접 수정하지 말고 사본에서 작업해
다음부터 해석 결과는 표, 그래프, 결론 순서로 정리해
```

LLM Wiki는 `memory.jsonl` 원장을 주제별 페이지로 자동 정리합니다. 자동 페이지는 다음 정리 때
재생성될 수 있으므로 직접 편집하지 않는 것이 원칙입니다.

- 사실이나 규칙을 고치고 싶을 때: 채팅에서 `기억해: ...`로 새 기억을 추가
- 사람이 직접 노트를 쓰고 싶을 때: `memory\wiki\manual\` 아래에 작성
- 전체를 책처럼 보고 싶을 때: 메뉴의 `지식책` 또는 `python agent_ops\agentops.py book --open`

### Obsidian으로 보기

Obsidian을 쓰면 기억 위키를 그래프와 백링크로 볼 수 있습니다.

```text
%USERPROFILE%\OpenCodeLIG\workspace\launch\wiki.bat
```

이 런처는 `memory\wiki` 폴더를 Obsidian vault로 열고, `.obsidian` 설정이 없을 때만 최소 설정을
만듭니다. 이미 사용자가 바꾼 Obsidian 설정은 덮어쓰지 않습니다. Obsidian이 없으면 탐색기로
위키 폴더를 엽니다.

포터블 Obsidian을 쓰려면 다음 위치에 넣습니다.

```text
%USERPROFILE%\OpenCodeLIG\tools\Obsidian\Obsidian.exe
```

## 7. 내장 지식과 자동 근거

업무 유형에 따라 관련 근거가 자동으로 붙습니다.

| 분야 | 자동 주입되는 지식 |
|---|---|
| Office/문서 | 보고서, PPT, 회의록, 한국 비즈니스 문체 |
| 앱 자동화 | Excel, HWP, SolidWorks, AutoCAD, MATLAB, Fluent 등 공식 API 레시피 |
| 공학 질문 | 구조, 진동, 피로, 열유체, 기계요소, 공작법, CNC, 치구, GD&T, 유도탄, 금속규격, MIL-STD-810H |
| 개인 업무 | 사용자가 기억시킨 규칙, 과거 교훈, 반복 작업 |

재료 물성, 규격 수치, 안전 관련 숫자는 내장 노트를 참고하더라도 원문 규격과 데이터시트 확인이
필요하다고 안내합니다.

## 8. 선택 기능 반입

기본 기능은 오프라인으로 동작합니다. 일부 고급 기능은 회사 반입 절차에 따라 wheel이나 실행 파일을
추가하면 켜집니다.

| 기능 | 필요한 것 | 없을 때 |
|---|---|---|
| PDF/Word/PPT/Excel 읽기 | `markitdown` wheel | 해당 문서 읽기만 제한 |
| 진짜 `.docx/.pptx/.xlsx` 생성 | `python-docx`, `python-pptx`, `openpyxl` | HTML/텍스트 산출은 가능 |
| 화면 OCR | OCR 엔진 또는 관련 wheel | 화면 읽기 기능만 제한 |
| COM 없는 앱 조작 | `windows-use` 등 | 공식 API/파일 기반 작업은 가능 |
| Obsidian GUI | `Obsidian.exe` | 탐색기로 위키 폴더 열기 |

현재 무엇이 준비됐는지 확인:

```bat
cd %USERPROFILE%\OpenCodeLIG\workspace
python agent_ops\agentops.py deps
```

## 9. 폴더 구조

```text
%USERPROFILE%\OpenCodeLIG
  bin\opencode.exe
  workspace
    RUN_OPENCODE_LIG.bat
    launch\menu.bat
    launch\wiki.bat
    agent_ops
      agentops.py
      results\artifacts
      results\reports
    docs

%USERPROFILE%\OpenCodeLIG_USERDATA
  secrets\lig-api.env
  memory
    memory.jsonl
    WIKI.md
    wiki
      index.md
      manual
  schedule
  audit
  diagnostics
```

`OpenCodeLIG_USERDATA`는 사용자 데이터입니다. 기억, 일정, 감사 기록, 설정이 들어 있으므로 삭제하면
안 됩니다.

## 10. 문제가 생기면

먼저 상태 진단을 실행합니다.

```bat
cd %USERPROFILE%\OpenCodeLIG\workspace
python agent_ops\agentops.py doctor
```

또는:

```text
launch\menu.bat → 상태 진단
```

| 증상 | 먼저 할 일 |
|---|---|
| LLM 응답 없음 | `lig-api.env`의 주소와 키 확인 후 `doctor` 실행 |
| 한글 입력이 밀림 | Windows Terminal 사용 권장, 반드시 `RUN_OPENCODE_LIG.bat` 또는 `launch\*.bat`로 실행 |
| 문서 생성 기능이 빠짐 | `python agent_ops\agentops.py deps`로 미반입 wheel 확인 |
| Obsidian이 안 열림 | `tools\Obsidian\Obsidian.exe` 위치 확인. 없으면 탐색기로 열리는 것이 정상 |
| 작업이 멈춘 듯함 | `python agent_ops\agentops.py watch`, 이후 `doctor` |
| 설치 검증 필요 | `python agent_ops\agentops.py verify` 실행. 설치본에 `VERIFY_OFFLINE_INSTALL.bat`가 있으면 그것도 사용 가능 |

진단 파일은 아래에 남습니다.

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics
```

더 자세한 장애 대응은 `docs\사용법\RUNBOOK.md`를 봅니다.
