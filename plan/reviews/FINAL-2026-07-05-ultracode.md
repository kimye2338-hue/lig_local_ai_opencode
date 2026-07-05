# Fable 울트라코드 최종 풀 검토 — 초기 의도 대비 완성도 (2026-07-05)

| 항목 | 값 |
|------|-----|
| 방식 | 42-에이전트 워크플로 (요구추출→커버리지 14건→리뷰 5차원→발견 22건 전건 적대검증) + Fable 직접 수정 |
| 모델 배분 | 고난이도(제품UX/real경로 심층)=상위 모델, 잔무(커버리지/문서/검증)=Sonnet — 사용자 지시 |
| 판정 | **초기 의도 충족 — 단, 최종 패스에서 플래그십 결함 2건 포함 22건 발견·전건 수정** |

## 1. 발견·수정 (must 10 / should 12 — 전건 종결)

**핵심 결함 (이번 수정 전엔 파일럿에서 바로 체감됐을 것):**
1. **`work --mode real`이 산출물 경로에서 무동작** — enrich(LLM 내용 채움)가 미연결이라 게이트웨이가 있어도 빈 서식만 생성. → cmd_work에 실 게이트웨이 `chat_with_fallback` 클라이언트 연결(품질검사 통과분만 반영, 실패 시 scaffold 유지+사유 출력). **실측: mock 배너/미설정 안내/모의 게이트웨이 폴백 3경로 확인.**
2. **`work --execute`가 실제로 아무 어댑터도 실행 안 함** — 가짜 "available" 보고. → `adapters.plan_execution()` 안전 dispatch 신설: matlab(.m 실행)·hwp(문서→.hwp 변환)·excel(입력 .xlsx 사본에 매크로 주입, 없으면 수동안내)·autocad(입력 .dwg 필요) / 매핑 없는 kind는 정직한 no-auto-run. 승인 위험 항목도 실제 실행될 것에만 생성. **실측: 가짜 MATLAB로 dispatch E2E `adapter matlab: ok`.**
3. **'HWP 변환' 오라우팅** — office_cad 키워드에 hwp/워드가 섞여 autocad_script까지 emit. → 문서 변환은 document_generation으로 이관(키워드 수술), CAD는 유지. **실측: document만 emit, bench 220 green.**
4. real 미설정 시 침묵/암호 메시지 → 한국어 안내+exit 2, `local_fallback`(게이트웨이 전면 실패) 사용자 안내 추가.
5. 메뉴 결함: 실패해도 성공처럼 안내+상위 폴더 열기 → errorlevel 검사+최신 run 폴더 열기+참고파일(--input) 프롬프트+일정 추가/보기/Outlook 동기화 메뉴 신설(브리핑 빈 상태 힌트 포함).

**문서 12건**: launch/README(검증 상태 stale)·INSTALL 경로 2건·REPOSITORY_MAP 전면·VALIDATION agent_ops 트랙·AI_HANDOFF 이중 트랙·README 맵·doctor/agentops stale 문구 — Sonnet 에이전트 2개가 일괄 수정, 재독 검증.

## 2. 커버리지 (초기 요구 14건)
비서(브리핑/회의록/주간보고/메일)·일정·Office/HWP·MATLAB/AutoCAD/Fluent/SW·Outlook·브라우저·오프라인 반입·게이트웨이 LLM·승인/감사·품질검증·한국어 파일작업·진단/복구·보안 — **전건 구현+실측 근거 존재**. 음성(R7)은 설계대로 인터페이스만(후순위). 잔여 실측: SolidWorks 매크로 실행·Fluent·Word/PPT 변환(파일럿에서).

## 3. 최종 건강도
회귀 **20 green**(RED 3=Windows 전용) — bench 220 / batch 44(dispatch 신규) / office 50(dispatch 신규) / work 20 / manifest 77. secret scan 통과. 신규 배선 4경로 실측(mock 배너·미설정 안내·모의 게이트웨이 enrich 폴백·dispatch 실행).

## 4. 남은 것 (전부 사람)
회사 파일럿 12종 실주행(P19-02) — 이제 real 모드가 내용까지 채우고 --execute가 실제 실행하므로 파일럿이 진짜 UX를 측정한다. 이후 음성(P20).
