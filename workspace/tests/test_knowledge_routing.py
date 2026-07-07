# -*- coding: utf-8 -*-
"""지식베이스 라우팅 골든셋 회귀 테스트 (Fable 검토 최우선 항목).

"작업 프롬프트 → 맞는 노트가 뽑히나"를 실사용형 질문으로 고정한다. 지식 도메인이
늘어도 라우팅 품질이 유지되는지 검증. 오프라인·결정적(임베딩 없음)이라 CI 가능.

- POSITIVE: 각 프롬프트의 acceptable(허용 노트) 중 하나라도 detect_domains 상위에 들면 통과.
  (아직 없는 노트는 skip — KB 성장에 견고)
- NEGATIVE: 무관/코칭성 프롬프트는 아무 노트도 주입 안 해야 함(약한 모델 오주입 방지).

`python tests/test_knowledge_routing.py` 로 실행."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_ops.knowledge_base import KB_DIR, detect_domains, routing_debug  # noqa: E402

PASS = 0
SKIP = 0
FAILURES = []


def _exists(name):
    for sub in ("domains", "standards", "lifeskills"):
        if (KB_DIR / sub / name).exists():
            return True
    return False


# (프롬프트, 허용 노트 파일명들 — 하나라도 뽑히면 정답)
POSITIVE = [
    ("브래킷 구조해석 안전율 검토해줘", ["구조해석.md"]),
    ("von Mises 응력으로 항복 판정", ["구조해석.md"]),
    ("이 부품 진동시험을 해야 하는데 어떻게 하지", ["MIL-STD-810H.md", "진동해석.md"]),
    ("유도탄 랜덤진동 지그 MIL-STD-810H Method 514", ["MIL-STD-810H.md", "진동해석.md"]),
    ("모달 해석으로 고유진동수 구하고 공진 회피", ["진동해석.md"]),
    ("이 PSD로 몇 시간 버티나 피로 수명", ["피로파괴.md", "진동해석.md"]),
    ("Miles 방정식으로 Grms 계산", ["진동해석.md"]),
    ("전자장비 열관리 CFD 난류모델 뭘 쓰지", ["열유체해석.md"]),
    ("y+ 얼마로 메시 만들어야 하나", ["열유체해석.md"]),
    ("베어링 수명 L10 계산해줘", ["기계요소설계.md"]),
    ("기어 굽힘응력 모듈 선정", ["기계요소설계.md"]),
    ("축 지름 피로 설계 DE-Goodman", ["기계요소설계.md", "피로파괴.md"]),
    ("알루미늄 브래킷 밀링 CNC 절삭조건", ["CNC.md", "기계공작법.md"]),
    ("G코드로 포켓 가공 프로그램", ["CNC.md"]),
    ("스테인리스 선삭 절삭속도 얼마", ["기계공작법.md", "CNC.md"]),
    ("열처리 담금질 뜨임 표면처리", ["기계공작법.md"]),
    ("시험 진동 데이터 FFT PSD 처리해줘", ["데이터처리.md", "진동해석.md"]),
    ("csv 계측 데이터 통계 이상치 처리", ["데이터처리.md"]),
    ("Nyquist 샘플링 에일리어싱", ["데이터처리.md"]),
    ("재료역학 굽힘응력 처짐 계산", ["재료역학.md", "구조해석.md"]),
]

# 주입되면 안 되는 것(무관/코칭 — 오주입 방지)
NEGATIVE = [
    "오늘 점심 뭐 먹지",
    "내일 회의 일정 잡아줘",
    "휴가 언제 쓸까",
    "이 이메일 답장 써줘",
]


def main():
    global PASS, SKIP
    for prompt, acceptable in POSITIVE:
        avail = [n for n in acceptable if _exists(n)]
        if not avail:
            SKIP += 1
            continue
        selected = [p.name for p in detect_domains(prompt)]
        if any(n in selected for n in avail):
            PASS += 1
        else:
            FAILURES.append(f"POSITIVE '{prompt[:30]}' → {selected} (기대 {avail}) | {routing_debug(prompt)['candidates'][:3]}")

    for prompt in NEGATIVE:
        selected = [p.name for p in detect_domains(prompt)]
        if not selected:
            PASS += 1
        else:
            FAILURES.append(f"NEGATIVE '{prompt[:30]}' → 오주입 {selected}")

    total = PASS + len(FAILURES)
    print(f"라우팅 골든셋: {PASS}/{total} 통과, {SKIP} skip(노트 미수집)")
    for f in FAILURES:
        print("  FAIL", f)
    if FAILURES:
        raise SystemExit(1)
    print(f"\nALL {PASS} ROUTING CHECKS PASSED (knowledge routing)")


if __name__ == "__main__":
    main()
