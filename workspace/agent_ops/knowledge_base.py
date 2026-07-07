# -*- coding: utf-8 -*-
"""레퍼런스 지식베이스 검색·주입 — 도메인 라우팅 → MOC 지도 → relevance 발췌.

개인 기억(USERDATA/memory)과 분리된 '큐레이션된 사실' 층. 공학 도메인·규격·소프트스킬을
`knowledge/domains|standards|skills/*.md`에 두고, 작업이 가리키는 도메인을 감지해
① 도메인 MOC(하위주제 지도) ② 관련 노트의 작업 관련 섹션을 system 컨텍스트로 주입한다.

팩트체크 인지: 각 노트 프론트매터의 verified/confidence/sources 를 읽어, verified 우선
주입하고 draft는 '미검증' 꼬리표를 단다. 파일이 없어도 안전(주입 생략).

검색 설계(약한 모델용):
  1) 도메인 라우팅: 프롬프트 → 관련 도메인(파일명/title/aliases/domain 키워드 매칭)
  2) MOC 주입: knowledge/_moc/<도메인>.md 가 있으면 지도로 먼저(Aider repo-map 패턴)
  3) relevance 발췌: 매칭 노트에서 작업 관련 섹션만 예산 내(api_reference와 동일 방식)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

KB_DIR = Path(__file__).resolve().parent / "knowledge"
# 공학 도메인 / 규격 / 소프트스킬. (기존 skills/=프로세스 스킬, domain/=한국 비즈니스
# 맥락은 별도 주입기가 담당하므로 여기 포함하지 않는다.)
_NOTE_DIRS = ("domains", "standards", "lifeskills")
_MOC_DIR = KB_DIR / "_moc"


def _tokens(s: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+|[가-힣]{2,}", (s or "").lower()) if len(t) >= 2}


def _parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """--- yaml --- 프론트매터를 얕게 파싱(외부 의존 없이). (meta, body) 반환."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    head = text[3:end]
    body = text[end + 4:].lstrip("\n")
    meta: Dict[str, str] = {}
    for line in head.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip().strip("[]").strip()
    return meta, body


def _iter_notes():
    """(path, meta, body) for every reference note."""
    for sub in _NOTE_DIRS:
        d = KB_DIR / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            meta, body = _parse_frontmatter(text)
            yield p, meta, body


def _note_terms(path: Path, meta: Dict[str, str]) -> set:
    """노트를 가리키는 '용어'(문자열) 집합 = 파일명 + title + domain + aliases의 각 항목.

    토큰 교집합이 아니라 '용어가 프롬프트에 포함되는가'(부분매칭)를 쓰기 위해 원형 용어를
    보존한다. 한국어 교착어에서 '진동시험을'이 '진동시험'을 포함하므로 리콜이 안정된다."""
    terms = {path.stem.strip().lower(),
             str(meta.get("title", "")).strip().lower(),
             str(meta.get("domain", "")).strip().lower()}
    for a in str(meta.get("aliases", "")).split(","):
        a = a.strip().lower()
        if a:
            terms.add(a)
    return {t for t in terms if len(t) >= 2}


def detect_domains(prompt: str, top: int = 2, min_score: int = 1) -> List[Path]:
    """작업 관련 노트를 반환. 부분매칭(노트 용어가 프롬프트에 포함).

    오주입 방지는 **임계값이 아니라 aliases curation**으로 한다: aliases에는 구체적
    기술 용어(응력·피로·von mises·y+·fft 등)만 넣고 일상어(설계·데이터·해석 같은 광범위
    단어 단독)는 피한다. 그러면 짧은 기술용어(2~3자)도 강한 신호로 살아나면서, 무관/코칭성
    프롬프트는 애초에 매칭될 용어가 없어 주입되지 않는다(라우팅 골든셋 NEGATIVE로 회귀 검증).
    약한 33B가 주입을 과신하므로 top=2로 제한한다.
    """
    low = (prompt or "").lower()
    if not low.strip():
        return []
    # 문서빈도(df): 여러 노트에 흔한 용어(응력·굽힘)는 변별력이 낮고, 한 노트에만 있는
    # 용어(기어·베어링·paris)는 강한 의도 신호다. 희소 용어에 가중(TF-IDF식)해 일반어가
    # 구체 의도어를 이기지 못하게 한다.
    notes = list(_iter_notes())
    df: Dict[str, int] = {}
    for path, meta, _b in notes:
        for t in _note_terms(path, meta):
            df[t] = df.get(t, 0) + 1

    def _w(t: str) -> float:
        d = df.get(t, 1)
        rarity = 3.0 if d <= 1 else (2.0 if d == 2 else 1.0)   # 희소할수록↑
        return rarity + (0.5 if len(t) >= 4 else 0.0)          # 긴 용어 소폭 가중

    scored: List[Tuple[float, int, Path]] = []
    for path, meta, _body in notes:
        hits = [t for t in _note_terms(path, meta) if t in low]
        if not hits:
            continue
        ws = sorted((_w(t) for t in hits), reverse=True)
        # 가장 변별력 있는 단일 용어가 라우팅을 지배(기어 하나 > 일반어 응력+굽힘) +
        # 나머지 히트는 소폭만 가산. 이러면 두 일반어가 한 구체어를 못 이긴다.
        score = ws[0] + 0.4 * sum(ws[1:])
        scored.append((score, max(len(t) for t in hits), path))
    qualified = [(s, ln, p) for s, ln, p in scored if s >= min_score]
    qualified.sort(key=lambda x: (-x[0], -x[1]))
    return [p for _s, _l, p in qualified[:top]]


def routing_debug(prompt: str) -> Dict[str, Any]:
    """진단용: 어떤 노트가 왜 뽑혔는지(히트 용어·점수). 라우팅 실패 관측·테스트에 사용."""
    low = (prompt or "").lower()
    rows = []
    for path, meta, _b in _iter_notes():
        hits = [t for t in _note_terms(path, meta) if t in low]
        if hits:
            rows.append({"note": path.name, "hits": hits,
                         "score": sum(1 + (1 if len(t) >= 4 else 0) for t in hits)})
    rows.sort(key=lambda r: -r["score"])
    return {"prompt": prompt, "selected": [p.name for p in detect_domains(prompt)], "candidates": rows}


def _excerpt(body: str, max_chars: int, prompt: str) -> str:
    """노트 본문에서 작업 관련 섹션만 발췌(relevance). 교착어 대응: 섹션의 토큰이
    프롬프트에 '부분매칭'되면 가점(라우팅과 동일 방식). 토큰 교집합은 '랜덤진동으로'≠
    '랜덤진동'처럼 조사 붙으면 깨진다."""
    if len(body) <= max_chars:
        return body
    low = (prompt or "").lower()
    # ## 뿐 아니라 ### 하위섹션도 개별 선택 가능하게 분할(교과서 깊이 노트에서 관련
    # 하위주제만 예산 내 주입 — 큰 ## 섹션이 통째로 안 맞아 skip되는 것 방지).
    blocks = re.split(r"(?m)^(?=#{2,} )", body)
    intro = blocks[0] if blocks else ""

    def _sc(b: str) -> int:
        # 섹션 '전체'의 토큰이 프롬프트에 포함되는 수 = 관련도. 긴 섹션에서 관련어가
        # 뒷부분(예: Paris 법칙이 §8 깊숙이)에 있어도 잡힌다. 헤더(첫 줄)는 가중.
        head = b.split("\n", 1)[0]
        score = sum(1 for t in _tokens(b) if len(t) >= 2 and t in low)
        score += sum(2 for t in _tokens(head) if len(t) >= 2 and t in low)  # 헤더 가중
        return score

    scored = sorted(((_sc(b), b) for b in blocks[1:]), key=lambda x: -x[0])
    out = intro
    for ov, b in scored:
        if ov <= 0 or len(out) + len(b) > max_chars:
            continue
        out += b
    return out[:max_chars]


def _moc_for(domain: str) -> Optional[str]:
    """도메인 MOC(지도) 본문 — 있으면."""
    if not domain:
        return None
    p = _MOC_DIR / f"{domain}.md"
    if p.exists():
        try:
            _m, body = _parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
            return body
        except Exception:
            return None
    return None


def context_for_prompt(prompt: str, max_chars: int = 2600) -> Optional[str]:
    """작업에 맞는 레퍼런스 지식을 system 주입 문자열로. 없으면 None.

    verified 노트 우선, draft는 '미검증' 꼬리표. MOC(지도)를 앞에 붙여 모델이
    '무엇이 있는지' 먼저 알게 한다."""
    notes = detect_domains(prompt, top=2)
    if not notes:
        return None
    seed_kb_vault()  # 첫 사용 시 knowledge/ 를 Obsidian vault 로 자동 준비(무개입)
    chunks: List[str] = []
    budget = max_chars
    seen_moc: set = set()
    for path in notes:
        try:
            meta, body = _parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        domain = meta.get("domain", "") or path.stem
        moc = _moc_for(domain)
        if moc and domain not in seen_moc:
            seen_moc.add(domain)
            m = moc[:min(len(moc), 500)]
            chunks.append(f"[지도: {domain}]\n{m}")
            budget -= len(m)
        verified = str(meta.get("verified", "")).lower() in ("true", "yes", "1")
        tag = "" if verified else " (미검증 draft — 확인 필요)"
        conf = meta.get("confidence", "")
        piece = _excerpt(body, max(500, budget // max(1, len(notes))), prompt)
        # 발췌마다 출처+수치경고를 헤더로 강제 노출(약한 모델이 하위섹션만 봐도 규약을
        # 잃지 않게). 프론트매터 numeric_claims:unverified는 본문 밖이라 발췌엔 안 실리므로
        # 여기서 붙인다(Fable 검토).
        src = meta.get("sources", "")
        src_hint = f" · 출처 {src.split(',')[0][:40]}" if src else ""
        num_warn = ""
        if str(meta.get("numeric_claims", "")).lower() == "unverified":
            num_warn = " · ⚠️수치·규격값은 원문/데이터시트 확인 필요"
        header = f"[{domain}{tag}{' · 신뢰도 ' + conf if conf else ''}{src_hint}{num_warn}]"
        chunks.append(f"{header}\n{piece}")
        budget -= len(piece)
        if budget <= 0:
            break
    if not chunks:
        return None
    intro = ("아래는 사내 레퍼런스 지식베이스 발췌다(공학 도메인·규격·실무). 사실·수치·규격은 "
             "여기 근거만 쓰고, 없거나 '미검증'이면 지어내지 말고 확인을 요청하라.\n\n")
    return intro + "\n\n---\n\n".join(chunks)


def seed_kb_vault() -> None:
    """knowledge/ 를 Obsidian vault 로 시드(.obsidian 없을 때만). 사용자가 레퍼런스
    지식 그래프를 Obsidian으로 브라우징할 수 있게 — 개인 기억 vault와 별개."""
    try:
        obs = KB_DIR / ".obsidian"
        if obs.exists():
            return
        import json
        obs.mkdir(parents=True, exist_ok=True)
        (obs / "core-plugins.json").write_text(json.dumps({
            "file-explorer": True, "global-search": True, "switcher": True,
            "graph": True, "backlink": True, "outgoing-link": True,
            "tag-pane": True, "page-preview": True, "outline": True,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        (obs / "community-plugins.json").write_text("[]", encoding="utf-8")
        (obs / "app.json").write_text(json.dumps({
            "useMarkdownLinks": False, "newLinkFormat": "shortest",
            "defaultViewMode": "preview",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        welcome = KB_DIR / "0-지식베이스-안내.md"
        if not welcome.exists():
            welcome.write_text(
                "# OpenCodeLIG 레퍼런스 지식베이스\n\n"
                "AI 조수의 **큐레이션된 사실 지식**(공학 도메인·규격·소프트웨어·소프트스킬).\n"
                "개인 기억(OpenCodeLIG_USERDATA)과 별개다.\n\n"
                "- `_moc/` 도메인 지도(무엇이 있는지) — 그래프 뷰로 연결이 보임\n"
                "- `domains/ standards/ lifeskills/ apis/` 주제 노트([[링크]]로 연결)\n"
                "- 각 노트 프론트매터의 verified/confidence/sources 로 신뢰도 확인\n\n"
                "여기서 직접 고치면 모델이 다음 작업에 그 근거를 씁니다.\n",
                encoding="utf-8")
    except Exception:
        pass


def kb_status() -> Dict[str, int]:
    """도메인/규격/스킬 노트 수 + verified 수(doctor/진단용)."""
    total = 0
    verified = 0
    for _p, meta, _b in _iter_notes():
        total += 1
        if str(meta.get("verified", "")).lower() in ("true", "yes", "1"):
            verified += 1
    mocs = len(list(_MOC_DIR.glob("*.md"))) if _MOC_DIR.is_dir() else 0
    return {"notes": total, "verified": verified, "mocs": mocs}


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 1:
        print(context_for_prompt(" ".join(sys.argv[1:])) or "(관련 지식 없음)")
    else:
        print(json.dumps(kb_status(), ensure_ascii=False, indent=2))
