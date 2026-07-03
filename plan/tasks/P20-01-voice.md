# P20-01 — 음성 입력 구현 (whisper.cpp)

| 항목 | 값 |
|------|-----|
| 단계 | P20 (MASTER_PLAN §4 P20 — **예약**, 파일럿 후) |
| 담당 | codex |
| 선행 | P19-02 |
| 환경 | ANY (마이크 있는 PC에서 실측) |

## 목표
구두 지시: 녹음 → whisper.cpp STT → 확인 → `work --task-file` 실행.
(P13의 --task-file과 P17의 whisper/ffmpeg 선반입이 이미 준비되어 있음)

## 작업 항목
1. `agent_ops/voice_input.py` (stdlib subprocess 오케스트레이션):
   녹음(ffmpeg dshow, N초) → whisper-cli(wav→txt, 한국어) → 후처리(타임스탬프/공백 제거)
   → 반환. 각 단계 exe 부재 시 안내 반환.
2. `launch/voice.bat`: 녹음(기본 8초) → 인식 문장 표시 → **y 확인 후에만**
   work --task-file 전달. n이면 재녹음/취소.
3. `tests/test_voice_input.py`: exe 부재 SKIP. 있으면 동봉 샘플 wav(1~2초, 1MB 미만,
   "보고서 만들어줘" 육성)로 STT에 "보고서" 포함 확인.
4. doctor `voice` 섹션: exe/모델/ffmpeg 존재, 샘플 STT 스모크.
5. 한국어 10문장 스모크 결과 기록 (오인식은 오인식대로).

## DoD
- [ ] 마이크→work E2E 1회 실측 (증빙)
- [ ] 확인 게이트 없이는 실행 안 됨
- [ ] 음성 부재 시 전 기능 정상 (부가 계층 증명)

## 금지
- 인식 텍스트 무확인 자동 실행 금지. 녹음 파일 커밋 금지 (샘플 1개 예외).
