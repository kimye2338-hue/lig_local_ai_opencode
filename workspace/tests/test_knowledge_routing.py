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
    # 규격/체결/도면
    ("810H Method 514 랜덤진동시험 카테고리", ["MIL-STD-810H.md", "진동해석.md"]),
    ("tailoring LCEP 시험계획 재단 근거", ["MIL-STD-810H.md"]),
    ("GD&T 위치도 MMC 보너스 공차", ["GD&T.md"]),
    ("데이텀 우선순위 A B C 흔들림", ["GD&T.md"]),
    ("3-2-1 위치결정 클램핑 시험지그", ["치구설계.md"]),
    ("진동시험 지그 고유진동수 몇 배", ["치구설계.md", "진동해석.md"]),
    ("AISI 4340 스테인리스 17-4PH 강종 표기", ["금속규격.md", "재료역학.md"]),
    ("7075 T73 알루미늄 조질 규격", ["금속규격.md", "재료역학.md"]),
    # 유도탄설계 캡스톤 — 구체 기술어로만 트리거(일반어 '설계' 금지)
    ("비례항법 유도 요격 지령가속도", ["유도탄설계.md"]),
    ("정적마진 압력중심 안정성", ["유도탄설계.md"]),
    ("미사일 종말유도 탐색기", ["유도탄설계.md"]),
    ("비추력 총역적 로켓 추진", ["유도탄설계.md"]),
    # 문서작성
    ("시험보고서 성적서 작성 구조", ["문서작성.md"]),
    ("논문 IMRaD 초록 작성법", ["문서작성.md"]),
]

# 주입되면 안 되는 것(무관/코칭/일상어 — 오주입 방지). 특히 캡스톤 트리거어('유도탄/설계')가
# 일상 어휘와 겹쳐 오주입되지 않는지 검증(Fable 검토: 허브 노트 최대 리스크).
NEGATIVE = [
    "오늘 점심 뭐 먹지",
    "내일 회의 일정 잡아줘",
    "휴가 언제 쓸까",
    "이 이메일 답장 써줘",
    "신제품 기획 설계 회의 잡아줘",   # '설계' 있으나 유도탄설계 아님
    "책상 설계 도와줘",
    "웹사이트 UI 설계",
    "이번 분기 성과 관리 계획",
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
