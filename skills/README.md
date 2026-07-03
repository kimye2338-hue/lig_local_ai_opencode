# skills/ — 압축된 작동 메모리 (워커 공용)

이 폴더는 [dzhng/skills](https://github.com/dzhng/skills) 형식을 따르는 **재사용 절차 지식**이다.
목적: 같은 규칙을 task 파일마다 반복 기술하지 않는다 → 지시서는 짧아지고,
워커(Codex)는 스킬 한 번 읽고 여러 작업에 적용한다.

| 스킬 | 언제 읽나 |
|------|----------|
| `worker-loop/` | 모든 작업 세션 시작 시 (진입점) |
| `repo-conventions/` | 코드/테스트를 작성하는 모든 작업 |
| `self-review/` | 보고서 제출 직전 (필수) |
| `windows-batch/` | .bat 파일을 만들거나 수정할 때 |
| `app-adapter/` | adapters/ 아래 모듈을 만들 때 |
| `delegate-to-codex/` | (Fable/사용자용) Codex에게 작업을 위임할 때 |

규칙: task 지시서와 스킬 내용이 충돌하면 **task가 이긴다** (task는 그 작업의 스펙).
스킬 수정은 Fable 전용 (hard gate).
