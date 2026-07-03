# P18-01 — secret 스캔 pre-commit 스크립트

| 항목 | 값 |
|------|-----|
| 단계 | P18 (MASTER_PLAN §4 P18) |
| 담당 | codex |
| 선행 | 없음 |
| 환경 | ANY |

## 목표
secret/내부 hostname이 커밋되는 사고를 기계적으로 차단.

## 작업 항목
1. `workspace-template/scripts/precommit_scan.py` (stdlib):
   - 대상: `git diff --cached --name-only` 파일들 (텍스트만).
   - 패턴: `LIG_API_KEY\s*=\s*[^P\s]`(placeholder 외 값), `Bearer\s+[A-Za-z0-9]`,
     `(api[_-]?key|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9]{8,}`,
     사내 도메인 패턴(정규식은 일반형 `[a-z0-9-]+\.(local|internal|corp)` + env
     `LIG_SECRET_EXTRA_PATTERNS` 파일로 회사별 패턴 추가 — **회사 hostname 원문을
     이 스크립트에 하드코딩 금지**).
   - 검출 시 파일:라인 출력 + exit 1. 예외 허용: 라인에 `# secret-scan-ok` 주석.
2. `.git/hooks/pre-commit` 설치 스크립트 `scripts/install_hooks.bat`
   (훅 파일은 py 호출 한 줄 — 훅 자체는 커밋 불가하므로 설치 스크립트로 배포).
3. `tests/test_secret_scan.py`: 검출 4패턴 각각 + placeholder 통과 + 예외 주석 통과 +
   한글 파일 무오탐 (tmp git repo 만들어 staged 상태 재현).

## DoD
- [ ] 4패턴 검출/통과 테스트
- [ ] 회사 hostname이 스크립트/테스트에 등장하지 않음
- [ ] install_hooks.bat manual smoke
- [ ] 기존 checks 무손상

## 금지
- 실제 secret 예시를 테스트 fixture에 사용 금지 (가짜 무의미 문자열만).
