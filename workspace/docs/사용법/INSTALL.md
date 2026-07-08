# 설치 요약

일반 사용자는 [GUIDE.md](GUIDE.md)의 “설치와 첫 실행”만 보면 됩니다. 이 문서는 설치 절차만
짧게 다시 적은 확인용입니다.

## 설치

1. 배포 폴더(또는 zip을 푼 폴더)를 엽니다.
2. `INSTALL_OFFLINE_LIG_OPENCODE.bat`를 더블클릭합니다.
   (전송 과정에서 파일이 `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt`로 보이면 확장자를 `.bat`로
   바꾼 뒤 실행하세요.)
3. 설치 후 실행:

```text
%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat
```

## 첫 설정 (기본은 자동 — 보통 건드릴 필요 없음)

게이트웨이 주소·키·라우트·모델은 배포 패키지에 이미 채워져 있습니다. 설치기가 아래 파일로
시드하므로 **따로 설정하지 않아도** 실행하면 바로 사내 게이트웨이에 연결됩니다.

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env
```

게이트웨이 주소가 바뀐 경우에만 위 파일의 두 값을 수정하세요(그 외에는 그대로 둡니다).

```env
LIG_GATEWAY_BASE_URL=http://사내게이트웨이주소
LIG_API_KEY=발급받은키
```

비밀값은 외부로 보내거나 커밋하지 않습니다.

## 확인

```bat
cd %USERPROFILE%\OpenCodeLIG\workspace
python agent_ops\agentops.py doctor
python agent_ops\agentops.py deps
```

런타임을 다시 검증하려면:

```bat
python agent_ops\agentops.py verify
```

설치본에 아래 파일이 함께 생성되어 있으면 더블클릭 검증용으로 사용할 수 있습니다.

```text
%USERPROFILE%\OpenCodeLIG\workspace\VERIFY_OFFLINE_INSTALL.bat
```

## 오프라인 제약

설치기는 인터넷 다운로드, GitHub clone, npm/bun 설치, PowerShell `ExecutionPolicy Bypass`를 하지
않습니다. 추가 wheel이나 실행 파일은 회사 반입 절차로 `tools\` 또는 wheelhouse에 넣어 사용합니다.
