# 반입 체크리스트 — OpenCodeLIG 오프라인 설치

집/개발 PC에서 번들을 만들어 회사 PC에 반입·설치·검증하는 전 과정. 각 단계는
**앞 단계가 OK일 때만** 다음으로. 실패 시 해당 줄의 "실패 시"를 따른다.

## A. 반입 전 (집/개발 PC, 인터넷 있음)

1. **의존성 prefetch 완료 확인** — `release/dependencies.json`의 `prefetch_files`
   중 **파일럿에 필요한 wheel 8종(office/COM)** 이 전부 `resolved`인가?
   - `py -3.11 release\verify_prefetch.py` → 대상 파일 `OK`.
   - **파일럿은 wheel 8종만 있으면 된다.** 회사는 오프라인 내부망이지만 사내 게이트웨이
     (`company_gateway` 프로필)가 LLM을 서빙하므로 로컬 llama.cpp/GGUF는 불필요.
   - `deferred` 3종(llama.cpp / whisper.cpp / ffmpeg)은 **로컬서빙(`local_openai`) 또는
     음성(P20) 채택 시에만** 필요 — 그때 집/개발 PC에서 공식 릴리스를 받아 `release\prefetch\`에
     두고 `certutil -hashfile <파일> SHA256`로 해시를 `dependencies.json`에 채워 status를
     `resolved`로 바꾼 뒤 build_bundle 재실행(자동 포함). 파일럿에는 건너뛴다.
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

## C. 설치 (회사 PC) — 더블클릭 한 번

8. 해제 폴더 루트의 **`설치.bat` 더블클릭**. 설치기가 [1/6]~[6/6] 순서로 자동 진행:
   - Python 3.11 자동 탐지(`py -3.11`→`python`→`python3.11`→`python3`)
   - 라이브러리 오프라인 설치(`pip --no-index`, 인터넷 없음)
   - 프로그램 배치(`%USERPROFILE%\OpenCodeLIG\workspace`) + 데이터 폴더
   - **게이트웨이 설정**: 주소/API 키 붙여넣기(모르면 Enter로 건너뜀 — 나중에 설정 가능)
   - 자가 진단(doctor) + **바탕화면 [AI비서] 바로가기 생성**
   - 실패 시: 각 `[중단]`/`[주의]`가 원인과 다음 행동을 출력한다(조용한 실패 없음).

## D. 확인 (doctor 기대값)

9. `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\setup_doctor.txt` 열기 — 기대값:
   - `encoding.roundtrip_ok: true` (UTF-8 왕복)
   - `operations.runbook: true` (RUNBOOK 동봉 확인)
   - `capabilities`/`adapters` 섹션 출력(secret 없이 presence flag만)
   - `lig_api_config.ready` — 설치 때 게이트웨이 값을 넣었으면 true, 건너뛰었으면 false.
   - 실패 시: `docs\RUNBOOK.md`의 해당 증상 행을 따른다.

## E. 게이트웨이 값 (설치 때 건너뛴 경우만)

10. 설치 5단계에서 Enter로 건너뛰었다면
    `%USERPROFILE%\OpenCodeLIG_USERDATA\secrets\lig-api.env` 를 열어
    `LIG_GATEWAY_BASE_URL` / `LIG_API_KEY` 두 값을 채운다.
    - **이 파일은 절대 git/번들/채팅에 넣지 않는다.** 진단·보고에는 presence flag만.
11. 바탕화면 [AI비서] → `5. 게이트웨이 점검` 으로 연결 확인(미설정 시 무엇이 빠졌는지 안내).
12. 이후는 `docs\PILOT_DAY1.md`(파일럿 1일차)로 이어진다.

## 금지 요약
- 인터넷 접근 설치 금지(`pip --no-index` 강제). PowerShell `-ExecutionPolicy Bypass` 금지.
- secret/내부 hostname을 번들·매체·커밋 어디에도 넣지 않는다.
- 자기추출 exe·인코딩된 페이로드 금지 — 투명 zip만.
