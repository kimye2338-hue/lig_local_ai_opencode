# OpenCodeLIG 사용설명서 (이 문서 하나면 됩니다)

## 1. 설치 — 1분

1. zip을 푼다.
2. `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt` 의 이름을 `INSTALL_OFFLINE_LIG_OPENCODE.bat`
   으로 바꾼 뒤(`.txt` 를 지운다) 더블클릭한다.
3. 설치가 끝나면 프로그램이 `%USERPROFILE%\OpenCodeLIG\workspace` 에 놓인다.

**게이트웨이 주소/키 입력은 첫 실행 때** 한다:
`%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat` 을 실행하면 설정 파일이
자동으로 만들어지고 **메모장이 열린다** — 게이트웨이 주소(`LIG_GATEWAY_BASE_URL`)와
키(`LIG_API_KEY`) 두 줄만 채우고 저장하면 된다. (라우트/모델명은 이미 채워져 있다.
나중에 바꾸려면 3번 항목의 파일을 편집한다.)

## 2. 사용 — 두 가지 방법

**방법 A — 오픈코드 채팅 (주 사용법)**
`%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat` 실행 → 한국어로 그냥 시킨다:

- "이 폴더의 회의메모.txt로 회의록 만들어줘"
- "지난주 기록으로 주간보고 초안 써줘"
- "이 진동시험.csv로 보고서랑 PPT 만들어줘" (표·차트·1슬라이드1메시지 자동 적용)
- "이 PDF/워드 문서 읽고 요약해줘" (Office 없이 읽음)
- "이 데이터 엑셀/HTML로 보기 좋게 만들어줘"
- "금요일 14시 진동시험 보고서 마감 일정 등록해줘"
- "기억해: 보고서 제목은 항상 [부서명] 으로 시작"
- 솔리드웍스(2022)/오토캐드/매트랩 매크로 요청 → **버전 맞는 공식 API 근거로** 코드 생성
- 웹 분석: `launch\chrome-debug.bat`로 크롬을 연 뒤 → "열린 탭에서 사내 포털 공지 요약해줘"

한국어로 시키면 **적절한 도구를 알아서 골라** 실행한다(따로 도구를 지정할 필요 없음).
자세한 능력은 아래 6번 참고.

어느 폴더의 파일을 다루든 **같은 비서**가 뜨고 **기억을 공유**한다 — 작업할 파일 경로를
채팅에서 알려주거나, "이 폴더의 …" 처럼 시키면 된다.

**터미널 권장(한글 입력 매끄럽게)**: Windows Terminal 을 쓰면 한글 입력 지연이 없다.
`WindowsTerminal_오프라인설치.zip` 로 설치 후, **기본 터미널로 지정**해두면 모든 실행이
자동으로 Windows Terminal 에서 열린다:
- Windows Terminal 실행 → 설정(Ctrl+,) → "시작 → 기본 터미널 응용 프로그램"을
  **Windows Terminal** 로 변경. 이후 `.bat` 더블클릭·`oc` 실행이 전부 Terminal 에서 열림.
- (지정 안 해도 동작은 하지만, 구형 콘솔에서는 한글 타자가 밀릴 수 있음.)

**승인(허락) 정책 — `Shift+Tab`**: ASK(매번 물어봄) → AUTO(한 건씩 자동 승인)
→ FULL(완전 오토 — 같은 종류는 세션 내내 기억, 끊김 최소) 순환.
위험 명령 차단은 어느 정책에서도 유지된다. 채팅에 `/perm full` 로도 전환 가능.

**방법 B — AI비서 메뉴 (오픈코드 없이)**
`%USERPROFILE%\OpenCodeLIG\workspace\launch\menu.bat` 실행 → 번호 선택
(1 업무 시키기 / 2 아침 브리핑 / 3 주간보고 / 4·5·6 일정 / 7 상태 진단 / 8 지식책).

## 3. 설정 — 파일 하나

`내문서 아님 주의 → %USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env`

```
LIG_GATEWAY_BASE_URL=http://사내게이트웨이주소
LIG_API_KEY=발급받은키
```

이 파일 하나가 전부다. **절대 메일/메신저/커밋으로 내보내지 말 것.**

## 4. 폴더 구조 — 어디에 뭐가 있나

```
%USERPROFILE%\OpenCodeLIG\
  bin\opencode.exe             패치된 오픈코드 본체
  workspace\                   프로그램 본체
    RUN_OPENCODE_LIG.bat           오픈코드 채팅 실행기 (방법 A)
    launch\menu.bat                AI비서 번호 메뉴 (방법 B)
    agent_ops\results\artifacts\   ← 만들어진 산출물 (run별 폴더)
    agent_ops\results\reports\     ← 브리핑/주간보고
%USERPROFILE%\OpenCodeLIG_USERDATA\
  secrets\lig-api.env          게이트웨이 설정 (위 3번)
  memory\WIKI.md               전역 기억 위키 (직접 편집 가능)
  audit\                       실행 감사 기록
```

## 5. 기억과 지식책 — 점점 똑똑해지는 구조

- 채팅에서 **"기억해: ..."** → 전역 저장, 모든 폴더·페르소나에서 공유.
- 실수를 지적하면 교훈으로 기록되어 다음엔 반복하지 않는다.
- **지식책** = 내가 배운 것들의 히스토리북(HTML). `launch\menu.bat` 의 **8번(지식책 보기)**
  또는 `python agent_ops\agentops.py book --open` 으로 연다. 자동으로 늘 최신:
  - 타임라인: 언제 뭘 배웠나 (보관된 옛 기록도 남는다 — 절대 휘발 없음)
  - 🔁 이번 주의 복습: 잊어갈 때쯤 오래된 지식을 다시 띄워준다 (매주 회전)
  - 분류(내 규칙/배운 것/실수 노트) + 검색 + 최근 활동
- 아침 브리핑에도 "오늘의 복습" 한 줄이 뜬다.
- 규칙집 원본은 `USERDATA\memory\WIKI.md` — 직접 편집해도 책에 반영된다.
- **한 일도 자동으로 정리된다**: 작업이 끝나면 자동으로 기억에 남아 위키 페이지로 정리되고,
  다음에 비슷한 일을 시키면 그 맥락을 참고해 더 잘한다. 기억이 아무리 쌓여도 핵심만
  추려 참고하므로 느려지지 않고, 사용자 규칙은 활동이 쌓여도 밀려나지 않는다.
- **Obsidian으로 위키 보기**(선택): `launch\wiki.bat` — 기억 위키를 Obsidian에서 열어
  그래프·백링크로 본다. (Obsidian 설치본을 `tools\Obsidian\`에 반입하면 자동 인식)

## 6. 추가로 할 수 있는 것 (자연어로 시키면 알아서 실행)

전부 한국어로 시키면 되고, 도구를 직접 고를 필요는 없다. 오프라인 반입이 필요한 항목만 표시.

| 하고 싶은 것 | 결과 | 반입 필요 |
|---|---|---|
| PDF·워드·PPT·엑셀 문서 읽기 | Office 없이 내용 읽어 요약/분석 | markitdown wheel |
| 진짜 .xlsx/.docx/.pptx 만들기 | Office 없이 실제 파일 생성 | openpyxl·python-docx·python-pptx wheel |
| 데이터를 표+차트 HTML로 | 브라우저로 여는 자립형 리포트 | (없음) |
| 반복 업무 자동 재생 | 성공한 작업을 저장→다음엔 자동 재생 | (없음) |
| 화면을 눈으로 읽기(막힐 때) | 스크린샷 OCR(한/영) | OCR 엔진(tools\ocr) |
| COM 없는 앱 조작 | 임의 Windows 앱 자동화 | windows-use wheel |
| 활동/멈춤 타임라인 보기 | 무엇을 언제 했는지 HTML | (없음) |

**오프라인 반입 방법**(인터넷 되는 PC에서 받아 USB로 반입):
```bat
pip download markitdown[pdf,docx,pptx,xlsx] python-docx python-pptx openpyxl -d wheelhouse
rem 회사 PC:
pip install --no-index --find-links wheelhouse markitdown[pdf,docx,pptx,xlsx] python-docx python-pptx openpyxl
```
미반입이어도 그 기능만 안내가 뜰 뿐, 나머지는 정상 동작한다. (각 항목 상세는 `docs\` 참고)

**지금 뭐가 준비됐고 뭘 더 넣어야 하나**: `python agent_ops\agentops.py deps` — 준비됨/미반입을
한눈에 보여준다. 반입 목록 한 장: `tools\README.md`. (설치 파일·바이너리는 패키지에 기본
포함돼 있지 않으니, 필요한 기능만 인터넷 PC에서 받아 반입한다.)

## 7. 문제가 생기면

| 증상 | 조치 |
|---|---|
| 뭔가 이상함 | `launch\menu.bat` → 7. 상태 진단 |
| LLM 응답 없음 | 3번 설정 확인 → `launch\menu.bat` → 7. 상태 진단(lig_api_config가 ready인지) |
| 한글이 밀리거나 깨짐 | 반드시 `RUN_OPENCODE_LIG.bat`/`launch\*.bat` 로 실행(chcp 65001 보장) |
| 오픈코드 안 뜸 | `workspace\VERIFY_OFFLINE_INSTALL.bat` 실행 |

진단 파일 위치: `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\`
