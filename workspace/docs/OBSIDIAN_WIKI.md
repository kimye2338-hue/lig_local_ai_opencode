# Obsidian으로 LLM 위키(기억) 관리

AI 비서의 장기 기억(LLM 위키)을 Obsidian으로 직접 읽고 편집하는 방법.

## 위키 위치 (vault)

```
%USERPROFILE%\OpenCodeLIG_USERDATA\memory\wiki\
```

이 폴더가 곧 Obsidian **vault**입니다. USERDATA 안에 있어 프로그램을 재설치/패치해도
지워지지 않습니다(불가침). 위키 페이지는 `[[주제]]` 위키링크를 쓰므로 Obsidian이
백링크·그래프로 그대로 렌더링합니다.

## 여는 방법

```bat
launch\wiki.bat
```

이 런처가 하는 일:
1. vault에 Obsidian 설정(`.obsidian/`)이 없으면 **최소 설정을 시드**합니다
   (코어 플러그인만: 그래프·백링크·검색·태그. 커뮤니티 플러그인 0 → 오프라인 안전).
   이미 있으면 건드리지 않습니다(사용자 설정 보존).
2. Obsidian을 찾아 vault를 엽니다. 못 찾으면 탐색기로 폴더만 엽니다.

## Obsidian 설치본 넣기 (오프라인)

인터넷이 없는 회사 PC이므로 설치 파일을 **반입**해야 합니다. 두 가지 방법:

- **포터블(권장, 관리자 권한 불필요)**: Obsidian 포터블을 아래에 풉니다.
  ```
  %USERPROFILE%\OpenCodeLIG\tools\Obsidian\Obsidian.exe
  ```
  `wiki.bat`가 이 경로를 최우선으로 찾습니다.
- **일반 설치**: Obsidian 설치 프로그램을 실행하면
  `%LOCALAPPDATA%\Obsidian\Obsidian.exe`에 깔리고, `wiki.bat`가 이것도 인식합니다.

> 반입 절차: 인터넷 되는 PC에서 obsidian.md 공식 다운로드 → 회사 반입 규정에 따라
> USB/승인 경로로 옮김 → 위 폴더에 배치. 라이선스는 개인 사용 무료.

## AI가 자동으로 관리하는 것

- 질문/지시/교훈/규칙이 기억 이벤트로 쌓이면 `consolidate`가 주제별 `.md` 페이지로 정리.
- `lint`가 중복·고아·오래 정체·**모순 후보**를 `log.md`에 보고(자동 삭제·자동 해결 없음).
- 사용자가 Obsidian에서 직접 고친 내용은 `manual/` 및 페이지에 남아 다음 정리에 반영.

## 원칙

- AI는 사용자 기억을 **조용히 지우지 않습니다**. 모순이 보이면 표시만 하고 사람이 판단.
- vault의 `.obsidian/` 사용자 설정은 시드 이후 덮어쓰지 않습니다.
