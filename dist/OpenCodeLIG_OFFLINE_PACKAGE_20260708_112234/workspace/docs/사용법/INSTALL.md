# 설치 요약

일반 사용자는 [GUIDE.md](GUIDE.md)의 “설치와 첫 실행”만 보면 됩니다. 이 문서는 설치 절차만
짧게 다시 적은 확인용입니다.

## 설치

1. 배포 zip을 풉니다.
2. `INSTALL_OFFLINE_LIG_OPENCODE.bat.txt`를 `INSTALL_OFFLINE_LIG_OPENCODE.bat`로 이름 변경합니다.
3. `.bat`를 더블클릭합니다.
4. 설치 후 실행:

```text
%USERPROFILE%\OpenCodeLIG\workspace\RUN_OPENCODE_LIG.bat
```

## 첫 설정

아래 파일에 사내 LLM 게이트웨이 주소와 키를 넣습니다.

```text
%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env
```

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
