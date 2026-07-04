---
name: self-review
description: 보고서 제출 직전의 자가 검증. 모든 작업의 마지막 단계에서 사용 — 리뷰어가 잡을 것을 미리 잡아 반려 왕복을 없앤다.
---

# self-review

제출 전 5분. 아래를 통과 못 하면 제출하지 말고 고친다.

## Workflow

1. **diff 재독**: `git diff HEAD~1` (또는 스테이징분)을 처음 보는 사람처럼 읽는다.
   디버그 출력, 주석 처리된 코드, 무관한 파일, 우발적 포맷 변경이 섞였으면 제거.
2. **회귀 증거**: tests/test_*.py 전부 실행하고 각 마지막 줄을 보고서 4번 섹션에
   원문 그대로 붙였는가. "통과했다"는 요약 문장은 증거가 아니다.
3. **DoD 대조**: task의 DoD를 한 항목씩 열고, 각각에 대응하는 **테스트/출력/파일**을
   가리킬 수 있는가. 가리킬 수 없으면 그 항목은 ✅가 아니다.
4. **거짓 성공 스캔**: 상태 어휘가 실제와 일치하는가 — 특히 "실행 안 해봤는데 됐다고
   쓴 문장", "SKIP인데 통과라고 쓴 문장", "집 검증인데 app validation이라 쓴 문장".
5. **deviation 고백**: 계획과 다르게 한 것을 보고서 5번에 전부 적었는가.
   사소해서 뺀 것이 리뷰에서 발견되면 REJECTED다.

## 반복 결함 체크리스트 (리뷰 1~17차 실측 통계 기반 — 해당 유형 작업이면 필수)

1. **capability 키워드 추가 시** (반려 4회 — 최다: `.m`→`.md`, `minutes`→`5 minutes`,
   `weekly`→`biweekly`, `해석`→일상어): 짧은 영어 단어·확장자·한국어 일상어는 상위어의
   substring이 된다. bench의 **NEGATIVE_CORPUS 메타 체크를 통과**해야 하고, 새 키워드마다
   "일상 문장에 이 단어가 들어가나?" negative check 1줄을 먼저 쓴다.
2. **subprocess 격리 시** (반려 1회: outlook "no JSON"): 자식은 부모 sys.path를 상속하지
   않는다. `cwd`와 `PYTHONPATH`를 **CODE_ROOT**(`Path(__file__).resolve().parents[N]`)로
   명시 — `core.ROOT`(AGENTOPS_ROOT=데이터 루트)를 cwd로 쓰지 마라.
3. **테스트 fake 실행파일/바이트** (반려 2회: `.cmd` POSIX 불가, printf `\x` dash 미해석):
   `os.name` 분기(.sh+chmod / .cmd), 바이트는 octal `\NNN`. OS 전용 assertion은 가드
   안에, **hard-gate check는 OS 의존 블록 앞에**.
4. **추출 정규식** (반려 2회: 요일 한 글자→제목 훼손, 담당→날짜 `7월`): 결과 검증은
   `단어 in 텍스트`(존재)만 말고 **틀린 값 없음**(`"| 7월 |" not in …`)도 넣는다. 치환
   후 잔여 조사(까지/에)를 strip.

## Rules

- 보고서의 모든 주장에는 재현 명령 또는 파일 경로가 붙어야 한다.
- secret/host 문자열이 diff·보고서에 없는지 마지막으로 grep 한다
  (api_key, token, Bearer, 사내 도메인 패턴).
- 자가 검증을 통과했다고 리뷰가 면제되는 게 아니다 — auto-advance 조건일 뿐이다.
