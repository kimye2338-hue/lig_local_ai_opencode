# 오프라인 설치 리허설 (P17-04)

회사와 **동일 조건(인터넷 0)** 에서 번들 설치가 끝까지 되는지 집 PC로 예행한다.
목적은 "됐다고 가정"이 아니라 **실제 air-gap에서 무엇이 실패하는지 관측**하는 것 —
실패 항목은 이 리허설의 정상 산출물이다.

> 두 부분으로 나뉜다.
> **[자동, 인터넷 있어도 됨]** 사전 점검 스크립트 → 사람이 손댈 것을 최소화.
> **[사람, 인터넷 반드시 차단]** 실제 air-gap 실행 → 기계가 대신할 수 없는 부분만.

---

## 0. 사전 점검 (자동 — 네트워크 차단 전에)

```bat
py -3.11 release\rehearsal_check.py
```

통과 조건 `ALL … PRE-FLIGHT CHECKS PASSED`. 이 스크립트가 미리 보장하는 것:
- `build_bundle.py`가 유효한 zip을 만든다 (setup.bat·doctor 포함, lig-api.env 미포함).
- `setup.bat`이 **오프라인 안전** — `pip --no-index`만 쓰고, curl/wget/git clone/
  `-ExecutionPolicy Bypass` 같은 인터넷 명령이 없다. (하드 실패로 검사)
- **runtime-network 감사(advisory)**: 번들 파이썬이 실행 중 아웃바운드를 낼 수 있는 지점을
  파일:줄로 나열한다. `[OK(local/env)]`는 localhost/env 게이트웨이(정상), `[REVIEW]`는
  실행 중 관측 대상. **아래 3절 트래픽 캡처에서 이 목록을 그대로 감시**한다.

여기서 FAIL이 나면 사람 리허설로 넘어가지 말고 먼저 고친다.

---

## 1. 번들 준비 (집 PC, 인터넷 있음)

1. P17-02 잔여 3종(llama.cpp / whisper.cpp / ffmpeg)을 공식 릴리스에서 받아
   `release\prefetch\`에 두고 `certutil -hashfile`로 해시를 `dependencies.json`에
   채운다 (status → `resolved`). `py -3.11 release\verify_prefetch.py` 전부 OK 확인.
   - 3종을 아직 못 받았으면 **source-only 번들로도 리허설 가능** — wheel/모델 설치 단계만
     건너뛴다(그 실패는 예상된 것으로 기록).
2. 번들 빌드: `py -3.11 release\build_bundle.py --date <YYYYMMDD>`
   → `release\dist\OpenCodeLIG_BUNDLE_<날짜>.zip`.
3. zip을 **다른 폴더**(가상의 "회사 PC" 루트, 예: `D:\FakeCompanyPC\`)에 복사. 원본 repo와
   섞이지 않게 완전히 분리된 경로를 쓴다.

---

## 2. 네트워크 차단 (사람)

4. **네트워크 어댑터 비활성화** — 제어판\네트워크 연결에서 모든 어댑터(유선/무선) 사용 안 함,
   또는 `netsh interface set interface "<이름>" admin=disable`. Wi-Fi도 반드시 끈다.
5. 차단 확인: `ping 8.8.8.8` → 100% loss여야 한다. (여기서 응답이 오면 리허설 무효)

---

## 3. 오프라인 설치 + 트래픽 캡처 (사람)

6. **아웃바운드 캡처 시작** (telemetry 실측 — P00-02 미해결 갭을 여기서 닫는다):
   - 간이: `netstat -bno 1 > D:\FakeCompanyPC\netstat.log` 를 별도 창에서 돌린 채 진행.
   - 정밀(권장): Wireshark 또는 `pktmon start --capture` 로 전체 캡처.
   - 감시 대상: 0절 `[REVIEW]` 목록 + OpenCode TUV 기동 시 **공개 호스트로의 연결 시도**.
     air-gap이므로 연결은 전부 실패해야 정상 — **어떤 공개 도메인이라도 시도가 보이면 기록**
     (hosts/방화벽 차단 보강 대상).
7. zip 해제 → 루트에서 **`release\setup.bat`** 실행. 각 단계 출력을 텍스트/스크린샷으로 남긴다.
   - source-only 번들이면 `[WARN] No release\prefetch\` 은 **예상된 정상**.
8. `%USERPROFILE%\OpenCodeLIG_USERDATA\diagnostics\setup_doctor.txt` 전체를 기록.
9. **mock 스모크 2종**(게이트웨이 없이도 도는 경로):
   ```bat
   pushd %USERPROFILE%\OpenCodeLIG\workspace
   py -3.11 agent_ops\agentops.py work --task "회의록 초안 만들어줘" --mode mock
   launch\briefing.bat
   popd
   ```
   각 명령의 종료코드와 산출물 생성 여부를 기록.

---

## 4. 네트워크 복구 + 기록 (사람)

10. 어댑터 다시 활성화, `ping 8.8.8.8` 정상 확인.
11. 결과를 **`plan/reports/P17-04-r1.md`** 에 기록:
    - setup.bat 단계별 결과(OK/WARN/STOP), doctor 전 섹션 값.
    - mock work + briefing 종료코드·산출물.
    - **트래픽 캡처 결론**: 공개 호스트 연결 시도 유무 → P00-02 telemetry 갭 `확인됨/추가차단 필요`.
    - 실패 항목은 각각 **원인 + 제안 수정 task**로. (Fable이 STATUS에 task화)

---

## DoD (task P17-04)
- [ ] 차단 상태에서 setup → doctor → mock work → briefing 성공(또는 실패 원인) 증빙
- [ ] 트래픽 캡처로 telemetry/아웃바운드 실측 결론 (P00-02 갭 종결)
- [ ] 실패 항목 → 수정 task 제안 (Fable이 task화)

## 금지
- 네트워크 차단 없이 "됐다고 가정" 금지 — 리허설의 존재 이유.
- lig-api.env 등 secret은 리허설에도 넣지 않는다(mock 모드는 불필요).
