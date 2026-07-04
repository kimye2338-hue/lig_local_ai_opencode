# 반입 체크리스트 — OpenCodeLIG 오프라인 설치

집/개발 PC에서 번들을 만들어 회사 PC에 반입·설치·검증하는 전 과정. 각 단계는
**앞 단계가 OK일 때만** 다음으로. 실패 시 해당 줄의 "실패 시"를 따른다.

## A. 반입 전 (집/개발 PC, 인터넷 있음)

1. **의존성 prefetch 완료 확인** — `release/dependencies.json`의 `prefetch_files`가
   전부 `resolved`인가?
   - `py -3.11 release\verify_prefetch.py` → 모든 파일 `OK`.
   - 실패 시: `PENDING_HOME_PREFETCH` 항목(llama.cpp / whisper.cpp / ffmpeg GitHub
     릴리스)을 공식 릴리스에서 받아 `release\prefetch\`에 두고, `certutil -hashfile <파일>
     SHA256`로 해시를 `dependencies.json`에 채운 뒤 status를 `resolved`로. 다시 verify.
2. **번들 빌드** — `py -3.11 release\build_bundle.py --date YYYYMMDD`
   → `release\dist\OpenCodeLIG_BUNDLE_<날짜>.zip` + 내부 `MANIFEST_SHA256.txt`.
   - 실패 시: 출력의 `[ABORT]`(secret 파일 포함) 메시지를 보고 해당 파일 제거 후 재빌드.
3. **번들 해시 기록** — `certutil -hashfile release\dist\OpenCodeLIG_BUNDLE_<날짜>.zip SHA256`
   → 이 값을 메모(반입 후 재검증용).
4. **매체 복사** — zip을 USB 등 반입 매체로. **lig-api.env·API 키는 절대 넣지 않는다**
   (번들 빌더가 secret 파일을 거부하지만 매체에도 수동 반입 금지).

## B. 반입 (회사 PC)

5. 매체를 회사 PC에 연결, zip을 작업 폴더로 복사.
6. **반입 후 해시 재검증** — `certutil -hashfile OpenCodeLIG_BUNDLE_<날짜>.zip SHA256`
   → A-3의 값과 **일치**해야 함. 불일치 시 전송 손상 — 재복사.
7. zip 해제(탐색기 또는 `tar -xf`). 자기추출 exe 사용 금지(투명 zip만).

## C. 설치 (회사 PC)

8. 해제 폴더 루트에서 **`release\setup.bat`** 실행. 단계별 출력:
   - `[OK] Python 3.11 present` — 없으면 `[STOP]` + 안내(번들 python-embed 또는 회사 Python).
   - `[OK] Wheels installed` — `pip --no-index`로 번들 wheel만(인터넷 접근 없음).
   - `[OK] Workspace at %USERPROFILE%\OpenCodeLIG\workspace`
   - `[OK] USERDATA at %USERPROFILE%\OpenCodeLIG_USERDATA`
   - `[OK] doctor completed`
   - 실패 시: 각 `[STOP]`/`[WARN]`이 원인과 다음 행동을 출력한다(조용한 실패 없음).

## D. 확인 (doctor 기대값)

9. `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\setup_doctor.txt` 열기 — 기대값:
   - `encoding.roundtrip_ok: true` (UTF-8 왕복)
   - `operations.runbook: true` (RUNBOOK 동봉 확인)
   - `capabilities`/`adapters` 섹션 출력(secret 없이 presence flag만)
   - `lig_api_config.ready`는 아직 **false 정상** — E 단계 후 true.
   - 실패 시: `docs\RUNBOOK.md`의 해당 증상 행을 따른다.

## E. lig-api.env 작성 (수동, 커밋·반출 금지)

10. `%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env`에 회사 gateway 값 입력
    (`LIG_API_KEY`, 라우트 3줄은 `/gateway/` 접두 — 실측: 누락 시 404).
    - **이 파일은 절대 git/번들/채팅에 넣지 않는다.** 진단·보고에는 presence flag만.
11. `launch\gateway-smoke.bat` → 3라우트 준비 확인(미설정 시 무엇이 빠졌는지 + exit 2).
12. 이후는 `docs\PILOT_DAY1.md`(파일럿 1일차)로 이어진다.

## 금지 요약
- 인터넷 접근 설치 금지(`pip --no-index` 강제). PowerShell `-ExecutionPolicy Bypass` 금지.
- secret/내부 hostname을 번들·매체·커밋 어디에도 넣지 않는다.
- 자기추출 exe·인코딩된 페이로드 금지 — 투명 zip만.
